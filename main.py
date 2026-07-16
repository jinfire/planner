from generator import generate_portfolios
from simulator.data import fetch_price_data
from simulator.portfolio import simulate_portfolio
from simulator.metrics import cagr, annual_volatility, max_drawdown

TICKERS = ["QQQ", "SCHD", "TLT"]
START = "2012-01-01"
END = "2024-12-31"
REBALANCE_FREQ = "annual"


def main():
    close, dividends = fetch_price_data(TICKERS, START, END)
    portfolios = generate_portfolios(TICKERS, step=10)
    print(f"Generated {len(portfolios)} portfolios from {TICKERS}\n")

    results = []
    for weights in portfolios:
        value = simulate_portfolio(close, dividends, weights, rebalance_freq=REBALANCE_FREQ)
        results.append(
            {
                "weights": weights,
                "cagr": cagr(value),
                "volatility": annual_volatility(value),
                "mdd": max_drawdown(value),
            }
        )

    results.sort(key=lambda r: r["cagr"], reverse=True)

    print("Top 5 by CAGR:")
    for r in results[:5]:
        print(f"  {r['weights']}  CAGR={r['cagr']:.2%}  Vol={r['volatility']:.2%}  MDD={r['mdd']:.2%}")


if __name__ == "__main__":
    main()
