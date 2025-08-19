
import os
import json
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

# ✅ FSM-класс
class ChatGift(StatesGroup):
    plan = State()
    access = State()

# ✅ Утилиты
async def create_invoice(
    user_id: int,
    amount: int,
    currency: str,
    description: str,
    pl: str | None = None,
):
    """Создание счёта для оплаты."""
    payload_str = f"{user_id}:{pl}" if pl else str(user_id)
    return f"INVOICE-{payload_str}-{amount}-{currency}"

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
