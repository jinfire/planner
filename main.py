import multiprocessing as mp
import os
import time

import pandas as pd

from generator import generate_portfolios
from ranking import rank_portfolios
from simulator.cpi import fetch_cpi
from simulator.data import fetch_extended_series, intersect_tickers
from simulator.metrics import annual_volatility, cagr, max_drawdown, years_survived
from simulator.monte_carlo import annual_returns, simulate_paths, survival_probability
from simulator.retirement_score import retirement_score
from simulator.rolling_window import evaluate_perpetual_success, evaluate_rolling_window
from simulator.strategy import (
    BucketWithdrawalStrategy,
    ConstantWithdrawalStrategy,
    GuytonKlingerWithdrawalStrategy,
    WithdrawalStrategy,
)

# "flat", "bucket", "guyton_klinger", or "all" (run every strategy below and rank them together)
WITHDRAWAL_STRATEGY = "flat"

# How survival_probability is computed - only one of these is used, checked in this
# order:
# 1. USE_PERPETUAL: re-run starting at every historical year, each time simulating all
#    the way to the *end* of available data (a different length each time) - "would
#    this have lasted through today if I'd started withdrawing back then?" No fixed
#    retirement length is assumed; the answer for a given combo is only as good as
#    however much history that combo's own tickers allow (see data_years below).
# 2. USE_ROLLING_WINDOW: fixed ROLLING_WINDOW_YEARS-long windows, many start years.
# 3. Monte Carlo (RETIREMENT_YEARS, bootstrapped from this combo's own return
#    history), for strategies that can supply a pure-growth return series.
# 4. A binary survived/not-survived fallback otherwise.
USE_PERPETUAL = True
PERPETUAL_MIN_YEARS = 5.0  # ignore start years with less runway than this to the end

USE_ROLLING_WINDOW = False
ROLLING_WINDOW_YEARS = 20

TICKERS = [
    "SPY", "QQQ", "QLD", "TQQQ", "SSO", "UPRO",  # US large-cap / growth / leveraged
    "VTI", "SCHD", "NOBL",  # US total market / dividend growth / dividend aristocrats
    "VEA", "VWO",  # developed ex-US / emerging markets
    "TLT", "IEF", "BND",  # long/intermediate treasuries / aggregate bond
    "SGOV",  # cash-equivalent
    "GLD", "DBC",  # gold / broad commodities
]
GENERATOR_STEP = 20  # % increments between candidate weights
WITHDRAWAL_RATE_OPTIONS = [0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06]
START = "2000-01-01"
END = "2024-12-31"
REBALANCE_FREQ = "quarterly"
WITHDRAWAL_RATE = 0.04  # used by bucket/Monte Carlo paths, which don't sweep rates
ASSUMED_INFLATION_RATE = 0.03
RETIREMENT_YEARS = 30
NUM_SIMULATIONS = 200
SEED = 42
RESULTS_CSV = "results.csv"

# strategies are fully independent, so evaluate() calls are split across processes
# instead of running single-threaded - leaves 2 cores free for the OS/other apps
NUM_WORKERS = max(1, (os.cpu_count() or 4) - 2)
PROGRESS_EVERY = 2000  # print elapsed/ETA every N completed strategies

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
        ConstantWithdrawalStrategy(weights, rate, REBALANCE_FREQ)
        for weights in generate_portfolios(TICKERS, step=GENERATOR_STEP)
        for rate in WITHDRAWAL_RATE_OPTIONS
    ]


