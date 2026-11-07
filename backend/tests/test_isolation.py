"""
backend/tests/test_isolation.py
================================================================================
Guards for the test sandbox itself. If these fail, no other test result can be trusted.
"""

import json
import os
from pathlib import Path

import pytest

import scripts.collector as collector
from app.core.config import settings

SEED_DIR = Path(__file__).parent / "fixtures" / "seed"


def test_seed_catalog_keeps_its_16_policies():
    """The seed is frozen. Other tests rely on it, so it must not be refreshed from data/."""
    with open(SEED_DIR / "welfare_catalog.json", "r", encoding="utf-8") as f:
        catalog = json.load(f)
    assert len(catalog["policies"]) == 16


def test_storage_paths_stay_outside_live_data():
    """Fails if any storage path used during a test points into the real data/ folder."""
    live_dir = settings.BASE_DIR / "data"
    storage_paths = [
        settings.CATALOG_PATH, settings.SYNC_PATH, settings.REGIONS_PATH,
        settings.QUARANTINE_PATH, settings.STAGING_PATH, settings.CHANGELOGS_DIR,
        os.environ["CATALOG_PATH"], os.environ["QUARANTINE_PATH"], os.environ["CHANGELOGS_DIR"],
        collector.CATALOG_PATH, collector.SYNC_PATH, collector.DATA_DIR,
    ]

    # TODO(human): assert that no path in storage_paths sits inside live_dir.
    pytest.fail("TODO(human): write the check, then delete this line")
