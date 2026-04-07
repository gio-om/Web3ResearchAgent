from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Общее состояние, разделяемое между всеми агентами в графе."""

    # Входные данные
    project_query: str                         # Что ввёл пользователь
    user_id: int = 0                           # Telegram user ID
    chat_id: int = 0                           # Telegram chat ID
    message_id: int | None = None              # ID сообщения для обновления статуса

    # Нормализованные данные о проекте
    project_name: str = ""
    project_slug: str = ""
    project_urls: dict = Field(default_factory=dict)
    # Ожидаемая структура: {"website": ..., "twitter": ..., "docs": ..., "github": ...}

    # Результаты агентов (заполняются по мере работы)
    aggregator_data: dict = Field(default_factory=dict)
    documentation_data: dict = Field(default_factory=dict)
    social_data: dict = Field(default_factory=dict)
    team_data: dict = Field(default_factory=dict)

    # Флаги завершения параллельных агентов
    aggregator_done: bool = False
    documentation_done: bool = False
    social_done: bool = False
    team_done: bool = False

    # Результаты верификации
    cross_check_results: list = Field(default_factory=list)

    # Финальный отчёт
    report: dict | None = None

    # Какие модули запускать в dispatcher (по умолчанию все)
    enabled_modules: list[str] = Field(
        default_factory=lambda: ["aggregator", "documentation", "social", "team"]
    )

    # Метаданные пайплайна
    errors: list[str] = Field(default_factory=list)
    status: str = "pending"            # pending | running | completed | failed
    started_at: str = ""
    completed_at: str = ""
