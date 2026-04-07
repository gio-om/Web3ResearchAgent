import pytest
from src.agents.cross_check import cross_check_node


@pytest.mark.asyncio
async def test_fdv_mcap_ratio_flag(sample_agent_state, sample_aggregator_data):
    """High FDV/MCap ratio should generate a red flag."""
    state = {
        **sample_agent_state,
        "aggregator_data": sample_aggregator_data,
    }
    result = await cross_check_node(state)
    flags = result["cross_check_results"]
    tokenomics_flags = [f for f in flags if f["category"] == "tokenomics"]
    assert any("FDV" in f["message"] or "ratio" in f["message"].lower() for f in tokenomics_flags)


@pytest.mark.asyncio
async def test_no_flags_on_empty_data(sample_agent_state):
    """Empty data should produce no critical flags."""
    result = await cross_check_node(sample_agent_state)
    red_flags = [f for f in result["cross_check_results"] if f["type"] == "red"]
    assert len(red_flags) == 0


@pytest.mark.asyncio
async def test_team_flags_passed_through(sample_agent_state):
    """Team flags from team agent should be included in cross-check results."""
    state = {
        **sample_agent_state,
        "team_data": {
            "members": [],
            "flags": [{"type": "red", "message": "Fully anonymous team"}],
        },
    }
    result = await cross_check_node(state)
    team_flags = [f for f in result["cross_check_results"] if f["category"] == "team"]
    assert len(team_flags) >= 1
    assert team_flags[0]["type"] == "red"


@pytest.mark.asyncio
async def test_negative_sentiment_generates_flag(sample_agent_state):
    """Negative sentiment score should generate a red flag."""
    state = {
        **sample_agent_state,
        "social_data": {
            "followers_count": 100_000,
            "engagement_rate": 0.02,
            "sentiment_score": -0.5,
            "kol_mentions": [],
            "bot_activity_signals": [],
        },
    }
    result = await cross_check_node(state)
    social_flags = [f for f in result["cross_check_results"] if f["category"] == "social"]
    red_flags = [f for f in social_flags if f["type"] == "red"]
    assert len(red_flags) >= 1
