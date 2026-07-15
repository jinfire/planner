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
