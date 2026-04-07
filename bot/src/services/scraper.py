"""
Universal async documentation scraper.

Strategy:
1. discover_docs_url()  — finds the docs/whitepaper URL from the project website
2. scrape_tokenomics_pages() — BFS crawl within the docs domain, collects pages
   that match tokenomics keywords
3. scrape_page() — single-page fetch used by the team agent

Limits:
- Max 10 pages per crawl
- Max 100 KB of text in total
- 15 s timeout per page
- 1 s delay between requests (respectful crawling)
- User-Agent rotation (2 agents)
"""
import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from bs4 import BeautifulSoup, Tag

from src.config import settings

log = structlog.get_logger()

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

MAX_PAGES = 10
MAX_TEXT_BYTES = 100_000
PAGE_TIMEOUT = 15.0
PAGE_DELAY = 1.0

TOKENOMICS_KEYWORDS = frozenset({
    "tokenomics", "token distribution", "token allocation",
    "vesting", "supply", "emission", "unlock", "tge",
    "whitepaper", "litepaper", "token sale", "fundraising",
})

# Keywords that suggest a link leads to team/about info
TEAM_KEYWORDS = frozenset({"team", "about", "founders", "people", "careers"})

# Subdomains / path patterns tried when looking for docs
DOCS_URL_CANDIDATES = [
    "https://docs.{domain}",
    "https://{base}.gitbook.io",
    "https://whitepaper.{domain}",
    "{origin}/docs",
    "{origin}/whitepaper",
    "{origin}/litepaper",
    "{origin}/learn",
]

USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
]


# ------------------------------------------------------------------
# Data types
# ------------------------------------------------------------------

@dataclass
class ScrapedPage:
    url: str
    title: str
    text_content: str
    tables: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _next_ua(counter: list[int]) -> str:
    ua = USER_AGENTS[counter[0] % len(USER_AGENTS)]
    counter[0] += 1
    return ua


def _base_headers(ua: str) -> dict:
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


