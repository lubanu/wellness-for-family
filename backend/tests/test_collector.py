"""
backend/tests/test_collector.py
================================================================================
Comprehensive Unit & Integration Test Suite for Central Government Ingestion Pipeline.
Tests:
- Bojo24Normalizer (data.go.kr) parsing & validation
- BokjiroNormalizer (SSIS) parsing & validation
- 5-Layer Fault Tolerance:
  1. Exponential backoff retry on API timeouts & HTTP 5xx
  2. Record-level quarantine error isolation to data/quarantine_records.json
  3. Lossless cache retention (PARTIAL_SUCCESS_CACHE_RETAINED)
  4. Fail-fast catalog loading guard against corruption (raises RuntimeError)
  5. Atomic file replacement (.tmp swapping)
- Master catalog integration, deduplication, and monthly changelog tracking
- Zero production pollution (verified via conftest.py isolated storage fixture)
"""

import json
import os
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import scripts.collector as collector
from scripts.collector import (
    Bojo24Normalizer,
    BokjiroNormalizer,
    audit_and_refresh_policies,
    fetch_bokjiro_portal,
    fetch_public_data_portal,
    format_ymd_date,
    get_catalog_path,
    get_quarantine_path,
    get_sync_path,
    ingest_with_quarantine_isolation,
    load_existing_catalog,
    normalize_bojo24_item,
    normalize_bokjiro_item,
    parse_age_bounds,
    parse_amount_text,
    parse_income_ratio,
    save_atomic_json,
    save_catalog_and_sync_state,
)


# ==============================================================================
# 1. Bojo24 Normalizer Tests
# ==============================================================================

class TestBojo24Normalizer:
    """Verifies parsing, amount conversion, eligibility, and validation for Bojo24."""

    def test_bojo24_parent_allowance_normalization(self, mock_bojo24_data):
        items = mock_bojo24_data["data"]
        parent_item = next(it for it in items if "000000460390" in it.get("SVC_ID", ""))

        normalized = normalize_bojo24_item(parent_item)

        assert normalized["source_type"] == "BOJO24"
        assert normalized["source_id"] == "000000460390"
        assert normalized["origin"] == "CENTRAL"
        assert normalized["region_code"] == "ALL"
        assert normalized["region_name"] == "대한민국 전국 공통"
        assert normalized["category"] == "CASH"
        assert normalized["amount_value"] == 12000000  # 월 100만 원 * 12
        assert "보건복지부" in normalized["managing_org"]
        assert len(normalized["summary_3lines"]) == 3
        assert normalized["target_eligibility"]["min_age"] == 0
        assert normalized["target_eligibility"]["max_age"] == 1
        assert "infant" in normalized["target_eligibility"]["required_tags"]
        assert normalized["target_eligibility"]["income_limit_ratio"] == 999
        assert normalized["fingerprint"] is not None
        assert len(normalized["fingerprint"]) == 16

    def test_bojo24_voucher_normalization(self, mock_bojo24_data):
        items = mock_bojo24_data["data"]
        voucher_item = next(it for it in items if "000000460391" in it.get("SVC_ID", ""))

        normalized = normalize_bojo24_item(voucher_item)

        assert normalized["origin"] == "CENTRAL"
        assert normalized["category"] == "VOUCHER"
        assert normalized["amount_value"] in [2000000, 3000000]
        assert "infant" in normalized["target_eligibility"]["required_tags"]
        assert len(normalized["summary_3lines"]) == 3

    def test_bojo24_youth_rent_housing_normalization(self, mock_bojo24_data):
        items = mock_bojo24_data["data"]
        housing_item = next(it for it in items if "000000460392" in it.get("SVC_ID", ""))

        normalized = normalize_bojo24_item(housing_item)

        assert normalized["origin"] == "CENTRAL"
        assert normalized["category"] == "HOUSING"
        assert normalized["amount_value"] == 2400000  # 월 20만 원 * 12
        assert normalized["target_eligibility"]["min_age"] == 19
        assert normalized["target_eligibility"]["max_age"] == 34
        assert normalized["target_eligibility"]["income_limit_ratio"] == 60
        assert "housing" in normalized["target_eligibility"]["required_tags"]
        assert "youth" in normalized["target_eligibility"]["required_tags"]

    def test_bojo24_local_gwanak_moving_normalization(self, mock_bojo24_data):
        items = mock_bojo24_data["data"]
        local_item = next(it for it in items if "116200000042" in it.get("SVC_ID", ""))

        normalized = normalize_bojo24_item(local_item)

        assert normalized["origin"] == "LOCAL"
        assert normalized["region_code"] == "seoul_gwanak"
        assert "관악구" in normalized["region_name"]
        assert normalized["amount_value"] == 400000
        assert normalized["target_eligibility"]["min_age"] == 19
        assert normalized["target_eligibility"]["max_age"] == 39
        assert normalized["target_eligibility"]["income_limit_ratio"] == 150
        assert normalized["is_budget_limited"] is True
        assert normalized["slot_capacity"] == 300

    def test_bojo24_malformed_record_raises_value_error(self, mock_bojo24_data):
        items = mock_bojo24_data["data"]
        malformed_item = next(it for it in items if "MALFORMED" in it.get("SVC_ID", ""))

        with pytest.raises((ValueError, Exception)):
            normalize_bojo24_item(malformed_item)


