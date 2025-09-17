from __future__ import annotations

import os
import asyncio
import logging
from typing import Any, Optional, Dict, Set

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

# текст/локализация и валюты берём из актуальных модулей
from modules.common.i18n import tr
from modules.constants.currencies import CURRENCIES
# REGION AI: VIP price from config
from shared.config.env import config
from modules.constants.paths import START_PHOTO, VIP_PHOTO
# END REGION AI
from modules.payments import create_invoice

from shared.db.repo import (
    save_pending_invoice,
    get_active_invoice,
    delete_pending_invoice,
)

from shared.utils.lang import get_lang
from shared.utils.telegram import send_with_retry
# Клавиатуры текущего модуля
from .keyboards import (
    main_menu_kb,
    reply_menu,
    vip_currency_kb,
    donate_keyboard,
    donate_currency_keyboard,
    donate_invoice_keyboard,
    vip_invoice_keyboard,
)
from .chat_keyboards import chat_tariffs_kb
from .chat_handlers import router as chat_router
from .utils import BOT_ID, _build_meta

log = logging.getLogger("juicyfox.ui_membership.handlers")

router = Router()
router.include_router(chat_router)

_donate_tasks: Dict[int, asyncio.Task] = {}
_donate_cancelled: Set[int] = set()

# --- Конфиг из ENV (позже переедет в shared.config.env) ---
VIP_URL = os.getenv("VIP_URL")
LIFE_URL = os.getenv("LIFE_URL")

# Набор доступных кодов активов (например, "USDT", "BTC")
CURRENCY_CODES = {code.upper() for _, code in CURRENCIES}


# --- FSM для донатов (оставляем в UI-модуле) ---
class Donate(StatesGroup):
    choosing_currency = State()


# =======================
# /start и главное меню
# =======================
# REGION AI: shared start handler for /start and Restart button
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    lang = get_lang(message.from_user)
    if START_PHOTO.exists():
        photo = FSInputFile(START_PHOTO)
    else:
        photo = "https://files.catbox.moe/cqckle.jpg"
    # REGION AI: show start photo with reply keyboard
    await send_with_retry(
        message.answer_photo,
        photo,
        caption=tr(lang, "menu", name=message.from_user.first_name),
        reply_markup=reply_menu(lang),
        logger=log,
    )
    # END REGION AI
    if LIFE_URL:
        # REGION AI: life promo link without preview
        await send_with_retry(
            message.answer,
            tr(lang, "life_promo"),
            parse_mode="HTML",
            disable_web_page_preview=True,
            logger=log,
        )
        # END REGION AI
    # Inline menu is not shown at start; it will appear on Back button


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await start_handler(message, state)


@router.message(lambda m: (m.text or "").strip().lower() == "restart")
async def restart_button(message: Message, state: FSMContext) -> None:
    await start_handler(message, state)
# END REGION AI


@router.callback_query(F.data.in_({"ui:back", "back_to_main", "back"}))
async def back_to_main(cq: CallbackQuery, state: FSMContext) -> None:
    """Return to main menu and reset any conversation state."""
    await state.clear()
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
    # REGION AI: vip club banner
    await cq.answer()
    await cq.message.delete()
    if VIP_PHOTO.exists():
        photo = FSInputFile(VIP_PHOTO)
        await send_with_retry(
            cq.message.answer_photo,
            photo,
            caption=tr(lang, "vip_club_description", amount=int(config.vip_price_usd)),
            reply_markup=vip_currency_kb(lang),
            parse_mode="HTML",
            logger=log,
        )
    else:
        await send_with_retry(
            cq.message.answer,
            tr(lang, "vip_club_description", amount=int(config.vip_price_usd)),
            reply_markup=vip_currency_kb(lang),
            parse_mode="HTML",
            logger=log,
        )
    # END REGION AI


