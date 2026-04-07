"""
Tests for callback handlers in src/bot/handlers/analyze.py.

Uses plain AsyncMock objects for CallbackQuery — no aiogram MockedBot required.
This is consistent with the rest of the test suite (unittest.mock style).
"""
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.handlers.analyze import cb_portfolio_add, cb_reanalyze


def _make_callback(data: str, user_id: int = 111) -> MagicMock:
    """Build a minimal CallbackQuery-like mock."""
    callback = MagicMock()
    callback.data = data
    callback.answer = AsyncMock()
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = AsyncMock()
    return callback


def _make_session_ctx(report_repo, portfolio_repo):
    """Async context manager that injects repo mocks into the handler."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield mock_session

    return _ctx, mock_session


@pytest.mark.asyncio
async def test_portfolio_add_duplicate():
    """If project is already in portfolio, callback.answer is called with show_alert=False."""
    report_id = 7
    callback = _make_callback(f"portfolio_add:{report_id}")

    mock_db_report = MagicMock()
    mock_db_report.project_id = 42

    mock_report_repo = AsyncMock()
    mock_report_repo.get_by_id.return_value = mock_db_report

    mock_portfolio_repo = AsyncMock()
    mock_portfolio_repo.is_in_portfolio.return_value = True  # duplicate

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    with patch("src.bot.handlers.analyze.async_session_factory", mock_session_factory), \
         patch("src.bot.handlers.analyze.ReportRepository", return_value=mock_report_repo), \
         patch("src.bot.handlers.analyze.PortfolioRepository", return_value=mock_portfolio_repo):
        await cb_portfolio_add(callback)

    callback.answer.assert_called_once_with("Проект уже в портфеле", show_alert=False)


@pytest.mark.asyncio
async def test_portfolio_add_not_found():
    """If report_id does not exist, callback.answer is called with show_alert=True."""
    report_id = 999
    callback = _make_callback(f"portfolio_add:{report_id}")

    mock_report_repo = AsyncMock()
    mock_report_repo.get_by_id.return_value = None  # not found

    mock_portfolio_repo = AsyncMock()

    mock_session = AsyncMock()

    @asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    with patch("src.bot.handlers.analyze.async_session_factory", mock_session_factory), \
         patch("src.bot.handlers.analyze.ReportRepository", return_value=mock_report_repo), \
         patch("src.bot.handlers.analyze.PortfolioRepository", return_value=mock_portfolio_repo):
        await cb_portfolio_add(callback)

    callback.answer.assert_called_once_with("❌ Отчёт не найден", show_alert=True)
    mock_portfolio_repo.add.assert_not_called()


@pytest.mark.asyncio
async def test_reanalyze_calls_run_analysis():
    """reanalyze:<name> callback must call _run_analysis(message, project_name)."""
    project_name = "LayerZero"
    callback = _make_callback(f"reanalyze:{project_name}")

    mock_run = AsyncMock()

    with patch("src.bot.handlers.analyze._run_analysis", mock_run):
        await cb_reanalyze(callback)

    callback.answer.assert_called_once()
    mock_run.assert_called_once_with(callback.message, project_name)
