from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.keyboards import main_keyboard

router = Router(name="start")


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 <b>Web3 Due Diligence Bot</b>\n\n"
        "Я анализирую криптостартапы и помогаю оценить риски инвестиций.\n\n"
        "Как использовать:\n"
        "• <code>/analyze LayerZero</code> — полный анализ проекта\n"
        "• <code>/portfolio</code> — ваш список проектов\n"
        "• <code>/help</code> — справка\n\n"
        "Просто отправьте мне название проекта или ссылку на него.",
        reply_markup=main_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "<b>Команды:</b>\n"
        "/analyze &lt;название&gt; — анализ проекта\n"
        "/portfolio — список отслеживаемых проектов\n"
        "/settings — настройки уведомлений\n\n"
        "<b>Что анализируется:</b>\n"
        "📊 Токеномика и вестинг\n"
        "💰 Инвесторы и раунды финансирования\n"
        "👥 Команда (верификация LinkedIn)\n"
        "📱 Социальные сети и сентимент\n"
        "🔍 Перекрёстная верификация данных"
    )
