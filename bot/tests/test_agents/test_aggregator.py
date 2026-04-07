import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.aggregator import aggregator_node


@pytest.mark.asyncio
async def test_backfill_website_from_coingecko(sample_agent_state):
    """If project_urls.website is None, aggregator fills it from CoinGecko data."""
    state = {
        **sample_agent_state,
        "project_urls": {},  # no website set
    }

    mock_cg = AsyncMock()
    mock_cg.get_coin_by_name.return_value = {
        "id": "layerzero",
        "name": "LayerZero",
        "symbol": "ZRO",
        "fdv_usd": 3_500_000_000,
        "market_cap_usd": 300_000_000,
        "current_price_usd": 3.5,
        "website": "https://layerzero.network",
        "twitter_handle": "LayerZero_Labs",
    }

    mock_cr = AsyncMock()
    mock_cr.search_project.return_value = None  # CryptoRank finds nothing

    with patch("src.agents.aggregator.CoinGeckoClient", return_value=mock_cg), \
         patch("src.agents.aggregator.CryptoRankClient", return_value=mock_cr):
        result = await aggregator_node(state)

    assert result["project_urls"]["website"] == "https://layerzero.network"
    assert result["project_urls"]["twitter"] == "https://twitter.com/LayerZero_Labs"


@pytest.mark.asyncio
async def test_coingecko_error_returns_empty(sample_agent_state):
    """If CoinGeckoClient raises, aggregator_data has no 'coingecko' key and errors is non-empty."""
    mock_cg = AsyncMock()
    mock_cg.get_coin_by_name.side_effect = Exception("CoinGecko timeout")

    mock_cr = AsyncMock()
    mock_cr.search_project.return_value = None

    with patch("src.agents.aggregator.CoinGeckoClient", return_value=mock_cg), \
         patch("src.agents.aggregator.CryptoRankClient", return_value=mock_cr):
        result = await aggregator_node(sample_agent_state)

    assert "coingecko" not in result["aggregator_data"]
    assert any("CoinGecko" in e for e in result["errors"])


@pytest.mark.asyncio
async def test_coingecko_flat_structure(sample_agent_state, sample_aggregator_data):
    """fdv_usd and market_cap_usd must be at the top level of aggregator_data['coingecko']."""
    coingecko_payload = sample_aggregator_data["coingecko"]

    mock_cg = AsyncMock()
    mock_cg.get_coin_by_name.return_value = coingecko_payload

    mock_cr = AsyncMock()
    mock_cr.search_project.return_value = None

    with patch("src.agents.aggregator.CoinGeckoClient", return_value=mock_cg), \
         patch("src.agents.aggregator.CryptoRankClient", return_value=mock_cr):
        result = await aggregator_node(sample_agent_state)

    cg = result["aggregator_data"]["coingecko"]
    assert isinstance(cg.get("fdv_usd"), (int, float))
    assert isinstance(cg.get("market_cap_usd"), (int, float))
    # Confirm values are NOT nested under a sub-key
    assert "market_data" not in cg
