import json
import stat

from pipeline.store import RawCache, SeriesData, read_series, write_json, write_series


def test_series_file_is_valid_json_with_one_observation_per_line(tmp_path):
    path = tmp_path / "series" / "fred" / "X.json"
    data = SeriesData(
        meta={"frequency": "monthly"},
        columns=["date", "value"],
        rows=[["2026-08-01", 1.5], ["2026-09-01", 2]],
    )
    write_series(path, {"key": "fred/X", "label": "X"}, data)
    text = path.read_text()
    assert json.loads(text)["observations"] == [["2026-08-01", 1.5], ["2026-09-01", 2]]
    assert '["2026-08-01",1.5],\n["2026-09-01",2]' in text
    back = read_series(path)
    assert back.rows == data.rows and back.meta["key"] == "fred/X" and back.columns == ["date", "value"]


def test_written_files_are_world_readable(tmp_path):
    path = tmp_path / "a.json"
    write_json(path, {"a": 1})
    assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_raw_cache_round_trip_and_corrupt_files(tmp_path):
    cache = RawCache(tmp_path)
    assert cache.load("fred", "X") is None
    cache.save("fred", "X", {"observations": [["2026-09-01", "1"]]})
    payload, saved_at = cache.load("fred", "X")
    assert payload["observations"] == [["2026-09-01", "1"]] and saved_at.endswith("Z")
    cache.path("fred", "Y").write_text("{broken")
    assert cache.load("fred", "Y") is None
