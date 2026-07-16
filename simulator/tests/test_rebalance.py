import pandas as pd

from simulator.rebalance import rebalance_dates


def test_none_frequency_returns_empty_set():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    assert rebalance_dates(dates, "none") == set()


def test_monthly_returns_first_trading_day_of_each_month():
    dates = pd.to_datetime(["2020-01-02", "2020-01-15", "2020-02-03", "2020-02-20"])
    result = rebalance_dates(dates, "monthly")
    assert result == {pd.Timestamp("2020-01-02"), pd.Timestamp("2020-02-03")}


def test_quarterly_returns_first_trading_day_of_each_quarter():
    dates = pd.to_datetime(["2020-01-02", "2020-02-10", "2020-04-01", "2020-05-10"])
    result = rebalance_dates(dates, "quarterly")
    assert result == {pd.Timestamp("2020-01-02"), pd.Timestamp("2020-04-01")}


def test_annual_returns_first_trading_day_of_each_year():
    dates = pd.to_datetime(["2020-01-02", "2020-06-01", "2021-01-04", "2021-06-01"])
    result = rebalance_dates(dates, "annual")
    assert result == {pd.Timestamp("2020-01-02"), pd.Timestamp("2021-01-04")}
