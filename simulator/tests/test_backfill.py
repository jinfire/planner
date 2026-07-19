import pandas as pd
import pytest

import simulator.backfill as backfill_module
from simulator.backfill import extend_close_series, replicate_leverage, splice_series


def test_replicate_leverage_doubles_returns_with_no_expense():
    dates = pd.date_range("2020-01-01", periods=3)
    base = pd.Series([100, 110, 99], index=dates)  # returns: +10%, -10%

    result = replicate_leverage(base, multiplier=2.0, expense_ratio=0.0)

    assert result.iloc[0] == pytest.approx(1.0)
    assert result.iloc[1] == pytest.approx(1.2)  # +20%
    assert result.iloc[2] == pytest.approx(1.2 * 0.8)  # -20%


def test_replicate_leverage_applies_daily_expense_drag():
    dates = pd.date_range("2020-01-01", periods=2)
    base = pd.Series([100, 102], index=dates)  # +2%

    result = replicate_leverage(base, multiplier=3.0, expense_ratio=0.0504)  # daily = 0.0002

    assert result.iloc[1] == pytest.approx(1 + (0.02 * 3 - 0.0002))


def test_splice_series_chain_links_proxy_before_real_start():
    dates = pd.date_range("2020-01-01", periods=5)
    proxy = pd.Series([50, 55, 60], index=dates[:3])
    real = pd.Series([200, 210], index=dates[3:])

    result = splice_series(proxy, real)

    assert list(result.index) == list(dates)
    assert result.iloc[0] == pytest.approx(200 / 1.2)
    assert result.iloc[1] == pytest.approx(200 / 1.2 * 1.1)
    assert result.iloc[2] == pytest.approx(200.0)
    assert result.iloc[3] == pytest.approx(200.0)
    assert result.iloc[4] == pytest.approx(210.0)


def test_splice_series_returns_real_unchanged_when_proxy_has_no_earlier_history():
    dates = pd.date_range("2020-01-01", periods=2)
    proxy = pd.Series([1.0], index=[dates[1]])
    real = pd.Series([200, 210], index=dates)

    result = splice_series(proxy, real)

    pd.testing.assert_series_equal(result, real)


def test_extend_close_series_returns_real_when_already_covers_start():
    dates = pd.date_range("2020-01-01", periods=2)
    real = pd.Series([10, 11], index=dates)

    result = extend_close_series("XYZ", start=dates[0], real=real, fetch_close=lambda t: None)

    pd.testing.assert_series_equal(result, real)


def test_extend_close_series_prefers_leverage_replication(monkeypatch):
    monkeypatch.setattr(backfill_module, "LEVERAGE_REPLICATION", {"QLD": ("QQQ", 2.0, 0.0)})
    monkeypatch.setattr(backfill_module, "INDEX_PROXY", {"QLD": "SHOULD_NOT_BE_USED"})

    early = pd.date_range("2000-01-01", periods=2)
    late = pd.date_range("2000-02-01", periods=2)  # >10 days after `early` (tolerance window)
    base_close = pd.Series([100, 110, 121, 133.1], index=early.append(late))
    real = pd.Series([50, 55], index=late)

    calls = []

    def fetch_close(ticker):
        calls.append(ticker)
        return base_close if ticker == "QQQ" else None

    result = extend_close_series("QLD", start=early[0], real=real, fetch_close=fetch_close)

    assert calls == ["QQQ"]
    assert result.index.min() == early[0]
    assert result.iloc[-1] == pytest.approx(55.0)


def test_extend_close_series_falls_back_to_index_proxy_when_no_leverage_map(monkeypatch):
    monkeypatch.setattr(backfill_module, "LEVERAGE_REPLICATION", {})
    monkeypatch.setattr(backfill_module, "INDEX_PROXY", {"SPY": "^GSPC"})
    monkeypatch.setattr(backfill_module, "SPLICE_PROXY", {"SPY": "SHOULD_NOT_BE_USED"})

    proxy_dates = pd.date_range("2020-01-01", periods=4)
    real_dates = pd.date_range("2020-02-01", periods=2)  # >10 days after proxy_dates[0]
    proxy_close = pd.Series([100, 105, 110, 115], index=proxy_dates)
    real = pd.Series([200, 210], index=real_dates)

    result = extend_close_series(
        "SPY", start=proxy_dates[0], real=real, fetch_close=lambda t: proxy_close if t == "^GSPC" else None
    )

    assert result.index.min() == proxy_dates[0]


def test_extend_close_series_falls_back_to_splice_proxy_last(monkeypatch):
    monkeypatch.setattr(backfill_module, "LEVERAGE_REPLICATION", {})
    monkeypatch.setattr(backfill_module, "INDEX_PROXY", {})
    monkeypatch.setattr(backfill_module, "SPLICE_PROXY", {"SCHD": "VYM"})

    proxy_dates = pd.date_range("2020-01-01", periods=4)
    real_dates = pd.date_range("2020-02-01", periods=2)  # >10 days after proxy_dates[0]
    proxy_close = pd.Series([10, 11, 12, 13], index=proxy_dates)
    real = pd.Series([100, 105], index=real_dates)

    result = extend_close_series(
        "SCHD", start=proxy_dates[0], real=real, fetch_close=lambda t: proxy_close if t == "VYM" else None
    )

    assert result.index.min() == proxy_dates[0]


def test_extend_close_series_keeps_partial_extension_even_if_it_falls_short(monkeypatch):
    monkeypatch.setattr(backfill_module, "LEVERAGE_REPLICATION", {})
    monkeypatch.setattr(backfill_module, "INDEX_PROXY", {})
    monkeypatch.setattr(backfill_module, "SPLICE_PROXY", {"SCHD": "VYM"})

    # proxy only reaches partway back to `start` - still an improvement worth keeping
    proxy_dates = pd.date_range("2006-01-01", periods=2)
    real_dates = pd.date_range("2011-01-01", periods=2)
    proxy_close = pd.Series([10, 11], index=proxy_dates)
    real = pd.Series([100, 105], index=real_dates)

    result = extend_close_series(
        "SCHD",
        start=pd.Timestamp("2000-01-01"),
        real=real,
        fetch_close=lambda t: proxy_close if t == "VYM" else None,
    )

    assert result.index.min() == proxy_dates[0]
    assert result.index.min() > pd.Timestamp("2000-01-01")  # still short of `start`


def test_extend_close_series_returns_truncated_real_when_no_mapping(monkeypatch):
    monkeypatch.setattr(backfill_module, "LEVERAGE_REPLICATION", {})
    monkeypatch.setattr(backfill_module, "INDEX_PROXY", {})
    monkeypatch.setattr(backfill_module, "SPLICE_PROXY", {})

    dates = pd.date_range("2020-01-05", periods=2)
    real = pd.Series([100, 105], index=dates)

    result = extend_close_series(
        "TLT", start=pd.Timestamp("2000-01-01"), real=real, fetch_close=lambda t: None
    )

    pd.testing.assert_series_equal(result, real)