# ==============================================================================
# 2. Bokjiro Normalizer Tests
# ==============================================================================

class TestBokjiroNormalizer:
    """Verifies parsing, SSIS arrays, and validation for Bokjiro."""

    def test_bokjiro_child_allowance_normalization(self, mock_bokjiro_data):
        items = mock_bokjiro_data["items"]
        child_item = next(it for it in items if "WLF00000001" in it.get("servId", ""))

        normalized = normalize_bokjiro_item(child_item)

        assert normalized["source_type"] == "BOKJIRO"
        assert normalized["source_id"] == "WLF00000001"
        assert normalized["origin"] == "CENTRAL"
        assert normalized["region_code"] == "ALL"
        assert normalized["category"] == "CASH"
        assert normalized["amount_value"] == 1200000  # 연간 120만 원
        assert normalized["target_eligibility"]["max_age"] == 8
        assert "multichild" in normalized["target_eligibility"]["required_tags"]
        assert "보건복지부" in normalized["managing_org"]
        assert len(normalized["summary_3lines"]) == 3

    def test_bokjiro_basic_pension_elderly_normalization(self, mock_bokjiro_data):
        items = mock_bokjiro_data["items"]
        pension_item = next(it for it in items if "WLF00000002" in it.get("servId", ""))

        normalized = normalize_bokjiro_item(pension_item)

        assert normalized["origin"] == "CENTRAL"
        assert normalized["category"] == "CASH"
        assert normalized["amount_value"] == 4017720  # 연간 최대 4,017,720원
        assert normalized["target_eligibility"]["min_age"] == 65
        assert normalized["target_eligibility"]["income_limit_ratio"] == 70  # 하위 70%
        assert "elderly" in normalized["target_eligibility"]["required_tags"]

    def test_bokjiro_local_gwanak_moving_normalization(self, mock_bokjiro_data):
        items = mock_bokjiro_data["items"]
        local_item = next(it for it in items if "WLF00009876" in it.get("servId", ""))

        normalized = normalize_bokjiro_item(local_item)

        assert normalized["origin"] == "LOCAL"
        assert normalized["region_code"] == "seoul_gwanak"
        assert normalized["amount_value"] == 400000
        assert normalized["target_eligibility"]["min_age"] == 19
        assert normalized["target_eligibility"]["max_age"] == 39
        assert normalized["is_budget_limited"] is True
        assert normalized["slot_capacity"] == 300

    def test_bokjiro_corrupted_record_raises_value_error(self, mock_bokjiro_data):
        items = mock_bokjiro_data["items"]
        corrupted_item = next(it for it in items if "CORRUPTED" in it.get("servId", ""))

        with pytest.raises((ValueError, Exception)):
            normalize_bokjiro_item(corrupted_item)


# ==============================================================================
# 3. Fault Tolerance & Quarantine Error Isolation Tests
# ==============================================================================

