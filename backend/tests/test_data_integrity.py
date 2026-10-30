"""
backend/tests/test_data_integrity.py
================================================================================
Comprehensive Unit Test Suite for Milestone 2:
- Unified Pydantic v2 domain schemas (UnifiedWelfarePolicy, TargetEligibility, LocalPolicy schemas)
- Hardened composite fingerprint hash deduplication engine
- GitOps recursive diff engine and monthly partitioned changelog tracker
"""

from datetime import date, datetime
import json
import os
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.schemas.unified_policy import (
    PolicyOrigin,
    PolicyCategory,
    BudgetStatus,
    ApplicationPeriodType,
    RequiredDocument,
    TargetEligibility,
    UnifiedWelfarePolicy,
    LocalPolicyCreateSchema,
    LocalPolicyStatusPatchSchema,
)
from app.services.deduplication import (
    generate_policy_fingerprint,
    generate_composite_hash,
)
from app.services.versioning import (
    compute_field_diff,
    track_policy_change,
)


# ==============================================================================
# 1. Unified Schema & Domain Model Unit Tests
# ==============================================================================

class TestUnifiedPolicySchema:
    def test_valid_unified_policy_construction(self):
        payload = {
            "id": "pol_unit_test_001",
            "title": "청년 월세 특별지원",
            "origin": "CENTRAL",
            "region_code": "ALL",
            "region_name": "전국 공통",
            "managing_org": "국토교통부",
            "category": "HOUSING",
            "amount_value": 2400000,
            "amount_text": "월 최대 20만 원 (최대 12개월)",
            "target_eligibility": {
                "min_age": 19,
                "max_age": 34,
                "income_limit_ratio": 60,
                "required_tags": ["youth", "housing"]
            },
            "summary_3lines": [
                "만 19~34세 무주택 청년 대상",
                "실제 납부하는 임차료 최대 월 20만 원 지원",
                "복지로 온라인 또는 주민센터 신청"
            ]
        }
        policy = UnifiedWelfarePolicy(**payload)
        assert policy.id == "pol_unit_test_001"
        assert policy.category_name == "주거/금융"
        assert len(policy.fingerprint) == 16
        assert policy.is_budget_limited is False
        assert policy.budget_status == BudgetStatus.OPEN

    def test_summary_3lines_strict_validation(self):
        base_payload = {
            "id": "pol_test_summary",
            "title": "테스트 지원",
            "origin": "LOCAL",
            "region_code": "seoul",
            "region_name": "서울특별시",
            "managing_org": "복지정책과",
            "category": "CASH",
            "amount_value": 100000,
            "amount_text": "10만 원",
        }

        # Case 1: 2 lines (too few)
        with pytest.raises(ValidationError) as exc:
            UnifiedWelfarePolicy(**{**base_payload, "summary_3lines": ["한 줄", "두 줄"]})
        assert "summary_3lines" in str(exc.value)

        # Case 2: 4 lines (too many)
        with pytest.raises(ValidationError):
            UnifiedWelfarePolicy(**{**base_payload, "summary_3lines": ["1", "2", "3", "4"]})

        # Case 3: Empty string in one line
        with pytest.raises(ValidationError):
            UnifiedWelfarePolicy(**{**base_payload, "summary_3lines": ["첫번째 요약", "", "세번째 요약"]})

    def test_negative_amount_value_rejected(self):
        with pytest.raises(ValidationError):
            UnifiedWelfarePolicy(
                id="pol_neg_amount",
                title="잘못된 금액 정책",
                origin=PolicyOrigin.CENTRAL,
                region_code="ALL",
                region_name="전국",
                managing_org="보건복지부",
                category=PolicyCategory.CASH,
                amount_value=-50000,  # Negative KRW
                amount_text="음수 금액",
                summary_3lines=["대상 요약", "금액 요약", "신청 요약"]
            )

    def test_date_conversion_from_date_object(self):
        policy = UnifiedWelfarePolicy(
            id="pol_date_test",
            title="날짜 변환 테스트 정책",
            origin=PolicyOrigin.LOCAL,
            region_code="seoul_gangnam",
            region_name="서울특별시 강남구",
            managing_org="강남구청",
            category=PolicyCategory.CASH,
            amount_value=300000,
            amount_text="30만 원",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 11, 30),
            summary_3lines=["강남구 주민 대상", "30만 원 지원", "구청 접수"]
        )
        assert policy.start_date == "2026-03-01"
        assert policy.end_date == "2026-11-30"


# ==============================================================================
# 2. TargetEligibility Boundary Tests
# ==============================================================================

class TestTargetEligibility:
    def test_age_inversion_validation(self):
        with pytest.raises(ValueError, match="최소 연령"):
            TargetEligibility(min_age=30, max_age=19)

    def test_age_out_of_bounds(self):
        with pytest.raises(ValidationError):
            TargetEligibility(min_age=-5, max_age=50)

        with pytest.raises(ValidationError):
            TargetEligibility(min_age=0, max_age=150)

    def test_income_limit_ratios(self):
        # 0% is valid (absolute poverty)
        e0 = TargetEligibility(income_limit_ratio=0)
        assert e0.income_limit_ratio == 0

        # 999% is valid (universal)
        e999 = TargetEligibility(income_limit_ratio=999)
        assert e999.income_limit_ratio == 999

        # Negative ratio rejected
        with pytest.raises(ValidationError):
            TargetEligibility(income_limit_ratio=-1)


# ==============================================================================
# 3. Local Policy Schemas & Validation Tests
# ==============================================================================

