import pandas as pd

FRED_CPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"


def fetch_cpi(start: str, end: str) -> pd.Series:
    """Monthly US CPI (CPIAUCSL) index from FRED, sliced to [start, end]."""
    df = pd.read_csv(FRED_CPI_URL, parse_dates=["observation_date"], index_col="observation_date")
    return df["CPIAUCSL"].loc[start:end]


def cpi_adjusted_withdrawal(base_withdrawal: float, cpi: pd.Series, date, base_date) -> float:
    """Nominal withdrawal matching `base_withdrawal`'s purchasing power at
    `base_date`, using the actual CPI ratio between `date` and `base_date`."""
    return base_withdrawal * cpi.asof(date) / cpi.asof(base_date)
