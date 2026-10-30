"""
backend/tests/test_local_admin.py
================================================================================
Comprehensive Unit and Integration Tests for Local Government Welfare Management:
- Municipal policy registration with ordinance & metadata validation.
- 1-Click 3-Second Quick Budget Status Patch (NEAR_EXHAUSTION -> is_urgent: True, EXHAUSTED -> is_budget_limited: True).
- Municipal policy listing, filtering by region and status.
- Direct local_welfare_service function invocation.
- Validation bounds and Human-in-the-Loop staging announcement approval.
"""

import json
from pathlib import Path
import pytest

from app.core.config import settings
from app.services import local_welfare_service
from scripts.local_announcement_crawler import (
    crawl_and_stage_announcements,
    load_candidate_notices,
    SYNTHETIC_MUNICIPAL_NOTICES,
)


@pytest.fixture
def sample_local_policy_payload():
    return {
        "title": "2026년 관악구 청년 전월세 중개보수 및 이사비 지원사업",
        "region_code": "seoul_gwanak",
        "region_name": "서울특별시 관악구",
        "managing_org": "서울특별시 관악구 청년정책과",
        "local_ordinance_basis": "서울특별시 관악구 청년 기본 조례 제12조",
        "category": "CASH",
        "amount_value": 400000,
        "amount_text": "최대 40만 원 (실비 현금 지원)",
        "application_period_type": "FIRST_COME_FIRST_SERVED",
        "start_date": "2026-03-01",
        "end_date": "2026-11-30",
        "is_budget_limited": True,
        "budget_status": "OPEN",
        "slot_capacity": 300,
        "current_applicant_count": 0,
        "target_eligibility": {
            "min_age": 19,
            "max_age": 39,
            "income_limit_ratio": 150,
            "required_tags": ["youth", "newlywed", "housing"],
            "residence_condition": "관악구 전입 1년 이내 무주택 청년"
        },
        "summary_3lines": [
            "관악구로 전입한 지 1년 이내의 만 19~39세 무주택 청년 가구",
            "부동산 중개수수료 및 이사 용달 실비 합산 최대 40만 원 지원",
            "선착순 300가구 예산 소진형 공고이므로 마감 전 온라인 신청 필수"
        ],
        "required_documents": [
            {"name": "주민등록초본", "issuer": "정부24", "can_online": True},
            {"name": "확정일자부 임대차계약서", "issuer": "본인 소지", "can_online": False}
        ],
        "application_url": "https://youth.seoul.go.kr",
        "contact_phone": "02-879-5931"
    }


def test_create_local_policy_with_municipal_metadata(test_client, sample_local_policy_payload):
    """
    [Local Gov] 실무 공무원 맞춤 신규 특화사업 등록 API:
    - POST /api/v1/admin/local-policies
    - Verifies required municipal metadata (region_code, local_ordinance_basis, contact_phone).
    - Persists policy to isolated catalog and verifies origin=LOCAL.
    - Verifies audit changelog records NEW_LOCAL_POLICY.
    """
    res = test_client.post("/api/v1/admin/local-policies", json=sample_local_policy_payload)
    assert res.status_code == 201, f"Expected 201 Created but got {res.status_code}: {res.text}"

    data = res.json()
    assert data["status"] == "SUCCESS"
    assert "policy_id" in data
    assert data["fingerprint"] is not None
    policy_id = data["policy_id"]

    # Verify catalog reflection
    catalog = local_welfare_service.load_catalog()
    stored = next((p for p in catalog["policies"] if p["id"] == policy_id), None)
    assert stored is not None, "Policy must be persisted to catalog"
    assert stored["origin"] == "LOCAL"
    assert stored["region_code"] == "seoul_gwanak"
    assert stored["local_ordinance_basis"] == "서울특별시 관악구 청년 기본 조례 제12조"
    assert stored["contact_phone"] == "02-879-5931"
    assert stored["version"] == 1


