# Web3 Due Diligence Bot

Telegram-бот для автоматического анализа криптостартапов на основе мультиагентного AI-пайплайна (LangGraph).

Пользователь отправляет название проекта → 6 агентов работают параллельно (~30–60 с) → карточка с оценкой 0–100, флагами рисков и кнопкой Mini App.

## Быстрый старт

```bash
cp .env.example .env          # заполнить секреты (см. раздел "Переменные окружения")
docker-compose up -d          # поднять postgres, redis, omniroute, ngrok, mini-app, bot
```

Первый запуск: контейнер бота автоматически применяет миграции Alembic и запускает бота + FastAPI-сервер.

Для локальной разработки без Docker:

```bash
cd bot
pip install -e ".[dev]"
alembic upgrade head
python -m src.main
```

## Архитектура

```
Пользователь → /analyze <проект>
                    ↓
             orchestrator       — нормализует имя/slug, определяет URL проекта
                    ↓
             dispatcher         — параллельно запускает 4 агента (timeout 60 с):
               ├── aggregator   — CryptoRank + CoinGecko: рынок, инвесторы, вестинг
               ├── documentation— BFS-скрапинг документации (до 30 страниц) + Claude
               ├── social       — Twitter/X: профиль, твиты, упоминания + Claude
               └── team         — LinkedIn-поиск (Brave/Apify) + верификация
                    ↓
             cross_check        — перекрёстная проверка данных, генерация флагов
                    ↓
             analyst            — скоринг (0–100) + итоговый отчёт, сохранение в БД
                    ↓
             Telegram-карточка + кнопка Mini App
```

Агент `graph.py` (LangGraph `StateGraph`) управляет всем флоу и шлёт live-прогресс в Telegram через `push_step()`.

### Режимы анализа

При вызове `/analyze <проект>` пользователь выбирает режим:

