import pytest

from simulator.inflation import inflation_adjusted_withdrawal


def test_no_inflation_returns_base_amount():
    assert inflation_adjusted_withdrawal(100.0, 0.0, 5) == pytest.approx(100.0)


def test_first_year_returns_base_amount():
    assert inflation_adjusted_withdrawal(100.0, 0.03, 0) == pytest.approx(100.0)


def test_compounds_over_years():
    assert inflation_adjusted_withdrawal(100.0, 0.03, 3) == pytest.approx(100 * 1.03**3)
