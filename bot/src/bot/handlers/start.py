import structlog
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from src.bot.i18n import t
from src.bot.keyboards import (
    docs_settings_keyboard,
    language_keyboard,
    language_settings_keyboard,
    main_keyboard,
    settings_keyboard,
    social_settings_keyboard,
)

router = Router(name="start")
log = structlog.get_logger()


class SocialSettingsStates(StatesGroup):
    entering_tweets_count = State()
    entering_mentions_count = State()
    entering_top_posts = State()


class DocsSettingsStates(StatesGroup):
    entering_pages_count = State()


async def _load_settings(user_id: int) -> dict:
    from src.db.engine import async_session_factory
    from src.db.repositories import UserRepository
    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        return dict(user.settings or {}) if user else {}


async def _save_setting(user_id: int, key: str, value) -> dict:
    from src.db.engine import async_session_factory
    from src.db.repositories import UserRepository
    async with async_session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_id(user_id)
        if user:
            new_settings = dict(user.settings or {})
            new_settings[key] = value
            await repo.update_settings(user_id, new_settings)
            await session.commit()
            return new_settings
    return {key: value}


async def _save_lang(user_id: int, lang: str) -> None:
    await _save_setting(user_id, "lang", lang)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        t("choose_language"),
        reply_markup=language_keyboard(),
    )


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_language(callback: CallbackQuery) -> None:
    _, code, context = callback.data.split(":", 2)
    user_id = callback.from_user.id

    try:
        await _save_lang(user_id, code)
    except Exception as e:
        log.warning("lang.save_error", error=str(e))

    await callback.answer(t("language_set", code))

    if context == "settings":
        await callback.message.edit_text(
            t("settings_menu", code, lang_label=t("lang_label", code)),
            reply_markup=settings_keyboard(code),
        )
    else:
        await callback.message.edit_text(
            t("welcome", code),
            reply_markup=main_keyboard(code),
        )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, lang: str = "ru") -> None:
    await callback.answer()
    await callback.message.edit_text(
        t("welcome", lang),
        reply_markup=main_keyboard(lang),
    )


@router.callback_query(F.data == "settings")
async def cb_settings(callback: CallbackQuery, lang: str = "ru") -> None:
    await callback.answer()
    await callback.message.edit_text(
        t("settings_menu", lang, lang_label=t("lang_label", lang)),
        reply_markup=settings_keyboard(lang),
    )


@router.callback_query(F.data == "settings_lang")
async def cb_settings_lang(callback: CallbackQuery, lang: str = "ru") -> None:
    await callback.answer()
    await callback.message.edit_text(
        t("choose_language", lang),
        reply_markup=language_settings_keyboard(),
    )


@router.callback_query(F.data == "settings_social")
async def cb_settings_social(callback: CallbackQuery, lang: str = "ru") -> None:
    await callback.answer()
    user_settings = await _load_settings(callback.from_user.id)
    tweets_count = int(user_settings.get("social_tweets_count", 15))
    mentions_count = int(user_settings.get("social_mentions_count", tweets_count))
    top_posts = int(user_settings.get("social_top_posts", 3))
    await callback.message.edit_text(
        t("social_settings_menu", lang, tweets_count=tweets_count, mentions_count=mentions_count, top_posts=top_posts),
        reply_markup=social_settings_keyboard(lang, tweets_count, mentions_count, top_posts),
    )


