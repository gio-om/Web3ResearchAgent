import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


# Minimal stand-in for ScrapedPage dataclass used by the real scraper
@dataclass
class _FakePage:
    url: str
    text_content: str


@pytest.mark.asyncio
async def test_text_truncated_to_50k(sample_agent_state):
    """Combined scraped text > 50 000 chars must be truncated to 50 000 before LLM call."""
    state = {
        **sample_agent_state,
        "project_urls": {"website": "https://layerzero.network", "docs": "https://docs.layerzero.network"},
    }

    # 3 pages × 20 000 chars = 60 000 total — exceeds the 50 000 limit
    pages = [_FakePage(url=f"https://docs.layerzero.network/page{i}", text_content="x" * 20_000)
             for i in range(3)]

    mock_scraper = AsyncMock()
    mock_scraper.scrape_tokenomics_pages.return_value = pages

    mock_llm = AsyncMock()
    mock_llm.analyze_documentation.return_value = {"token_name": "ZRO", "total_supply": 1_000_000_000}

    with patch("src.agents.documentation.DocumentationScraper", return_value=mock_scraper), \
         patch("src.agents.documentation.LLMService", return_value=mock_llm):
        await documentation_node(state)

    call_kwargs = mock_llm.analyze_documentation.call_args
    passed_prompt = call_kwargs.kwargs.get("task_prompt") or call_kwargs.args[0]
    # The text portion inserted into the prompt must be at most 50 000 chars
    # (the full prompt is longer due to the template, so check the text slice)
    # We verify by checking the total prompt length is less than template overhead + 50 000
    assert len(passed_prompt) <= 50_000 + 2_000  # 2 000 chars of template overhead


@pytest.mark.asyncio
async def test_no_docs_url_graceful(sample_agent_state):
    """No docs or website in project_urls → no exception, documentation_data contains 'error'."""
    state = {
        **sample_agent_state,
        "project_urls": {},  # neither 'docs' nor 'website'
    }

    mock_scraper = AsyncMock()
    mock_llm = AsyncMock()

    with patch("src.agents.documentation.DocumentationScraper", return_value=mock_scraper), \
         patch("src.agents.documentation.LLMService", return_value=mock_llm):
        result = await documentation_node(state)

    assert "error" in result["documentation_data"]
    assert result["documentation_done"] is True
    # Scraper should never have been asked to discover or scrape anything
    mock_scraper.discover_docs_url.assert_not_called()
    mock_scraper.scrape_tokenomics_pages.assert_not_called()


# Import at module level so errors surface early
from src.agents.documentation import documentation_node  # noqa: E402
