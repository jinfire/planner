from data import fetch_price_data
from portfolio import simulate_portfolio
from metrics import cagr, annual_volatility, max_drawdown
from rebalance import REBALANCE_FREQUENCIES

TICKERS = ["QQQ", "SCHD"]
WEIGHTS = {"QQQ": 0.6, "SCHD": 0.4}
START = "2012-01-01"
END = "2024-12-31"


def main():
    close, dividends = fetch_price_data(TICKERS, START, END)

    print(f"Portfolio: {WEIGHTS}")
    print(f"Period: {START} ~ {END}\n")

    for freq in REBALANCE_FREQUENCIES:
        value = simulate_portfolio(close, dividends, WEIGHTS, rebalance_freq=freq)
        print(f"[rebalance={freq}]")
        print(f"  CAGR: {cagr(value):.2%}")
        print(f"  Annual Volatility: {annual_volatility(value):.2%}")
        print(f"  Max Drawdown: {max_drawdown(value):.2%}")


if __name__ == "__main__":
    main()
