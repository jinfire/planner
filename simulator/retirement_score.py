def retirement_score(
    survival_probability: float,
    cagr: float,
    max_drawdown: float,
    survival_weight: float = 100.0,
    growth_weight: float = 100.0,
    risk_weight: float = 50.0,
) -> float:
    """Composite score for ranking portfolios (higher is better): rewards survival
    probability and CAGR, penalizes drawdown severity. Not bounded to a fixed scale -
    meant for relative comparison between portfolios, not as an absolute grade."""
    return (
        survival_probability * survival_weight
        + cagr * growth_weight
        - abs(max_drawdown) * risk_weight
    )
