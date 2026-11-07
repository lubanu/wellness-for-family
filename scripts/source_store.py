#!/usr/bin/env python3
"""
scripts/source_store.py
================================================================================
Safe storage for imported records (P3). It knows nothing about any API, so every
source adapter shares the same protections:

- Sorted JSONL with stable key order, so an unchanged run leaves Git untouched.
- A safety check that runs before any write, so a bad sync can't damage good data.
- A record is retired only after several full runs without it.
- One changelog event per run, written only when something changed.

Records are plain dicts with a unique "id". No per-record timestamps belong here:
they would change every line on every run.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import uuid

Record = Dict[str, Any]


@dataclass(frozen=True)
class SafetyLimits:
    """Each ratio is the largest share allowed before a sync stops."""
    max_missing_ratio: float = 0.05
    max_changed_ratio: float = 0.30
    max_quarantine_ratio: float = 0.05
    retire_after_absent_runs: int = 3


@dataclass(frozen=True)
class StorePaths:
    records: Path
    absence: Path
    changelog_dir: Path


@dataclass
class Changes:
    added: List[str] = field(default_factory=list)
    changed: Dict[str, List[str]] = field(default_factory=dict)
    retired: List[str] = field(default_factory=list)

    @property
    def any(self) -> bool:
        return bool(self.added or self.changed or self.retired)


@dataclass
class SyncReport:
    total: int
    changes: Changes
    waiting_to_retire: int
    files_written: List[str]


class StoreError(Exception):
    """Stored data can't be trusted. Stop rather than overwrite it."""


