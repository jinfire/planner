import pandas as pd

from generator import generate_portfolios
from ranking import rank_portfolios
from simulator.data import fetch_price_data
from simulator.metrics import annual_volatility, cagr, max_drawdown
from simulator.monte_carlo import annual_returns, simulate_paths, survival_probability
from simulator.portfolio import simulate_portfolio
from simulator.retirement_score import retirement_score

TICKERS = ["QQQ", "SCHD", "TLT"]
START = "2012-01-01"
END = "2024-12-31"
REBALANCE_FREQ = "annual"
WITHDRAWAL_RATE = 0.04
ASSUMED_INFLATION_RATE = 0.03
RETIREMENT_YEARS = 30
NUM_SIMULATIONS = 200
SEED = 42
RESULTS_CSV = "results.csv"


def main():
    close, dividends = fetch_price_data(TICKERS, START, END)
    portfolios = generate_portfolios(TICKERS, step=10)
    print(f"Generated {len(portfolios)} portfolios from {TICKERS}\n")

    results = []
    for weights in portfolios:
        value = simulate_portfolio(close, dividends, weights, rebalance_freq=REBALANCE_FREQ)
        portfolio_cagr = cagr(value)
        portfolio_mdd = max_drawdown(value)

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

        results.append(
            {
                "weights": weights,
                "cagr": portfolio_cagr,
                "volatility": annual_volatility(value),
                "mdd": portfolio_mdd,
                "survival_probability": survival,
                "retirement_score": retirement_score(survival, portfolio_cagr, portfolio_mdd),
            }
        )

    ranked = rank_portfolios(results)

    df = pd.DataFrame([{**r["weights"], **{k: v for k, v in r.items() if k != "weights"}} for r in ranked])
    df.to_csv(RESULTS_CSV, index=False)
    print(f"Saved {len(df)} ranked portfolios to {RESULTS_CSV}\n")

    print("Top 5 by Retirement Score:")
    for r in ranked[:5]:
        print(
            f"  {r['weights']}  Score={r['retirement_score']:.1f}  "
            f"Survival={r['survival_probability']:.1%}  CAGR={r['cagr']:.2%}  MDD={r['mdd']:.2%}"
        )


if __name__ == "__main__":
    main()
