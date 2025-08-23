JuicyFox Bot Platform 🦊
JuicyFox — это white-label бот-платформа для NSFW-проектов и сообществ.
Она реализует План A — модульную архитектуру с единым токеном и отдельными сервисами для платежей, подписок, истории и постинга.
Платформа поддерживает как многомодульный режим, так и сборку в монолит (juicyfox_bot_single.py) для упрощённого деплоя.
🚀 Установка
1. Клонирование репозитория
git clone https://github.com/your-org/juicyfox_bot.git
cd juicyfox_bot
2. Настройка окружения
Скопируйте шаблон .env.example:
cp .env.example .env
Заполните .env своими значениями:
TELEGRAM_TOKEN — токен бота;
VIP_CHANNEL_ID, CHAT_GROUP_ID, LIFE_CHANNEL_ID и др. — ID каналов и групп;
CRYPTOBOT_TOKEN — токен платежного провайдера (CryptoBot);
DB_PATH — путь к SQLite базе (по умолчанию /app/data/juicyfox.sqlite).
3. Установка зависимостей (локально)
pip install -r requirements.txt
Или соберите Docker-образ:
docker compose build
4. Запуск
Запустить API и воркеры можно так:
docker compose up -d
Или локально:
# API (FastAPI + aiogram webhook)
uvicorn apps.bot_core.main:app --host 0.0.0.0 --port 8000

# Worker для постинга
python worker_posting.py
🧩 Архитектура и модули
ui_membership — меню, платёжные кнопки, управление доступами.
payments — сервис инвойсов и нормализация вебхуков.
posting — планировщик и воркер отложенных постов.
chat_relay — пересылка сообщений в рабочую группу и ответы.
history — хранение и просмотр истории сообщений.
⚙️ Использование
Запуск возможен как локально, так и через Docker Compose.
Все параметры задаются через .env.
Для клонирования нового бота:
создайте копию .env с новыми значениями (например, BOT_ID, TELEGRAM_TOKEN);
используйте отдельный volume для базы данных.
📦 Монолитный режим
Для упрощённого деплоя можно собрать монолит:
python scripts/build_single.py
Он создаст файл juicyfox_bot_single.py, включающий все модули.
Запуск:
# API-режим
RUN_MODE=api python juicyfox_bot_single.py

# Worker-режим
RUN_MODE=worker python juicyfox_bot_single.py
🗄️ База данных
По умолчанию используется SQLite:
/app/data/juicyfox.sqlite
При необходимости можно перейти на PostgreSQL через Alembic-миграции (в будущем).
🛠️ План A vs Монолит
Plan A (модульный режим): каждый модуль работает как сервис, используется Docker Compose.
Монолит: всё собрано в juicyfox_bot_single.py, удобно для хостингов с ограниченными возможностями.

## 🧩 Архитектура и модули

- **ui_membership** — меню, платёжные кнопки, управление доступами.
- **payments** — сервис инвойсов и нормализация вебхуков.
- **posting** — планировщик и воркер отложенных постов.
- **chat_relay** — пересылка сообщений в рабочую группу и ответы.
- **history** — хранение и просмотр истории сообщений.

### 📂 Полная структура проекта

```plaintext
juicyfox/
├─ api/
│  ├─ webhook.py           # POST /bot/{bot_id}/webhook → aiogram Dispatcher
│  ├─ payments.py          # POST /payments/<provider> → normalize → events
│  └─ health.py            # /healthz, /readyz (и опц. /metrics)
│
├─ apps/
│  └─ bot_core/
│      ├─ main.py          # запуск FastAPI/uvicorn, инициализация Bot/DP
│      ├─ routers.py       # include_router(ui, posting, chat_relay, …)
│      ├─ state.py         # FSM: Post, Donate, ChatGift
│      └─ middleware.py    # логирование, rate-limit, error handler, tracing
│
├─ modules/
│  ├─ ui_membership/       # /start, меню, донат, VIP/чат
│  ├─ payments/            # сервис инвойсов, идемпотентность, провайдеры
│  ├─ posting/             # планировщик и worker для постинга
│  ├─ chat_relay/          # пересылка сообщений в группу
│  └─ history/             # архив/лог контента
│
├─ shared/
│  ├─ config/              # .env + YAML, алиасы, валидация
│  ├─ db/                  # repo, migrations (Alembic)
│  └─ utils/               # logging, time, idempotency, metrics
│
├─ configs/                # sample_bot.yaml
├─ scripts/                # provisioner.py, build_single.py, seed_demo.py
├─ worker_posting.py       # entrypoint: posting.worker
├─ docker/                 # Dockerfile, compose.yaml
├─ .env.example
├─ requirements.txt
├─ README.md
└─ alembic.ini
