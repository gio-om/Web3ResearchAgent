TEXTS: dict[str, dict[str, str]] = {
    "ru": {
        # Start / welcome
        "choose_language": "🌐 Выберите язык / Choose language:",
        "language_set": "✅ Язык установлен: Русский",
        "welcome": (
            "👋 <b>Web3 Due Diligence Bot</b>\n\n"
            "Я анализирую криптостартапы и помогаю оценить риски инвестиций.\n\n"
            "Как использовать:\n"
            "• <code>/analyze LayerZero</code> — полный анализ проекта\n"
            "• <code>/portfolio</code> — ваш список проектов\n"
            "• <code>/help</code> — справка\n\n"
            "Просто отправьте мне название проекта или ссылку на него."
        ),
        "help": (
            "📖 <b>Справка</b>\n\n"
            "<b>Команды:</b>\n"
            "/analyze &lt;название&gt; — анализ проекта\n"
            "/portfolio — список отслеживаемых проектов\n"
            "/settings — настройки\n\n"
            "<b>Что анализируется:</b>\n"
            "📊 Токеномика и вестинг\n"
            "💰 Инвесторы и раунды финансирования\n"
            "👥 Команда (верификация LinkedIn)\n"
            "📱 Социальные сети и сентимент\n"
            "🔍 Перекрёстная верификация данных"
        ),
        # Settings
        "settings_menu": "⚙️ <b>Настройки</b>\n\nЯзык: {lang_label}",
        "lang_label": "🇷🇺 Русский",
        "social_settings_menu": (
            "📱 <b>Настройки соцсетей</b>\n\n"
            "Твитов для анализа: <b>{tweets_count}</b>\n"
            "Важных постов: <b>{top_posts}</b>"
        ),
        "social_tweets_saved": "✅ Твитов для анализа: {n}",
        "social_top_saved": "✅ Важных постов: {n}",
        "enter_tweets_count": "✏️ Введите количество твитов для анализа (1–200):",
        "enter_top_posts": "✏️ Введите количество важных постов для отображения (1–20):",
        "invalid_number": "❌ Некорректное значение. Введите целое число.",
        # Main keyboard buttons
        "btn_analyze": "🔍 Анализировать проект",
        "btn_portfolio": "📁 Мой портфель",
        "btn_settings": "⚙️ Настройки",
        # Settings keyboard buttons
        "btn_language": "🌐 Язык",
        "btn_social_settings": "📱 Соцсети",
        "btn_back": "◀️ Назад",
        # Language keyboard buttons
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_lang_en": "🇬🇧 English",
        # Analysis type keyboard buttons
        "btn_full_analysis": "🔄 Полный анализ",
        "btn_market_data": "📊 Рыночные данные",
        "btn_docs": "📄 Документация / токеномика",
        "btn_social": "📱 Соцсети",
        "btn_team": "👥 Команда",
        "btn_cancel": "❌ Отмена",
        # Report keyboard buttons
        "btn_detailed_report": "📊 Подробный отчёт",
        "btn_add_portfolio": "➕ В портфель",
        "btn_reanalyze": "🔄 Обновить анализ",
        # Portfolio keyboard buttons
        "btn_report": "📊 Отчёт",
        "btn_remove": "🗑 Удалить",
        # Analyze handler
        "analyze_prompt": (
            "❓ Укажи название проекта или ссылку:\n"
            "<code>/analyze LayerZero</code>\n"
            "<code>/analyze https://cryptorank.io/price/layerzero</code>"
        ),
        "enter_project": (
            "🔍 Введите название проекта или ссылку:\n"
            "<code>LayerZero</code>\n"
            "<code>https://cryptorank.io/price/layerzero</code>"
        ),
        "choose_analysis_mode": "🔍 Проект: <b>{query}</b>\n\nВыбери тип анализа:",
        "analysis_cancelled": "❌ Анализ отменён.",
        "unknown_mode": "❓ Неизвестный режим анализа.",
        "no_query": "❓ Не найден запрос. Введите название проекта заново.",
        "project_mode_label": "🔍 Проект: <b>{query}</b>\nРежим: <b>{mode}</b>",
        "progress_header": "🔍 <b>Анализ проекта: {project}</b>",
        "progress_mode": "<i>Режим: {mode}</i>",
        "analysis_failed": "❌ Анализ проекта <b>{project}</b> не удался.\nОшибки: {errors}",
        "analysis_error": "❌ Произошла ошибка при анализе <b>{project}</b>:\n<code>{error}</code>",
        "no_flags": "Флагов не найдено",
        "investors_line": "Инвесторы: {investors}\n",
        "data_sources_fallback": "агрегаторы",
        "result_template": (
            "📊 <b>Анализ: {project_name}</b>\n\n"
            "Скоринг: <b>{score}/100</b> {stars}\n"
            "Рекомендация: <b>{recommendation}</b> {rec_emoji}\n\n"
            "{investors_line}"
            "{fdv_line}"
            "\n{flags}\n"
            "Источники данных: {sources}"
        ),
        # Analysis mode labels (used in keyboards and progress)
        "mode_full": "Полный анализ",
        "mode_market": "Рыночные данные",
        "mode_docs": "Документация / токеномика",
        "mode_social": "Соцсети",
        "mode_team": "Команда",
        # Module labels (progress message)
        "module_aggregator": "Сбор данных с агрегаторов",
        "module_documentation": "Анализ документации",
        "module_social": "Проверка соцсетей",
        "module_team": "Верификация команды",
        # Portfolio
        "portfolio_empty": (
            "📁 <b>Ваш портфель пуст</b>\n\n"
            "Проанализируйте проект и нажмите <b>➕ В портфель</b>:\n"
            "<code>/analyze &lt;название проекта&gt;</code>"
        ),
        "portfolio_header": "📁 <b>Ваш портфель</b>\n",
        "portfolio_item": "• <b>{name}</b> — {score} (добавлен {date})",
        "report_not_found_alert": "Отчёт не найден",
        "last_report_label": "📊 Последний отчёт: <b>{name}</b> — {score}",
        "removed_from_portfolio": "🗑 Удалено из портфеля",
        # Generic errors
        "already_in_portfolio": "Проект уже в портфеле",
        "added_to_portfolio": "✅ Добавлено в портфель",
        "report_not_found": "❌ Отчёт не найден",
        "error_generic": "❌ Ошибка: {error}",
    },
    "en": {
        # Start / welcome
        "choose_language": "🌐 Выберите язык / Choose language:",
        "language_set": "✅ Language set: English",
        "welcome": (
            "👋 <b>Web3 Due Diligence Bot</b>\n\n"
            "I analyze crypto startups and help assess investment risks.\n\n"
            "How to use:\n"
            "• <code>/analyze LayerZero</code> — full project analysis\n"
            "• <code>/portfolio</code> — your project list\n"
            "• <code>/help</code> — help\n\n"
            "Just send me a project name or link."
        ),
        "help": (
            "📖 <b>Help</b>\n\n"
            "<b>Commands:</b>\n"
            "/analyze &lt;name&gt; — analyze a project\n"
            "/portfolio — list of tracked projects\n"
            "/settings — settings\n\n"
            "<b>What is analyzed:</b>\n"
            "📊 Tokenomics and vesting\n"
            "💰 Investors and funding rounds\n"
            "👥 Team (LinkedIn verification)\n"
            "📱 Social media and sentiment\n"
            "🔍 Cross-verification of data"
        ),
        # Settings
        "settings_menu": "⚙️ <b>Settings</b>\n\nLanguage: {lang_label}",
        "lang_label": "🇬🇧 English",
        "social_settings_menu": (
            "📱 <b>Social media settings</b>\n\n"
            "Tweets to analyse: <b>{tweets_count}</b>\n"
            "Top posts to show: <b>{top_posts}</b>"
        ),
        "social_tweets_saved": "✅ Tweets to analyse: {n}",
        "social_top_saved": "✅ Top posts: {n}",
        "enter_tweets_count": "✏️ Enter the number of tweets to analyse (1–200):",
        "enter_top_posts": "✏️ Enter the number of top posts to display (1–20):",
        "invalid_number": "❌ Invalid value. Please enter a whole number.",
        # Main keyboard buttons
        "btn_analyze": "🔍 Analyze project",
        "btn_portfolio": "📁 My portfolio",
        "btn_settings": "⚙️ Settings",
        # Settings keyboard buttons
        "btn_language": "🌐 Language",
        "btn_social_settings": "📱 Social media",
        "btn_back": "◀️ Back",
        # Language keyboard buttons
        "btn_lang_ru": "🇷🇺 Русский",
        "btn_lang_en": "🇬🇧 English",
        # Analysis type keyboard buttons
        "btn_full_analysis": "🔄 Full analysis",
        "btn_market_data": "📊 Market data",
        "btn_docs": "📄 Documentation / tokenomics",
        "btn_social": "📱 Social media",
        "btn_team": "👥 Team",
        "btn_cancel": "❌ Cancel",
        # Report keyboard buttons
        "btn_detailed_report": "📊 Detailed report",
        "btn_add_portfolio": "➕ Add to portfolio",
        "btn_reanalyze": "🔄 Re-analyze",
        # Portfolio keyboard buttons
        "btn_report": "📊 Report",
        "btn_remove": "🗑 Remove",
        # Analyze handler
        "analyze_prompt": (
            "❓ Enter a project name or link:\n"
            "<code>/analyze LayerZero</code>\n"
            "<code>/analyze https://cryptorank.io/price/layerzero</code>"
        ),
        "enter_project": (
            "🔍 Enter a project name or link:\n"
            "<code>LayerZero</code>\n"
            "<code>https://cryptorank.io/price/layerzero</code>"
        ),
        "choose_analysis_mode": "🔍 Project: <b>{query}</b>\n\nChoose analysis type:",
        "analysis_cancelled": "❌ Analysis cancelled.",
        "unknown_mode": "❓ Unknown analysis mode.",
        "no_query": "❓ No query found. Please enter a project name again.",
        "project_mode_label": "🔍 Project: <b>{query}</b>\nMode: <b>{mode}</b>",
        "progress_header": "🔍 <b>Analyzing project: {project}</b>",
        "progress_mode": "<i>Mode: {mode}</i>",
        "analysis_failed": "❌ Analysis of <b>{project}</b> failed.\nErrors: {errors}",
        "analysis_error": "❌ An error occurred while analyzing <b>{project}</b>:\n<code>{error}</code>",
        "no_flags": "No flags found",
        "investors_line": "Investors: {investors}\n",
        "data_sources_fallback": "aggregators",
        "result_template": (
            "📊 <b>Analysis: {project_name}</b>\n\n"
            "Score: <b>{score}/100</b> {stars}\n"
            "Recommendation: <b>{recommendation}</b> {rec_emoji}\n\n"
            "{investors_line}"
            "{fdv_line}"
            "\n{flags}\n"
            "Data sources: {sources}"
        ),
        # Analysis mode labels
        "mode_full": "Full analysis",
        "mode_market": "Market data",
        "mode_docs": "Documentation / tokenomics",
        "mode_social": "Social media",
        "mode_team": "Team",
        # Module labels
        "module_aggregator": "Aggregator data collection",
        "module_documentation": "Documentation analysis",
        "module_social": "Social media check",
        "module_team": "Team verification",
        # Portfolio
        "portfolio_empty": (
            "📁 <b>Your portfolio is empty</b>\n\n"
            "Analyze a project and click <b>➕ Add to portfolio</b>:\n"
            "<code>/analyze &lt;project name&gt;</code>"
        ),
        "portfolio_header": "📁 <b>My Portfolio</b>\n",
        "portfolio_item": "• <b>{name}</b> — {score} (added {date})",
        "report_not_found_alert": "Report not found",
        "last_report_label": "📊 Latest report: <b>{name}</b> — {score}",
        "removed_from_portfolio": "🗑 Removed from portfolio",
        # Generic errors
        "already_in_portfolio": "Project already in portfolio",
        "added_to_portfolio": "✅ Added to portfolio",
        "report_not_found": "❌ Report not found",
        "error_generic": "❌ Error: {error}",
    },
}

DEFAULT_LANG = "ru"


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    lang_dict = TEXTS.get(lang, TEXTS[DEFAULT_LANG])
    text = lang_dict.get(key, TEXTS[DEFAULT_LANG].get(key, key))
    return text.format(**kwargs) if kwargs else text
