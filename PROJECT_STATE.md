# PROJECT_STATE.md — Web3 Due Diligence Bot

> Документ для восстановления контекста в новой сессии.
> Актуален на: 2026-04-20
> Статус: **Фазы 1–6 завершены. Документация: полный редизайн (анализ всех страниц, а не только токеномики). Двуязычные статусы. Настройка кол-ва страниц в боте. Debug-скрипт через Docker.**

---

## Текущий статус

Всё работает. `twitter.py` — полностью реализован через Playwright + Bearer Token (аналогично CryptoRank). Заглушка удалена.

---

## Сессия 2026-04-20 — Редизайн анализа документации + настройки

### Что сделано

#### 1. Редизайн анализа документации (`documentation.py`, `scraper.py`)

**Было:** `scrape_tokenomics_pages` — BFS с фильтром по tokenomics-ключевым словам. Если вводная страница не содержала слова "tokenomics/vesting/supply" — возвращал 0 страниц.

**Стало:** `scrape_docs_pages` — BFS без фильтра, собирает все читаемые страницы. LLM-промпт переориентирован на выжимку самого интересного из документации (`project_description`, `key_features`, `unusual_conditions`).

```python
# Новый промпт — общее резюме, а не токеномика
DOCUMENTATION_PROMPT = """...
{
  "project_description": "<2-3 sentence summary>",
  "key_features": [...],
  "token_name", "token_symbol", "total_supply",
  "unusual_conditions": [...],
  "data_completeness": "high|medium|low"
}
"""
```

#### 2. Двуязычные статусы в боте

- `documentation.py` — `_STEPS` dict с ключами `"ru"`/`"en"`, хелпер `_step(key, lang)`
- `graph.py` — `_MODULE_LABEL`, `_HEADER`, `_FORMING` — dict-of-dicts с RU/EN вариантами; `lang` хранится в `_progress`

#### 3. Настройка максимального числа страниц документации

Новая настройка в боте (по образцу social settings): кнопки **10 / 30 / 50 / своё**, по умолчанию **30**.

| Файл | Изменение |
|---|---|
| `bot/src/bot/keyboards.py` | `docs_settings_keyboard(lang, max_pages)` + кнопка в `settings_keyboard` |
| `bot/src/bot/i18n.py` | `docs_settings_menu`, `docs_pages_saved`, `enter_docs_pages`, `btn_docs_settings` (RU + EN) |
| `bot/src/bot/handlers/start.py` | `DocsSettingsStates`, `cb_settings_docs`, `cb_docs_pages`, `msg_custom_docs_pages` |
| `bot/src/agents/documentation.py` | Читает `state["user_settings"]["docs_max_pages"]` → передаёт в `scrape_docs_pages(max_pages=...)` |

#### 4. Debug-скрипт `debug_documentation.py`

Файл в `web3-dd-bot/` (не в `bot/`). Стабит Redis и `push_step`, принимает аргументы `<project_name> [--docs <url>] [--lang ru|en]`. Запускается через Docker:

```bash
docker compose run --rm debug python /app/debug_documentation.py "Pixie Chess" --docs https://...
```

Добавлен сервис `debug` в `docker-compose.yml` с `profiles: ["debug"]` и bind-mount `./debug_documentation.py:/app/debug_documentation.py:ro`.

#### 5. Фильтрация медиа-ссылок в scraper'е

`_collect_internal_links` теперь пропускает URL с расширениями `.png .jpg .svg .gif .webp .ico .pdf .woff .mp4` и др. — не делает лишних HTTP-запросов.

#### 6. Сбор внешних (официальных) ссылок из документации

Во время BFS-кролла каждая страница анализируется на внешние ссылки → сохраняются в `ScrapedPage.external_links: dict[str, str]`. В `documentation_node` они мёрджатся в `documentation_data["project_links"]`. В `analyst.py` добавляются в `report["project_links"]` (не перезаписывая уже известные).

Полезно для страниц "Official Links" — автоматически находит Twitter, Discord, Telegram и т.д.

#### 7. mini-app: компонент `DocumentationAnalysis.tsx`

Полный рерайт компонента: docs link + completeness badge сверху, затем `project_description`, `key_features` буллет-листом, token info, счётчик страниц, unusual conditions.

Добавлены поля `project_description?: string | null` и `key_features?: string[]` в `DocumentationInfo` (`types/index.ts`).

