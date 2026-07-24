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

        # cpi is passed through unsliced (not cpi.loc[start:end]): cpi_adjusted_withdrawal
        # looks up the *first* withdrawal date via .asof(), which needs history at or
        # before that date. Slicing cpi to start exactly at the window start leaves no
        # such entry (CPI ticks land on the 1st of the month; a window's first trading
        # day is never the 1st), so .asof() would return NaN and poison the whole run.
        result = strategy.simulate(window_close, window_dividends, cpi)
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


def perpetual_start_years(dates: pd.DatetimeIndex, min_years: float = 5.0) -> list[int]:
    """Every calendar year with at least `min_years` of data remaining until the end
    of `dates` - a starting point too close to the end doesn't give the strategy
    enough runway to say anything meaningful about whether it would have lasted."""
    first_year = dates.min().year
    last_year = dates.max().year
    return [y for y in range(first_year, last_year + 1) if last_year - y + 1 >= min_years]


def evaluate_perpetual_success(
    strategy: WithdrawalStrategy,
    close: pd.DataFrame,
    dividends: pd.DataFrame,
    cpi: pd.Series | None,
    min_years: float = 5.0,
) -> dict:
    """"Would this have lasted forever?" can't literally be tested with finite data,
    so approximate it as: starting from every historical year (each with a different
    amount of runway, unlike evaluate_rolling_window's fixed-length windows), simulate
    withdrawing all the way to the *end* of the available data - if it never depletes
    before running out of data to check, count it as surviving so far. A strategy that
    only survives when started at a lucky year (e.g. right before a long bull run)
    will show a low success rate here."""
    start_years = perpetual_start_years(close.index, min_years)

    survived_flags = []
    final_values = []
    years_tested = []
    for start_year in start_years:
        start = f"{start_year}-01-01"
        window_close = close.loc[start:]
        window_dividends = dividends.loc[start:]

        # see the matching comment in evaluate_rolling_window: cpi must stay unsliced
        # so .asof() can resolve the window's first withdrawal date.
        result = strategy.simulate(window_close, window_dividends, cpi)
        final_value = result.value.iloc[-1]
        survived_flags.append(final_value > 0)
        final_values.append(final_value)
        years_tested.append((window_close.index.max() - window_close.index.min()).days / 365.25)

    sorted_values = sorted(final_values)
    return {
        "num_windows": len(start_years),
        "success_rate": sum(survived_flags) / len(survived_flags) if survived_flags else 0.0,
        "median_final_value": sorted_values[len(sorted_values) // 2] if sorted_values else 0.0,
        "worst_final_value": min(final_values) if final_values else 0.0,
        "shortest_years_tested": min(years_tested) if years_tested else 0.0,
        "start_years": start_years,
    }
