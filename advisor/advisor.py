import pandas as pd

from simulator.retirement_score import retirement_score


def recommend_portfolios(
    results: pd.DataFrame,
    tickers: list[str],
    withdrawal_rate: float,
    total_assets: float,
    survival_weight: float = 100.0,
    growth_weight: float = 20.0,
    risk_weight: float = 50.0,
    longevity_weight: float = 10.0,
    top_n: int = 3,
    rate_tolerance: float = 1e-6,
) -> list[dict]:
    """Pick `top_n` portfolios from a precomputed `results` table (see main.py's
    RESULTS_CSV) that best match the user's own values (score weights) and their
    chosen withdrawal rate - no re-simulation needed, since retirement_score's raw
    inputs (survival_probability/cagr/mdd/years_survived) were already stored
    per-combo. `total_assets` is only used to translate the withdrawal *rate* into an
    actual monthly amount for this user.

    Diversity: only the single best-scoring row per distinct *set of active tickers*
    is kept, so the 3 recommendations aren't near-duplicates of the same allocation
    at slightly different weights."""
    matching = results[(results["withdrawal_rate"] - withdrawal_rate).abs() < rate_tolerance]

    scored = matching.assign(
        score=[
            retirement_score(
                row.survival_probability,
                row.cagr,
                row.mdd,
                row.years_survived,
                survival_weight=survival_weight,
                growth_weight=growth_weight,
                risk_weight=risk_weight,
                longevity_weight=longevity_weight,
            )
            for row in matching.itertuples()
        ]
    ).sort_values("score", ascending=False)

    picked_ticker_sets: set[frozenset] = set()
    recommendations = []
    for row in scored.itertuples():
        weights = {t: getattr(row, t) for t in tickers if getattr(row, t) > 0}
        active = frozenset(weights)
        if active in picked_ticker_sets:
            continue
        picked_ticker_sets.add(active)

        depleted = not row.historical_survived
        recommendations.append(
            {
                "weights": weights,
                "retirement_score": row.score,
                "withdrawal_rate": row.withdrawal_rate,
                "survival_probability": row.survival_probability,
                "cagr": row.cagr,
                "mdd": row.mdd,
                "final_value": row.final_value,
                "data_start": row.data_start,
                "data_years": row.data_years,
                "monthly_withdrawal": total_assets * withdrawal_rate / 12,
                "depleted": depleted,
                "depleted_at": _estimate_depletion_date(row) if depleted else None,
            }
        )
        if len(recommendations) == top_n:
            break

    return recommendations


def _estimate_depletion_date(row) -> str:
    """Only the single fixed-start historical backtest (not the perpetual multi-window
    one) tracks *when* a depleted portfolio ran out - years_survived is the fraction of
    that run's span it lasted. Approximate, not exact (real deplation could land on any
    day, not just proportionally through the span), but honest about its only source."""
    start = pd.Timestamp(row.data_start)
    days_survived = row.years_survived * row.data_years * 365.25
    return (start + pd.Timedelta(days=days_survived)).date().isoformat()


def explain_recommendation(rec: dict, rank: int) -> str:
    """Code-based (no LLM) natural-language summary of one recommendation."""
    allocation = ", ".join(f"{t} {w:.0%}" for t, w in sorted(rec["weights"].items(), key=lambda kv: -kv[1]))
    monthly = f"{rec['monthly_withdrawal']:,.0f}"

    if rec["depleted"]:
        outcome = f"과거 데이터 기준 {rec['depleted_at']}경 자산이 고갈된 이력이 있습니다."
    else:
        outcome = f"과거 데이터 기준 고갈 없이 최종 {rec['final_value']:.2f}배로 유지됐습니다."

    return (
        f"{rank}순위: {allocation} (인출률 {rec['withdrawal_rate']:.1%})\n"
        f"  생존확률 {rec['survival_probability']:.1%}, 월 인출액 약 {monthly}원\n"
        f"  연평균 성장률 {rec['cagr']:.2%}, 최대낙폭 {rec['mdd']:.2%} ({rec['data_years']}년 데이터 기준)\n"
        f"  {outcome}"
    )
