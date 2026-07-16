def generate_portfolios(tickers: list[str], step: int = 10) -> list[dict[str, float]]:
    """All weight allocations across tickers in `step`% increments summing to 100%.
    No financial calculation here — pure combinatorics."""
    steps = 100 // step
    combos: list[list[int]] = []

    def helper(remaining: int, index: int, current: list[int]):
        if index == len(tickers) - 1:
            combos.append(current + [remaining])
            return
        for s in range(remaining + 1):
            helper(remaining - s, index + 1, current + [s])

    helper(steps, 0, [])

    return [
        {ticker: units * step / 100 for ticker, units in zip(tickers, combo)}
        for combo in combos
    ]
