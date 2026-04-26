"""
Standalone debug runner for documentation analysis.

Usage (run from web3-dd-bot/):
  python debug_documentation.py <project_name> [--docs <url>] [--website <url>] [--lang ru|en]

Examples:
  python debug_documentation.py "Celestia"
  python debug_documentation.py "Arbitrum" --docs https://docs.arbitrum.io
  python debug_documentation.py "Pixie Chess" --website https://pixiechess.io
  python debug_documentation.py "Sui" --lang en

Output: full documentation_data JSON printed to stdout.
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
            print(f"[debug_documentation] Loaded .env from {candidate}")
            break
    else:
        print("[debug_documentation] No .env found — using shell env vars")
except ImportError:
    print("[debug_documentation] python-dotenv not installed")

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
    docs_url = ""
    website_url = ""
    lang = "ru"

    i = 1
    while i < len(args):
        if args[i] == "--docs" and i + 1 < len(args):
            docs_url = args[i + 1]
            i += 2
        elif args[i] == "--website" and i + 1 < len(args):
            website_url = args[i + 1]
            i += 2
        elif args[i] == "--lang" and i + 1 < len(args):
            lang = args[i + 1]
            i += 2
        else:
            i += 1

    return project_name, docs_url, website_url, lang


# ── 5. Main ───────────────────────────────────────────────────────────────────
async def main():
    project_name, docs_url, website_url, lang = _parse_args()

    print(f"\n{'='*60}")
    print(f"Project : {project_name}")
    print(f"Docs URL: {docs_url or '(auto-discover)'}")
    if website_url:
        print(f"Website : {website_url}")
    print(f"Lang    : {lang}")
    print(f"{'='*60}\n")

    project_urls: dict = {}
    if docs_url:
        project_urls["docs"] = docs_url
    if website_url:
        project_urls["website"] = website_url

    state = {
        "project_name": project_name,
        "project_query": project_name,
        "project_urls": project_urls,
        "lang": lang,
        "enabled_modules": ["documentation"],
        "errors": [],
    }

    from src.agents.documentation import documentation_node

    result = await documentation_node(state)

    doc_data = result.get("documentation_data", {})
    errors = result.get("errors", [])

    print(f"\n{'='*60}")
    print("DOCUMENTATION DATA:")
    print("="*60)
    print(json.dumps(doc_data, indent=2, ensure_ascii=False, default=str))

    if errors:
        print(f"\n{'='*60}")
        print("ERRORS:")
        for e in errors:
            print(f"  - {e}")

    print()


if __name__ == "__main__":
    asyncio.run(main())
