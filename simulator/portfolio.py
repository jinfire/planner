import pandas as pd

from rebalance import rebalance_dates


def simulate_portfolio(
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    weights: dict[str, float],
    rebalance_freq: str = "none",
    initial_capital: float = 1.0,
) -> pd.Series:
    """Share-based portfolio simulation with dividend reinvestment and periodic rebalancing."""
    tickers = list(weights.keys())
    dates = close.index
    rebal_dates = rebalance_dates(dates, rebalance_freq)

    shares = pd.Series(
        {t: initial_capital * weights[t] / close[t].iloc[0] for t in tickers}
    )

    values = []
    for date in dates:
        price_today = close.loc[date, tickers]
        div_today = dividends.loc[date, tickers]

        # reinvest today's dividend back into the same ticker
        shares = shares + (div_today * shares) / price_today

        value_today = (shares * price_today).sum()

        if date in rebal_dates:
            shares = pd.Series({t: value_today * weights[t] / price_today[t] for t in tickers})

        values.append(value_today)

    return pd.Series(values, index=dates)
