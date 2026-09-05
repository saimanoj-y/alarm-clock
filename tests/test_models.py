from dataclasses import replace
from datetime import datetime

import pytest

from alarm.models import Alarm, is_due, new_alarm, next_fire_time, parse_time


# --- parse_time -----------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("07:30", (7, 30)),
        ("00:00", (0, 0)),
        ("23:59", (23, 59)),
        ("  09:05 ", (9, 5)),
    ],
)
def test_parse_time_valid(text, expected):
    assert parse_time(text) == expected


@pytest.mark.parametrize(
    "text",
    ["7:30", "07:5", "0730", "noon", "", "07:30:00", "24:00", "23:60", "-1:00", "1a:00"],
)
def test_parse_time_invalid(text):
    with pytest.raises(ValueError, match="Invalid time"):
        parse_time(text)


# --- new_alarm ------------------------------------------------------------

def test_new_alarm_defaults_and_unique_ids():
    a = new_alarm(7, 30, "wake")
    b = new_alarm(7, 30, "wake")
    assert a.enabled and a.label == "wake" and a.time_str == "07:30"
    assert a.id != b.id


def test_alarm_is_immutable():
    a = new_alarm(7, 30)
    with pytest.raises(Exception):
        a.enabled = False  # type: ignore[misc]
    assert replace(a, enabled=False).enabled is False


# --- next_fire_time -------------------------------------------------------

ALARM = Alarm(id="ab12", hour=7, minute=30)


def test_next_fire_time_later_today():
    now = datetime(2026, 9, 4, 6, 0)
    assert next_fire_time(ALARM, now) == datetime(2026, 9, 4, 7, 30)


def test_next_fire_time_rolls_to_tomorrow_when_passed():
    now = datetime(2026, 9, 4, 8, 0)
    assert next_fire_time(ALARM, now) == datetime(2026, 9, 5, 7, 30)


def test_next_fire_time_exact_minute_is_tomorrow():
    # Strictly-after semantics: at 07:30:00 the 07:30 occurrence has started.
    now = datetime(2026, 9, 4, 7, 30, 0)
    assert next_fire_time(ALARM, now) == datetime(2026, 9, 5, 7, 30)


def test_next_fire_time_ignores_seconds_of_reference():
    now = datetime(2026, 9, 4, 7, 29, 59)
    assert next_fire_time(ALARM, now) == datetime(2026, 9, 4, 7, 30)


def test_next_fire_time_crosses_month_boundary():
    now = datetime(2026, 9, 30, 23, 0)
    late = Alarm(id="x", hour=1, minute=0)
    assert next_fire_time(late, now) == datetime(2026, 10, 1, 1, 0)


# --- is_due ---------------------------------------------------------------

def test_is_due_inside_window():
    since = datetime(2026, 9, 4, 7, 29, 55)
    now = datetime(2026, 9, 4, 7, 30, 2)
    assert is_due(ALARM, since, now)


def test_is_due_not_yet():
    since = datetime(2026, 9, 4, 7, 29, 50)
    now = datetime(2026, 9, 4, 7, 29, 58)
    assert not is_due(ALARM, since, now)


def test_is_due_fires_only_once_across_consecutive_checks():
    t0 = datetime(2026, 9, 4, 7, 29, 58)
    t1 = datetime(2026, 9, 4, 7, 30, 1)
    t2 = datetime(2026, 9, 4, 7, 30, 4)
    assert is_due(ALARM, t0, t1)
    assert not is_due(ALARM, t1, t2)


def test_is_due_catches_alarm_skipped_during_long_gap():
    # Process slept from 07:00 to 09:00; the 07:30 alarm must still fire.
    since = datetime(2026, 9, 4, 7, 0)
    now = datetime(2026, 9, 4, 9, 0)
    assert is_due(ALARM, since, now)


def test_is_due_across_midnight():
    midnight_alarm = Alarm(id="m", hour=0, minute=0)
    since = datetime(2026, 9, 4, 23, 59, 58)
    now = datetime(2026, 9, 5, 0, 0, 1)
    assert is_due(midnight_alarm, since, now)


def test_is_due_disabled_never_fires():
    since = datetime(2026, 9, 4, 7, 0)
    now = datetime(2026, 9, 4, 9, 0)
    assert not is_due(replace(ALARM, enabled=False), since, now)
