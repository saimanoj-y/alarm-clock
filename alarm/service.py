"""Operations on the alarm list. Pure: each takes a list and returns a new one."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from .models import Alarm, is_due, new_alarm


class AlarmError(Exception):
    """A request that cannot be satisfied against the current alarm list."""


def add(alarms: list[Alarm], hour: int, minute: int, label: str = "") -> tuple[list[Alarm], Alarm]:
    for existing in alarms:
        if (existing.hour, existing.minute, existing.label) == (hour, minute, label):
            raise AlarmError(f"Alarm {existing.id} already exists at {existing.time_str} with that label")
    taken = {a.id for a in alarms}
    alarm = new_alarm(hour, minute, label)
    while alarm.id in taken:
        alarm = new_alarm(hour, minute, label)
    return [*alarms, alarm], alarm


def find(alarms: list[Alarm], alarm_id: str) -> Alarm:
    for alarm in alarms:
        if alarm.id == alarm_id:
            return alarm
    raise AlarmError(f"No alarm with id {alarm_id!r}")


def remove(alarms: list[Alarm], alarm_id: str) -> list[Alarm]:
    target = find(alarms, alarm_id)
    return [a for a in alarms if a is not target]


def set_enabled(alarms: list[Alarm], alarm_id: str, enabled: bool) -> list[Alarm]:
    target = find(alarms, alarm_id)
    return [replace(a, enabled=enabled) if a is target else a for a in alarms]


def due(alarms: list[Alarm], since: datetime, now: datetime) -> list[Alarm]:
    return [a for a in alarms if is_due(a, since, now)]
