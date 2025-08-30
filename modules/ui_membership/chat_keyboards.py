from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from modules.common.i18n import tr

from modules.constants.currencies import CURRENCIES


def membership_currency_kb(plan_code: str, lang: str | None = None) -> InlineKeyboardMarkup:
    """Keyboard with payment currencies for a membership plan."""
    builder = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        builder.button(text=title, callback_data=f"paymem:{plan_code}:{code}")
    builder.button(text=tr(lang or "en", "btn_back"), callback_data="ui:back")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()



def chat_tariffs_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "chat_flower_1"), callback_data="chatplan:7d")
    b.button(text=tr(lang, "chat_flower_2"), callback_data="chatplan:15d")
    b.button(text=tr(lang, "chat_flower_3"), callback_data="chatplan:30d")
    b.button(text=tr(lang, "back"), callback_data="ui:back")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()

