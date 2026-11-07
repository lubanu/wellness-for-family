# WelFamily Test Infrastructure Guide (`TEST_INFRA.md`)

> **Version**: 1.0.0  
> **Date**: 2026-10-29  
> **Status**: Verified & Operational  
> **Target**: WelFamily 맞춤형 복지 큐레이션 백엔드 및 데이터 파이프라인  

---

## 1. Overview & Test Architecture

The WelFamily automated test infrastructure is designed under **Dual Track Agile principles** to provide exhaustive, opaque-box, requirement-driven verification across the **three stakeholder perspectives**:
1. **Central Government**: Statutory normalization, public API integration (Bojo24 / Bokjiro), and fault-tolerant error quarantine.
2. **Local Government**: Municipal ordinance management, 1-click budget status patches, and urgent D-Day badges.
3. **IT Developer**: Canonical Pydantic v2 schemas, deterministic composite hash deduplication, monthly partitioned GitOps changelogs, and 100% test isolation.

```
========================================================================================
                            WelFamily Test Infrastructure
========================================================================================
   [Test Isolation Gate]                   [Synthetic Fixtures]           [Test Suite Tiers]
   backend/tests/conftest.py               backend/tests/fixtures/        backend/tests/
----------------------------------------------------------------------------------------
 • tmp_path filesystem sandbox          • mock_bojo24.json             • Tier 1: Feature Coverage
 • Zero production pollution            • mock_bokjiro.json            • Tier 2: Boundary & Corner
 • Dynamic env & settings patch         • mock_local_notice.json       • Tier 3: Cross-Combinations
 • Isolated catalog & changelogs        • 100% Offline (No rate limits)• Tier 4: Real-World E2E
========================================================================================
```

---

## 2. Test Isolation Architecture (`conftest.py`)

### 2.1 The Test Pollution Problem Solved
Prior to this infrastructure, running test suites mutated production files (`data/welfare_catalog.json` and `data/latest_sync.json`), causing git dirty state and potential data corruption.

### 2.2 Autouse Isolation Sandbox
`backend/tests/conftest.py` implements an `autouse=True` fixture `isolate_test_storage`:
- Copies frozen seed files from `backend/tests/fixtures/seed/` into pytest's temporary directory (`tmp_path / "data"`). It never reads the live `data/` folder, so tests pass the same way whatever the sync has written there.
- Replaces the storage paths in `settings`, in environment variables (`CATALOG_PATH`, `SYNC_PATH`, `REGIONS_PATH`, `QUARANTINE_PATH`, `STAGING_PATH`, `CHANGELOGS_DIR`), and in `scripts.collector`.
- Guarantees that any CRUD mutation or sync trigger executes strictly within the sandbox and is cleanly discarded upon test completion.
- `backend/tests/test_isolation.py` guards the sandbox itself.

---

## 3. Synthetic Mock Fixture Inventory (`backend/tests/fixtures/`)

To achieve **100% offline determinism** without requiring external API keys or hitting government rate limits:

| Fixture Path | Description & Schema | Key Test Scenarios Covered |
| :--- | :--- | :--- |
| `backend/tests/fixtures/mock_bojo24.json` | Synthetic response from data.go.kr (Bojo24 `serviceList` API) | - Central cash normalization (Parent Allowance)<br>- Voucher normalization (First Encounter)<br>- Malformed item for quarantine isolation |
| `backend/tests/fixtures/mock_bokjiro.json` | Synthetic response from SSIS (Bokjiro `NationalWelfarelist` API) | - LifeCycle & target characteristic mapping<br>- Cross-agency duplicate policy with Bojo24<br>- Corrupted record error isolation |
| `backend/tests/fixtures/mock_local_notice.json` | Municipal announcements & staging queue items (`local_staging_queue.json`) | - Municipal ordinance metadata & slot limits<br>- Zero-amount in-kind care service<br>- Corrupted notice with inverted age ranges |
| `backend/tests/fixtures/seed/` | Frozen copies of the original 16-policy catalog, sync metadata, and regions | - Starting data for every test<br>- Do not refresh these from `data/` |

The `mock_*` files are synthetic. They show that the code agrees with itself, not that it fits the real government APIs.

---

## 4. Test Suite Structure & Tiering

The comprehensive E2E test suite resides at `backend/tests/test_e2e_welfare_pipeline.py`:

```
backend/tests/
├── conftest.py                       # Storage isolation sandbox & mock loaders
├── fixtures/                         # Deterministic synthetic JSON datasets
│   ├── mock_bojo24.json
│   ├── mock_bokjiro.json
│   ├── mock_local_notice.json
│   └── seed/                         # Frozen starting data for every test
├── test_admin.py                     # Legacy Admin CMS & monetized affiliate tests (isolated)
├── test_backend.py                   # Public matching, catalog, and widget tests
├── test_collector.py                 # Collector normalization and fault tolerance tests
├── test_data_integrity.py            # Schema, deduplication, and versioning unit tests
├── test_e2e_welfare_pipeline.py      # Comprehensive 4-Tier E2E Welfare Pipeline Test Suite
├── test_isolation.py                 # Guards for the test sandbox itself
└── test_local_admin.py               # Local policy API and staging queue tests
```

### 4.1 No Silent Passes
Tests must fail loudly when code is missing or broken:
- Import modules at the top of the file. Do not wrap them in `try/except` or `pytest.skip`.
- Do not write fallback branches (`if hasattr(...)`, `if res.status_code == 404`) that test something else instead.
- Do not put assertions behind `if file.exists():`. Assert that the file exists.
- Read the sandbox through the `isolate_test_storage` fixture, never through `settings.BASE_DIR`.

---

## 5. Execution Guide

### 5.1 Running the Full Test Suite
```bash
backend/.venv/bin/pytest backend/tests -v
```

### 5.2 Running the E2E Welfare Pipeline Suite Specifically
```bash
backend/.venv/bin/pytest backend/tests/test_e2e_welfare_pipeline.py -v
```

### 5.3 Running Specific Tiers
```bash
# Tier 1 Feature Coverage
backend/.venv/bin/pytest backend/tests/test_e2e_welfare_pipeline.py -k "TestTier1" -v

# Tier 2 Boundary Cases
backend/.venv/bin/pytest backend/tests/test_e2e_welfare_pipeline.py -k "TestTier2" -v

# Tier 3 Cross-Feature Combinations
backend/.venv/bin/pytest backend/tests/test_e2e_welfare_pipeline.py -k "TestTier3" -v

# Tier 4 Real-World End-to-End Scenario
backend/.venv/bin/pytest backend/tests/test_e2e_welfare_pipeline.py -k "TestTier4" -v
```

### 5.4 Verifying Zero Pollution
```bash
git status --short
# data/welfare_catalog.json and data/latest_sync.json will remain untouched!
```
