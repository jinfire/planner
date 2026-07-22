import pandas as pd

import simulator.data as data_module
from simulator.data import fetch_price_data


def test_fetch_price_data_splits_and_aligns(monkeypatch):
    dates = pd.date_range("2020-01-01", periods=4)
    close_raw = pd.DataFrame({"A": [10, 11, None, 13], "B": [20, 21, 22, 23]}, index=dates)
    div_raw = pd.DataFrame({"A": [0, 0, 0, 0.5], "B": [0, 1.0, 0, 0]}, index=dates)
    raw = pd.concat({"Close": close_raw, "Dividends": div_raw}, axis=1)

    monkeypatch.setattr(data_module.yf, "download", lambda *a, **k: raw)

    close, dividends = fetch_price_data(["A", "B"], "2020-01-01", "2020-01-04")

    # the row with NaN close (date index 2) must be dropped
    assert list(close.index) == [dates[0], dates[1], dates[3]]
    assert dividends.loc[dates[3], "A"] == 0.5
    assert dividends.loc[dates[1], "B"] == 1.0
    assert dividends.loc[dates[0], "A"] == 0.0


def test_fetch_price_data_recursively_extends_a_backfill_base_ticker(monkeypatch):
    # QLD's own "real" history only reaches 2015; its backfill base QQQ only reaches
    # 2010 on its own - but QQQ has its own backfill mapping to ^NDX, which reaches
    # back to 2000. QLD's extension should chain through QQQ's extension, not just
    # QQQ's own truncated real data.
    ndx_dates = pd.date_range("2000-01-03", periods=2)
    qqq_dates = pd.date_range("2010-01-04", periods=2)
    qld_dates = pd.date_range("2015-01-05", periods=2)

    def fake_download(tickers, start=None, end=None, auto_adjust=False, actions=False):
        if tickers == ["QLD"]:
            close = pd.DataFrame({"QLD": [50.0, 51.0]}, index=qld_dates)
            div = pd.DataFrame({"QLD": [0.0, 0.0]}, index=qld_dates)
            return pd.concat({"Close": close, "Dividends": div}, axis=1)
        if tickers == "QQQ":
            return pd.DataFrame({"Close": [100.0, 101.0]}, index=qqq_dates)
        if tickers == "^NDX":
            return pd.DataFrame({"Close": [10.0, 10.2]}, index=ndx_dates)
        raise AssertionError(f"unexpected yf.download call: {tickers!r}")

    monkeypatch.setattr(data_module.yf, "download", fake_download)

    close, _ = fetch_price_data(["QLD"], "2000-01-01", "2020-12-31")

    # reaches back near 2000 (via QQQ's own ^NDX extension), not stuck at QQQ's
    # truncated real start (2010) or QLD's own real start (2015)
    assert close.index.min() <= pd.Timestamp("2000-01-13")
