"""Telegram helper utilities for JuicyFox bots."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional, TypeVar

try:
    from aiogram.exceptions import TelegramNetworkError
except Exception:  # pragma: no cover - fallback when aiogram is unavailable
    class TelegramNetworkError(Exception):
        """Fallback Telegram network error used when aiogram is missing."""

        pass

try:
    from shared.config import config
except Exception:  # pragma: no cover - configuration may be unavailable during import
    config = None  # type: ignore

T = TypeVar("T")

AsyncCall = Callable[..., Awaitable[T]]


def _qualname(func: Callable[..., Any]) -> str:
    """Return a readable name for logging purposes."""
    return getattr(func, "__qualname__", repr(func))


async def send_with_retry(
    func: AsyncCall[T],
    *args: Any,
    attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    logger: Optional[logging.Logger] = None,
    **kwargs: Any,
) -> T:
    """Execute ``func`` with retries on :class:`TelegramNetworkError`.

    Parameters
    ----------
    func:
        Awaitable Telegram API call (e.g. ``bot.send_message`` or
        ``message.answer``).
    attempts:
        Override number of attempts.  Defaults to the value provided by
        configuration (``config.telegram_send_attempts``) or ``3``.
    base_delay:
        Base delay in seconds before retrying.  Each subsequent retry uses an
        exponential backoff: ``delay * 2 ** (attempt - 1)``.  Defaults to
        ``config.telegram_send_base_delay`` or ``1.0`` seconds.
    logger:
        Optional logger used for diagnostics.  Falls back to a module-wide
        logger named ``"juicyfox.telegram"``.

    Returns
    -------
    The result of ``func`` on success.  If all retries fail with a
    ``TelegramNetworkError`` the exception is re-raised, preserving previous
    behaviour of direct Telegram API calls.
    """

    log = logger or logging.getLogger("juicyfox.telegram")

    cfg_attempts = getattr(config, "telegram_send_attempts", None) if config else None
    cfg_delay = getattr(config, "telegram_send_base_delay", None) if config else None

    try:
        attempts_val = int(attempts if attempts is not None else (cfg_attempts or 3))
    except Exception:
        attempts_val = 3
    if attempts_val < 1:
        attempts_val = 1

    try:
        delay_val = float(base_delay if base_delay is not None else (cfg_delay if cfg_delay is not None else 1.0))
    except Exception:
        delay_val = 1.0
    if delay_val < 0:
        delay_val = 0.0

    last_error: Optional[TelegramNetworkError] = None

    for attempt_num in range(1, attempts_val + 1):
        try:
            return await func(*args, **kwargs)
        except TelegramNetworkError as err:
            last_error = err
            if attempt_num >= attempts_val:
                log.exception(
                    "send_with_retry: %s failed after %s attempts due to network error",
                    _qualname(func),
                    attempts_val,
                )
                raise
            sleep_for = delay_val * (2 ** (attempt_num - 1))
            log.warning(
                "send_with_retry: %s network error on attempt %s/%s; retrying in %.2fs",
                _qualname(func),
                attempt_num,
                attempts_val,
                sleep_for,
            )
            await asyncio.sleep(sleep_for)
        except Exception:
            log.exception(
                "send_with_retry: %s raised unexpected exception", _qualname(func)
            )
            raise

    # Should never be reached because the loop returns on success or raises.
    if last_error:
        raise last_error
    raise RuntimeError("send_with_retry: execution finished without result")
