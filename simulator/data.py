import warnings

import yfinance as yf
import pandas as pd

from .backfill import extend_close_series, reaches_start
from .fred_data import fetch_fred_series


def fetch_extended_series(tickers: list[str], start: str, end: str) -> dict[str, tuple[pd.Series, pd.Series]]:
    """Per-ticker (close_prices, dividends_per_share), each individually backfilled as
    far as possible via simulator.backfill - NOT intersected across tickers, so a
    short-history ticker (e.g. QLD) doesn't drag a long-history one (e.g. SPY) down.
    Use `intersect_tickers` to combine a chosen subset for a specific portfolio -
    different subsets naturally end up with different usable date ranges depending on
    which tickers are involved. A ticker that can't be backfilled all the way to
    `start` is left truncated to its real (or best-effort extended) start, with a
    warning."""
    raw = yf.download(tickers, start=start, end=end, auto_adjust=False, actions=True)
    close = raw["Close"]
    dividends = raw["Dividends"]
    start_ts = pd.Timestamp(start)

    def fetch_fred(series_id: str):
        series = fetch_fred_series(series_id, start, end)
        return series if not series.empty else None

    def fetch_close(other_ticker: str, _seen: frozenset[str] = frozenset()):
        # A backfill source (base/proxy ticker) can itself have a backfill mapping -
        # e.g. QLD's base QQQ can be extended via ^NDX - so extend recursively before
        # handing it back. `_seen` guards against cycles between mappings.
        if other_ticker in _seen:
            return None
        _seen = _seen | {other_ticker}

        if other_ticker in close.columns:
            series = close[other_ticker].dropna()
        else:
            other_raw = yf.download(other_ticker, start=start, end=end, auto_adjust=False)
            if other_raw.empty:
                return None
            other_close = other_raw["Close"]
            if isinstance(other_close, pd.DataFrame):
                other_close = other_close[other_ticker]
            series = other_close.dropna()

        if not reaches_start(series, start_ts):
            series = extend_close_series(
                other_ticker, start_ts, series, lambda t: fetch_close(t, _seen), fetch_fred
            )
        return series

    result = {}
    for ticker in tickers:
        series = close[ticker].dropna()
        if not reaches_start(series, start_ts):
            series = extend_close_series(ticker, start_ts, series, fetch_close, fetch_fred)
            if not reaches_start(series, start_ts):
                warnings.warn(
                    f"No historical extension available for {ticker}; "
                    f"data starts {series.index.min().date()} instead of {start_ts.date()}"
                )
        div_series = dividends[ticker].reindex(series.index).fillna(0.0)
        result[ticker] = (series, div_series)

    return result


def intersect_tickers(
    series_by_ticker: dict[str, tuple[pd.Series, pd.Series]], tickers: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Close/dividend DataFrames for just `tickers`, aligned on their common dates -
    the usable date range for this particular subset, which may differ from what any
    single ticker in it (or a different subset) could reach on its own."""
    close_df = pd.DataFrame({t: series_by_ticker[t][0] for t in tickers}).dropna()
    dividends_df = pd.DataFrame({t: series_by_ticker[t][1] for t in tickers}).reindex(close_df.index).fillna(0.0)
    return close_df, dividends_df


def fetch_price_data(tickers: list[str], start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (close_prices, dividends_per_share), unadjusted, aligned on the same date
    index across all of `tickers`. See fetch_extended_series for how each ticker is
    individually backfilled before being intersected."""
    series_by_ticker = fetch_extended_series(tickers, start, end)
    return intersect_tickers(series_by_ticker, tickers)
