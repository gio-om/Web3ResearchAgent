"""
Aggregator agent: fetches quantitative data from Cryptorank and CoinGecko.
"""
import structlog

log = structlog.get_logger()


async def aggregator_node(state: dict) -> dict:
    """
    Collects market data, funding rounds, and investor info from aggregators.
    Writes results to state['aggregator_data'].
    """
    project_name = state.get("project_name", "")
    project_slug = state.get("project_slug", "")
    log.info("aggregator.start", project=project_name)

    aggregator_data: dict = {}
    errors = list(state.get("errors", []))

    try:
        from src.services.cryptorank import CryptoRankClient
        client = CryptoRankClient()

        project = await client.search_project(project_name)
        if project:
            project_id = project.get("id") or project.get("slug")
            if project_id:
                details = await client.get_project_details(str(project_id))
                funding = await client.get_funding_rounds(str(project_id))
                vesting = await client.get_token_vesting(str(project_id))
                aggregator_data["cryptorank"] = {
                    "project": details,
                    "funding_rounds": funding,
                    "vesting": vesting,
                }
    except Exception as e:
        log.warning("aggregator.cryptorank_failed", error=str(e))
        errors.append(f"CryptoRank: {e}")

    try:
        from src.services.coingecko import CoinGeckoClient, CoinGeckoError
        cg = CoinGeckoClient()
        coin_data = await cg.get_coin_by_name(project_name)
        if coin_data:
            aggregator_data["coingecko"] = coin_data
            # Back-fill project URLs from CoinGecko if not already set
            state_urls = dict(state.get("project_urls", {}))
            if coin_data.get("website") and not state_urls.get("website"):
                state_urls["website"] = coin_data["website"]
            if coin_data.get("twitter_handle") and not state_urls.get("twitter"):
                state_urls["twitter"] = f"https://twitter.com/{coin_data['twitter_handle']}"
            state = {**state, "project_urls": state_urls}
    except Exception as e:
        log.warning("aggregator.coingecko_failed", error=str(e))
        errors.append(f"CoinGecko: {e}")

    log.info("aggregator.done", project=project_name, has_data=bool(aggregator_data))

    return {
        **state,
        "aggregator_data": aggregator_data,
        "aggregator_done": True,
        "errors": errors,
    }
