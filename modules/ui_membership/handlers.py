from __future__ import annotations

import os
import logging
from typing import Any, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# текст/локализация и валюты берём из актуальных модулей
from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
from modules.constants.prices import VIP_PRICE_USD
from modules.constants.paths import START_PHOTO
from modules.payments import create_invoice
from shared.utils.lang import get_lang

log = logging.getLogger("juicyfox.ui_membership.handlers")

# Клавиатуры текущего модуля
from .keyboards import (
    main_menu_kb,
    reply_menu,
    vip_currency_kb,
    donate_keyboard,
    donate_currency_keyboard,
)
from .chat_keyboards import chat_tariffs_kb
from .chat_handlers import router as chat_router
from .utils import BOT_ID, _build_meta

router = Router()
router.include_router(chat_router)

# --- Конфиг из ENV (позже переедет в shared.config.env) ---
VIP_URL = os.getenv("VIP_URL")
LIFE_URL = os.getenv("LIFE_URL")

# Набор доступных кодов активов (например, "USDT", "BTC")
CURRENCY_CODES = {code.upper() for _, code in CURRENCIES}


# --- FSM для донатов (оставляем в UI-модуле) ---
class Donate(StatesGroup):
    choosing_currency = State()
    entering_amount = State()
    confirm = State()


# =======================
# /start и главное меню
# =======================
@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = get_lang(message.from_user)
    if START_PHOTO.exists():
        photo = FSInputFile(START_PHOTO)
    else:
        photo = "https://files.catbox.moe/cqckle.jpg"
    await message.answer_photo(
        photo,
        caption=tr(lang, "menu", name=message.from_user.first_name),
    )
    if LIFE_URL:
        await message.answer(
            tr(lang, "my_channel", link=LIFE_URL),
            reply_markup=reply_menu(lang),
        )
    else:
        await message.answer(
            tr(lang, "choose_action"),
            reply_markup=reply_menu(lang),
        )
    await message.answer(
        tr(lang, "choose_action"),
        reply_markup=main_menu_kb(lang),
    )


@router.callback_query(F.data.in_({"ui:back", "back_to_main", "back"}))
async def back_to_main(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "choose_action"),
        reply_markup=main_menu_kb(lang)
    )


