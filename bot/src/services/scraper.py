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

_SKIP_EXTENSIONS = frozenset({
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".woff", ".woff2", ".ttf", ".eot",
})

TOKENOMICS_KEYWORDS = frozenset({
    "tokenomics", "token distribution", "token allocation",
    "vesting", "supply", "emission", "unlock", "tge",
    "whitepaper", "litepaper", "token sale", "fundraising",
})

# Keywords that suggest a link leads to team/about info
TEAM_KEYWORDS = frozenset({"team", "about", "founders", "people"})

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
    external_links: dict[str, str] = field(default_factory=dict)  # label → url


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


async def _validate_external_links(links: dict[str, str]) -> dict[str, str]:
    """Keep only links that respond with HTTP 2xx. Uses concurrent HEAD requests."""
    if not links:
        return {}

    sem = asyncio.Semaphore(5)
    headers = _base_headers(USER_AGENTS[0])

    async def _check(label: str, url: str) -> tuple[str, str] | None:
        async with sem:
            try:
                async with httpx.AsyncClient(
                    timeout=5.0,
                    follow_redirects=True,
                    headers=headers,
                ) as client:
                    resp = await client.head(url)
                    if 200 <= resp.status_code < 300:
                        return label, url
                    # Some servers reject HEAD — retry with GET (headers only)
                    if resp.status_code in (405, 403):
                        async with client.stream("GET", url) as gresp:
                            if 200 <= gresp.status_code < 300:
                                return label, url
            except Exception:
                pass
        return None

    results = await asyncio.gather(*(_check(l, u) for l, u in links.items()))
    return dict(r for r in results if r is not None)


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
        path_lower = urlparse(full).path.lower()
        if any(path_lower.endswith(ext) for ext in _SKIP_EXTENSIONS):
            continue
        if keyword_filter:
            link_text = a.get_text(strip=True).lower()
            path = urlparse(full).path.lower()
            if not any(kw in link_text or kw in path for kw in keyword_filter):
                continue
        links.append(full.split("#")[0])  # Strip fragment
    return links


_SOCIAL_DOMAINS = frozenset({
    "twitter.com", "x.com", "t.me", "telegram.org", "discord.gg", "discord.com",
    "github.com", "medium.com", "linkedin.com", "youtube.com", "instagram.com",
    "reddit.com", "mirror.xyz", "substack.com", "docs.google.com",
})

# Hosting/platform domains whose links appear as footer branding (e.g. "Powered by GitBook").
# Matched against netloc after stripping "www." prefix.
_PLATFORM_DOMAINS = frozenset({
    "gitbook.com",           # "Powered by GitBook" footer badge
    "notion.so",             # Notion platform branding
    "notionhq.com",
    "vercel.com",            # hosting
    "netlify.com",           # hosting
    "webflow.com", "webflow.io",
    "wordpress.com",
    "wixsite.com",
    "squarespace.com",
    "ghost.io",
    "readme.com", "readme.io",  # ReadMe docs platform
    "intercom.io",           # chat widget
    "crisp.chat",
    "zendesk.com",
    "hubspot.com",
    "typeform.com",
    "cloudflare.com",
    "amazonaws.com",
    "googletagmanager.com",
    "google-analytics.com",
    "analytics.google.com",
})

_LABEL_OVERRIDES: dict[str, str] = {
    "twitter.com": "twitter", "x.com": "twitter",
    "t.me": "telegram", "telegram.org": "telegram",
    "discord.gg": "discord", "discord.com": "discord",
    "github.com": "github",
    "medium.com": "medium",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "instagram.com": "instagram",
    "reddit.com": "reddit",
    "mirror.xyz": "mirror",
}


def _collect_external_links(html: str, base_netloc: str) -> dict[str, str]:
    """Extract external HTTP(S) links from a page, keyed by a clean label."""
    soup = BeautifulSoup(html, "lxml")
    result: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        href: str = a["href"].strip()
        if not href.startswith("http"):
            continue
        parsed = urlparse(href)
        netloc = parsed.netloc.lower().removeprefix("www.")
        if netloc == base_netloc:
            continue
        # Skip platform homepage links (e.g. gitbook.com), but keep project pages (gitbook.com/projectname)
        if netloc in _PLATFORM_DOMAINS and parsed.path.strip("/") == "":
            continue
        # Prefer known social domains; also accept any external link with anchor text
        anchor = a.get_text(strip=True)
        label = _LABEL_OVERRIDES.get(netloc) or anchor or netloc
        label = label.lower().strip()
        if not label:
            continue
        # Deduplicate: first occurrence wins
        if label not in result:
            result[label] = href.split("?")[0].rstrip("/")
    return result


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

        # Fallback: scan homepage for docs-related links
        html = await _fetch_html(website_url, self._ua_counter)
        if html:
            soup = BeautifulSoup(html, "lxml")
            _docs_keywords = frozenset({
                "docs", "documentation", "whitepaper", "litepaper",
                "gitbook", "wiki", "learn", "guide", "knowledge",
                "notion", "confluence", "readme",
            })
            candidates_from_page: list[str] = []
            for a in soup.find_all("a", href=True):
                href: str = a["href"].strip()
                if not href or href.startswith("#") or href.startswith("mailto:"):
                    continue
                text = a.get_text(strip=True).lower()
                href_l = href.lower()
                if any(kw in href_l or kw in text for kw in _docs_keywords):
                    full = urljoin(website_url, href)
                    if full not in candidates_from_page:
                        candidates_from_page.append(full)

            for url in candidates_from_page[:5]:
                page_html = await _fetch_html(url, self._ua_counter)
                if page_html and len(page_html) > 1000:
                    log.info("scraper.docs_discovered_from_homepage", url=url)
                    return url
                await asyncio.sleep(0.3)

        return None

    async def scrape_docs_pages(
        self,
        docs_url: str,
        max_pages: int = MAX_PAGES,
        on_page=None,  # Optional[Callable[[str], Awaitable[None]]]
    ) -> list[ScrapedPage]:
        """
        BFS crawl from docs_url within the same domain.
        Collects all readable pages — no keyword filter.
        Returns up to max_pages pages.
        """
        base_netloc = urlparse(docs_url).netloc
        visited: set[str] = set()
        queue: list[str] = [docs_url]
        pages: list[ScrapedPage] = []
        total_bytes = 0

        while queue and len(pages) < max_pages and total_bytes < MAX_TEXT_BYTES:
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
            if not text.strip():
                continue

            total_bytes += len(text.encode("utf-8"))
            soup_tmp = BeautifulSoup(html, "lxml")
            title = _extract_title(soup_tmp)
            tables = _extract_tables(html)
            ext_links = _collect_external_links(html, base_netloc)
            pages.append(ScrapedPage(
                url=url,
                title=title,
                text_content=text[:20_000],
                tables=tables,
                external_links=ext_links,
            ))
            log.debug("scraper.docs_page_collected", url=url, title=title, ext_links=len(ext_links))
            if on_page:
                try:
                    await on_page(url)
                except Exception:
                    pass

            new_links = _collect_internal_links(html, url, base_netloc)
            for link in new_links:
                if link not in visited:
                    queue.append(link)

        log.info(
            "scraper.crawl_done",
            docs_url=docs_url,
            pages_visited=len(visited),
            docs_pages=len(pages),
        )
        return pages

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