def test_quick_status_patch_near_exhaustion_auto_urgent(test_client, sample_local_policy_payload):
    """
    [Local Gov] 1-Click 3-Second Quick Budget Status Patch (NEAR_EXHAUSTION):
    - When budget_status transitions to NEAR_EXHAUSTION, system automatically sets is_urgent: True
    - Automatically updates dday_text to '선착순 마감임박!' if not explicitly provided.
    """
    create_res = test_client.post("/api/v1/admin/local-policies", json=sample_local_policy_payload)
    assert create_res.status_code == 201
    policy_id = create_res.json()["policy_id"]

    patch_payload = {
        "budget_status": "NEAR_EXHAUSTION",
        "current_applicant_count": 285
    }

    res = test_client.patch(f"/api/v1/admin/local-policies/{policy_id}/status", json=patch_payload)
    assert res.status_code == 200, f"Expected 200 OK but got {res.status_code}: {res.text}"

    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["budget_status"] == "NEAR_EXHAUSTION"
    assert data["is_urgent"] is True
    assert "마감임박" in data["dday_text"]
    assert data["version"] == 2

    # Verify catalog state
    catalog = local_welfare_service.load_catalog()
    stored = next(p for p in catalog["policies"] if p["id"] == policy_id)
    assert stored["budget_status"] == "NEAR_EXHAUSTION"
    assert stored["is_urgent"] is True
    assert stored["current_applicant_count"] == 285


def test_quick_status_patch_exhausted_sets_budget_limited(test_client, sample_local_policy_payload):
    """
    [Local Gov] 1-Click 3-Second Quick Budget Status Patch (EXHAUSTED):
    - When budget_status transitions to EXHAUSTED, sets is_budget_limited: True
    - Automatically updates dday_text to reflect closure.
    """
    create_res = test_client.post("/api/v1/admin/local-policies", json=sample_local_policy_payload)
    policy_id = create_res.json()["policy_id"]

    patch_payload = {
        "budget_status": "EXHAUSTED",
        "is_urgent": False
    }

    res = test_client.patch(f"/api/v1/admin/local-policies/{policy_id}/status", json=patch_payload)
    assert res.status_code == 200

    data = res.json()
    assert data["budget_status"] == "EXHAUSTED"
    assert data["is_urgent"] is False
    assert "소진 마감" in data["dday_text"]

    catalog = local_welfare_service.load_catalog()
    stored = next(p for p in catalog["policies"] if p["id"] == policy_id)
    assert stored["budget_status"] == "EXHAUSTED"
    assert stored["is_budget_limited"] is True
    assert stored["is_urgent"] is False


def test_list_local_policies_and_filtering(test_client, sample_local_policy_payload):
    """
    [Local Gov] Listing and filtering municipal policies by region_code, status, and search query.
    """
    # Create Gwanak policy
    test_client.post("/api/v1/admin/local-policies", json=sample_local_policy_payload)

    # Create Seongnam policy
    seongnam_payload = dict(sample_local_policy_payload)
    seongnam_payload["title"] = "성남시 청년기본소득 2분기"
    seongnam_payload["region_code"] = "gyeonggi_seongnam"
    seongnam_payload["region_name"] = "경기도 성남시"
    seongnam_payload["budget_status"] = "HALF_CONSUMED"
    test_client.post("/api/v1/admin/local-policies", json=seongnam_payload)

    # 1. List all
    res_all = test_client.get("/api/v1/admin/local-policies")
    assert res_all.status_code == 200
    all_data = res_all.json()
    assert all_data["total"] >= 2

    # 2. Filter by region_code
    res_gwanak = test_client.get("/api/v1/admin/local-policies?region_code=seoul_gwanak")
    assert res_gwanak.status_code == 200
    gwanak_data = res_gwanak.json()
    assert all(p["region_code"] == "seoul_gwanak" for p in gwanak_data["policies"])

    # 3. Filter by budget_status
    res_half = test_client.get("/api/v1/admin/local-policies?budget_status=HALF_CONSUMED")
    assert res_half.status_code == 200
    half_data = res_half.json()
    assert any(p["region_code"] == "gyeonggi_seongnam" for p in half_data["policies"])

    # 4. Search query
    res_q = test_client.get("/api/v1/admin/local-policies?q=기본소득")
    assert res_q.status_code == 200
    assert any("기본소득" in p["title"] for p in res_q.json()["policies"])