@router.callback_query(F.data.startswith("social_tweets:"))
async def cb_social_tweets(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "custom":
        await state.set_state(SocialSettingsStates.entering_tweets_count)
        await state.update_data(lang=lang)
        await callback.message.answer(t("enter_tweets_count", lang))
        return

    n = int(value)
    new_settings = await _save_setting(callback.from_user.id, "social_tweets_count", n)
    await callback.answer(t("social_tweets_saved", lang, n=n))
    mentions_count = int(new_settings.get("social_mentions_count", n))
    top_posts = int(new_settings.get("social_top_posts", 3))
    await callback.message.edit_text(
        t("social_settings_menu", lang, tweets_count=n, mentions_count=mentions_count, top_posts=top_posts),
        reply_markup=social_settings_keyboard(lang, n, mentions_count, top_posts),
    )


@router.callback_query(F.data.startswith("social_mentions:"))
async def cb_social_mentions(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "custom":
        await state.set_state(SocialSettingsStates.entering_mentions_count)
        await state.update_data(lang=lang)
        await callback.message.answer(t("enter_mentions_count", lang))
        return

    n = int(value)
    new_settings = await _save_setting(callback.from_user.id, "social_mentions_count", n)
    await callback.answer(t("social_mentions_saved", lang, n=n))
    tweets_count = int(new_settings.get("social_tweets_count", 15))
    top_posts = int(new_settings.get("social_top_posts", 3))
    await callback.message.edit_text(
        t("social_settings_menu", lang, tweets_count=tweets_count, mentions_count=n, top_posts=top_posts),
        reply_markup=social_settings_keyboard(lang, tweets_count, n, top_posts),
    )


@router.callback_query(F.data.startswith("social_top:"))
async def cb_social_top(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "custom":
        await state.set_state(SocialSettingsStates.entering_top_posts)
        await state.update_data(lang=lang)
        await callback.message.answer(t("enter_top_posts", lang))
        return

    n = int(value)
    new_settings = await _save_setting(callback.from_user.id, "social_top_posts", n)
    await callback.answer(t("social_top_saved", lang, n=n))
    tweets_count = int(new_settings.get("social_tweets_count", 15))
    mentions_count = int(new_settings.get("social_mentions_count", tweets_count))
    await callback.message.edit_text(
        t("social_settings_menu", lang, tweets_count=tweets_count, mentions_count=mentions_count, top_posts=n),
        reply_markup=social_settings_keyboard(lang, tweets_count, mentions_count, n),
    )


@router.message(SocialSettingsStates.entering_tweets_count)
async def msg_custom_tweets_count(message: Message, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.clear()

    try:
        n = int(message.text.strip())
        if n < 1 or n > 200:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer(t("invalid_number", stored_lang))
        return

    new_settings = await _save_setting(message.from_user.id, "social_tweets_count", n)
    mentions_count = int(new_settings.get("social_mentions_count", n))
    top_posts = int(new_settings.get("social_top_posts", 3))
    await message.answer(
        t("social_settings_menu", stored_lang, tweets_count=n, mentions_count=mentions_count, top_posts=top_posts),
        reply_markup=social_settings_keyboard(stored_lang, n, mentions_count, top_posts),
    )


@router.message(SocialSettingsStates.entering_mentions_count)
async def msg_custom_mentions_count(message: Message, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.clear()

    try:
        n = int(message.text.strip())
        if n < 1 or n > 200:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer(t("invalid_number", stored_lang))
        return

    new_settings = await _save_setting(message.from_user.id, "social_mentions_count", n)
    tweets_count = int(new_settings.get("social_tweets_count", 15))
    top_posts = int(new_settings.get("social_top_posts", 3))
    await message.answer(
        t("social_settings_menu", stored_lang, tweets_count=tweets_count, mentions_count=n, top_posts=top_posts),
        reply_markup=social_settings_keyboard(stored_lang, tweets_count, n, top_posts),
    )


@router.message(SocialSettingsStates.entering_top_posts)
async def msg_custom_top_posts(message: Message, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.clear()

    try:
        n = int(message.text.strip())
        if n < 1 or n > 20:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer(t("invalid_number", stored_lang))
        return

    new_settings = await _save_setting(message.from_user.id, "social_top_posts", n)
    tweets_count = int(new_settings.get("social_tweets_count", 15))
    mentions_count = int(new_settings.get("social_mentions_count", tweets_count))
    await message.answer(
        t("social_settings_menu", stored_lang, tweets_count=tweets_count, mentions_count=mentions_count, top_posts=n),
        reply_markup=social_settings_keyboard(stored_lang, tweets_count, mentions_count, n),
    )


@router.callback_query(F.data == "settings_docs")
async def cb_settings_docs(callback: CallbackQuery, lang: str = "ru") -> None:
    await callback.answer()
    user_settings = await _load_settings(callback.from_user.id)
    max_pages = int(user_settings.get("docs_max_pages", 30))
    await callback.message.edit_text(
        t("docs_settings_menu", lang, max_pages=max_pages),
        reply_markup=docs_settings_keyboard(lang, max_pages),
    )


@router.callback_query(F.data.startswith("docs_pages:"))
async def cb_docs_pages(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "custom":
        await state.set_state(DocsSettingsStates.entering_pages_count)
        await state.update_data(lang=lang)
        await callback.message.answer(t("enter_docs_pages", lang))
        return

    n = int(value)
    await _save_setting(callback.from_user.id, "docs_max_pages", n)
    await callback.answer(t("docs_pages_saved", lang, n=n))
    await callback.message.edit_text(
        t("docs_settings_menu", lang, max_pages=n),
        reply_markup=docs_settings_keyboard(lang, n),
    )


@router.message(DocsSettingsStates.entering_pages_count)
async def msg_custom_docs_pages(message: Message, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.clear()

    try:
        n = int(message.text.strip())
        if n < 1 or n > 100:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer(t("invalid_number", stored_lang))
        return

    await _save_setting(message.from_user.id, "docs_max_pages", n)
    await message.answer(
        t("docs_settings_menu", stored_lang, max_pages=n),
        reply_markup=docs_settings_keyboard(stored_lang, n),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, lang: str = "ru") -> None:
    await message.answer(t("help", lang))


@router.message(Command("settings"))
async def cmd_settings(message: Message, lang: str = "ru") -> None:
    await message.answer(
        t("settings_menu", lang, lang_label=t("lang_label", lang)),
        reply_markup=settings_keyboard(lang),
    )
