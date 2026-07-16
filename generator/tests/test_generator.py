from math import comb

import pytest

from generator import generate_portfolios


def test_two_tickers_step_50_gives_three_combinations():
    result = generate_portfolios(["A", "B"], step=50)
    assert result == [
        {"A": 0.0, "B": 1.0},
        {"A": 0.5, "B": 0.5},
        {"A": 1.0, "B": 0.0},
    ]


def test_all_portfolios_sum_to_one():
    result = generate_portfolios(["A", "B", "C"], step=10)
    for weights in result:
        assert sum(weights.values()) == pytest.approx(1.0)


def test_combination_count_matches_stars_and_bars():
    tickers = ["A", "B", "C"]
    step = 10
    k = 100 // step
    n = len(tickers)
    expected = comb(k + n - 1, n - 1)
    assert len(generate_portfolios(tickers, step)) == expected