| Режим | Агенты | Когда использовать |
|---|---|---|
| `full` | все 4 параллельных агента | полный due diligence |
| `market` | только aggregator | быстрые рыночные данные |
| `docs` | aggregator + documentation | анализ документации |
| `social` | aggregator + social | проверка соцсетей |
| `team` | aggregator + team | верификация команды |

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram Bot Token ([@BotFather](https://t.me/BotFather)) |
| `DATABASE_URL` | ✅ | `postgres+asyncpg://user:pass@postgres:5432/web3dd` |
| `REDIS_URL` | ✅ | `redis://redis:6379/0` |
| `WEBAPP_URL` | ✅ | Публичный HTTPS URL Mini App (ngrok или хост) |
| `OPENAI_API_KEY` | ✅ | API-ключ для OmniRoute (роутер LLM-запросов) |
| `OPENAI_MODEL` | — | Модель по умолчанию в OmniRoute (пример: `claude-3-7-sonnet`) |
| `OPENAI_BASE_URL` | — | OmniRoute endpoint (по умолч. `http://omniroute:20128/v1`) |
| `CRYPTORANK_BEARER` | — | Bearer-токен: DevTools → Network → `api.cryptorank.io` |
| `TWITTER_BEARER_TOKEN` | — | Bearer-токен X/Twitter: DevTools → Network → `api.x.com` |
| `TWITTER_AUTH_COOKIE` | — | Cookie `auth_token` из браузера (нужен, если X требует логин) |
| `BRAVE_API_KEY` | — | Brave Search API key (поиск LinkedIn для команды) |
| `APIFY_TOKEN` | — | Apify token (альтернативный LinkedIn-скрапер) |
| `NGROK_AUTHTOKEN` | — | Ngrok token для публичного туннеля (Mini App) |

### LLM через OmniRoute

Бот использует **OmniRoute** — OpenAI-совместимый LLM-роутер, который работает как отдельный контейнер. Все агенты обращаются к нему через `OPENAI_BASE_URL`. OmniRoute сам маршрутизирует запросы к нужной модели (Claude, GPT, GLM и т.д.).

```env
OPENAI_API_KEY=<ключ для OmniRoute>
OPENAI_BASE_URL=http://omniroute:20128/v1
OPENAI_MODEL=claude-3-7-sonnet   # модель, доступная в вашем OmniRoute
```

## Скоринг

```
overall_score = int(formula_score × 0.7 + llm_score × 0.3)
formula_score = Σ subscores − penalties
```

| Категория | Макс. баллов | Критерий |
|---|---|---|
| Tokenomics | 25 | FDV/MCap ratio, аллокация на команду |
| Investors | 25 | Tier-1 фонды (a16z, Paradigm, Sequoia…), раунды |
| Team | 25 | Верификация LinkedIn, опыт в Tier-1 компаниях |
| Social | 25 | Подписчики, engagement, KOL-упоминания, тональность |

Штрафы: **−5** за красный флаг, **−2** за жёлтый.

LLM-оценка (0–100) — Claude анализирует все данные и ставит финальное суждение.

Рекомендации: `Strong` (80+) · `Interesting` (60–79) · `DYOR` (40–59) · `Avoid` (< 40)

## API-интеграции

| API | Авторизация | Назначение |
|---|---|---|
| **CryptoRank** | Bearer из DevTools | Рыночные данные, раунды, инвесторы, вестинг |
| **CoinGecko** | Без ключа (free tier) | MCap, FDV, цена, supply |
| **Twitter/X** | Bearer + auth cookie из браузера | Профиль, твиты, упоминания |
| **Brave Search** | API key | Поиск LinkedIn-профилей команды |
| **Apify** | Token | LinkedIn-скрапинг (альтернатива Brave) |
| **OmniRoute** | OPENAI_API_KEY | Роутинг к LLM (Claude, GPT, …) |

> **Внимание:** Bearer-токены CryptoRank и Twitter/X истекают. При ошибках авторизации — обновите их в `.env` вручную через DevTools браузера.

## Mini App

Фронтенд на **React 18 + TypeScript + Vite + Tailwind CSS v4**.

Компоненты: `ScoreGauge`, `TokenDistribution` (recharts), `RiskFlags`, `FundsList`, `TeamVerification`, `DocumentationAnalysis`, `ProjectLinks`, `PortfolioView`.

Маршруты (URLSearchParams):
- `?report_id=N` — просмотр отчёта
- `?view=portfolio&user_id=N` — портфолио пользователя

## Структура проекта

```
web3-dd-bot/
├── bot/
│   ├── src/
│   │   ├── agents/           # orchestrator, aggregator, documentation,
│   │   │                     # social, team, cross_check, analyst, graph
│   │   ├── services/         # llm, coingecko, cryptorank, twitter,
│   │   │                     # scraper, search, apify_search, cache
│   │   ├── bot/              # handlers, keyboards, middlewares, i18n
│   │   ├── db/               # models, engine, repositories
│   │   ├── schemas/          # AgentState, ScoreCard, RiskFlag, …
│   │   └── main.py           # точка входа: бот + FastAPI
│   ├── tests/                # 52 теста (pytest-asyncio)
│   ├── alembic/              # миграции БД
│   └── pyproject.toml
├── mini-app/                 # React frontend
├── docker-compose.yml
├── .env.example
└── debug_documentation.py    # отладочный запуск агента docs
```

## Тесты

```bash
cd bot && pytest tests/ -v
```

52 теста покрывают: агенты (оркестратор, скоринг, cross-check), сервисы (LLM, CoinGecko, скрапер), Telegram-хендлеры.

## Отладка

Запустить только агент документации:

```bash
docker compose run --rm bot python /app/debug_documentation.py "ProjectName" \
  --docs https://docs.example.io --lang ru
```

## База данных

PostgreSQL 16. Таблицы: `users`, `projects`, `analysis_reports` (JSONB: `report_data`, `risk_flags`), `user_portfolio`, `api_cache`.

Миграции применяются автоматически при старте контейнера или вручную:

```bash
cd bot && alembic upgrade head
```
