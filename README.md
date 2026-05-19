# Web3 Due Diligence Bot

Мультиагентная система для автоматического due diligence криптовалютных проектов.  
Пользователь отправляет название проекта или ссылку в Telegram — бот за **~2 минуты** собирает данные из 5+ источников, верифицирует их и выдаёт структурированный отчёт с оценкой **0–100** и рекомендацией **Buy / Watch / Avoid**.

## Быстрый старт

```bash
cp .env.example .env          # заполнить секреты (см. раздел "Переменные окружения")
docker compose up -d          # поднять все 6 сервисов
```

Первый запуск: контейнер бота автоматически применяет миграции Alembic и запускает бота + FastAPI-сервер.

Для локальной разработки без Docker:

```bash
cd bot
pip install -e ".[dev]"
alembic upgrade head
python -m src.main
```

---

## Технический стек

| Слой | Технология |
|------|-----------|
| Граф агентов | LangGraph (StateGraph) |
| LLM | OmniRoute → GLM-5.1 (OpenAI-совместимый шлюз) |
| Telegram Bot | aiogram 3.x |
| REST API | FastAPI + uvicorn |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS v4 |
| База данных | PostgreSQL 16 (asyncpg + SQLAlchemy 2.0) |
| Кэш | Redis 7 (TTL 3600 с) |
| Браузерная автоматизация | Playwright |
| Скрейпинг LinkedIn | Apify actor `M2FMdjRVeF1HPGFcc` |
| Миграции | Alembic |
| Логирование | structlog |
| Оркестрация | Docker Compose (6 сервисов) |

---

## Архитектура

```
Пользователь Telegram
      │  /analyze LayerZero
      ▼
aiogram 3.x Bot ──► FSM (выбор режима) ──► FastAPI + React Mini App
      │
      ▼
LangGraph StateGraph
┌──────────────────────────────────────────────────────────────┐
│  orchestrator → dispatcher ──────────────► cross_check → analyst │
│                    │                                          │
│         aggregator · documentation · social · team            │
│                (параллельно, asyncio.as_completed)            │
└──────────────────────────────────────────────────────────────┘
      │
      ▼
PostgreSQL 16  +  Redis 7
```

Всё состояние — единый словарь `state: dict`, который каждый узел читает и дополняет.

---

## Узлы пайплайна

### 1. Orchestrator (`src/agents/orchestrator.py`)

Нормализует произвольный пользовательский ввод в `project_name + project_slug + project_urls`.

| Ввод | project_name | project_slug | project_urls |
|------|-------------|-------------|--------------|
| `"LayerZero"` | LayerZero | layerzero | `{}` |
| `cryptorank.io/price/layer-zero` | Layer Zero | layer-zero | `{cryptorank: url}` |
| `coingecko.com/en/coins/solana` | Solana | solana | `{}` |
| Ссылка на доку (задана пользователем) | — | — | `{docs: url}` |

Предустановленные пользователем URL имеют приоритет над автоопределёнными. Для простого текста slug строится через regex без LLM.

---

### 2. Dispatcher (`src/agents/graph.py`)

Параллельно запускает агентов-сборщиков и мержит результаты.

- Один раз резолвит проект в CryptoRank (чтобы агенты не дублировали запрос)
- Запускает активные модули через `asyncio.as_completed` с таймаутом **150 с** на агент
- По мере завершения каждого агента редактирует Telegram-сообщение с прогрессом:

```
🔍 Анализ проекта: LayerZero

✅ Сбор данных с агрегаторов...
⏳ Анализ документации...
   └ Читаю Whitepaper...
⏳ Проверка соцсетей...
⏳ Верификация команды...
```

При сбое или таймауте агента — ошибка фиксируется в `errors`, пайплайн продолжается.

---

### 3. Агенты-сборщики (параллельно)

| Агент | Файл | Источники | Что извлекает |
|-------|------|-----------|--------------|
| **Aggregator** | `agents/aggregator.py` | CryptoRank API + CoinGecko API | Цена, FDV, MCap, раунды финансирования, инвесторы с тирингом, вестинг-расписания |
| **Documentation** | `agents/documentation.py` | Playwright BFS-скрейпер (до 50 стр.) → LLM | vesting_months, cliff, TGE%, распределение токенов, описание проекта |
| **Social** | `agents/social.py` | Twitter/X (Playwright + Cookie) · Apify LinkedIn | followers, engagement_rate, sentiment_score, KOL-упоминания, bot_signals |
| **Team** | `agents/team.py` | Сайт проекта → LLM → Apify LinkedIn | Члены команды, verified, tier1_background, опыт |

**Fallback-цепочки:**

| Ситуация | Поведение |
|----------|----------|
| CryptoRank дневной лимит | `skip_cryptorank: True` → только CoinGecko |
| Whitepaper / документация недоступна | BFS-скрейпинг главного сайта проекта |
| LinkedIn URL не найден | Поиск по имени через Apify actor |

