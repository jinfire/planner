import pandas as pd
import pytest

from advisor import describe_ticker, explain_recommendation, recommend_portfolios

TICKERS = ["A", "B", "C"]


def _row(a, b, c, rate, cagr, mdd, survival, years_survived, historical_survived, final_value):
    return {
        "A": a,
        "B": b,
        "C": c,
        "withdrawal_rate": rate,
        "cagr": cagr,
        "mdd": mdd,
        "historical_survived": historical_survived,
        "survival_probability": survival,
        "years_survived": years_survived,
        "final_value": final_value,
        "data_start": "2000-01-01",
        "data_years": 20.0,
    }


def _make_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(1.0, 0.0, 0.0, 0.04, 0.10, -0.30, 0.60, 1.0, True, 3.0),  # row1: A only
            _row(0.0, 1.0, 0.0, 0.04, 0.02, -0.05, 0.95, 1.0, True, 1.5),  # row2: B only
            _row(0.0, 0.0, 1.0, 0.04, -0.01, -0.02, 0.30, 0.4, False, 0.0),  # row3: C only, depleted
            _row(0.5, 0.5, 0.0, 0.04, 0.05, -0.15, 0.80, 1.0, True, 2.0),  # row4: A+B 50/50
            _row(1.0, 0.0, 0.0, 0.05, 0.10, -0.30, 0.55, 1.0, True, 2.8),  # row5: A only, different rate
            _row(0.9, 0.1, 0.0, 0.04, 0.06, -0.20, 0.70, 1.0, True, 2.2),  # row6: A+B 90/10 (dup set w/ row4)
        ]
    )


def test_filters_by_withdrawal_rate():
    results = _make_results()

    recs = recommend_portfolios(results, TICKERS, withdrawal_rate=0.04, total_assets=100_000, top_n=10)

    assert all(r["withdrawal_rate"] == pytest.approx(0.04) for r in recs)
    # row5 (rate=0.05) must never appear, even though it'd otherwise score well
    assert not any(set(r["weights"]) == {"A"} and r["final_value"] == 2.8 for r in recs)


def test_dedups_by_active_ticker_set_keeping_best_score():
    results = _make_results()

    recs = recommend_portfolios(results, TICKERS, withdrawal_rate=0.04, total_assets=100_000, top_n=3)

    active_sets = [frozenset(r["weights"]) for r in recs]
    assert active_sets == [frozenset({"B"}), frozenset({"A", "B"}), frozenset({"A"})]
    # row4 (score 83.5) beats row6 (score 71.2) for the {A, B} slot under default weights
    ab_rec = recs[1]
    assert ab_rec["weights"] == {"A": 0.5, "B": 0.5}


def test_score_weights_change_which_row_wins_a_duplicate_set():
    results = _make_results()

    # growth-only weighting: row6 (cagr=0.06) beats row4 (cagr=0.05) for the {A, B} slot
    recs = recommend_portfolios(
        results,
        TICKERS,
        withdrawal_rate=0.04,
        total_assets=100_000,
        survival_weight=0.0,
        growth_weight=100.0,
        risk_weight=0.0,
        longevity_weight=0.0,
        top_n=3,
    )

    active_sets = [frozenset(r["weights"]) for r in recs]
    assert active_sets == [frozenset({"A"}), frozenset({"A", "B"}), frozenset({"B"})]
    ab_rec = recs[1]
    assert ab_rec["weights"] == {"A": 0.9, "B": 0.1}


def test_depleted_row_reports_estimated_depletion_date():
    results = _make_results()

    recs = recommend_portfolios(results, TICKERS, withdrawal_rate=0.04, total_assets=100_000, top_n=10)

    c_rec = next(r for r in recs if set(r["weights"]) == {"C"})
    assert c_rec["depleted"] is True
    # data_start=2000-01-01 + 0.4 * 20 years (= 8 years, incl. 2 leap years) = 2008-01-01
    assert c_rec["depleted_at"] == "2008-01-01"

    survived_rec = next(r for r in recs if set(r["weights"]) == {"B"})
    assert survived_rec["depleted"] is False
    assert survived_rec["depleted_at"] is None


def test_monthly_withdrawal_scales_with_total_assets():
    results = _make_results()

    recs = recommend_portfolios(results, TICKERS, withdrawal_rate=0.04, total_assets=120_000, top_n=1)

    assert recs[0]["monthly_withdrawal"] == pytest.approx(120_000 * 0.04 / 12)


def test_explain_recommendation_mentions_key_figures():
    results = _make_results()
    rec = recommend_portfolios(results, TICKERS, withdrawal_rate=0.04, total_assets=120_000, top_n=1)[0]

    text = explain_recommendation(rec, rank=1)

    assert "1순위" in text
    assert "B 100%" in text
    assert "4.0%" in text
    assert "생존확률" in text


def test_describe_ticker_adds_asset_class_for_known_tickers():
    assert describe_ticker("IEF") == "IEF(미국 중기국채)"
    assert describe_ticker("GLD") == "GLD(금)"


def test_describe_ticker_falls_back_to_bare_ticker_when_unmapped():
    assert describe_ticker("ZZZ") == "ZZZ"


def test_explain_recommendation_describes_asset_class_not_just_ticker():
    results = _make_results()
    rec = recommend_portfolios(results, TICKERS, withdrawal_rate=0.04, total_assets=120_000, top_n=10)[0]
    # row2 (B only) is the top pick, but B has no asset-class mapping (test fixture
    # tickers aren't real symbols) - swap in a real one to check the labeling itself.
    rec["weights"] = {"GLD": 1.0}

    text = explain_recommendation(rec, rank=1)

    assert "GLD(금) 100%" in text
