"""Tests for DocumentationScraper — all HTTP calls are mocked."""
import pytest
from unittest.mock import AsyncMock, patch

from src.services.scraper import (
    DocumentationScraper,
    ScrapedPage,
    _extract_text,
    _extract_tables,
    _is_tokenomics_page,
    _collect_internal_links,
)


# ------------------------------------------------------------------
# Unit tests for helpers
# ------------------------------------------------------------------

def test_extract_text_removes_scripts():
    html = "<html><body><script>alert(1)</script><p>Token supply: 1B</p></body></html>"
    text = _extract_text(html)
    assert "alert" not in text
    assert "Token supply" in text


def test_extract_text_removes_nav_footer():
    html = "<html><body><nav>Menu</nav><main><p>Vesting 24 months</p></main><footer>© 2024</footer></body></html>"
    text = _extract_text(html)
    assert "Menu" not in text
    assert "2024" not in text
    assert "Vesting" in text


def test_extract_tables_with_headers():
    html = """
    <table>
        <tr><th>Category</th><th>Allocation</th><th>Vesting</th></tr>
        <tr><td>Team</td><td>15%</td><td>36 months</td></tr>
        <tr><td>Investors</td><td>20%</td><td>24 months</td></tr>
    </table>
    """
    tables = _extract_tables(html)
    assert len(tables) == 1
    assert tables[0]["headers"] == ["Category", "Allocation", "Vesting"]
    assert len(tables[0]["rows"]) == 2
    assert tables[0]["rows"][0] == {"Category": "Team", "Allocation": "15%", "Vesting": "36 months"}


def test_extract_tables_without_headers():
    html = "<table><tr><td>A</td><td>B</td></tr></table>"
    tables = _extract_tables(html)
    assert tables[0]["rows"][0] == ["A", "B"]


def test_extract_tables_skips_empty():
    html = "<table><tr><th>Header</th></tr></table>"
    tables = _extract_tables(html)
    assert tables == []


def test_is_tokenomics_page_by_url():
    assert _is_tokenomics_page("https://docs.example.com/tokenomics", "")
    assert _is_tokenomics_page("https://docs.example.com/vesting-schedule", "")
    assert not _is_tokenomics_page("https://docs.example.com/team", "contact us here")


def test_is_tokenomics_page_by_text():
    assert _is_tokenomics_page("https://docs.example.com/overview", "TGE unlock percent is 10%")
    assert _is_tokenomics_page("https://docs.example.com/x", "total supply 1 billion tokens")
    assert not _is_tokenomics_page("https://docs.example.com/x", "our team is distributed globally")


def test_collect_internal_links():
    html = """
    <html><body>
      <a href="/tokenomics">Tokenomics</a>
      <a href="/vesting">Vesting</a>
      <a href="https://external.com/vesting">External</a>
      <a href="/about">About</a>
    </body></html>
    """
    from src.services.scraper import TOKENOMICS_KEYWORDS
    links = _collect_internal_links(
        html,
        base_url="https://docs.test.com/intro",
        base_netloc="docs.test.com",
        keyword_filter=TOKENOMICS_KEYWORDS,
    )
    assert "https://docs.test.com/tokenomics" in links
    assert "https://docs.test.com/vesting" in links
    assert "https://external.com/vesting" not in links
    assert "https://docs.test.com/about" not in links


def test_collect_internal_links_no_filter():
    html = '<a href="/page1">P1</a><a href="https://other.com/page">External</a>'
    links = _collect_internal_links(
        html,
        base_url="https://docs.test.com/",
        base_netloc="docs.test.com",
    )
    assert "https://docs.test.com/page1" in links
    assert "https://other.com/page" not in links


# ------------------------------------------------------------------
# Integration-style tests (HTTP mocked)
# ------------------------------------------------------------------

@pytest.fixture
def scraper():
    return DocumentationScraper()


@pytest.mark.asyncio
async def test_scrape_page_returns_none_on_failure(scraper):
    with patch("src.services.scraper._fetch_html", return_value=None):
        result = await scraper.scrape_page("https://nonexistent.example.com/docs")
    assert result is None


@pytest.mark.asyncio
async def test_scrape_page_returns_scraped_page(scraper):
    html = "<html><title>Tokenomics</title><body><p>Total supply 1B. Vesting 24 months.</p></body></html>"
    with patch("src.services.scraper._fetch_html", return_value=html):
        result = await scraper.scrape_page("https://docs.example.com/tokenomics")
    assert isinstance(result, ScrapedPage)
    assert result.title == "Tokenomics"
    assert "Total supply" in result.text_content
    assert result.url == "https://docs.example.com/tokenomics"


@pytest.mark.asyncio
async def test_discover_docs_url_finds_first_responding(scraper):
    async def fake_fetch(url, ua_counter):
        if "docs." in url:
            return "<html><body>Documentation site with lots of content here</body></html>"
        return None

    with patch("src.services.scraper._fetch_html", side_effect=fake_fetch), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await scraper.discover_docs_url("https://example.com")
    assert result is not None
    assert "docs." in result


@pytest.mark.asyncio
async def test_discover_docs_url_falls_back_to_homepage_link(scraper):
    homepage_html = """
    <html><body>
      <a href="https://myproject.gitbook.io">Read the docs</a>
    </body></html>
    """

    async def fake_fetch(url, ua_counter):
        if url == "https://example.com":
            return homepage_html
        return None  # All pattern candidates fail

    with patch("src.services.scraper._fetch_html", side_effect=fake_fetch), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        result = await scraper.discover_docs_url("https://example.com")
    assert result == "https://myproject.gitbook.io"


@pytest.mark.asyncio
async def test_scrape_tokenomics_pages_collects_relevant_pages(scraper):
    tokenomics_html = """
    <html><title>Token Distribution</title>
    <body>
      <p>Total supply 1,000,000,000 ZRO. Vesting schedule: Team 15% cliff 12 months.</p>
      <a href="/tokenomics/vesting">Vesting Details</a>
    </body></html>
    """
    vesting_html = """
    <html><title>Vesting</title>
    <body><p>Token allocation vesting: investors 20%, TGE unlock 5%.</p></body>
    </html>
    """

    call_count = [0]
    async def fake_fetch(url, ua_counter):
        call_count[0] += 1
        if "vesting" in url:
            return vesting_html
        return tokenomics_html

    with patch("src.services.scraper._fetch_html", side_effect=fake_fetch), \
         patch("asyncio.sleep", new_callable=AsyncMock):
        pages = await scraper.scrape_tokenomics_pages("https://docs.example.com/tokenomics")

    assert len(pages) >= 1
    assert all(isinstance(p, ScrapedPage) for p in pages)
    assert any("Total supply" in p.text_content or "Vesting" in p.title for p in pages)
