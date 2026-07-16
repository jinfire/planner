def inflation_adjusted_withdrawal(base_withdrawal: float, inflation_rate: float, years_elapsed: int) -> float:
    """Nominal amount needed after `years_elapsed` years of `inflation_rate` inflation
    to match the purchasing power of `base_withdrawal` today."""
    return base_withdrawal * (1 + inflation_rate) ** years_elapsed
