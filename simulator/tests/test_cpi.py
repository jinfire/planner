import pandas as pd
import pytest

import simulator.cpi as cpi_module
from simulator.cpi import cpi_adjusted_withdrawal, fetch_cpi


def test_fetch_cpi_slices_to_date_range(monkeypatch):
    dates = pd.to_datetime(["2019-12-01", "2020-01-01", "2020-02-01", "2021-01-01"])
    raw = pd.DataFrame({"CPIAUCSL": [250.0, 251.0, 252.0, 260.0]}, index=dates)
    raw.index.name = "observation_date"

    monkeypatch.setattr(cpi_module.pd, "read_csv", lambda *a, **k: raw)

    result = fetch_cpi("2020-01-01", "2020-02-28")

    assert list(result.index) == [dates[1], dates[2]]
    assert result.tolist() == [251.0, 252.0]


def test_cpi_adjusted_withdrawal_uses_ratio():
    dates = pd.to_datetime(["2020-01-01", "2021-01-01"])
    cpi = pd.Series([100.0, 103.0], index=dates)

    result = cpi_adjusted_withdrawal(1000.0, cpi, dates[1], dates[0])

    assert result == pytest.approx(1030.0)


def test_cpi_adjusted_withdrawal_same_date_returns_base():
    date = pd.Timestamp("2020-01-01")
    cpi = pd.Series([100.0], index=[date])

    result = cpi_adjusted_withdrawal(500.0, cpi, date, date)

    assert result == pytest.approx(500.0)
