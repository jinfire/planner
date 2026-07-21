import numpy as np
import pandas as pd

from .cpi import cpi_adjusted_withdrawal
from .inflation import inflation_adjusted_withdrawal
from .rebalance import rebalance_dates


def simulate_bucket_withdrawal(
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    growth_ticker: str,
    reserve_ticker: str,
    reserve_weight: float,
    withdrawal_rate: float,
    cash_years: float,
    down_threshold: float = 0.0,
    initial_capital: float = 1.0,
    inflation_rate: float = 0.0,
    cpi: pd.Series | None = None,
) -> dict:
    """Bucket-strategy withdrawal with a cash guardrail.

    `reserve_ticker` (e.g. a leveraged growth sleeve like QLD) is never sold - it just
    compounds untouched. `growth_ticker` (e.g. QQQ) funds withdrawals in years its own
    return is >= `down_threshold` (a "down year" is defined by the growth ticker's own
    calendar-year return, not the whole portfolio's), and any surplus tops the cash
    bucket back up to `cash_years` worth of the current (inflation-adjusted) annual
    withdrawal. In a down year, withdrawals are drawn from cash instead, so the growth
    sleeve isn't sold at a loss. If cash can't cover a down-year withdrawal, the
    shortfall is pulled from `growth_ticker` anyway and the date is recorded in
    `guardrail_failures` - the guardrail only prevents selling low when it can.

    Vectorized: `reserve_ticker` never resets, so its whole share path is one cumulative
    product over the entire series. `growth_ticker` only resets at withdrawal dates, so
    it's computed per withdrawal-to-withdrawal segment - see portfolio.simulate_portfolio
    for the same technique. The Python loop only runs once per withdrawal date (annual),
    not once per trading day.

    Returns {"value": pd.Series (total, mark-to-market), "cash": pd.Series,
    "guardrail_failures": list[Timestamp]}."""
    dates = close.index
    withdrawal_dates = rebalance_dates(dates, "annual")
    base_withdrawal = initial_capital * withdrawal_rate

    reserve_capital = initial_capital * reserve_weight
    cash = base_withdrawal * cash_years
    growth_capital = initial_capital - reserve_capital - cash

    price_growth = close[growth_ticker].to_numpy()
    price_reserve = close[reserve_ticker].to_numpy()
    growth_factor_growth = 1 + (dividends[growth_ticker] / close[growth_ticker]).to_numpy()
    growth_factor_reserve = 1 + (dividends[reserve_ticker] / close[reserve_ticker]).to_numpy()

    # reserve is never sold/reset, so its share path is one cumulative product over
    # the whole series
    reserve_shares_path = (reserve_capital / price_reserve[0]) * growth_factor_reserve.cumprod()
    reserve_value_path = reserve_shares_path * price_reserve

    segment_ends = [i for i, d in enumerate(dates) if d in withdrawal_dates]
    if not segment_ends or segment_ends[-1] != len(dates) - 1:
        segment_ends.append(len(dates) - 1)

    values = np.empty(len(dates))
    cash_series = np.empty(len(dates))
    guardrail_failures = []

    growth_shares = growth_capital / price_growth[0]
    last_withdrawal_price = None
    first_withdrawal_date = None
    years_elapsed = 0

    start = 0
    for end in segment_ends:
        cum_growth = growth_factor_growth[start : end + 1].cumprod()
        seg_growth_value = (growth_shares * cum_growth) * price_growth[start : end + 1]

        cash_series[start : end + 1] = cash
        values[start : end + 1] = seg_growth_value + reserve_value_path[start : end + 1] + cash

        boundary_date = dates[end]
        price_today = price_growth[end]

        if boundary_date in withdrawal_dates:
            growth_shares = growth_shares * cum_growth[-1]  # carry post-dividend shares forward
            year_return = (
                price_today / last_withdrawal_price - 1 if last_withdrawal_price is not None else 0.0
            )

            if first_withdrawal_date is None:
                first_withdrawal_date = boundary_date
            if cpi is not None:
                withdrawal_amount = cpi_adjusted_withdrawal(base_withdrawal, cpi, boundary_date, first_withdrawal_date)
            else:
                withdrawal_amount = inflation_adjusted_withdrawal(base_withdrawal, inflation_rate, years_elapsed)
            years_elapsed += 1
            cash_target = withdrawal_amount * cash_years

            if year_return < down_threshold:
                if cash >= withdrawal_amount:
                    cash -= withdrawal_amount
                else:
                    shortfall = withdrawal_amount - cash
                    cash = 0.0
                    growth_value = growth_shares * price_today
                    sold = min(shortfall, growth_value)
                    growth_shares -= sold / price_today
                    guardrail_failures.append(boundary_date)
            else:
                growth_value = growth_shares * price_today
                need = withdrawal_amount + max(cash_target - cash, 0.0)
                sell = min(need, growth_value)
                growth_shares -= sell / price_today
                proceeds_to_cash = sell - withdrawal_amount
                cash = cash + proceeds_to_cash if proceeds_to_cash >= 0 else max(cash + proceeds_to_cash, 0.0)

            last_withdrawal_price = price_today
            values[end] = growth_shares * price_today + reserve_value_path[end] + cash
            cash_series[end] = cash

        start = end + 1

    return {
        "value": pd.Series(values, index=dates),
        "cash": pd.Series(cash_series, index=dates),
        "guardrail_failures": guardrail_failures,
    }
