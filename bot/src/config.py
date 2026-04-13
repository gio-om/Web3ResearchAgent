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
