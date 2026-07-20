def retirement_score(
    survival_probability: float,
    cagr: float,
    max_drawdown: float,
    survival_fraction: float = 1.0,
    survival_weight: float = 100.0,
    growth_weight: float = 100.0,
    risk_weight: float = 50.0,
    longevity_weight: float = 10.0,
) -> float:
    """Composite score for ranking portfolios (higher is better): rewards survival
    probability and CAGR, penalizes drawdown severity. Not bounded to a fixed scale -
    meant for relative comparison between portfolios, not as an absolute grade.

    `survival_fraction` (see metrics.years_survived) is how much of the backtest
    window a depleted portfolio lasted before running out (1.0 if it never does).
    Its weight is deliberately small - it only meaningfully separates portfolios that
    already share the same survival_probability/cagr/max_drawdown outcome (e.g. two
    that both fully deplete), not compete with actually surviving."""
    return (
        survival_probability * survival_weight
        + cagr * growth_weight
        - abs(max_drawdown) * risk_weight
        + survival_fraction * longevity_weight
    )
