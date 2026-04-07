# Web3 Due Diligence Bot

Telegram-бот для автоматического анализа криптостартапов.

Пользователь отправляет название проекта → мультиагентный AI-пайплайн (~30–60 с) → карточка с оценкой 0–100 и флагами рисков.

## Быстрый старт

```bash
cp .env.example .env          # заполнить BOT_TOKEN, ANTHROPIC_API_KEY
docker-compose up -d postgres redis
cd bot && pip install -e . && alembic upgrade head
python -m src.main
```

## Тесты

```bash
cd bot && pytest tests/ -v
```

## Переменные окружения

| Переменная | Обязательная | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram Bot Token |
| `ANTHROPIC_API_KEY` | ✅ | Claude API key |
| `DATABASE_URL` | ✅ | `postgres+asyncpg://user:pass@postgres:5432/web3dd` |
| `REDIS_URL` | ✅ | `redis://redis:6379/0` |
| `WEBAPP_URL` | ✅ | URL Mini App (https://...) |
| `CRYPTORANK_API_KEY` | — | Не используется (заглушка) |
| `TWITTER_BEARER_TOKEN` | — | Не используется (заглушка) |

## Архитектура

```
Пользователь → /analyze <проект>
                    ↓
             orchestrator        ← определяет slug/URLs проекта
                    ↓
             dispatcher          ← параллельно запускает 4 агента:
               ├── aggregator    ← CoinGecko + CryptoRank API
               ├── documentation ← скрапинг Whitepaper/Gitbook + Claude
               ├── social        ← Twitter метрики
               └── team          ← верификация команды
                    ↓
             cross_check         ← перекрёстная верификация, генерация флагов
                    ↓
             analyst             ← скоринг (0–100) + итоговый отчёт
                    ↓
             Telegram-карточка + Mini App кнопка
```

## Скоринг

Итоговый балл = `int(formula_score × 0.7 + llm_score × 0.3)`, где `formula_score` складывается из:

| Категория | Макс. баллов |
|---|---|
| Tokenomics (FDV/MCap ratio) | 25 |
| Investors (Tier 1 фонды) | 25 |
| Team (верификация) | 25 |
| Social (подписчики + тональность) | 25 |

Штрафы: −5 за каждый red flag, −2 за yellow flag.