class TestLocalPolicySchemas:
    def test_phone_number_validation(self):
        valid_phones = [
            "02-879-5931",
            "031-123-4567",
            "010-9876-5432",
            "129",
            "120",
            "1350",
            "070-1234-5678"
        ]
        for phone in valid_phones:
            schema = LocalPolicyCreateSchema(
                title="관악구 청년 지원",
                region_code="seoul_gwanak",
                region_name="서울특별시 관악구",
                managing_org="청년정책과",
                amount_value=400000,
                amount_text="최대 40만 원",
                summary_3lines=["관악구 청년", "40만원 지원", "온라인 신청"],
                application_url="https://youth.seoul.go.kr",
                contact_phone=phone
            )
            assert schema.contact_phone == phone

        # Invalid phones
        invalid_phones = ["123", "02-12-34", "not_a_phone", "010-12-34567"]
        for phone in invalid_phones:
            with pytest.raises(ValidationError):
                LocalPolicyCreateSchema(
                    title="관악구 청년 지원",
                    region_code="seoul_gwanak",
                    region_name="서울특별시 관악구",
                    managing_org="청년정책과",
                    amount_value=400000,
                    amount_text="최대 40만 원",
                    summary_3lines=["관악구 청년", "40만원 지원", "온라인 신청"],
                    application_url="https://youth.seoul.go.kr",
                    contact_phone=phone
                )

    def test_date_range_chronological_order(self):
        with pytest.raises(ValidationError, match="마감일.*시작일"):
            LocalPolicyCreateSchema(
                title="역전 날짜 정책",
                region_code="seoul_gwanak",
                region_name="서울특별시 관악구",
                managing_org="청년정책과",
                amount_value=400000,
                amount_text="40만 원",
                start_date="2026-11-30",
                end_date="2026-03-01",  # Inverted
                summary_3lines=["대상 요약", "금액 요약", "신청 요약"],
                application_url="https://youth.seoul.go.kr",
                contact_phone="129"
            )


# ==============================================================================
# 4. Deduplication Engine Tests
# ==============================================================================

class TestDeduplicationEngine:
    def test_age_discrimination_zero_collision(self):
        """
        Ensures national parent allowances for Age 0 vs Age 1 produce distinct fingerprints.
        """
        p0 = {
            "title": "2026 정부 공통 부모급여 (만 0세)",
            "region_code": "ALL",
            "category": "CASH",
            "managing_org": "보건복지부",
            "target_eligibility": {"min_age": 0, "max_age": 0}
        }
        p1 = {
            "title": "2026 정부 공통 부모급여 (만 1세)",
            "region_code": "ALL",
            "category": "CASH",
            "managing_org": "보건복지부",
            "target_eligibility": {"min_age": 1, "max_age": 1}
        }
        h0 = generate_policy_fingerprint(p0)
        h1 = generate_policy_fingerprint(p1)
        assert h0 != h1, "Age tiers must produce distinct fingerprints to eliminate collision"

    def test_dual_invocation_dict_and_positional(self):
        dict_payload = {
            "title": "관악구 청년 이사비 지원",
            "region_code": "seoul_gwanak",
            "category": "CASH",
            "managing_org": "서울특별시 관악구 청년정책과",
            "target_eligibility": {"min_age": 19, "max_age": 39}
        }
        hash_dict = generate_policy_fingerprint(dict_payload)
        hash_pos = generate_policy_fingerprint(
            "seoul_gwanak", "CASH", "관악구 청년 이사비 지원", "서울특별시 관악구 청년정책과", 19, 39
        )
        assert hash_dict == hash_pos

    def test_alias_equivalence(self):
        p = {"title": "아동수당", "region_code": "ALL", "category": "CASH", "managing_org": "보건복지부"}
        assert generate_policy_fingerprint(p) == generate_composite_hash(p)


# ==============================================================================
# 5. Versioning & Monthly Changelog Tests
# ==============================================================================

class TestVersioningService:
    def test_nested_diff_detection(self):
        old = {
            "title": "원래 정책",
            "target_eligibility": {
                "min_age": 19,
                "income_limit_ratio": 120
            }
        }
        new = {
            "title": "원래 정책",
            "target_eligibility": {
                "min_age": 19,
                "income_limit_ratio": 150  # Changed
            }
        }
        diffs = compute_field_diff(old, new)
        assert len(diffs) == 1
        assert diffs[0]["field"] == "target_eligibility.income_limit_ratio"
        assert diffs[0]["old_value"] == 120
        assert diffs[0]["new_value"] == 150

    def test_excluded_fields_suppression(self):
        old = {"title": "동일", "version": 1, "last_verified_at": "2026-10-28T10:00:00Z"}
        new = {"title": "동일", "version": 2, "last_verified_at": "2026-10-29T10:00:00Z"}
        diffs = compute_field_diff(old, new)
        assert len(diffs) == 0

    def test_track_policy_change_monthly_persistence(self, tmp_path, monkeypatch):
        test_changelogs = tmp_path / "test_changelogs"
        monkeypatch.setenv("CHANGELOGS_DIR", str(test_changelogs))

        old_p = {"id": "pol_unit_01", "amount_value": 300000, "version": 1}
        new_p = {"id": "pol_unit_01", "amount_value": 400000, "version": 2}

        event = track_policy_change(old_p, new_p, author="unit_test_officer")
        assert event is not None
        assert event["change_type"] == "POLICY_UPDATED"
        assert event["author"] == "unit_test_officer"

        partition_file = test_changelogs / f"{datetime.now().strftime('%Y-%m')}.json"
        assert partition_file.exists()
        with open(partition_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data["events"]) == 1
            assert data["events"][0]["diffs"][0]["field"] == "amount_value"
