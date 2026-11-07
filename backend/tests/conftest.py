"""
Pytest isolation configuration and fixtures for WelFamily Backend & Pipeline Tests.
Tests run on frozen copies in tests/fixtures/seed/. They never read or write the live data/ folder,
so results stay the same whatever the daily sync has written there.
"""

import json
import os
import shutil
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure backend root and repo root are in sys.path
backend_dir = Path(__file__).resolve().parent.parent
repo_dir = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
if str(repo_dir) not in sys.path:
    sys.path.insert(0, str(repo_dir))

import scripts.collector as collector_mod
from app.core.config import settings
from app.main import app


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SEED_DIR = FIXTURES_DIR / "seed"


def load_fixture(name: str):
    """Loads a JSON fixture. A missing file fails the test instead of giving empty data."""
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def isolate_test_storage(tmp_path, monkeypatch):
    """
    Autouse fixture that gives every test its own temporary data directory,
    built only from tests/fixtures/seed/. It never reads the live data/ folder.
    """
    temp_data_dir = tmp_path / "data"
    temp_data_dir.mkdir(parents=True, exist_ok=True)

    temp_catalog = temp_data_dir / "welfare_catalog.json"
    temp_sync = temp_data_dir / "latest_sync.json"
    temp_regions = temp_data_dir / "regions.json"
    temp_quarantine = temp_data_dir / "quarantine_records.json"
    temp_staging = temp_data_dir / "local_staging_queue.json"
    temp_changelogs = temp_data_dir / "changelogs"
    temp_changelogs.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(SEED_DIR / "welfare_catalog.json", temp_catalog)
    shutil.copyfile(SEED_DIR / "latest_sync.json", temp_sync)
    shutil.copyfile(SEED_DIR / "regions.json", temp_regions)

    temp_quarantine.write_text(json.dumps({"quarantined_records": []}, ensure_ascii=False))
    temp_staging.write_text(json.dumps({"staged_policies": []}, ensure_ascii=False))

    # Monkeypatch settings
    monkeypatch.setattr(settings, "CATALOG_PATH", str(temp_catalog))
    monkeypatch.setattr(settings, "SYNC_PATH", str(temp_sync))
    monkeypatch.setattr(settings, "REGIONS_PATH", str(temp_regions))
    monkeypatch.setattr(settings, "QUARANTINE_PATH", str(temp_quarantine))
    monkeypatch.setattr(settings, "STAGING_PATH", str(temp_staging))
    monkeypatch.setattr(settings, "CHANGELOGS_DIR", str(temp_changelogs))

    # Monkeypatch environment variables
    monkeypatch.setenv("CATALOG_PATH", str(temp_catalog))
    monkeypatch.setenv("SYNC_PATH", str(temp_sync))
    monkeypatch.setenv("REGIONS_PATH", str(temp_regions))
    monkeypatch.setenv("QUARANTINE_PATH", str(temp_quarantine))
    monkeypatch.setenv("STAGING_PATH", str(temp_staging))
    monkeypatch.setenv("CHANGELOGS_DIR", str(temp_changelogs))

    # Also monkeypatch scripts.collector module paths
    monkeypatch.setattr(collector_mod, "CATALOG_PATH", str(temp_catalog))
    monkeypatch.setattr(collector_mod, "SYNC_PATH", str(temp_sync))
    monkeypatch.setattr(collector_mod, "QUARANTINE_PATH", str(temp_quarantine))
    monkeypatch.setattr(collector_mod, "DATA_DIR", str(temp_data_dir))

    return {
        "data_dir": temp_data_dir,
        "catalog_path": temp_catalog,
        "sync_path": temp_sync,
        "regions_path": temp_regions,
        "quarantine_path": temp_quarantine,
        "staging_path": temp_staging,
        "changelogs_dir": temp_changelogs,
    }


@pytest.fixture
def test_client():
    """Provides isolated FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_bojo24_data():
    """Loads synthetic raw Bojo24 API payload."""
    return load_fixture("mock_bojo24.json")


@pytest.fixture
def mock_bokjiro_data():
    """Loads synthetic raw Bokjiro API payload."""
    return load_fixture("mock_bokjiro.json")


@pytest.fixture
def mock_local_notice_data():
    """Loads synthetic raw local government municipal notices payload."""
    return load_fixture("mock_local_notice.json")
