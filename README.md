# JuicyFox Bot

Telegram-бот для проекта JuicyFox.  
Архитектура построена на **FastAPI + aiogram3 (webhook mode)**.  
Сервис упакован в Docker, деплой на Northflank.  
Основной режим работы — многомодульный (Plan A).

---

## 🚀 Установка и запуск (локально)

```bash
git clone https://github.com/your-org/juicyfox-bot.git
cd juicyfox-bot

python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# Локальный запуск (dev)
uvicorn api.main:app --reload --port ${PORT:-8080}  # Если PORT не задан, будет использоваться 8080

# Продакшн (Docker / Northflank)
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}  # Использует переменную PORT или 8080 по умолчанию
```

🐳 **Docker**  
Сборка и запуск:

```bash
docker build -t juicyfox-bot .
docker run --rm -p ${PORT:-8080}:${PORT:-8080} juicyfox-bot  # Если PORT не задан, будет использоваться 8080
```

---

## 📂 Структура проекта

```text
juicyfox/
1├─ api/
│  1.1├─ __init__.py
│  1.2├─ webhook.py           # POST /bot/{bot_id}/webhook → aiogram Dispatcher
│  1.3├─ payments.py          # POST /payments/<provider> → normalize → events
│  1.4├─ health.py            # /healthz, /readyz (и опц. /metrics)
│  1.5└─ check_logs.py        # просмотр логов сервиса
│
2├─ apps/
│  2.1└─ bot_core/
│     2.1.1├─ __init__.py
│     2.1.2├─ main.py        # запуск FastAPI/uvicorn, инициализация Bot/DP, webhook
│     2.1.3├─ routers.py     # include_router(ui, posting, chat_relay, access,…)
│     2.1.4├─ state.py       # FSM: Post, Donate, ChatGift
│     2.1.5└─ middleware.py  # логирование, rate‑limit, error handler, tracing
│
3├─ modules/
│  3.1├─ ui_membership/
│  │   3.1.1├─ __init__.py
│  │   3.1.2├─ handlers.py    # /start, меню, донат, VIP/чат, ссылки, “проверить доступ”
│  │   3.1.3├─ keyboards.py   # inline/reply‑кнопки (ui:*, vip:*, chat:*)
│  │   3.1.4├─ chat_handlers.py  # логика VIP/чат‑подписок (повышение/понижение статуса)
│  │   3.1.5└─ chat_keyboards.py # клавиатуры для VIP/чат, уровни доступа
│  │
│  3.2├─ payments/
│  │   3.2.1├─ __init__.py
│  │   3.2.2├─ service.py     # create_invoice(), normalize_webhook(), идемпотентность
│  │   3.2.3├─ handlers.py    # бизнес‑логика: начисления, обработка событий и планов
│  │   3.2.4└─ providers/
│  │       3.2.4.1├─ __init__.py
│  │       3.2.4.2└─ cryptobot.py # интеграция с CryptoBot API (платежи в USDT/TON)
│  │
│  3.3├─ posting/
│  │   3.3.1├─ __init__.py
│  │   3.3.2├─ handlers.py    # планировщик → events(POST_SCHEDULED)
│  │   3.3.3└─ worker.py      # send‑only воркер (читает events, шлёт, ретраи/backoff)
│  │
│  3.4├─ chat_relay/          # (опционально)
│  │   3.4.1├─ __init__.py
│  │   3.4.2└─ handlers.py    # пересылка в группу ↔ канал, модерация
│  │
│  3.5├─ history/             # (опционально)
│  │   3.5.1├─ __init__.py
│  │   3.5.2└─ handlers.py    # архив/лог контента, “последние N”
│  │
│  3.6├─ access/
│  │   3.6.1└─ __init__.py    # mapping событий платежей → планы подписок (VIP/Chat)
│  │
│  3.7├─ constants/
│  │   3.7.1├─ __init__.py
│  │   3.7.2├─ currencies.py  # коды валют для платежей (USDT, TON…)
│  │   3.7.3└─ prices.py      # прайс‑планы: VIP, chat
│  │
│  3.8├─ common/
│  │   3.8.1├─ __init__.py
│  │   3.8.2├─ i18n.py        # загрузка локалей JSON и функция tr() для переводов
│  │   3.8.3└─ shared.py      # общие вспомогательные функции, типы состояний
│  │
│  └─ (другие модули)
│
4├─ shared/
│  4.1├─ config/
│  │   4.1.1├─ __init__.py
│  │   4.1.2└─ env.py         # загрузка .env + YAML, алиасы, валидация
│  │
│  4.2├─ db/
│  │   4.2.1├─ __init__.py
│  │   4.2.2├─ repo.py        # Postgres/Redis, CRUD, events API (SKIP LOCKED)
│  │   4.2.3└─ migrations/    # Alembic (users, payments, subscriptions, posts, events)
│  │
│  4.3└─ utils/
│     4.3.1├─ __init__.py
│     4.3.2├─ logging.py     # структурированные логи: bot_id, module, corr_id
│     4.3.3├─ time.py        # работа с таймштампами и таймзонами
│     4.3.4├─ idempotency.py # идемпотентные ключи для событий/платежей
│     4.3.5├─ metrics.py     # метрики (Prometheus)
│     4.3.6├─ lang.py        # определение языка пользователя (ru/en)
│     4.3.7└─ l10n.py        # алиас на tr() для удобства импорта
│
5├─ configs/
│  5.1└─ bots/
│     5.1.1└─ sample_bot.yaml # пример конфигурации бота (token, url, варианты модулей)
│
6├─ scripts/
│  6.1├─ provisioner.py       # new-bot --bot-id bella --token … (создание бота и настроек)
│  6.2├─ build_single.py      # склейка → juicyfox_bot_single.py (single-file build)
│  6.3└─ seed_demo.py         # демо‑данные для локального тестирования
│
7├─ data/
│  7.1└─ Start.py             # вспомогательные/тестовые данные
│
8├─ locales/                  # локализация UI
│  8.1├─ en.json
│  8.2├─ ru.json
│  8.3└─ es.json
│
9├─ common/
│  9.1└─ shared.py            # вспомогательные функции общего пользования (legacy)
│
10├─ docker/
│   10.1└─ compose.yaml       # multi-service deployment (API + worker)
│
11├─ .dockerignore
12├─ .env.example
13├─ .gitignore
14├─ .python-version
15├─ README.md               # этот файл (здесь показано актуальное дерево)
16├─ alembic.ini
17├─ requirements-dev.txt
18├─ requirements.txt
19├─ test_dummy.py
20├─ metrics.py
21└─ worker_posting.py         # entrypoint воркера постинга

```

---

## 🌐 Архитектура
- **FastAPI** — HTTP API: эндпоинты `/webhook`, `/payments`, `/healthz`.
- **Aiogram 3** — обработка апдейтов Telegram.
- **Postgres / Redis** (опционально) — хранение состояния и кеша.
- **Docker** — упаковка и деплой.
- **Northflank** — хостинг и CI/CD.

---

## 🔧 Переменные окружения

Пример `.env`:

```env
TELEGRAM_TOKEN=...
CRYPTO_BOT_TOKEN=...
BOT_ID=7248774167
BASE_URL=https://site--juicyfox-bot--fl4vz2vflbbx.code.run
WEBHOOK_URL=${BASE_URL}/webhook
```

---

## 📌 TODO / Roadmap
- Подключение Stripe / PayPal  
- Расширение FSM (donate/chat gift)  
- UI/UX оптимизация membership  
- Автоматизация логов и метрик  
