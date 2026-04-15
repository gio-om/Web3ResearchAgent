"""
Shared utility: resolve project_urls from CryptoRank + CoinGecko.

Used by any agent that needs social/website links but runs without the aggregator.
CryptoRank has priority; CoinGecko fills gaps.
"""
import structlog

log = structlog.get_logger()


def _clean(url: str) -> str:
    """Strip tracking query params and trailing slashes from any social URL."""
    return url.split("?")[0].split("#")[0].rstrip("/")


async def resolve_project_urls(project_name: str, project_urls: dict) -> dict:
    """
    Fetch social/website links for *project_name* and merge into *project_urls*.
    Already-set keys are NOT overwritten (caller's data takes priority).
    Returns the merged dict.
    """
    urls = dict(project_urls)

    # ── CryptoRank (highest priority) ────────────────────────────────────────
    try:
        from src.services.cryptorank import CryptoRankClient, _LINK_TYPES
        cr = CryptoRankClient()
        project = await cr.search_project(project_name)
        if project:
            cr_id = project.get("id") or project.get("slug")
            if cr_id:
                details = await cr.get_project_details(cr_id)
                for key in _LINK_TYPES:
                    if details.get(key) and not urls.get(key):
                        urls[key] = _clean(details[key])
    except Exception as e:
        log.warning("resolve_urls.cryptorank_failed", project=project_name, error=str(e))

    # ── CoinGecko (fallback for website + twitter) ────────────────────────────
    try:
        from src.services.coingecko import CoinGeckoClient
        cg = CoinGeckoClient()
        coin = await cg.get_coin_by_name(project_name)
        if coin:
            if coin.get("website") and not urls.get("website"):
                urls["website"] = _clean(coin["website"])
            if coin.get("twitter_handle") and not urls.get("twitter"):
                urls["twitter"] = f"https://twitter.com/{coin['twitter_handle']}"
    except Exception as e:
        log.warning("resolve_urls.coingecko_failed", project=project_name, error=str(e))

    return urls
