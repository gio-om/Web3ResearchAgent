"""
Standalone debug runner for src/services/twitter.py

Usage (run from web3-dd-bot/bot/):
  python debug_twitter.py find     <project_name>
  python debug_twitter.py profile  <username>
  python debug_twitter.py tweets   <username> [count]
  python debug_twitter.py mentions <project_name> [count]

Options (env vars):
  PAUSE=5        — seconds to freeze before closing browser (default: 5)
  SCREENSHOT=1   — save screenshots to ./debug_screenshots/ on each nav

Browser runs in VISIBLE mode. All logs go to stdout.
Redis / redis module not required.
"""
import asyncio
import json
import logging
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

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
            print(f"[debug_twitter] Loaded .env from {candidate}")
            break
    else:
        print("[debug_twitter] No .env found — using env vars from shell")
except ImportError:
    print("[debug_twitter] python-dotenv not installed")

PAUSE_SECS = int(os.environ.get("PAUSE", "5"))
SCREENSHOT = os.environ.get("SCREENSHOT", "0") != "0"
SCREENSHOT_DIR = Path(__file__).parent / "debug_screenshots"


# ── 1. Fake src.services.cache (no redis needed) ─────────────────────────────
async def _cache_get_stub(key: str):
    log.debug("cache.get [stubbed → miss]", key=key)
    return None

async def _cache_set_stub(key: str, value, ttl: int):
    log.debug("cache.set [stubbed → no-op]", key=key, ttl=ttl)

async def _cache_incr_stub(key: str, ttl_if_new: int) -> int:
    return 0

_fake_cache = types.ModuleType("src.services.cache")
_fake_cache.cache_get = _cache_get_stub
_fake_cache.cache_set = _cache_set_stub
_fake_cache.cache_incr = _cache_incr_stub
sys.modules["src.services.cache"] = _fake_cache


# ── 2. structlog → console ────────────────────────────────────────────────────
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s %(message)s", stream=sys.stdout)
log = structlog.get_logger("debug_twitter")


# ── 3. Visible browser + pause/screenshot wrappers ───────────────────────────
_screenshot_counter = 0

async def _launch_browser_visible():
    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        slow_mo=400,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-notifications",
            "--start-maximized",
        ],
        ignore_default_args=["--enable-automation"],
    )
    log.info("browser.launched", mode="VISIBLE", slow_mo=400)
    return pw, browser


async def _new_page_debug(browser, raw_cookie: str):
    """
    Wraps the original _new_page and patches:
      - page.goto  → logs URL + current title + optional screenshot after nav
      - context.close → pauses PAUSE_SECS seconds so you can inspect the browser
    """
    import src.services.twitter as _tw
    context, page = await _tw._new_page_orig(browser, raw_cookie)

    # --- wrap page.goto to add logging + auto screenshot ---
    _orig_goto = page.goto
    async def _goto_debug(url, **kw):
        log.info("page.goto →", url=url)
        resp = await _orig_goto(url, **kw)
        status = resp.status if resp else "?"
        title = await page.title()
        current = page.url
        log.info("page.loaded", status=status, title=repr(title), url=current)
        # Always take screenshot in debug mode
        global _screenshot_counter
        _screenshot_counter += 1
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        path = SCREENSHOT_DIR / f"{_screenshot_counter:03d}_{status}.png"
        await page.screenshot(path=str(path), full_page=False)
        log.info("screenshot.saved", path=str(path))
        return resp
    page.goto = _goto_debug  # type: ignore[method-assign]

    # --- wrap context.close to pause first ---
    _orig_close = context.close
    async def _close_with_pause(**kw):
        if PAUSE_SECS > 0:
            log.info(f"debug.pause — browser stays open for {PAUSE_SECS}s …")
            await asyncio.sleep(PAUSE_SECS)
        await _orig_close(**kw)
    context.close = _close_with_pause  # type: ignore[method-assign]

    return context, page


# ── 4. Main ───────────────────────────────────────────────────────────────────
async def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()
    arg = sys.argv[2]
    count = int(sys.argv[3]) if len(sys.argv) > 3 else 20

    import src.services.twitter as _tw_mod

    # Save originals so wrappers can call them
    _tw_mod._new_page_orig = _tw_mod._new_page
    _orig_scroll = _tw_mod._scroll_and_collect
    _orig_parse  = _tw_mod._parse_tweet_article

    async def _scroll_debug(page, selector: str, count: int):
        log.info("scroll.start", selector=selector, want=count)
        results = await _orig_scroll(page, selector, count)
        log.info("scroll.done", raw_articles=len(results))
        return results

    async def _parse_debug(article):
        result = await _orig_parse(article)
        if result is None:
            # Show a snippet of the article HTML to understand why it was skipped
            try:
                snippet = (await article.inner_html())[:300].replace("\n", " ")
                log.debug("parse_tweet.skipped (no text?)", html_snippet=snippet)
            except Exception:
                log.debug("parse_tweet.skipped (could not read html)")
        else:
            log.debug("parse_tweet.ok", text_preview=result["text"][:80])
        return result

    with (
        patch.object(_tw_mod, "_launch_browser", side_effect=_launch_browser_visible),
        patch.object(_tw_mod, "_new_page", side_effect=_new_page_debug),
        patch.object(_tw_mod, "_scroll_and_collect", side_effect=_scroll_debug),
        patch.object(_tw_mod, "_parse_tweet_article", side_effect=_parse_debug),
    ):
        from src.services.twitter import TwitterClient

        client = TwitterClient()
        log.info(
            "twitter_client.init",
            has_cookie=bool(client._cookie),
            pause_secs=PAUSE_SECS,
            screenshots=SCREENSHOT,
        )

        result = None

        if command == "find":
            log.info(">> find_project_account", project=arg)
            result = await client.find_project_account(arg)

        elif command == "profile":
            log.info(">> get_profile", username=arg)
            result = await client.get_profile(arg)

        elif command == "tweets":
            log.info(">> get_recent_tweets", username=arg, count=count)
            result = await client.get_recent_tweets(arg, count=count)

        elif command == "mentions":
            log.info(">> search_mentions", project=arg, count=count)
            result = await client.search_mentions(arg, count=count)

        else:
            print(f"Unknown command: {command!r}")
            print(__doc__)
            sys.exit(1)

    print("\n" + "=" * 60)
    print("RESULT:")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    asyncio.run(main())
