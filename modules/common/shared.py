
import os
import json
import logging
import httpx
from aiogram.fsm.state import StatesGroup, State

# Здесь будут все общие константы, классы и функции,
# которые нужны и боту, и UI-модулям.

# ✅ Константы
# Список валют используется клавиатурами и хендлерами, поэтому
# каждая запись содержит отображаемый текст и код валюты.
CURRENCIES = [
    ("TON", "ton"),
    ("BTC", "btc"),
    ("USDT", "usdt"),
    ("ETH", "eth"),
]

# LIFE_URL теперь берётся из переменных окружения
# (если не задано в ENV, используется дефолтная ссылка)
LIFE_URL = os.getenv("LIFE_URL", "https://t.me/JuicyFoxOfficialLife")

CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "")
log = logging.getLogger(__name__)

# ✅ FSM-класс
class ChatGift(StatesGroup):
    plan = State()
    access = State()
    choose_tier = State()

# ✅ Утилиты
async def create_invoice(
    user_id: int,
    amount: int,
    currency: str,
    description: str,
    pl: str | None = None,
):
    """Создание инвойса через CryptoBot API."""
    if currency.lower() not in [code for _, code in CURRENCIES]:
        log.error("Unsupported currency: %s", currency)
        return None

    if not CRYPTOBOT_TOKEN:
        log.error("CRYPTOBOT_TOKEN is not set")
        return None

    payload_str = f"{user_id}:{pl}" if pl else str(user_id)
    url = "https://pay.crypt.bot/api/createInvoice"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {CRYPTOBOT_TOKEN}"},
                json={
                    "asset": currency.upper(),
                    "amount": amount,
                    "description": description,
                    "payload": payload_str,
                },
            )
        data = await resp.json()
    except Exception as e:
        log.exception("CryptoBot request failed: %s", e)
        return None

    if not data.get("ok"):
        log.error("CryptoBot error: %s", data)
        return None

    log.info("Invoice created for user %s: %s %s", user_id, amount, currency)
    return data["result"]["pay_url"]

# ✅ Функция перевода
LOCALES = {}
for lang in ["ru", "en", "es"]:
    try:
        with open(f"locales/{lang}.json", "r", encoding="utf-8") as f:
            LOCALES[lang] = json.load(f)
    except FileNotFoundError:
        LOCALES[lang] = {}


def tr(lang: str, key: str, **kwargs) -> str:
    text = LOCALES.get(lang, {}).get(key, key)
    return text.format(**kwargs) if kwargs else text
