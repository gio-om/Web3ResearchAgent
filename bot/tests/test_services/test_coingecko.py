"""Tests for CoinGeckoClient — all HTTP calls are mocked."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.coingecko import CoinGeckoClient, CoinGeckoError


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

SEARCH_RESPONSE = {
    "coins": [
        {"id": "layerzero", "name": "LayerZero", "symbol": "ZRO", "market_cap_rank": 50},
        {"id": "layerzero-fake", "name": "LayerZero Fake", "symbol": "FAKE", "market_cap_rank": 999},
    ]
}

COIN_DETAIL_RESPONSE = {
    "id": "layerzero",
    "name": "LayerZero",
    "symbol": "zro",
    "description": {"en": "Omnichain interoperability protocol."},
    "links": {
        "homepage": ["https://layerzero.network"],
        "twitter_screen_name": "LayerZero_Labs",
    },
    "categories": ["Cross-chain", "Interoperability"],
    "market_data": {
        "current_price": {"usd": 3.5},
        "market_cap": {"usd": 300_000_000},
        "fully_diluted_valuation": {"usd": 3_500_000_000},
        "ath": {"usd": 10.0},
        "circulating_supply": 85_000_000,
        "total_supply": 1_000_000_000,
        "max_supply": 1_000_000_000,
    },
}


def _mock_httpx_response(data: dict, status: int = 200):
    response = MagicMock()
    response.status_code = status
    response.json.return_value = data
    response.raise_for_status = MagicMock()
    if status >= 400:
        from httpx import HTTPStatusError, Request, Response
        response.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    headers_mock = MagicMock()
    headers_mock.get.return_value = "text/html"
    response.headers = headers_mock
    return response


@pytest.fixture
def client():
    return CoinGeckoClient()


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_coin_id_exact_name_match(client):
    """Should prefer exact name match over first result."""
    with patch("src.services.coingecko.cache_get", return_value=None), \
         patch("src.services.coingecko.cache_set", new_callable=AsyncMock), \
         patch("httpx.AsyncClient") as MockClient:

        mock_resp = _mock_httpx_response(SEARCH_RESPONSE)
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        result = await client.search_coin_id("LayerZero")
        assert result == "layerzero"


@pytest.mark.asyncio
async def test_search_coin_id_returns_none_on_empty(client):
    with patch("src.services.coingecko.cache_get", return_value=None), \
         patch("src.services.coingecko.cache_set", new_callable=AsyncMock), \
         patch("httpx.AsyncClient") as MockClient:

        mock_resp = _mock_httpx_response({"coins": []})
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        result = await client.search_coin_id("nonexistent_xyz_abc")
        assert result is None


@pytest.mark.asyncio
async def test_get_market_data_parses_flat_structure(client):
    with patch("src.services.coingecko.cache_get", return_value=None), \
         patch("src.services.coingecko.cache_set", new_callable=AsyncMock), \
         patch("httpx.AsyncClient") as MockClient:

        mock_resp = _mock_httpx_response(COIN_DETAIL_RESPONSE)
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)

        result = await client.get_market_data("layerzero")

        assert result["name"] == "LayerZero"
        assert result["symbol"] == "ZRO"
        assert result["current_price_usd"] == 3.5
        assert result["market_cap_usd"] == 300_000_000
        assert result["fdv_usd"] == 3_500_000_000
        assert result["website"] == "https://layerzero.network"
        assert result["twitter_handle"] == "LayerZero_Labs"
        assert "Cross-chain" in result["categories"]


@pytest.mark.asyncio
async def test_get_market_data_returns_empty_on_error(client):
    with patch("src.services.coingecko.cache_get", return_value=None), \
         patch("src.services.coingecko.cache_set", new_callable=AsyncMock), \
         patch("httpx.AsyncClient") as MockClient:

        from httpx import RequestError, Request
        MockClient.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=RequestError("timeout", request=MagicMock())
        )

        result = await client.get_market_data("layerzero")
        assert result == {}


@pytest.mark.asyncio
async def test_cache_is_used_on_second_call(client):
    """Second call with same args should hit cache, not make HTTP request."""
    cached_data = {"name": "LayerZero", "symbol": "ZRO", "current_price_usd": 3.5}

    with patch("src.services.coingecko.cache_get", return_value=cached_data) as mock_cache, \
         patch("httpx.AsyncClient") as MockClient:

        result = await client._get("/coins/layerzero", {})
        assert result == cached_data
        MockClient.assert_not_called()


@pytest.mark.asyncio
async def test_rate_limit_retries(client):
    """429 responses should trigger retry with backoff."""
    with patch("src.services.coingecko.cache_get", return_value=None), \
         patch("src.services.coingecko.cache_set", new_callable=AsyncMock), \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("httpx.AsyncClient") as MockClient:

        rate_limited = _mock_httpx_response({}, status=429)
        rate_limited.raise_for_status = MagicMock()  # Don't raise on 429
        ok_resp = _mock_httpx_response(SEARCH_RESPONSE)

        MockClient.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=[rate_limited, ok_resp]
        )

        result = await client._get("/search", {"query": "test"})
        assert result == SEARCH_RESPONSE
        mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_get_coin_by_name_full_flow(client):
    """End-to-end: search → get_market_data."""
    with patch.object(client, "search_coin_id", return_value="layerzero"), \
         patch.object(client, "get_market_data", return_value={"name": "LayerZero"}) as mock_gmd:

        result = await client.get_coin_by_name("layerzero")
        assert result["name"] == "LayerZero"
        mock_gmd.assert_called_once_with("layerzero")
