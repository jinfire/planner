import json
from unittest.mock import MagicMock

import pytest
import requests

from planner.planner import _parse_candidate_etfs, select_candidate_etfs


def _fake_http_client(reply_text: str) -> MagicMock:
    fake_response = MagicMock()
    fake_response.json.return_value = {"content": [{"text": reply_text}]}
    fake_client = MagicMock()
    fake_client.post.return_value = fake_response
    return fake_client


def test_parse_candidate_etfs_returns_ticker_list():
    text = json.dumps({"candidate_etfs": ["QQQ", "SCHD"]})

    assert _parse_candidate_etfs(text) == ["QQQ", "SCHD"]


def test_parse_candidate_etfs_rejects_empty_list():
    text = json.dumps({"candidate_etfs": []})

    with pytest.raises(ValueError):
        _parse_candidate_etfs(text)


def test_parse_candidate_etfs_rejects_malformed_json():
    with pytest.raises(json.JSONDecodeError):
        _parse_candidate_etfs("not json")


def test_select_candidate_etfs_uses_injected_http_client():
    fake_client = _fake_http_client(json.dumps({"candidate_etfs": ["QQQ", "TLT"]}))

    result = select_candidate_etfs(
        additional_contribution=500,
        current_assets=100_000,
        required_monthly_income=3_000,
        free_form_request="prefer growth ETFs",
        api_key="test-key",
        http_client=fake_client,
    )

    assert result == ["QQQ", "TLT"]
    fake_client.post.assert_called_once()


def test_select_candidate_etfs_sends_api_key_and_prompt():
    fake_client = _fake_http_client(json.dumps({"candidate_etfs": ["QQQ"]}))

    select_candidate_etfs(
        additional_contribution=500,
        current_assets=100_000,
        required_monthly_income=3_000,
        free_form_request="include QQQ",
        api_key="test-key",
        http_client=fake_client,
    )

    _, kwargs = fake_client.post.call_args
    assert kwargs["headers"]["x-api-key"] == "test-key"
    sent_message = kwargs["json"]["messages"][0]["content"]
    assert "500" in sent_message
    assert "100000" in sent_message
    assert "include QQQ" in sent_message


def test_select_candidate_etfs_raises_on_http_error():
    fake_response = MagicMock()
    fake_response.raise_for_status.side_effect = requests.HTTPError("boom")
    fake_client = MagicMock()
    fake_client.post.return_value = fake_response

    with pytest.raises(requests.HTTPError):
        select_candidate_etfs(
            additional_contribution=0,
            current_assets=0,
            required_monthly_income=0,
            api_key="test-key",
            http_client=fake_client,
        )


def test_select_candidate_etfs_reads_api_key_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
    fake_client = _fake_http_client(json.dumps({"candidate_etfs": ["QQQ"]}))

    select_candidate_etfs(
        additional_contribution=0,
        current_assets=0,
        required_monthly_income=0,
        http_client=fake_client,
    )

    _, kwargs = fake_client.post.call_args
    assert kwargs["headers"]["x-api-key"] == "env-key"
