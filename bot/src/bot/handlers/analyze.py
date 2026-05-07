"""
Handler for /analyze command and related callbacks.

Flow:
1. User sends /analyze LayerZero (or just a project name)
2. Bot shows analysis-type keyboard (full / individual module)
3. User picks mode → bot sends progress message → runs pipeline
4. On completion, sends the result card with Mini App button
"""
import html
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from src.bot.i18n import t
from src.bot.keyboards import (
    analysis_type_keyboard, docs_link_keyboard, report_keyboard,
    fdv_context_ask_keyboard, fdv_sector_keyboard, fdv_comparable_keyboard,
    fdv_confirm_keyboard,
)

router = Router(name="analyze")


class AnalysisStates(StatesGroup):
    choosing_mode = State()
    asking_docs_link = State()   # waiting for yes/no on user-provided docs URL
    waiting_docs_url = State()   # waiting for the user to type the docs URL
    # FDV prediction context collection
    asking_fdv_context = State()   # yes/no gate
    fdv_sector = State()
    fdv_comparable = State()       # text or skip
    fdv_confirm = State()          # confirmation before running


_MODE_MODULES: dict[str, list[str]] = {
    "full":          ["aggregator", "documentation", "social", "team"],
    "market":        ["aggregator"],
    "docs":          ["aggregator"],
    "documentation": ["documentation"],
    "social":        ["social"],
    "team":          ["team"],
}

_MODE_LABEL_KEY: dict[str, str] = {
    "full":          "mode_full",
    "market":        "mode_market",
    "docs":          "mode_docs",
    "documentation": "mode_documentation",
    "social":        "mode_social",
    "team":          "mode_team",
}

_MODULE_LABEL_KEY: dict[str, str] = {
    "aggregator":    "module_aggregator",
    "documentation": "module_documentation",
    "social":        "module_social",
    "team":          "module_team",
}


def _resolve_user_id(user_id: int, message: Message) -> int:
    return user_id or (message.from_user.id if message.from_user else 0)


def _fmt_usd(value: float | None) -> str:
    if not value:
        return "N/A"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M"
    return f"${value:,.0f}"


def _build_progress_text(project_name: str, mode: str, lang: str) -> str:
    modules = _MODE_MODULES.get(mode, _MODE_MODULES["full"])
    lines = [t("progress_header", lang, project=project_name)]
    if mode != "full":
        lines.append(t("progress_mode", lang, mode=t(_MODE_LABEL_KEY[mode], lang)))
    lines.append("")
    for m in modules:
        lines.append(f"⏳ {t(_MODULE_LABEL_KEY[m], lang)}...")
    return "\n".join(lines)


def score_to_stars(score: int) -> str:
    stars = round(score / 20)
    return "⭐" * stars + "☆" * (5 - stars)


def recommendation_emoji(rec: str) -> str:
    return {"Strong": "🟢", "Interesting": "🟡", "DYOR": "🟠", "Avoid": "🔴"}.get(rec, "⚪")


async def _ask_mode(message: Message, state: FSMContext, query: str, lang: str, user_id: int = 0) -> None:
    await state.set_state(AnalysisStates.choosing_mode)
    await state.update_data(query=query, user_id=_resolve_user_id(user_id, message), lang=lang)
    await message.answer(
        t("choose_analysis_mode", lang, query=query),
        reply_markup=analysis_type_keyboard(lang),
    )


@router.message(Command("analyze"))
async def cmd_analyze(message: Message, state: FSMContext, lang: str = "ru") -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(t("analyze_prompt", lang))
        return
    await _ask_mode(message, state, args[1].strip(), lang)


