import pandas as pd
import pytest

from simulator.metrics import cagr, annual_volatility, max_drawdown, years_survived


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


def test_years_survived_is_one_when_never_depleted():
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    value = pd.Series([1.0, 1.2, 0.6, 0.9, 1.5], index=dates)
    assert years_survived(value) == 1.0


def test_years_survived_is_fraction_of_span_before_depletion():
    dates = pd.date_range("2020-01-01", periods=11, freq="D")  # 10-day span
    value = pd.Series([1.0] * 6 + [0.0] * 5, index=dates)  # depletes on day index 6
    assert years_survived(value) == pytest.approx(6 / 10)


def test_earlier_depletion_scores_lower_years_survived():
    dates = pd.date_range("2020-01-01", periods=11, freq="D")
    early = pd.Series([1.0] * 3 + [0.0] * 8, index=dates)
    late = pd.Series([1.0] * 8 + [0.0] * 3, index=dates)
    assert years_survived(early) < years_survived(late)
