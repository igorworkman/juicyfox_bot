from __future__ import annotations

import os
from typing import Any, Dict, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

# текст/локализация и валюты берём из актуальных модулей
from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
from modules.constants.paths import START_PHOTO
from modules.payments import create_invoice
from shared.utils.lang import get_lang

# Клавиатуры текущего модуля
from .keyboards import (
    chat_plan_kb,
    donate_back_kb,
    donate_kb,
    main_menu_kb,
    reply_menu,
    vip_currency_kb,
)

router = Router()

# --- Конфиг из ENV (позже переедет в shared.config.env) ---
BOT_ID = os.getenv("BOT_ID", "sample")
VIP_URL = os.getenv("VIP_URL")
LIFE_URL = os.getenv("LIFE_URL")
VIP_PRICE_USD = float(os.getenv("VIP_30D_USD", "25"))
CHAT_PRICE_USD = float(os.getenv("CHAT_30D_USD", "15"))

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
            reply_markup=reply_menu(lang)
        )
    await message.answer(
        tr(lang, "choose_action"),
        reply_markup=main_menu_kb(lang)
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
    await cq.message.edit_text(tr(lang, "vip_secret_desc"), reply_markup=vip_currency_kb(lang))


@router.message(Command("currency"))
async def cmd_currency(message: Message) -> None:
    """Show currency menu for VIP subscription."""
    lang = get_lang(message.from_user)
    await message.answer(
        tr(lang, "choose_cur", amount=VIP_PRICE_USD),
        reply_markup=vip_currency_kb(lang),
    )


@router.callback_query(F.data.in_({"ui:chat", "chat"}))
async def show_chat(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(tr(lang, "chat_desc"), reply_markup=chat_plan_kb())


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
def _build_meta(user_id: int, plan_code: str, currency: str) -> Dict[str, Any]:
    return {"user_id": user_id, "plan_code": plan_code, "currency": currency, "bot_id": BOT_ID}

def _invoice_url(inv: Any) -> Optional[str]:
    """Поддерживаем и dict с 'pay_url', и просто строку-URL."""
    if isinstance(inv, dict):
        return inv.get("pay_url") or inv.get("url")
    if isinstance(inv, str):
        return inv
    return None

@router.callback_query(F.data == "pay:vip")
async def pay_vip(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    currency = "USDT"
    amount = VIP_PRICE_USD
    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code="vip_30d",
        amount_usd=float(amount),
        meta=_build_meta(cq.from_user.id, "vip_30d", currency),
        asset=currency,
    )
    url = _invoice_url(inv)
    await cq.message.answer(tr(lang, "invoice_created"), reply_markup=vip_currency_kb(lang))
    if url:
        await cq.message.answer(url)


@router.callback_query(F.data.startswith("vipay:"))
async def vipay_currency(cq: CallbackQuery) -> None:
    """Handle currency-specific VIP payments."""
    lang = get_lang(cq.from_user)
    _, _, cur = cq.data.partition("vipay:")
    cur = cur.strip().upper()
    if cur not in CURRENCY_CODES:
        await cq.answer("Unsupported currency", show_alert=True)
        return

    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code="vip_30d",
        amount_usd=float(VIP_PRICE_USD),
        meta=_build_meta(cq.from_user.id, "vip_30d", cur),
        asset=cur,
    )
    url = _invoice_url(inv)
    await cq.message.answer(tr(lang, "invoice_created"), reply_markup=vip_currency_kb(lang))
    if url:
        await cq.message.answer(url)

@router.callback_query(F.data == "pay:chat")
async def pay_chat(cq: CallbackQuery) -> None:
    lang = get_lang(cq.from_user)
    currency = "USDT"
    amount = CHAT_PRICE_USD
    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code="chat_30d",
        amount_usd=float(amount),
        meta=_build_meta(cq.from_user.id, "chat_30d", currency),
        asset=currency,
    )
    url = _invoice_url(inv)
    await cq.message.answer(tr(lang, "invoice_created"), reply_markup=donate_back_kb(lang))
    if url:
        await cq.message.answer(url)


# =======================
# Донаты
# =======================
@router.callback_query(F.data.in_({"donate", "ui:tip"}))
async def donate_currency(cq: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Donate.choosing_currency)
    await cq.message.edit_text(
        tr(get_lang(cq.from_user), "choose_cur", amount="donate"),
        reply_markup=donate_kb(),
    )

