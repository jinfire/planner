import pandas as pd
import pytest

from simulator.rolling_window import evaluate_rolling_window, rolling_start_years
from simulator.strategy import WithdrawalResult


class _FakeStrategy:
    """Returns a fixed WithdrawalResult per call, controlled by the window's start
    year, so rolling-window aggregation logic can be tested independent of any real
    withdrawal math (that's covered separately by each engine's own tests)."""

    def __init__(self, fail_years: set[int]):
        self.fail_years = fail_years
        self.seen_ranges: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def simulate(self, close, dividends, cpi):
        self.seen_ranges.append((close.index.min(), close.index.max()))
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
