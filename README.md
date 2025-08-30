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


🐳 Docker
Сборка и запуск:
docker build -t juicyfox-bot .
docker run --rm -p ${PORT:-8080}:${PORT:-8080} juicyfox-bot  # Если PORT не задан, будет использоваться 8080



🐳 Docker
Сборка и запуск:
docker build -t juicyfox-bot .
docker run --rm -p ${PORT:-8080}:${PORT:-8080} juicyfox-bot  # Если PORT не задан, будет использоваться 8080


📂 Структура проекта

juicyfox/
1├─ api/
│  1.1├─ __init__.py
│  1.2├─ webhook.py           # POST /bot/{bot_id}/webhook → aiogram Dispatcher
│  1.3├─ payments.py          # POST /payments/<provider> → normalize → events
│  1.4└─ health.py            # /healthz, /readyz (и опц. /metrics)
│
2├─ apps/
│  2.1└─ bot_core/
│      2.1.1├─ __init__.py
│      2.1.2├─ main.py        # запуск FastAPI/uvicorn, инициализация Bot/DP
│      2.1.3├─ routers.py     # include_router(ui, posting, chat_relay, …)
│      2.1.4├─ state.py       # FSM: Post, Donate, ChatGift ——————————————————
│      2.1.5└─ middleware.py  # логирование, rate-limit, error handler, tracing
│
3├─ modules/
│  3.1├─ ui_membership/
│  │   3.1.1├─ __init__.py
│  │   3.1.2├─ handlers.py    # /start, меню, донат, VIP/чат, ссылки, “проверить доступ”
│  │   3.1.3└─ keyboards.py   # inline/reply-кнопки, namespace: ui:*, vip:*, chat:*
│  │
│  3.2├─ payments/
│  │   3.2.1├─ __init__.py
│  │   3.2.2├─ service.py     # create_invoice(), normalize_webhook(), идемпотентность
│  │   3.2.3└─ providers/
│  │        3.2.3.1├─ __init__.py
│  │        3.2.3.2└─ cryptobot.py
│  │
│  3.3├─ posting/
│  │   3.3.1├─ __init__.py
│  │   3.3.2├─ handlers.py    # планировщик → events(POST_SCHEDULED)
│  │   3.3.3└─ worker.py      # send-only воркер (читает events, шлёт, ретраи/backoff)
│  │
│  3.4├─ chat_relay/          # (опционально)
│  │   3.4.1├─ __init__.py
│  │   3.4.2└─ handlers.py    # пересылка в группу и обратно, модерация
│  │
│  3.5└─ history/             # (опционально)
│      3.5.1├─ __init__.py
│      3.5.2└─ handlers.py    # архив/лог контента, “последние N”
│
4├─ shared/
│  4.1├─ config/
│  │   4.1.1├─ __init__.py
│  │   4.1.2└─ env.py         # загрузка .env + YAML бота, алиасы, валидация
│  │
│  4.2├─ db/
│  │   4.2.1├─ __init__.py
│  │   4.2.2├─ repo.py        # Postgres/Redis, CRUD, events API (SKIP LOCKED)
│  │   4.2.3└─ migrations/    # Alembic (users, payments, subscriptions, memberships, posts, events)
│  │
│  4.3└─ utils/
│      4.3.1├─ __init__.py
│      4.3.2├─ logging.py     # логи: bot_id, module, corr_id
│      4.3.3├─ time.py
│      4.3.4├─ idempotency.py # ключи: provider:ext_id / post_id:run_at / user_id:channel
│      4.3.5└─ metrics.py     # (если нужны прометей-метрики)
│
5├─ configs/
│  5.1└─ bots/
│      5.1.1└─ sample_bot.yaml
│
6├─ scripts/
│  6.1├─ provisioner.py       # new-bot --bot-id bella --token ...
│  6.2├─ build_single.py      # склейка → juicyfox_bot_single.py
│  6.3└─ seed_demo.py
│
7├─ worker_posting.py         # entrypoint: from modules.posting.worker import main; main()
│
8├─ .github/
│  8.1└─ workflows/
│      8.1.1├─ ci.yml
│      8.1.2└─ deploy.yml
│
9├─ docker/
│  9.1├─ Dockerfile
│  9.2└─ compose.yaml
│
10├─ .env.example
11├─ requirements.txt
12├─ README.md
13└─ alembic.ini

🌐 Архитектура
FastAPI — HTTP API, точки входа /webhook, /payments, /healthz.
Aiogram 3 — обработка апдейтов Telegram.
Postgres / Redis (опционально) — для хранения состояния и кеша.
Docker — упаковка и деплой.
Northflank — хостинг и CI/CD.

🔧 Переменные окружения
Пример .env:

TELEGRAM_TOKEN=...
CRYPTO_BOT_TOKEN=...
BOT_ID=7248774167
BASE_URL=https://site--juicyfox-bot--fl4vz2vflbbx.code.run
WEBHOOK_URL=${BASE_URL}/webhook

📌 TODO / Roadmap
 Подключение Stripe / PayPal
 Расширение FSM (donate/chat gift)
 UI/UX оптимизация для membership
 Автоматизация логов и метрик





