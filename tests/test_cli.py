import io
from datetime import datetime

import pytest

from alarm import store
from alarm.cli import main

SIX_AM = datetime(2026, 9, 4, 6, 0)


class Cli:
    """Runs the CLI against a temp file with a fixed clock and captured streams."""

    def __init__(self, tmp_path):
        self.path = tmp_path / "alarms.json"

    def run(self, *args, clock=lambda: SIX_AM, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        code = main(["--file", str(self.path), *args], clock=clock, out=out, err=err, **kwargs)
        return code, out.getvalue(), err.getvalue()

    def only_alarm(self):
        (alarm,) = store.load(self.path)
        return alarm


@pytest.fixture
def cli(tmp_path):
    return Cli(tmp_path)


# --- argument validation (argparse exits with 2) --------------------------

@pytest.mark.parametrize("argv", [[], ["bogus"], ["add"], ["remove"], ["add", "07:30", "extra"]])
def test_usage_errors_exit_2(cli, argv, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.run(*argv)
    assert exc.value.code == 2
    assert "usage:" in capsys.readouterr().err


@pytest.mark.parametrize("bad_time", ["7:30", "25:00", "noon"])
def test_add_invalid_time_shows_domain_message(cli, bad_time, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.run("add", bad_time)
    assert exc.value.code == 2
    assert "Invalid time" in capsys.readouterr().err


@pytest.mark.parametrize("interval", ["0", "-5", "soon"])
def test_watch_rejects_bad_interval(cli, interval, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.run("watch", "--interval", interval)
    assert exc.value.code == 2
    assert "nterval" in capsys.readouterr().err


# --- commands -------------------------------------------------------------

def test_add_then_list(cli):
    code, out, _ = cli.run("add", "07:30", "-l", "wake")
    assert code == 0
    assert "next fires Fri 2026-09-04 07:30" in out
    code, out, _ = cli.run("list")
    assert code == 0
    alarm = cli.only_alarm()
    assert f"{alarm.id}  07:30  on    wake" in out


def test_add_past_time_reports_tomorrow(cli):
    _, out, _ = cli.run("add", "05:00")
    assert "next fires Sat 2026-09-05 05:00" in out


def test_add_duplicate_is_rejected(cli):
    cli.run("add", "07:30")
    code, _, err = cli.run("add", "07:30")
    assert code == 1
    assert "already exists" in err
    assert len(store.load(cli.path)) == 1


def test_list_empty(cli):
    assert cli.run("list") == (0, "No alarms.\n", "")


def test_disable_enable_remove(cli):
    cli.run("add", "07:30")
    alarm_id = cli.only_alarm().id

    assert cli.run("disable", alarm_id)[0] == 0
    assert cli.only_alarm().enabled is False
    assert "off" in cli.run("list")[1]

    assert cli.run("enable", alarm_id)[0] == 0
    assert cli.only_alarm().enabled is True

    assert cli.run("remove", alarm_id)[0] == 0
    assert store.load(cli.path) == []


@pytest.mark.parametrize("command", ["remove", "enable", "disable"])
def test_unknown_id_exits_1(cli, command):
    code, _, err = cli.run(command, "zzzz")
    assert code == 1
    assert "No alarm with id 'zzzz'" in err


def test_corrupt_store_is_reported_not_overwritten(cli):
    cli.path.write_text("garbage")
    code, _, err = cli.run("add", "07:30")
    assert code == 1
    assert "Cannot read alarms" in err
    assert cli.path.read_text() == "garbage"


# --- watch loop, driven by a fake clock and fake sleep ----------------------

def test_watch_rings_once_disables_and_stops_on_ctrl_c(cli):
    cli.run("add", "07:30", "-l", "wake")
    ticks = iter([
        datetime(2026, 9, 4, 7, 29, 58),  # start
        datetime(2026, 9, 4, 7, 30, 1),   # tick 1: due
        datetime(2026, 9, 4, 7, 30, 6),   # tick 2: must not re-ring
    ])
    sleeps: list[float] = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise KeyboardInterrupt

    rung = []
    code, out, err = cli.run(
        "watch", "--interval", "5", clock=lambda: next(ticks), sleep=fake_sleep, ring=rung.append
    )
    assert code == 0 and err == ""
    assert "Watching 1 enabled alarm(s)" in out
    assert "Stopped watching. Your alarms are saved." in out and "Goodbye!" in out
    assert [a.label for a in rung] == ["wake"]
    assert sleeps == [5.0, 5.0, 5.0]
    assert cli.only_alarm().enabled is False


def test_watch_sees_alarm_added_by_another_process(cli):
    ticks = iter([datetime(2026, 9, 4, 7, 29, 58), datetime(2026, 9, 4, 7, 30, 1)])
    calls = 0

    def sleep_then_add(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            cli.run("add", "07:30", "-l", "late add")  # simulates a second terminal
        else:
            raise KeyboardInterrupt

    rung = []
    code, out, _ = cli.run("watch", clock=lambda: next(ticks), sleep=sleep_then_add, ring=rung.append)
    assert code == 0
    assert "Watching 0 enabled alarm(s)" in out
    assert [a.label for a in rung] == ["late add"]


def test_watch_survives_unwritable_store_with_message(cli):
    cli.run("add", "07:30")
    ticks = iter([datetime(2026, 9, 4, 7, 29), datetime(2026, 9, 4, 7, 31)])
    cli.path.write_text("garbage")
    code, _, err = cli.run("watch", clock=lambda: next(ticks), sleep=lambda _: None)
    assert code == 1
    assert "Cannot read alarms" in err


def test_watch_default_ring_prints_banner_and_bell(cli):
    cli.run("add", "07:30", "-l", "wake")
    ticks = iter([datetime(2026, 9, 4, 7, 29), datetime(2026, 9, 4, 7, 31)])

    def sleep_once_then_stop(_):
        if not hasattr(sleep_once_then_stop, "called"):
            sleep_once_then_stop.called = True
            return
        raise KeyboardInterrupt

    _, out, _ = cli.run("watch", clock=lambda: next(ticks), sleep=sleep_once_then_stop)
    assert "\a" in out and "*** ALARM 07:30 wake" in out
