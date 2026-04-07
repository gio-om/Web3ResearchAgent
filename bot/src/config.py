from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    WEBAPP_URL: str = "https://your-domain.com"

    # LLM
    ANTHROPIC_API_KEY: str
    ANTHROPIC_BASE_URL: str = ""
    ANTHROPIC_PROXY_URL: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # External APIs
    CRYPTORANK_API_KEY: str = ""
    CRYPTORANK_COOKIE: str = ""
    CRYPTORANK_BEARER: str = ""   # Bearer token from DevTools → Network → Authorization header
    TWITTER_BEARER_TOKEN: str = ""

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


settings = Settings()
