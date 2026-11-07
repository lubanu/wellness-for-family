"""
backend/tests/test_source_store.py
================================================================================
Tests for safe record storage. The promises under test:
an unchanged run changes nothing, and a bad run writes nothing.
"""

from datetime import datetime, timezone
import json

import pytest

from scripts.source_store import (
    SafetyLimits,
    StoreError,
    StorePaths,
    UnsafeSync,
    compare,
    read_records,
    serialize_records,
    sync,
)

NOW = datetime(2026, 11, 8, tzinfo=timezone.utc)


def rows(count, prefix="gov24", **extra):
    return [{"id": f"{prefix}:{i:04d}", "title": f"복지 {i}", **extra} for i in range(count)]


@pytest.fixture
def paths(tmp_path):
    base = tmp_path / "store"
    return StorePaths(records=base / "gov24.jsonl", absence=base / "absence.json", changelog_dir=base / "changelogs")


def snapshot(paths):
    """Every stored file and its contents."""
    base = paths.records.parent
    if not base.exists():
        return {}
    return {path.relative_to(base): path.read_text(encoding="utf-8") for path in base.rglob("*") if path.is_file()}


def events(paths):
    log = paths.changelog_dir / "2026-11.json"
    return json.loads(log.read_text(encoding="utf-8"))["events"] if log.exists() else []


# ---------------------------------------------------------------- stable files
def test_output_does_not_depend_on_input_order():
    a = {"gov24:2": {"id": "gov24:2", "title": "둘", "org": "기관"}, "gov24:1": {"title": "하나", "id": "gov24:1"}}
    b = {"gov24:1": {"id": "gov24:1", "title": "하나"}, "gov24:2": {"org": "기관", "title": "둘", "id": "gov24:2"}}
    assert serialize_records(a) == serialize_records(b)


def test_one_record_per_line_with_readable_korean():
    text = serialize_records({"gov24:1": {"id": "gov24:1", "title": "부모급여"}})
    assert text == '{"id":"gov24:1","title":"부모급여"}\n'


def test_records_survive_a_round_trip(paths):
    sync(rows(3), paths, now=NOW)
    assert read_records(paths.records) == {row["id"]: row for row in rows(3)}


def test_second_identical_run_changes_nothing(paths):
    first = sync(rows(20), paths, now=NOW)
    before = snapshot(paths)
    second = sync(list(reversed(rows(20))), paths, now=datetime(2026, 11, 9, tzinfo=timezone.utc))
    assert first.files_written
    assert second.files_written == []
    assert second.changes.any is False
    assert snapshot(paths) == before


# ---------------------------------------------------------------- bad data stops
def test_truncated_run_stops_and_writes_nothing(paths):
    sync(rows(100), paths, now=NOW)
    before = snapshot(paths)
    with pytest.raises(UnsafeSync) as stopped:
        sync(rows(40), paths, now=NOW)
    assert "60 of 100 stored records are missing" in str(stopped.value)
    assert snapshot(paths) == before


def test_small_drop_is_allowed(paths):
    sync(rows(100), paths, now=NOW)
    assert sync(rows(95), paths, now=NOW).total == 100


def test_empty_fetch_stops_even_on_a_first_run(paths):
    with pytest.raises(UnsafeSync, match="no records were fetched"):
        sync([], paths, now=NOW)
    assert snapshot(paths) == {}


def test_quarantine_spike_stops(paths):
    with pytest.raises(UnsafeSync, match="10 of 100 records were quarantined"):
        sync(rows(90), paths, quarantined=10, now=NOW)


def test_mass_change_stops(paths):
    sync(rows(100), paths, now=NOW)
    changed = [{**row, "title": "바뀜"} if i < 40 else row for i, row in enumerate(rows(100))]
    with pytest.raises(UnsafeSync, match="40 of 100 stored records changed at once"):
        sync(changed, paths, now=NOW)


def test_expected_mass_change_can_pass_with_relaxed_limits(paths):
    sync(rows(100), paths, now=NOW)
    changed = [{**row, "title": "바뀜"} for row in rows(100)]
    report = sync(changed, paths, limits=SafetyLimits(max_changed_ratio=1.0), now=NOW)
    assert len(report.changes.changed) == 100


