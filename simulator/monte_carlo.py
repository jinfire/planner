import numpy as np
import pandas as pd

from .inflation import inflation_adjusted_withdrawal


def annual_returns(value: pd.Series) -> np.ndarray:
    """Year-over-year returns computed from a daily portfolio value series."""
    yearly = value.resample("YE").last()
    return yearly.pct_change().dropna().to_numpy()


def simulate_paths(
    returns: np.ndarray,
    years: int,
    withdrawal_rate: float,
    inflation_rate: float,
    initial_capital: float = 1.0,
    num_simulations: int = 1000,
    seed: int | None = None,
) -> np.ndarray:
    """Bootstrap `years` annual returns from historical `returns` (with replacement)
    for each of `num_simulations` paths, applying an inflation-adjusted annual
    withdrawal. Returns each path's final value (0.0 if depleted)."""
    rng = np.random.default_rng(seed)
    base_withdrawal = initial_capital * withdrawal_rate

    final_values = np.empty(num_simulations)
    for i in range(num_simulations):
        value = initial_capital
        sampled_returns = rng.choice(returns, size=years, replace=True)
        for year, r in enumerate(sampled_returns):
            value *= 1 + r
            value -= inflation_adjusted_withdrawal(base_withdrawal, inflation_rate, year)
            if value <= 0:
                value = 0.0
                break
        final_values[i] = value

    return final_values


def survival_probability(final_values: np.ndarray) -> float:
    return float(np.mean(final_values > 0))
