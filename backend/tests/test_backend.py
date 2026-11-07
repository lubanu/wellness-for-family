import pytest
from fastapi.testclient import TestClient
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app

client = TestClient(app)

def test_root_and_health():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "WelFamily API"
    assert data["status"] == "ONLINE"

    health = client.get("/health")
    assert health.status_code == 200
    h_data = health.json()
    assert h_data["status"] == "HEALTHY"
    assert h_data["catalog_policies_count"] >= 16

def test_get_policies():
    # Fetch all
    response = client.get("/api/v1/policies/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 16
    assert len(data["policies"]) >= 16

    # Region filter: seoul_gwanak
    res_reg = client.get("/api/v1/policies/?region=seoul_gwanak")
    assert res_reg.status_code == 200
    reg_policies = res_reg.json()["policies"]
    for p in reg_policies:
        assert p["region_code"] in ["ALL", "seoul_gwanak", "seoul"]

    # Keyword filter
    res_q = client.get("/api/v1/policies/?q=부모급여")
    assert res_q.status_code == 200
    assert any("부모급여" in p["title"] for p in res_q.json()["policies"])

def test_get_policy_detail():
    response = client.get("/api/v1/policies/pol_parent_0")
    assert response.status_code == 200
    data = response.json()
    assert data["policy"]["id"] == "pol_parent_0"
    assert "recommended_deals" in data
    assert len(data["recommended_deals"]) > 0

    # 404 for unknown policy
    res_404 = client.get("/api/v1/policies/pol_non_existent")
    assert res_404.status_code == 404

def test_matching_dashboard():
    payload = {
        "sido": "seoul",
        "sigungu": "gwanak",
        "income_bracket": "under_150",
        "housing_type": "RENTAL_MONTHLY",
        "tags": ["newlywed", "infant", "housing"],
        "claimed_policy_ids": []
    }
    response = client.post("/api/v1/matching/dashboard", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["financial_metrics"]["matched_policy_count"] >= 3
    assert data["financial_metrics"]["total_annual_amount_krw"] > 0
    assert data["financial_metrics"]["unclaimed_annual_amount_krw"] > 0
    assert "care_plus_plan" in data
    assert "monetization_deals" in data
    assert len(data["monetization_deals"]) > 0

def test_calendar_events():
    response = client.get("/api/v1/matching/calendar?year=2026&month=11")
    assert response.status_code == 200
    data = response.json()
    assert data["year"] == 2026
    assert data["month"] == 11
    assert len(data["events"]) >= 3
    assert any(e["is_urgent"] for e in data["events"])

def test_affiliate_deals_and_tracking():
    # List deals
    res_deals = client.get("/api/v1/affiliate/deals")
    assert res_deals.status_code == 200
    deals = res_deals.json()["deals"]
    assert len(deals) >= 5

    # Track a click
    first_deal = deals[0]
    track_payload = {
        "deal_id": first_deal["id"],
        "user_session_id": "test_session_123",
        "referrer_page": "dashboard_test"
    }
    res_track = client.post("/api/v1/affiliate/track-click", json=track_payload)
    assert res_track.status_code == 200
    track_data = res_track.json()
    assert track_data["status"] == "TRACKED"
    assert track_data["redirect_url"] == first_deal["outbound_url"]

    # Verify stats
    res_stats = client.get("/api/v1/affiliate/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    assert stats["total_clicks"] >= 1
    assert stats["estimated_revenue_krw"] > 0

def test_care_plus_subscription_flow():
    # Summary
    summary = client.get("/api/v1/care-plus/summary")
    assert summary.status_code == 200
    assert summary.json()["pricing"]["annual_krw"] == 39000

    # Calculate ROI
    roi_req = {"unclaimed_amount_krw": 3600000, "household_size": 3}
    res_roi = client.post("/api/v1/care-plus/calculate-roi", json=roi_req)
    assert res_roi.status_code == 200
    roi_data = res_roi.json()
    assert "expected_roi_percentage" in roi_data
    assert roi_data["annual_price_krw"] == 39000

    # Subscribe
    sub_payload = {
        "user_name": "테스터",
        "phone_number": "010-9999-8888",
        "billing_cycle": "ANNUAL",
        "payment_method": "KAKAO_PAY"
    }
    res_sub = client.post("/api/v1/care-plus/subscribe", json=sub_payload)
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    assert sub_data["status"] == "SUCCESS"
    assert sub_data["subscription"]["vip_benefits_activated"] is True
    assert sub_data["subscription"]["paid_amount_krw"] == 39000

def test_widgets_endpoint():
    calc_payload = {
        "sido": "seoul",
        "sigungu": "gwanak",
        "family_type": "newlywed",
        "income_level": "medium"
    }
    res_calc = client.post("/api/v1/widgets/calculate", json=calc_payload)
    assert res_calc.status_code == 200
    calc_data = res_calc.json()
    assert calc_data["estimated_annual_krw"] > 0
    assert len(calc_data["top_policies"]) > 0
    assert calc_data["featured_deal"] is not None

    res_embed = client.get("/api/v1/widgets/embed-code")
    assert res_embed.status_code == 200
    assert "<iframe" in res_embed.json()["iframe_snippet"]


def test_care_plus_roi_invents_nothing_when_unclaimed_is_zero():
    res = client.post("/api/v1/care-plus/calculate-roi", json={"unclaimed_amount_krw": 0})
    assert res.status_code == 200
    data = res.json()
    assert data["estimated_unclaimed_benefit_krw"] == 0
    assert data["expected_roi_percentage"] == "0.0%"