@router.callback_query(F.data.startswith("donate:cur:"), Donate.choosing_currency)
async def donate_set_currency(cq: CallbackQuery, state: FSMContext) -> None:
    # ожидаем формат donate:cur:<ASSET>, например donate:cur:USDT
    _, _, cur = cq.data.partition("donate:cur:")
    cur = cur.strip().upper()
    if cur not in CURRENCY_CODES:
        await cq.answer("Unsupported currency", show_alert=True)
        return
    await state.update_data(currency=cur)
    await state.set_state(Donate.entering_amount)
    await cq.message.edit_text(
        tr(get_lang(cq.from_user), "enter_amount", cur=cur),
        reply_markup=donate_back_kb(get_lang(cq.from_user)),
    )

@router.message(Donate.entering_amount, F.text.regexp(r"^\d+([.,]\d{1,2})?$"))
async def donate_make_invoice(msg: Message, state: FSMContext) -> None:
    lang = get_lang(msg.from_user)
    data = await state.get_data()
    cur = (data.get("currency") or "USDT").upper()
    raw = (msg.text or "0").replace(",", ".")
    amount = float(raw)

    amount_usd = amount  # TODO: конверсия при необходимости
    inv = await create_invoice(
        user_id=msg.from_user.id,
        plan_code="donation",
        amount_usd=amount_usd,
        meta={"user_id": msg.from_user.id, "currency": cur, "kind": "donate", "bot_id": BOT_ID},
        asset=cur,
    )
    url = _invoice_url(inv)
    await msg.answer(tr(lang, "invoice_created"))
    if url:
        await msg.answer(url)
    await state.clear()

@router.callback_query(F.data == "donate:back")
async def donate_back(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))


# --- Legacy reply-кнопки (на переходный период) ---

def _norm(s: Optional[str]) -> str:
    return (s or "").strip()

@router.message(lambda m: _norm(m.text) in {
    _norm(tr(get_lang(m.from_user), "btn_chat")) or "SEE YOU MY CHAT💬"
})
async def legacy_reply_chat(msg: Message, state: FSMContext) -> None:
    await state.clear()
    lang = get_lang(msg.from_user)
    await msg.answer(tr(lang, "chat_desc"), reply_markup=chat_plan_kb())

@router.message(lambda m: _norm(m.text) in {
    _norm(tr(get_lang(m.from_user), "btn_club")) or "💎 Luxury Room - 15 $"
})
async def legacy_reply_luxury(msg: Message) -> None:
    lang = get_lang(msg.from_user)
    kb = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        kb.button(text=title, callback_data="pay:chat")  # при желании сделай отдельный plan_code
    kb.adjust(2)
    await msg.answer(tr(lang, "luxury_room_desc"), reply_markup=kb.as_markup())

@router.message(lambda m: _norm(m.text) in {
    _norm(tr(get_lang(m.from_user), "btn_vip")) or "❤️‍🔥 VIP Secret - 35 $"
})
async def legacy_reply_vip(msg: Message) -> None:
    lang = get_lang(msg.from_user)
    await msg.answer(tr(lang, "vip_secret_desc"), reply_markup=vip_currency_kb())

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
    inv = await create_invoice(
        user_id=msg.from_user.id,
        plan_code="donation",
        amount_usd=amount_usd,
        meta={"user_id": msg.from_user.id, "currency": cur, "kind": "donate", "bot_id": BOT_ID},
        asset=cur,
    )
    url = _invoice_url(inv)
    if url:
        await msg.answer(f"Счёт на оплату (Donate): {url}")
    else:
        await msg.reply(tr(get_lang(msg.from_user), "inv_err"))
    await state.clear()


@router.message(F.text == "SEE YOU MY CHAT💬")
async def handle_chat_btn(msg: Message, state: FSMContext):
    lang = get_lang(msg.from_user)
    await state.set_state(ChatGift.plan)
    await msg.answer(tr(lang, "chat_access"), reply_markup=chat_plan_kb(lang))


@router.message(F.text == "💎 Luxury Room – 15$")
async def luxury_room_reply(msg: Message):
    lang = get_lang(msg.from_user)
    kb = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        kb.button(text=title, callback_data=f"payc:club:{code}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await msg.answer(tr(lang, "luxury_room_desc"), reply_markup=kb.as_markup())


@router.message(F.text == "❤️‍🔥 VIP Secret - 35 $")
async def vip_secret_reply(msg: Message):
    lang = get_lang(msg.from_user)
    await msg.answer(tr(lang, "vip_secret_desc"), reply_markup=vip_currency_kb())


@router.callback_query(F.data == "tip_menu")
async def tip_menu(cq: CallbackQuery):
    lang = get_lang(cq.from_user)
    await cq.message.answer(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))
