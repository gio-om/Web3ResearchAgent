import pytest


@pytest.fixture
def sample_aggregator_data():
    """Realistic aggregator_data structure matching CoinGeckoClient.get_market_data() output."""
    return {
        "cryptorank": {
            "project": {"name": "LayerZero", "slug": "layerzero"},
            "funding_rounds": [
                {
                    "round_type": "Seed",
                    "date": "2022-03-15",
                    "amount_usd": 6_000_000,
                    "valuation_usd": 1_000_000_000,
                    "token_price": 0.001,
                    "investors": ["a16z", "Sequoia"],
                }
            ],
            "vesting": [
                {
                    "category": "Team",
                    "allocation_pct": 15,
                    "cliff_months": 12,
                    "vesting_months": 36,
                    "tge_unlock_pct": 0,
                }
            ],
        },
        # Flat structure as returned by CoinGeckoClient.get_market_data()
        "coingecko": {
            "id": "layerzero",
            "name": "LayerZero",
            "symbol": "ZRO",
            "current_price_usd": 3.5,
            "market_cap_usd": 300_000_000,
            "fdv_usd": 3_500_000_000,
            "ath_usd": 10.0,
            "circulating_supply": 85_714_285,
            "total_supply": 1_000_000_000,
            "categories": ["Cross-chain", "Interoperability"],
            "website": "https://layerzero.network",
            "twitter_handle": "LayerZero_Labs",
        },
    }


@pytest.fixture
def sample_agent_state():
    return {
        "project_query": "LayerZero",
        "project_name": "LayerZero",
        "project_slug": "layerzero",
        "project_urls": {"website": "https://layerzero.network"},
        "aggregator_data": {},
        "documentation_data": {},
        "social_data": {},
        "team_data": {"members": [], "flags": []},
        "cross_check_results": [],
        "report": None,
        "errors": [],
        "status": "pending",
        "user_id": 123456,
        "chat_id": 123456,
        "message_id": None,
        "started_at": "",
        "completed_at": "",
        "aggregator_done": False,
        "documentation_done": False,
        "social_done": False,
        "team_done": False,
    }
