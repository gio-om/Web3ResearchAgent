from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    WEBAPP_URL: str = "https://your-domain.com"

    # OmniRoute — единственный LLM шлюз
    OMNIROUTE_API_KEY: str
    OMNIROUTE_BASE_URL: str = "http://omniroute:20128/v1"
    OMNIROUTE_MODEL: str = "glm/glm-5.1"

    # External APIs
    CRYPTORANK_API_KEY: str = ""
    CRYPTORANK_COOKIE: str = ""
    CRYPTORANK_BEARER: str = ""

    # Brave Search API
    BRAVE_API_KEY: str = ""

    # Apify — LinkedIn scraping
    APIFY_TOKEN: str = ""
    APIFY_ACTOR_ID: str = "M2FMdjRVeF1HPGFcc"

    # Team search mode: "brave" | "apify"
    TEAM_SEARCH_MODE: str = "brave"
    # Twitter/X — cookie captured from browser DevTools:
    #   Open x.com → DevTools → Network → any request → Headers → Cookie → copy full string
    TWITTER_AUTH_COOKIE: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://web3dd:web3dd_secret@postgres:5432/web3dd"
    REDIS_URL: str = "redis://redis:6379/0"

    # Scraping
    REQUEST_TIMEOUT: int = 30
    MAX_CONCURRENT_REQUESTS: int = 10

    # API server for Mini App
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8080

    # Rate limiting
    RATE_LIMIT_ANALYSES_PER_HOUR: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
