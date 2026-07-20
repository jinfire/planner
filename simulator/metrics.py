import pandas as pd


def cagr(value: pd.Series) -> float:
    years = (value.index[-1] - value.index[0]).days / 365.25
    return (value.iloc[-1] / value.iloc[0]) ** (1 / years) - 1


def annual_volatility(value: pd.Series) -> float:
    daily_returns = value.pct_change().dropna()
    return daily_returns.std() * (252 ** 0.5)


def max_drawdown(value: pd.Series) -> float:
    running_max = value.cummax()
    drawdown = value / running_max - 1
    return drawdown.min()


def years_survived(value: pd.Series) -> float:
    """Fraction of the series' timespan survived before the balance hits 0 (1.0 if it
    never does). Lets depleted portfolios still be ranked against each other - running
    out of money in year 5 is worse than running out in year 24, even though both
    technically "failed"."""
    depleted = value[value <= 0]
    if depleted.empty:
        return 1.0

    total_span = (value.index[-1] - value.index[0]).days
    if total_span <= 0:
        return 1.0

    survived_span = (depleted.index[0] - value.index[0]).days
    return survived_span / total_span
