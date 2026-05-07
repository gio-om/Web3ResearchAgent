export type Lang = "ru" | "en";

const TR = {
  en: {
    // App
    no_report_selected: "No report selected.",
    failed_load_report: "Failed to load report.",
    portfolio_empty: "Portfolio is empty.",
    failed_load_portfolio: "Failed to load portfolio.",
    failed_compare: "Failed to compare projects.",
    section_overview: "Overview",
    section_documentation: "Documentation",
    section_risk_flags: "Risk Flags",
    section_tokenomics: "Tokenomics — Vesting",
    section_funding: "Funding & Investors",
    section_team: "Team",
    section_socials: "Socials",
    section_data_sources: "Data Sources",
    compare_title: "Compare",
    portfolio_title: "Portfolio",
    // ProjectCard
    strengths: "Strengths",
    weaknesses: "Weaknesses",
    market_cap: "Market Cap",
    // RiskFlags
    no_risk_flags: "No risk flags detected.",
    flag_cat_tokenomics: "Tokenomics",
    flag_cat_team: "Team",
    flag_cat_social: "Social",
    flag_cat_investors: "Investors",
    flag_cat_general: "General",
    // TeamVerification
    no_team_data: "No team data available.",
    all_members: "All members",
    // SocialAnalysis
    no_social_data: "No social data available.",
    sentiment: "Sentiment",
    tweets_analysed: "tweets analysed",
    followers: "followers",
    engagement: "Engagement",
    avg_views: "Avg views",
    following: "Following",
    top_posts: "Top posts",
    positive_signals: "Positive signals",
    key_concerns: "Key concerns",
    kol_mentions: "KOL mentions",
    bot_activity_signals: "Bot activity signals",
    // DocumentationAnalysis
    no_docs_data: "No documentation data.",
    docs_not_found: "Documentation not found:",
    docs_fallback_notice: "No documentation found — collected general info from the project website",
    key_features: "Key features",
    token_label: "Token:",
    supply_label: "Supply:",
    unusual_conditions: "Unusual conditions",
    no_unusual_conditions: "No unusual conditions detected",
    completeness_data: "data",
    completeness_high: "High",
    completeness_medium: "Medium",
    completeness_low: "Low",
    // FundsList
    no_funding_data: "No funding data available.",
    total_raised: "Total Raised",
    raised: "Raised",
    valuation: "Val.",
    all_investors: "All Investors",
    col_name: "Name",
    col_tier: "Tier",
    col_type: "Type",
    col_stage: "Stage",
    lead_badge: "Lead",
    no_investor_data: "No investor data",
    // FDV prediction
    predicted_val: "Pred. FDV",
    conf_high: "High",
    conf_medium: "Med.",
    conf_low: "Low",
    fdv_range_label: "Range",
    fdv_methodology_label: "Method",
    // VestingChart
    no_vesting_data: "No vesting data available.",
    allocation: "Allocation",
    max_supply: "Max. Supply:",
    vesting_schedule: "Vesting Schedule",
    col_recipient: "Recipient",
    col_total: "Total",
    col_unlocked: "Unlocked",
    col_locked: "Locked",
    col_cliff: "Cliff",
    col_vesting: "Vesting",
    today_label: "TODAY",
    timeline_unavailable: "Timeline unavailable — no TGE date in data.",
    tab_table: "Table",
    tab_timeline: "Timeline",
    tab_chart: "Chart",
    tooltip_allocation: "Allocation",
    vested_at_tge: "Vested at TGE",
    linear: "Linear",
  },
  ru: {
    // App
    no_report_selected: "Отчёт не выбран.",
    failed_load_report: "Не удалось загрузить отчёт.",
    portfolio_empty: "Портфолио пусто.",
    failed_load_portfolio: "Не удалось загрузить портфолио.",
    failed_compare: "Не удалось сравнить проекты.",
    section_overview: "Обзор",
    section_documentation: "Документация",
    section_risk_flags: "Риск-флаги",
    section_tokenomics: "Токеномика — Вестинг",
    section_funding: "Финансирование и инвесторы",
    section_team: "Команда",
    section_socials: "Соцсети",
    section_data_sources: "Источники данных",
    compare_title: "Сравнение",
    portfolio_title: "Портфолио",
    // ProjectCard
    strengths: "Сильные стороны",
    weaknesses: "Слабые стороны",
    market_cap: "Капитализация",
    // RiskFlags
    no_risk_flags: "Риск-флаги не обнаружены.",
    flag_cat_tokenomics: "Токеномика",
    flag_cat_team: "Команда",
    flag_cat_social: "Соцсети",
    flag_cat_investors: "Инвесторы",
    flag_cat_general: "Общее",
    // TeamVerification
    no_team_data: "Данные о команде не найдены.",
    all_members: "Все участники",
    // SocialAnalysis
    no_social_data: "Данные о соцсетях недоступны.",
    sentiment: "Тональность",
    tweets_analysed: "твитов проанализировано",
    followers: "подписчиков",
    engagement: "Вовлечённость",
    avg_views: "Сред. просмотры",
    following: "Подписки",
    top_posts: "Топ посты",
    positive_signals: "Позитивные сигналы",
    key_concerns: "Ключевые риски",
    kol_mentions: "Упоминания KOL",
    bot_activity_signals: "Сигналы бот-активности",
    // DocumentationAnalysis
    no_docs_data: "Данные о документации отсутствуют.",
    docs_not_found: "Документация не найдена:",
    docs_fallback_notice: "Документация не найдена — собрана общая информация с сайта проекта",
    key_features: "Ключевые функции",
    token_label: "Токен:",
    supply_label: "Предложение:",
    unusual_conditions: "Необычные условия",
    no_unusual_conditions: "Необычных условий не обнаружено",
    completeness_data: "данные",
    completeness_high: "Высокая",
    completeness_medium: "Средняя",
    completeness_low: "Низкая",
    // FundsList
    no_funding_data: "Данные о финансировании недоступны.",
    total_raised: "Всего привлечено",
    raised: "Привлечено",
    valuation: "Оценка",
    all_investors: "Все инвесторы",
    col_name: "Название",
    col_tier: "Уровень",
    col_type: "Тип",
    col_stage: "Стадия",
    lead_badge: "Лид",
    no_investor_data: "Нет данных об инвесторах",
    // FDV prediction
    predicted_val: "Прогн. FDV",
    conf_high: "Высок.",
    conf_medium: "Средн.",
    conf_low: "Низкая",
    fdv_range_label: "Диапазон",
    fdv_methodology_label: "Метод",
    // VestingChart
    no_vesting_data: "Данные о вестинге недоступны.",
    allocation: "Аллокация",
    max_supply: "Макс. предложение:",
    vesting_schedule: "График вестинга",
    col_recipient: "Получатель",
    col_total: "Всего",
    col_unlocked: "Разблокировано",
    col_locked: "Заблокировано",
    col_cliff: "Клифф",
    col_vesting: "Вестинг",
    today_label: "СЕГОДНЯ",
    timeline_unavailable: "Таймлайн недоступен — нет даты TGE в данных.",
    tab_table: "Таблица",
    tab_timeline: "Таймлайн",
    tab_chart: "График",
    tooltip_allocation: "Аллокация",
    vested_at_tge: "Разблокировано на TGE",
    linear: "Линейный",
  },
} as const;

type Keys = keyof typeof TR.en;

export function t(key: Keys, lang: Lang): string {
  return (TR[lang] as Record<Keys, string>)[key] ?? TR.en[key];
}

export function fmtPages(n: number, lang: Lang): string {
  if (lang === "ru") {
    if (n === 1) return "Проанализирована 1 страница";
    if (n >= 2 && n <= 4) return `Проанализировано ${n} страницы`;
    return `Проанализировано ${n} страниц`;
  }
  return `Analysed ${n} page${n !== 1 ? "s" : ""}`;
}

export function fmtProjectLinks(n: number, lang: Lang): string {
  return lang === "ru"
    ? `Ссылки проекта из документации (${n})`
    : `Project links from docs (${n})`;
}

export function fmtPagination(from: number, to: number, total: number, lang: Lang): string {
  return lang === "ru"
    ? `${from} – ${to} из ${total}`
    : `${from} – ${to} from ${total}`;
}

export function fmtMonthYear(date: Date, lang: Lang): string {
  return date.toLocaleDateString(lang === "ru" ? "ru-RU" : "en-US", {
    month: "short",
    year: "numeric",
  });
}
