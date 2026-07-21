import pandas as pd

from .strategy import WithdrawalStrategy


def rolling_start_years(dates: pd.DatetimeIndex, window_years: int) -> list[int]:
    """Every calendar year whose `window_years`-long window fits entirely within
    `dates`, so every window compared is the same length. A single fixed historical
    start date (like our usual "2000") gives one data point; picking a strategy that
    only survived a lucky starting year is a well-known trap - this is what lets a
    strategy be judged across many different starting points instead."""
    first_year = dates.min().year
    last_year = dates.max().year
    return list(range(first_year, last_year - window_years + 2))


def evaluate_rolling_window(
    strategy: WithdrawalStrategy,
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    cpi: pd.Series | None,
    window_years: int,
) -> dict:
    """Re-run `strategy` once per rolling `window_years`-long start year, and
    summarize how it did across all of them - a single historical start date can make
    a strategy look better or worse than it really is (sequence-of-returns luck)."""
    start_years = rolling_start_years(close.index, window_years)

    survived_flags = []
    final_values = []
    for start_year in start_years:
        start = f"{start_year}-01-01"
        end = f"{start_year + window_years - 1}-12-31"
        window_close = close.loc[start:end]
        window_dividends = dividends.loc[start:end]
        window_cpi = cpi.loc[start:end] if cpi is not None else None

        result = strategy.simulate(window_close, window_dividends, window_cpi)
        final_value = result.value.iloc[-1]
        survived_flags.append(final_value > 0)
        final_values.append(final_value)

    sorted_values = sorted(final_values)
    return {
        "num_windows": len(start_years),
        "success_rate": sum(survived_flags) / len(survived_flags) if survived_flags else 0.0,
        "median_final_value": sorted_values[len(sorted_values) // 2] if sorted_values else 0.0,
        "worst_final_value": min(final_values) if final_values else 0.0,
        "start_years": start_years,
    }
