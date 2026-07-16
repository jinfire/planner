import pandas as pd
import pytest

from simulator.portfolio import simulate_portfolio
from simulator.withdrawal import simulate_withdrawal


def _make_data(prices: dict):
    dates = pd.to_datetime(["2020-01-02", "2020-06-01", "2021-01-04", "2021-06-01"])
    close = pd.DataFrame(prices, index=dates)
    div = pd.DataFrame({t: [0.0] * len(dates) for t in prices}, index=dates)
    return close, div


def test_withdrawal_taken_on_first_trading_day_of_each_year():
    close, div = _make_data({"A": [10, 10, 10, 10]})
    weights = {"A": 1.0}

    value = simulate_withdrawal(close, div, weights, withdrawal_rate=0.1, initial_capital=1.0)

    # year 1: 1.0 - 0.1 = 0.9; year 2: 0.9 - 0.1 = 0.8, flat price in between
    assert value.iloc[0] == pytest.approx(0.9)
    assert value.iloc[1] == pytest.approx(0.9)
    assert value.iloc[2] == pytest.approx(0.8)
    assert value.iloc[-1] == pytest.approx(0.8)


def test_portfolio_depletes_and_stays_at_zero():
    close, div = _make_data({"A": [10, 10, 10, 10]})
    weights = {"A": 1.0}

    value = simulate_withdrawal(close, div, weights, withdrawal_rate=0.5, initial_capital=1.0)

    # year 1: 1.0 - 0.5 = 0.5; year 2: 0.5 - 0.5 = 0.0 -> depleted
    assert value.iloc[1] == pytest.approx(0.5)
    assert value.iloc[2] == 0.0
    assert value.iloc[-1] == 0.0


def test_inflation_adjusted_withdrawal_grows_each_year():
    close, div = _make_data({"A": [10, 10, 10, 10]})
    weights = {"A": 1.0}

    value = simulate_withdrawal(
        close, div, weights, withdrawal_rate=0.1, initial_capital=1.0, inflation_rate=0.1
    )

    # year 1 withdrawal = 0.1 (base); year 2 withdrawal = 0.1 * 1.1 = 0.11
    assert value.iloc[0] == pytest.approx(0.9)
    assert value.iloc[2] == pytest.approx(0.9 - 0.11)
    assert value.iloc[-1] == pytest.approx(0.9 - 0.11)


def test_zero_withdrawal_rate_matches_plain_rebalanced_portfolio():
    close, div = _make_data({"A": [10, 11, 12, 13], "B": [20, 19, 22, 21]})
    weights = {"A": 0.5, "B": 0.5}

    withdrawn = simulate_withdrawal(close, div, weights, withdrawal_rate=0.0, rebalance_freq="annual")
    plain = simulate_portfolio(close, div, weights, rebalance_freq="annual")

    pd.testing.assert_series_equal(withdrawn, plain)
