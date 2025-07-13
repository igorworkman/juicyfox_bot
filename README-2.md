# JuicyFox Bot — NSFW Telegram бот на Python

## 📌 Назначение
JuicyFox Bot — это Telegram-бот, предназначенный для монетизации NSFW-контента через подписки, приватные каналы и криптовалютные оплаты. Проект реализован на Python с использованием `aiogram`, `CryptoBot API` и Telegram Bot API.

---

## ⚙️ Технологии
- Язык: Python 3.10+
- Фреймворк: aiogram
- Платёжная система: [CryptoBot API](https://docs.crypt.bot/)
- Хостинг: Railway (через webhook)
- Telegram Bot API (callback-кнопки, сообщения, доступ к каналам)

---

## 💼 Основной функционал
- Команда `/start` с выбором тарифов:
  - 👀 Juicy Life — $0
  - 🔓 luxaru room — $15
  - 👑 VIP Secret — $35
  - 💬 Juicy Chat
  - ❤️ Custom
- Обработка выбора тарифа через callback-кнопки
- Выбор валюты: 💵 USDT / 🔮 TON / ₿ BTC
- Создание инвойса через CryptoBot и выдача ссылки на оплату
- Автоматическая или ручная выдача доступа в каналы после оплаты
- Логика монолитная: один файл `juicyfox_bot_single.py` (на текущий момент)

---

## 🔐 Переменные окружения (.env)

```
TELEGRAM_TOKEN=ваш_токен_бота
CRYPTOBOT_TOKEN=ваш_токен_от_CryptoBot
VIP_CHANNEL_ID=-1001234567890
CHAT_GROUP_ID=-1002813332213
LIFE_CHANNEL_ID=-1002741506579
LOG_CHANNEL_ID=-1002828644255
LUXURY_CHANNEL_ID=-1002808420871
LIFE_URL=https://t.me/JuisyFoxOfficialLife
```

---

## 🚀 Планируемый деплой

Будет использоваться [Railway](https://railway.app/) в связке с webhook. Локальная разработка ведётся через polling, далее переключение на aiohttp-сервер.

---

## 🧠 Цель GPTs

В GPTs (NSFW Pyaton JFB) бот ведёт по шагам, контролирует каждую стадию разработки, не даёт новых задач до завершения текущих и работает как ассистент-разработчик, запоминая весь код проекта.

---

## 🧩 Текущий статус

На данный момент бот реализован в монолитном файле `juicyfox_bot_single.py`. В будущем планируется разбивка на модули (`bot.py`, `payments.py`, `access.py` и др.) для облегчения масштабирования и поддержки нескольких моделей.
