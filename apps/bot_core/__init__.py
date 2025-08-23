from aiogram import Dispatcher
from . import start

def register(dp: Dispatcher, cfg=None):
    dp.include_router(start.router)
