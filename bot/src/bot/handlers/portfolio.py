from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from src.bot.i18n import t
from src.bot.keyboards import portfolio_item_keyboard, report_keyboard

router = Router(name="portfolio")


def _format_score(score: int | None) -> str:
    if score is None:
        return "—"
    if score >= 71:
        return f"{score} 🟢"
    if score >= 41:
        return f"{score} 🟡"
    return f"{score} 🔴"


async def _show_portfolio(target: Message, user_id: int, lang: str = "ru") -> None:
    from src.db.engine import async_session_factory
    from src.db.repositories import PortfolioRepository, ReportRepository

    async with async_session_factory() as session:
        entries = await PortfolioRepository(session).list_by_user(user_id)
        if not entries:
            await target.answer(t("portfolio_empty", lang))
            return

        report_repo = ReportRepository(session)
        items: list[dict] = []
        for entry in entries:
            project_name = entry.project.name if entry.project else f"#{entry.project_id}"
            latest = await report_repo.get_latest_by_project(user_id, entry.project_id)
            items.append({
                "project_id": entry.project_id,
                "project_name": project_name,
                "score": latest.overall_score if latest else None,
                "added": entry.added_at.strftime("%d.%m.%Y"),
            })

    lines = [t("portfolio_header", lang)]
    for item in items:
        lines.append(
            t("portfolio_item", lang,
              name=item["project_name"],
              score=_format_score(item["score"]),
              date=item["added"])
        )
    await target.answer("\n".join(lines))

    for item in items:
        await target.answer(
            f"<b>{item['project_name']}</b>",
            reply_markup=portfolio_item_keyboard(item["project_id"], lang),
        )


@router.message(Command("portfolio"))
async def cmd_portfolio(message: Message, lang: str = "ru") -> None:
    await _show_portfolio(message, message.from_user.id, lang)


@router.callback_query(F.data == "portfolio")
async def cb_portfolio(callback: CallbackQuery, lang: str = "ru") -> None:
    await callback.answer()
    await _show_portfolio(callback.message, callback.from_user.id, lang)


@router.callback_query(F.data.startswith("portfolio_remove:"))
async def cb_portfolio_remove(callback: CallbackQuery, lang: str = "ru") -> None:
    project_id = int(callback.data.split(":", 1)[1])
    user_id = callback.from_user.id

    try:
        from src.db.engine import async_session_factory
        from src.db.repositories import PortfolioRepository
        async with async_session_factory() as session:
            await PortfolioRepository(session).remove(user_id=user_id, project_id=project_id)
            await session.commit()
        await callback.answer(t("removed_from_portfolio", lang))
        await _show_portfolio(callback.message, user_id, lang)
    except Exception as e:
        await callback.answer(t("error_generic", lang, error=str(e)), show_alert=True)


@router.callback_query(F.data.startswith("view_report:"))
async def cb_view_report(callback: CallbackQuery, lang: str = "ru") -> None:
    project_id = int(callback.data.split(":", 1)[1])
    user_id = callback.from_user.id

    try:
        from src.db.engine import async_session_factory
        from src.db.repositories import ReportRepository
        async with async_session_factory() as session:
            latest = await ReportRepository(session).get_latest_by_project(user_id, project_id)

        if latest is None:
            await callback.answer(t("report_not_found_alert", lang), show_alert=True)
            return

        await callback.answer()
        report_data = latest.report_data or {}
        project_name = report_data.get("project_name", f"#{project_id}")
        await callback.message.answer(
            t("last_report_label", lang, name=project_name, score=_format_score(latest.overall_score)),
            reply_markup=report_keyboard(project_name=project_name, report_id=latest.id, lang=lang),
        )
    except Exception as e:
        await callback.answer(t("error_generic", lang, error=str(e)), show_alert=True)
