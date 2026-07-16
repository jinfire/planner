import pandas as pd

from rebalance import rebalance_dates


def simulate_withdrawal(
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    weights: dict[str, float],
    withdrawal_rate: float,
    rebalance_freq: str = "annual",
    initial_capital: float = 1.0,
) -> pd.Series:
    """Share-based simulation with dividend reinvestment, periodic rebalancing, and a
    fixed-dollar withdrawal (initial_capital * withdrawal_rate) taken on the first
    trading day of every year. Once the portfolio can't cover a withdrawal, value is
    floored at 0 for the rest of the series (no inflation adjustment yet)."""
    tickers = list(weights.keys())
    dates = close.index
    rebal_dates = rebalance_dates(dates, rebalance_freq)
    withdrawal_dates = rebalance_dates(dates, "annual")
    annual_withdrawal = initial_capital * withdrawal_rate

    shares = pd.Series(
        {t: initial_capital * weights[t] / close[t].iloc[0] for t in tickers}
    )

    values = []
    depleted = False
    for date in dates:
        if depleted:
            values.append(0.0)
            continue

        price_today = close.loc[date, tickers]
        div_today = dividends.loc[date, tickers]

        shares = shares + (div_today * shares) / price_today
        value_today = (shares * price_today).sum()

        if date in withdrawal_dates:
            value_today -= annual_withdrawal
            if value_today <= 0:
                depleted = True
                values.append(0.0)
                continue
            shares = pd.Series({t: value_today * weights[t] / price_today[t] for t in tickers})
        elif date in rebal_dates:
            shares = pd.Series({t: value_today * weights[t] / price_today[t] for t in tickers})

        values.append(value_today)

    return pd.Series(values, index=dates)
