"""
Entry point for Web3 Due Diligence Bot.
Starts the Telegram bot and FastAPI server concurrently.
"""
import asyncio
import logging

import structlog
import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI

from src.config import settings
from src.db.engine import engine
from src.db.models import Base

log = structlog.get_logger()


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%H:%M:%S"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),   # human-readable in dev
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=logging.INFO)


def create_api_app() -> FastAPI:
    """Create FastAPI app for Mini App endpoints."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Web3 DD Bot API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/report/{report_id}")
    async def get_report(report_id: int) -> dict:
        from fastapi import HTTPException
        from src.db.engine import async_session_factory
        from src.db.repositories import ReportRepository
        async with async_session_factory() as session:
            report = await ReportRepository(session).get_by_id(report_id)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return report.report_data or {}

    @app.get("/api/portfolio/{user_id}")
    async def get_portfolio(user_id: int) -> list:
        from src.db.engine import async_session_factory
        from src.db.repositories import PortfolioRepository
        async with async_session_factory() as session:
            entries = await PortfolioRepository(session).list_by_user(user_id)
        return [
            {
                "project_id": e.project_id,
                "project_name": e.project.name if e.project else str(e.project_id),
                "added_at": e.added_at.isoformat(),
            }
            for e in entries
        ]

    @app.post("/api/compare")
    async def compare(body: dict) -> dict:
        from fastapi import HTTPException
        from src.agents.graph import build_analysis_graph
        project_a = body.get("project_a", "")
        project_b = body.get("project_b", "")
        if not project_a or not project_b:
            raise HTTPException(status_code=400, detail="project_a and project_b required")
        graph = build_analysis_graph()
        a, b = await asyncio.gather(
            graph.ainvoke({"project_query": project_a, "user_id": 0}),
            graph.ainvoke({"project_query": project_b, "user_id": 0}),
        )
        return {"project_a": a.get("report"), "project_b": b.get("report")}

    return app


async def create_bot() -> tuple[Bot, Dispatcher]:
    """Create and configure the Telegram bot."""
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Import and register handlers
    from src.bot.handlers.start import router as start_router
    from src.bot.handlers.analyze import router as analyze_router
    from src.bot.handlers.portfolio import router as portfolio_router

    # Register middlewares
    from src.bot.middlewares import RateLimitMiddleware, LoggingMiddleware, UserRegistrationMiddleware, LanguageMiddleware
    dp.message.middleware(LoggingMiddleware())
    dp.message.middleware(RateLimitMiddleware())
    dp.message.middleware(UserRegistrationMiddleware())
    dp.message.middleware(LanguageMiddleware())
    dp.callback_query.middleware(LanguageMiddleware())

    dp.include_router(start_router)
    dp.include_router(analyze_router)
    dp.include_router(portfolio_router)

    # Give the agent graph a reference to the bot for live progress updates
    from src.agents.graph import set_bot as graph_set_bot
    graph_set_bot(bot)

    return bot, dp


async def run_bot(bot: Bot, dp: Dispatcher) -> None:
    log.info("bot.starting")
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        except Exception as e:
            log.error("bot.crashed", error=str(e))
            await asyncio.sleep(5)
            log.info("bot.restarting")
        else:
            break
    await bot.session.close()
    from src.services.cache import close_redis
    await close_redis()


async def run_api(app: FastAPI) -> None:
    config = uvicorn.Config(
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    configure_logging()
    log.info("startup", webapp_url=settings.WEBAPP_URL)

    bot, dp = await create_bot()
    api_app = create_api_app()

    await asyncio.gather(
        run_bot(bot, dp),
        run_api(api_app),
        return_exceptions=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
