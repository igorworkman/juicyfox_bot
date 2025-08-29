from aiogram import Router

router = Router()


# Старый обработчик /start оставлен для истории.
# Основная реализация теперь находится в modules.ui_membership.handlers.cmd_start.
# @router.message(Command("start"))
# async def cmd_start(message: types.Message):
#     await message.answer(
#         "👋 Привет! Я JuicyFox бот.\n\n"
#         "✨ Доступные опции:\n"
#         "💎 Luxury Room - 15$\n"
#         "🔥 VIP Secret - 35$"
#     )
