import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager

from src.agents.analyst import _calculate_score, analyst_node


# ---------------------------------------------------------------------------
# Pure function tests — no mocking needed
# ---------------------------------------------------------------------------

def test_low_fdv_mcap_ratio_score():
    """FDV/MCap ratio < 3 must yield tokenomics_score = 22."""
    aggregator_data = {
        "coingecko": {
            "fdv_usd": 1_000_000_000,    # 1B
            "market_cap_usd": 500_000_000,  # 500M → ratio = 2.0 < 3
        }
    }
    _, scores = _calculate_score(
        aggregator_data=aggregator_data,
        documentation_data={},
        social_data={},
        team_data={"members": []},
        cross_check_results=[],
    )
    assert scores["tokenomics"] == 22


def test_red_flag_penalty():
    """Each red flag subtracts 5, each yellow subtracts 2 from the base score."""
    aggregator_data = {
        "coingecko": {"fdv_usd": 1_000_000_000, "market_cap_usd": 500_000_000}
    }
    flags_one_red = [{"type": "red", "message": "Rug risk", "category": "tokenomics"}]
    flags_one_yellow = [{"type": "yellow", "message": "Low liquidity", "category": "tokenomics"}]

    overall_no_flags, _ = _calculate_score(aggregator_data, {}, {}, {"members": []}, [])
    overall_red, _ = _calculate_score(aggregator_data, {}, {}, {"members": []}, flags_one_red)
    overall_yellow, _ = _calculate_score(aggregator_data, {}, {}, {"members": []}, flags_one_yellow)

    assert overall_no_flags - overall_red == 5
    assert overall_no_flags - overall_yellow == 2


# ---------------------------------------------------------------------------
# analyst_node integration tests — LLM + DB mocked
# ---------------------------------------------------------------------------

def _make_session_ctx():
    """Return an async context manager that yields a mock session."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield mock_session

    return _ctx


def _make_repo_mocks():
    """Return (ProjectRepository mock, ReportRepository mock) configured for normal flow."""
    mock_project = MagicMock()
    mock_project.id = 42

    mock_proj_repo = AsyncMock()
    mock_proj_repo.get_or_create.return_value = (mock_project, True)

    mock_db_report = MagicMock()
    mock_db_report.id = 99

    mock_report_repo = AsyncMock()
    mock_report_repo.create.return_value = mock_db_report
    mock_report_repo.complete = AsyncMock()

    return mock_proj_repo, mock_report_repo


@pytest.mark.asyncio
async def test_coingecko_summary_in_report(sample_agent_state, sample_aggregator_data):
    """report['coingecko_summary'] must contain fdv_usd and market_cap_usd."""
    state = {
        **sample_agent_state,
        "aggregator_data": sample_aggregator_data,
    }

    mock_llm = AsyncMock()
    mock_llm.generate_final_report.return_value = {
        "overall_score": 70,
        "recommendation": "Interesting",
        "summary": "Solid project.",
        "strengths": ["Good investors"],
        "weaknesses": ["High FDV"],
        "tokenomics_score": 18,
        "investors_score": 20,
        "team_score": 15,
        "social_score": 12,
    }

    mock_proj_repo, mock_report_repo = _make_repo_mocks()

    with patch("src.agents.analyst.LLMService", return_value=mock_llm), \
         patch("src.agents.analyst.async_session_factory", _make_session_ctx()), \
         patch("src.agents.analyst.ProjectRepository", return_value=mock_proj_repo), \
         patch("src.agents.analyst.ReportRepository", return_value=mock_report_repo):
        result = await analyst_node(state)

    report = result["report"]
    assert "coingecko_summary" in report
    assert "fdv_usd" in report["coingecko_summary"]
    assert "market_cap_usd" in report["coingecko_summary"]


@pytest.mark.asyncio
async def test_score_blend_formula(sample_agent_state, sample_aggregator_data):
    """Final score = int(formula_score * 0.7 + llm_score * 0.3)."""
    state = {
        **sample_agent_state,
        "aggregator_data": sample_aggregator_data,
        "cross_check_results": [],
    }

    # Pre-compute what _calculate_score will produce for sample_aggregator_data
    formula_score, _ = _calculate_score(
        aggregator_data=sample_aggregator_data,
        documentation_data={},
        social_data={},
        team_data={"members": []},
        cross_check_results=[],
    )
    llm_score = 60
    expected = int(formula_score * 0.7 + llm_score * 0.3)

    mock_llm = AsyncMock()
    mock_llm.generate_final_report.return_value = {
        "overall_score": llm_score,
        "recommendation": "DYOR",
        "summary": "",
        "strengths": [],
        "weaknesses": [],
    }

    mock_proj_repo, mock_report_repo = _make_repo_mocks()

    with patch("src.agents.analyst.LLMService", return_value=mock_llm), \
         patch("src.agents.analyst.async_session_factory", _make_session_ctx()), \
         patch("src.agents.analyst.ProjectRepository", return_value=mock_proj_repo), \
         patch("src.agents.analyst.ReportRepository", return_value=mock_report_repo):
        result = await analyst_node(state)

    assert result["report"]["overall_score"] == expected
