import warnings

import yfinance as yf
import pandas as pd

from .backfill import extend_close_series, reaches_start


def fetch_price_data(tickers: list[str], start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (close_prices, dividends_per_share), unadjusted, aligned on the same date
    index. A ticker whose real data doesn't reach `start` is backfilled via
    simulator.backfill (leverage replication, then index proxy, then a similar older
    fund - whichever applies first); if none apply, it's left truncated to its real
    start and a warning is raised."""
    raw = yf.download(tickers, start=start, end=end, auto_adjust=False, actions=True)
    close = raw["Close"]
    dividends = raw["Dividends"]
    start_ts = pd.Timestamp(start)

    def fetch_close(other_ticker: str):
        if other_ticker in close.columns:
            return close[other_ticker].dropna()
        other_raw = yf.download(other_ticker, start=start, end=end, auto_adjust=False)
        if other_raw.empty:
            return None
        other_close = other_raw["Close"]
        if isinstance(other_close, pd.DataFrame):
            other_close = other_close[other_ticker]
        return other_close.dropna()

    extended = {}
    for ticker in tickers:
        series = close[ticker].dropna()
        if not reaches_start(series, start_ts):
            series = extend_close_series(ticker, start_ts, series, fetch_close)
            if not reaches_start(series, start_ts):
                warnings.warn(
                    f"No historical extension available for {ticker}; "
                    f"data starts {series.index.min().date()} instead of {start_ts.date()}"
                )
        extended[ticker] = series

    close_df = pd.DataFrame(extended).dropna()
    dividends_df = dividends.reindex(close_df.index).fillna(0.0)[tickers]
    return close_df, dividends_df
