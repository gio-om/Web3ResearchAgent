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
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from src.bot.keyboards import analysis_type_keyboard, report_keyboard

router = Router(name="analyze")


class AnalysisStates(StatesGroup):
    choosing_mode = State()   # query stored, waiting for mode selection


# ─── Mapping: mode → enabled_modules ────────────────────────────────────────
_MODE_MODULES: dict[str, list[str]] = {
    "full":   ["aggregator", "documentation", "social", "team"],
    "market": ["aggregator"],
    "docs":   ["aggregator", "documentation"],   # aggregator нужен для вестинга и раундов
    "social": ["social"],
    "team":   ["team"],
}

_MODE_LABEL: dict[str, str] = {
    "full":   "Полный анализ",
    "market": "Рыночные данные",
    "docs":   "Документация / токеномика",
    "social": "Соцсети",
    "team":   "Команда",
}

_MODULE_LABEL: dict[str, str] = {
    "aggregator":    "Сбор данных с агрегаторов",
    "documentation": "Анализ документации",
    "social":        "Проверка соцсетей",
    "team":          "Верификация команды",
}

RESULT_TEMPLATE = (
    "📊 <b>Анализ: {project_name}</b>\n\n"
    "Скоринг: <b>{score}/100</b> {stars}\n"
    "Рекомендация: <b>{recommendation}</b> {rec_emoji}\n\n"
    "{investors_line}"
    "{fdv_line}"
    "\n{flags}\n"
    "Источники данных: {sources}"
)


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


def _build_progress_text(project_name: str, mode: str) -> str:
    modules = _MODE_MODULES.get(mode, _MODE_MODULES["full"])
    lines = [f"🔍 <b>Анализ проекта: {project_name}</b>"]
    if mode != "full":
        lines.append(f"<i>Режим: {_MODE_LABEL.get(mode, mode)}</i>")
    lines.append("")
    for m in modules:
        lines.append(f"⏳ {_MODULE_LABEL[m]}...")
    return "\n".join(lines)


def score_to_stars(score: int) -> str:
    stars = round(score / 20)
    return "⭐" * stars + "☆" * (5 - stars)


def recommendation_emoji(rec: str) -> str:
    return {"Strong": "🟢", "Interesting": "🟡", "DYOR": "🟠", "Avoid": "🔴"}.get(rec, "⚪")


# ─── Ask user to choose mode ─────────────────────────────────────────────────

async def _ask_mode(message: Message, state: FSMContext, query: str, user_id: int = 0) -> None:
    """Store query in FSM and present the mode-selection keyboard."""
    await state.set_state(AnalysisStates.choosing_mode)
    await state.update_data(query=query, user_id=_resolve_user_id(user_id, message))
    await message.answer(
        f"🔍 Проект: <b>{query}</b>\n\nВыбери тип анализа:",
        reply_markup=analysis_type_keyboard(),
    )


# ─── Entry-point handlers ────────────────────────────────────────────────────

@router.message(Command("analyze"))
async def cmd_analyze(message: Message, state: FSMContext) -> None:
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.answer(
            "❓ Укажи название проекта или ссылку:\n"
            "<code>/analyze LayerZero</code>\n"
            "<code>/analyze https://cryptorank.io/price/layerzero</code>"
        )
        return
    await _ask_mode(message, state, args[1].strip())


@router.message(F.text & ~F.text.startswith("/"))
async def handle_plain_text(message: Message, state: FSMContext) -> None:
    """Handle plain project name or URL without /analyze command."""
    query = message.text.strip()
    if len(query) < 2:
        return
    await _ask_mode(message, state, query)


@router.callback_query(F.data == "analyze_start")
async def cb_analyze_start(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "🔍 Введите название проекта или ссылку:\n"
        "<code>LayerZero</code>\n"
        "<code>https://cryptorank.io/price/layerzero</code>"
    )


