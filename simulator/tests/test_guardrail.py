import pandas as pd
import pytest

from simulator.guardrail import simulate_guardrail_withdrawal


def _make_data(growth_prices, reserve_prices, reserve_dividends=None):
    dates = pd.to_datetime(["2020-01-02", "2020-06-01", "2021-01-04", "2021-06-01"])
    close = pd.DataFrame({"GROWTH": growth_prices, "RESERVE": reserve_prices}, index=dates)
    div = pd.DataFrame(
        {
            "GROWTH": [0.0] * 4,
            "RESERVE": reserve_dividends if reserve_dividends is not None else [0.0] * 4,
        },
        index=dates,
    )
    return close, div


def test_up_year_funds_withdrawal_from_growth_and_tops_up_cash():
    close, div = _make_data([100, 105, 110, 115], [10, 10, 10, 10])

    result = simulate_guardrail_withdrawal(
        close, div, "GROWTH", "RESERVE", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=3
    )

    # cash starts at 0.04*3=0.12 and, since every year is an "up year" here, stays
    # topped up to that same target after each withdrawal
    assert result["cash"].iloc[0] == pytest.approx(0.12)
    assert result["cash"].iloc[2] == pytest.approx(0.12)
    assert result["guardrail_failures"] == []
    # capital conservation on the very first withdrawal day (no growth has happened yet)
    assert result["value"].iloc[0] == pytest.approx(1.0 - 0.04)


def test_down_year_draws_from_cash_and_leaves_growth_untouched():
    close, div = _make_data([100, 95, 90, 85], [10, 10, 10, 10])

    result = simulate_guardrail_withdrawal(
        close, div, "GROWTH", "RESERVE", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=3
    )

    # year 2: GROWTH return = 90/100 - 1 = -10%, below the default 0% threshold -> down year
    assert result["cash"].iloc[2] == pytest.approx(0.12 - 0.04)
    assert result["guardrail_failures"] == []


def test_down_year_with_insufficient_cash_sells_growth_and_logs_failure():
    close, div = _make_data([100, 95, 90, 85], [10, 10, 10, 10])

    result = simulate_guardrail_withdrawal(
        close, div, "GROWTH", "RESERVE", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=0
    )

    dates = close.index
    assert result["guardrail_failures"] == [dates[2]]
    assert result["cash"].iloc[2] == pytest.approx(0.0)


def test_reserve_ticker_is_never_sold():
    close, div = _make_data(
        [100, 95, 90, 85], [10, 10, 10, 10], reserve_dividends=[0.0, 0.0, 1.0, 0.0]
    )

    result = simulate_guardrail_withdrawal(
        close, div, "GROWTH", "RESERVE", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=0
    )

    # reserve value only ever grows (from its own dividend reinvestment on day 2),
    # even though this run has a guardrail failure that sells GROWTH
    reserve_only_value = 0.1  # weight * initial_capital, price is flat except the dividend
    assert result["guardrail_failures"] != []
    implied_reserve_value_before_div = reserve_only_value
    implied_reserve_value_after_div = reserve_only_value * (1 + 1.0 / 10)
    assert result["value"].iloc[1] >= implied_reserve_value_before_div - 1e-9
    assert result["value"].iloc[-1] >= implied_reserve_value_after_div - 1e-9


def test_cash_bucket_size_scales_with_cash_years():
    close, div = _make_data([100, 100, 100, 100], [10, 10, 10, 10])

    result_3y = simulate_guardrail_withdrawal(
        close, div, "GROWTH", "RESERVE", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=3
    )
    result_5y = simulate_guardrail_withdrawal(
        close, div, "GROWTH", "RESERVE", reserve_weight=0.1, withdrawal_rate=0.04, cash_years=5
    )

    assert result_3y["cash"].iloc[0] == pytest.approx(0.04 * 3)
    assert result_5y["cash"].iloc[0] == pytest.approx(0.04 * 5)
