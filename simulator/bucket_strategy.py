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

    Returns {"value": pd.Series (total, mark-to-market), "cash": pd.Series,
    "guardrail_failures": list[Timestamp]}."""
    dates = close.index
    withdrawal_dates = rebalance_dates(dates, "annual")
    base_withdrawal = initial_capital * withdrawal_rate

    reserve_capital = initial_capital * reserve_weight
    cash = base_withdrawal * cash_years
    growth_capital = initial_capital - reserve_capital - cash

    growth_shares = growth_capital / close[growth_ticker].iloc[0]
    reserve_shares = reserve_capital / close[reserve_ticker].iloc[0]

    values = []
    cash_series = []
    guardrail_failures = []
    last_withdrawal_price = None
    first_withdrawal_date = None
    years_elapsed = 0

    for date in dates:
        price_growth = close.loc[date, growth_ticker]
        price_reserve = close.loc[date, reserve_ticker]
        div_growth = dividends.loc[date, growth_ticker]
        div_reserve = dividends.loc[date, reserve_ticker]

        growth_shares += (div_growth * growth_shares) / price_growth
        reserve_shares += (div_reserve * reserve_shares) / price_reserve

        if date in withdrawal_dates:
            year_return = (
                price_growth / last_withdrawal_price - 1 if last_withdrawal_price is not None else 0.0
            )

            if first_withdrawal_date is None:
                first_withdrawal_date = date
            if cpi is not None:
                withdrawal_amount = cpi_adjusted_withdrawal(base_withdrawal, cpi, date, first_withdrawal_date)
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
                    growth_value = growth_shares * price_growth
                    sold = min(shortfall, growth_value)
                    growth_shares -= sold / price_growth
                    guardrail_failures.append(date)
            else:
                growth_value = growth_shares * price_growth
                need = withdrawal_amount + max(cash_target - cash, 0.0)
                sell = min(need, growth_value)
                growth_shares -= sell / price_growth
                proceeds_to_cash = sell - withdrawal_amount
                cash = cash + proceeds_to_cash if proceeds_to_cash >= 0 else max(cash + proceeds_to_cash, 0.0)

            last_withdrawal_price = price_growth

        total_value = growth_shares * price_growth + reserve_shares * price_reserve + cash
        values.append(total_value)
        cash_series.append(cash)

    return {
        "value": pd.Series(values, index=dates),
        "cash": pd.Series(cash_series, index=dates),
        "guardrail_failures": guardrail_failures,
    }
