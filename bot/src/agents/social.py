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

    try:
        from src.services.twitter import TwitterClient
        from src.services.llm import LLMService

        twitter = TwitterClient()
        llm = LLMService()

        # Determine Twitter handle
        twitter_handle = None
        twitter_url = project_urls.get("twitter", "")
        if twitter_url:
            # Extract handle from URL like https://twitter.com/LayerZero_Labs
            parts = twitter_url.rstrip("/").split("/")
            if parts:
                twitter_handle = parts[-1].lstrip("@")

        if not twitter_handle:
            twitter_handle = await twitter.find_project_account(project_name)

        if twitter_handle:
            profile = await twitter.get_profile(twitter_handle)
            tweets = await twitter.get_recent_tweets(twitter_handle, count=50)
            mentions = await twitter.search_mentions(project_name, count=30)

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
            }
        else:
            log.info("social.no_twitter_account", project=project_name)
            social_data["error"] = "Twitter account not found"

    except Exception as e:
        log.warning("social.failed", error=str(e))
        errors.append(f"Social: {e}")

    log.info("social.done", project=project_name, has_data=bool(social_data))

    return {
        **state,
        "social_data": social_data,
        "social_done": True,
        "errors": errors,
    }
