"""
CryptoRank client — direct JSON API calls to api.cryptorank.io.

Endpoints discovered via DevTools (Fetch/XHR):
  - GET /v0/coins/{slug}                                         → coin metadata
  - GET /v0/funding-rounds/with-investors/by-coin-key/{slug}     → all VC rounds + investors
  - GET /v0/coins/last-by-funding-rounds/{slug}/exclusive        → last funding rounds (alt source)
  - GET /v0/app/coins/{slug}/token-sales/exclusive/limited       → token sales (IDO/IEO/public)
  - GET /v0/app/coins/{slug}/vesting/allocations                 → vesting schedule

Auth: Bearer token from browser DevTools → Network → Authorization header.
All responses cached in Redis (TTL 3600 s).
All methods exception-safe: on error log and return None / [] / {}.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

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


def _extract_investors(investors) -> list[dict]:
    """
    Extract investor {name, logo} from funding round investor objects.

    Handles two formats:
      - tiered dict: {tier1/tier2/.../tier5/angel/other: [{name, logo, ...}]}
      - flat list:   [{name, logo/image, ...}]
    """
    result: list[dict] = []
    seen: set[str] = set()

    if isinstance(investors, dict):
        all_invs: list = []
        for key in ("tier1", "tier2", "tier3", "tier4", "tier5", "angel", "other"):
            all_invs.extend(investors.get(key) or [])
        for inv in all_invs:
            name = inv.get("name") or inv.get("slug", "")
            if name and name not in seen:
                seen.add(name)
                result.append({"name": name, "logo": inv.get("logo")})
    elif isinstance(investors, list):
        for inv in investors:
            name = inv.get("name") or inv.get("slug", "")
            if name and name not in seen:
                seen.add(name)
                result.append({"name": name, "logo": inv.get("logo") or inv.get("image")})

    return result


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class CryptoRankClient:
    """Direct JSON API client for api.cryptorank.io using Bearer token auth."""

    def __init__(self) -> None:
        self.limit_reached: bool = False

    async def _search_by_query(self, name: str) -> dict | None:
        """
        Search via GET /v0/global-search?query=NAME — same endpoint as the CryptoRank website.
        Takes the first cryptoasset result (highest relevance per CryptoRank's own ranking).
        """
        data = await _api_get("/v0/global-search", params={"query": name, "locale": "en", "limit": 5})
        if not data or not isinstance(data, dict):
            return None

        items = (data.get("cryptoassets") or {}).get("data") or []
        if not items:
            return None

        chosen = items[0]
        key = chosen.get("key") or chosen.get("slug") or str(chosen.get("id", ""))
        if not key:
            return None

        # Fetch full details to get social links
        details = await _api_get(f"/v0/coins/{key}")
        coin = (details.get("data") if isinstance(details, dict) else None) or chosen
        links = _extract_links(coin.get("links", []))
        result = {
            "id": key,
            "slug": key,
            "name": coin.get("name", chosen.get("name", name)),
            "symbol": coin.get("symbol", chosen.get("symbol", "")),
            "rank": coin.get("rank") or chosen.get("rank"),
            **links,
        }
        log.info("cryptorank.search.found_via_global", name=name, slug=key, rank=result.get("rank"))
        return result

    async def _slug_lookup(self, name: str) -> dict | None:
        """Direct slug lookup — tries all slug variants, returns first hit with rank."""
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
                "rank": coin.get("rank"),
                **links,
            }
            log.info("cryptorank.search.slug_hit", name=name, slug=coin["key"], rank=result.get("rank"))
            return result
        return None

    async def search_project(self, name: str) -> dict | None:
        """
        Find a project on CryptoRank by name.

        Strategy:
          Runs slug lookup and query search concurrently, then picks the result
          with the better (lower) rank so that more popular/trusted projects win
          over name-collision candidates.

        Returns:
            {"id": slug, "name": ..., "symbol": ..., "website": ..., "twitter": ...}
            or None if not found.
        """
        cache_key = f"cr:search:{name.lower()}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached or None

        # Run both lookups concurrently — slug is fast, query catches popular alternatives
        slug_result, query_result = await asyncio.gather(
            self._slug_lookup(name),
            self._search_by_query(name),
        )

        if slug_result and query_result:
            slug_rank = slug_result.get("rank") or 999_999
            query_rank = query_result.get("rank") or 999_999
            result = slug_result if slug_rank <= query_rank else query_result
            log.info(
                "cryptorank.search.picked",
                name=name,
                slug_candidate=slug_result["slug"],
                slug_rank=slug_rank,
                query_candidate=query_result["slug"],
                query_rank=query_rank,
                chosen=result["slug"],
            )
        else:
            result = slug_result or query_result

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

    def _parse_round_item(self, r: dict) -> dict | None:
        """Parse a single funding round dict from any CryptoRank endpoint into canonical form."""
        rtype = _map_round_type(r.get("type", "") or r.get("kind", "") or "Unknown")
        date = _parse_date(r.get("date") or r.get("start"))

        raise_val = r.get("raise") or r.get("amount")
        amount = _safe_float(raise_val.get("USD") if isinstance(raise_val, dict) else raise_val)

        price = r.get("price") or r.get("price_usd")
        token_price = _safe_float(price.get("USD") if isinstance(price, dict) else price)

        investors = _extract_investors(r.get("investors") or [])

        return {
            "round_type": rtype,
            "date": date,
            "amount_usd": amount,
            "valuation_usd": _safe_float(r.get("valuation")),
            "token_price": token_price,
            "investors": investors,
            "announcement": r.get("linkToAnnouncement") or r.get("announcement") or "",
        }

    async def get_funding_rounds(self, project_id: str) -> list[dict]:
        """
        Get all funding rounds with investors (name + logo).

        Tries three endpoints concurrently and merges results (deduplicated by round_type:date):
          1. GET /v0/app/coins/{slug}/token-sales/exclusive/limited?sortBy=Date
          2. GET /v0/funding-rounds/with-investors/by-coin-key/{slug}/exclusive
          3. GET /v0/coins/last-by-funding-rounds/{slug}/exclusive?locale=en

        Returns list of:
            {round_type, date, amount_usd, valuation_usd, token_price, investors, announcement}
        where investors = [{name, logo}]
        """
        cache_key = f"cr:funding4:{project_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        sales_data, with_inv_data, last_rounds_data = await asyncio.gather(
            _api_get(
                f"/v0/app/coins/{project_id}/token-sales/exclusive/limited",
                params={"sortBy": "Date"},
            ),
            _api_get(
                f"/v0/funding-rounds/with-investors/by-coin-key/{project_id}/exclusive",
            ),
            _api_get(
                f"/v0/coins/last-by-funding-rounds/{project_id}/exclusive",
                params={"locale": "en"},
            ),
        )

        # Collect raw round dicts from all responses
        raw_rounds: list[dict] = []

        def _extract_raw(resp, endpoint: str) -> list[dict]:
            """Pull round list out of any response shape and detect limit_reached."""
            if resp is None:
                return []
            if isinstance(resp, list):
                return resp
            if not isinstance(resp, dict):
                return []
            if resp.get("blocked") == "limit_reached":
                log.warning("cryptorank.limit_reached", endpoint=endpoint, slug=project_id)
                self.limit_reached = True
                return []
            log.info("cryptorank.raw_response", endpoint=endpoint, slug=project_id,
                     keys=list(resp.keys())[:8])
            # Try all known nesting patterns
            inner = resp.get("data")
            if isinstance(inner, list):
                return inner
            if isinstance(inner, dict):
                nested = inner.get("rounds") or inner.get("data") or []
                if nested:
                    return nested
            return resp.get("rounds") or resp.get("items") or []

        raw_rounds.extend(_extract_raw(sales_data, "token-sales"))
        raw_rounds.extend(_extract_raw(with_inv_data, "with-investors"))
        raw_rounds.extend(_extract_raw(last_rounds_data, "last-by-funding-rounds"))

        log.info("cryptorank.funding.raw_total", slug=project_id, count=len(raw_rounds))

        rounds: list[dict] = []
        seen_keys: set[str] = set()
        for r in raw_rounds:
            parsed = self._parse_round_item(r)
            if not parsed:
                continue
            key = f"{parsed['round_type']}:{parsed['date']}"
            if key in seen_keys:
                # Keep the one with more investor data
                existing = next((x for x in rounds if f"{x['round_type']}:{x['date']}" == key), None)
                if existing and len(parsed["investors"]) > len(existing["investors"]):
                    existing["investors"] = parsed["investors"]
                continue
            seen_keys.add(key)
            rounds.append(parsed)

        rounds = [r for r in rounds if r["date"] or r["amount_usd"]]
        rounds.sort(key=lambda r: r["date"] or "", reverse=True)

        log.info("cryptorank.funding.done", slug=project_id, count=len(rounds))
        await cache_set(cache_key, rounds, ttl=3600)
        return rounds

    async def get_investors_list(self, project_id: str) -> list[dict]:
        """
        Get flat list of all investors for a project with logos and tier info.

        Endpoint: GET /v0/coins/{slug}/investors-list/exclusive/limited
        Returns list of:
            {name, logo, tier, category, is_lead, stage}
        """
        cache_key = f"cr:investors2:{project_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        data = await _api_get(
            f"/v0/coins/{project_id}/investors-list/exclusive/limited",
            params={"limit": 50, "skip": 0},
        )
        if not data or not isinstance(data, dict):
            return []

        if data.get("blocked") == "limit_reached":
            log.warning("cryptorank.limit_reached", endpoint="investors-list", slug=project_id)
            self.limit_reached = True
            return []

        log.info("cryptorank.investors_list.raw", slug=project_id, keys=list(data.keys())[:8])
        result = []
        for inv in data.get("investors") or data.get("data") or []:
            name = inv.get("name") or inv.get("slug", "")
            if not name:
                continue
            result.append({
                "name": name,
                "logo": inv.get("image"),
                "tier": inv.get("tier"),
                "category": inv.get("category"),
                "is_lead": inv.get("isLead", False),
                "stage": inv.get("stage") or [],
            })

        log.info("cryptorank.investors_list.done", slug=project_id, count=len(result))
        await cache_set(cache_key, result, ttl=3600)
        return result

    async def get_token_vesting(self, project_id: str) -> dict:
        """
        Get token vesting schedule.

        Tries two endpoints (fallback order):
          1. GET /v0/coins/vesting/{slug}/exclusive  (premium, has batches with dates)
          2. GET /v0/app/coins/{slug}/vesting/allocations  (public fallback)

        Returns:
            {
              "tge_start_date": "2024-05-16",
              "allocations": [{
                recipient_type, total_percent, cliff_months, vesting_months,
                tge_percent, round_date, unlock_type, tokens, unlocked_percent
              }]
            }
        """
        cache_key = f"cr:vesting4:{project_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        # Try primary endpoint first, then fallback
        data = await _api_get(f"/v0/coins/vesting/{project_id}/exclusive")
        if not data:
            data = await _api_get(f"/v0/app/coins/{project_id}/vesting/allocations")

        log.debug("cryptorank.vesting.raw", slug=project_id, data_type=type(data).__name__,
                  keys=list(data.keys()) if isinstance(data, dict) else None)

        tge_start_date = None
        allocations_raw: list = []
        if isinstance(data, dict):
            inner = data.get("data") or {}
            if isinstance(inner, dict):
                vesting_meta = inner.get("vesting") or {}
                tge_start_date = _parse_date(
                    vesting_meta.get("tge_start_date") or vesting_meta.get("total_start_date")
                )
                allocations_raw = inner.get("allocations") or []
            # Some endpoints nest differently: data.allocations at top level
            if not allocations_raw:
                allocations_raw = data.get("allocations") or []
            # Or data.data is the list directly
            if not allocations_raw and isinstance(inner, list):
                allocations_raw = inner
        elif isinstance(data, list):
            allocations_raw = data

        log.info("cryptorank.vesting.parsed", slug=project_id, count=len(allocations_raw),
                 tge_date=tge_start_date)

        today = datetime.now(timezone.utc)
        result_allocations: list[dict] = []
        for alloc in allocations_raw:
            batches = alloc.get("batches", []) or []
            tge_pct = next(
                (float(b.get("unlock_percent") or 0) for b in batches if b.get("is_tge")),
                0.0,
            )
            unlocked_pct = 0.0
            for b in batches:
                try:
                    bd = datetime.fromisoformat(b["date"].replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                if bd <= today:
                    unlocked_pct += float(b.get("unlock_percent") or 0)

            result_allocations.append({
                "recipient_type": alloc.get("name", "Unknown"),
                "total_percent": float(alloc.get("tokens_percent", 0) or 0),
                "cliff_months": _cliff_months(batches),
                "vesting_months": _vesting_months(alloc),
                "tge_percent": tge_pct,
                "round_date": _parse_date(alloc.get("round_date")),
                "unlock_type": alloc.get("unlock_type", "linear"),
                "tokens": int(alloc.get("tokens") or 0),
                "unlocked_percent": round(min(unlocked_pct, 100.0), 4),
            })

        result = {
            "tge_start_date": tge_start_date,
            "allocations": result_allocations,
        }
        log.info("cryptorank.vesting.done", slug=project_id, count=len(result_allocations))
        await cache_set(cache_key, result, ttl=3600)
        return result
