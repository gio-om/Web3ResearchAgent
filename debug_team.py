"""
Standalone debug runner for team analysis.

Usage (run from web3-dd-bot/):
  python debug_team.py <project_name> [--website <url>] [--linkedin <url>] [--lang ru|en]
                       [--debug-content] [--debug-search]

Flags:
  --debug-content   Print raw scraped page text (LinkedIn company page, team page)
  --debug-search    Print raw DDG search results before LLM processing

Examples:
  python debug_team.py "Celestia"
  python debug_team.py "Arbitrum" --website https://arbitrum.io
  python debug_team.py "Celestia" --linkedin https://www.linkedin.com/company/celestiaorg
  python debug_team.py "Sui" --website https://sui.io --linkedin https://www.linkedin.com/company/mysten-labs --lang en
  python debug_team.py "Celestia" --debug-search
  python debug_team.py "Celestia" --linkedin https://www.linkedin.com/company/celestiaorg --debug-content --debug-search

Output: full team_data JSON printed to stdout.
"""
import asyncio
import json
import logging
import sys
import types
from pathlib import Path

# Allow imports from bot/src when running from web3-dd-bot/
sys.path.insert(0, str(Path(__file__).parent / "bot"))

import structlog

# ── 0. Load .env ──────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    for candidate in [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
    ]:
        if candidate.exists():
            load_dotenv(candidate)
            print(f"[debug_team] Loaded .env from {candidate}")
            break
    else:
        print("[debug_team] No .env found — using shell env vars")
except ImportError:
    print("[debug_team] python-dotenv not installed")

# ── 1. Stub Redis / cache ─────────────────────────────────────────────────────
async def _cache_get_stub(key: str):
    return None

async def _cache_set_stub(key: str, value, ttl: int):
    pass

async def _cache_incr_stub(key: str, ttl_if_new: int) -> int:
    return 0

_fake_cache = types.ModuleType("src.services.cache")
_fake_cache.cache_get = _cache_get_stub
_fake_cache.cache_set = _cache_set_stub
_fake_cache.cache_incr = _cache_incr_stub
sys.modules["src.services.cache"] = _fake_cache

# ── 2. Stub push_step — print to console instead of editing Telegram message ──
async def _push_step_stub(agent_name: str, step_text: str) -> None:
    print(f"  [{agent_name}] {step_text}")

_fake_graph = types.ModuleType("src.agents.graph")
_fake_graph.push_step = _push_step_stub
sys.modules["src.agents.graph"] = _fake_graph

# ── 3. structlog → console ────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

# ── 4. Parse args ─────────────────────────────────────────────────────────────
def _parse_args():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        sys.exit(1)

    project_name = args[0]
    website_url = ""
    linkedin_url = ""
    lang = "ru"
    debug_content = False
    debug_search = False

    i = 1
    while i < len(args):
        if args[i] == "--website" and i + 1 < len(args):
            website_url = args[i + 1]
            i += 2
        elif args[i] == "--linkedin" and i + 1 < len(args):
            linkedin_url = args[i + 1]
            i += 2
        elif args[i] == "--lang" and i + 1 < len(args):
            lang = args[i + 1]
            i += 2
        elif args[i] == "--debug-content":
            debug_content = True
            i += 1
        elif args[i] == "--debug-search":
            debug_search = True
            i += 1
        else:
            i += 1

    return project_name, website_url, linkedin_url, lang, debug_content, debug_search


# ── 5. Main ───────────────────────────────────────────────────────────────────
async def main():
    project_name, website_url, linkedin_url, lang, debug_content, debug_search = _parse_args()

    print(f"\n{'='*60}")
    print(f"Project : {project_name}")
    if website_url:
        print(f"Website : {website_url}")
    if linkedin_url:
        print(f"LinkedIn: {linkedin_url}")
    print(f"Lang    : {lang}")
    modes = [f for f, on in [("debug-content", debug_content), ("debug-search", debug_search)] if on]
    if modes:
        print(f"Mode    : {', '.join(modes)}")
    print(f"{'='*60}\n")

    project_urls: dict = {}
    if website_url:
        project_urls["website"] = website_url
    if linkedin_url:
        project_urls["linkedin"] = linkedin_url

    # Intercept scraper.scrape_page to print raw page content
    if debug_content:
        from src.services import scraper as _scraper_mod

        _orig_scrape_page = _scraper_mod.DocumentationScraper.scrape_page

        async def _debug_scrape_page(self, url: str):
            page = await _orig_scrape_page(self, url)
            if page:
                print(f"\n{'─'*60}")
                print(f"[debug-content] RAW PAGE: {url}")
                print(f"{'─'*60}")
                print(page.text_content[:5000])
                if len(page.text_content) > 5000:
                    print(f"[... {len(page.text_content)} chars total, showing first 5000 ...]")
                print()
            return page

        _scraper_mod.DocumentationScraper.scrape_page = _debug_scrape_page

    # Intercept _brave_search to print per-query results as they arrive
    if debug_search:
        import src.services.search as _search_mod

        _orig_brave_search = _search_mod._brave_search

        async def _debug_brave_search(query: str, max_results: int = 4):
            results = await _orig_brave_search(query, max_results)
            linkedin_hits = [r for r in results if "linkedin.com/in/" in r["url"]]
            print(f"\n{'─'*60}")
            print(f"[debug-search] QUERY: {query}")
            print(f"  → {len(linkedin_hits)} LinkedIn profiles")
            for r in linkedin_hits:
                print(f"\n  Title  : {r['title']}")
                print(f"  Snippet: {r['snippet']}")
                print(f"  URL    : {r['url']}")
            return results

        _search_mod._brave_search = _debug_brave_search

    state = {
        "project_name": project_name,
        "project_query": project_name,
        "project_urls": project_urls,
        "lang": lang,
        "enabled_modules": ["team"],
        "errors": [],
    }

    from src.config import settings
    print(f"[debug_team] TEAM_SEARCH_MODE = {settings.TEAM_SEARCH_MODE}")
    print(f"[debug_team] APIFY_ACTOR_ID   = {settings.APIFY_ACTOR_ID}")
    print(f"[debug_team] APIFY_TOKEN      = {'SET' if settings.APIFY_TOKEN else 'NOT SET'}")

    from src.agents.team import team_node

    result = await team_node(state)

    team_data = result.get("team_data", {})
    errors = result.get("errors", [])

    print(f"\n{'='*60}")
    print("TEAM DATA:")
    print("="*60)
    print(json.dumps(team_data, indent=2, ensure_ascii=False, default=str))

    if errors:
        print(f"\n{'='*60}")
        print("ERRORS:")
        for e in errors:
            print(f"  - {e}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
