import pandas as pd

from generator import generate_portfolios
from ranking import rank_portfolios
from simulator.cpi import fetch_cpi
from simulator.data import fetch_price_data
from simulator.guardrail import simulate_guardrail_withdrawal
from simulator.metrics import annual_volatility, cagr, max_drawdown
from simulator.monte_carlo import annual_returns, simulate_paths, survival_probability
from simulator.portfolio import simulate_portfolio
from simulator.retirement_score import retirement_score
from simulator.withdrawal import simulate_withdrawal

# "flat": fixed-rate proportional withdrawal across a swept set of ticker weights.
# "guardrail": QQQ/QLD/cash bucket strategy, swept across candidate cash buffer sizes.
WITHDRAWAL_STRATEGY = "flat"

TICKERS = ["QQQ", "QLD"]
START = "2000-01-01"
END = "2024-12-31"
REBALANCE_FREQ = "annual"
WITHDRAWAL_RATE = 0.04
ASSUMED_INFLATION_RATE = 0.03
RETIREMENT_YEARS = 30
NUM_SIMULATIONS = 200
SEED = 42
RESULTS_CSV = "results.csv"

# guardrail-strategy-only config
GUARDRAIL_GROWTH_TICKER = "QQQ"
GUARDRAIL_RESERVE_TICKER = "QLD"
GUARDRAIL_RESERVE_WEIGHT = 0.10
GUARDRAIL_CASH_YEARS_OPTIONS = list(range(1, 11))
GUARDRAIL_DOWN_THRESHOLD = 0.0  # a "down year" = the growth ticker's own return < this


def _evaluate_with_monte_carlo(value: pd.Series, withdrawal_value: pd.Series) -> dict:
    """Shared scoring: real-CPI historical survival gates whether Monte Carlo (future,
    assumed-inflation) is worth running at all."""
    portfolio_cagr = cagr(value)
    portfolio_mdd = max_drawdown(value)
    historical_survived = withdrawal_value.iloc[-1] > 0

    if historical_survived:
        returns = annual_returns(value)
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
        survival = 0.0

    return {
        "cagr": portfolio_cagr,
        "volatility": annual_volatility(value),
        "mdd": portfolio_mdd,
        "historical_survived": historical_survived,
        "survival_probability": survival,
        "retirement_score": retirement_score(survival, portfolio_cagr, portfolio_mdd),
    }


def run_flat_strategy(close: pd.DataFrame, dividends: pd.DataFrame, cpi: pd.Series) -> list[dict]:
    portfolios = generate_portfolios(TICKERS, step=10)
    print(f"Generated {len(portfolios)} portfolios from {TICKERS}\n")

    results = []
    for weights in portfolios:
        value = simulate_portfolio(close, dividends, weights, rebalance_freq=REBALANCE_FREQ)
        withdrawal_value = simulate_withdrawal(
            close, dividends, weights, withdrawal_rate=WITHDRAWAL_RATE, rebalance_freq=REBALANCE_FREQ, cpi=cpi
        )
        results.append({"weights": weights, **_evaluate_with_monte_carlo(value, withdrawal_value)})
    return results


def run_guardrail_strategy(close: pd.DataFrame, dividends: pd.DataFrame, cpi: pd.Series) -> list[dict]:
    print(
        f"Testing guardrail strategy: growth={GUARDRAIL_GROWTH_TICKER}, "
        f"reserve={GUARDRAIL_RESERVE_TICKER} ({GUARDRAIL_RESERVE_WEIGHT:.0%}, never sold), "
        f"cash_years in {GUARDRAIL_CASH_YEARS_OPTIONS}\n"
    )

    results = []
    for cash_years in GUARDRAIL_CASH_YEARS_OPTIONS:
        outcome = simulate_guardrail_withdrawal(
            close,
            dividends,
            GUARDRAIL_GROWTH_TICKER,
            GUARDRAIL_RESERVE_TICKER,
            reserve_weight=GUARDRAIL_RESERVE_WEIGHT,
            withdrawal_rate=WITHDRAWAL_RATE,
            cash_years=cash_years,
            down_threshold=GUARDRAIL_DOWN_THRESHOLD,
            cpi=cpi,
        )
        value = outcome["value"]
        historical_survived = value.iloc[-1] > 0
        portfolio_cagr = cagr(value)
        portfolio_mdd = max_drawdown(value)
        # Monte Carlo isn't wired up for the guardrail engine yet - it would need the
        # whole bucket state machine replayed per simulated path, not just a formula.
        # Report the historical-only outcome for now (1.0/0.0 survival, no probability).
        results.append(
            {
                "weights": {"cash_years": cash_years},
                "cagr": portfolio_cagr,
                "volatility": annual_volatility(value),
                "mdd": portfolio_mdd,
                "historical_survived": historical_survived,
                "survival_probability": 1.0 if historical_survived else 0.0,
                "retirement_score": retirement_score(
                    1.0 if historical_survived else 0.0, portfolio_cagr, portfolio_mdd
                ),
                "guardrail_failures": len(outcome["guardrail_failures"]),
            }
        )
    return results


def main():
    close, dividends = fetch_price_data(TICKERS, START, END)
    cpi = fetch_cpi(START, END)

    if WITHDRAWAL_STRATEGY == "flat":
        results = run_flat_strategy(close, dividends, cpi)
    elif WITHDRAWAL_STRATEGY == "guardrail":
        results = run_guardrail_strategy(close, dividends, cpi)
    else:
        raise ValueError(f"unknown WITHDRAWAL_STRATEGY: {WITHDRAWAL_STRATEGY!r}")

    ranked = rank_portfolios(results)

    df = pd.DataFrame([{**r["weights"], **{k: v for k, v in r.items() if k != "weights"}} for r in ranked])
    df.to_csv(RESULTS_CSV, index=False)
    print(f"Saved {len(df)} ranked results to {RESULTS_CSV}\n")

    print("Top 5 by Retirement Score:")
    for r in ranked[:5]:
        print(
            f"  {r['weights']}  Score={r['retirement_score']:.1f}  "
            f"HistSurvived={r['historical_survived']}  Survival={r['survival_probability']:.1%}  "
            f"CAGR={r['cagr']:.2%}  MDD={r['mdd']:.2%}"
        )


if __name__ == "__main__":
    main()
