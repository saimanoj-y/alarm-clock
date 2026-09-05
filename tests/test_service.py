from datetime import datetime

import pytest

from alarm import service
from alarm.models import Alarm


def test_add_appends_without_mutating_input():
    original: list[Alarm] = []
    alarms, alarm = service.add(original, 7, 30, "wake")
    assert original == []
    assert alarms == [alarm]


def test_add_rejects_same_time_and_label():
    alarms, _ = service.add([], 7, 30, "wake")
    with pytest.raises(service.AlarmError, match="already exists"):
        service.add(alarms, 7, 30, "wake")


def test_add_allows_same_time_with_different_label():
    alarms, _ = service.add([], 7, 30, "wake")
    alarms, _ = service.add(alarms, 7, 30, "pills")
    assert len(alarms) == 2


def test_add_avoids_id_collision(monkeypatch):
    ids = iter(["dup", "dup", "ok"])
    monkeypatch.setattr(service, "new_alarm", lambda h, m, l="": Alarm(next(ids), h, m, l))
    alarms, _ = service.add([], 7, 30)
    _, second = service.add(alarms, 8, 0)
    assert second.id == "ok"


def test_remove_and_unknown_id():
    alarms, alarm = service.add([], 7, 30)
    assert service.remove(alarms, alarm.id) == []
    with pytest.raises(service.AlarmError, match="No alarm with id"):
        service.remove(alarms, "nope")


def test_set_enabled_round_trip():
    alarms, alarm = service.add([], 7, 30)
    alarms = service.set_enabled(alarms, alarm.id, False)
    assert alarms[0].enabled is False
    alarms = service.set_enabled(alarms, alarm.id, True)
    assert alarms[0].enabled is True


def test_due_returns_only_due_alarms():
    alarms = [
        Alarm("a", 7, 30),
        Alarm("b", 7, 30, enabled=False),
        Alarm("c", 9, 0),
    ]
    since, now = datetime(2026, 9, 4, 7, 29), datetime(2026, 9, 4, 7, 31)
    assert [a.id for a in service.due(alarms, since, now)] == ["a"]
