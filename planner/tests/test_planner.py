import json
from unittest.mock import MagicMock

import pytest

from planner.planner import _parse_candidate_etfs, select_candidate_etfs


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


def test_select_candidate_etfs_uses_injected_client():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps({"candidate_etfs": ["QQQ", "TLT"]}))]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    result = select_candidate_etfs(
        additional_contribution=500,
        current_assets=100_000,
        required_monthly_income=3_000,
        free_form_request="prefer growth ETFs",
        client=fake_client,
    )

    assert result == ["QQQ", "TLT"]
    fake_client.messages.create.assert_called_once()


def test_select_candidate_etfs_includes_inputs_in_the_prompt():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps({"candidate_etfs": ["QQQ"]}))]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    select_candidate_etfs(
        additional_contribution=500,
        current_assets=100_000,
        required_monthly_income=3_000,
        free_form_request="include QQQ",
        client=fake_client,
    )

    sent_message = fake_client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "500" in sent_message
    assert "100000" in sent_message
    assert "include QQQ" in sent_message
