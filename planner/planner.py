import json

import anthropic

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are the Portfolio Planner for a retirement investment system.

Given a user's financial situation and any free-form requests, select a list of
candidate ETF tickers worth evaluating for their retirement portfolio. A separate
system will test every possible weight combination of the ETFs you select, so you
never decide portfolio weights - only which tickers are worth considering.

Respond with ONLY a JSON object in this exact shape, no other text:
{"candidate_etfs": ["TICKER1", "TICKER2", ...]}
"""


def select_candidate_etfs(
    additional_contribution: float,
    current_assets: float,
    required_monthly_income: float,
    free_form_request: str = "",
    client: anthropic.Anthropic | None = None,
) -> list[str]:
    """Ask the LLM to select candidate ETF tickers for the given retirement
    situation. Does not determine portfolio weights - see architecture-1.md."""
    client = client or anthropic.Anthropic()

    user_message = (
        f"Additional monthly contribution: {additional_contribution}\n"
        f"Current retirement assets: {current_assets}\n"
        f"Required monthly retirement income: {required_monthly_income}\n"
        f"Free-form request: {free_form_request or '(none)'}"
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return _parse_candidate_etfs(response.content[0].text)


def _parse_candidate_etfs(text: str) -> list[str]:
    data = json.loads(text)
    tickers = data["candidate_etfs"]
    if not isinstance(tickers, list) or not tickers:
        raise ValueError(f"expected a non-empty list of tickers, got: {tickers!r}")
    return tickers