@router.callback_query(F.data == "docs_link:yes")
async def cb_docs_link_yes(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.set_state(AnalysisStates.waiting_docs_url)
    await callback.answer()
    await callback.message.edit_text(t("docs_link_prompt", stored_lang))


@router.callback_query(F.data == "docs_link:no")
async def cb_docs_link_no(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    query = fsm_data.get("query", "")
    user_id = fsm_data.get("user_id") or callback.from_user.id
    stored_lang = fsm_data.get("lang", lang)
    mode = fsm_data.get("mode", "documentation")
    await state.clear()
    await callback.answer()
    mode_label = t(_MODE_LABEL_KEY[mode], stored_lang)
    await callback.message.edit_text(
        t("project_mode_label", stored_lang, query=query, mode=mode_label)
    )
    await _run_analysis(callback.message, query, mode, stored_lang, user_id=user_id)


@router.message(AnalysisStates.waiting_docs_url, F.text)
async def handle_docs_url_input(message: Message, state: FSMContext, lang: str = "ru") -> None:
    docs_url = message.text.strip()
    fsm_data = await state.get_data()
    query = fsm_data.get("query", "")
    user_id = fsm_data.get("user_id") or (message.from_user.id if message.from_user else 0)
    stored_lang = fsm_data.get("lang", lang)
    mode = fsm_data.get("mode", "documentation")
    await state.clear()
    mode_label = t(_MODE_LABEL_KEY[mode], stored_lang)
    await message.answer(
        t("project_mode_label", stored_lang, query=query, mode=mode_label)
    )
    await _run_analysis(message, query, mode, stored_lang, user_id=user_id, docs_url=docs_url)


@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def handle_plain_text(message: Message, state: FSMContext, lang: str = "ru") -> None:
    query = message.text.strip()
    if len(query) < 2:
        return
    await _ask_mode(message, state, query, lang)


@router.callback_query(F.data == "analyze_start")
async def cb_analyze_start(callback: CallbackQuery, lang: str = "ru") -> None:
    await callback.answer()
    await callback.message.answer(t("enter_project", lang))


@router.callback_query(F.data.startswith("atype:"))
async def cb_analysis_type(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    mode = callback.data.split(":", 1)[1]
    await callback.answer()

    if mode == "cancel":
        await state.clear()
        await callback.message.edit_text(t("analysis_cancelled", lang))
        return

    if mode not in _MODE_MODULES:
        await callback.message.edit_text(t("unknown_mode", lang))
        return

    fsm_data = await state.get_data()
    query = fsm_data.get("query", "")
    user_id = fsm_data.get("user_id") or callback.from_user.id
    # Prefer lang stored when _ask_mode was called
    stored_lang = fsm_data.get("lang", lang)

    if not query:
        await state.clear()
        await callback.message.edit_text(t("no_query", stored_lang))
        return

    # Documentation mode: ask user whether they have a docs link
    if mode == "documentation":
        await state.set_state(AnalysisStates.asking_docs_link)
        await state.update_data(query=query, user_id=user_id, lang=stored_lang, mode=mode)
        await callback.message.edit_text(
            t("docs_link_question", stored_lang),
            reply_markup=docs_link_keyboard(stored_lang),
        )
        return

    # For modes with aggregator: offer FDV context collection
    if "aggregator" in _MODE_MODULES.get(mode, []):
        await state.set_state(AnalysisStates.asking_fdv_context)
        await state.update_data(query=query, user_id=user_id, lang=stored_lang, mode=mode)
        await callback.message.edit_text(
            t("fdv_context_question", stored_lang),
            reply_markup=fdv_context_ask_keyboard(stored_lang),
        )
        return

    await state.clear()
    mode_label = t(_MODE_LABEL_KEY[mode], stored_lang)
    await callback.message.edit_text(
        t("project_mode_label", stored_lang, query=query, mode=mode_label)
    )
    await _run_analysis(callback.message, query, mode, stored_lang, user_id=user_id)


# ── FDV context: skip ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "fdv_context:skip")
async def cb_fdv_context_skip(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    query = fsm_data.get("query", "")
    user_id = fsm_data.get("user_id") or callback.from_user.id
    stored_lang = fsm_data.get("lang", lang)
    mode = fsm_data.get("mode", "full")
    await state.clear()
    await callback.answer()
    mode_label = t(_MODE_LABEL_KEY[mode], stored_lang)
    await callback.message.edit_text(
        t("project_mode_label", stored_lang, query=query, mode=mode_label)
    )
    await _run_analysis(callback.message, query, mode, stored_lang, user_id=user_id)


# ── FDV context: start → collect 6 params ────────────────────────────────────

@router.callback_query(F.data == "fdv_context:start")
async def cb_fdv_context_start(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.set_state(AnalysisStates.fdv_sector)
    await callback.answer()
    await callback.message.edit_text(
        t("fdv_sector_prompt", stored_lang),
        reply_markup=fdv_sector_keyboard(stored_lang),
    )


@router.callback_query(F.data.startswith("fdv_sector:"))
async def cb_fdv_sector(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    value = callback.data.split(":", 1)[1]
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.update_data(fdv_sector=value)
    await state.set_state(AnalysisStates.fdv_comparable)
    await callback.answer()
    await callback.message.edit_text(
        t("fdv_comparable_prompt", stored_lang),
        reply_markup=fdv_comparable_keyboard(stored_lang),
    )


async def _build_fdv_confirm(state: FSMContext, lang: str) -> tuple[str, object, str]:
    """Returns (text, markup, stored_lang) for the FDV confirmation screen."""
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    query = fsm_data.get("query", "")
    sector_key = fsm_data.get("fdv_sector", "")
    comparable = fsm_data.get("fdv_comparable")
    sector_label = t(f"sector_{sector_key}", stored_lang) if sector_key else "—"
    comparable_label = _fmt_usd(comparable) if comparable else t("fdv_comparable_none", stored_lang)
    text = t("fdv_confirm_prompt", stored_lang, query=query, sector=sector_label, comparable=comparable_label)
    return text, fdv_confirm_keyboard(stored_lang), stored_lang


@router.callback_query(F.data == "fdv_comparable:skip")
async def cb_fdv_comparable_skip(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    await state.update_data(fdv_comparable=None)
    await state.set_state(AnalysisStates.fdv_confirm)
    await callback.answer()
    text, markup, _ = await _build_fdv_confirm(state, lang)
    await callback.message.edit_text(text, reply_markup=markup)


@router.message(AnalysisStates.fdv_comparable, F.text)
async def handle_fdv_comparable_input(message: Message, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    raw = message.text.strip().replace(",", "").replace("$", "").replace("M", "").replace("m", "")
    try:
        value_m = float(raw)
        if value_m <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer(t("fdv_comparable_invalid", stored_lang),
                             reply_markup=fdv_comparable_keyboard(stored_lang))
        return
    await state.update_data(fdv_comparable=int(value_m * 1_000_000))
    await state.set_state(AnalysisStates.fdv_confirm)
    text, markup, _ = await _build_fdv_confirm(state, stored_lang)
    await message.answer(text, reply_markup=markup)


# ── FDV back navigation ────────────────────────────────────────────────────────

@router.callback_query(F.data == "fdv_back:sector")
async def cb_fdv_back_sector(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.set_state(AnalysisStates.fdv_sector)
    await callback.answer()
    await callback.message.edit_text(
        t("fdv_sector_prompt", stored_lang),
        reply_markup=fdv_sector_keyboard(stored_lang),
    )


@router.callback_query(F.data == "fdv_back:comparable")
async def cb_fdv_back_comparable(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await state.set_state(AnalysisStates.fdv_comparable)
    await callback.answer()
    await callback.message.edit_text(
        t("fdv_comparable_prompt", stored_lang),
        reply_markup=fdv_comparable_keyboard(stored_lang),
    )


@router.callback_query(F.data == "fdv_confirm:yes")
async def cb_fdv_confirm(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    await callback.answer()
    await callback.message.edit_text(t("fdv_context_saved", stored_lang))
    await _finalize_fdv_context(callback.message, state, callback.from_user.id, lang)


async def _finalize_fdv_context(message: Message, state: FSMContext, user_id: int, lang: str) -> None:
    fsm_data = await state.get_data()
    stored_lang = fsm_data.get("lang", lang)
    query = fsm_data.get("query", "")
    resolved_user_id = fsm_data.get("user_id") or user_id
    mode = fsm_data.get("mode", "full")
    fdv_context = {
        "sector": fsm_data.get("fdv_sector"),
        "comparable_fdv_usd": fsm_data.get("fdv_comparable"),
    }
    await state.clear()
    await _run_analysis(message, query, mode, stored_lang, user_id=resolved_user_id,
                        fdv_context=fdv_context)


@router.callback_query(F.data.startswith("reanalyze:"))
async def cb_reanalyze(callback: CallbackQuery, state: FSMContext, lang: str = "ru") -> None:
    project_name = callback.data.split(":", 1)[1]
    await callback.answer()
    await _ask_mode(callback.message, state, project_name, lang, user_id=callback.from_user.id)


@router.callback_query(F.data.startswith("portfolio_add:"))
async def cb_portfolio_add(callback: CallbackQuery, lang: str = "ru") -> None:
    report_id = int(callback.data.split(":", 1)[1])
    user_id = callback.from_user.id

    try:
        from src.db.engine import async_session_factory
        from src.db.repositories import PortfolioRepository, ReportRepository
        async with async_session_factory() as session:
            report_repo = ReportRepository(session)
            portfolio_repo = PortfolioRepository(session)

            db_report = await report_repo.get_by_id(report_id)
            if db_report is None:
                await callback.answer(t("report_not_found", lang), show_alert=True)
                return

            already = await portfolio_repo.is_in_portfolio(user_id, db_report.project_id)
            if already:
                await callback.answer(t("already_in_portfolio", lang))
                return

            await portfolio_repo.add(user_id=user_id, project_id=db_report.project_id)
            await session.commit()

        await callback.answer(t("added_to_portfolio", lang))
    except Exception as e:
        await callback.answer(t("error_generic", lang, error=str(e)), show_alert=True)


async def _load_user_settings(user_id: int) -> dict:
    try:
        from src.db.engine import async_session_factory
        from src.db.repositories import UserRepository
        async with async_session_factory() as session:
            repo = UserRepository(session)
            user = await repo.get_by_id(user_id)
            return dict(user.settings or {}) if user else {}
    except Exception:
        return {}


async def _run_analysis(
    message: Message,
    query: str,
    mode: str = "full",
    lang: str = "ru",
    user_id: int = 0,
    docs_url: str = "",
    fdv_context: dict | None = None,
) -> None:
    from src.agents.graph import build_analysis_graph
    from src.schemas.agent_state import AgentState
    from datetime import datetime, timezone

    enabled_modules = _MODE_MODULES.get(mode, _MODE_MODULES["full"])
    progress_msg = await message.answer(_build_progress_text(query, mode, lang))

    resolved_user_id = _resolve_user_id(user_id, message)
    user_settings = await _load_user_settings(resolved_user_id)
    state = AgentState(
        project_query=query,
        user_id=resolved_user_id,
        chat_id=message.chat.id,
        message_id=progress_msg.message_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        enabled_modules=enabled_modules,
        user_settings=user_settings,
        lang=lang,
        skip_cryptorank=(mode == "market"),
        project_urls={"docs": docs_url} if docs_url else {},
        fdv_context=fdv_context or {},
    )

    try:
        graph = build_analysis_graph()
        final_state = await graph.ainvoke(state.model_dump())

        if final_state.get("status") == "failed":
            errors = '; '.join(html.escape(e) for e in final_state.get('errors', []))
            await progress_msg.edit_text(
                t("analysis_failed", lang, project=html.escape(query), errors=errors)
            )
            return

        report = final_state.get("report", {})
        project_name = html.escape(final_state.get("project_name", query))
        score = report.get("overall_score", 0)
        recommendation = html.escape(report.get("recommendation", "DYOR"))
        risk_flags = report.get("risk_flags", [])

        flag_lines = []
        for flag in risk_flags[:5]:
            icon = {"red": "🔴", "yellow": "🟡", "green": "🟢"}.get(flag.get("type", ""), "⚪")
            flag_lines.append(f"{icon} {html.escape(flag.get('message', ''))}")
        flags_text = "\n".join(flag_lines) if flag_lines else t("no_flags", lang)

        coingecko_summary = report.get("coingecko_summary", {}) or {}
        fdv = coingecko_summary.get("fdv_usd")
        mcap = coingecko_summary.get("market_cap_usd")
        fdv_line = f"FDV: {_fmt_usd(fdv)} | MCap: {_fmt_usd(mcap)}\n" if fdv and mcap else ""

        investors = report.get("investors", [])
        top_investors = [html.escape(inv.get("name", "")) for inv in investors[:3] if inv.get("name")]
        investors_line = t("investors_line", lang, investors=", ".join(top_investors)) if top_investors else ""

        sources = html.escape(", ".join(report.get("data_sources", [])[:3]))

        result_text = t("result_template", lang).format(
            project_name=project_name,
            score=score,
            stars=score_to_stars(score),
            recommendation=recommendation,
            rec_emoji=recommendation_emoji(recommendation),
            investors_line=investors_line,
            fdv_line=fdv_line,
            flags=flags_text,
            sources=sources or t("data_sources_fallback", lang),
        )

        report_id = report.get("id", 0)
        await progress_msg.edit_text(
            result_text,
            reply_markup=report_keyboard(project_name=project_name, report_id=report_id, lang=lang),
        )

    except Exception as e:
        await progress_msg.edit_text(
            t("analysis_error", lang, project=html.escape(query), error=html.escape(str(e)))
        )
