"""
Orchestrator node: normalizes user input, resolves project name and URLs.
"""
import re
import structlog

log = structlog.get_logger()

CRYPTORANK_URL_RE = re.compile(r"cryptorank\.io/price/([a-z0-9\-]+)")
COINGECKO_URL_RE = re.compile(r"coingecko\.com/en/coins/([a-z0-9\-]+)")


async def orchestrator_node(state: dict) -> dict:
    """
    Normalizes project query → project_name + project_urls.
    Uses Claude API to extract project name from arbitrary user input.
    """
    query = state.get("project_query", "").strip()
    log.info("orchestrator.start", query=query)

    project_name = query
    project_slug = ""
    project_urls: dict = {}

    # Check for Cryptorank URL
    if m := CRYPTORANK_URL_RE.search(query):
        project_slug = m.group(1)
        project_name = project_slug.replace("-", " ").title()
        project_urls["cryptorank"] = f"https://cryptorank.io/price/{project_slug}"

    # Check for CoinGecko URL
    elif m := COINGECKO_URL_RE.search(query):
        project_slug = m.group(1)
        project_name = project_slug.replace("-", " ").title()

    # Plain text — normalize locally (no LLM needed for simple names)
    elif not query.startswith("http"):
        project_name = query.strip()
        project_slug = re.sub(r"[^a-z0-9]+", "-", query.lower().strip()).strip("-")

    if not project_slug:
        project_slug = project_name.lower().replace(" ", "-")

    log.info("orchestrator.done", project_name=project_name, project_slug=project_slug)

    return {
        **state,
        "project_name": project_name,
        "project_slug": project_slug,
        "project_urls": project_urls,
        "status": "running",
    }
