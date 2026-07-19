import json
import os

import requests

MODEL = "claude-sonnet-5"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

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
    api_key: str | None = None,
    http_client=requests,
) -> list[str]:
    """Ask the LLM to select candidate ETF tickers for the given retirement
    situation, calling the Anthropic Messages API directly over HTTP (no SDK).
    Does not determine portfolio weights - see architecture-1.md.

    `http_client` just needs a `.post(url, headers=, json=)` method returning an
    object with `.raise_for_status()` and `.json()` - defaults to the `requests`
    module itself, but tests inject a fake to avoid a real network call."""
    api_key = api_key or os.environ["ANTHROPIC_API_KEY"]

    user_message = (
        f"Additional monthly contribution: {additional_contribution}\n"
        f"Current retirement assets: {current_assets}\n"
        f"Required monthly retirement income: {required_monthly_income}\n"
        f"Free-form request: {free_form_request or '(none)'}"
    )

    response = http_client.post(
        API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_message}],
        },
    )
    response.raise_for_status()

    return _parse_candidate_etfs(response.json()["content"][0]["text"])


def _parse_candidate_etfs(text: str) -> list[str]:
    data = json.loads(text)
    tickers = data["candidate_etfs"]
    if not isinstance(tickers, list) or not tickers:
        raise ValueError(f"expected a non-empty list of tickers, got: {tickers!r}")
    return tickers