# =======================
# VIP / Chat / Life
# =======================
@router.callback_query(F.data.in_({"ui:vip", "vip"}))
async def show_vip(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(tr(lang, "vip_club_description"), reply_markup=vip_currency_kb(lang))


@router.message(Command("currency"))
async def cmd_currency(message: Message) -> None:
    """Show currency menu for VIP subscription."""
    lang = get_lang(message.from_user)
    await message.answer(
        tr(lang, "choose_cur", amount=VIP_PRICE_USD),
        reply_markup=vip_currency_kb(lang),
    )


@router.callback_query(F.data.in_({"ui:life", "life"}))
async def show_life_link(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    if not LIFE_URL:
        await cq.answer(tr(lang, "link_is_missing"), show_alert=True)
        return
    await cq.message.answer(tr(lang, "life_room_link"))
    await cq.message.answer(LIFE_URL)


# =======================
# Оплата подписок (VIP/Chat)
# =======================

def _invoice_url(inv: Any) -> Optional[str]:
    """Поддерживаем и dict с 'pay_url', и просто строку-URL."""
    if isinstance(inv, dict):
        return inv.get("pay_url") or inv.get("url")
    if isinstance(inv, str):
        return inv
    return None

@router.callback_query(F.data == "pay:vip")
async def pay_vip(callback: CallbackQuery, state: FSMContext) -> None:
    lang = get_lang(callback.from_user)
    currency = "USDT"
    amount = VIP_PRICE_USD
    await state.update_data(
        plan_name="VIP CLUB",
        price=float(amount),
        period=30,
        plan_callback="vipay",
    )
    data = await state.get_data()
    log.debug("Saved plan_name: %s", data.get("plan_name"))
    log.info(
        "pay_vip: user=%s currency=%s amount=%s",
        callback.from_user.id,
        currency,
        amount,
    )
    inv = await create_invoice(
        user_id=callback.from_user.id,
        plan_code="vip_30d",
        amount_usd=float(amount),
        meta=_build_meta(callback.from_user.id, "vip_30d", currency),
        asset=currency,
    )
    url = _invoice_url(inv)
    if url:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=tr(lang, "btn_cancel"), callback_data="cancel")]]
        )
        await callback.message.edit_text(
            tr(lang, "invoice_message", plan="VIP CLUB", url=url),
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text(tr(lang, "inv_err"))


@router.callback_query(F.data.startswith("vipay:"))
async def vipay_currency(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle currency-specific VIP payments."""
    lang = get_lang(callback.from_user)
    _, _, cur = callback.data.partition("vipay:")
    cur = cur.strip().upper()
    if cur not in CURRENCY_CODES:
        await callback.answer("Unsupported currency", show_alert=True)
        return

    log.info(
        "vipay_currency: user=%s currency=%s amount=%s",
        callback.from_user.id,
        cur,
        VIP_PRICE_USD,
    )
    await state.update_data(
        plan_name="VIP CLUB",
        price=float(VIP_PRICE_USD),
        period=30,
        plan_callback="vipay",
    )
    data = await state.get_data()
    log.debug("Saved plan_name: %s", data.get("plan_name"))
    inv = await create_invoice(
        user_id=callback.from_user.id,
        plan_code="vip_30d",
        amount_usd=float(VIP_PRICE_USD),
        meta=_build_meta(callback.from_user.id, "vip_30d", cur),
        asset=cur,
    )
    url = _invoice_url(inv)
    if url:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=tr(lang, "btn_cancel"), callback_data="cancel")]]
        )
        await callback.message.edit_text(
            tr(lang, "invoice_message", plan="VIP CLUB", url=url),
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text(tr(lang, "inv_err"))



# =======================
# Донаты
# =======================
@router.message(lambda m: (m.text or "").strip() == tr(get_lang(m.from_user), "btn_donate"))
async def donate_menu(msg: Message, state: FSMContext) -> None:
    await state.clear()
    lang = get_lang(msg.from_user)
    await msg.answer(
        tr(lang, "donate_menu"),
        reply_markup=donate_keyboard(lang),
    )

@router.callback_query(F.data.startswith("donate_"))
async def donate_currency(cq: CallbackQuery, state: FSMContext) -> None:
    amount = int(cq.data.split("_", 1)[1])
    await state.update_data(amount=amount)
    await state.set_state(Donate.choosing_currency)
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "donate_currency"),
        reply_markup=donate_currency_keyboard(lang),
    )

@router.callback_query(F.data.startswith("donate$"), Donate.choosing_currency)
async def donate_set_currency(cq: CallbackQuery, state: FSMContext) -> None:
    # ожидаем формат donate$<ASSET>, например donate$USDT
    _, cur = cq.data.split("$", 1)
    cur = cur.strip().upper()
    if cur not in CURRENCY_CODES:
        await cq.answer("Unsupported currency", show_alert=True)
        return
    data = await state.get_data()
    amount = data.get("amount", 0)
    lang = get_lang(cq.from_user)
    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code="donation",
        amount_usd=amount,
        meta={"user_id": cq.from_user.id, "currency": cur, "kind": "donate", "bot_id": BOT_ID},
        asset=cur,
    )
    url = _invoice_url(inv)
    if url:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=tr(lang, "btn_cancel"), callback_data="cancel")]]
        )
        await cq.message.answer(
            tr(lang, "invoice_message", plan="Donate", url=url),
            reply_markup=kb,
        )
    else:
        await cq.message.answer(tr(lang, "inv_err"))
    await state.clear()

@router.callback_query(F.data == "donate_cancel")
async def cancel_donate(callback: CallbackQuery, state: FSMContext) -> None:
    lang = get_lang(callback.from_user)
    await state.clear()
    await callback.answer(tr(lang, "donate_cancel"))
    await callback.message.edit_text(
        tr(lang, "donate_menu"),
        reply_markup=donate_keyboard(lang),
    )


# --- Legacy reply-кнопки (на переходный период) ---

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

@router.message(lambda m: _norm(m.text) in {
    _norm(tr(get_lang(m.from_user), "btn_lux")) or "💎 Luxury Room - 15 $"
})
async def legacy_reply_luxury(msg: Message) -> None:
    lang = get_lang(msg.from_user)
    kb = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        kb.button(text=title, callback_data=f"paymem:chat_30:{code}")
    kb.adjust(2)
    await msg.answer(tr(lang, "luxury_room_desc"), reply_markup=kb.as_markup())

@router.callback_query(F.data == "life")
async def life_link(cq: CallbackQuery):
    lang = get_lang(cq.from_user)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back")
    await cq.message.edit_text(tr(lang, "life", my_channel=LIFE_URL), reply_markup=kb.as_markup())


@router.callback_query(F.data == "back")
async def back_to_main(cq: CallbackQuery):
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))

"""
@router.callback_query(F.data == "donate")
async def donate_currency(cq: CallbackQuery, state: FSMContext):
    await cq.message.edit_text(
        tr(get_lang(cq.from_user), "choose_cur", amount="donate"),
        reply_markup=donate_kb(),
    )
    await state.set_state(Donate.choosing_currency)


@router.callback_query(F.data.startswith("doncur:"), Donate.choosing_currency)
async def donate_amount(cq: CallbackQuery, state: FSMContext):
    await state.update_data(currency=cq.data.split(":")[1])
    await cq.message.edit_text(
        tr(get_lang(cq.from_user), "don_enter"),
        reply_markup=donate_back_kb(),
    )
    await state.set_state(Donate.entering_amount)


@router.callback_query(F.data == "don_back", Donate.entering_amount)
async def donate_back(cq: CallbackQuery, state: FSMContext):
    await state.set_state(Donate.choosing_currency)
    await cq.message.edit_text(
        tr(get_lang(cq.from_user), "choose_cur", amount="donate"),
        reply_markup=donate_kb(),
    )


@router.message(Donate.entering_amount)
async def donate_finish(msg: Message, state: FSMContext):
    text = msg.text.replace(",", ".")
    if not text.replace(".", "", 1).isdigit():
        await msg.reply(tr(get_lang(msg.from_user), "don_num"))
        return
    amount = float(text)
    data = await state.get_data()
    cur = data["currency"]
    amount_usd = amount  # TODO: конверсия при необходимости
    log.info(
        "donate_finish: user=%s currency=%s amount=%s",
        msg.from_user.id,
        cur,
        amount_usd,
    )
    inv = await create_invoice(
        user_id=msg.from_user.id,
        plan_code="donation",
        amount_usd=amount_usd,
        meta={"user_id": msg.from_user.id, "currency": cur, "kind": "donate", "bot_id": BOT_ID},
        asset=cur,
    )
    url = _invoice_url(inv)
    if url:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=tr(get_lang(msg.from_user), "btn_cancel"), callback_data="cancel")]]
        )
        await msg.answer(
            tr(get_lang(msg.from_user), "invoice_message", plan="Donate", url=url),
            reply_markup=kb,
        )
    else:
        await msg.reply(tr(get_lang(msg.from_user), "inv_err"))
    await state.clear()
