import pandas as pd

import simulator.fred_data as fred_data_module
from simulator.fred_data import fetch_fred_series


def test_fetch_fred_series_slices_to_date_range(monkeypatch):
    dates = pd.to_datetime(["2019-12-01", "2020-01-01", "2020-02-01", "2021-01-01"])
    raw = pd.DataFrame({"DGS20": [4.0, 4.1, 4.2, 4.5]}, index=dates)
    raw.index.name = "observation_date"

    monkeypatch.setattr(fred_data_module.pd, "read_csv", lambda *a, **k: raw)

    result = fetch_fred_series("DGS20", "2020-01-01", "2020-02-28")

    assert list(result.index) == [dates[1], dates[2]]
    assert result.tolist() == [4.1, 4.2]


def test_fetch_fred_series_drops_missing_values(monkeypatch):
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"])
    raw = pd.DataFrame({"DTB3": [2.0, None, 2.1]}, index=dates)
    raw.index.name = "observation_date"

    monkeypatch.setattr(fred_data_module.pd, "read_csv", lambda *a, **k: raw)

    result = fetch_fred_series("DTB3", "2020-01-01", "2020-01-31")

    assert list(result.index) == [dates[0], dates[2]]
