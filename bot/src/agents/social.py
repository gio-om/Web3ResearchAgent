"""
Social agent: analyzes Twitter/X presence and sentiment.
"""
import structlog

log = structlog.get_logger()

SENTIMENT_PROMPT = """Analyze the sentiment and social presence of this crypto project based on the tweets below.
Return ONLY valid JSON, no markdown fences.

Return:
{{
  "sentiment_score": number from -1.0 (very negative) to 1.0 (very positive),
  "key_concerns": ["list of main concerns mentioned"],
  "positive_signals": ["list of positive signals"],
  "notable_supporters": ["list of KOL/influencer names who mentioned the project"],
  "bot_activity_signals": ["any signs of fake engagement"],
  "overall_assessment": "brief 1-sentence assessment"
}}

Project: {project_name}
Tweets:
{tweets_text}
"""


async def social_node(state: dict) -> dict:
    """
    Analyzes project's Twitter presence, sentiment, and audience quality.
    Writes results to state['social_data'].
    """
    project_name = state.get("project_name", "")
    project_urls = state.get("project_urls", {})
    log.info("social.start", project=project_name)

    social_data: dict = {}
    errors = list(state.get("errors", []))

    # Resolve social URLs (CryptoRank priority → CoinGecko fallback)
    from src.agents.resolve_urls import resolve_project_urls
    project_urls = await resolve_project_urls(project_name, project_urls)

    # Fetch FDV / MCap separately for coingecko_summary in the report
    coingecko_summary: dict = {}
    try:
        from src.services.coingecko import CoinGeckoClient
        cg = CoinGeckoClient()
        coin_data = await cg.get_coin_by_name(project_name)
        if coin_data:
            coingecko_summary = {
                "fdv_usd": coin_data.get("fdv_usd"),
                "market_cap_usd": coin_data.get("market_cap_usd"),
            }
    except Exception as e:
        log.warning("social.coingecko_failed", error=str(e))

    try:
        from src.services.twitter import TwitterClient
        from src.services.llm import LLMService

        twitter = TwitterClient()
        llm = LLMService()

        # Determine Twitter handle
        twitter_handle = None
        twitter_url = project_urls.get("twitter", "")
        if twitter_url:
            # Strip tracking params (e.g. ?hzet=... added by CryptoRank) before parsing
            clean_url = twitter_url.split("?")[0].split("#")[0].rstrip("/")
            parts = clean_url.split("/")
            candidate = parts[-1].lstrip("@") if parts else ""
            # Ignore bare domain segments
            if candidate and candidate.lower() not in ("twitter.com", "x.com", ""):
                twitter_handle = candidate
            # Normalise the stored URL to the clean version
            project_urls["twitter"] = f"https://twitter.com/{twitter_handle}" if twitter_handle else clean_url

        if not twitter_handle:
            twitter_handle = await twitter.find_project_account(project_name)

        # Back-fill project_urls so the URL appears in project_links in the report
        if twitter_handle and not project_urls.get("twitter"):
            project_urls["twitter"] = f"https://twitter.com/{twitter_handle}"

        if twitter_handle:
            profile = await twitter.get_profile(twitter_handle)
            tweets = await twitter.get_recent_tweets(twitter_handle, count=20)
            mentions = await twitter.search_mentions(project_name, count=15)

            # Combine tweets for sentiment analysis
            all_tweets = [t.get("text", "") for t in (tweets + mentions)[:50]]
            tweets_text = "\n---\n".join(all_tweets[:30])

            sentiment_result = await llm.analyze_sentiment(
                tweets=all_tweets,
                project_name=project_name,
            )

            followers = profile.get("public_metrics", {}).get("followers_count", 0)
            following = profile.get("public_metrics", {}).get("following_count", 1)

            # Calculate engagement rate
            total_engagement = sum(
                t.get("public_metrics", {}).get("like_count", 0)
                + t.get("public_metrics", {}).get("retweet_count", 0)
                for t in tweets
            )
            engagement_rate = (total_engagement / len(tweets) / max(followers, 1)) if tweets else 0.0

            social_data = {
                "handle": twitter_handle,
                "followers_count": followers,
                "following_count": following,
                "engagement_rate": round(engagement_rate, 4),
                "tweet_count": len(tweets),
                "sentiment_score": sentiment_result.get("sentiment_score", 0.0),
                "key_concerns": sentiment_result.get("key_concerns", []),
                "positive_signals": sentiment_result.get("positive_signals", []),
                "kol_mentions": sentiment_result.get("notable_supporters", []),
                "bot_activity_signals": sentiment_result.get("bot_activity_signals", []),
                "overall_assessment": sentiment_result.get("overall_assessment", ""),
                "coingecko_summary": coingecko_summary,
            }
        else:
            log.info("social.no_twitter_account", project=project_name)
            social_data = {"error": "Twitter account not found", "coingecko_summary": coingecko_summary}

    except Exception as e:
        log.warning("social.failed", error=str(e))
        errors.append(f"Social: {e}")

    log.info("social.done", project=project_name, has_data=bool(social_data))

    return {
        **state,
        "social_data": social_data,
        "social_done": True,
        "project_urls": project_urls,
        "errors": errors,
    }
