from __future__ import annotations

import os
from typing import Any, Dict, Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

# текст/локализация и валюты берём из общего модуля
from modules.common.shared import CURRENCIES, tr

# create_invoice по Плану A живёт в payments.service,
# но поддержим обратную совместимость с монолитом.
try:  # pragma: no cover - мягкий fallback
    from modules.payments.service import create_invoice  # type: ignore
except Exception:  # старый путь
    from modules.common.shared import create_invoice  # type: ignore

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

# --- Конфиг, который пока читаем из ENV (позже переедет в shared.config.env) ---
VIP_URL = os.getenv("VIP_URL")
LIFE_URL = os.getenv("LIFE_URL")
VIP_PRICE_USD = float(os.getenv("VIP_30D_USD", "25"))
CHAT_PRICE_USD = float(os.getenv("CHAT_30D_USD", "15"))

# --- FSM для донатов (оставляем в UI-модуле, как и было) ---
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
    lang = message.from_user.language_code
    await message.answer(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))
    # По желанию можно показать reply-меню
    await message.answer(tr(lang, "reply_menu_hint"), reply_markup=reply_menu(lang))


@router.callback_query(F.data.in_({"ui:back", "back_to_main"}))
async def back_to_main(cq: CallbackQuery) -> None:
    lang = cq.from_user.language_code
    await cq.message.edit_text(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))


# =======================
# VIP / Chat / Life
# =======================
@router.callback_query(F.data.in_({"ui:vip", "vip"}))
async def show_vip(cq: CallbackQuery) -> None:
    lang = cq.from_user.language_code
    await cq.message.edit_text(tr(lang, "vip_secret_desc"), reply_markup=vip_currency_kb())


@router.callback_query(F.data.in_({"ui:chat", "chat"}))
async def show_chat(cq: CallbackQuery) -> None:
    lang = cq.from_user.language_code
    await cq.message.edit_text(tr(lang, "chat_desc"), reply_markup=chat_plan_kb())


@router.callback_query(F.data.in_({"ui:life", "life"}))
async def show_life_link(cq: CallbackQuery) -> None:
    lang = cq.from_user.language_code
    url = LIFE_URL
    if not url:
        await cq.answer(tr(lang, "link_is_missing"), show_alert=True)
        return
    await cq.message.answer(tr(lang, "life_room_link"), reply_markup=None)
    await cq.message.answer(url)


# =======================
# Оплата подписок (VIP/Chat)
# =======================
def _build_meta(user_id: int, plan_code: str, currency: str) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "plan_code": plan_code,
        "currency": currency,
    }

@router.callback_query(F.data.in_({"pay:vip"}))
async def pay_vip(cq: CallbackQuery) -> None:
    lang = cq.from_user.language_code
    # по умолчанию считаем USD, дальше можно добавить выбор валюты
    currency = "USD"
    amount = VIP_PRICE_USD
    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code="vip_30d",
        amount_usd=float(amount) if currency == "USD" else float(amount),
        meta=_build_meta(cq.from_user.id, "vip_30d", currency),
    )
    url = inv.get("pay_url")
    await cq.message.answer(tr(lang, "invoice_created"), reply_markup=donate_back_kb(lang))
    if url:
        await cq.message.answer(url)


@router.callback_query(F.data.in_({"pay:chat"}))
async def pay_chat(cq: CallbackQuery) -> None:
    lang = cq.from_user.language_code
    currency = "USD"
    amount = CHAT_PRICE_USD
    inv = await create_invoice(
        user_id=cq.from_user.id,
        plan_code="chat_30d",
        amount_usd=float(amount) if currency == "USD" else float(amount),
        meta=_build_meta(cq.from_user.id, "chat_30d", currency),
    )
    url = inv.get("pay_url")
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
        tr(cq.from_user.language_code, "choose_cur", amount="donate"),
        reply_markup=donate_kb(),
    )

@router.callback_query(F.data.startswith("donate:cur:"), Donate.choosing_currency)
async def donate_set_currency(cq: CallbackQuery, state: FSMContext) -> None:
    # ожидаем формат donate:cur:USD
    _, _, cur = cq.data.partition("donate:cur:")
    cur = cur.strip().upper()
    if cur not in CURRENCIES:
        await cq.answer("Unsupported currency", show_alert=True)
        return
    await state.update_data(currency=cur)
    await state.set_state(Donate.entering_amount)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "enter_amount", cur=cur),
        reply_markup=donate_back_kb(cq.from_user.language_code),
    )

@router.message(Donate.entering_amount, F.text.regexp(r"^\d+([.,]\d{1,2})?$"))
async def donate_make_invoice(msg: Message, state: FSMContext) -> None:
    lang = msg.from_user.language_code
    data = await state.get_data()
    cur = data.get("currency", "USD")
    # парсим сумму
    raw = msg.text.replace(",", ".")
    amount = float(raw)
    # считаем в USD (если валюта не USD — здесь может быть конверсия; пока 1:1 заглушка)
    amount_usd = amount if cur == "USD" else amount

    inv = await create_invoice(
        user_id=msg.from_user.id,
        plan_code="donation",
        amount_usd=amount_usd,
        meta={"user_id": msg.from_user.id, "currency": cur, "kind": "donate"},
    )
    url = inv.get("pay_url")
    await msg.answer(tr(lang, "invoice_created"))
    if url:
        await msg.answer(url)
    await state.clear()

@router.callback_query(F.data == "donate:back")
async def donate_back(cq: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    lang = cq.from_user.language_code
    await cq.message.edit_text(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))

# --- Legacy reply-кнопки (опционально, на переходный период) ---

@router.message(F.text == "SEE YOU MY CHAT💬")
async def legacy_reply_chat(msg: Message, state: FSMContext) -> None:
    # Поведение как при ui:chat
    await state.clear()
    lang = msg.from_user.language_code
    await msg.answer(tr(lang, "chat_desc"), reply_markup=chat_plan_kb())

@router.message(F.text == "💎 Luxury Room – 15$")
async def legacy_reply_luxury(msg: Message) -> None:
    # Открываем выбор валюты для «клубного» плана (аналог старого хендлера)
    lang = msg.from_user.language_code
    kb = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        # Можно заменить на отдельный план, если нужен отличать от chat_30d
        kb.button(text=title, callback_data="pay:chat")
    kb.adjust(2)
    await msg.answer(tr(lang, "luxury_room_desc"), reply_markup=kb.as_markup())

@router.message(F.text == "❤️‍🔥 VIP Secret – 35$")
async def legacy_reply_vip(msg: Message) -> None:
    # Поведение как при ui:vip
    lang = msg.from_user.language_code
    await msg.answer(tr(lang, "vip_secret_desc"), reply_markup=vip_currency_kb())
