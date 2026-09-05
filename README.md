# alarm

A small command-line alarm clock. Standard library only, Python 3.10+.

Alarms are a time of day. Each fires at its next occurrence while `alarm watch`
is running, then switches itself off. Alarms persist in a JSON file so they
survive restarts.

## Run

```sh
python3 -m alarm add 07:30 -l "wake up"
python3 -m alarm list
python3 -m alarm watch
```

Run the tests with `python3 -m pytest -q`.

## Commands

| Command | What it does |
|---------|--------------|
| `add HH:MM [-l LABEL]` | Add an alarm. A time already passed today schedules for tomorrow. |
| `list` | Show alarms sorted by time with id, state, and label. |
| `remove ID` | Delete an alarm. |
| `enable ID` / `disable ID` | Toggle an alarm without deleting it. |
| `watch [--interval SECONDS]` | Wait in the foreground and ring alarms as they come due. Ctrl+C stops it. |

Ids are short hex strings shown by `add` and `list`. Times are 24-hour, two
digits each. Adding the same time with the same label twice is rejected; the
same time with a different label is allowed.

Alarms live in `~/.alarms.json`. Override with `--file PATH` before the
command, or the `ALARM_FILE` environment variable.

Exit codes: 0 success, 1 for a request that can't be satisfied (unknown id,
duplicate, unreadable file), 2 for a usage error.

## How firing works

`watch` polls every five seconds. On each tick it reloads the file, so alarms
added or toggled from another terminal are picked up without a restart. An
alarm is due when its time of day falls inside the window since the previous
tick, so each fires exactly once even if the machine slept past the minute.
The alarm is saved as disabled before it rings, so a crash can't ring it twice.

Ringing prints a banner and the terminal bell. Many terminals mute the bell,
so treat the banner as the alert.

## Design notes

Four modules, each with one job:

- `models.py`: the `Alarm` dataclass, time parsing, and the two scheduling
  rules. Pure functions; the current time is always passed in.
- `service.py`: add, remove, toggle, and due-alarm selection over a list.
  Takes a list, returns a new one.
- `store.py`: JSON load and save. Validates every field on load and refuses to
  overwrite a file it can't read. Saves via a unique temp file and rename.
- `cli.py`: argument parsing, output, and the watch loop. The clock, sleep,
  ringer, and output streams are injectable, so the whole loop is tested with
  fake timestamps and no waiting.

Polling was chosen over sleeping until the next alarm because it is simpler to
reason about and stays correct when the file changes underneath it.

## Known limitations

- Alarms ring only while `watch` is running. There is no background daemon.
- Local naive time. On a daylight-saving transition a firing can shift by an
  hour that day.
- No file locking. Two processes writing at the same instant can lose one
  update. Single user, one writer at a time, is the assumed use.
- An alarm added within a few seconds of its own minute may ring immediately
  even though `add` reported tomorrow, if `watch` is already running.
- One-shot only. Re-enable an alarm to use it again.

## Possible extensions

Daily repeat (skip the auto-disable), snooze, relative times like `+20m`, and
sound playback through the pluggable ringer. Each is deliberately out of scope.
