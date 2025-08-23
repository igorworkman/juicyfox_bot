from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Привет! Я JuicyFox бот.\n\n"
        "✨ Доступные опции:\n"
        "💎 Luxury Room - 15$\n"
        "🔥 VIP Secret - 35$"
    )
