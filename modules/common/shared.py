import os
import json
from aiogram.fsm.state import StatesGroup, State

"""Shared helpers used by bot and UI modules."""

# Константы и платежи берём из обновлённых модулей
from modules.constants.currencies import CURRENCIES
from modules.payments import create_invoice

# LIFE_URL теперь берётся из переменных окружения
# (если не задано в ENV, используется дефолтная ссылка)
LIFE_URL = os.getenv("LIFE_URL", "https://t.me/JuicyFoxOfficialLife")

# ✅ FSM-класс
class ChatGift(StatesGroup):
    plan = State()
    access = State()
    choose_tier = State()

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
