from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES


def chat_tariffs_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "chat_flower_1"), callback_data="chatplan:10d")
    b.button(text=tr(lang, "chat_flower_2"), callback_data="chatplan:20d")
    b.button(text=tr(lang, "chat_flower_3"), callback_data="chatplan:30d")
    b.button(text=tr(lang, "btn_back"), callback_data="ui:back")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()


def chat_currency_kb(plan_code: str, lang: str | None = None) -> InlineKeyboardMarkup:
    """Keyboard for choosing payment currency for chat plans."""
    # REGION AI: add Stars option
    b = InlineKeyboardBuilder()
    stars_code = plan_code
    b.button(text="⭐ Stars", callback_data=f"pay_stars:{stars_code}")
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"paymem:{plan_code}:{code}")
    b.button(text=tr(lang or "en", "btn_back"), callback_data="ui:back")
    b.adjust(1, 2, 2, 2, 2, 1)
    return b.as_markup()
    # END REGION AI
