import pytest

from alarm import store
from alarm.models import Alarm


def test_missing_file_is_empty(tmp_path):
    assert store.load(tmp_path / "none.json") == []


def test_round_trip_leaves_no_temp_files(tmp_path):
    path = tmp_path / "alarms.json"
    alarms = [Alarm("ab12", 7, 30, "wake"), Alarm("cd34", 22, 0, enabled=False)]
    store.save(path, alarms)
    assert store.load(path) == alarms
    assert list(tmp_path.iterdir()) == [path]


GOOD = '{"id":"x","hour":7,"minute":30,"label":"","enabled":true}'


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "{}",
        "[1]",
        '[{"id": "x"}]',
        '[{"id":"x","hour":1,"minute":2,"extra":true}]',
        GOOD.replace('"hour":7', '"hour":25'),
        GOOD.replace('"minute":30', '"minute":60'),
        GOOD.replace('"hour":7', '"hour":"7"'),
        GOOD.replace('"hour":7', '"hour":true'),
        GOOD.replace('"id":"x"', '"id":5'),
        GOOD.replace('"enabled":true', '"enabled":"yes"'),
    ],
)
def test_corrupt_file_raises_instead_of_discarding(tmp_path, content):
    path = tmp_path / "alarms.json"
    path.write_text(content if content.startswith(("[", "{", "n")) else f"[{content}]")
    original = path.read_text()
    with pytest.raises(store.StoreError, match=str(path)):
        store.load(path)
    assert path.read_text() == original


def test_load_wraps_os_errors(tmp_path):
    with pytest.raises(store.StoreError, match="Cannot read"):
        store.load(tmp_path)  # a directory, not a file


def test_save_wraps_os_errors(tmp_path):
    with pytest.raises(store.StoreError, match="Cannot write"):
        store.save(tmp_path / "missing" / "alarms.json", [])
