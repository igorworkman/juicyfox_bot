# modules/common/shared.py

# Здесь будут все общие константы, классы и функции,
# которые нужны и боту, и UI-модулям.

# ✅ Константы
CURRENCIES = ["USD", "EUR", "RUB"]  # примеры, возьми реальные из juicyfox_bot_single.py
LIFE_URL = "https://example.com/life"  # замени на актуальное

# ✅ FSM-класс
from aiogram.fsm.state import StatesGroup, State

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
def tr(lang: str, key: str) -> str:
    """
    Простая функция перевода.
    Возьми оригинал из juicyfox_bot_single.py
    """
    translations = {
        "en": {"choose_action": "Choose action"},
        "ru": {"choose_action": "Выберите действие"},
    }
    return translations.get(lang, {}).get(key, key)