---

### 4. Cross-Check (`src/agents/cross_check.py`)

Верифицирует согласованность данных между источниками, генерирует риск-флаги.

| Проверка | Условие | Флаг |
|----------|---------|:----:|
| Расхождение supply | CryptoRank vs Whitepaper > 5% | RED |
| Короткий вестинг | Вестинг команды/фаундеров < 12 мес. | RED |
| Высокий TGE unlock | TGE > 20% для private/investors | YELLOW |
| Высокий ROI инвесторов | Текущая цена / цена раунда > 50x | YELLOW |
| Бот-аудитория | Engagement < 0.001 при > 50k followers | RED |
| Сигналы бот-активности | Паттерны в Twitter-анализе | YELLOW |
| Негативный сентимент | sentiment_score < -0.3 | RED |
| Позитивный сентимент | sentiment_score > 0.5 | GREEN |
| FDV/MCap экстремальный | ratio > 10x | RED |
| FDV/MCap высокий | ratio > 5x | YELLOW |
| Флаги из team_data | Передаются из агента Team | Наследуются |

Структура флага: `{ type, category, message, source, severity_score }`

---

### 5. Analyst (`src/agents/analyst.py`)

Синтезирует все данные в финальный отчёт, вычисляет оценку, сохраняет в БД.

#### Алгоритм скоринга

4 суб-оценки, каждая 0–25 баллов:

| Суб-оценка | Формула |
|-----------|---------|
| **Tokenomics** | FDV/MCap: < 3x → 22 · < 5x → 18 · < 10x → 12 · ≥ 10x → 6 |
| **Investors** | `min(25, 10 + tier1_count × 5)` · Tier-1: a16z, Paradigm, Sequoia, Binance Labs, Polychain, Multicoin, Pantera, Framework, Dragonfly |
| **Team** | `min(25, 10 + verified/total × 10 + tier1_bg × 2)` · без команды → 5 |
| **Social** | > 100k + eng > 1% → 22 · > 50k → 16 · > 10k → 12 · иначе → 6 · `+ sentiment×3 + min(kol,3)` |

Штрафы: RED флаг −5 · YELLOW флаг −2

```
formula_score = max(0, сумма суб-оценок − штрафы)
overall_score = int(formula_score × 0.70 + llm_score × 0.30)
```

| Оценка | Рекомендация |
|--------|-------------|
| ≥ 70 | Buy |
| 40–69 | Watch |
| < 40 | Avoid |

**Частичный режим:** если модуль не запускался, его суб-оценка берётся из предыдущего отчёта в БД. Повторный запуск отдельного модуля обогащает отчёт, не перезаписывает.

**FDV Prediction:** для раундов без `valuation_usd` LLM предсказывает FDV с `confidence`, `fdv_range_low/high_usd` и `methodology`.

---

## Режимы анализа

| Режим | Агенты | Назначение |
|-------|--------|-----------|
| `full` | aggregator + documentation + social + team | Полный анализ |
| `market` | aggregator | Быстрые рыночные данные |
| `docs` | aggregator + documentation | Токеномика и документация |
| `social` | social | Только соцсети |
| `team` | team | Только команда |

FSM-состояния: `choosing_mode → asking_docs_link → waiting_docs_url`  
и `asking_fdv_context → fdv_sector → fdv_comparable → fdv_confirm`

---

## Структура отчёта (JSON)

```json
{
  "project_name": "LayerZero",
  "overall_score": 74,
  "recommendation": "Buy",
  "scorecard": {
    "tokenomics_score": 18,
    "investors_score": 25,
    "team_score": 21,
    "social_score": 19
  },
  "risk_flags": [...],
  "strengths": [...],
  "weaknesses": [...],
  "summary": "...",
  "coingecko_summary": { "fdv_usd": ..., "market_cap_usd": ... },
  "funding_rounds": [...],
  "investors": [...],
  "tokenomics": { "vesting_schedules": [...], "token_distribution": {...} },
  "documentation": { "project_description": "...", "key_features": [...] },
  "social": {...},
  "team": [...],
  "data_sources": ["Cryptorank", "CoinGecko", "Twitter/X"],
  "project_links": { "website": "...", "twitter": "...", "cryptorank": "..." }
}
```

---

## Mini App

Фронтенд на **React 18 + TypeScript + Vite + Tailwind CSS v4**. Открывается кнопкой в сообщении бота.

| Компонент | Что показывает |
|-----------|---------------|
| `ScoreGauge` | Круговой SVG-индикатор 0–100, цвет по порогу |
| `TokenDistribution` | Диаграмма распределения токенов (Recharts) |
| `RiskFlags` | Флаги с severity-бейджами и фильтрами по категориям |
| `FundsList` | Таблица инвесторов с тирингом и ролью lead |
| `PortfolioView` | История анализов пользователя |