### Изменённые файлы (сессия 2026-04-20)

| Файл | Изменение |
|---|---|
| `bot/src/agents/documentation.py` | Новый промпт, `scrape_docs_pages`, билингвальные статусы, чтение `docs_max_pages`, сохранение `project_links` |
| `bot/src/agents/graph.py` | `_MODULE_LABEL`/`_HEADER`/`_FORMING` билингвальные; `lang` в `_progress` |
| `bot/src/agents/analyst.py` | `project_description`/`key_features` в `documentation`; мёрдж `project_links` из docs |
| `bot/src/services/scraper.py` | `scrape_docs_pages` (без фильтра); `_SKIP_EXTENSIONS`; `_collect_external_links`; `ScrapedPage.external_links` |
| `bot/src/bot/keyboards.py` | `docs_settings_keyboard`, кнопка в `settings_keyboard` |
| `bot/src/bot/i18n.py` | Тексты для docs settings (RU + EN) |
| `bot/src/bot/handlers/start.py` | `DocsSettingsStates` + 3 обработчика docs settings |
| `bot/src/config.py` | `extra = "ignore"` в `Settings.Config` |
| `docker-compose.yml` | Сервис `debug` с `profiles: ["debug"]` |
| `debug_documentation.py` | Новый файл — standalone debug runner |
| `mini-app/src/types/index.ts` | `project_description`, `key_features` в `DocumentationInfo` |
| `mini-app/src/components/DocumentationAnalysis.tsx` | Новый файл — полный рерайт компонента |

---

## Сессия 2026-04-15 — Все ссылки проекта в mini-app + SVG иконки

### Что сделано

#### 1. SVG иконки в ProjectLinks.tsx (коммит `ece884f`, частично предыдущий `6d11784`)
Заменены emoji/символы на настоящие inline SVG логотипы:
- **X (Twitter)** — официальный логотип X (диагональный крест), `text-gray-900`
- **Discord** — официальный логотип Discord (robot mask), `text-indigo-500`
- **CryptoRank** — кастомная SVG иконка с синим фоном и знаком "C>"
- Все остальные: Telegram, GitHub, LinkedIn, Medium, Reddit, YouTube — тоже SVG
- **Все кнопки**: `bg-white border border-gray-200 shadow-sm hover:bg-gray-50` (белый фон)

Добавлены иконки для новых типов ссылок: GitBook, Whitepaper, Blog, CoinMarketCap, CoinGecko, Linktree.

#### 2. Бот теперь собирает ВСЕ типы ссылок (не только 9 предопределённых)

**Проблема:** `_LINK_TYPES` в `cryptorank.py` и `_LINK_KEYS` в `analyst.py` содержали хардкодные списки из 9–10 типов — `gitbook`, `whitepaper`, `blog`, `coinmarketcap` и другие игнорировались.

**Файлы и изменения:**

| Файл | Изменение |
|---|---|
| `bot/src/services/cryptorank.py` | `_extract_links` — убран фильтр `t not in _LINK_TYPES`, теперь захватываются все типы; spread `**links` вместо `{k: links[k] for k in _LINK_TYPES if k in links}` в `search_project` и `get_project_details` |
| `bot/src/agents/aggregator.py` | Back-fill в `project_urls` теперь итерирует все ключи из `details` (кроме метаданных), убран импорт `_LINK_TYPES` |
| `bot/src/agents/resolve_urls.py` | Аналогично: итерирует `details.items()` вместо `_LINK_TYPES`, убран импорт `_LINK_TYPES` |
| `bot/src/agents/analyst.py` | `_LINK_KEYS` убран, заменён на `for key, url in project_urls.items()` — все ключи копируются в `project_links` |
| `mini-app/src/components/ProjectLinks.tsx` | Добавлены иконки + конфиг для: `gitbook`, `whitepaper`, `blog`, `coinmarketcap`, `coingecko`, `linktree`; расширен `LINK_ORDER` |

**Важно:** `_LINK_TYPES` в `cryptorank.py` **оставлен** — используется внешне как набор "приоритетных" соцсетей для back-fill в `social.py`. Это только документационный набор, не фильтр.

---

## Сессия 2026-04-14 — Twitter/X scraper (Playwright + Bearer Token)

### Что сделано

Заглушка `twitter.py` полностью заменена на реальный Playwright-скрапер. Паттерн аутентификации идентичен CryptoRank: токены копируются из браузера DevTools и хранятся в `.env`.