async def _fetch_html(url: str, ua_counter: list[int]) -> str | None:
    headers = _base_headers(_next_ua(ua_counter))
    try:
        async with httpx.AsyncClient(
            timeout=PAGE_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            # Only process HTML responses
            ct = resp.headers.get("content-type", "")
            if "html" not in ct and "text" not in ct:
                return None
            return resp.text
    except Exception as e:
        log.debug("scraper.fetch_failed", url=url, error=str(e))
        return None


def _extract_title(soup: BeautifulSoup) -> str:
    tag = soup.find("title")
    if tag:
        return tag.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def _clean_soup(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove boilerplate tags in-place."""
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "meta", "noscript", "svg", "iframe", "aside"]):
        tag.decompose()
    return soup


def _extract_text(html: str) -> str:
    """Extract clean readable text from HTML."""
    soup = BeautifulSoup(html, "lxml")
    _clean_soup(soup)
    # Join with newline to preserve structure, then collapse whitespace
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def _extract_tables(html: str) -> list[dict]:
    """
    Extract all HTML tables as list of dicts.
    Each dict: {"headers": [...], "rows": [[...], ...]}
    """
    soup = BeautifulSoup(html, "lxml")
    result = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not cells:
                continue
            if headers and len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))
            else:
                rows.append(cells)
        if rows:
            result.append({"headers": headers, "rows": rows})
    return result


def _is_tokenomics_page(url: str, text: str) -> bool:
    url_l = url.lower()
    text_l = text.lower()[:3000]  # Check only the beginning
    return any(kw in url_l or kw in text_l for kw in TOKENOMICS_KEYWORDS)


def _is_same_domain(url: str, base_netloc: str) -> bool:
    try:
        return urlparse(url).netloc == base_netloc
    except Exception:
        return False


def _collect_internal_links(
    html: str,
    base_url: str,
    base_netloc: str,
    keyword_filter: frozenset | None = None,
) -> list[str]:
    """
    Extract internal links from a page, optionally filtered by keyword.
    """
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("mailto:"):
            continue
        full = urljoin(base_url, href)
        if not _is_same_domain(full, base_netloc):
            continue
        if keyword_filter:
            link_text = a.get_text(strip=True).lower()
            path = urlparse(full).path.lower()
            if not any(kw in link_text or kw in path for kw in keyword_filter):
                continue
        links.append(full.split("#")[0])  # Strip fragment
    return links


# ------------------------------------------------------------------
# Public class
# ------------------------------------------------------------------

class DocumentationScraper:
    """
    Discovers and scrapes project documentation pages.
    Stateless — create a new instance per pipeline run or share one.
    """

    def __init__(self) -> None:
        self._ua_counter = [0]

    async def discover_docs_url(self, website_url: str) -> str | None:
        """
        Try common documentation URL patterns and return the first that responds.
        Also scans the homepage for links to docs/whitepaper.
        """
        parsed = urlparse(website_url)
        domain = parsed.netloc.removeprefix("www.")
        base = parsed.scheme + "://" + parsed.netloc
        base_domain = domain.split(".")[0]

        candidates = [
            tmpl.format(domain=domain, base=base_domain, origin=base.rstrip("/"))
            for tmpl in DOCS_URL_CANDIDATES
        ]
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique = [c for c in candidates if not (c in seen or seen.add(c))]

        for url in unique:
            html = await _fetch_html(url, self._ua_counter)
            if html and len(html) > 1000:
                log.info("scraper.docs_discovered", url=url)
                return url
            await asyncio.sleep(0.3)

        # Fallback: scan homepage for docs/whitepaper links
        html = await _fetch_html(website_url, self._ua_counter)
        if html:
            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href: str = a["href"]
                text = a.get_text(strip=True).lower()
                href_l = href.lower()
                if any(kw in href_l or kw in text for kw in ["docs", "whitepaper", "gitbook", "litepaper"]):
                    return urljoin(website_url, href)

        return None

    async def scrape_tokenomics_pages(self, docs_url: str) -> list[ScrapedPage]:
        """
        BFS crawl from docs_url within the same domain.
        Follows only links that mention tokenomics keywords.
        Returns pages that contain tokenomics-relevant content.
        """
        base_netloc = urlparse(docs_url).netloc
        visited: set[str] = set()
        queue: list[str] = [docs_url]
        pages: list[ScrapedPage] = []
        total_bytes = 0

        while queue and len(pages) < MAX_PAGES and total_bytes < MAX_TEXT_BYTES:
            url = queue.pop(0)
            url_clean = url.split("#")[0]
            if url_clean in visited:
                continue
            visited.add(url_clean)

            await asyncio.sleep(PAGE_DELAY)
            html = await _fetch_html(url, self._ua_counter)
            if not html:
                continue

            text = _extract_text(html)
            total_bytes += len(text.encode("utf-8"))

            if _is_tokenomics_page(url, text):
                soup_tmp = BeautifulSoup(html, "lxml")
                title = _extract_title(soup_tmp)
                tables = _extract_tables(html)
                pages.append(ScrapedPage(
                    url=url,
                    title=title,
                    text_content=text[:20_000],
                    tables=tables,
                ))
                log.debug("scraper.tokenomics_page_found", url=url, title=title)

            # Follow links — prefer tokenomics-related, but also visit all internal
            # links to discover pages the BFS might miss
            new_links = _collect_internal_links(
                html, url, base_netloc,
                keyword_filter=TOKENOMICS_KEYWORDS,
            )
            for link in new_links:
                if link not in visited:
                    queue.append(link)

        log.info(
            "scraper.crawl_done",
            docs_url=docs_url,
            pages_visited=len(visited),
            tokenomics_pages=len(pages),
        )
        return pages

    async def scrape_page(self, url: str) -> ScrapedPage | None:
        """
        Fetch and parse a single page. Returns None on failure.
        Used by the team agent to scrape About/Team pages.
        """
        html = await _fetch_html(url, self._ua_counter)
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")
        title = _extract_title(soup)
        text = _extract_text(html)
        tables = _extract_tables(html)

        return ScrapedPage(
            url=url,
            title=title,
            text_content=text[:20_000],
            tables=tables,
        )

    async def find_team_page(self, website_url: str) -> str | None:
        """
        Scan the homepage and common paths to find the team/about page.
        Returns the URL or None.
        """
        parsed = urlparse(website_url)
        origin = parsed.scheme + "://" + parsed.netloc

        candidates = [
            f"{origin}/team",
            f"{origin}/about",
            f"{origin}/about-us",
            f"{origin}/company",
            f"{origin}/people",
        ]

        # Also check homepage links
        html = await _fetch_html(website_url, self._ua_counter)
        if html:
            homepage_links = _collect_internal_links(
                html, website_url, parsed.netloc, keyword_filter=TEAM_KEYWORDS
            )
            candidates = list(dict.fromkeys(candidates + homepage_links))

        for url in candidates[:8]:
            page_html = await _fetch_html(url, self._ua_counter)
            if page_html and len(page_html) > 500:
                # Verify it actually has team-related content
                text = _extract_text(page_html)[:3000].lower()
                if any(kw in text for kw in TEAM_KEYWORDS):
                    log.info("scraper.team_page_found", url=url)
                    return url
            await asyncio.sleep(0.3)

        return None
