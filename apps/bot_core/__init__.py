from aiogram import Dispatcher
from .routers import start   # импортируем start.py из папки routers

def register(dp: Dispatcher, cfg=None):
    dp.include_router(start.router)