#### Изменённые файлы

| Файл | Изменение |
|---|---|
| `bot/src/services/twitter.py` | **Полная перепись** — Playwright headless Chromium, Bearer Token инъекция через `context.route()`, DOM-парсинг твитов |
| `bot/src/config.py` | Добавлено поле `TWITTER_AUTH_COOKIE: str = ""` |
| `bot/pyproject.toml` | Добавлена зависимость `playwright>=1.44.0` |
| `bot/Dockerfile` | Добавлен шаг `playwright install chromium --with-deps` |

#### Архитектура twitter.py

```
TwitterClient
├── find_project_account(project_name)
│     Перебирает handle-кандидаты (camelCase / underscore / lower),
│     навигирует x.com/{handle}, проверяет наличие [data-testid="UserName"]
│
├── get_profile(username)
│     Загружает x.com/{username}, парсит:
│       - display name, bio
│       - followers / following (из href="/username/followers")
│
├── get_recent_tweets(username, count=50)
│     Скроллит таймлайн (MAX_SCROLL_ROUNDS=6, пауза 1.8 с),
│     собирает article[data-testid="tweet"], парсит text + created_at + metrics
│
└── search_mentions(project_name, count=30)
      Навигирует x.com/search?q={name}&f=live,
      собирает твиты + author_username из href атрибутов
```

#### Аутентификация (из браузера DevTools)

- `TWITTER_BEARER_TOKEN` — значение заголовка `Authorization` из любого XHR-запроса к `api.x.com`. Инжектируется через Playwright `context.route()` во все запросы к `*.x.com` / `*.twitter.com`.
- `TWITTER_AUTH_COOKIE` — raw строка заголовка `Cookie` (например `auth_token=abc; ct0=xyz`). Парсится и добавляется как cookies в browser context через `context.add_cookies()`. Опционально — без него публичные профили скрапятся без аутентификации.

#### Особенности реализации

- Каждый вызов метода запускает и останавливает свой `async_playwright` + `browser` — без persistent пула (простота, без утечек).
- `playwright` импортируется лениво (`from playwright.async_api import async_playwright`) — если библиотека не установлена, ошибка проявится только при вызове.
- Все методы exception-safe: любое исключение логируется через structlog, метод возвращает `{}` / `[]`.
- Redis-кэш TTL 1800 с (30 мин) — одинаково для всех методов.
- `_parse_metric("1.2K")` → `1200`, `"2.5M"` → `2_500_000` — нормализация чисел из DOM.
- В Docker: `--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage` обязательны для Chromium внутри контейнера.

#### Как получить токены

1. Открыть `x.com` в браузере → F12 → Network → любой XHR-запрос к `api.x.com`
2. `TWITTER_BEARER_TOKEN` → Headers → Authorization (значение после слова "Bearer ")
3. `TWITTER_AUTH_COOKIE` → Headers → Cookie (вся строка целиком)
4. Вставить в `.env`, пересобрать: `docker compose up --build -d`

---

## Сессия 2026-04-09 — выбор LLM-провайдера (Claude / OpenAI)

### Что сделано

Добавлена поддержка OpenAI-совместимого API в качестве альтернативы Claude. Выбор провайдера — через `LLM_PROVIDER` в `.env`.

#### Изменённые файлы

| Файл | Изменение |
|---|---|
| `bot/src/config.py` | `LLM_PROVIDER: str = "claude"`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`; `ANTHROPIC_API_KEY` теперь опциональный |
| `bot/src/services/llm.py` | `_call_openai_httpx()` — SSE-стриминг; `LLMService.__init__` ветвится по провайдеру; fallback `reasoning_content` для codex/o-series моделей |
| `.env` | `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| `.env.example` | Аналогично `.env` |

#### Архитектура LLM-маршрутизации

```
LLM_PROVIDER=claude  →  ANTHROPIC_BASE_URL задан?
                           да  → raw httpx POST /v1/messages (orcai.cc proxy)
                           нет → официальный anthropic SDK

LLM_PROVIDER=openai  →  SSE-стриминг POST /v1/chat/completions
                           собирает delta.content (стандартные модели)
                           или delta.reasoning_content (codex/o-series)
```

#### Особенности OpenAI-пути

