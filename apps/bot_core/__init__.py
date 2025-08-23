from aiogram import Dispatcher


def register(dp: Dispatcher, cfg=None):
    """Placeholder for registering core routers.

    The previous implementation attempted to import a non-existent
    ``start`` module from ``apps.bot_core.routers`` which raised an
    ``ImportError`` during application start-up.  The explicit import has
    been removed to avoid this failure; router registration can be
    extended here when new modules are added.
    """
    return None
