import pandas as pd
import pytest

from simulator.strategy import BucketWithdrawalStrategy, ConstantWithdrawalStrategy


def _make_data():
    dates = pd.to_datetime(["2020-01-02", "2020-06-01", "2021-01-04", "2021-06-01"])
    close = pd.DataFrame({"A": [10, 11, 12, 13], "B": [20, 19, 22, 21]}, index=dates)
    div = pd.DataFrame({"A": [0.0] * 4, "B": [0.0] * 4}, index=dates)
    return close, div


def test_constant_strategy_label_matches_its_weights():
    strategy = ConstantWithdrawalStrategy({"A": 0.6, "B": 0.4}, withdrawal_rate=0.04)
    close, div = _make_data()

    result = strategy.simulate(close, div, cpi=None)

    assert result.label == {"A": 0.6, "B": 0.4}


def test_constant_strategy_value_reflects_the_actual_withdrawal_path():
    strategy = ConstantWithdrawalStrategy({"A": 1.0}, withdrawal_rate=0.5)
    close, div = _make_data()

    result = strategy.simulate(close, div, cpi=None)

    # `value` is the realized (withdrawal-included) balance, not the hypothetical
    # no-withdrawal buy-and-hold value (13/10)
    assert result.value.iloc[-1] != pytest.approx(13 / 10)


def test_constant_strategy_value_reflects_depletion():
    dates = pd.to_datetime(["2020-01-02", "2020-06-01", "2021-01-04", "2021-06-01"])
    close = pd.DataFrame({"A": [10, 10, 10, 10]}, index=dates)
    div = pd.DataFrame({"A": [0.0] * 4}, index=dates)
    strategy = ConstantWithdrawalStrategy({"A": 1.0}, withdrawal_rate=0.5)

    result = strategy.simulate(close, div, cpi=None)

    # a 50% annual withdrawal on a $1 start, flat price, depletes after two withdrawals
    assert result.value.iloc[-1] == 0.0


def test_constant_strategy_supplies_pure_growth_returns_for_monte_carlo():
    strategy = ConstantWithdrawalStrategy({"A": 1.0}, withdrawal_rate=0.5)
    close, div = _make_data()

    result = strategy.simulate(close, div, cpi=None)

    assert result.monte_carlo_returns is not None
    # monte_carlo_returns ignores withdrawal_rate entirely - pure buy-and-hold
    assert result.monte_carlo_returns.iloc[-1] == pytest.approx(13 / 10)


def test_bucket_strategy_label_is_cash_years():
    strategy = BucketWithdrawalStrategy("A", "B", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=3)
    close, div = _make_data()

    result = strategy.simulate(close, div, cpi=None)

    assert result.label == {"cash_years": 3}


def test_bucket_strategy_has_no_monte_carlo_returns():
    strategy = BucketWithdrawalStrategy("A", "B", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=3)
    close, div = _make_data()

    result = strategy.simulate(close, div, cpi=None)

    assert result.monte_carlo_returns is None


def test_bucket_strategy_reports_guardrail_failure_count():
    # heavy withdrawal, no cash buffer, growth ticker crashes -> a guardrail failure
    dates = pd.to_datetime(["2020-01-02", "2021-01-04"])
    close = pd.DataFrame({"A": [100, 50], "B": [10, 10]}, index=dates)
    div = pd.DataFrame({"A": [0.0, 0.0], "B": [0.0, 0.0]}, index=dates)
    strategy = BucketWithdrawalStrategy("A", "B", reserve_weight=0.1, withdrawal_rate=0.5, cash_years=0)

    result = strategy.simulate(close, div, cpi=None)

    assert result.extra["guardrail_failures"] >= 1