def build_guyton_klinger_strategies() -> list[GuytonKlingerWithdrawalStrategy]:
    return [
        GuytonKlingerWithdrawalStrategy(weights, rate, REBALANCE_FREQ)
        for weights in generate_portfolios(TICKERS, step=GENERATOR_STEP)
        for rate in WITHDRAWAL_RATE_OPTIONS
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

    See the USE_PERPETUAL/USE_ROLLING_WINDOW comment above for how survival_probability
    is computed."""
    close, dividends = intersect_tickers(universe, strategy.tickers)

    # full_cpi is passed through unsliced: cpi_adjusted_withdrawal resolves the first
    # withdrawal date via .asof(), which needs CPI history at or before that date.
    # Slicing to close.index.min() left no such entry (CPI ticks land on the 1st of
    # the month; a data series's first trading day never is), so .asof() returned NaN
    # and silently poisoned every subsequent value in the series.
    result = strategy.simulate(close, dividends, full_cpi)
    portfolio_cagr = cagr(result.value)
    portfolio_mdd = max_drawdown(result.value)
    survival_fraction = years_survived(result.value)
    final_value = result.value.iloc[-1]
    historical_survived = final_value > 0

    if USE_PERPETUAL:
        perpetual = evaluate_perpetual_success(strategy, close, dividends, full_cpi, PERPETUAL_MIN_YEARS)
        survival = perpetual["success_rate"]
    elif USE_ROLLING_WINDOW:
        rolling = evaluate_rolling_window(strategy, close, dividends, full_cpi, ROLLING_WINDOW_YEARS)
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

    withdrawal_rate = getattr(strategy, "withdrawal_rate", None) or getattr(strategy, "initial_withdrawal_rate", None)

    return {
        "weights": result.label,
        "withdrawal_rate": withdrawal_rate,
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


# Set once per worker process via Pool's initializer, instead of re-pickling universe/
# full_cpi (small but non-trivial - a couple thousand rows per ticker) on every single
# one of 183k+ tasks. Module-level so worker processes (which re-import this module
# under Windows' spawn start method) can find them by name when unpickling _evaluate_worker.
_worker_universe: dict | None = None
_worker_cpi: pd.Series | None = None


def _init_worker(universe: dict, full_cpi: pd.Series) -> None:
    global _worker_universe, _worker_cpi
    _worker_universe = universe
    _worker_cpi = full_cpi


def _evaluate_worker(strategy: WithdrawalStrategy) -> dict:
    return evaluate(strategy, _worker_universe, _worker_cpi)


def main():
    strategies = build_strategies()
    universe = fetch_extended_series(universe_tickers(strategies), START, END)
    full_cpi = fetch_cpi(START, END)
    print(
        f"Running {len(strategies)} strategy configuration(s) ({WITHDRAWAL_STRATEGY}) "
        f"across {NUM_WORKERS} worker processes\n"
    )

    results = []
    start_time = time.monotonic()
    with mp.Pool(NUM_WORKERS, initializer=_init_worker, initargs=(universe, full_cpi)) as pool:
        for i, result in enumerate(pool.imap_unordered(_evaluate_worker, strategies, chunksize=20), 1):
            results.append(result)
            if i % PROGRESS_EVERY == 0 or i == len(strategies):
                elapsed = time.monotonic() - start_time
                rate = i / elapsed
                eta_min = (len(strategies) - i) / rate / 60 if rate > 0 else float("inf")
                print(f"  {i}/{len(strategies)} done - {elapsed / 60:.1f}min elapsed, ETA {eta_min:.1f}min ({rate:.1f}/s)")

    ranked = rank_portfolios(results)

    df = pd.DataFrame([{**r["weights"], **{k: v for k, v in r.items() if k != "weights"}} for r in ranked])
    df.to_csv(RESULTS_CSV, index=False)
    print(f"Saved {len(df)} ranked results to {RESULTS_CSV}\n")

    print("Top 5 by Retirement Score:")
    for r in ranked[:5]:
        print(
            f"  {r['weights']}  Rate={r['withdrawal_rate']:.1%}  Score={r['retirement_score']:.1f}  "
            f"HistSurvived={r['historical_survived']}  Survival={r['survival_probability']:.1%}  "
            f"CAGR={r['cagr']:.2%}  MDD={r['mdd']:.2%}  "
            f"TotalReturn={r['total_return_pct']:.1f}%  FinalValue={r['final_value']:.3f}x  "
            f"Data={r['data_start']}~ ({r['data_years']}y)"
        )


if __name__ == "__main__":
    main()
