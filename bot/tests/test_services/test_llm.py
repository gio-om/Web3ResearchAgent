"""Tests for LLMService — all Claude API calls are mocked."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.llm import LLMService, _strip_fences, _parse_json, LLMError


# ------------------------------------------------------------------
# Unit tests for helpers
# ------------------------------------------------------------------

def test_strip_fences_plain_json():
    raw = '{"key": "value"}'
    assert _strip_fences(raw) == '{"key": "value"}'


def test_strip_fences_with_json_block():
    raw = "```json\n{\"key\": \"value\"}\n```"
    assert _strip_fences(raw) == '{"key": "value"}'


def test_strip_fences_with_plain_block():
    raw = "```\n[1, 2, 3]\n```"
    assert _strip_fences(raw) == "[1, 2, 3]"


def test_strip_fences_trims_whitespace():
    raw = "  \n```json\n{}\n```\n  "
    assert _strip_fences(raw) == "{}"


def test_parse_json_valid():
    result = _parse_json('{"score": 75}')
    assert result == {"score": 75}


def test_parse_json_with_fences():
    result = _parse_json('```json\n{"score": 75}\n```')
    assert result == {"score": 75}


def test_parse_json_extracts_embedded_object():
    raw = "Sure, here's the JSON: {\"score\": 75} done."
    result = _parse_json(raw)
    assert result == {"score": 75}


def test_parse_json_raises_on_garbage():
    with pytest.raises(LLMError):
        _parse_json("This is not JSON at all.")


# ------------------------------------------------------------------
# Integration-style tests with mocked Anthropic client
# ------------------------------------------------------------------

def _make_mock_response(text: str):
    content = MagicMock()
    content.text = text
    response = MagicMock()
    response.content = [content]
    return response


@pytest.fixture
def llm_with_mock():
    """LLMService with a mocked Anthropic client."""
    with patch("src.services.llm.AsyncAnthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages = MagicMock()
        instance.messages.create = AsyncMock()
        service = LLMService()
        service._client = instance
        yield service, instance


@pytest.mark.asyncio
async def test_extract_json_returns_parsed_dict(llm_with_mock):
    service, mock_client = llm_with_mock
    mock_client.messages.create.return_value = _make_mock_response('{"project_name": "LayerZero"}')

    result = await service.extract_json("some prompt")
    assert result == {"project_name": "LayerZero"}


@pytest.mark.asyncio
async def test_analyze_documentation_returns_dict(llm_with_mock):
    service, mock_client = llm_with_mock
    payload = {
        "token_name": "ZRO",
        "total_supply": 1_000_000_000,
        "vesting_schedules": [],
    }
    mock_client.messages.create.return_value = _make_mock_response(json.dumps(payload))

    result = await service.analyze_documentation("extract tokenomics...")
    assert result["token_name"] == "ZRO"
    assert result["total_supply"] == 1_000_000_000


@pytest.mark.asyncio
async def test_analyze_documentation_returns_error_on_bad_json(llm_with_mock):
    service, mock_client = llm_with_mock
    mock_client.messages.create.return_value = _make_mock_response("not json at all!!!")

    result = await service.analyze_documentation("task")
    assert "error" in result or "raw" in result


@pytest.mark.asyncio
async def test_analyze_sentiment_empty_tweets(llm_with_mock):
    service, _ = llm_with_mock
    result = await service.analyze_sentiment([], "TestProject")
    assert result["sentiment_score"] == 0.0
    assert result["overall_assessment"] == "No tweets available"
    # Should NOT call the API
    service._client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_analyze_sentiment_parses_response(llm_with_mock):
    service, mock_client = llm_with_mock
    payload = {
        "sentiment_score": 0.6,
        "key_concerns": ["inflation risk"],
        "positive_signals": ["Tier-1 backers"],
        "notable_supporters": ["@CryptoKOL"],
        "bot_activity_signals": [],
        "overall_assessment": "Mostly positive",
    }
    mock_client.messages.create.return_value = _make_mock_response(json.dumps(payload))

    result = await service.analyze_sentiment(["tweet1", "tweet2"], "MyProject")
    assert result["sentiment_score"] == 0.6
    assert "inflation risk" in result["key_concerns"]


@pytest.mark.asyncio
async def test_normalize_project_query(llm_with_mock):
    service, mock_client = llm_with_mock
    payload = {
        "project_name": "LayerZero",
        "project_slug": "layerzero",
        "possible_website": "https://layerzero.network",
        "possible_twitter": None,
    }
    mock_client.messages.create.return_value = _make_mock_response(json.dumps(payload))

    result = await service.normalize_project_query("layerzero")
    assert result["project_name"] == "LayerZero"
    assert result["project_slug"] == "layerzero"


@pytest.mark.asyncio
async def test_extract_team_members_returns_list(llm_with_mock):
    service, mock_client = llm_with_mock
    payload = [
        {"name": "Alice", "role": "CEO", "linkedin_url": None,
         "previous_companies": ["Google"], "profile_notes": ""},
    ]
    mock_client.messages.create.return_value = _make_mock_response(json.dumps(payload))

    result = await service.extract_team_members("some team page content")
    assert len(result) == 1
    assert result[0]["name"] == "Alice"


@pytest.mark.asyncio
async def test_extract_team_members_empty_content(llm_with_mock):
    service, _ = llm_with_mock
    result = await service.extract_team_members("")
    assert result == []
