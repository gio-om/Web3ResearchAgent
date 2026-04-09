# Web3 Due Diligence Bot

Telegram-бот для автоматического анализа криптостартапов.

Пользователь отправляет название проекта → мультиагентный AI-пайплайн (~30–60 с) → карточка с оценкой 0–100 и флагами рисков.

## Быстрый старт

```bash
cp .env.example .env          # заполнить BOT_TOKEN, ANTHROPIC_API_KEY (или OPENAI_API_KEY)
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
| `DATABASE_URL` | ✅ | `postgres+asyncpg://user:pass@postgres:5432/web3dd` |
| `REDIS_URL` | ✅ | `redis://redis:6379/0` |
| `WEBAPP_URL` | ✅ | URL Mini App (https://...) |
| `LLM_PROVIDER` | — | `claude` (по умолчанию) или `openai` |
| `ANTHROPIC_API_KEY` | ✅ если `LLM_PROVIDER=claude` | Claude API key (или orcai.cc key) |
| `ANTHROPIC_BASE_URL` | — | Прокси-URL (напр. `https://api.orcai.cc`). Если пустой — используется официальный SDK |
| `CLAUDE_MODEL` | — | Модель Claude (по умолч. `claude-sonnet-4-20250514`) |
| `OPENAI_API_KEY` | ✅ если `LLM_PROVIDER=openai` | OpenAI API key (или orcai.cc key) |
| `OPENAI_BASE_URL` | — | OpenAI-совместимый прокси (по умолч. `https://api.openai.com`) |
| `OPENAI_MODEL` | — | Модель OpenAI (по умолч. `gpt-4o`) |
| `CRYPTORANK_BEARER` | — | Bearer-токен из DevTools → Network → api.cryptorank.io |
| `TWITTER_BEARER_TOKEN` | — | Не используется (заглушка) |

### Выбор LLM-провайдера

В `.env` выставить `LLM_PROVIDER`:

```env
# Claude через orcai.cc прокси
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=cr_...
ANTHROPIC_BASE_URL=https://api.orcai.cc
CLAUDE_MODEL=claude-3-5-sonnet-20241022

# OpenAI-совместимый (orcai.cc или api.openai.com)
LLM_PROVIDER=openai
OPENAI_API_KEY=cr_...
OPENAI_BASE_URL=https://api.orcai.cc
OPENAI_MODEL=gpt-5.1-codex
```

Оба провайдера поддерживают одинаковый набор методов (`LLMService`). OpenAI-путь использует SSE-стриминг и поддерживает reasoning-модели (собирает `reasoning_content` из чанков, если `content` пустой).

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
