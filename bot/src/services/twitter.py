"""
Twitter / X API v2 client — STUB.

The API requires a Bearer Token (free tier has very limited access;
paid Basic/Pro tiers provide search/timeline endpoints).

This stub returns empty data so the pipeline degrades gracefully.

TODO: implement when TWITTER_BEARER_TOKEN is available.
Endpoints to implement (all under https://api.twitter.com/2):
  GET /users/by/username/{username}
      params: user.fields=public_metrics,description,created_at
      -> get_profile()

  GET /users/{id}/tweets
      params: max_results, tweet.fields=public_metrics,created_at,text,
              exclude=retweets,replies
      -> get_recent_tweets()

  GET /tweets/search/recent
      params: query, max_results, tweet.fields=..., expansions=author_id
      -> search_mentions()  and  find_project_account()

All methods should:
  - Use Authorization: Bearer {TWITTER_BEARER_TOKEN} header
  - Cache responses in Redis via cache_get/cache_set (TTL 1800 s = 30 min)
  - Retry on 429 with a longer backoff (Twitter rate windows are 15-min)
  - Return empty dict/list (never raise) so callers can always proceed
"""
import structlog

from src.config import settings

log = structlog.get_logger()


class TwitterClient:
    """
    Stub client. All methods log a warning and return empty data.
    Replace method bodies one by one as API access is configured.
    """

    def __init__(self) -> None:
        self._bearer_token = settings.TWITTER_BEARER_TOKEN
        if not self._bearer_token:
            log.warning("twitter.no_bearer_token", hint="Set TWITTER_BEARER_TOKEN in .env")

    @property
    def is_configured(self) -> bool:
        return bool(self._bearer_token)

    # ------------------------------------------------------------------
    # Stubs
    # ------------------------------------------------------------------

    async def find_project_account(self, project_name: str) -> str | None:
        """
        Search for the project's official Twitter/X handle.

        Expected return: username string (without @), e.g. "LayerZero_Labs"
        or None if not found.

        Implementation hint:
          Search recent tweets from likely handles, pick the one with the
          highest follower count and matching description.
        """
        log.info("twitter.stub.find_project_account", project_name=project_name)
        return None  # TODO: implement

    async def get_profile(self, username: str) -> dict:
        """
        Fetch public profile data for a Twitter username.

        Expected return shape:
        {
          "id": "123456789",
          "name": "LayerZero",
          "username": "LayerZero_Labs",
          "description": "...",
          "created_at": "2021-06-01T00:00:00.000Z",
          "public_metrics": {
            "followers_count": 250000,
            "following_count": 500,
            "tweet_count": 1200,
            "listed_count": 800
          }
        }
        """
        log.info("twitter.stub.get_profile", username=username)
        return {}  # TODO: implement

    async def get_recent_tweets(self, username: str, count: int = 50) -> list[dict]:
        """
        Get the most recent original tweets (excluding RTs and replies).

        Expected return (list of):
        {
          "id": "...",
          "text": "...",
          "created_at": "...",
          "public_metrics": {
            "like_count": 120,
            "retweet_count": 45,
            "reply_count": 12,
            "impression_count": 8000
          }
        }
        """
        log.info("twitter.stub.get_recent_tweets", username=username, count=count)
        return []  # TODO: implement

    async def search_mentions(self, project_name: str, count: int = 30) -> list[dict]:
        """
        Search for recent tweets mentioning the project (not from the project account).

        Expected return: same shape as get_recent_tweets() with additional
        "author_username" key from expansions.
        """
        log.info("twitter.stub.search_mentions", project_name=project_name, count=count)
        return []  # TODO: implement
