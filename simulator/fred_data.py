import pandas as pd

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def fetch_fred_series(series_id: str, start: str, end: str) -> pd.Series:
    """Any single FRED economic data series, sliced to [start, end]. No API key
    needed - FRED serves a plain CSV per series."""
    df = pd.read_csv(
        f"{FRED_CSV_URL}?id={series_id}", parse_dates=["observation_date"], index_col="observation_date"
    )
    return df[series_id].loc[start:end].dropna()
