"""
backend/app/services/versioning.py
================================================================================
GitOps Versioning, Field-Level Recursive Diff, and Monthly Partitioned Changelog.
Enforces auditability, zero-delta idempotency, and non-pollution of production.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from app.core.config import settings


EXCLUDED_DIFF_FIELDS = {
    "last_verified_at",
    "updated_at",
    "created_at",
    "version",
    "fingerprint"
}


def compute_field_diff(
    old_dict: Optional[Dict[str, Any]],
    new_dict: Optional[Dict[str, Any]],
    prefix: str = ""
) -> List[Dict[str, Any]]:
    """
    Recursively compute field-level differences between two policy dictionaries.
    Excludes transient timestamps (last_verified_at, updated_at) and version counter.
    """
    diffs: List[Dict[str, Any]] = []
    old_d = old_dict if isinstance(old_dict, dict) else {}
    new_d = new_dict if isinstance(new_dict, dict) else {}

    all_keys = (set(old_d.keys()) | set(new_d.keys())) - EXCLUDED_DIFF_FIELDS

    for key in sorted(all_keys):
        field_path = f"{prefix}.{key}" if prefix else key
        old_val = old_d.get(key)
        new_val = new_d.get(key)

        if isinstance(old_val, dict) and isinstance(new_val, dict):
            diffs.extend(compute_field_diff(old_val, new_val, prefix=field_path))
        elif old_val != new_val:
            diffs.append({
                "field": field_path,
                "old_value": old_val,
                "new_value": new_val
            })

    return diffs


def track_policy_change(
    old_policy: Optional[Dict[str, Any]],
    new_policy: Dict[str, Any],
    author: str = "system",
    change_type: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Compute delta and append audit record into monthly partitioned changelog:
    data/changelogs/YYYY-MM.json
    Returns the created event record, or None if zero delta detected.
    """
    diffs = compute_field_diff(old_policy, new_policy)

    # Idempotent sync guard: if old policy exists and 0 diffs, do not record duplicate event
    if old_policy is not None and len(diffs) == 0:
        return None

    policy_id = new_policy.get("id") or (old_policy.get("id") if old_policy else "unknown")
    determined_change_type = change_type or ("NEW_POLICY" if old_policy is None else "POLICY_UPDATED")

    event = {
        "event_id": f"evt_{policy_id}_{int(datetime.now(timezone.utc).timestamp())}_{uuid.uuid4().hex[:6]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "policy_id": policy_id,
        "change_type": determined_change_type,
        "author": author,
        "version": new_policy.get("version", 1),
        "diffs": diffs
    }

    # Resolve changelogs directory
    changelogs_dir_str = os.getenv(
        "CHANGELOGS_DIR",
        getattr(settings, "CHANGELOGS_DIR", str(settings.BASE_DIR / "data" / "changelogs"))
    )
    changelogs_dir = Path(changelogs_dir_str)
    changelogs_dir.mkdir(parents=True, exist_ok=True)

    now_partition = datetime.now().strftime("%Y-%m")
    partition_file = changelogs_dir / f"{now_partition}.json"

    cl_data: Dict[str, Any] = {"partition": now_partition, "events": []}
    if partition_file.exists():
        try:
            with open(partition_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "events" in loaded:
                    cl_data = loaded
        except Exception:
            cl_data = {"partition": now_partition, "events": []}

    cl_data["events"].append(event)

    # Write atomically
    temp_file = partition_file.with_suffix(".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(cl_data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, partition_file)

    return event
