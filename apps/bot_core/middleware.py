"""
Middleware registry for aiogram (stub version).
Here you can connect logging, rate limiting, error handlers, tracing, etc.
"""

from aiogram import Dispatcher


def register_middlewares(dp: Dispatcher) -> None:
    """
    Register global middlewares for the bot.
    Currently stub — extend later if needed.
    """
    # Example: dp.message.middleware(my_logging_middleware)
    # Example: dp.update.middleware(my_rate_limit_middleware)
    pass
