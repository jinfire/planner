import pandas as pd
import pytest

from simulator.portfolio import simulate_portfolio


def _make_data(prices: dict, dividends: dict | None = None):
    dates = pd.date_range("2020-01-01", periods=len(next(iter(prices.values()))), freq="D")
    close = pd.DataFrame(prices, index=dates)
    if dividends is None:
        dividends = {t: [0.0] * len(dates) for t in prices}
    div = pd.DataFrame(dividends, index=dates)
    return close, div


def test_buy_and_hold_no_dividends_matches_weighted_return():
    close, div = _make_data({"A": [10, 11, 12], "B": [20, 22, 18]})
    weights = {"A": 0.5, "B": 0.5}
    value = simulate_portfolio(close, div, weights, rebalance_freq="none", initial_capital=1.0)

    expected_last = 0.5 * (12 / 10) + 0.5 * (18 / 20)
    assert value.iloc[-1] == pytest.approx(expected_last)


def test_dividend_reinvestment_increases_value():
    close, div = _make_data({"A": [10, 10, 10]}, {"A": [0.0, 1.0, 0.0]})
    value = simulate_portfolio(close, div, {"A": 1.0}, rebalance_freq="none")

    # $1 buys 0.1 shares at price 10; a $1/share dividend on day 2 buys 0.1 more shares
    assert value.iloc[1] == pytest.approx(1.1)
    assert value.iloc[-1] == pytest.approx(1.1)


def test_monthly_rebalance_changes_future_allocation():
    dates = pd.to_datetime(["2020-01-01", "2020-02-01", "2020-02-15"])
    close = pd.DataFrame({"A": [10, 20, 10], "B": [10, 10, 10]}, index=dates)
    div = pd.DataFrame({"A": [0, 0, 0], "B": [0, 0, 0]}, index=dates)
    weights = {"A": 0.5, "B": 0.5}

    value = simulate_portfolio(close, div, weights, rebalance_freq="monthly")

    # Without the Feb 1 rebalance, the Feb 15 value would be 1.0 instead of 1.125
    assert value.iloc[-1] == pytest.approx(1.125)