- Модель `gpt-5.1-codex` на orcai.cc возвращает ответ только через `reasoning_content` в SSE-чанках (`content: null` в non-streaming). Реализован SSE-парсер, который собирает оба поля и предпочитает `content`.
- `stream: True` — принудительно, т.к. orcai.cc игнорирует `stream: false` для codex-модели.

---

## Сессия 2026-04-05 (ночь) — очистка БД + диагностика подключения

### Что сделано
- Подтверждено: всё работает, Docker запущен, все контейнеры живы
- Очищены таблицы `analysis_reports`, `projects`, `user_portfolio` (TRUNCATE CASCADE)
- `users` не тронуты

### Как подключаться к БД
```bash
# Правильное имя контейнера:
docker exec -it web3-dd-bot-postgres-1 psql -U web3dd -d web3dd

# Очистить отчёты (каскадно чистит projects и user_portfolio):
# TRUNCATE analysis_reports, projects RESTART IDENTITY CASCADE;
```
DBeaver не подключался — не тратить время, использовать psql напрямую.

---

## Сессия 2026-04-05 (вечер) — фикс белого экрана mini-app

### Причина

**Основной краш:** `FundsList.tsx:78` — обращение к `inv.portfolio_notable.length` без optional chaining.

Python `_build_investor_list` возвращает `{name: str, round: str}` — поле `portfolio_notable` отсутствует. При попытке `.length` на `undefined` React падал с unhandled exception → белый экран (без сообщения об ошибке).

### Все исправленные файлы

| Файл | Строка | Проблема | Фикс |
|---|---|---|---|
| `mini-app/src/components/FundsList.tsx` | 78 | `inv.portfolio_notable.length` → undefined | `inv.portfolio_notable?.length ?? 0` |
| `mini-app/src/components/ProjectCard.tsx` | 61, 76 | `report.strengths/weaknesses.length` → LLM может вернуть null | `?.length ?? 0` |
| `mini-app/src/components/TeamVerification.tsx` | 37 | `member.previous_projects.length` → поле может отсутствовать | `?.length ?? 0` |
| `mini-app/src/App.tsx` | 88–90 | `report.investors/funding_rounds/team` → null из БД | `?? []` на всех массивах при передаче в компоненты |
| `mini-app/src/App.tsx` | 97 | `report.data_sources.length` | `?.length ?? 0` |

### Добавлен React Error Boundary

В `App.tsx` добавлен `ErrorBoundary` компонент — теперь вместо белого экрана при render-ошибке показывается читаемое сообщение `Render error: <message>`. Это критично для диагностики будущих проблем.

```tsx
class ErrorBoundary extends Component<...> {
  static getDerivedStateFromError(error: Error) { return { error: error.message }; }
  render() {
    if (this.state.error) return <p>Render error: {this.state.error}</p>;
    return this.props.children;
  }
}

export default function App() {
  return <ErrorBoundary><Router /></ErrorBoundary>;
}
```

---

## Сессия 2026-04-05 (день) — CryptoRank API + отладка отчёта

### 1. CryptoRank — полный переход на прямые JSON API запросы

**Было:** HTML-скрапинг + парсинг `__NEXT_DATA__` (Next.js SSR). Работало только для 2 открытых раундов. Инвесторов не было.

**Стало:** Прямые запросы к `api.cryptorank.io` с Bearer токеном. Все 8+ раундов с именами инвесторов (a16z, Sequoia, Binance Labs и т.д.).

#### Эндпоинты (найдены через DevTools → Network → Fetch/XHR):

| Эндпоинт | Данные | Формат investors |
|---|---|---|
| `GET /v0/coins/{slug}` | Metadata монеты | — |
| `GET /v0/app/coins/{slug}/token-sales/exclusive/limited?sortBy=Date` | **Все раунды** (VC + IDO/IEO/Public) | `{tier1: [], tier2: [], tier3: []}` |
| `GET /v0/funding-rounds/with-investors/by-coin-key/{slug}` | Доп. раунды (дедупликация) | `[{type, name, slug, ...}]` |
| `GET /v0/coins/vesting/{slug}/exclusive` | Вестинг аллокации | `{"data": {"allocations": [...]}}` |

#### Аутентификация:
- Bearer токен из браузера DevTools → Network → любой XHR на api.cryptorank.io → заголовок Authorization
- Хранится в `.env` как `CRYPTORANK_BEARER=...`
- Добавлен в `config.py` как `CRYPTORANK_BEARER: str = ""`

