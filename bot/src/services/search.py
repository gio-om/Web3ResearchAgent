"""
Web search via Brave Search API.
Used to find LinkedIn profiles of project team members.

Requires in .env:
  BRAVE_API_KEY=...   (https://api-dashboard.search.brave.com)
"""
import asyncio

import httpx
import structlog

from src.config import settings

log = structlog.get_logger()

SEARCH_TIMEOUT = 15.0
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# Every title is quoted for exact-phrase matching (dork style: site:linkedin.com/in "Title" "Project").
_TITLE_QUERY_GROUPS = [
    '"Founder" OR "Co-Founder" OR "Founding Engineer" OR "Founding Partner"',
    '"CEO" OR "CTO" OR "COO" OR "CFO" OR "CPO" OR "CMO" OR "CSO" OR "CRO" OR "CISO"',
    '"Head of" OR "VP of" OR "Vice President" OR "President" OR "Director"',
    '"Protocol Lead" OR "Core Developer" OR "Core Contributor" OR "Principal Engineer" OR "Staff Engineer" OR "Technical Lead" OR "Lead Engineer"',
    '"Head of Research" OR "Chief Scientist" OR "Research Director" OR "General Counsel" OR "Head of Legal" OR "Head of Ecosystem" OR "Head of Community" OR "Developer Relations"',
]


async def _brave_search(query: str, max_results: int = 4) -> list[dict]:
    """GET Brave Search API. Returns list of {title, snippet, url}."""
    if not settings.BRAVE_API_KEY:
        log.warning("search.brave_not_configured")
        return []

    params = {
        "q": query,
        "count": min(max_results, 20),
        "search_lang": "en",
        "country": "US",
        "safesearch": "off",
    }
    headers = {
        "x-subscription-token": settings.BRAVE_API_KEY,
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            resp = await client.get(BRAVE_SEARCH_URL, params=params, headers=headers)
            resp.raise_for_status()
    except Exception as e:
        log.warning("search.brave_failed", query=query[:100], error=str(e))
        return []

    results = []
    for item in resp.json().get("web", {}).get("results", []):
        results.append({
            "title": item.get("title", ""),
            "snippet": item.get("description", ""),
            "url": item.get("url", ""),
        })

    log.debug("search.brave_results", query=query[:80], count=len(results))
    return results


async def resolve_linkedin_company_name(project_name: str, linkedin_url: str = "") -> str:
    """
    Find the exact company name as it appears on LinkedIn.
    Searches for the LinkedIn company page and parses the page title.
    Returns resolved name, or project_name as fallback.

    LinkedIn page titles look like: "Celestia Labs | LinkedIn"
    """
    if linkedin_url:
        # Strip to just the company slug path for a targeted query
        query = f'site:linkedin.com/company "{project_name}"'
    else:
        query = f'site:linkedin.com/company "{project_name}"'

    results = await _brave_search(query, max_results=5)

    for r in results:
        if "linkedin.com/company/" not in r["url"]:
            continue
        title = r["title"]
        for sep in [" | LinkedIn", " - LinkedIn", " | Linkedin", " - Linkedin"]:
            if sep in title:
                name = title.split(sep)[0].strip()
                if name:
                    log.info("search.company_name_resolved", project=project_name, resolved=name)
                    return name

    log.warning("search.company_name_not_resolved", project=project_name)
    return project_name


async def search_linkedin_team(company_name: str) -> list[dict]:
    """
    Run one Brave query per title to find senior LinkedIn profiles at the project.
    Returns deduplicated results (linkedin.com/in/* only), up to 4 per title.
    """
    seen: set[str] = set()
    all_results: list[dict] = []

    for title_terms in _TITLE_QUERY_GROUPS:
        query = f'site:linkedin.com/in ({title_terms}) "{company_name}"'
        results = await _brave_search(query, max_results=10)

        for r in results:
            url = r["url"]
            if "linkedin.com/in/" not in url:
                continue
            clean_url = url.split("?")[0].rstrip("/")
            if clean_url in seen:
                continue
            seen.add(clean_url)
            r["url"] = clean_url
            all_results.append(r)

        await asyncio.sleep(0.3)

    log.info("search.linkedin_team_done", company=company_name, profiles_found=len(all_results))
    return all_results
