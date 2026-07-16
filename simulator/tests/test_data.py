import pandas as pd

import data as data_module
from data import fetch_price_data


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