#### Заголовки запроса (browser-like, из DevTools):
```python
{
    "Accept": "*/*",
    "Origin": "https://cryptorank.io",
    "Referer": "https://cryptorank.io/",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Authorization": f"Bearer {bearer}",
    ...
}
```

#### Особенности парсинга:
- `_extract_investor_names()` обрабатывает оба формата (tiered dict и flat list)
- Дедупликация раундов по ключу `{round_type}:{date}` при объединении двух эндпоинтов
- Инвесторы — plain strings: `["Andreessen Horowitz (a16z crypto)", "Paradigm", ...]`

**Файл:** `bot/src/services/cryptorank.py` — полностью переписан (убран весь HTML scraping).

---

### 2. analyst.py — исправления маппинга полей

#### Добавленные функции:

**`_build_tokenomics(documentation_data, cr_vesting)`**
- Мёрджит данные из documentation агента с вестингом из CryptoRank
- CryptoRank вестинг приоритетен для `vesting_schedules`
- Всегда возвращает dict (никогда None)

**`_build_funding_rounds(funding_rounds)`**
- Конвертирует `round_type` → `round_name` (mini-app TypeScript тип ожидает `round_name`)
- CryptoRank → `{round_type, date, amount_usd, ...}` → mini-app → `{round_name, date, amount_usd, ...}`

**`_build_investor_list(funding_rounds)`**
- Дедупликация инвесторов из всех раундов
- Формат: `[{name: str, round: str}]` ← **plain strings, не объекты с tier/portfolio_notable**

**Исправлен `_calculate_score`:**
- Investors теперь plain strings (не dict) → `if any(t in inv_name.lower() for t in TIER1_FUNDS)`

---

### 3. analyze.py — исправления

**`docs` режим теперь включает `aggregator`:**
```python
"docs": ["aggregator", "documentation"],  # aggregator нужен для вестинга и раундов
```

**`_fmt_usd()` — умное форматирование чисел:**
```python
# $100M / $1.23B / $500K правильно
```

---

### 4. mini-app — исправления форматирования (день)

**`ProjectCard.tsx` и `FundsList.tsx` — `formatUsd()`:**
```ts
if (value >= 1_000_000) return `$${Math.round(value / 1_000_000)}M`;
```

---

## Архитектурные решения (не менять)

1. **`StateGraph(dict)`** — агенты принимают и возвращают `dict`; `AgentState` используется только как начальный объект (`.model_dump()`).
2. **Плоская структура CoinGecko** — поля `fdv_usd`, `market_cap_usd`, `current_price_usd` на верхнем уровне в `aggregator_data["coingecko"]`.
3. **`ScrapedPage` dataclass** — доступ через `page.text_content`, не `page["text_content"]`.
4. **Singleton Redis** — `get_redis()` / `close_redis()` в `cache.py`.
5. **`coingecko_summary`** в `report` — `{fdv_usd, market_cap_usd}`, берётся из `aggregator_data["coingecko"]` в `analyst_node`.
6. **Investors в funding_rounds** — plain strings `["a16z", "Paradigm"]`, не объекты. `_calculate_score` использует `any(t in inv_name.lower() ...)`.
7. **CryptoRank Bearer токен** — копируется вручную из DevTools. Срок жизни неизвестен, при 401/403 обновлять в `.env` и перезапускать бот.
8. **`_build_investor_list` возвращает `{name, round}`** — без полей `tier`, `portfolio_notable`, `portfolio_notable`. Mini-app использует `?.` для доступа к необязательным полям.

---

## Структура `report` (выход `analyst_node`) — АКТУАЛЬНАЯ

```python
{
  "project_name": str,
  "project_slug": str,
  "overall_score": int,          # 0–100
  "recommendation": str,         # "DYOR"|"Interesting"|"Strong"|"Avoid"
  "scorecard": {
    "tokenomics_score": int,     # 0–25
    "investors_score": int,      # 0–25
    "team_score": int,           # 0–25
    "social_score": int,         # 0–25
    "overall_score": int,
  },
  "coingecko_summary": {"fdv_usd": float|None, "market_cap_usd": float|None},
  "tokenomics": {                # _build_tokenomics(documentation_data, cr_vesting)
    "vesting_schedules": [...],  # из CryptoRank /v0/coins/vesting/{slug}/exclusive
    # + всё из documentation_data (docs_url, scraped_pages, token_name, etc.)
  },
  "funding_rounds": [            # _build_funding_rounds(cr_funding_rounds)
    {"round_name", "date", "amount_usd", "valuation_usd"}
  ],
  "investors": [                 # _build_investor_list(cr_funding_rounds)
    {"name": str, "round": str}  # БЕЗ tier и portfolio_notable
  ],
  "team": [...],
  "social": {...},
  "risk_flags": [...],
  "strengths": [...],
  "weaknesses": [...],
  "summary": str,
  "data_sources": [...],         # ["Cryptorank", "CoinGecko", ...]
  "id": int,                     # db report id (добавляется ПОСЛЕ сохранения в БД)
}
```