@router.message(Command("currency"))
async def cmd_currency(message: Message) -> None:
    """Show currency menu for VIP subscription."""
    lang = get_lang(message.from_user)
    await send_with_retry(
        message.answer,
        tr(lang, "choose_cur", amount=config.vip_price_usd),
        reply_markup=vip_currency_kb(lang),
        logger=log,
    )

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
    amount = config.vip_price_usd
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
    invoice_id = inv.get("invoice_id") if isinstance(inv, dict) else None
    if invoice_id:
        await state.update_data(invoice_id=invoice_id, currency=currency, plan_code="vip_30d")
        await save_pending_invoice(
            callback.from_user.id,
            invoice_id,
            "vip_30d",
            currency,
            "vipay",
            "VIP CLUB",
            float(amount),
            30,
        )
    url = _invoice_url(inv)
    if url:
        await callback.message.edit_text(
            tr(lang, "invoice_message", plan="VIP CLUB", url=url),
            reply_markup=vip_invoice_keyboard(lang, url),
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
        config.vip_price_usd,
    )
    await state.update_data(
        plan_name="VIP CLUB",
        price=float(config.vip_price_usd),
        period=30,
        plan_callback="vipay",
    )
    data = await state.get_data()
    log.debug("Saved plan_name: %s", data.get("plan_name"))
    inv = await create_invoice(
        user_id=callback.from_user.id,
        plan_code="vip_30d",
        amount_usd=float(config.vip_price_usd),
        meta=_build_meta(callback.from_user.id, "vip_30d", cur),
        asset=cur,
    )
    invoice_id = inv.get("invoice_id") if isinstance(inv, dict) else None
    if invoice_id:
        await state.update_data(invoice_id=invoice_id, currency=cur, plan_code="vip_30d")
        await save_pending_invoice(
            callback.from_user.id,
            invoice_id,
            "vip_30d",
            cur,
            "vipay",
            "VIP CLUB",
            float(config.vip_price_usd),
            30,
        )
    url = _invoice_url(inv)
    if url:
        await callback.message.edit_text(
            tr(lang, "invoice_message", plan="VIP CLUB", url=url),
            reply_markup=vip_invoice_keyboard(lang, url),
        )
    else:
        await callback.message.edit_text(tr(lang, "inv_err"))



# =======================
# Донаты
# =======================
@router.callback_query(F.data == "ui:donate")
async def donate_menu(cq: CallbackQuery, state: FSMContext) -> None:
    # start donation flow without dropping stored data
    await state.set_state(None)
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "donate_menu"),
        reply_markup=donate_keyboard(lang),
    )


@router.message(lambda m: (m.text or "").strip() == tr(get_lang(m.from_user), "btn_donate"))
async def donate_menu_legacy(msg: Message, state: FSMContext) -> None:
    """Legacy reply-keyboard support."""
    await state.set_state(None)
    lang = get_lang(msg.from_user)
    await send_with_retry(
        msg.answer,
        tr(lang, "donate_menu"),
        reply_markup=donate_keyboard(lang),
        logger=log,
    )

@router.callback_query(F.data.regexp(r"^donate_\d+$"))
async def donate_currency(cq: CallbackQuery, state: FSMContext) -> None:
    amount = int(cq.data.split("_", 1)[1])
    await state.update_data(amount=amount)
    await state.set_state(Donate.choosing_currency)
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "donate_currency"),
        reply_markup=donate_currency_keyboard(lang),
    )

