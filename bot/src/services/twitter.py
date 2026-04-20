"""
Twitter/X scraper using Playwright (cookie-based auth, no API).

Auth:
  - TWITTER_AUTH_COOKIE — raw Cookie header string from browser DevTools
                          (e.g. "auth_token=abc123; ct0=xyz…")
                          Copy from: DevTools → Network → any x.com request → Headers → Cookie

Strategy:
  1. find_project_account()  — try common handle patterns; navigate each
                                candidate URL and check that the page resolves
  2. get_profile()           — load x.com/{username}, parse header section
  3. get_recent_tweets()     — scroll timeline, harvest tweet articles from DOM
  4. search_mentions()       — load x.com/search?q={name}, harvest first page

All methods:
  - Cache responses in Redis (TTL 1800 s = 30 min)
  - Return {} / [] on error — never raise
  - Use headless Chromium via Playwright with anti-bot measures
"""
from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import quote

import structlog

from src.config import settings
from src.services.cache import cache_get, cache_set

log = structlog.get_logger()

CACHE_TTL = 1800          # 30 min
PAGE_TIMEOUT = 30_000     # ms — initial page load
NAV_TIMEOUT = 20_000      # ms — subsequent navigations
SCROLL_PAUSE = 3.5        # seconds between scrolls (X needs time to fetch new tweets)
MAX_SCROLL_ROUNDS = 8     # how many times to scroll down the timeline

X_BASE = "https://x.com"

# data-testid selectors — X keeps these stable across redesigns
SEL_TWEET_ARTICLE = 'article[data-testid="tweet"]'
SEL_TWEET_TEXT = '[data-testid="tweetText"]'
SEL_TIMESTAMP = "time[datetime]"
SEL_USER_NAME = '[data-testid="UserName"]'
SEL_USER_DESC = '[data-testid="UserDescription"]'


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_metric(text: str) -> int:
    """'1.2K' → 1200, '2.5M' → 2_500_000, '123' → 123."""
    text = text.strip().replace(",", "")
    try:
        if text.endswith("K"):
            return int(float(text[:-1]) * 1_000)
        if text.endswith("M"):
            return int(float(text[:-1]) * 1_000_000)
        return int(text)
    except (ValueError, TypeError):
        return 0


def _extract_metric_from_aria(label: str, key: str) -> int:
    """
    X puts counts in aria-labels: "1,234 Likes" / "567 Reposts" / "89 Replies".
    key = "like" | "repost" | "retweet" | "reply"
    """
    label_l = label.lower()
    if key.lower() in label_l:
        match = re.search(r"([\d,]+(?:\.\d+)?[KkMm]?)", label)
        if match:
            return _parse_metric(match.group(1))
    return 0


def _parse_cookie_string(raw: str) -> list[dict]:
    """
    Parse a raw "name=value; name2=value2" cookie string into a list of dicts
    suitable for Playwright's context.add_cookies().
    """
    cookies = []
    for part in raw.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".x.com",
            "path": "/",
        })
    return cookies


def _handle_from_url(url: str) -> str | None:
    """Extract 'LayerZero_Labs' from 'https://x.com/LayerZero_Labs' etc."""
    url = url.rstrip("/")
    parts = url.split("/")
    candidate = parts[-1].lstrip("@") if parts else ""
    # Skip known non-handle path segments
    if candidate.lower() in ("twitter.com", "x.com", "search", ""):
        return None
    return candidate


# ---------------------------------------------------------------------------
# Low-level Playwright helpers
# ---------------------------------------------------------------------------

async def _launch_browser():
    """Launch headless Chromium. Returns (playwright_ctx, browser)."""
    from playwright.async_api import async_playwright  # lazy import
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            # Do NOT pass --disable-blink-features=AutomationControlled —
            # it's detectable. We hide webdriver via init script instead.
            "--disable-infobars",
            "--disable-notifications",
            "--start-maximized",
        ],
        ignore_default_args=["--enable-automation"],
    )
    return pw, browser


