"""JSON persistence. The only module that touches the filesystem."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path

from .models import Alarm

DEFAULT_PATH = Path(os.environ.get("ALARM_FILE", Path.home() / ".alarms.json"))


class StoreError(Exception):
    """The alarm file cannot be read or written. Never silently discard it."""


def _to_alarm(item: object) -> Alarm:
    """Build an Alarm from one JSON object, rejecting anything the model can't act on."""
    if not isinstance(item, dict):
        raise ValueError(f"expected an alarm object, got {item!r}")
    alarm = Alarm(**item)  # TypeError on unknown or missing keys
    if not isinstance(alarm.id, str) or not alarm.id:
        raise ValueError(f"alarm has invalid id {alarm.id!r}")
    ints = type(alarm.hour) is int and type(alarm.minute) is int
    if not (ints and 0 <= alarm.hour <= 23 and 0 <= alarm.minute <= 59):
        raise ValueError(f"alarm {alarm.id} has invalid time {alarm.hour!r}:{alarm.minute!r}")
    if not isinstance(alarm.label, str) or not isinstance(alarm.enabled, bool):
        raise ValueError(f"alarm {alarm.id} has invalid label or enabled flag")
    return alarm


def load(path: Path) -> list[Alarm]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
        if not isinstance(raw, list):
            raise ValueError("expected a JSON list of alarms")
        return [_to_alarm(item) for item in raw]
    except (OSError, ValueError, TypeError) as exc:
        raise StoreError(f"Cannot read alarms from {path}: {exc}") from exc


def save(path: Path, alarms: list[Alarm]) -> None:
    # Write to a uniquely named temp file, then rename: a crash cannot leave a
    # truncated file, and two concurrent writers cannot share a temp file.
    try:
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump([asdict(a) for a in alarms], f, indent=2)
        os.replace(tmp, path)
    except OSError as exc:
        raise StoreError(f"Cannot write alarms to {path}: {exc}") from exc
