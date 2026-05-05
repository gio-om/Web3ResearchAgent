from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.bot.i18n import t
from src.config import settings


def _webapp_url(path_and_params: str) -> str:
    base = settings.WEBAPP_URL.rstrip("/")
    url = f"{base}/{path_and_params.lstrip('/')}"
    if "ngrok" in base:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}ngrok-skip-browser-warning=true"
    return url


def language_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard shown on /start or from settings."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru:start")
    builder.button(text="🇬🇧 English", callback_data="lang:en:start")
    builder.adjust(2)
    return builder.as_markup()


def language_settings_keyboard() -> InlineKeyboardMarkup:
    """Language selection keyboard opened from settings."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🇷🇺 Русский", callback_data="lang:ru:settings")
    builder.button(text="🇬🇧 English", callback_data="lang:en:settings")
    builder.button(text=t("btn_back", "ru"), callback_data="settings")
    builder.adjust(2, 1)
    return builder.as_markup()


def main_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_analyze", lang), callback_data="analyze_start")
    builder.button(text=t("btn_portfolio", lang), callback_data="portfolio")
    builder.button(text=t("btn_settings", lang), callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()


def settings_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_language", lang), callback_data="settings_lang")
    builder.button(text=t("btn_social_settings", lang), callback_data="settings_social")
    builder.button(text=t("btn_docs_settings", lang), callback_data="settings_docs")
    builder.button(text=t("btn_back", lang), callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def docs_settings_keyboard(
    lang: str = "ru",
    max_pages: int = 30,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    _presets = (10, 30, 50)

    for n in _presets:
        mark = "✓ " if n == max_pages else ""
        label = f"{mark}{n} стр." if lang == "ru" else f"{mark}{n} pages"
        builder.button(text=label, callback_data=f"docs_pages:{n}")

    custom_label = f"✓ ✏️ {max_pages}" if max_pages not in _presets else ("✏️ Своё" if lang == "ru" else "✏️ Custom")
    builder.button(text=custom_label, callback_data="docs_pages:custom")

    builder.button(text=t("btn_back", lang), callback_data="settings")
    builder.adjust(4, 1)
    return builder.as_markup()


def social_settings_keyboard(
    lang: str = "ru",
    tweets_count: int = 15,
    mentions_count: int = 15,
    top_posts: int = 3,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    _presets = (10, 20, 50)

    # Row 1: official tweets
    for n in _presets:
        mark = "✓ " if n == tweets_count else ""
        builder.button(text=f"{mark}{n} твитов" if lang == "ru" else f"{mark}{n} tweets",
                       callback_data=f"social_tweets:{n}")
    custom_tweet_label = f"✓ ✏️ {tweets_count}" if tweets_count not in _presets else ("✏️ Своё" if lang == "ru" else "✏️ Custom")
    builder.button(text=custom_tweet_label, callback_data="social_tweets:custom")

    # Row 2: mentions
    for n in _presets:
        mark = "✓ " if n == mentions_count else ""
        builder.button(text=f"{mark}{n} упом." if lang == "ru" else f"{mark}{n} ment.",
                       callback_data=f"social_mentions:{n}")
    custom_mentions_label = f"✓ ✏️ {mentions_count}" if mentions_count not in _presets else ("✏️ Своё" if lang == "ru" else "✏️ Custom")
    builder.button(text=custom_mentions_label, callback_data="social_mentions:custom")

    # Row 3: top posts
    _top_presets = (1, 3, 5)
    for n in _top_presets:
        mark = "✓ " if n == top_posts else ""
        builder.button(text=f"{mark}топ-{n}" if lang == "ru" else f"{mark}top-{n}",
                       callback_data=f"social_top:{n}")
    custom_top_label = f"✓ ✏️ {top_posts}" if top_posts not in _top_presets else ("✏️ Своё" if lang == "ru" else "✏️ Custom")
    builder.button(text=custom_top_label, callback_data="social_top:custom")

    builder.button(text=t("btn_back", lang), callback_data="settings")
    builder.adjust(4, 4, 4, 1)
    return builder.as_markup()


def docs_link_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_docs_link_yes", lang), callback_data="docs_link:yes")
    builder.button(text=t("btn_docs_link_no", lang), callback_data="docs_link:no")
    builder.adjust(2)
    return builder.as_markup()


def analysis_type_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_full_analysis", lang), callback_data="atype:full")
    builder.button(text=t("btn_market_data", lang), callback_data="atype:market")
    builder.button(text=t("btn_docs", lang), callback_data="atype:docs")
    builder.button(text=t("btn_documentation", lang), callback_data="atype:documentation")
    builder.button(text=t("btn_social", lang), callback_data="atype:social")
    builder.button(text=t("btn_team", lang), callback_data="atype:team")
    builder.button(text=t("btn_cancel", lang), callback_data="atype:cancel")
    builder.adjust(1)
    return builder.as_markup()


def report_keyboard(project_name: str, report_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    webapp_url = _webapp_url(f"?report_id={report_id}&lang={lang}")
    builder.button(
        text=t("btn_detailed_report", lang),
        web_app=WebAppInfo(url=webapp_url),
    )
    builder.button(
        text=t("btn_add_portfolio", lang),
        callback_data=f"portfolio_add:{report_id}",
    )
    builder.button(
        text=t("btn_reanalyze", lang),
        callback_data=f"reanalyze:{project_name}",
    )
    builder.adjust(1)
    return builder.as_markup()


def portfolio_item_keyboard(project_id: int, lang: str = "ru") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t("btn_report", lang), callback_data=f"view_report:{project_id}")
    builder.button(text=t("btn_remove", lang), callback_data=f"portfolio_remove:{project_id}")
    builder.adjust(2)
    return builder.as_markup()
