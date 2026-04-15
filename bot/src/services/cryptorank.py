"""
CryptoRank client — direct JSON API calls to api.cryptorank.io.

Endpoints discovered via DevTools (Fetch/XHR):
  - GET /v0/coins/{slug}                                         → coin metadata
  - GET /v0/funding-rounds/with-investors/by-coin-key/{slug}     → all VC rounds + investors
  - GET /v0/app/coins/{slug}/token-sales/exclusive/limited       → token sales (IDO/IEO/public)
  - GET /v0/app/coins/{slug}/vesting/allocations                 → vesting schedule

Auth: Bearer token from browser DevTools → Network → Authorization header.
All responses cached in Redis (TTL 3600 s).
All methods exception-safe: on error log and return None / [] / {}.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

import httpx
import structlog

from src.config import settings
from src.services.cache import cache_get, cache_set

log = structlog.get_logger()

_API_BASE = "https://api.cryptorank.io"
_TIMEOUT = 20


def _build_headers() -> dict:
    """Browser-like headers matching what DevTools shows for api.cryptorank.io requests."""
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://cryptorank.io",
        "Referer": "https://cryptorank.io/",
        "Sec-Ch-Ua": '"Chromium";v="146", "Not-A-Brand";v="24", "Google Chrome";v="146"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
    }
    bearer = settings.CRYPTORANK_BEARER.strip()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


async def _api_get(path: str, params: dict | None = None) -> dict | list | None:
    """GET api.cryptorank.io/{path}, return parsed JSON or None on error."""
    url = f"{_API_BASE}/{path.lstrip('/')}"
    try:
        async with httpx.AsyncClient(
            headers=_build_headers(), timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            resp = await client.get(url, params=params)
            if resp.status_code in (401, 403):
                log.warning(
                    "cryptorank.auth_failed",
                    url=url,
                    status=resp.status_code,
                    hint="CRYPTORANK_BEARER expired — copy a fresh one from browser DevTools",
                )
                return None
            if resp.status_code == 200:
                return resp.json()
            log.debug("cryptorank.unexpected_status", url=url, status=resp.status_code)
    except Exception as e:
        log.debug("cryptorank.fetch_failed", url=url, error=str(e))
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify_candidates(name: str) -> list[str]:
    clean = name.lower().strip()
    seen: set[str] = set()
    result: list[str] = []
    for variant in [
        clean.replace(" ", "-"),
        clean.replace(" ", ""),
        clean.replace(" ", "_"),
        clean,
    ]:
        if variant and variant not in seen:
            seen.add(variant)
            result.append(variant)
    return result


# Used externally by aggregator / resolve_urls for priority back-fill of social URLs.
_LINK_TYPES = {
    "website", "twitter", "telegram", "discord",
    "github", "medium", "reddit", "youtube", "linkedin",
}


def _clean_url(url: str) -> str:
    """Strip trailing slash and query/fragment params from a social URL."""
    # Remove fragment
    url = url.split("#")[0]
    # Remove query string (tracking params like ?hzet=... from CryptoRank)
    url = url.split("?")[0]
    return url.rstrip("/")


def _extract_links(links_list: list) -> dict:
    """
    Extract ALL link URLs from the CryptoRank links array (website, twitter,
    telegram, discord, github, gitbook, whitepaper, blog, etc.).
    Returns clean full URLs keyed by lowercase type name.
    """
    result: dict = {}
    for item in links_list or []:
        t = (item.get("type") or "").lower()
        v = (item.get("value") or "").strip()
        if not v or not t or t in result:
            continue
        result[t] = _clean_url(v)
    return result


def _cliff_months(batches: list) -> int:
    tge_dt: datetime | None = None
    first_unlock_dt: datetime | None = None
    for b in batches or []:
        try:
            d = datetime.fromisoformat(b["date"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if b.get("is_tge") and tge_dt is None:
            tge_dt = d
        elif not b.get("is_tge") and first_unlock_dt is None:
            first_unlock_dt = d
    if tge_dt and first_unlock_dt:
        return max(0, (first_unlock_dt.year - tge_dt.year) * 12
                   + (first_unlock_dt.month - tge_dt.month))
    return 0


def _vesting_months(alloc: dict) -> int:
    val = alloc.get("vesting_duration_value") or 0
    typ = alloc.get("vesting_duration_type", "month")
    return int(val * 12) if typ == "year" else int(val)


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_date(v: str | None) -> str | None:
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return v[:10] if v else None


_ROUND_TYPE_MAP = {
    "SEED": "Seed",
    "SERIES_A": "Series A",
    "SERIES_B": "Series B",
    "SERIES_C": "Series C",
    "PRIVATE": "Private",
    "STRATEGIC": "Strategic",
    "PRE_SEED": "Pre-Seed",
    "PUBLIC": "Public",
    "IDO": "IDO",
    "IEO": "IEO",
    "ICO": "ICO",
}


def _map_round_type(raw: str) -> str:
    return _ROUND_TYPE_MAP.get(raw.upper() if raw else "", raw or "Unknown")


def _extract_investor_names(investors) -> list[str]:
    """
    Extract investor names from funding round investor objects.

    Handles two formats from different endpoints:
      - flat list: [{name: ..., type: LEAD/NORMAL}, ...]
      - tiered dict: {tier1: [...], tier2: [...], tier3: [...]}
    """
    names = []
    if isinstance(investors, dict):
        # /v0/app/coins/{slug}/token-sales/exclusive/limited format
        all_invs = (
            investors.get("tier1", [])
            + investors.get("tier2", [])
            + investors.get("tier3", [])
        )
        for inv in all_invs:
            name = inv.get("name") or inv.get("slug", "")
            if name:
                names.append(name)
    elif isinstance(investors, list):
        # /v0/funding-rounds/with-investors/by-coin-key/{slug} format
        for inv in investors:
            name = inv.get("name") or inv.get("slug", "")
            if name:
                names.append(name)
    return names


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class CryptoRankClient:
    """Direct JSON API client for api.cryptorank.io using Bearer token auth."""

    async def _search_by_query(self, name: str) -> dict | None:
        """
        Fallback search via GET /v0/coins?search=NAME when slug lookup fails.
        Returns the same dict format as search_project, or None.
        """
        data = await _api_get("/v0/coins", params={"search": name, "limit": 10})
        if not data:
            return None
        items = None
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("data") or data.get("coins") or []
        if not items:
            return None

        name_lower = name.lower()
        # Exact symbol or name match; partial name-contains match as second priority
        chosen = None
        partial = None
        for item in items:
            sym = (item.get("symbol") or "").lower()
            nm = (item.get("name") or "").lower()
            if sym == name_lower or nm == name_lower:
                chosen = item
                break
            if partial is None and (name_lower in nm or nm in name_lower):
                partial = item
        if chosen is None:
            chosen = partial
        if chosen is None:
            return None

        key = chosen.get("key") or chosen.get("slug") or chosen.get("id")
        if not key:
            return None

        # Fetch full details to get social links
        details = await _api_get(f"/v0/coins/{key}")
        coin = (details.get("data") if isinstance(details, dict) else None) or chosen
        links = _extract_links(coin.get("links", []))
        result = {
            "id": key,
            "slug": key,
            "name": coin.get("name", name),
            "symbol": coin.get("symbol", ""),
            **links,
        }
        log.info("cryptorank.search.found_via_query", name=name, slug=key)
        return result

    async def search_project(self, name: str) -> dict | None:
        """
        Find a project on CryptoRank by name.

        Strategy:
          1. Direct slug lookup — fast, exact match.
          2. Query-based search (GET /v0/coins?search=NAME) — fallback when slug fails.

        Returns:
            {"id": slug, "name": ..., "symbol": ..., "website": ..., "twitter": ...}
            or None if not found.
        """
        cache_key = f"cr:search:{name.lower()}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached or None

        # Step 1: try direct slug variants
        for slug in _slugify_candidates(name):
            data = await _api_get(f"/v0/coins/{slug}")
            if not data:
                continue
            coin = data.get("data") if isinstance(data, dict) else None
            if not coin or not coin.get("key"):
                continue

            links = _extract_links(coin.get("links", []))
            result = {
                "id": coin["key"],
                "slug": coin["key"],
                "name": coin.get("name", name),
                "symbol": coin.get("symbol", ""),
                # All link types (website, twitter, gitbook, whitepaper, etc.)
                **links,
            }
            log.info("cryptorank.search.found", name=name, slug=coin["key"])
            await cache_set(cache_key, result, ttl=3600)
            return result

        # Step 2: slug lookup failed — try query-based search
        log.info("cryptorank.search.trying_query_fallback", name=name)
        result = await self._search_by_query(name)
        if result:
            await cache_set(cache_key, result, ttl=3600)
            return result

        log.info("cryptorank.search.not_found", name=name)
        await cache_set(cache_key, {}, ttl=600)
        return None

    async def get_project_details(self, project_id: str) -> dict:
        """
        Get project metadata by CryptoRank slug.

        Endpoint: GET /v0/coins/{slug}
        """
        cache_key = f"cr:details:{project_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        data = await _api_get(f"/v0/coins/{project_id}")
        if not data:
            return {}

        coin = data.get("data", {}) if isinstance(data, dict) else {}
        if not coin:
            return {}

        links = _extract_links(coin.get("links", []))
        result = {
            "key": coin.get("key", project_id),
            "name": coin.get("name", ""),
            "symbol": coin.get("symbol", ""),
            "category": coin.get("category", ""),
            "total_supply": coin.get("totalSupply"),
            "max_supply": coin.get("maxSupply"),
            "available_supply": coin.get("availableSupply"),
            "fully_diluted_market_cap": _safe_float(coin.get("fullyDilutedMarketCap")),
            "market_cap": _safe_float(coin.get("marketCap")),
            "rank": coin.get("rank"),
            "has_funding_rounds": coin.get("hasFundingRounds", False),
            "has_vesting": coin.get("hasVesting", False),
            "listing_date": coin.get("listingDate", ""),
            "description": coin.get("shortDescription", ""),
            # All social links as full URLs (keys match _LINK_TYPES)
            **links,
        }
        await cache_set(cache_key, result, ttl=3600)
        return result

    async def get_funding_rounds(self, project_id: str) -> list[dict]:
        """
        Get all funding rounds with named investors.

        Uses two endpoints discovered via DevTools:
          1. /v0/funding-rounds/with-investors/by-coin-key/{slug}
             → VC rounds (Seed, Series A/B/C, Strategic, etc.) with full investor list
          2. /v0/app/coins/{slug}/token-sales/exclusive/limited?sortBy=Date
             → Token sales (IDO, IEO, Public Sale, Private Sale)

        Returns list of:
            {round_type, date, amount_usd, valuation_usd, token_price, investors}
        """
        cache_key = f"cr:funding:{project_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        rounds: list[dict] = []
        seen_keys: set[str] = set()  # dedup by (type, date)

        def _add_round(r: dict, price_field: bool = False) -> None:
            raise_val = r.get("raise")
            amount = _safe_float(raise_val.get("USD") if isinstance(raise_val, dict) else raise_val)

            token_price = None
            if price_field:
                price = r.get("price")
                token_price = _safe_float(price.get("USD") if isinstance(price, dict) else price)

            rtype = _map_round_type(r.get("type", "Unknown"))
            date = _parse_date(r.get("date") or r.get("start"))
            key = f"{rtype}:{date}"
            if key in seen_keys:
                return
            seen_keys.add(key)

            rounds.append({
                "round_type": rtype,
                "date": date,
                "amount_usd": amount,
                "valuation_usd": _safe_float(r.get("valuation")),
                "token_price": token_price,
                "investors": _extract_investor_names(r.get("investors", [])),
                "announcement": r.get("linkToAnnouncement", ""),
            })

        # Fetch both endpoints concurrently — they're independent.
        # Primary: token-sales — ALL rounds (VC + IDO/IEO), investors as {tier1/tier2/tier3}
        # Supplement: funding-rounds/with-investors — flat investor list, may add missing rounds
        sales_data, vc_data = await asyncio.gather(
            _api_get(
                f"/v0/app/coins/{project_id}/token-sales/exclusive/limited",
                params={"sortBy": "Date"},
            ),
            _api_get(f"/v0/funding-rounds/with-investors/by-coin-key/{project_id}"),
        )

        if sales_data:
            items = sales_data.get("rounds", []) if isinstance(sales_data, dict) else sales_data
            for r in items or []:
                _add_round(r, price_field=True)

        if vc_data:
            items = vc_data if isinstance(vc_data, list) else vc_data.get("data", [])
            for r in items or []:
                _add_round(r, price_field=False)

        # Sort by date descending, drop empty placeholders
        rounds = [r for r in rounds if r["date"] or r["amount_usd"]]
        rounds.sort(key=lambda r: r["date"] or "", reverse=True)

        log.info("cryptorank.funding.done", slug=project_id, count=len(rounds))
        await cache_set(cache_key, rounds, ttl=3600)
        return rounds

    async def get_token_vesting(self, project_id: str) -> list[dict]:
        """
        Get token vesting schedule.

        Endpoint (discovered via DevTools):
          GET /v0/coins/vesting/{slug}/exclusive

        Returns list of:
            {recipient_type, total_percent, cliff_months, vesting_months, tge_percent}
        """
        cache_key = f"cr:vesting:{project_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        data = await _api_get(f"/v0/coins/vesting/{project_id}/exclusive")

        allocations: list = []
        if isinstance(data, list):
            allocations = data
        elif isinstance(data, dict):
            # /v0/coins/vesting/{slug}/exclusive → {"data": {"allocations": [...]}}
            inner = data.get("data") or {}
            allocations = (
                inner.get("allocations")
                or data.get("allocations")
                or (inner if isinstance(inner, list) else [])
            )

        result: list[dict] = []
        for alloc in allocations:
            batches = alloc.get("batches", []) or []
            tge_pct = next(
                (b.get("unlock_percent", 0) for b in batches if b.get("is_tge")),
                0,
            )
            result.append({
                "recipient_type": alloc.get("name", "Unknown"),
                "total_percent": float(alloc.get("tokens_percent", 0) or 0),
                "cliff_months": _cliff_months(batches),
                "vesting_months": _vesting_months(alloc),
                "tge_percent": float(tge_pct or 0),
            })

        log.info("cryptorank.vesting.done", slug=project_id, count=len(result))
        await cache_set(cache_key, result, ttl=3600)
        return result
