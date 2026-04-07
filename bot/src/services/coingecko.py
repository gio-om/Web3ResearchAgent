"""
Async client for CoinGecko API (free tier, no API key required).

Caches all responses in Redis (TTL 1 hour).
Retries on 429 with exponential backoff.
"""
import asyncio
import hashlib
import json
from typing import Any

import httpx
import structlog

from src.config import settings
from src.services.cache import cache_get, cache_set

log = structlog.get_logger()

BASE_URL = "https://api.coingecko.com/api/v3"
CACHE_TTL = 3600          # 1 hour
REQUEST_TIMEOUT = 20.0
MAX_RETRIES = 3
BASE_RETRY_DELAY = 2.0


def _cache_key(path: str, params: dict) -> str:
    raw = f"coingecko:{path}:{json.dumps(params, sort_keys=True)}"
    return hashlib.sha256(raw.encode()).hexdigest()


class CoinGeckoError(Exception):
    pass


class CoinGeckoClient:
    """
    Stateless async CoinGecko client.
    Creates a fresh httpx.AsyncClient per request to avoid connection reuse issues
    in long-running async applications.
    """

    _HEADERS = {
        "Accept": "application/json",
        "User-Agent": "Web3DDBot/0.1",
    }

    async def _get(self, path: str, params: dict | None = None) -> Any:
        """
        GET request with Redis cache + retry on 429.
        Returns parsed JSON or raises CoinGeckoError.
        """
        params = params or {}
        key = _cache_key(path, params)

        cached = await cache_get(key)
        if cached is not None:
            log.debug("coingecko.cache_hit", path=path)
            return cached

        url = f"{BASE_URL}{path}"
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=REQUEST_TIMEOUT,
                    headers=self._HEADERS,
                    follow_redirects=True,
                ) as client:
                    resp = await client.get(url, params=params)

                if resp.status_code == 429:
                    delay = BASE_RETRY_DELAY * (2 ** attempt)
                    log.warning("coingecko.rate_limit", attempt=attempt + 1, retry_in=delay)
                    await asyncio.sleep(delay)
                    continue

                resp.raise_for_status()
                data = resp.json()
                await cache_set(key, data, CACHE_TTL)
                return data

            except httpx.HTTPStatusError as e:
                log.error("coingecko.http_error", status=e.response.status_code, path=path)
                raise CoinGeckoError(f"HTTP {e.response.status_code} from CoinGecko") from e
            except httpx.RequestError as e:
                delay = BASE_RETRY_DELAY * (2 ** attempt)
                log.warning("coingecko.request_error", attempt=attempt + 1, error=str(e), retry_in=delay)
                last_error = e
                await asyncio.sleep(delay)

        raise CoinGeckoError(f"CoinGecko request failed after {MAX_RETRIES} attempts") from last_error

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def search_coin_id(self, name: str) -> str | None:
        """
        Find CoinGecko coin ID by project name.
        Returns the best-matching ID or None if not found.
        """
        try:
            data = await self._get("/search", {"query": name})
        except CoinGeckoError as e:
            log.warning("coingecko.search_failed", name=name, error=str(e))
            return None

        coins = data.get("coins", []) if isinstance(data, dict) else []
        if not coins:
            return None

        # Prefer exact name/symbol match
        name_lower = name.lower()
        for coin in coins:
            if coin.get("name", "").lower() == name_lower:
                return coin["id"]
            if coin.get("symbol", "").lower() == name_lower:
                return coin["id"]

        return coins[0]["id"]

    async def get_market_data(self, coin_id: str) -> dict:
        """
        Get market data for a coin by CoinGecko ID.

        Returns a flat dict with keys:
          name, symbol, description, website, twitter_handle,
          current_price_usd, market_cap_usd, fdv_usd, ath_usd,
          circulating_supply, total_supply, categories
        """
        try:
            raw = await self._get(
                f"/coins/{coin_id}",
                {
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                    "sparkline": "false",
                },
            )
        except CoinGeckoError as e:
            log.warning("coingecko.market_data_failed", coin_id=coin_id, error=str(e))
            return {}

        if not isinstance(raw, dict):
            return {}

        md = raw.get("market_data", {})
        links = raw.get("links", {})

        def usd(field: str) -> float | None:
            v = md.get(field, {})
            return v.get("usd") if isinstance(v, dict) else None

        homepage = links.get("homepage", [])
        twitter_handle = links.get("twitter_screen_name") or None

        return {
            "id": raw.get("id"),
            "name": raw.get("name"),
            "symbol": (raw.get("symbol") or "").upper(),
            "description": (raw.get("description") or {}).get("en", "")[:1000],
            "website": homepage[0] if homepage else None,
            "twitter_handle": twitter_handle,
            "current_price_usd": usd("current_price"),
            "market_cap_usd": usd("market_cap"),
            "fdv_usd": usd("fully_diluted_valuation"),
            "ath_usd": usd("ath"),
            "circulating_supply": md.get("circulating_supply"),
            "total_supply": md.get("total_supply"),
            "max_supply": md.get("max_supply"),
            "categories": raw.get("categories", []),
            # Pass raw market_data for cross-check node
            "_raw_market_data": md,
        }

    async def get_coin_by_name(self, name: str) -> dict:
        """
        Convenience method: search by name, then fetch market data.
        Returns empty dict if not found.
        """
        coin_id = await self.search_coin_id(name)
        if not coin_id:
            log.info("coingecko.not_found", name=name)
            return {}
        return await self.get_market_data(coin_id)

    async def get_price_history(self, coin_id: str, days: int = 90) -> list[dict]:
        """
        Get OHLC price history for the last N days.
        Returns list of {"timestamp_ms", "open", "high", "low", "close"}.
        Used for calculating investor ROI at various entry points.
        """
        try:
            raw = await self._get(
                f"/coins/{coin_id}/ohlc",
                {"vs_currency": "usd", "days": str(days)},
            )
        except CoinGeckoError as e:
            log.warning("coingecko.ohlc_failed", coin_id=coin_id, error=str(e))
            return []

        if not isinstance(raw, list):
            return []

        return [
            {
                "timestamp_ms": entry[0],
                "open": entry[1],
                "high": entry[2],
                "low": entry[3],
                "close": entry[4],
            }
            for entry in raw
            if len(entry) == 5
        ]
