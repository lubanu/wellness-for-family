#!/usr/bin/env python3
"""
scripts/sync_to_supabase.py
Optional synchronization script to push welfare policies into Supabase Free Tier.
Uses Supabase PostgREST API with zero external dependencies (Python standard library only).
"""

import os
import sys
import json
import urllib.request
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(ROOT_DIR, "data", "welfare_catalog.json")


def log(msg: str):
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    print(f"[{now_str}] {msg}", flush=True)


def main():
    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")

    if not supabase_url or not supabase_key:
        log("Notice: SUPABASE_URL or SUPABASE_KEY not provided.")
        log("Skipping Supabase cloud push. Utilizing GitOps Flat JSON storage (100% Free).")
        return

    if not os.path.exists(CATALOG_PATH):
        log(f"Error: Catalog file not found at {CATALOG_PATH}")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    policies = catalog.get("policies", [])
    log(f"Upserting {len(policies)} policies into Supabase ({supabase_url})...")

    endpoint = f"{supabase_url.rstrip('/')}/rest/v1/welfare_policies?on_conflict=id"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }

    req = urllib.request.Request(endpoint, data=json.dumps(policies).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            log("Successfully synced policies to Supabase PostgreSQL database!")
    except Exception as e:
        log(f"Supabase sync failed: {e}")


if __name__ == "__main__":
    main()