"""

@router.message(
    lambda m: _norm(m.text) == _norm(tr(get_lang(m.from_user), "btn_chat"))
)
async def handle_chat_btn(msg: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(msg.from_user)
    await msg.answer(tr(lang, "chat_access"), reply_markup=chat_tariffs_kb(lang))


@router.message(F.text == "💎 Luxury Room – 15$")
async def luxury_room_reply(msg: Message):
    lang = get_lang(msg.from_user)
    kb = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        kb.button(text=title, callback_data=f"payc:club:{code}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await msg.answer(tr(lang, "luxury_room_desc"), reply_markup=kb.as_markup())


@router.message(
    lambda m: _norm(m.text) in {
        _norm(tr(get_lang(m.from_user), "btn_vip")),
        "VIP CLUB 🔞 - 19 $",
        "❤️‍🔥 VIP Secret - 35 $",
    }
)
async def vip_secret_reply(msg: Message) -> None:
    lang = get_lang(msg.from_user)
    text = (_norm(msg.text)).upper()
    key = "vip_club_description" if "VIP CLUB" in text else "vip_secret_desc"
    await msg.answer(tr(lang, key), reply_markup=vip_currency_kb(lang))


@router.callback_query(F.data == "tip_menu")
async def tip_menu(cq: CallbackQuery):
    lang = get_lang(cq.from_user)
    await cq.message.answer(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))
