"""Alarm domain model and time handling.

All functions here are pure: the current time is always passed in, never read
from the system clock. That keeps every time rule testable with fixed values.
"""
from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

_TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")


@dataclass(frozen=True)
class Alarm:
    id: str
    hour: int
    minute: int
    label: str = ""
    enabled: bool = True

    @property
    def time_str(self) -> str:
        return f"{self.hour:02d}:{self.minute:02d}"


def parse_time(text: str) -> tuple[int, int]:
    """Parse strict 24-hour 'HH:MM' into (hour, minute).

    Raises ValueError with a user-facing message on malformed or out-of-range input.
    """
    match = _TIME_RE.match(text.strip())
    if not match:
        raise ValueError(f"Invalid time {text!r}: expected HH:MM (24-hour), e.g. 07:30")
    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time {text!r}: hour must be 00-23 and minute 00-59")
    return hour, minute


def new_alarm(hour: int, minute: int, label: str = "") -> Alarm:
    """Create an enabled alarm with a short random id (users type these)."""
    return Alarm(id=secrets.token_hex(2), hour=hour, minute=minute, label=label)


def next_fire_time(alarm: Alarm, after: datetime) -> datetime:
    """First occurrence of the alarm's time of day strictly after `after`.

    An alarm whose time has already passed today (or equals `after` to the
    minute) resolves to tomorrow. Seconds are ignored: alarms have minute
    precision.
    """
    candidate = after.replace(
        hour=alarm.hour, minute=alarm.minute, second=0, microsecond=0
    )
    if candidate <= after:
        candidate += timedelta(days=1)
    return candidate


def is_due(alarm: Alarm, since: datetime, now: datetime) -> bool:
    """True if an enabled alarm has an occurrence in the window (since, now].

    The watch loop passes the previous check time as `since`, so an alarm is
    reported exactly once even if the process slept past its minute. A gap
    longer than a day still yields a single firing.
    """
    if not alarm.enabled:
        return False
    return next_fire_time(alarm, since) <= now
