
import os
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
async def create_invoice(user_id: int, amount: int, currency: str, description: str):
    """
    Создание счёта для оплаты.
    Реализуй тут логику из juicyfox_bot_single.py
    """
    # пример:
    return f"INVOICE-{user_id}-{amount}-{currency}"

# ✅ Функция перевода
def tr(lang: str, key: str, **kwargs) -> str:
    """
    Простая функция перевода с поддержкой подстановки параметров.
    """
    translations = {
        "en": {"choose_action": "Choose action"},
        "ru": {"choose_action": "Выберите действие"},
    }
    text = translations.get(lang, {}).get(key, key)
    return text.format(**kwargs) if kwargs else text
