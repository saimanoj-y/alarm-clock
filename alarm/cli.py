"""Command-line interface. Owns argument parsing, output, the clock, and the watch loop.

`main` accepts the clock, sleep, ringer, and output streams as keyword arguments
so the whole CLI, including `watch`, can be driven from tests without real time.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, TextIO

from . import service, store
from .models import Alarm, next_fire_time, parse_time

Clock = Callable[[], datetime]
Ringer = Callable[[Alarm], None]


def _time_arg(text: str) -> tuple[int, int]:
    try:
        return parse_time(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _positive_seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid interval {text!r}: expected a number of seconds")
    if value <= 0:
        raise argparse.ArgumentTypeError("Interval must be greater than 0 seconds")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alarm",
        description="A small alarm clock. Alarms ring only while `alarm watch` is running.",
    )
    parser.add_argument(
        "--file", type=Path, default=store.DEFAULT_PATH,
        help="alarm storage file (default: %(default)s)",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    add = sub.add_parser("add", help="add an alarm for a time of day")
    add.add_argument("time", type=_time_arg, metavar="HH:MM", help="24-hour time, e.g. 07:30")
    add.add_argument("-l", "--label", default="", help="optional description")

    sub.add_parser("list", help="list alarms")
    for name, text in [("remove", "delete an alarm"), ("enable", "enable an alarm"), ("disable", "disable an alarm")]:
        sub.add_parser(name, help=text).add_argument("id", help="alarm id from `alarm list`")

    watch = sub.add_parser("watch", help="wait in the foreground and ring alarms as they come due")
    watch.add_argument(
        "--interval", type=_positive_seconds, default=5.0, metavar="SECONDS",
        help="seconds between checks (default: %(default)s)",
    )
    return parser


def default_ring(alarm: Alarm, out: TextIO) -> None:
    label = f" {alarm.label}" if alarm.label else ""
    print(f"\a\n*** ALARM {alarm.time_str}{label} (id {alarm.id}) ***\n", file=out, flush=True)


def print_list(alarms: list[Alarm], out: TextIO) -> None:
    if not alarms:
        print("No alarms.", file=out)
        return
    print(f"{'ID':<6}{'TIME':<7}{'STATE':<6}LABEL", file=out)
    for a in sorted(alarms, key=lambda a: (a.hour, a.minute, a.id)):
        print(f"{a.id:<6}{a.time_str:<7}{'on' if a.enabled else 'off':<6}{a.label}", file=out)


def watch(path: Path, interval: float, clock: Clock, sleep: Callable[[float], None], ring: Ringer, out: TextIO) -> None:
    since = clock()
    enabled = sum(a.enabled for a in store.load(path))
    print(f"Watching {enabled} enabled alarm(s) in {path}. Press Ctrl+C to stop.", file=out, flush=True)
    while True:
        sleep(interval)
        now = clock()
        alarms = store.load(path)  # reload each tick so edits from another terminal are seen
        for alarm in service.due(alarms, since, now):
            alarms = service.set_enabled(alarms, alarm.id, False)
            store.save(path, alarms)  # persist before ringing so a crash cannot re-ring it
            ring(alarm)
        since = now


def main(
    argv: list[str] | None = None,
    *,
    clock: Clock = datetime.now,
    sleep: Callable[[float], None] = time.sleep,
    ring: Ringer | None = None,
    out: TextIO = sys.stdout,
    err: TextIO = sys.stderr,
) -> int:
    args = build_parser().parse_args(argv)
    path: Path = args.file
    try:
        if args.command == "watch":
            watch(path, args.interval, clock, sleep, ring or (lambda a: default_ring(a, out)), out)
            return 0
        alarms = store.load(path)
        if args.command == "add":
            hour, minute = args.time
            alarms, alarm = service.add(alarms, hour, minute, args.label)
            store.save(path, alarms)
            fires = next_fire_time(alarm, clock())
            print(f"Added alarm {alarm.id} at {alarm.time_str}, next fires {fires:%a %Y-%m-%d %H:%M}", file=out)
        elif args.command == "list":
            print_list(alarms, out)
        elif args.command == "remove":
            store.save(path, service.remove(alarms, args.id))
            print(f"Removed alarm {args.id}", file=out)
        else:  # enable / disable
            enabled = args.command == "enable"
            store.save(path, service.set_enabled(alarms, args.id, enabled))
            print(f"{'Enabled' if enabled else 'Disabled'} alarm {args.id}", file=out)
        return 0
    except (service.AlarmError, store.StoreError) as exc:
        print(f"error: {exc}", file=err)
        return 1
    except KeyboardInterrupt:
        print(
            "\nStopped watching. Your alarms are saved.\n"
            "Run `python3 -m alarm watch` again whenever you want them to ring.\n"
            "Thanks for using alarm. Goodbye!",
            file=out,
        )
        return 0
