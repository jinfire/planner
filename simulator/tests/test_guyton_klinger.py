import pandas as pd
import pytest

from simulator.guyton_klinger import simulate_guyton_klinger_withdrawal


def _make_data(prices):
    dates = pd.to_datetime(["2020-01-02", "2021-01-04"])
    close = pd.DataFrame({"A": prices}, index=dates)
    div = pd.DataFrame({"A": [0.0, 0.0]}, index=dates)
    return close, div


def test_first_withdrawal_is_initial_rate_times_capital():
    close, div = _make_data([10, 10])  # flat price, no guardrail trigger possible

    value = simulate_guyton_klinger_withdrawal(close, div, {"A": 1.0}, initial_withdrawal_rate=0.04)

    assert value.iloc[0] == pytest.approx(1.0 - 0.04)


def test_capital_preservation_rule_cuts_withdrawal_after_crash():
    close, div = _make_data([10, 6])  # -40% crash pushes the withdrawal rate way up

    value = simulate_guyton_klinger_withdrawal(close, div, {"A": 1.0}, initial_withdrawal_rate=0.04)

    # year 2 value pre-withdrawal: 0.096 shares * 6 = 0.576; planned=0.04 (frozen since
    # year_return is negative anyway); rate 0.04/0.576=6.9% > 4%*1.2=4.8% -> cut 10%
    assert value.iloc[1] == pytest.approx(0.576 - 0.04 * 0.9)


def test_prosperity_rule_raises_withdrawal_after_big_gain():
    close, div = _make_data([10, 30])  # +200% growth pushes the withdrawal rate way down

    value = simulate_guyton_klinger_withdrawal(close, div, {"A": 1.0}, initial_withdrawal_rate=0.04)

    # year 2 value pre-withdrawal: 0.096 shares * 30 = 2.88; planned=0.04; rate
    # 0.04/2.88=1.4% < 4%*0.8=3.2% -> raise 10%
    assert value.iloc[1] == pytest.approx(2.88 - 0.04 * 1.1)


def test_inflation_rule_freezes_withdrawal_after_down_year():
    close, div = _make_data([10, 9])  # mild -10% down year, no guardrail trigger

    value = simulate_guyton_klinger_withdrawal(
        close, div, {"A": 1.0}, initial_withdrawal_rate=0.04, inflation_rate=0.10
    )

    # year_return = 0.864/0.96 - 1 = -10% -> frozen at last year's 0.04, not grown to 0.044
    assert value.iloc[1] == pytest.approx(0.864 - 0.04)


def test_withdrawal_grows_with_inflation_after_up_year():
    close, div = _make_data([10, 11])  # mild +10% up year, no guardrail trigger

    value = simulate_guyton_klinger_withdrawal(
        close, div, {"A": 1.0}, initial_withdrawal_rate=0.04, inflation_rate=0.10
    )

    # year_return = +10% (not negative) -> not frozen, grows to 0.04*1.10=0.044
    assert value.iloc[1] == pytest.approx(1.056 - 0.044)


def test_depletes_and_floors_to_zero():
    close, div = _make_data([10, 1])  # near-total wipeout

    value = simulate_guyton_klinger_withdrawal(close, div, {"A": 1.0}, initial_withdrawal_rate=0.5)

    assert value.iloc[-1] == 0.0
