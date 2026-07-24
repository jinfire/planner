import pandas as pd
import pytest

from simulator.rolling_window import (
    evaluate_perpetual_success,
    evaluate_rolling_window,
    perpetual_start_years,
    rolling_start_years,
)
from simulator.strategy import WithdrawalResult


class _FakeStrategy:
    """Returns a fixed WithdrawalResult per call, controlled by the window's start
    year, so rolling-window aggregation logic can be tested independent of any real
    withdrawal math (that's covered separately by each engine's own tests)."""

    def __init__(self, fail_years: set[int]):
        self.fail_years = fail_years
        self.seen_ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []
        self.seen_cpi: list = []

    def simulate(self, close, dividends, cpi):
        self.seen_ranges.append((close.index.min(), close.index.max()))
        self.seen_cpi.append(cpi)
        start_year = close.index.min().year
        final_value = 0.0 if start_year in self.fail_years else 1.5
        value = pd.Series([1.0, final_value], index=[close.index.min(), close.index.max()])
        return WithdrawalResult(label={}, value=value)


def _make_data(start="2000-01-01", end="2005-12-31"):
    dates = pd.date_range(start, end, freq="D")
    close = pd.DataFrame({"A": [10.0] * len(dates)}, index=dates)
    div = pd.DataFrame({"A": [0.0] * len(dates)}, index=dates)
    return close, div


def test_rolling_start_years_only_includes_windows_that_fully_fit():
    dates = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    assert rolling_start_years(dates, window_years=3) == [2000, 2001, 2002, 2003]


def test_rolling_start_years_single_window_when_span_equals_window():
    dates = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    assert rolling_start_years(dates, window_years=6) == [2000]


def test_evaluate_rolling_window_slices_correct_date_ranges():
    close, div = _make_data()
    strategy = _FakeStrategy(fail_years=set())

    evaluate_rolling_window(strategy, close, div, cpi=None, window_years=3)

    assert strategy.seen_ranges == [
        (pd.Timestamp("2000-01-01"), pd.Timestamp("2002-12-31")),
        (pd.Timestamp("2001-01-01"), pd.Timestamp("2003-12-31")),
        (pd.Timestamp("2002-01-01"), pd.Timestamp("2004-12-31")),
        (pd.Timestamp("2003-01-01"), pd.Timestamp("2005-12-31")),
    ]


def test_evaluate_rolling_window_computes_success_rate():
    close, div = _make_data()
    # 4 windows (2000-2003 starts), 1 of them (starting 2002) fails
    strategy = _FakeStrategy(fail_years={2002})

    result = evaluate_rolling_window(strategy, close, div, cpi=None, window_years=3)

    assert result["num_windows"] == 4
    assert result["success_rate"] == pytest.approx(3 / 4)
    assert result["worst_final_value"] == 0.0


def test_evaluate_rolling_window_all_survive_gives_full_success_rate():
    close, div = _make_data()
    strategy = _FakeStrategy(fail_years=set())

    result = evaluate_rolling_window(strategy, close, div, cpi=None, window_years=3)

    assert result["success_rate"] == pytest.approx(1.0)
    assert result["median_final_value"] == pytest.approx(1.5)


def test_perpetual_start_years_includes_up_to_the_last_year_when_min_years_is_one():
    dates = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    assert perpetual_start_years(dates, min_years=1) == [2000, 2001, 2002, 2003, 2004, 2005]


def test_perpetual_start_years_excludes_years_without_enough_runway():
    dates = pd.date_range("2000-01-01", "2005-12-31", freq="D")
    assert perpetual_start_years(dates, min_years=3) == [2000, 2001, 2002, 2003]


def test_evaluate_perpetual_success_uses_variable_length_windows_all_ending_at_data_end():
    close, div = _make_data()
    strategy = _FakeStrategy(fail_years=set())

    evaluate_perpetual_success(strategy, close, div, cpi=None, min_years=1)

    # every window starts at a different year but all run to the same final date -
    # unlike evaluate_rolling_window, where every window is the same *length* instead
    ends = {end for _, end in strategy.seen_ranges}
    assert ends == {pd.Timestamp("2005-12-31")}
    starts = [start for start, _ in strategy.seen_ranges]
    assert starts == [pd.Timestamp(f"{y}-01-01") for y in range(2000, 2006)]


def test_evaluate_rolling_window_passes_cpi_through_unsliced():
    # Regression test: cpi_adjusted_withdrawal resolves the first withdrawal date via
    # .asof(), which needs CPI history at or before that date. A per-window
    # cpi.loc[start:end] slice left no such entry and silently produced NaN for every
    # window - so each window must receive the *same*, un-sliced cpi series.
    close, div = _make_data()
    cpi = pd.Series([100.0], index=[pd.Timestamp("1999-01-01")])
    strategy = _FakeStrategy(fail_years=set())

    evaluate_rolling_window(strategy, close, div, cpi=cpi, window_years=3)

    assert all(seen is cpi for seen in strategy.seen_cpi)


def test_evaluate_perpetual_success_passes_cpi_through_unsliced():
    close, div = _make_data()
    cpi = pd.Series([100.0], index=[pd.Timestamp("1999-01-01")])
    strategy = _FakeStrategy(fail_years=set())

    evaluate_perpetual_success(strategy, close, div, cpi=cpi, min_years=1)

    assert all(seen is cpi for seen in strategy.seen_cpi)


def test_evaluate_perpetual_success_computes_success_rate():
    close, div = _make_data()
    # starting in 2003 fails to make it to the end; every other start survives
    strategy = _FakeStrategy(fail_years={2003})

    result = evaluate_perpetual_success(strategy, close, div, cpi=None, min_years=1)

    assert result["num_windows"] == 6
    assert result["success_rate"] == pytest.approx(5 / 6)
    assert result["worst_final_value"] == 0.0
