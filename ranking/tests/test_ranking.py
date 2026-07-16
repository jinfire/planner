from ranking import rank_portfolios


def test_ranks_by_retirement_score_descending():
    results = [
        {"weights": {"A": 1.0}, "retirement_score": 50.0},
        {"weights": {"B": 1.0}, "retirement_score": 90.0},
        {"weights": {"C": 1.0}, "retirement_score": 70.0},
    ]

    ranked = rank_portfolios(results)

    assert [r["weights"] for r in ranked] == [{"B": 1.0}, {"C": 1.0}, {"A": 1.0}]


def test_empty_list_returns_empty():
    assert rank_portfolios([]) == []


def test_does_not_mutate_input():
    results = [{"retirement_score": 1}, {"retirement_score": 2}]
    original_order = list(results)

    rank_portfolios(results)

    assert results == original_order
