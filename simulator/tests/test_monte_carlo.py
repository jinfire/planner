import numpy as np
import pandas as pd
import pytest

from simulator.monte_carlo import annual_returns, simulate_paths, survival_probability


def test_annual_returns_from_yearly_value_series():
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="D")
    value = pd.Series(1.0, index=dates)
    value.loc["2020"] = 1.0
    value.loc["2021"] = 1.1
    value.loc["2022"] = 1.21

    result = annual_returns(value)

    assert result == pytest.approx([0.1, 0.1])


def test_simulate_paths_compounds_a_single_possible_return():
    returns = np.array([0.05])
    result = simulate_paths(
        returns, years=3, withdrawal_rate=0.0, inflation_rate=0.0,
        initial_capital=1.0, num_simulations=1, seed=0,
    )
    assert result[0] == pytest.approx(1.05 ** 3)


def test_simulate_paths_depletes_when_withdrawal_exceeds_flat_return():
    returns = np.array([0.0])
    result = simulate_paths(
        returns, years=5, withdrawal_rate=0.3, inflation_rate=0.0,
        initial_capital=1.0, num_simulations=1, seed=0,
    )
    # 1.0 -> 0.7 -> 0.4 -> 0.1 -> depleted on the 4th withdrawal
    assert result[0] == 0.0


def test_simulate_paths_reproducible_with_seed():
    returns = np.array([0.1, -0.05, 0.2])
    first = simulate_paths(
        returns, years=10, withdrawal_rate=0.04, inflation_rate=0.03,
        initial_capital=1.0, num_simulations=50, seed=42,
    )
    second = simulate_paths(
        returns, years=10, withdrawal_rate=0.04, inflation_rate=0.03,
        initial_capital=1.0, num_simulations=50, seed=42,
    )
    np.testing.assert_array_equal(first, second)


def test_survival_probability():
    final_values = np.array([1.0, 0.0, 2.0, 0.0])
    assert survival_probability(final_values) == pytest.approx(0.5)