@router.callback_query(F.data == "donate_back", Donate.choosing_currency)
async def donate_back(cq: CallbackQuery, state: FSMContext) -> None:
    """Return from donate flow to the main inline menu."""
    await state.clear()
    lang = get_lang(cq.from_user)
    await cq.message.edit_text(
        tr(lang, "choose_action"),
        reply_markup=main_menu_kb(lang),
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
    await state.update_data(price=float(amount), currency=cur)

    lang = get_lang(cq.from_user)
    try:
        inv = await create_invoice(
            user_id=cq.from_user.id,
            plan_code="donation",
            amount_usd=amount,
            meta={"user_id": cq.from_user.id, "currency": cur, "kind": "donate", "bot_id": BOT_ID},
            asset=cur,
        )
    except Exception:
        log.exception("donate_set_currency: create_invoice failed")
        await send_with_retry(
            cq.message.answer,
            tr(lang, "donate_error"),
            logger=log,
        )
        return

    invoice_id = inv.get("invoice_id") if isinstance(inv, dict) else None
    invoice_url = _invoice_url(inv)
    if invoice_url:
        if invoice_id:
            data = await state.get_data()
            try:
                await save_pending_invoice(
                    cq.from_user.id,
                    invoice_id,
                    "donation",
                    data.get("currency", cur),
                    "donate",
                    "Donate",
                    float(data.get("price", amount)),
                    0,
                )
            except Exception:
                log.exception("donate_set_currency: save_pending_invoice failed")
                await send_with_retry(
                    cq.message.answer,
                    tr(lang, "donate_error"),
                    logger=log,
                )
                return


    await cq.answer()

    user_id = cq.from_user.id
    # cancel previous pending task if any
    prev = _donate_tasks.pop(user_id, None)
    if prev and not prev.done():
        prev.cancel()
    _donate_cancelled.discard(user_id)

    task = asyncio.create_task(
        _create_donate_invoice(cq, state, user_id, cur, float(amount))
    )
    _donate_tasks[user_id] = task


async def _create_donate_invoice(
    cq: CallbackQuery,
    state: FSMContext,
    user_id: int,
    currency: str,
    amount: float,
) -> None:
    """Background task: create invoice and notify user."""
    invoice_id: Optional[str] = None
    lang = get_lang(cq.from_user)
    try:
        inv = await create_invoice(
            user_id=user_id,
            plan_code="donation",
            amount_usd=amount,
            meta={
                "user_id": user_id,
                "currency": currency,
                "kind": "donate",
                "bot_id": BOT_ID,
            },
            asset=currency,
        )
        invoice_id = inv.get("invoice_id") if isinstance(inv, dict) else None
        invoice_url = _invoice_url(inv)
        if not invoice_url or not invoice_id:
            await send_with_retry(
                cq.message.answer,
                tr(lang, "inv_err"),
                logger=log,
            )
            return

        await save_pending_invoice(
            user_id,
            invoice_id,
            "donation",
            currency,
            "donate",
            "Donate",
            float(amount),
            0,
        )

        if user_id in _donate_cancelled:
            await delete_pending_invoice(invoice_id)
            return


        await cq.message.edit_text(
            tr(lang, "invoice_message", plan="Donate", url=invoice_url),
            reply_markup=donate_invoice_keyboard(lang, invoice_url),
        )
        await state.clear()
    except asyncio.CancelledError:
        if invoice_id:
            await delete_pending_invoice(invoice_id)
        log.info("donation task cancelled: user_id=%s", user_id)
    except Exception:
        log.exception("donation invoice failed: user_id=%s", user_id)
        try:
            await send_with_retry(
                cq.message.answer,
                tr(lang, "donate_error"),
                logger=log,
            )
        except Exception:
            log.exception("failed to send donate_error message: user_id=%s", user_id)
    finally:
        _donate_tasks.pop(user_id, None)
        _donate_cancelled.discard(user_id)

@router.callback_query(F.data == "donate_cancel_invoice")
async def cancel_donate_invoice(callback: CallbackQuery, state: FSMContext):
    """Cancel donation invoice and return to currency selection."""
    lang = get_lang(callback.from_user)
    user_id = callback.from_user.id

    _donate_cancelled.add(user_id)
    task = _donate_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()

    invoice = await get_active_invoice(user_id)

    log.debug("Active invoice for user %s: %s", user_id, invoice)
    if not invoice:
        await callback.answer(tr(lang, "nothing_cancel"), show_alert=True)
        return

    fsm_state = await state.get_state()
    deleted_rows = await delete_pending_invoice(invoice["invoice_id"])
    log.info(
        "cancel_donate_invoice: user_id=%s invoice_id=%s plan_code=%s state=%s deleted=%s",
        user_id,
        invoice["invoice_id"],
        invoice["plan_code"],
        fsm_state,
        deleted_rows > 0,
    )
    await state.clear()
    await state.update_data(amount=invoice.get("price"))
    await state.set_state(Donate.choosing_currency)
    await callback.answer(tr(lang, "donate_cancel"))
    await callback.message.edit_text(
        tr(lang, "donate_currency"),
        reply_markup=donate_currency_keyboard(lang),
    )


@router.callback_query(F.data == "donate_cancel")
async def cancel_donate(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle external donate cancel actions and return to currency selection."""
    lang = get_lang(callback.from_user)
    user_id = callback.from_user.id

    _donate_cancelled.add(user_id)
    task = _donate_tasks.pop(user_id, None)
    if task and not task.done():
        task.cancel()

    invoice = await get_active_invoice(user_id)
    log.debug("Active invoice for user %s: %s", user_id, invoice)
    if not invoice:
        await callback.answer(tr(lang, "nothing_cancel"), show_alert=True)
        return
    fsm_state = await state.get_state()
    deleted_rows = await delete_pending_invoice(invoice["invoice_id"])
    log.info(
        "cancel_donate: user_id=%s invoice_id=%s plan_code=%s state=%s deleted=%s",
        user_id,
        invoice["invoice_id"],
        invoice["plan_code"],
        fsm_state,
        deleted_rows > 0,
    )
    await state.clear()
    await state.update_data(amount=invoice.get("price"))
    await state.set_state(Donate.choosing_currency)
    await callback.answer(tr(lang, "donate_cancel"))
    await callback.message.edit_text(
        tr(lang, "donate_currency"),
        reply_markup=donate_currency_keyboard(lang),
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
    await send_with_retry(
        msg.answer,
        tr(lang, "luxury_room_desc"),
        reply_markup=kb.as_markup(),
        logger=log,
    )

@router.message(
    lambda m: _norm(m.text) == _norm(tr(get_lang(m.from_user), "btn_chat"))
)
async def handle_chat_btn(msg: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(msg.from_user)
    await send_with_retry(
        msg.answer,
        tr(lang, "chat_access"),
        reply_markup=chat_tariffs_kb(lang),
        logger=log,
    )


@router.message(F.text == "💎 Luxury Room – 15$")
async def luxury_room_reply(msg: Message):
    lang = get_lang(msg.from_user)
    kb = InlineKeyboardBuilder()
    for title, code in CURRENCIES:
        kb.button(text=title, callback_data=f"payc:club:{code}")
    kb.button(text=tr(lang, "btn_back"), callback_data="ui:back")
    kb.adjust(2)
    await send_with_retry(
        msg.answer,
        tr(lang, "luxury_room_desc"),
        reply_markup=kb.as_markup(),
        logger=log,
    )

@router.message(
    lambda m: _norm(m.text) in {
        _norm(tr(get_lang(m.from_user), "btn_vip")),
        _norm("❤️‍🔥 VIP Secret - 35 $"),
    }
)
async def vip_secret_reply(msg: Message):
    lang = get_lang(msg.from_user)
    text = _norm(msg.text)
    descriptions = {
        _norm(tr(lang, "btn_vip")): "vip_club_description",  # VIP CLUB plan
        _norm("❤️‍🔥 VIP Secret - 35 $"): "vip_secret_desc",  # VIP Secret plan
    }
    key = descriptions.get(text, "vip_club_description")

    log.info(f"Handler: vip_club_reply / plan={key}")
    # REGION AI: vip description parse mode
    await send_with_retry(
        msg.answer,
        tr(lang, key),
        reply_markup=vip_currency_kb(lang),
        parse_mode="HTML",
        logger=log,
    )
    # END REGION AI


@router.callback_query(F.data == "tip_menu")
async def tip_menu(cq: CallbackQuery):
    lang = get_lang(cq.from_user)
    await send_with_retry(
        cq.message.answer,
        tr(lang, "choose_action"),
        reply_markup=main_menu_kb(lang),
        logger=log,
    )
