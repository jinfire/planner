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

# Bond ETF -> (FRED constant-maturity yield series, approximate effective duration in
# years). Reconstructs a total-return price series from the yield history - see
# replicate_from_treasury_yield. Duration is a fixed approximation (real funds' actual
# duration drifts with the market), not a time-varying model.
YIELD_DURATION_REPLICATION: dict[str, tuple[str, float]] = {
    "TLT": ("DGS20", 17.0),
    "IEF": ("DGS10", 7.5),
}

# Cash-like ETF -> FRED T-bill yield series. Reconstructs a price series that's pure
# daily carry (no rate-sensitivity term - duration is short enough to be negligible).
TBILL_REPLICATION: dict[str, str] = {
    "SGOV": "DTB3",
    "BIL": "DTB3",
}

# ETF -> a freely available index/futures ticker that approximates its price
# benchmark.
INDEX_PROXY: dict[str, str] = {
    "QQQ": "^NDX",
    "SPY": "^GSPC",
    "DIA": "^DJI",
    "IWM": "^RUT",
    "GLD": "GC=F",  # gold futures continuous contract, back to 2000-08
}

# ETF -> a similar, longer-history fund to splice in before the real ETF's inception.
SPLICE_PROXY: dict[str, str] = {
    "SCHD": "VYM",  # both track high-dividend-yield US equity baskets
    "VTI": "SPY",  # VTI adds small/mid caps SPY lacks, but both are broad US market
    "NOBL": "DVY",  # both dividend-focused US equity ETFs
    "VEA": "EFA",  # both track MSCI EAFE (developed ex-US)
    "VWO": "EEM",  # both track MSCI Emerging Markets
    "BND": "AGG",  # both track the Bloomberg US Aggregate Bond index
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


def replicate_from_treasury_yield(yield_pct: pd.Series, duration: float) -> pd.Series:
    """Approximate a treasury bond ETF's total-return price series from a constant-
    maturity yield history (e.g. FRED's DGS20), using a simple duration model:
    daily_return ~= -duration * (change in yield) + (yield / 365) carry. `yield_pct`
    is in percent (FRED's convention, e.g. 4.5 for 4.5%). Normalized to 1.0 at the
    first date; the caller (splice_series) rescales it to chain into the real ETF's
    actual price level."""
    yield_decimal = yield_pct / 100
    delta_yield = yield_decimal.diff()
    daily_carry = yield_decimal.shift(1) / 365
    daily_return = -duration * delta_yield + daily_carry
    daily_return.iloc[0] = 0.0
    return (1 + daily_return).cumprod()


def replicate_from_tbill_yield(yield_pct: pd.Series) -> pd.Series:
    """Approximate a T-bill/cash ETF's total-return price series from a short-term
    yield history (e.g. FRED's DTB3): pure daily carry, no rate-sensitivity term since
    duration is short enough to be negligible. `yield_pct` is in percent."""
    yield_decimal = yield_pct / 100
    daily_return = yield_decimal.shift(1) / 365
    daily_return.iloc[0] = 0.0
    return (1 + daily_return).cumprod()


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


def _leverage_replication_tier(ticker, fetch_close, fetch_fred):
    if ticker not in LEVERAGE_REPLICATION:
        return None
    base_ticker, multiplier, expense_ratio = LEVERAGE_REPLICATION[ticker]
    base_close = fetch_close(base_ticker)
    if base_close is None:
        return None
    return replicate_leverage(base_close, multiplier, expense_ratio)


def _yield_duration_tier(ticker, fetch_close, fetch_fred):
    if ticker not in YIELD_DURATION_REPLICATION or fetch_fred is None:
        return None
    series_id, duration = YIELD_DURATION_REPLICATION[ticker]
    yield_series = fetch_fred(series_id)
    if yield_series is None:
        return None
    return replicate_from_treasury_yield(yield_series, duration)


def _tbill_tier(ticker, fetch_close, fetch_fred):
    if ticker not in TBILL_REPLICATION or fetch_fred is None:
        return None
    yield_series = fetch_fred(TBILL_REPLICATION[ticker])
    if yield_series is None:
        return None
    return replicate_from_tbill_yield(yield_series)


def _index_proxy_tier(ticker, fetch_close, fetch_fred):
    if ticker not in INDEX_PROXY:
        return None
    return fetch_close(INDEX_PROXY[ticker])


def _splice_proxy_tier(ticker, fetch_close, fetch_fred):
    if ticker not in SPLICE_PROXY:
        return None
    return fetch_close(SPLICE_PROXY[ticker])


# Tried in order, most rigorous/formulaic first, least rigorous (generic fund
# substitution) last.
_TIERS = (
    _leverage_replication_tier,
    _yield_duration_tier,
    _tbill_tier,
    _index_proxy_tier,
    _splice_proxy_tier,
)


def extend_close_series(
    ticker: str, start: pd.Timestamp, real: pd.Series, fetch_close, fetch_fred=None
) -> pd.Series:
    """Backfill `real` (a ticker's actual close series) towards `start` using, in
    priority order: (1) formulaic leverage replication, (2) treasury-yield duration
    replication, (3) T-bill yield replication, (4) a tracked-index/futures proxy,
    (5) a similar older fund spliced in. `fetch_close(other_ticker) -> pd.Series|None`
    fetches another ticker's close series; `fetch_fred(series_id) -> pd.Series|None`
    fetches a FRED economic series (tiers 2-3 are skipped if not given).

    Each method is applied if it pushes the series back further than what's already
    been assembled, even if it still doesn't fully reach `start` - e.g. SCHD (2011)
    spliced with VYM (2006) is an improvement worth keeping even though VYM itself
    doesn't reach back to a `start` of 2000. Falls through to the next method once the
    combined result is close enough to `start`, and returns whatever was assembled
    (still truncated, if nothing fully closed the gap)."""
    result = real

    for tier in _TIERS:
        if reaches_start(result, start):
            break

        proxy_close = tier(ticker, fetch_close, fetch_fred)
        if proxy_close is not None and proxy_close.index.min() < result.index.min():
            result = splice_series(proxy_close, result)

    return result