FastAPI-эндпоинты: `GET /api/report/{id}` · `GET /api/portfolio/{user_id}` · `POST /api/compare`

---

## Инфраструктура (Docker Compose)

| Сервис | Образ | Порт | Роль |
|--------|-------|:----:|------|
| `bot` | `./bot/Dockerfile` | 8080 | Python-бэкенд + FastAPI |
| `mini-app` | `./mini-app/Dockerfile` | 3000 | React SPA (nginx) |
| `omniroute` | `diegosouzapw/omniroute` | 20128 | LLM-шлюз (GLM-5.1) |
| `postgres` | `postgres:16-alpine` | 5433 | PostgreSQL + Alembic-миграции при старте |
| `redis` | `redis:7-alpine` | 6379 | Кэш API (TTL 3600 с) |
| `ngrok` | `ngrok/ngrok` | — | Публичный туннель для Mini App |

---

## База данных

PostgreSQL 16, 5 таблиц:

| Таблица | Ключевые поля |
|---------|--------------|
| `users` | `telegram_id`, `username`, `settings` (JSONB) |
| `projects` | `slug` (unique), `name`, `website_url`, `twitter_url`, `docs_url` |
| `analysis_reports` | `overall_score`, `recommendation`, `report_data` (JSONB), `risk_flags` (JSONB), `status` |
| `user_portfolio` | `user_id`, `project_id`, `notes` |
| `api_cache` | `cache_key`, `response_data` (JSONB), `expires_at` |

Миграции применяются автоматически при старте контейнера или вручную:

```bash
cd bot && alembic upgrade head
```

---

## Переменные окружения

| Переменная | Обязательная | Описание |
|-----------|:---:|---------|
| `BOT_TOKEN` | + | Telegram Bot Token ([@BotFather](https://t.me/BotFather)) |
| `DATABASE_URL` | + | `postgresql+asyncpg://web3dd:web3dd_secret@postgres:5432/web3dd` |
| `REDIS_URL` | + | `redis://redis:6379/0` |
| `WEBAPP_URL` | + | Публичный HTTPS URL Mini App (ngrok или хост) |
| `OMNIROUTE_API_KEY` | + | API-ключ для OmniRoute |
| `OMNIROUTE_BASE_URL` | — | OmniRoute endpoint (по умолч. `http://omniroute:20128/v1`) |
| `OMNIROUTE_MODEL` | — | Модель (по умолч. `glm/glm-5.1`) |
| `CRYPTORANK_BEARER` | — | Bearer-токен: DevTools → Network → `api.cryptorank.io` |
| `CRYPTORANK_COOKIE` | — | Cookie из браузера для CryptoRank |
| `TWITTER_AUTH_COOKIE` | — | Cookie `auth_token` из X.com DevTools |
| `APIFY_TOKEN` | — | Apify token для LinkedIn-скрейпинга |
| `NGROK_AUTHTOKEN` | — | Ngrok token для публичного туннеля |

> Bearer-токены CryptoRank и Twitter/X истекают. При ошибках авторизации — обновите их в `.env` вручную через DevTools браузера.

---

## API-интеграции

| API | Авторизация | Назначение |
|-----|-----------|-----------|
| **CryptoRank** | Bearer из DevTools | Рыночные данные, раунды, инвесторы, вестинг |
| **CoinGecko** | Без ключа (free tier) | MCap, FDV, цена, supply, история цены |
| **Twitter/X** | Bearer + auth cookie | Профиль, твиты, метрики, упоминания |
| **Apify** | Token | LinkedIn-скрейпинг команды |
| **OmniRoute** | OMNIROUTE_API_KEY | Роутинг LLM-запросов (GLM, Claude, GPT…) |

---

## Структура проекта

```
web3-dd-bot/
├── bot/
│   ├── src/
│   │   ├── agents/           # orchestrator, aggregator, documentation,
│   │   │                     # social, team, cross_check, analyst, graph
│   │   ├── services/         # llm, coingecko, cryptorank, twitter, scraper, apify
│   │   ├── bot/              # handlers, keyboards, middlewares, i18n
│   │   ├── db/               # models, engine, repositories
│   │   ├── schemas/          # AgentState, ScoreCard, RiskFlag
│   │   └── main.py           # точка входа: бот + FastAPI
│   ├── tests/                # 52 теста (pytest-asyncio)
│   ├── alembic/              # миграции БД
│   └── pyproject.toml
├── mini-app/                 # React frontend
├── docker-compose.yml
├── .env.example
└── debug_documentation.py   # отладочный запуск агента docs
```

---

## Тесты

```bash
cd bot && pytest tests/ -v
```

52 теста: агенты (оркестратор, скоринг, cross-check), сервисы (LLM, CoinGecko, скрейпер), Telegram-хэндлеры.

---

## Отладка

Запустить только агент документации:

```bash
docker compose run --rm bot python /app/debug_documentation.py "ProjectName" \
  --docs https://docs.example.io --lang ru
```
