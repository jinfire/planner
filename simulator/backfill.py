import pandas as pd

# Trading calendars have no data on weekends/holidays, so a series "starting" a few
# days after a requested calendar `start` (e.g. start=Jan 1) still counts as covering
# it. Used wherever we check whether a series reaches back far enough.
START_TOLERANCE = pd.Timedelta(days=10)


def reaches_start(series: pd.Series, start: pd.Timestamp) -> bool:
    return series.index.min() <= start + START_TOLERANCE


# Leveraged/inverse ETFs whose daily return is a well-defined formula of a base
# ticker: ticker -> (base_ticker, daily leverage multiplier, annual expense ratio).
LEVERAGE_REPLICATION: dict[str, tuple[str, float, float]] = {
    "QLD": ("QQQ", 2.0, 0.0095),
    "TQQQ": ("QQQ", 3.0, 0.0086),
    "SSO": ("SPY", 2.0, 0.0091),
    "UPRO": ("SPY", 3.0, 0.0091),
}

# ETF -> a freely available index ticker that approximates its price benchmark.
INDEX_PROXY: dict[str, str] = {
    "QQQ": "^NDX",
    "SPY": "^GSPC",
    "DIA": "^DJI",
    "IWM": "^RUT",
}

# ETF -> a similar, longer-history fund to splice in before the real ETF's inception.
SPLICE_PROXY: dict[str, str] = {
    "SCHD": "VYM",
}


def replicate_leverage(base_close: pd.Series, multiplier: float, expense_ratio: float) -> pd.Series:
    """Synthesize a leveraged/inverse ETF's total-return price series from its base
    ticker's daily returns: daily_return * multiplier, minus the expense ratio's daily
    drag. Normalized to 1.0 at the first date; the caller (splice_series) rescales it
    to chain into the real ETF's actual price level."""
    daily_returns = base_close.pct_change()
    daily_expense = expense_ratio / 252
    leveraged_returns = daily_returns * multiplier - daily_expense
    leveraged_returns.iloc[0] = 0.0  # no return (and no expense drag) on the first day
    return (1 + leveraged_returns).cumprod()


def splice_series(proxy: pd.Series, real: pd.Series) -> pd.Series:
    """Backfill `real` with `proxy`'s history before real's start date. The proxy
    segment is chain-linked (rescaled) so its last value equals real's first value,
    preserving the proxy's day-to-day % moves. Assumes `proxy` is (approximately) a
    total-return series; if it's price-only (e.g. a plain index), pre-inception
    dividends are effectively treated as 0 - an accepted approximation."""
    real_start = real.index.min()
    pre = proxy[proxy.index < real_start]
    if pre.empty:
        return real

    pre_price = pre / pre.iloc[0]
    scale = real.iloc[0] / pre_price.iloc[-1]
    return pd.concat([pre_price * scale, real])


def extend_close_series(ticker: str, start: pd.Timestamp, real: pd.Series, fetch_close) -> pd.Series:
    """Backfill `real` (a ticker's actual close series) towards `start` using, in
    priority order: (1) formulaic leverage replication, (2) a tracked-index proxy,
    (3) a similar older fund spliced in. `fetch_close(other_ticker) -> pd.Series | None`
    fetches another ticker's close series.

    Each method is applied if it pushes the series back further than what's already
    been assembled, even if it still doesn't fully reach `start` - e.g. SCHD (2011)
    spliced with VYM (2006) is an improvement worth keeping even though VYM itself
    doesn't reach back to a `start` of 2000. Falls through to the next method once the
    combined result is close enough to `start`, and returns whatever was assembled
    (still truncated, if nothing fully closed the gap)."""
    result = real

    for proxy_map, replicate in (
        (LEVERAGE_REPLICATION, True),
        (INDEX_PROXY, False),
        (SPLICE_PROXY, False),
    ):
        if reaches_start(result, start):
            break
        if ticker not in proxy_map:
            continue

        if replicate:
            base_ticker, multiplier, expense_ratio = proxy_map[ticker]
            base_close = fetch_close(base_ticker)
            proxy_close = (
                replicate_leverage(base_close, multiplier, expense_ratio)
                if base_close is not None
                else None
            )
        else:
            proxy_close = fetch_close(proxy_map[ticker])

        if proxy_close is not None and proxy_close.index.min() < result.index.min():
            result = splice_series(proxy_close, result)

    return result
