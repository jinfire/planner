import pandas as pd

from generator import generate_portfolios
from ranking import rank_portfolios
from simulator.cpi import fetch_cpi
from simulator.data import fetch_price_data
from simulator.metrics import annual_volatility, cagr, max_drawdown, years_survived
from simulator.monte_carlo import annual_returns, simulate_paths, survival_probability
from simulator.retirement_score import retirement_score
from simulator.strategy import (
    BucketWithdrawalStrategy,
    ConstantWithdrawalStrategy,
    GuytonKlingerWithdrawalStrategy,
    WithdrawalResult,
)

# "flat", "bucket", "guyton_klinger", or "all" (run every strategy below and rank them together)
WITHDRAWAL_STRATEGY = "flat"

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


def required_tickers() -> list[str]:
    """Union of every ticker any active strategy needs, so fetch_price_data always
    covers whichever strategy/strategies WITHDRAWAL_STRATEGY selects."""
    tickers = set(TICKERS)
    if WITHDRAWAL_STRATEGY in ("bucket", "all"):
        tickers |= {BUCKET_GROWTH_TICKER, BUCKET_RESERVE_TICKER}
    return sorted(tickers)


def evaluate(result: WithdrawalResult) -> dict:
    """CAGR/MDD/survival are all judged from `result.value` - the balance a retiree
    would actually see - so every strategy is scored on the same footing regardless of
    how differently it's shaped internally. Monte Carlo only runs for strategies that
    can supply a pure-growth return series to bootstrap from; the rest fall back to a
    binary survived/not-survived score."""
    portfolio_cagr = cagr(result.value)
    portfolio_mdd = max_drawdown(result.value)
    survival_fraction = years_survived(result.value)
    final_value = result.value.iloc[-1]
    historical_survived = final_value > 0

    if historical_survived and result.monte_carlo_returns is not None:
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
        "retirement_score": retirement_score(survival, portfolio_cagr, portfolio_mdd, survival_fraction),
        **result.extra,
    }


def main():
    close, dividends = fetch_price_data(required_tickers(), START, END)
    cpi = fetch_cpi(START, END)

    strategies = build_strategies()
    print(f"Running {len(strategies)} strategy configuration(s) ({WITHDRAWAL_STRATEGY})\n")

    results = [evaluate(strategy.simulate(close, dividends, cpi)) for strategy in strategies]
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
            f"TotalReturn={r['total_return_pct']:.1f}%  FinalValue={r['final_value']:.3f}x"
        )


if __name__ == "__main__":
    main()
