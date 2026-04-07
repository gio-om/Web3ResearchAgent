from urllib.parse import urlencode

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from src.config import settings


def _webapp_url(path_and_params: str) -> str:
    """
    Build a WebApp URL. Appends ngrok-skip-browser-warning when using ngrok,
    so the interstitial page is bypassed.
    """
    base = settings.WEBAPP_URL.rstrip("/")
    url = f"{base}/{path_and_params.lstrip('/')}"
    if "ngrok" in base:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}ngrok-skip-browser-warning=true"
    return url


def analysis_type_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for choosing analysis depth after entering a project name."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Полный анализ", callback_data="atype:full")
    builder.button(text="📊 Рыночные данные", callback_data="atype:market")
    builder.button(text="📄 Документация / токеномика", callback_data="atype:docs")
    builder.button(text="📱 Соцсети", callback_data="atype:social")
    builder.button(text="👥 Команда", callback_data="atype:team")
    builder.button(text="❌ Отмена", callback_data="atype:cancel")
    builder.adjust(1)
    return builder.as_markup()


def main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Анализировать проект", callback_data="analyze_start")
    builder.button(text="📁 Мой портфель", callback_data="portfolio")
    builder.adjust(1)
    return builder.as_markup()


def report_keyboard(project_name: str, report_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    webapp_url = _webapp_url(f"?report_id={report_id}")
    builder.button(
        text="📊 Подробный отчёт",
        web_app=WebAppInfo(url=webapp_url),
    )
    builder.button(
        text="➕ В портфель",
        callback_data=f"portfolio_add:{report_id}",
    )
    builder.button(
        text="🔄 Обновить анализ",
        callback_data=f"reanalyze:{project_name}",
    )
    builder.adjust(1)
    return builder.as_markup()


def portfolio_item_keyboard(project_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Отчёт", callback_data=f"view_report:{project_id}")
    builder.button(text="🗑 Удалить", callback_data=f"portfolio_remove:{project_id}")
    builder.adjust(2)
    return builder.as_markup()