---

## Как запустить после паузы

```bash
cd web3-dd-bot

# Пересобрать и запустить (нужно при изменении Python/TS кода):
docker compose up --build -d

# Только перезапустить (если образы актуальны):
docker compose up -d

# Логи бота в реальном времени:
docker compose logs -f bot

# Очистить Redis кэш (если нужны свежие данные от CryptoRank):
docker compose exec redis redis-cli FLUSHDB
```

---

## TODO / Известные проблемы

| Приоритет | Проблема | Файл | Статус |
|---|---|---|---|
| 🟡 MED | Bearer токен истекает — нет авто-обновления | `cryptorank.py`, `twitter.py` | Обновлять вручную из DevTools |
| 🟡 MED | `report_data` сохраняется в БД без поля `id` | `analyst.py` | Не мешает работе (id добавляется в state) |
| 🟡 MED | `twitter.py` — каждый вызов создаёт новый browser process | `services/twitter.py` | При высокой нагрузке оптимизировать через пул |
| 🟢 LOW | `docs` режим медленный (aggregator + docs) | `handlers/analyze.py` | Ожидаемо, не баг |
| 🟢 LOW | X может показывать логин-стену в headless режиме | `services/twitter.py` | Решается заполнением `TWITTER_AUTH_COOKIE` |

---

## Что построено

Telegram-бот + Mini App для автоматического анализа криптостартапов.
Пользователь отправляет название проекта → мультиагентный AI-пайплайн (~30–60 с) → карточка с оценкой 0–100 и флагами рисков.

**Стек:** Python 3.11, aiogram 3.x, LangGraph, Claude / OpenAI API (через orcai.cc proxy или напрямую), PostgreSQL 16 + asyncpg, Redis 7, SQLAlchemy 2.0 async, Alembic, Pydantic v2, FastAPI, Docker Compose.
Mini App: React 18 + Vite 5 + TypeScript + Tailwind CSS v4 + recharts.

**Корень проекта:** `web3-dd-bot/` (внутри рабочей папки `ResearchAgent/`)

---

## Фазы 1–6 — ЗАВЕРШЕНЫ

### Фаза 1 — Фундамент
- `docker-compose.yml` — postgres:16 + redis:7 + bot + mini-app + ngrok, health checks
- `bot/src/config.py` — `Settings(BaseSettings)`
- `bot/src/schemas/` — Pydantic-схемы + `AgentState`
- `bot/src/db/` — 5 таблиц ORM, репозитории, Alembic миграция

### Фаза 2 — Сервисы
- `cache.py` — Singleton Redis
- `llm.py` — `LLMService` (raw httpx, не SDK — orcai.cc блокирует SDK-заголовки)
- `coingecko.py` — плоская структура данных
- `scraper.py` — BFS-скрапер
- `cryptorank.py` — **✅ полностью реализован** (Bearer token, 4 эндпоинта API)
- `twitter.py` — **✅ полностью реализован** (Playwright + Bearer token, DOM-скрапинг)

### Фаза 3 — Агенты
Граф: `START → orchestrator → dispatcher → cross_check → analyst → END`

`dispatcher_node` запускает агентов через `asyncio.as_completed` с таймаутом 60с и live-обновлением Telegram-сообщения.

### Фаза 4 — Telegram-бот
- Режимы анализа: full / market / docs / social / team
- FSM для выбора режима
- Callbacks: `analyze_start`, `atype:{mode}`, `portfolio_add:{id}`, `reanalyze:{name}`

### Фаза 5 — Mini App
React SPA — роутинг через URLSearchParams: `?report_id=N`, `?view=portfolio&user_id=N`, `?compare=a,b`.
ErrorBoundary оборачивает весь роутер — render-ошибки показывают читаемое сообщение.

