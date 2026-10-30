"""
Pytest isolation configuration and fixtures for WelFamily Backend & Pipeline Tests.
Ensures 100% isolation from production data files (data/welfare_catalog.json, data/latest_sync.json).
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

from app.core.config import settings
from app.main import app


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolate_test_storage(tmp_path, monkeypatch):
    """
    Autouse fixture that ensures every test runs in an isolated directory
    with temporary copies of catalog, sync, regions, quarantine, staging, and changelogs.
    This guarantees zero pollution to the production data/ directory.
    """
    real_data_dir = settings.BASE_DIR / "data"

    temp_data_dir = tmp_path / "data"
    temp_data_dir.mkdir(parents=True, exist_ok=True)

    temp_catalog = temp_data_dir / "welfare_catalog.json"
    temp_sync = temp_data_dir / "latest_sync.json"
    temp_regions = temp_data_dir / "regions.json"
    temp_quarantine = temp_data_dir / "quarantine_records.json"
    temp_staging = temp_data_dir / "local_staging_queue.json"
    temp_changelogs = temp_data_dir / "changelogs"
    temp_changelogs.mkdir(parents=True, exist_ok=True)

    # Copy existing production files if present, else seed minimal valid structure
    orig_catalog = Path(settings.CATALOG_PATH)
    if orig_catalog.exists():
        shutil.copyfile(orig_catalog, temp_catalog)
    else:
        temp_catalog.write_text(json.dumps({"version": "1.0.0", "policies": []}, ensure_ascii=False))

    orig_sync = Path(settings.SYNC_PATH)
    if orig_sync.exists():
        shutil.copyfile(orig_sync, temp_sync)
    else:
        temp_sync.write_text(json.dumps({"sync_status": "SUCCESS", "total_active_policies": 0}, ensure_ascii=False))

    orig_regions = Path(settings.REGIONS_PATH)
    if orig_regions.exists():
        shutil.copyfile(orig_regions, temp_regions)
    else:
        temp_regions.write_text(json.dumps({"regions": []}, ensure_ascii=False))

    temp_quarantine.write_text(json.dumps({"quarantined_records": []}, ensure_ascii=False))
    temp_staging.write_text(json.dumps({"staged_policies": []}, ensure_ascii=False))

    # Monkeypatch settings
    monkeypatch.setattr(settings, "CATALOG_PATH", str(temp_catalog))
    monkeypatch.setattr(settings, "SYNC_PATH", str(temp_sync))
    monkeypatch.setattr(settings, "REGIONS_PATH", str(temp_regions))

    # Monkeypatch environment variables
    monkeypatch.setenv("CATALOG_PATH", str(temp_catalog))
    monkeypatch.setenv("SYNC_PATH", str(temp_sync))
    monkeypatch.setenv("REGIONS_PATH", str(temp_regions))
    monkeypatch.setenv("QUARANTINE_PATH", str(temp_quarantine))
    monkeypatch.setenv("STAGING_PATH", str(temp_staging))
    monkeypatch.setenv("CHANGELOGS_DIR", str(temp_changelogs))

    # Also monkeypatch scripts.collector module paths if loaded
    try:
        import scripts.collector as collector_mod
        monkeypatch.setattr(collector_mod, "CATALOG_PATH", str(temp_catalog), raising=False)
        monkeypatch.setattr(collector_mod, "SYNC_PATH", str(temp_sync), raising=False)
        monkeypatch.setattr(collector_mod, "DATA_DIR", str(temp_data_dir), raising=False)
    except ImportError:
        pass

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
    fixture_path = FIXTURES_DIR / "mock_bojo24.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"data": []}


@pytest.fixture
def mock_bokjiro_data():
    """Loads synthetic raw Bokjiro API payload."""
    fixture_path = FIXTURES_DIR / "mock_bokjiro.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"items": []}


@pytest.fixture
def mock_local_notice_data():
    """Loads synthetic raw local government municipal notices payload."""
    fixture_path = FIXTURES_DIR / "mock_local_notice.json"
    if fixture_path.exists():
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"staged_policies": []}
