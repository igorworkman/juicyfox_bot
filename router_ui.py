from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from juicyfox_bot_single import CURRENCIES, create_invoice, tr
from aiogram.filters import Command

router = Router()


@router.message(Command("ui_test"))
async def ui_stub(message: Message):
    await message.answer("🖥️ UI модуль временно недоступен.")


class Donate(StatesGroup):
    choosing_currency = State()
    entering_amount = State()


@router.callback_query(F.data == "donate")
async def donate_currency(cq: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"doncur:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "choose_cur", amount="donate"),
        reply_markup=kb.as_markup(),
    )
    await state.set_state(Donate.choosing_currency)


@router.callback_query(F.data.startswith("doncur:"), Donate.choosing_currency)
async def donate_amount(cq: CallbackQuery, state: FSMContext):
    """Отображаем просьбу ввести сумму + кнопка 🔙 Назад"""
    await state.update_data(currency=cq.data.split(":")[1])
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="don_back")]]
    )
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "don_enter"),
        reply_markup=back_kb,
    )
    await state.set_state(Donate.entering_amount)


@router.callback_query(F.data == "don_back", Donate.entering_amount)
async def donate_back(cq: CallbackQuery, state: FSMContext):
    """Возврат к выбору валюты с кнопкой Назад"""
    await state.set_state(Donate.choosing_currency)
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"doncur:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "choose_cur", amount="donate"),
        reply_markup=kb.as_markup(),
    )


@router.message(Donate.entering_amount)
async def donate_finish(msg: Message, state: FSMContext):
    """Получаем сумму в USD, создаём счёт и завершаем FSM"""
    text = msg.text.replace(",", ".").strip()
    if not text.replace(".", "", 1).isdigit():
        await msg.reply(tr(msg.from_user.language_code, "don_num"))
        return
    usd = float(text)
    data = await state.get_data()
    cur = data["currency"]
    url = await create_invoice(msg.from_user.id, usd, cur, "JuicyFox Donation", pl="donate")
    if url:
        await msg.answer(f"Счёт на оплату (Donate): {url}")
    else:
        await msg.reply(tr(msg.from_user.language_code, "inv_err"))
    await state.clear()
