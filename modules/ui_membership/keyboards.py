from __future__ import annotations

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

from modules.common.shared import CURRENCIES, tr


# ---------- INLINE КНОПКИ (стабильные callback'и) ----------

def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    """Главное меню: VIP, Chat, Life, Donate."""
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang, "btn_vip") or "❤️‍🔥 VIP Secret", callback_data="ui:vip")
    b.button(text=tr(lang, "btn_chat") or "💬 Chat", callback_data="ui:chat")
    b.button(text=tr(lang, "btn_life") or "⭐️ Life", callback_data="ui:life")
    b.button(text=tr(lang, "btn_donate") or "💸 Donate", callback_data="donate")
    b.adjust(2, 2)
    return b.as_markup()


def vip_currency_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    """Экран VIP: даём кнопку оплаты (pay:vip) и Назад."""
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang or "en", "btn_pay_vip") or "Pay VIP", callback_data="pay:vip")
    b.button(text=tr(lang or "en", "btn_back") or "⬅️ Back", callback_data="ui:back")
    b.adjust(1)
    return b.as_markup()


def chat_plan_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    """Экран Chat: кнопка оплаты (pay:chat) и Назад."""
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang or "en", "btn_pay_chat") or "Pay Chat", callback_data="pay:chat")
    b.button(text=tr(lang or "en", "btn_back") or "⬅️ Back", callback_data="ui:back")
    b.adjust(1)
    return b.as_markup()


def donate_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    """Выбор валюты для доната: donate:cur:<CODE> + Назад."""
    b = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"donate:cur:{code}")
    b.button(text=tr(lang or "en", "btn_back") or "⬅️ Back", callback_data="donate:back")
    b.adjust(3, 1)
    return b.as_markup()


def donate_back_kb(lang: str | None = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=tr(lang or "en", "btn_back") or "⬅️ Back", callback_data="donate:back")
    return b.as_markup()


# ---------- REPLY-МЕНЮ (legacy/UX по желанию) ----------

def reply_menu(lang: str) -> ReplyKeyboardMarkup:
    """
    Лёгкое reply-меню на старый манер (тексты — из локалей).
    Можно показывать всегда — это не ломает inline-сценарии.
    """
    chat_label = tr(lang, "reply_chat_btn") or "SEE YOU MY CHAT💬"
    luxury_label = tr(lang, "reply_luxury_btn") or "💎 Luxury Room – 15$"
    vip_label = tr(lang, "reply_vip_btn") or "❤️‍🔥 VIP Secret – 35$"

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=chat_label)],
            [KeyboardButton(text=luxury_label)],
            [KeyboardButton(text=vip_label)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=tr(lang, "reply_placeholder") or "",
    )
    kb.adjust(1)
    return kb.as_markup()


def vip_currency_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"vipay:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()


def reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="SEE YOU MY CHAT💬")],
            [
                KeyboardButton(text="💎 Luxury Room – 15$"),
                KeyboardButton(text="❤️‍🔥 VIP Secret – 35$")
            ],
        ],
        resize_keyboard=True,
    )
