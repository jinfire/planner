import yfinance as yf
import pandas as pd


def fetch_price_data(tickers: list[str], start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (close_prices, dividends_per_share), unadjusted, aligned on the same date index."""
    raw = yf.download(tickers, start=start, end=end, auto_adjust=False, actions=True)
    close = raw["Close"].dropna()
    dividends = raw["Dividends"].reindex(close.index).fillna(0.0)
    return close, dividends