def test_get_and_update_local_policy(test_client, sample_local_policy_payload):
    """
    [Local Gov] Detail retrieval and full update (PUT) of municipal policy.
    """
    create_res = test_client.post("/api/v1/admin/local-policies", json=sample_local_policy_payload)
    policy_id = create_res.json()["policy_id"]

    # GET detail
    get_res = test_client.get(f"/api/v1/admin/local-policies/{policy_id}")
    assert get_res.status_code == 200
    assert get_res.json()["policy"]["id"] == policy_id

    # PUT update
    updated_payload = dict(sample_local_policy_payload)
    updated_payload["title"] = "2026년 관악구 청년 이사비 지원사업 (예산 증액)"
    updated_payload["amount_value"] = 500000
    updated_payload["amount_text"] = "최대 50만 원 실비 지원"

    put_res = test_client.put(f"/api/v1/admin/local-policies/{policy_id}", json=updated_payload)
    assert put_res.status_code == 200
    put_data = put_res.json()
    assert put_data["status"] == "SUCCESS"
    assert put_data["data"]["amount_value"] == 500000
    assert put_data["data"]["version"] == 2


def test_delete_local_policy(test_client, sample_local_policy_payload):
    """
    [Local Gov] Policy retirement and deletion with 404 confirmation.
    """
    create_res = test_client.post("/api/v1/admin/local-policies", json=sample_local_policy_payload)
    policy_id = create_res.json()["policy_id"]

    del_res = test_client.delete(f"/api/v1/admin/local-policies/{policy_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "SUCCESS"

    # Subsequent GET returns 404
    get_res = test_client.get(f"/api/v1/admin/local-policies/{policy_id}")
    assert get_res.status_code == 404


def test_validation_errors_rejected(test_client, sample_local_policy_payload):
    """
    [Boundary] Negative and format boundary validation:
    - Invalid phone number format rejected with 422
    - Chronological date inversion rejected with 422
    - Summary lines not exactly 3 rejected with 422
    """
    # 1. Invalid phone
    bad_phone = dict(sample_local_policy_payload)
    bad_phone["contact_phone"] = "invalid_number_123"
    res1 = test_client.post("/api/v1/admin/local-policies", json=bad_phone)
    assert res1.status_code == 422

    # 2. Chronological date inversion
    bad_dates = dict(sample_local_policy_payload)
    bad_dates["start_date"] = "2026-12-31"
    bad_dates["end_date"] = "2026-01-01"
    res2 = test_client.post("/api/v1/admin/local-policies", json=bad_dates)
    assert res2.status_code == 422

    # 3. Summary lines count != 3
    bad_summary = dict(sample_local_policy_payload)
    bad_summary["summary_3lines"] = ["1줄 요약만 제공"]
    res3 = test_client.post("/api/v1/admin/local-policies", json=bad_summary)
    assert res3.status_code == 422


def test_staging_crawler_and_approval_flow(test_client):
    """
    [Local Gov Staging] Announcement crawler staging and Human-in-the-Loop approval:
    1. Crawler executes and populates local_staging_queue.json with PENDING_REVIEW.
    2. Officer approves candidate via POST /staging/{candidate_id}/approve.
    3. Policy is promoted into active master catalog.
    """
    crawl_result = crawl_and_stage_announcements()
    assert crawl_result["status"] == "SUCCESS"
    assert crawl_result["total_staged_count"] >= 1

    candidate_id = crawl_result["staged_policies"][0]["stg_id"]

    # Approve candidate
    approve_res = test_client.post(f"/api/v1/admin/local-policies/staging/{candidate_id}/approve")
    assert approve_res.status_code == 201
    approve_data = approve_res.json()
    assert approve_data["status"] == "SUCCESS"

    promoted_id = approve_data["policy_id"]
    catalog = local_welfare_service.load_catalog()
    assert any(p["id"] == promoted_id for p in catalog["policies"]), "Promoted policy must exist in catalog"


def test_service_level_direct_invocation(sample_local_policy_payload):
    """
    Verifies direct Python service-level invocations of local_welfare_service functions.
    """
    # 1. Create
    policy = local_welfare_service.create_local_policy(sample_local_policy_payload)
    assert policy.id.startswith("pol_seoul_gwanak_")
    assert policy.version == 1

    # 2. Status Patch
    patched = local_welfare_service.patch_policy_status(
        policy.id,
        {"budget_status": "NEAR_EXHAUSTION", "is_urgent": True}
    )
    assert patched["budget_status"] == "NEAR_EXHAUSTION"
    assert patched["is_urgent"] is True
    assert patched.version == 2

    # 3. Get
    retrieved = local_welfare_service.get_local_policy(policy.id)
    assert retrieved.id == policy.id
    assert retrieved.budget_status == "NEAR_EXHAUSTION"

    # 4. Patch non-existent policy strictly raises KeyError (zero backdoor verification)
    with pytest.raises(KeyError) as exc_info:
        local_welfare_service.patch_policy_status(
            "pol_non_existent_id",
            {"budget_status": "EXHAUSTED"}
        )
    assert "not found in catalog" in str(exc_info.value)

    with pytest.raises(KeyError) as exc_info_test_prefix:
        local_welfare_service.patch_policy_status(
            "pol_test_non_existent_id",
            {"budget_status": "EXHAUSTED"}
        )
    assert "not found in catalog" in str(exc_info_test_prefix.value)


def test_crawler_decoupling_and_custom_source(tmp_path):
    """
    Verifies that local announcement crawler is cleanly decoupled from test fixtures:
    - Default invocation uses production synthetic notices without hardcoded fixture paths.
    - Custom source path parameterization functions correctly without test-specific filtering.
    """
    # 1. Default without source path returns clean production notices
    default_candidates = load_candidate_notices()
    assert len(default_candidates) == len(SYNTHETIC_MUNICIPAL_NOTICES)
    assert default_candidates[0]["stg_id"] == "stg_seoul_gwanak_moving_2026"

    # 2. Custom source path parameterization
    custom_fixture = tmp_path / "custom_notices.json"
    custom_data = {
        "staged_policies": [
            {
                "stg_id": "stg_custom_notice_001",
                "title": "커스텀 지자체 출산장려금 지원 공고",
                "region_code": "custom_region",
                "region_name": "커스텀시",
                "managing_org": "복지정책과",
                "local_ordinance_basis": "커스텀시 조례 제1조",
                "category": "CASH",
                "amount_value": 500000,
                "amount_text": "50만 원",
            }
        ]
    }
    custom_fixture.write_text(json.dumps(custom_data, ensure_ascii=False), encoding="utf-8")

    loaded_custom = load_candidate_notices(str(custom_fixture))
    assert len(loaded_custom) == 1
    assert loaded_custom[0]["stg_id"] == "stg_custom_notice_001"

    # 3. Crawl and stage with custom staging path and source
    custom_staging = tmp_path / "staging_queue.json"
    result = crawl_and_stage_announcements(
        staging_path=str(custom_staging),
        source_fixture=str(custom_fixture),
    )
    assert result["status"] == "SUCCESS"
    assert result["newly_staged_count"] == 1
    assert result["staged_policies"][0]["stg_id"] == "stg_custom_notice_001"