async def _new_page(browser, raw_cookie: str):
    """
    Create a browser context with auth cookies injected for authenticated sessions.
    """
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )

    # Inject session cookies
    if raw_cookie:
        cookies = _parse_cookie_string(raw_cookie)
        if cookies:
            await context.add_cookies(cookies)

    page = await context.new_page()
    # Hide all common bot-detection signals
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
        Object.defineProperty(navigator, 'permissions', {
            get: () => ({ query: () => Promise.resolve({ state: 'granted' }) })
        });
    """)
    return context, page


async def _scroll_and_collect(page, selector: str, count: int, max_rounds: int | None = None) -> list[Any]:
    """
    Scroll the page up to `max_rounds` times, collecting elements that match
    `selector` until we have at least `count` items or run out of content.
    Returns deduplicated list of element handles.
    """
    seen_ids: set[str] = set()
    elements: list[Any] = []
    rounds = max_rounds if max_rounds is not None else MAX_SCROLL_ROUNDS

    for _ in range(rounds):
        articles = await page.query_selector_all(selector)
        for el in articles:
            # Use tweet URL (/status/ID) as unique key; fall back to timestamp
            link_el = await el.query_selector('a[href*="/status/"]')
            if link_el:
                el_id = await link_el.get_attribute("href") or ""
            else:
                time_el = await el.query_selector("time[datetime]")
                el_id = (await time_el.get_attribute("datetime") or "") if time_el else ""
            if not el_id:
                el_id = str(id(el))  # last resort: object identity
            if el_id not in seen_ids:
                seen_ids.add(el_id)
                elements.append(el)
        if len(elements) >= count:
            break
        prev_count = len(elements)
        # Scroll one viewport at a time — scrolling to the very bottom skips content
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
        await asyncio.sleep(SCROLL_PAUSE)
        # If nothing new appeared after the wait, try one more slow scroll
        articles_now = await page.query_selector_all(selector)
        if len(articles_now) == prev_count:
            await page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
            await asyncio.sleep(SCROLL_PAUSE)

    return elements[:count]


# ---------------------------------------------------------------------------
# Tweet parsing
# ---------------------------------------------------------------------------

async def _parse_tweet_article(article) -> dict | None:
    """
    Extract structured data from a single tweet <article> element.
    Returns None if the element doesn't look like a real tweet.
    """
    try:
        # --- text ---
        # Expand truncated tweets ("Show more" button) before reading text
        show_more = await article.query_selector('[data-testid="tweet-text-show-more-link"]')
        if show_more:
            await show_more.click()
            await asyncio.sleep(0.5)
        text_el = await article.query_selector(SEL_TWEET_TEXT)
        text = (await text_el.inner_text()).strip() if text_el else ""

        # --- timestamp & URL ---
        time_el = await article.query_selector(SEL_TIMESTAMP)
        created_at = ""
        tweet_url = ""
        if time_el:
            created_at = await time_el.get_attribute("datetime") or ""
            # The <time> element is wrapped in an <a href="/user/status/ID">
            parent_a = await time_el.evaluate_handle("el => el.closest('a')")
            if parent_a:
                href = await parent_a.get_attribute("href") or ""
                if "/status/" in href:
                    tweet_url = f"https://x.com{href}" if href.startswith("/") else href

        # --- metrics via aria-label ---
        like_count = retweet_count = reply_count = view_count = 0
        for btn_testid in ("like", "retweet", "reply", "analyticsButton"):
            btn = await article.query_selector(f'[data-testid="{btn_testid}"]')
            if btn:
                aria = await btn.get_attribute("aria-label") or ""
                if not aria:
                    span = await btn.query_selector("span")
                    aria = (await span.inner_text()).strip() if span else ""
                n = _parse_metric(aria.split()[0]) if aria else 0
                if btn_testid == "like":
                    like_count = n
                elif btn_testid == "retweet":
                    retweet_count = n
                elif btn_testid == "reply":
                    reply_count = n
                elif btn_testid == "analyticsButton":
                    view_count = n

        # Skip if no text (ads, "show more" cards, etc.)
        if not text:
            return None

        return {
            "text": text,
            "created_at": created_at,
            "url": tweet_url,
            "public_metrics": {
                "like_count": like_count,
                "retweet_count": retweet_count,
                "reply_count": reply_count,
                "view_count": view_count,
            },
        }
    except Exception as e:
        log.debug("twitter.parse_tweet_failed", error=str(e))
        return None


async def _get_article_id(article) -> str:
    """Stable unique ID for a tweet article element (tweet URL or timestamp)."""
    link_el = await article.query_selector('a[href*="/status/"]')
    if link_el:
        return await link_el.get_attribute("href") or str(id(article))
    time_el = await article.query_selector("time[datetime]")
    if time_el:
        return await time_el.get_attribute("datetime") or str(id(article))
    return str(id(article))


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class TwitterClient:
    """Playwright-based scraper for public X (Twitter) profiles."""

    def __init__(self) -> None:
        self._cookie = settings.TWITTER_AUTH_COOKIE.strip()
        if not self._cookie:
            log.warning(
                "twitter.no_credentials",
                hint="Set TWITTER_AUTH_COOKIE in .env (copy Cookie header from x.com DevTools)",
            )

    @property
    def is_configured(self) -> bool:
        return bool(self._cookie)

    # ------------------------------------------------------------------
    # Public API  (same interface as the original stub)
    # ------------------------------------------------------------------

    async def find_project_account(self, project_name: str) -> str | None:
        """
        Try common username patterns derived from the project name.
        Returns the first handle whose x.com profile page loads successfully.
        """
        cache_key = f"tw:find:{project_name.lower()}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached or None

        name_clean = project_name.strip()
        candidates: list[str] = list(dict.fromkeys([
            name_clean.replace(" ", ""),
            name_clean.replace(" ", "_"),
            name_clean.replace(" ", "-"),
            name_clean.lower().replace(" ", ""),
            name_clean.lower().replace(" ", "_"),
        ]))

        pw = browser = None
        try:
            pw, browser = await _launch_browser()
            context, page = await _new_page(browser, self._cookie)
            try:
                for handle in candidates:
                    url = f"{X_BASE}/{handle}"
                    try:
                        resp = await page.goto(url, timeout=NAV_TIMEOUT, wait_until="domcontentloaded")
                        if resp and resp.ok:
                            # Verify it's a real profile (has the UserName element)
                            try:
                                await page.wait_for_selector(SEL_USER_NAME, timeout=5_000)
                                log.info("twitter.find_account.found", project=project_name, handle=handle)
                                await cache_set(cache_key, handle, CACHE_TTL)
                                return handle
                            except Exception:
                                pass
                    except Exception:
                        pass
            finally:
                await context.close()
        except Exception as e:
            log.warning("twitter.find_account.error", project=project_name, error=str(e))
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

        log.info("twitter.find_account.not_found", project=project_name)
        await cache_set(cache_key, "", CACHE_TTL)
        return None

    async def get_profile(self, username: str) -> dict:
        """
        Load x.com/{username} and scrape the profile header.

        Returns:
        {
          "username": "LayerZero_Labs",
          "name": "LayerZero",
          "description": "…",
          "public_metrics": {
            "followers_count": 250000,
            "following_count": 500,
            "tweet_count": 0      # X no longer shows this in the header
          }
        }
        """
        cache_key = f"tw:profile:{username.lower()}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        pw = browser = None
        result: dict = {}
        try:
            pw, browser = await _launch_browser()
            context, page = await _new_page(browser, self._cookie)
            try:
                await page.goto(
                    f"{X_BASE}/{username}",
                    timeout=PAGE_TIMEOUT,
                    wait_until="load",
                )
                await page.wait_for_selector(SEL_USER_NAME, timeout=10_000)
                await asyncio.sleep(1.5)

                # --- Display name & handle ---
                name_el = await page.query_selector(SEL_USER_NAME)
                display_name = ""
                if name_el:
                    spans = await name_el.query_selector_all("span")
                    for sp in spans:
                        t = (await sp.inner_text()).strip()
                        if t and not t.startswith("@"):
                            display_name = t
                            break

                # --- Bio ---
                desc_el = await page.query_selector(SEL_USER_DESC)
                description = (await desc_el.inner_text()).strip() if desc_el else ""

                # --- Followers / Following ---
                # X renders these as links: /username/followers and /username/following
                followers = following = 0
                for stat_href, stat_key in [
                    (f"/{username}/followers", "followers"),
                    (f"/{username}/verified_followers", "followers"),
                    (f"/{username}/following", "following"),
                ]:
                    el = await page.query_selector(f'a[href="{stat_href}"]')
                    if not el:
                        continue
                    text = (await el.inner_text()).strip()
                    num = _parse_metric(text.split()[0]) if text else 0
                    if stat_key == "followers" and not followers:
                        followers = num
                    elif stat_key == "following":
                        following = num

                result = {
                    "username": username,
                    "name": display_name,
                    "description": description,
                    "public_metrics": {
                        "followers_count": followers,
                        "following_count": following,
                        "tweet_count": 0,
                    },
                }
                log.info("twitter.get_profile.done", username=username, followers=followers)
            finally:
                await context.close()
        except Exception as e:
            log.warning("twitter.get_profile.error", username=username, error=str(e))
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

        if result:
            await cache_set(cache_key, result, CACHE_TTL)
        return result

    async def get_recent_tweets(self, username: str, count: int = 50) -> list[dict]:
        """
        Scroll through x.com/{username} and return up to `count` recent tweets
        (original posts only — retweets and replies are typically mixed in but
        can be filtered by the caller).

        Returns list of:
        {
          "text": "…",
          "created_at": "2024-05-01T12:00:00.000Z",
          "public_metrics": {
            "like_count": 120,
            "retweet_count": 45,
            "reply_count": 12
          }
        }
        """
        cache_key = f"tw:tweets:{username.lower()}:{count}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        pw = browser = None
        tweets: list[dict] = []
        try:
            pw, browser = await _launch_browser()
            context, page = await _new_page(browser, self._cookie)
            try:
                await page.goto(
                    f"{X_BASE}/{username}",
                    timeout=PAGE_TIMEOUT,
                    wait_until="load",
                )
                # Wait until an actual tweet *with text* is visible (not a skeleton)
                await page.wait_for_selector(SEL_TWEET_TEXT, timeout=20_000)

                seen_ids: set[str] = set()
                no_new_rounds = 0
                max_rounds = min(50, max(MAX_SCROLL_ROUNDS, count + 10))

                for _ in range(max_rounds):
                    articles = await page.query_selector_all(SEL_TWEET_ARTICLE)
                    new_this_round = 0
                    for article in articles:
                        el_id = await _get_article_id(article)
                        if el_id in seen_ids:
                            continue
                        seen_ids.add(el_id)
                        new_this_round += 1
                        parsed = await _parse_tweet_article(article)
                        if parsed:
                            tweets.append(parsed)
                            if len(tweets) >= count:
                                break
                    if len(tweets) >= count:
                        break
                    if new_this_round == 0:
                        no_new_rounds += 1
                        if no_new_rounds >= 2:
                            break
                    else:
                        no_new_rounds = 0
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
                    await asyncio.sleep(SCROLL_PAUSE)

                log.info("twitter.get_tweets.done", username=username, count=len(tweets))
            finally:
                await context.close()
        except Exception as e:
            log.warning("twitter.get_tweets.error", username=username, error=str(e))
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

        if tweets:
            await cache_set(cache_key, tweets, CACHE_TTL)
        return tweets

    async def search_mentions(
        self,
        project_name: str,
        count: int = 30,
        twitter_handle: str | None = None,
    ) -> list[dict]:
        """
        Load x.com/search with a crypto-aware query and collect the first page of results.

        If twitter_handle is provided the query combines @handle mentions with a
        crypto-contextual name search, avoiding false positives from common words.

        Returns list in the same shape as get_recent_tweets(), with an extra
        "author_username" key when detectable.
        """
        cache_key = f"tw:mentions:{project_name.lower()}:{twitter_handle or ''}:{count}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        pw = browser = None
        tweets: list[dict] = []
        try:
            pw, browser = await _launch_browser()
            context, page = await _new_page(browser, self._cookie)
            try:
                _CRYPTO = "(crypto OR token OR blockchain OR web3 OR defi OR airdrop)"
                if twitter_handle:
                    query = f'@{twitter_handle} OR ("{project_name}" {_CRYPTO})'
                else:
                    query = f'"{project_name}" {_CRYPTO}'
                search_url = (
                    f"{X_BASE}/search?q={quote(query, safe='')}"
                    f"&src=typed_query&f=live"
                )
                await page.goto(search_url, timeout=PAGE_TIMEOUT, wait_until="load")
                await page.wait_for_selector(SEL_TWEET_TEXT, timeout=20_000)

                seen_ids: set[str] = set()
                no_new_rounds = 0
                max_rounds = min(50, max(MAX_SCROLL_ROUNDS, count + 10))

                for _ in range(max_rounds):
                    articles = await page.query_selector_all(SEL_TWEET_ARTICLE)
                    new_this_round = 0
                    for article in articles:
                        el_id = await _get_article_id(article)
                        if el_id in seen_ids:
                            continue
                        seen_ids.add(el_id)
                        new_this_round += 1
                        parsed = await _parse_tweet_article(article)
                        if parsed:
                            author_el = await article.query_selector('[data-testid="User-Name"] a')
                            if author_el:
                                href = await author_el.get_attribute("href") or ""
                                handle = _handle_from_url(href)
                                if handle:
                                    parsed["author_username"] = handle
                            tweets.append(parsed)
                            if len(tweets) >= count:
                                break
                    if len(tweets) >= count:
                        break
                    if new_this_round == 0:
                        no_new_rounds += 1
                        if no_new_rounds >= 2:
                            break
                    else:
                        no_new_rounds = 0
                    await page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
                    await asyncio.sleep(SCROLL_PAUSE)

                log.info("twitter.search_mentions.done", project=project_name, count=len(tweets))
            finally:
                await context.close()
        except Exception as e:
            log.warning("twitter.search_mentions.error", project=project_name, error=str(e))
        finally:
            if browser:
                await browser.close()
            if pw:
                await pw.stop()

        if tweets:
            await cache_set(cache_key, tweets, CACHE_TTL)
        return tweets