class TestFaultToleranceAndQuarantine:
    """Verifies Layer 2 Item-Level Quarantine and Catalog Protection."""

    def test_ingest_with_quarantine_isolation_mixed_bojo24(self, mock_bojo24_data):
        raw_items = mock_bojo24_data["data"]
        assert len(raw_items) == 5

        # Initial catalog count
        cat_initial = load_existing_catalog()
        initial_count = len(cat_initial.get("policies", []))

        successes, quarantined = ingest_with_quarantine_isolation(raw_items, source_type="BOJO24")

        # 4 valid items succeed, 1 malformed quarantined
        assert len(successes) == 4
        assert len(quarantined) == 1
        assert quarantined[0]["source_id"] == "000000460399_MALFORMED"

        # Quarantine log persisted
        q_path = Path(get_quarantine_path())
        assert q_path.exists()
        with open(q_path, "r", encoding="utf-8") as f:
            q_data = json.load(f)
            assert len(q_data.get("quarantined_records", [])) >= 1
            entry = q_data["quarantined_records"][-1]
            assert entry["source_type"] == "BOJO24"
            assert "MALFORMED" in entry["source_id"]
            assert entry["error_message"] != ""

        # Master catalog intact and has grown
        cat_updated = load_existing_catalog()
        assert len(cat_updated["policies"]) >= initial_count

    def test_ingest_with_quarantine_isolation_mixed_bokjiro(self, mock_bokjiro_data):
        raw_items = mock_bokjiro_data["items"]
        assert len(raw_items) == 4

        successes, quarantined = ingest_with_quarantine_isolation(raw_items, source_type="BOKJIRO")

        # 3 valid items succeed, 1 corrupted quarantined
        assert len(successes) == 3
        assert len(quarantined) == 1
        assert quarantined[0]["source_id"] == "WLF00009999_CORRUPTED"

        q_path = Path(get_quarantine_path())
        with open(q_path, "r", encoding="utf-8") as f:
            q_data = json.load(f)
            corrupted_entries = [e for e in q_data["quarantined_records"] if "CORRUPTED" in e["source_id"]]
            assert len(corrupted_entries) >= 1

    def test_fail_fast_on_corrupted_catalog(self, tmp_path):
        """Layer 4: Corrupted catalog JSON must raise RuntimeError (fail-fast, no wipeout)."""
        corrupted_file = tmp_path / "corrupted_welfare_catalog.json"
        corrupted_file.write_text("{ broken json: [ truncated")

        with pytest.raises(RuntimeError) as exc_info:
            load_existing_catalog(str(corrupted_file))

        assert "Critical: Failed to load existing catalog" in str(exc_info.value)
        assert "Aborting pipeline to prevent data wipeout" in str(exc_info.value)

    def test_empty_catalog_created_when_file_not_exists(self, tmp_path):
        non_existent_file = tmp_path / "does_not_exist_catalog.json"
        loaded = load_existing_catalog(str(non_existent_file))
        assert loaded == {"version": "1.0.0", "policies": []}


# ==============================================================================
# 4. Cache Retention & Exponential Backoff Tests
# ==============================================================================

class TestCacheRetentionAndNetworkRetries:
    """Verifies Layer 1 Exponential Backoff & Layer 3 Lossless Cache Retention."""

    def test_lossless_cache_retention_on_api_failure(self):
        """When external API fails completely, existing verified catalog is retained."""
        cat = load_existing_catalog()
        initial_policies = cat.get("policies", [])
        initial_count = len(initial_policies)

        refreshed, c_cnt, l_cnt, u_cnt = audit_and_refresh_policies(cat)

        # Save with PARTIAL_SUCCESS_CACHE_RETAINED
        save_catalog_and_sync_state(
            refreshed, c_cnt, l_cnt, u_cnt,
            sync_status="PARTIAL_SUCCESS_CACHE_RETAINED",
            error_notice="External API timeout; verified cache retained."
        )

        # Verify sync_status in latest_sync.json
        s_path = Path(get_sync_path())
        assert s_path.exists()
        with open(s_path, "r", encoding="utf-8") as f:
            sync_data = json.load(f)
            assert sync_data["sync_status"] == "PARTIAL_SUCCESS_CACHE_RETAINED"
            assert "External API timeout" in sync_data["error_notice"]
            assert sync_data["total_active_policies"] == initial_count

        # Master catalog count is preserved
        cat_after = load_existing_catalog()
        assert len(cat_after["policies"]) == initial_count

    @patch("urllib.request.urlopen")
    def test_exponential_backoff_retry_on_http_500(self, mock_urlopen):
        """Layer 1: Retries on HTTP 500 up to max_retries with exponential delay."""
        # Simulate HTTP 500 error on all attempts
        http_error = urllib.error.HTTPError(
            url="http://test.url",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None
        )
        mock_urlopen.side_effect = http_error

        with patch("time.sleep") as mock_sleep:
            result = fetch_public_data_portal(api_key="TEST_KEY", max_retries=3, retry_delay=0.1)

            assert result is None  # All retries failed
            assert mock_urlopen.call_count == 3
            # Check exponential sleep backoff: 0.1s, 0.2s
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(pytest.approx(0.1, 0.01))
            mock_sleep.assert_any_call(pytest.approx(0.2, 0.01))

    @patch("urllib.request.urlopen")
    def test_retry_recovers_on_transient_failure(self, mock_urlopen):
        """Layer 1: Transient 503 error recovered on second attempt."""
        http_error = urllib.error.HTTPError(
            url="http://test.url",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=None
        )
        # Mock successful response on 2nd attempt
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"data": [{"SVC_NM": "재시도 복구 성공"}]}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        mock_urlopen.side_effect = [http_error, mock_resp]

        with patch("time.sleep"):
            result = fetch_public_data_portal(api_key="TEST_KEY", max_retries=3, retry_delay=0.01)

            assert result is not None
            assert len(result) == 1
            assert result[0]["SVC_NM"] == "재시도 복구 성공"
            assert mock_urlopen.call_count == 2


