import pytest

from simulator.retirement_score import retirement_score


def test_higher_survival_probability_scores_higher():
    low = retirement_score(survival_probability=0.5, cagr=0.05, max_drawdown=-0.2)
    high = retirement_score(survival_probability=0.9, cagr=0.05, max_drawdown=-0.2)
    assert high > low


def test_higher_cagr_scores_higher():
    low = retirement_score(survival_probability=0.8, cagr=0.03, max_drawdown=-0.2)
    high = retirement_score(survival_probability=0.8, cagr=0.08, max_drawdown=-0.2)
    assert high > low


def test_larger_drawdown_scores_lower():
    small_dd = retirement_score(survival_probability=0.8, cagr=0.05, max_drawdown=-0.1)
    large_dd = retirement_score(survival_probability=0.8, cagr=0.05, max_drawdown=-0.4)
    assert small_dd > large_dd


def test_known_value():
    result = retirement_score(survival_probability=1.0, cagr=0.1, max_drawdown=-0.2)
    # 1.0*100 + 0.1*100 - 0.2*50 = 100 + 10 - 10 = 100
    assert result == pytest.approx(100.0)
