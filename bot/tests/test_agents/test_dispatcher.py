import pytest
from unittest.mock import AsyncMock, patch

from src.agents.graph import dispatcher_node


def _make_agent_result(base_state: dict, data_key: str, done_key: str, extra_errors=None):
    """Return a minimal valid agent result dict."""
    result = {
        **base_state,
        data_key: {"mocked": True},
        done_key: True,
        "errors": list(base_state.get("errors", [])) + (extra_errors or []),
    }
    return result


@pytest.mark.asyncio
async def test_all_four_agents_called(sample_agent_state):
    """dispatcher_node must invoke aggregator, documentation, social, and team agents."""
    mock_agg = AsyncMock(return_value={**sample_agent_state, "aggregator_data": {}, "aggregator_done": True, "errors": []})
    mock_doc = AsyncMock(return_value={**sample_agent_state, "documentation_data": {}, "documentation_done": True, "errors": []})
    mock_soc = AsyncMock(return_value={**sample_agent_state, "social_data": {}, "social_done": True, "errors": []})
    mock_team = AsyncMock(return_value={**sample_agent_state, "team_data": {"members": [], "flags": []}, "team_done": True, "errors": []})

    with patch("src.agents.graph.aggregator_node", mock_agg), \
         patch("src.agents.graph.documentation_node", mock_doc), \
         patch("src.agents.graph.social_node", mock_soc), \
         patch("src.agents.graph.team_node", mock_team):
        await dispatcher_node(sample_agent_state)

    mock_agg.assert_called_once()
    mock_doc.assert_called_once()
    mock_soc.assert_called_once()
    mock_team.assert_called_once()


@pytest.mark.asyncio
async def test_one_agent_crash_does_not_break_pipeline(sample_agent_state):
    """If one agent raises an Exception, other agents still run and errors list is populated."""
    mock_agg = AsyncMock(side_effect=RuntimeError("aggregator exploded"))
    mock_doc = AsyncMock(return_value={**sample_agent_state, "documentation_data": {"ok": True}, "documentation_done": True, "errors": []})
    mock_soc = AsyncMock(return_value={**sample_agent_state, "social_data": {"ok": True}, "social_done": True, "errors": []})
    mock_team = AsyncMock(return_value={**sample_agent_state, "team_data": {"members": [], "flags": []}, "team_done": True, "errors": []})

    with patch("src.agents.graph.aggregator_node", mock_agg), \
         patch("src.agents.graph.documentation_node", mock_doc), \
         patch("src.agents.graph.social_node", mock_soc), \
         patch("src.agents.graph.team_node", mock_team):
        result = await dispatcher_node(sample_agent_state)

    # Crashed agent leaves an error entry
    assert any("crashed" in e or "aggregator" in e.lower() for e in result["errors"])
    # Other agents' data was still merged
    assert result.get("documentation_data", {}).get("ok") is True
    assert result.get("social_data", {}).get("ok") is True


@pytest.mark.asyncio
async def test_errors_from_multiple_agents_merged(sample_agent_state):
    """Errors returned by multiple agents must all appear in the merged state."""
    mock_agg = AsyncMock(return_value={**sample_agent_state, "aggregator_data": {}, "aggregator_done": True, "errors": ["CryptoRank: timeout"]})
    mock_doc = AsyncMock(return_value={**sample_agent_state, "documentation_data": {}, "documentation_done": True, "errors": ["Documentation: 404"]})
    mock_soc = AsyncMock(return_value={**sample_agent_state, "social_data": {}, "social_done": True, "errors": []})
    mock_team = AsyncMock(return_value={**sample_agent_state, "team_data": {"members": [], "flags": []}, "team_done": True, "errors": []})

    with patch("src.agents.graph.aggregator_node", mock_agg), \
         patch("src.agents.graph.documentation_node", mock_doc), \
         patch("src.agents.graph.social_node", mock_soc), \
         patch("src.agents.graph.team_node", mock_team):
        result = await dispatcher_node(sample_agent_state)

    errors = result["errors"]
    assert any("CryptoRank" in e for e in errors)
    assert any("Documentation" in e for e in errors)
