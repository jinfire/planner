import numpy as np
import pandas as pd

from .cpi import cpi_adjusted_withdrawal
from .inflation import inflation_adjusted_withdrawal
from .rebalance import rebalance_dates


def simulate_constant_withdrawal(
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    weights: dict[str, float],
    withdrawal_rate: float,
    rebalance_freq: str = "annual",
    initial_capital: float = 1.0,
    inflation_rate: float = 0.0,
    cpi: pd.Series | None = None,
) -> pd.Series:
    """Share-based simulation with dividend reinvestment, periodic rebalancing, and a
    withdrawal (initial_capital * withdrawal_rate) taken on the first trading day of
    every year. Once the portfolio can't cover a withdrawal, value is floored at 0 for
    the rest of the series.

    The withdrawal amount grows each year so its purchasing power stays constant:
    if `cpi` (an actual CPI index series, see cpi.fetch_cpi) is given, it's used to
    track real inflation over the backtest period; otherwise the withdrawal grows by
    the assumed `inflation_rate` each year.

    Vectorized per rebalance/withdrawal segment instead of a day-by-day Python loop -
    see portfolio.simulate_portfolio for the same technique. The Python loop only
    runs once per rebalance-or-withdrawal date, not once per trading day."""
    tickers = list(weights.keys())
    dates = close.index
    rebal_dates = rebalance_dates(dates, rebalance_freq)
    withdrawal_dates = rebalance_dates(dates, "annual")
    base_withdrawal = initial_capital * withdrawal_rate
    weight_arr = pd.Series(weights, index=tickers).to_numpy()

    price = close[tickers].to_numpy()
    growth_factor = 1 + (dividends[tickers] / close[tickers]).to_numpy()

    boundary_dates = rebal_dates | withdrawal_dates
    segment_ends = [i for i, d in enumerate(dates) if d in boundary_dates]
    if not segment_ends or segment_ends[-1] != len(dates) - 1:
        segment_ends.append(len(dates) - 1)

    values = np.zeros(len(dates))
    shares = weight_arr * initial_capital / price[0]

    start = 0
    years_elapsed = 0
    first_withdrawal_date = None

    for end in segment_ends:
        cum_growth = growth_factor[start : end + 1].cumprod(axis=0)
        seg_shares = shares * cum_growth
        seg_price = price[start : end + 1]
        seg_values = (seg_shares * seg_price).sum(axis=1)
        values[start : end + 1] = seg_values

        boundary_date = dates[end]
        last_value = seg_values[-1]
        last_price = seg_price[-1]

        if boundary_date in withdrawal_dates:
            if cpi is not None:
                if first_withdrawal_date is None:
                    first_withdrawal_date = boundary_date
                withdrawal_amount = cpi_adjusted_withdrawal(base_withdrawal, cpi, boundary_date, first_withdrawal_date)
            else:
                withdrawal_amount = inflation_adjusted_withdrawal(base_withdrawal, inflation_rate, years_elapsed)
            years_elapsed += 1

            remaining_value = last_value - withdrawal_amount
            if remaining_value <= 0:
                values[end:] = 0.0
                return pd.Series(values, index=dates)

            values[end] = remaining_value
            shares = weight_arr * remaining_value / last_price
        elif boundary_date in rebal_dates:
            shares = weight_arr * last_value / last_price

        start = end + 1

    return pd.Series(values, index=dates)
