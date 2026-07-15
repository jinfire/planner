import pandas as pd

REBALANCE_FREQUENCIES = ["none", "monthly", "quarterly", "annual"]


def rebalance_dates(dates: pd.DatetimeIndex, freq: str) -> set:
    if freq == "none":
        return set()
    if freq == "monthly":
        period = dates.to_period("M")
    elif freq == "quarterly":
        period = dates.to_period("Q")
    elif freq == "annual":
        period = dates.to_period("Y")
    else:
        raise ValueError(f"unknown rebalance frequency: {freq}")

    first_day_per_period = pd.Series(dates, index=period).groupby(level=0).first()
    return set(first_day_per_period.tolist())
