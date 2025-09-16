from __future__ import annotations

# fix: correct Juicy Life channel link
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton

from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
# REGION: imports
from shared.config.env import config
# END REGION

# ---------- INLINE КНОПКИ (стабильные callback'и) ----------

def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    """Главное меню: Life, Luxury, VIP, Chat."""
    b = InlineKeyboardBuilder()
    # REGION AI: direct life channel link
    b.add(
        InlineKeyboardButton(
            text="JUICY LIFE 👀",
            url=config.life_url or "https://t.me/JuicyFoxOfficialLife",
        )
    )
    # END REGION AI
    # b.button(text=tr(lang, "btn_lux"), callback_data="ui:luxury")  # temporarily hidden
    # REGION AI: remove price from VIP button
    vip_label = tr(lang, "btn_vip").replace(" – ", " - ").split(" - ", 1)[0]
    b.button(text=vip_label, callback_data="ui:vip")
    # END REGION AI
    b.button(text=tr(lang, "btn_chat"), callback_data="ui:chat")
    b.button(text=tr(lang, "btn_donate"), callback_data="ui:donate")
    b.adjust(2, 2)
    return b.as_markup()


# REGION AI: stars in currency menu
def vip_currency_kb(lang: str | None = None) -> InlineKeyboardMarkup:

    """Меню выбора валюты для VIP-подписки."""
    b = InlineKeyboardBuilder()
    b.button(text="⭐ Stars", callback_data="pay_stars")
    if len(CURRENCIES) != 8:
        raise ValueError("CURRENCIES must contain exactly eight items")
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"vipay:{code}")
    b.button(text=tr(lang or "en", "btn_back"), callback_data="ui:back")
    b.adjust(1, 2, 2, 2, 2, 1)
    return b.as_markup()


def currency_menu(lang: str | None, prefix: str) -> InlineKeyboardMarkup:
    """Build currency menu based on VIP layout with custom prefix."""
    kb = vip_currency_kb(lang)
    for row in kb.inline_keyboard[:-1]:
        for btn in row:
            data = btn.callback_data or ""
            if data == "pay_stars":
                continue
            code = data.split(":", 1)[1] if ":" in data else data
            btn.callback_data = f"{prefix}{code}"
    back_btn = kb.inline_keyboard[-1][0]
    back_btn.callback_data = "donate:back" if prefix.startswith("donate") else "ui:back"
    return kb
# END REGION AI


def luxury_currency_kb(lang: str | None = None) -> InlineKeyboardMarkup:

    """Меню выбора валюты для Luxury-подписки."""
    b = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"luxpay:{code}")
    b.button(text=tr(lang or "en", "btn_back"), callback_data="ui:back")
    b.adjust(3, 1)
    return b.as_markup()


def donate_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="5$", callback_data="donate_5"),
             InlineKeyboardButton(text="10$", callback_data="donate_10"),
             InlineKeyboardButton(text="25$", callback_data="donate_25")],
            [InlineKeyboardButton(text="50$", callback_data="donate_50"),
             InlineKeyboardButton(text="100$", callback_data="donate_100"),
             InlineKeyboardButton(text="200$", callback_data="donate_200")],
            [InlineKeyboardButton(text="500$", callback_data="donate_500")],
            [InlineKeyboardButton(text=tr(lang or "en", "btn_back"), callback_data="ui:back")],
        ]
    )


def donate_currency_keyboard(lang: str | None = None) -> InlineKeyboardMarkup:
    # REGION AI: remove stars from donate menu
    b = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        b.button(text=title, callback_data=f"donate${code}")
    b.button(text=tr(lang or "en", "btn_back"), callback_data="donate_back")
    b.adjust(2, 2, 2, 2, 1)
    return b.as_markup()
    # END REGION AI


def _invoice_keyboard(lang, url: str, cancel_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=tr(lang, "btn_pay"), url=url)],
            [InlineKeyboardButton(text=tr(lang, "btn_cancel"), callback_data=cancel_data)],
        ]
    )


def donate_invoice_keyboard(lang, url: str) -> InlineKeyboardMarkup:
    return _invoice_keyboard(lang, url, "donate_cancel_invoice")


def vip_invoice_keyboard(lang, url: str) -> InlineKeyboardMarkup:
    return _invoice_keyboard(lang, url, "cancel")


def chat_invoice_keyboard(lang, url: str) -> InlineKeyboardMarkup:
    return _invoice_keyboard(lang, url, "cancel")

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
    # luxury_label = tr(lang, "btn_lux")  # temporarily hidden
    # REGION AI: remove price from VIP button
    vip_label = tr(lang, "btn_vip").replace(" – ", " - ").split(" - ", 1)[0]
    # END REGION AI
    donate_label = tr(lang, "btn_donate")

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=chat_label)],
            # [KeyboardButton(text=luxury_label), KeyboardButton(text=vip_label)],  # temporarily hidden
            [KeyboardButton(text=vip_label)],
            [KeyboardButton(text=donate_label)],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=tr(lang, "reply_placeholder"),
    )


