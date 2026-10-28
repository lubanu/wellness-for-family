import pytest
from fastapi.testclient import TestClient
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)

def test_admin_stats():
    res = client.get("/api/v1/admin/stats")
    assert res.status_code == 200
    data = res.json()
    assert "policies_overview" in data
    assert data["policies_overview"]["total_count"] >= 16
    assert "care_plus_revenue" in data
    assert data["care_plus_revenue"]["annual_recurring_revenue_krw"] > 0
    assert "affiliate_monetization" in data
    assert data["affiliate_monetization"]["total_clicks"] > 0
    assert "pipeline_health" in data
    assert data["pipeline_health"]["sync_status"] == "SUCCESS"

def test_admin_policies_list():
    res = client.get("/api/v1/admin/policies")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 16
    assert len(data["policies"]) >= 16

    # Filter by origin
    res_local = client.get("/api/v1/admin/policies?origin=LOCAL")
    assert res_local.status_code == 200
    for p in res_local.json()["policies"]:
        assert (p.get("origin") or p.get("origin_type")) == "LOCAL"

def test_admin_policy_crud():
    # 1. Create policy
    new_policy_payload = {
        "id": "pol_admin_test_999",
        "title": "어드민 테스트 지원금",
        "origin_type": "LOCAL",
        "region_code": "seoul_gwanak",
        "region_name": "서울시 관악구",
        "managing_org": "테스트부서",
        "category": "CASH",
        "financial_value": {
            "monthly_amount_krw": 100000,
            "annual_amount_krw": 1200000,
            "display_amount": "월 100,000원"
        },
        "summary_3lines": ["누가: 테스트가구", "얼마: 10만원", "어떻게: 온라인 신청"],
        "target_eligibility": {
            "income_ceiling": "under_150",
            "housing_types": ["RENTAL_MONTHLY"],
            "required_tags": ["newlywed"]
        },
        "application_info": {
            "deadline_type": "REGULAR",
            "dday_date": "2026-12-31",
            "is_urgent": False,
            "required_documents": ["주민등록등본"],
            "contact_phone": "02-1234-5678"
        }
    }
    create_res = client.post("/api/v1/admin/policies", json=new_policy_payload)
    assert create_res.status_code == 200
    assert create_res.json()["status"] == "CREATED"
    assert create_res.json()["policy"]["id"] == "pol_admin_test_999"

    # 2. Update policy
    new_policy_payload["title"] = "어드민 테스트 지원금 (수정됨)"
    new_policy_payload["financial_value"]["display_amount"] = "월 200,000원"
    update_res = client.put("/api/v1/admin/policies/pol_admin_test_999", json=new_policy_payload)
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "UPDATED"
    assert update_res.json()["policy"]["title"] == "어드민 테스트 지원금 (수정됨)"

    # 3. Delete policy
    delete_res = client.delete("/api/v1/admin/policies/pol_admin_test_999")
    assert delete_res.status_code == 200
    assert delete_res.json()["status"] == "DELETED"
    assert delete_res.json()["deleted_id"] == "pol_admin_test_999"

    # 4. Verify 404 after deletion
    del_again = client.delete("/api/v1/admin/policies/pol_admin_test_999")
    assert del_again.status_code == 404

def test_admin_sync_trigger():
    res = client.post("/api/v1/admin/sync/trigger")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "SUCCESS"
    assert data["sync_metadata"]["sync_status"] == "SUCCESS"
    assert data["sync_metadata"]["total_active_policies"] >= 16

def test_admin_subscribers():
    res = client.get("/api/v1/admin/subscribers")
    assert res.status_code == 200
    data = res.json()
    assert data["total_active"] >= 1
    assert len(data["subscribers"]) >= 1
    sub = data["subscribers"][0]
    assert "subscription_id" in sub
    assert "user_name" in sub
    assert "billing_cycle" in sub
    assert "guarantee_days_remaining" in sub

def test_admin_affiliate_performance():
    res = client.get("/api/v1/admin/affiliate-performance")
    assert res.status_code == 200
    data = res.json()
    assert data["total_deals"] >= 5
    assert len(data["deals_performance"]) >= 5
    deal = data["deals_performance"][0]
    assert "deal_id" in deal
    assert "unit_payout_krw" in deal
    assert "total_clicks" in deal
    assert "estimated_commission_krw" in deal
