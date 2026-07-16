import pandas as pd
import pytest

from simulator.metrics import cagr, annual_volatility, max_drawdown


def test_cagr_doubles_in_one_year():
    dates = pd.date_range("2020-01-01", "2021-01-01", freq="D")
    value = pd.Series(1.0, index=dates)
    value.iloc[-1] = 2.0
    assert cagr(value) == pytest.approx(1.0, rel=1e-2)


def test_cagr_flat_series_is_zero():
    dates = pd.date_range("2020-01-01", periods=365, freq="D")
    value = pd.Series(1.0, index=dates)
    assert cagr(value) == pytest.approx(0.0, abs=1e-9)


def test_annual_volatility_zero_for_constant_series():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    value = pd.Series(1.0, index=dates)
    assert annual_volatility(value) == 0.0


def test_max_drawdown_known_scenario():
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    value = pd.Series([1.0, 1.2, 0.6, 0.9, 1.5], index=dates)
    assert max_drawdown(value) == pytest.approx(-0.5)