class UnsafeSync(Exception):
    """The new data looks wrong, so nothing was written."""

    def __init__(self, reasons: List[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


# ------------------------------------------------------------------------------
# Reading and writing
# ------------------------------------------------------------------------------

def read_records(path: Path) -> Dict[str, Record]:
    """A missing file means a first run. A damaged file stops the sync."""
    if not path.exists():
        return {}
    records: Dict[str, Record] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            record = json.loads(line)
            records[record["id"]] = record
        except (ValueError, KeyError, TypeError) as error:
            raise StoreError(f"{path} line {number} is damaged: {error}") from error
    return records


def serialize_records(records: Dict[str, Record]) -> str:
    lines = [json.dumps(records[key], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
             for key in sorted(records)]
    return "".join(f"{line}\n" for line in lines)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as error:
        raise StoreError(f"{path} is damaged: {error}") from error


def serialize_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_files(files: Dict[Path, str]) -> List[str]:
    """Writes every changed file to a temp copy first, then swaps them all in."""
    pending = []
    for path, text in files.items():
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f"{path.name}.tmp_{uuid.uuid4().hex[:6]}")
        temp.write_text(text, encoding="utf-8")
        pending.append((temp, path))
    for temp, path in pending:
        os.replace(temp, path)
    return [str(path) for _, path in pending]


# ------------------------------------------------------------------------------
# Comparing and checking
# ------------------------------------------------------------------------------

def index_rows(rows: Iterable[Record]) -> Tuple[Dict[str, Record], List[str]]:
    """Returns records by id, plus problems such as a missing or repeated id."""
    records: Dict[str, Record] = {}
    problems: List[str] = []
    for row in rows:
        key = row.get("id")
        if not key:
            problems.append("a record has no id")
        elif key in records:
            problems.append(f"id {key} appears more than once")
        else:
            records[key] = row
    return records, problems


def compare(old: Dict[str, Record], fetched: Dict[str, Record]) -> Changes:
    changes = Changes(added=sorted(set(fetched) - set(old)))
    for key in sorted(set(old) & set(fetched)):
        fields = sorted(name for name in set(old[key]) | set(fetched[key])
                        if old[key].get(name) != fetched[key].get(name))
        if fields:
            changes.changed[key] = fields
    return changes


def safety_problems(old: Dict[str, Record], fetched: Dict[str, Record], quarantined: int,
                    required_ids: Iterable[str], full_run: bool, limits: SafetyLimits) -> List[str]:
    """Reasons to stop. An empty list means the sync is safe to write."""
    problems: List[str] = []

    if not fetched:
        problems.append("no records were fetched")

    attempted = len(fetched) + quarantined
    if attempted and quarantined / attempted > limits.max_quarantine_ratio:
        problems.append(f"{quarantined} of {attempted} records were quarantined")

    if full_run:
        not_returned = sorted(set(required_ids) - set(fetched))
        if not_returned:
            problems.append(f"checked records are missing: {', '.join(not_returned[:5])}")

    # A first run has nothing to compare against.
    if old:
        missing = len(set(old) - set(fetched))
        if full_run and missing / len(old) > limits.max_missing_ratio:
            problems.append(f"{missing} of {len(old)} stored records are missing from this run")
        changed = len(compare(old, fetched).changed)
        if changed / len(old) > limits.max_changed_ratio:
            problems.append(f"{changed} of {len(old)} stored records changed at once")

    return problems


def update_absence(old: Dict[str, Record], fetched: Dict[str, Record], absence: Dict[str, int],
                   full_run: bool, limits: SafetyLimits) -> Tuple[Dict[str, Record], List[str], Dict[str, int]]:
    """Returns (records to keep despite being absent, retired ids, new absence counts)."""
    if not full_run:
        kept = {key: record for key, record in old.items() if key not in fetched}
        return kept, [], {key: count for key, count in absence.items() if key not in fetched}

    kept: Dict[str, Record] = {}
    retired: List[str] = []
    counts: Dict[str, int] = {}
    for key in sorted(set(old) - set(fetched)):
        count = absence.get(key, 0) + 1
        if count >= limits.retire_after_absent_runs:
            retired.append(key)
        else:
            kept[key] = old[key]
            counts[key] = count
    return kept, retired, counts


def build_event(changes: Changes, first_run: bool, now: datetime) -> Record:
    event: Record = {"timestamp": now.isoformat(), "change_type": "SOURCE_SYNC"}
    if first_run:
        # A first import can add thousands of records, so only the count is kept.
        event["first_run_added_count"] = len(changes.added)
    else:
        event.update(added=changes.added, changed=changes.changed, retired=changes.retired)
    return event


# ------------------------------------------------------------------------------
# Sync
# ------------------------------------------------------------------------------

def sync(rows: Iterable[Record], paths: StorePaths, quarantined: int = 0, required_ids: Iterable[str] = (),
         full_run: bool = True, limits: SafetyLimits = SafetyLimits(), now: Optional[datetime] = None) -> SyncReport:
    """
    Stores one run's records. Raises UnsafeSync and writes nothing if the data looks wrong.
    Set full_run=False when only part of a source was fetched: absent records then stay untouched.
    """
    now = now or datetime.now(timezone.utc)
    required = list(required_ids)
    old = read_records(paths.records)
    absence = read_json(paths.absence, {})

    fetched, problems = index_rows(rows)
    problems += safety_problems(old, fetched, quarantined, required, full_run, limits)
    if problems:
        raise UnsafeSync(problems)

    changes = compare(old, fetched)
    kept, changes.retired, new_absence = update_absence(old, fetched, absence, full_run, limits)
    records = {**kept, **fetched}

    files = {paths.records: serialize_records(records)}
    if new_absence or paths.absence.exists():
        files[paths.absence] = serialize_json(new_absence)
    if changes.any:
        log_path = paths.changelog_dir / f"{now.strftime('%Y-%m')}.json"
        log = read_json(log_path, {"partition": now.strftime("%Y-%m"), "events": []})
        log["events"].append(build_event(changes, not old, now))
        files[log_path] = serialize_json(log)

    return SyncReport(
        total=len(records),
        changes=changes,
        waiting_to_retire=len(new_absence),
        files_written=write_files(files),
    )
