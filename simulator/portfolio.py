import numpy as np
import pandas as pd

from .rebalance import rebalance_dates


def simulate_portfolio(
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    weights: dict[str, float],
    rebalance_freq: str = "none",
    initial_capital: float = 1.0,
) -> pd.Series:
    """Share-based portfolio simulation with dividend reinvestment and periodic
    rebalancing.

    Vectorized per rebalance segment instead of a day-by-day Python loop: between two
    rebalance dates, share counts only move via dividend reinvestment, which is a
    per-ticker cumulative product - cheap to compute over a whole segment at once with
    numpy. The Python loop only runs once per rebalance date (dozens to low hundreds
    of times), not once per trading day (thousands of times)."""
    tickers = list(weights.keys())
    dates = close.index
    rebal_dates = rebalance_dates(dates, rebalance_freq)
    weight_arr = pd.Series(weights, index=tickers).to_numpy()

    price = close[tickers].to_numpy()
    growth_factor = 1 + (dividends[tickers] / close[tickers]).to_numpy()

    segment_ends = [i for i, d in enumerate(dates) if d in rebal_dates]
    if not segment_ends or segment_ends[-1] != len(dates) - 1:
        segment_ends.append(len(dates) - 1)

    values = np.empty(len(dates))
    shares = weight_arr * initial_capital / price[0]

    start = 0
    for end in segment_ends:
        cum_growth = growth_factor[start : end + 1].cumprod(axis=0)
        seg_shares = shares * cum_growth
        seg_price = price[start : end + 1]
        seg_values = (seg_shares * seg_price).sum(axis=1)
        values[start : end + 1] = seg_values

        shares = weight_arr * seg_values[-1] / seg_price[-1]
        start = end + 1

    return pd.Series(values, index=dates)
