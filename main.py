import pandas as pd

from generator import generate_portfolios
from ranking import rank_portfolios
from simulator.cpi import fetch_cpi
from simulator.data import fetch_extended_series, intersect_tickers
from simulator.metrics import annual_volatility, cagr, max_drawdown, years_survived
from simulator.monte_carlo import annual_returns, simulate_paths, survival_probability
from simulator.retirement_score import retirement_score
from simulator.rolling_window import evaluate_rolling_window
from simulator.strategy import (
    BucketWithdrawalStrategy,
    ConstantWithdrawalStrategy,
    GuytonKlingerWithdrawalStrategy,
    WithdrawalStrategy,
)

# "flat", "bucket", "guyton_klinger", or "all" (run every strategy below and rank them together)
WITHDRAWAL_STRATEGY = "flat"

# If True, survival_probability comes from re-running each strategy across every
# rolling `ROLLING_WINDOW_YEARS`-long historical start year and taking the success
# rate, instead of a single fixed start date (2000) plus Monte Carlo. A strategy that
# only looks good because it happened to dodge 2000's crash won't get away with it.
USE_ROLLING_WINDOW = False
ROLLING_WINDOW_YEARS = 20

TICKERS = ["SPY", "QQQ", "QLD", "TLT", "IEF", "SGOV"]
GENERATOR_STEP = 20  # % increments between candidate weights
START = "2000-01-01"
END = "2024-12-31"
REBALANCE_FREQ = "quarterly"
WITHDRAWAL_RATE = 0.04
ASSUMED_INFLATION_RATE = 0.03
RETIREMENT_YEARS = 30
NUM_SIMULATIONS = 200
SEED = 42
RESULTS_CSV = "results.csv"

# How much each factor moves retirement_score (see simulator.retirement_score) -
# tune to taste, there's no universally "correct" answer here. Defaults below assume
# retirement (not accumulation): not running out of money matters far more than
# growth, since growth mainly matters *indirectly* - a bigger balance lowers your
# effective withdrawal rate and de-risks everything else. So survival dominates,
# growth is a minor bonus, and MDD still counts a lot since a scary drawdown is
# exactly what threatens survival under a fixed withdrawal rate.
SCORE_SURVIVAL_WEIGHT = 100.0
SCORE_GROWTH_WEIGHT = 20.0
SCORE_RISK_WEIGHT = 50.0
SCORE_LONGEVITY_WEIGHT = 10.0

# bucket-strategy-only config
BUCKET_GROWTH_TICKER = "QQQ"
BUCKET_RESERVE_TICKER = "QLD"
BUCKET_RESERVE_WEIGHT = 0.10
BUCKET_CASH_YEARS_OPTIONS = list(range(1, 11))
BUCKET_DOWN_THRESHOLD = 0.0  # a "down year" = the growth ticker's own return < this


def build_flat_strategies() -> list[ConstantWithdrawalStrategy]:
    return [
        ConstantWithdrawalStrategy(weights, WITHDRAWAL_RATE, REBALANCE_FREQ)
        for weights in generate_portfolios(TICKERS, step=GENERATOR_STEP)
    ]


def build_guyton_klinger_strategies() -> list[GuytonKlingerWithdrawalStrategy]:
    return [
        GuytonKlingerWithdrawalStrategy(weights, WITHDRAWAL_RATE, REBALANCE_FREQ)
        for weights in generate_portfolios(TICKERS, step=GENERATOR_STEP)
    ]


def build_bucket_strategies() -> list[BucketWithdrawalStrategy]:
    return [
        BucketWithdrawalStrategy(
            BUCKET_GROWTH_TICKER,
            BUCKET_RESERVE_TICKER,
            BUCKET_RESERVE_WEIGHT,
            WITHDRAWAL_RATE,
            cash_years,
            BUCKET_DOWN_THRESHOLD,
        )
        for cash_years in BUCKET_CASH_YEARS_OPTIONS
    ]


STRATEGY_BUILDERS = {
    "flat": build_flat_strategies,
    "guyton_klinger": build_guyton_klinger_strategies,
    "bucket": build_bucket_strategies,
}


def build_strategies() -> list:
    if WITHDRAWAL_STRATEGY == "all":
        return [strategy for builder in STRATEGY_BUILDERS.values() for strategy in builder()]
    if WITHDRAWAL_STRATEGY not in STRATEGY_BUILDERS:
        raise ValueError(f"unknown WITHDRAWAL_STRATEGY: {WITHDRAWAL_STRATEGY!r}")
    return STRATEGY_BUILDERS[WITHDRAWAL_STRATEGY]()