# ─── Mode selection callback ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("atype:"))
async def cb_analysis_type(callback: CallbackQuery, state: FSMContext) -> None:
    mode = callback.data.split(":", 1)[1]
    await callback.answer()

    if mode == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Анализ отменён.")
        return

    if mode not in _MODE_MODULES:
        await callback.message.edit_text("❓ Неизвестный режим анализа.")
        return

    fsm_data = await state.get_data()
    query = fsm_data.get("query", "")
    user_id = fsm_data.get("user_id") or callback.from_user.id
    await state.clear()

    if not query:
        await callback.message.edit_text(
            "❓ Не найден запрос. Введите название проекта заново."
        )
        return

    await callback.message.edit_text(
        f"🔍 Проект: <b>{query}</b>\nРежим: <b>{_MODE_LABEL[mode]}</b>"
    )
    await _run_analysis(callback.message, query, mode, user_id=user_id)


# ─── Reanalyze callback (always full) ────────────────────────────────────────

@router.callback_query(F.data.startswith("reanalyze:"))
async def cb_reanalyze(callback: CallbackQuery, state: FSMContext) -> None:
    project_name = callback.data.split(":", 1)[1]
    await callback.answer()
    await _ask_mode(callback.message, state, project_name, user_id=callback.from_user.id)


# ─── Portfolio-add callback ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("portfolio_add:"))
async def cb_portfolio_add(callback: CallbackQuery) -> None:
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
                await callback.answer("❌ Отчёт не найден", show_alert=True)
                return

            already = await portfolio_repo.is_in_portfolio(user_id, db_report.project_id)
            if already:
                await callback.answer("Проект уже в портфеле", show_alert=False)
                return

            await portfolio_repo.add(user_id=user_id, project_id=db_report.project_id)
            await session.commit()

        await callback.answer("✅ Добавлено в портфель")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ─── Core pipeline runner ─────────────────────────────────────────────────────

async def _run_analysis(message: Message, query: str, mode: str = "full", user_id: int = 0) -> None:
    from src.agents.graph import build_analysis_graph
    from src.schemas.agent_state import AgentState
    from datetime import datetime, timezone

    enabled_modules = _MODE_MODULES.get(mode, _MODE_MODULES["full"])

    progress_msg = await message.answer(_build_progress_text(query, mode))

    resolved_user_id = _resolve_user_id(user_id, message)
    state = AgentState(
        project_query=query,
        user_id=resolved_user_id,
        chat_id=message.chat.id,
        message_id=progress_msg.message_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        enabled_modules=enabled_modules,
    )

    try:
        graph = build_analysis_graph()
        final_state = await graph.ainvoke(state.model_dump())

        if final_state.get("status") == "failed":
            errors = '; '.join(html.escape(e) for e in final_state.get('errors', ['Неизвестная ошибка']))
            await progress_msg.edit_text(
                f"❌ Анализ проекта <b>{html.escape(query)}</b> не удался.\n"
                f"Ошибки: {errors}"
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
        flags_text = "\n".join(flag_lines) if flag_lines else "Флагов не найдено"

        coingecko_summary = report.get("coingecko_summary", {}) or {}
        fdv = coingecko_summary.get("fdv_usd")
        mcap = coingecko_summary.get("market_cap_usd")
        fdv_line = f"FDV: {_fmt_usd(fdv)} | MCap: {_fmt_usd(mcap)}\n" if fdv and mcap else ""

        investors = report.get("investors", [])
        top_investors = [html.escape(inv.get("name", "")) for inv in investors[:3] if inv.get("name")]
        investors_line = f"Инвесторы: {', '.join(top_investors)}\n" if top_investors else ""

        sources = html.escape(", ".join(report.get("data_sources", [])[:3]))

        result_text = RESULT_TEMPLATE.format(
            project_name=project_name,
            score=score,
            stars=score_to_stars(score),
            recommendation=recommendation,
            rec_emoji=recommendation_emoji(recommendation),
            investors_line=investors_line,
            fdv_line=fdv_line,
            flags=flags_text,
            sources=sources or "агрегаторы",
        )

        report_id = report.get("id", 0)
        await progress_msg.edit_text(
            result_text,
            reply_markup=report_keyboard(project_name=project_name, report_id=report_id),
        )

    except Exception as e:
        await progress_msg.edit_text(
            f"❌ Произошла ошибка при анализе <b>{html.escape(query)}</b>:\n<code>{html.escape(str(e))}</code>"
        )
