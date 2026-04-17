"""
Aggregator agent: fetches quantitative data from Cryptorank and CoinGecko.
"""
import structlog

def _clean_url(url: str) -> str:
    """Strip tracking query params and trailing slashes."""
    return url.split("?")[0].split("#")[0].rstrip("/")

log = structlog.get_logger()


async def aggregator_node(state: dict) -> dict:
    """
    Collects market data, funding rounds, and investor info from aggregators.
    Writes results to state['aggregator_data'].
    """
    project_name = state.get("project_name", "")
    project_slug = state.get("project_slug", "")
    log.info("aggregator.start", project=project_name)

    from src.agents.graph import push_step

    aggregator_data: dict = {}
    errors = list(state.get("errors", []))

    if state.get("skip_cryptorank"):
        log.info("aggregator.cryptorank_skipped", project=project_name)
    else:
        try:
            from src.services.cryptorank import CryptoRankClient
            client = CryptoRankClient()

            await push_step("aggregator", "Ищем проект в CryptoRank...")
            project = await client.search_project(project_name)
            if project:
                project_id = project.get("id") or project.get("slug")
                if project_id:
                    await push_step("aggregator", "Загружаем данные: раунды финансирования, вестинг...")
                    details = await client.get_project_details(str(project_id))
                    funding = await client.get_funding_rounds(str(project_id))
                    vesting = await client.get_token_vesting(str(project_id))
                    aggregator_data["cryptorank"] = {
                        "project": details,
                        "funding_rounds": funding,
                        "vesting": vesting,
                    }
                    # Back-fill project URLs from CryptoRank (all link types, highest priority)
                    state_urls = dict(state.get("project_urls", {}))
                    _non_link_keys = {"key", "name", "symbol", "category", "total_supply",
                                       "max_supply", "available_supply", "fully_diluted_market_cap",
                                       "market_cap", "rank", "has_funding_rounds", "has_vesting",
                                       "listing_date", "description"}
                    for key, val in details.items():
                        if key not in _non_link_keys and val and not state_urls.get(key):
                            state_urls[key] = _clean_url(str(val))
                    # Always set the resolved CryptoRank URL and slug (e.g. "opinion-labs" not "opinion")
                    state_urls["cryptorank"] = f"https://cryptorank.io/price/{project_id}"
                    state = {**state, "project_urls": state_urls, "project_slug": project_id}
        except Exception as e:
            log.warning("aggregator.cryptorank_failed", error=str(e))
            errors.append(f"CryptoRank: {e}")

    try:
        from src.services.coingecko import CoinGeckoClient, CoinGeckoError
        await push_step("aggregator", "Запрашиваем цены и капитализацию в CoinGecko...")
        cg = CoinGeckoClient()
        coin_data = await cg.get_coin_by_name(project_name)
        if coin_data:
            aggregator_data["coingecko"] = coin_data
            # Back-fill project URLs from CoinGecko only for keys missing after CryptoRank
            state_urls = dict(state.get("project_urls", {}))
            if coin_data.get("website") and not state_urls.get("website"):
                state_urls["website"] = _clean_url(coin_data["website"])
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
