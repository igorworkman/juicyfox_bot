"""Time utilities for JuicyFox (Plan A).

This module contains helper functions for working with time and
timestamps.  It uses ``datetime`` from the standard library with
timezone awareness (UTC) for all conversions.  The helpers are
intended to standardize how time is represented across the codebase.

Functions provided:

* ``utc_now()`` – current UTC datetime.
* ``to_timestamp(dt)`` – convert a datetime to an integer Unix timestamp.
* ``from_timestamp(ts)`` – convert a timestamp to a UTC datetime.
* ``parse_iso8601(s)`` – parse an ISO‑8601 string into a UTC datetime.
* ``now_timestamp()`` – current UTC timestamp in seconds (alias).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union


def utc_now() -> datetime:
    """Return the current time as a timezone‑aware UTC datetime."""
    return datetime.now(timezone.utc)


def to_timestamp(dt: datetime) -> int:
    """Convert a datetime to an integer Unix timestamp (UTC).

    :param dt: datetime instance; if naive, it is assumed to be in UTC.
    :returns: The integer number of seconds since the Unix epoch.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def from_timestamp(ts: Union[int, float]) -> datetime:
    """Convert a Unix timestamp to a timezone‑aware UTC datetime."""
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


def parse_iso8601(s: str) -> datetime:
    """Parse an ISO‑8601 formatted string into a UTC datetime.

    This leverages ``datetime.fromisoformat`` and normalizes the
    resulting datetime to UTC.  If the string lacks timezone
    information, UTC is assumed.  ISO8601 strings ending with 'Z'
    (e.g. ``2025-08-22T13:45:00Z``) are treated as UTC and normalized.
    """
    # Support trailing 'Z' suffix (e.g. "2025-08-22T13:45:00Z") by replacing with +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_timestamp() -> int:
    """Shortcut: return the current UTC time as a Unix timestamp.

    This is equivalent to ``to_timestamp(utc_now())`` and provided as a
    convenience function for calling code that needs the current time in
    seconds.
    """
    return to_timestamp(utc_now())
