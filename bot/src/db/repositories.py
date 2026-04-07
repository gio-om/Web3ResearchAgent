from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import AnalysisReport, ApiCache, Project, User, UserPortfolio

log = structlog.get_logger()


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(self, telegram_id: int, username: str | None = None, first_name: str | None = None) -> User:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, username=username, first_name=first_name)
            self.session.add(user)
            await self.session.flush()
            log.info("user.created", telegram_id=telegram_id)
        return user

    async def get_by_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def update_settings(self, telegram_id: int, settings: dict) -> None:
        await self.session.execute(
            update(User).where(User.telegram_id == telegram_id).values(settings=settings)
        )


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_slug(self, slug: str) -> Project | None:
        result = await self.session.execute(select(Project).where(Project.slug == slug))
        return result.scalar_one_or_none()

    async def get_or_create(self, name: str, slug: str, **kwargs) -> tuple[Project, bool]:
        project = await self.get_by_slug(slug)
        if project is not None:
            return project, False
        project = Project(name=name, slug=slug, **kwargs)
        self.session.add(project)
        await self.session.flush()
        log.info("project.created", slug=slug)
        return project, True

    async def update_urls(self, project_id: int, urls: dict) -> None:
        await self.session.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(
                website_url=urls.get("website"),
                twitter_url=urls.get("twitter"),
                docs_url=urls.get("docs"),
                github_url=urls.get("github"),
            )
        )


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, project_id: int, user_id: int) -> AnalysisReport:
        report = AnalysisReport(project_id=project_id, user_id=user_id, status="running")
        self.session.add(report)
        await self.session.flush()
        return report

    async def get_by_id(self, report_id: int) -> AnalysisReport | None:
        result = await self.session.execute(
            select(AnalysisReport).where(AnalysisReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def complete(self, report_id: int, report_data: dict, overall_score: int, recommendation: str, risk_flags: list, errors: list) -> None:
        await self.session.execute(
            update(AnalysisReport)
            .where(AnalysisReport.id == report_id)
            .values(
                status="completed",
                overall_score=overall_score,
                recommendation=recommendation,
                report_data=report_data,
                risk_flags=risk_flags,
                errors=errors,
            )
        )

    async def fail(self, report_id: int, errors: list) -> None:
        await self.session.execute(
            update(AnalysisReport)
            .where(AnalysisReport.id == report_id)
            .values(status="failed", errors=errors)
        )

    async def list_by_user(self, user_id: int, limit: int = 10) -> list[AnalysisReport]:
        result = await self.session.execute(
            select(AnalysisReport)
            .where(AnalysisReport.user_id == user_id)
            .order_by(AnalysisReport.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_latest_by_project(self, user_id: int, project_id: int) -> AnalysisReport | None:
        result = await self.session.execute(
            select(AnalysisReport)
            .where(
                AnalysisReport.user_id == user_id,
                AnalysisReport.project_id == project_id,
                AnalysisReport.status == "completed",
            )
            .order_by(AnalysisReport.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: int, project_id: int, notes: str | None = None) -> UserPortfolio:
        entry = UserPortfolio(user_id=user_id, project_id=project_id, notes=notes)
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def remove(self, user_id: int, project_id: int) -> None:
        result = await self.session.execute(
            select(UserPortfolio).where(
                UserPortfolio.user_id == user_id,
                UserPortfolio.project_id == project_id,
            )
        )
        entry = result.scalar_one_or_none()
        if entry:
            await self.session.delete(entry)

    async def list_by_user(self, user_id: int) -> list[UserPortfolio]:
        result = await self.session.execute(
            select(UserPortfolio)
            .options(selectinload(UserPortfolio.project))
            .where(UserPortfolio.user_id == user_id)
            .order_by(UserPortfolio.added_at.desc())
        )
        return list(result.scalars().all())

    async def is_in_portfolio(self, user_id: int, project_id: int) -> bool:
        result = await self.session.execute(
            select(UserPortfolio).where(
                UserPortfolio.user_id == user_id,
                UserPortfolio.project_id == project_id,
            )
        )
        return result.scalar_one_or_none() is not None


class CacheRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, cache_key: str) -> dict | list | None:
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ApiCache).where(
                ApiCache.cache_key == cache_key,
                ApiCache.expires_at > now,
            )
        )
        entry = result.scalar_one_or_none()
        return entry.response_data if entry else None

    async def set(self, cache_key: str, data: dict | list, expires_at: datetime) -> None:
        result = await self.session.execute(
            select(ApiCache).where(ApiCache.cache_key == cache_key)
        )
        entry = result.scalar_one_or_none()
        if entry:
            entry.response_data = data
            entry.expires_at = expires_at
        else:
            entry = ApiCache(cache_key=cache_key, response_data=data, expires_at=expires_at)
            self.session.add(entry)
        await self.session.flush()
