from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES


# ---------- INLINE КНОПКИ (стабильные callback'и) ----------

def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    """Главное меню: Life, Luxury, VIP, Donate, Chat."""
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "btn_life"), callback_data="ui:life")
    b.button(text=tr(lang, "btn_club"), callback_data="ui:luxury")
    b.button(text=tr(lang, "btn_vip"), callback_data="ui:vip")
    b.button(text=tr(lang, "btn_donate"), callback_data="donate")
    b.button(text=tr(lang, "btn_chat"), callback_data="ui:chat")
    b.adjust(2, 2, 1)
    return b.as_markup()


def vip_currency_kb(lang: str | None = None) -> InlineKeyboardMarkup:

    """Меню выбора валюты для VIP-подписки."""
    b = InlineKeyboardBuilder()
    if len(CURRENCIES) != 8:
        raise ValueError("CURRENCIES must contain exactly eight items")
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"vipay:{code}")
    b.button(text=tr(lang or "en", "btn_back"), callback_data="ui:back")
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup()


def luxury_currency_kb(lang: str | None = None) -> InlineKeyboardMarkup:

    """Меню выбора валюты для Luxury-подписки."""
    b = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"luxpay:{code}")
    b.button(text=tr(lang or "en", "btn_back"), callback_data="ui:back")
    b.adjust(3, 1)
    return b.as_markup()

def donate_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    """Выбор валюты для доната: donate:cur:<CODE> + Назад."""
    b = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"donate:cur:{code}")
    b.button(text=tr(lang or "en", "btn_back"), callback_data="donate:back")
    b.adjust(3, 1)
    return b.as_markup()


def donate_back_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang or "en", "btn_back"), callback_data="donate:back")
    return b.as_markup()


# ---------- REPLY-МЕНЮ (legacy/UX по желанию) ----------

def reply_menu(lang: str) -> ReplyKeyboardMarkup:
    """
    Лёгкое reply-меню на старый манер (тексты — из локалей).
    Можно показывать всегда — это не ломает inline-сценарии.
    """
    chat_label = tr(lang, "btn_chat")
    luxury_label = tr(lang, "btn_club")
    vip_label = tr(lang, "btn_vip")

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=chat_label)],
            [KeyboardButton(text=luxury_label), KeyboardButton(text=vip_label)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=tr(lang, "reply_placeholder"),
    )


