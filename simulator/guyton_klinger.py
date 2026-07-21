import numpy as np
import pandas as pd

from .cpi import cpi_adjusted_withdrawal
from .inflation import inflation_adjusted_withdrawal
from .rebalance import rebalance_dates


def simulate_guyton_klinger_withdrawal(
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    weights: dict[str, float],
    initial_withdrawal_rate: float,
    rebalance_freq: str = "annual",
    initial_capital: float = 1.0,
    inflation_rate: float = 0.0,
    cpi: pd.Series | None = None,
    upper_guardrail: float = 1.20,
    lower_guardrail: float = 0.80,
    adjustment_pct: float = 0.10,
) -> pd.Series:
    """Guyton-Klinger dynamic withdrawal: the withdrawal *amount* itself is adjusted
    each year based on portfolio performance, instead of a fixed real amount.

    Each year, start from last year's actual withdrawal amount, grown by one year of
    inflation - unless the portfolio's own investment return over the past year (net
    of withdrawals) was negative, in which case the inflation increase is skipped
    (frozen at last year's nominal amount). Compare that planned amount to the current
    portfolio value as a withdrawal rate: if it exceeds `initial_withdrawal_rate *
    upper_guardrail`, cut the withdrawal by `adjustment_pct` (capital preservation
    rule). If it falls below `initial_withdrawal_rate * lower_guardrail`, raise the
    withdrawal by `adjustment_pct` (prosperity rule). Otherwise withdraw the planned
    amount unchanged. Floors to 0 for the rest of the series once depleted.

    Vectorized per rebalance/withdrawal segment - see portfolio.simulate_portfolio for
    the technique."""
    tickers = list(weights.keys())
    dates = close.index
    rebal_dates = rebalance_dates(dates, rebalance_freq)
    withdrawal_dates = rebalance_dates(dates, "annual")
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
    last_withdrawal_amount = None
    last_transaction_value = None
    last_transaction_date = None

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
            year_return = (
                last_value / last_transaction_value - 1 if last_transaction_date is not None else 0.0
            )

            if last_withdrawal_amount is None:
                planned = initial_capital * initial_withdrawal_rate
            elif year_return < 0:
                planned = last_withdrawal_amount  # inflation rule: freeze after a down year
            elif cpi is not None:
                planned = cpi_adjusted_withdrawal(last_withdrawal_amount, cpi, boundary_date, last_transaction_date)
            else:
                planned = inflation_adjusted_withdrawal(last_withdrawal_amount, inflation_rate, 1)

            current_rate = planned / last_value
            if current_rate > initial_withdrawal_rate * upper_guardrail:
                actual_withdrawal = planned * (1 - adjustment_pct)  # capital preservation rule
            elif current_rate < initial_withdrawal_rate * lower_guardrail:
                actual_withdrawal = planned * (1 + adjustment_pct)  # prosperity rule
            else:
                actual_withdrawal = planned

            remaining_value = last_value - actual_withdrawal
            if remaining_value <= 0:
                values[end:] = 0.0
                return pd.Series(values, index=dates)

            values[end] = remaining_value
            shares = weight_arr * remaining_value / last_price
            last_withdrawal_amount = actual_withdrawal
            last_transaction_value = remaining_value
            last_transaction_date = boundary_date
        elif boundary_date in rebal_dates:
            shares = weight_arr * last_value / last_price

        start = end + 1

    return pd.Series(values, index=dates)
