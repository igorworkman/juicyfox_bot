from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from juicyfox_bot_single import CURRENCIES, tr


def main_menu_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=tr(lang, "btn_life"), callback_data="life")
    kb.button(text=tr(lang, "btn_club"), callback_data="pay:club")
    kb.button(text=tr(lang, "btn_vip"), callback_data="pay:vip")
    kb.button(text=tr(lang, "btn_donate"), callback_data="donate")
    kb.button(text="💬 Chat", callback_data="pay:chat")
    kb.adjust(1)
    return kb.as_markup()


def donate_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"doncur:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()


def donate_back_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="don_back")
    kb.adjust(1)
    return kb.as_markup()


def chat_plan_kb(lang: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for key, days in [("chat_flower_1",7),("chat_flower_2",15),("chat_flower_3",30)]:
        kb.button(text=tr(lang, key), callback_data=f"chatgift:{days}")
    kb.button(text="⬅️ Назад", callback_data="back")
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
