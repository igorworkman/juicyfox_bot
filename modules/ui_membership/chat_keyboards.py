from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from modules.common.i18n import tr


def chat_tariffs_kb(lang: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "chat_flower_1"), callback_data="chatplan:7d")
    b.button(text=tr(lang, "chat_flower_2"), callback_data="chatplan:15d")
    b.button(text=tr(lang, "chat_flower_3"), callback_data="chatplan:30d")
    b.button(text=tr(lang, "back"), callback_data="ui:back")
    b.adjust(1, 1, 1, 1)
    return b.as_markup()