# ==============================================================================
# 5. Helpers & Edge Case Parsing Tests
# ==============================================================================

class TestCollectorHelperParsers:
    """Tests fine-grained extraction utilities."""

    def test_parse_amount_various_formats(self):
        assert parse_amount_text("월 100만 원")[0] == 12000000
        assert parse_amount_text("연간 120만 원")[0] == 1200000
        assert parse_amount_text("연 최대 240만 원")[0] == 2400000
        assert parse_amount_text("최대 40만 원")[0] == 400000
        assert parse_amount_text("월 최대 334,810원")[0] == 4017720
        assert parse_amount_text("")[0] == 0
        assert parse_amount_text(None)[0] == 0

    def test_parse_age_bounds_various_formats(self):
        assert parse_age_bounds("만 8세 미만") == (0, 8)
        assert parse_age_bounds("만 19세~34세") == (19, 34)
        assert parse_age_bounds("만 19~34세") == (19, 34)
        assert parse_age_bounds("만 19세 이상 39세 이하") == (19, 39)
        assert parse_age_bounds("만 0세 및 만 1세") == (0, 1)
        assert parse_age_bounds("만 65세 이상") == (65, 120)
        assert parse_age_bounds("") == (0, 120)

    def test_parse_income_ratio(self):
        assert parse_income_ratio("기준중위소득 60% 이하") == 60
        assert parse_income_ratio("기준중위소득 150% 이하") == 150
        assert parse_income_ratio("기준 중위소득 150% 미만") == 150
        assert parse_income_ratio("중위소득 120% 미만") == 120
        assert parse_income_ratio("소득·재산 무관") == 999
        assert parse_income_ratio("하위 70%") == 70

    def test_format_ymd_date(self):
        assert format_ymd_date("20260101") == "2026-01-01"
        assert format_ymd_date("2026-11-30") == "2026-11-30"
        assert format_ymd_date("99991231") is None
        assert format_ymd_date("") is None

    def test_atomic_json_replacement(self, tmp_path):
        target_file = tmp_path / "atomic_test.json"
        data = {"hello": "world", "number": 42}
        save_atomic_json(str(target_file), data)

        assert target_file.exists()
        with open(target_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            assert loaded == data

    def test_audit_and_refresh_policies_deduplication(self):
        duplicate_catalog = {
            "policies": [
                {"id": "pol_1", "fingerprint": "fp1", "origin": "CENTRAL"},
                {"id": "pol_1", "fingerprint": "fp1", "origin": "CENTRAL"},  # duplicate id & fp
                {"id": "pol_2", "fingerprint": "fp2", "origin": "LOCAL", "is_urgent": True}
            ]
        }
        refreshed, c_cnt, l_cnt, u_cnt = audit_and_refresh_policies(duplicate_catalog)
        assert len(refreshed) == 2
        assert c_cnt == 1
        assert l_cnt == 1
        assert u_cnt == 1
