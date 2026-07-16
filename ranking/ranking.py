def rank_portfolios(results: list[dict]) -> list[dict]:
    """Sort simulated portfolio results by retirement_score, highest first."""
    return sorted(results, key=lambda r: r["retirement_score"], reverse=True)
