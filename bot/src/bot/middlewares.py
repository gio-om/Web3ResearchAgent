import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from src.config import settings

log = structlog.get_logger()


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        start = time.monotonic()
        user_id = event.from_user.id if event.from_user else None
        text = event.text or ""
        log.info("message.received", user_id=user_id, text=text[:100])
        result = await handler(event, data)
        elapsed = time.monotonic() - start
        log.info("message.handled", user_id=user_id, elapsed_ms=round(elapsed * 1000))
        return result


class RateLimitMiddleware(BaseMiddleware):
    """Rate limiting (currently disabled)."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        return await handler(event, data)


class UserRegistrationMiddleware(BaseMiddleware):
    """Register user in DB on first message."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if event.from_user:
            try:
                from src.db.engine import async_session_factory
                from src.db.repositories import UserRepository
                async with async_session_factory() as session:
                    repo = UserRepository(session)
                    await repo.get_or_create(
                        telegram_id=event.from_user.id,
                        username=event.from_user.username,
                        first_name=event.from_user.first_name,
                    )
                    await session.commit()
            except Exception as e:
                log.warning("user_registration.error", error=str(e))
        return await handler(event, data)


class LanguageMiddleware(BaseMiddleware):
    """Inject user language from DB settings into handler data."""

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        from_user = None
        if isinstance(event, Message):
            from_user = event.from_user
        elif isinstance(event, CallbackQuery):
            from_user = event.from_user

        lang = "ru"
        if from_user:
            try:
                from src.db.engine import async_session_factory
                from src.db.repositories import UserRepository
                async with async_session_factory() as session:
                    user = await UserRepository(session).get_by_id(from_user.id)
                    if user and user.settings:
                        lang = user.settings.get("lang", "ru")
            except Exception as e:
                log.warning("language_middleware.error", error=str(e))

        data["lang"] = lang
        return await handler(event, data)