### Фаза 6 — Тесты
52 теста. Inline-импорты в агентах → патчи указывают на исходный модуль (`src.services.X`, не `src.agents.Y`).

---

## Карта изменённых файлов (все сессии)

| Файл | Что изменено |
|---|---|
| `bot/src/agents/documentation.py` | Новый промпт (общее резюме), `scrape_docs_pages`, билингвальные статусы, `docs_max_pages`, `project_links` (04-20) |
| `bot/src/agents/graph.py` | Билингвальные `_MODULE_LABEL`/`_HEADER`/`_FORMING`; `lang` в `_progress` (04-20) |
| `bot/src/agents/analyst.py` | `project_description`/`key_features` в `documentation`; мёрдж `project_links` из docs (04-20) |
| `bot/src/services/scraper.py` | `scrape_docs_pages`; `_SKIP_EXTENSIONS`; `_collect_external_links`; `ScrapedPage.external_links` (04-20) |
| `bot/src/bot/keyboards.py` | `docs_settings_keyboard`, кнопка в `settings_keyboard` (04-20) |
| `bot/src/bot/i18n.py` | Тексты docs settings RU+EN (04-20) |
| `bot/src/bot/handlers/start.py` | `DocsSettingsStates` + обработчики (04-20) |
| `bot/src/config.py` | `extra = "ignore"` (04-20) |
| `docker-compose.yml` | Сервис `debug` с `profiles: ["debug"]` (04-20) |
| `debug_documentation.py` | Новый файл — standalone debug runner (04-20) |
| `mini-app/src/types/index.ts` | `project_description`, `key_features` в `DocumentationInfo` (04-20) |
| `mini-app/src/components/DocumentationAnalysis.tsx` | Новый файл — полный рерайт (04-20) |
| `bot/src/services/twitter.py` | **Полная перепись** — Playwright + Bearer Token, DOM-скрапинг (сессия 2026-04-14) |
| `bot/src/services/cryptorank.py` | `_extract_links` захватывает все типы ссылок; `**links` spread вместо фильтра (04-15) |
| `bot/src/agents/aggregator.py` | Back-fill всех ключей из CryptoRank в `project_urls`, убран `_LINK_TYPES` (04-15) |
| `bot/src/agents/resolve_urls.py` | Итерирует все ключи `details`, убран `_LINK_TYPES` (04-15) |
| `bot/src/agents/analyst.py` | `_LINK_KEYS` → `for key, url in project_urls.items()` — копируются все ключи (04-15) |
| `mini-app/src/components/ProjectLinks.tsx` | **Перепись** — SVG иконки (X, Discord, CryptoRank, GitBook, CMC и др.), белый фон (04-15) |
| `bot/src/config.py` | `CRYPTORANK_BEARER`; `LLM_PROVIDER`, `OPENAI_*` (04-09); `TWITTER_AUTH_COOKIE` (04-14) |
| `bot/pyproject.toml` | `playwright>=1.44.0` (сессия 2026-04-14) |
| `bot/Dockerfile` | `playwright install chromium --with-deps` (сессия 2026-04-14) |
| `bot/src/services/cryptorank.py` | **Полная перепись** — Bearer API вместо HTML scraping |
| `.env` | `CRYPTORANK_BEARER`; `LLM_PROVIDER`, `OPENAI_*` (сессия 2026-04-09) |
| `.env.example` | `LLM_PROVIDER`, `OPENAI_*` (сессия 2026-04-09) |
| `bot/src/services/llm.py` | OpenAI SSE-провайдер, routing по `LLM_PROVIDER` (сессия 2026-04-09) |
| `bot/src/agents/analyst.py` | `_build_tokenomics`, `_build_funding_rounds`, `_build_investor_list`; fix investor string format |
| `bot/src/bot/handlers/analyze.py` | `docs` режим включает `aggregator`; `_fmt_usd()` умное форматирование |
| `mini-app/src/App.tsx` | ErrorBoundary; `?? []` для массивов; optional chaining для `data_sources` |
| `mini-app/src/components/ProjectCard.tsx` | `formatUsd` M/B/K; `?.length ?? 0` для strengths/weaknesses |
| `mini-app/src/components/FundsList.tsx` | `formatUsd` M/B/K; `inv.portfolio_notable?.length ?? 0` |
| `mini-app/src/components/TeamVerification.tsx` | `member.previous_projects?.length ?? 0` |