def universe_tickers(strategies: list[WithdrawalStrategy]) -> list[str]:
    """Union of every ticker any strategy in `strategies` needs, so the universe fetch
    covers all of them. Each strategy still only gets intersected down to its own
    `.tickers` later - this is just what to fetch once, up front."""
    tickers: set[str] = set()
    for strategy in strategies:
        tickers |= set(strategy.tickers)
    return sorted(tickers)


def evaluate(strategy: WithdrawalStrategy, universe: dict, full_cpi: pd.Series) -> dict:
    """Each strategy gets data intersected down to only *its own* active tickers, so
    a combo that includes a short-history asset (e.g. QLD) doesn't force a combo that
    doesn't need it (e.g. SPY+TLT only) down to the same short window - different
    combos legitimately get different amounts of history to backtest over.

    CAGR/MDD/survival are all judged from `result.value` - the balance a retiree
    would actually see - so every strategy is scored on the same footing regardless of
    how differently it's shaped internally.

    survival_probability comes from one of three sources, in priority order: (1) the
    rolling-window success rate across every historical start year this combo's own
    data range allows, if USE_ROLLING_WINDOW is on - the most grounded estimate, since
    it's built from many real sequences rather than one fixed start date or synthetic
    resampling; (2) Monte Carlo, for strategies that can supply a pure-growth return
    series to bootstrap from; (3) a binary survived/not-survived fallback otherwise."""
    close, dividends = intersect_tickers(universe, strategy.tickers)
    cpi = full_cpi.loc[close.index.min() : close.index.max()]

    result = strategy.simulate(close, dividends, cpi)
    portfolio_cagr = cagr(result.value)
    portfolio_mdd = max_drawdown(result.value)
    survival_fraction = years_survived(result.value)
    final_value = result.value.iloc[-1]
    historical_survived = final_value > 0

    if USE_ROLLING_WINDOW:
        rolling = evaluate_rolling_window(strategy, close, dividends, cpi, ROLLING_WINDOW_YEARS)
        survival = rolling["success_rate"]
    elif historical_survived and result.monte_carlo_returns is not None:
        returns = annual_returns(result.monte_carlo_returns)
        final_values = simulate_paths(
            returns,
            years=RETIREMENT_YEARS,
            withdrawal_rate=WITHDRAWAL_RATE,
            inflation_rate=ASSUMED_INFLATION_RATE,
            num_simulations=NUM_SIMULATIONS,
            seed=SEED,
        )
        survival = survival_probability(final_values)
    else:
        survival = 1.0 if historical_survived else 0.0

    return {
        "weights": result.label,
        "cagr": portfolio_cagr,
        "volatility": annual_volatility(result.value),
        "mdd": portfolio_mdd,
        "historical_survived": historical_survived,
        "survival_probability": survival,
        "years_survived": survival_fraction,
        "final_value": final_value,
        "total_return_pct": (final_value - 1) * 100,
        "data_start": close.index.min().date().isoformat(),
        "data_years": round((close.index.max() - close.index.min()).days / 365.25, 1),
        "retirement_score": retirement_score(
            survival,
            portfolio_cagr,
            portfolio_mdd,
            survival_fraction,
            survival_weight=SCORE_SURVIVAL_WEIGHT,
            growth_weight=SCORE_GROWTH_WEIGHT,
            risk_weight=SCORE_RISK_WEIGHT,
            longevity_weight=SCORE_LONGEVITY_WEIGHT,
        ),
        **result.extra,
    }


def main():
    strategies = build_strategies()
    universe = fetch_extended_series(universe_tickers(strategies), START, END)
    full_cpi = fetch_cpi(START, END)
    print(f"Running {len(strategies)} strategy configuration(s) ({WITHDRAWAL_STRATEGY})\n")

    results = [evaluate(strategy, universe, full_cpi) for strategy in strategies]
    ranked = rank_portfolios(results)

    df = pd.DataFrame([{**r["weights"], **{k: v for k, v in r.items() if k != "weights"}} for r in ranked])
    df.to_csv(RESULTS_CSV, index=False)
    print(f"Saved {len(df)} ranked results to {RESULTS_CSV}\n")

    print("Top 5 by Retirement Score:")
    for r in ranked[:5]:
        print(
            f"  {r['weights']}  Score={r['retirement_score']:.1f}  "
            f"HistSurvived={r['historical_survived']}  Survival={r['survival_probability']:.1%}  "
            f"CAGR={r['cagr']:.2%}  MDD={r['mdd']:.2%}  "
            f"TotalReturn={r['total_return_pct']:.1f}%  FinalValue={r['final_value']:.3f}x  "
            f"Data={r['data_start']}~ ({r['data_years']}y)"
        )


if __name__ == "__main__":
    main()
