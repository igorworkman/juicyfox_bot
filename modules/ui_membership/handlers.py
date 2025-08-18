from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from modules.common.shared import CURRENCIES, LIFE_URL, ChatGift, create_invoice, tr
from .keyboards import (
    chat_plan_kb,
    donate_back_kb,
    donate_kb,
    main_menu_kb,
    reply_menu,
    vip_currency_kb,
)

router = Router()


class Donate(StatesGroup):
    choosing_currency = State()
    entering_amount = State()


@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
    lang = msg.from_user.language_code
    await msg.answer_photo(
        "https://files.catbox.moe/cqckle.jpg",
        caption=tr(lang, "menu", name=msg.from_user.first_name),
    )
    await msg.answer(tr(lang, "my_channel", link=LIFE_URL), reply_markup=reply_menu())
    await msg.answer(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "life")
async def life_link(cq: CallbackQuery):
    lang = cq.from_user.language_code
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад", callback_data="back")
    await cq.message.edit_text(tr(lang, "life", my_channel=LIFE_URL), reply_markup=kb.as_markup())


@router.callback_query(F.data == "back")
async def back_to_main(cq: CallbackQuery):
    lang = cq.from_user.language_code
    await cq.message.edit_text(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))


@router.callback_query(F.data == "donate")
async def donate_currency(cq: CallbackQuery, state: FSMContext):
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "choose_cur", amount="donate"),
        reply_markup=donate_kb(),
    )
    await state.set_state(Donate.choosing_currency)


@router.callback_query(F.data.startswith("doncur:"), Donate.choosing_currency)
async def donate_amount(cq: CallbackQuery, state: FSMContext):
    await state.update_data(currency=cq.data.split(":")[1])
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "don_enter"),
        reply_markup=donate_back_kb(),
    )
    await state.set_state(Donate.entering_amount)


@router.callback_query(F.data == "don_back", Donate.entering_amount)
async def donate_back(cq: CallbackQuery, state: FSMContext):
    await state.set_state(Donate.choosing_currency)
    await cq.message.edit_text(
        tr(cq.from_user.language_code, "choose_cur", amount="donate"),
        reply_markup=donate_kb(),
    )


@router.message(Donate.entering_amount)
async def donate_finish(msg: Message, state: FSMContext):
    text = msg.text.replace(",", ".")
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


@router.message(F.text == "SEE YOU MY CHAT💬")
async def handle_chat_btn(msg: Message, state: FSMContext):
    lang = msg.from_user.language_code
    await state.set_state(ChatGift.plan)
    await msg.answer(tr(lang, "chat_access"), reply_markup=chat_plan_kb(lang))


@router.message(F.text == "💎 Luxury Room – 15$")
async def luxury_room_reply(msg: Message):
    lang = msg.from_user.language_code
    kb = InlineKeyboardBuilder()
    for t, c in CURRENCIES:
        kb.button(text=t, callback_data=f"payc:club:{c}")
    kb.button(text="⬅️ Назад", callback_data="back")
    kb.adjust(2)
    await msg.answer(tr(lang, "luxury_room_desc"), reply_markup=kb.as_markup())


@router.message(F.text == "❤️‍🔥 VIP Secret – 35$")
async def vip_secret_reply(msg: Message):
    lang = msg.from_user.language_code
    await msg.answer(tr(lang, "vip_secret_desc"), reply_markup=vip_currency_kb())


@router.callback_query(F.data == "tip_menu")
async def tip_menu(cq: CallbackQuery):
    lang = cq.from_user.language_code
    await cq.message.answer(tr(lang, "choose_action"), reply_markup=main_menu_kb(lang))
