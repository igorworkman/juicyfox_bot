"""Idempotency key helpers for JuicyFox (Plan A).

Idempotency keys prevent duplicate processing of the same external
events (e.g. payment webhooks) or scheduled jobs.  This module
provides simple functions to generate deterministic keys based on
distinct resource identifiers.  These keys can be used in a cache or
database to detect whether a particular operation has already been
performed.

Functions provided:

* ``provider_key(provider, ext_id)`` – key for external provider events.
* ``post_key(post_id, run_at)`` – key for scheduled posts.
* ``user_channel_key(user_id, channel_id)`` – key for user/channel pairs.

Additional helpers can be added as needed for other idempotent
operations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


def provider_key(provider: str, ext_id: Any) -> str:
    """Return an idempotency key for an external provider event.

    :param provider: Name of the provider (e.g. 'cryptobot').
    :param ext_id: External identifier (invoice ID, transaction ID, etc.).
    :returns: A string key combining provider and external ID.
    """
    return f"{provider}:{ext_id}"


def post_key(post_id: Any, run_at: datetime) -> str:
    """Return an idempotency key for a scheduled post.

    :param post_id: Identifier of the post (could be int or str).
    :param run_at: Scheduled run time as a datetime.
    :returns: A string key combining post ID and run timestamp.

    The datetime is normalized to UTC before converting to a timestamp.
    If the datetime is naive (lacks tzinfo), it is assumed to be UTC.
    """
    # Normalize naive datetimes to UTC before converting to a timestamp.
    # Using a naive datetime will interpret the timestamp relative to the
    # system local timezone, which can lead to inconsistent keys across
    # different deployments.  We therefore treat naive datetimes as
    # UTC and always convert aware datetimes to UTC.
    if run_at.tzinfo is None:
        run_at = run_at.replace(tzinfo=timezone.utc)
    ts = int(run_at.astimezone(timezone.utc).timestamp())
    return f"post:{post_id}:{ts}"


def user_channel_key(user_id: Any, channel_id: Any) -> str:
    """Return an idempotency key for a user/channel combination.

    :param user_id: Telegram user ID.
    :param channel_id: Telegram channel ID or chat ID.
    :returns: A string key combining user and channel IDs.
    """
    return f"user:{user_id}:channel:{channel_id}"


def telegram_update_key(bot_id: Any, update: Any) -> str:
    """Return an idempotency key for a Telegram update.

    The primary identifier is :attr:`Update.update_id`.  If the update lacks
    this field (which should be rare), we fall back to hashing the payload so
    that structurally identical updates map to the same key.

    :param bot_id: Identifier of the bot handling the update.  Including the
        bot ID prevents collisions when multiple bots share the same storage.
    :param update: Either an :class:`aiogram.types.Update` instance or the raw
        decoded JSON dictionary received from Telegram.
    :returns: A deterministic idempotency key.
    """

    update_id = getattr(update, "update_id", None)
    if update_id is None and isinstance(update, Mapping):
        update_id = update.get("update_id")

    if update_id is not None:
        return f"telegram:{bot_id}:{update_id}"

    if isinstance(update, Mapping):
        # ``json.dumps`` provides a stable representation so that two
        # equivalent payloads yield the same digest and, consequently, the
        # same idempotency key.
        payload = json.dumps(
            update,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
    else:
        payload = repr(update)

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"telegram:{bot_id}:payload:{digest}"