def test_missing_checked_record_stops_even_when_the_drop_is_small(paths):
    sync(rows(100), paths, now=NOW)
    with pytest.raises(UnsafeSync, match="checked records are missing: gov24:0099"):
        sync(rows(99), paths, required_ids=["gov24:0099"], now=NOW)


def test_repeated_id_stops(paths):
    with pytest.raises(UnsafeSync, match="appears more than once"):
        sync(rows(2) + rows(1), paths, now=NOW)


def test_record_without_id_stops(paths):
    with pytest.raises(UnsafeSync, match="a record has no id"):
        sync([{"title": "이름만 있음"}], paths, now=NOW)


def test_every_problem_is_reported_at_once(paths):
    sync(rows(100), paths, now=NOW)
    with pytest.raises(UnsafeSync) as stopped:
        sync(rows(50), paths, quarantined=50, now=NOW)
    assert len(stopped.value.reasons) == 2


def test_damaged_store_stops_instead_of_being_overwritten(paths):
    sync(rows(3), paths, now=NOW)
    paths.records.write_text('{"id":"gov24:0"}\nnot json\n', encoding="utf-8")
    with pytest.raises(StoreError, match="line 2 is damaged"):
        sync(rows(3), paths, now=NOW)
    assert "not json" in paths.records.read_text(encoding="utf-8")


def test_damaged_changelog_stops_instead_of_being_reset(paths):
    sync(rows(3), paths, now=NOW)
    (paths.changelog_dir / "2026-11.json").write_text("not json", encoding="utf-8")
    with pytest.raises(StoreError):
        sync(rows(4), paths, now=NOW)


# ---------------------------------------------------------------- retiring
def test_record_retires_only_after_three_full_runs_without_it(paths):
    sync(rows(100), paths, now=NOW)

    first = sync(rows(99), paths, now=NOW)
    second = sync(rows(99), paths, now=NOW)
    assert (first.total, second.total) == (100, 100)
    assert second.waiting_to_retire == 1
    assert "gov24:0099" in read_records(paths.records)

    third = sync(rows(99), paths, now=NOW)
    assert third.total == 99
    assert third.changes.retired == ["gov24:0099"]
    assert third.waiting_to_retire == 0
    assert "gov24:0099" not in read_records(paths.records)


def test_returning_record_resets_its_count(paths):
    sync(rows(100), paths, now=NOW)
    sync(rows(99), paths, now=NOW)
    sync(rows(99), paths, now=NOW)
    assert sync(rows(100), paths, now=NOW).waiting_to_retire == 0
    assert sync(rows(99), paths, now=NOW).waiting_to_retire == 1


def test_partial_run_never_counts_as_absence(paths):
    sync(rows(100), paths, now=NOW)
    for _ in range(5):
        report = sync(rows(10), paths, full_run=False, now=NOW)
    assert report.total == 100
    assert report.waiting_to_retire == 0


def test_partial_run_still_saves_what_it_fetched(paths):
    sync(rows(10), paths, now=NOW)
    sync([{"id": "gov24:0003", "title": "바뀜"}], paths, full_run=False, now=NOW)
    assert read_records(paths.records)["gov24:0003"]["title"] == "바뀜"
    assert len(read_records(paths.records)) == 10


# ---------------------------------------------------------------- changelog
def test_compare_names_the_changed_fields():
    old = {"a": {"id": "a", "title": "x", "org": "y"}}
    new = {"a": {"id": "a", "title": "z", "org": "y"}, "b": {"id": "b"}}
    changes = compare(old, new)
    assert changes.added == ["b"]
    assert changes.changed == {"a": ["title"]}


def test_one_event_per_run(paths):
    sync(rows(10), paths, now=NOW)
    updated = [{**row, "title": "바뀜"} if i == 0 else row for i, row in enumerate(rows(11))]
    sync(updated, paths, now=NOW)
    assert len(events(paths)) == 2
    assert events(paths)[1]["added"] == ["gov24:0010"]
    assert events(paths)[1]["changed"] == {"gov24:0000": ["title"]}


def test_first_run_logs_a_count_instead_of_every_id(paths):
    sync(rows(500), paths, now=NOW)
    assert events(paths)[0]["first_run_added_count"] == 500
    assert "added" not in events(paths)[0]


def test_no_temp_files_are_left_behind(paths):
    sync(rows(5), paths, now=NOW)
    assert [path for path in paths.records.parent.rglob("*") if ".tmp_" in path.name] == []
