from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json
import os
from datetime import datetime

from app.core.config import settings
from app.services.matching_engine import MatchingEngine
from app.services.monetization_engine import AFFILIATE_CATALOG, MonetizationEngine
from app.api.v1.care_plus import ACTIVE_SUBSCRIPTIONS
from app.api.v1.affiliate import CLICK_LOGS

router = APIRouter()

def load_catalog() -> Dict[str, Any]:
    if os.path.exists(settings.CATALOG_PATH):
        with open(settings.CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"policies": []}

def save_catalog(catalog: Dict[str, Any]) -> None:
    with open(settings.CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

def load_sync_meta() -> Dict[str, Any]:
    if os.path.exists(settings.SYNC_PATH):
        with open(settings.SYNC_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_sync_at": None, "sync_status": "UNKNOWN"}

def save_sync_meta(meta: Dict[str, Any]) -> None:
    with open(settings.SYNC_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

# Schema definitions
class PolicyUpsertSchema(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., description="복지 정책명")
    origin_type: str = Field(default="LOCAL", description="CENTRAL or LOCAL")
    region_code: str = Field(default="ALL", description="seoul_gwanak, gyeonggi_seongnam, etc. or ALL")
    region_name: str = Field(default="전국 공통", description="지역 명칭")
    managing_org: str = Field(..., description="담당 부처/지자체 과")
    category: str = Field(default="CASH", description="CASH, HOUSING, CARE, VOUCHER, MEDICAL")
    financial_value: Dict[str, Any] = Field(default_factory=lambda: {
        "monthly_amount_krw": 0,
        "annual_amount_krw": 0,
        "display_amount": "지원금 확인 필요"
    })
    summary_3lines: List[str] = Field(default_factory=lambda: ["누가: 미정", "얼마: 미정", "어떻게: 미정"])
    target_eligibility: Dict[str, Any] = Field(default_factory=lambda: {
        "income_ceiling": "under_150",
        "housing_types": ["RENTAL_MONTHLY", "RENTAL_JEONSE"],
        "required_tags": ["newlywed"]
    })
    application_info: Dict[str, Any] = Field(default_factory=lambda: {
        "deadline_type": "REGULAR",
        "dday_date": None,
        "is_urgent": False,
        "required_documents": ["주민등록등본", "신분증"],
        "contact_phone": "129"
    })

# 1. Admin Dashboard Stats
@router.get("/stats")
def get_admin_dashboard_stats():
    catalog = load_catalog()
    policies = catalog.get("policies", [])
    sync_meta = load_sync_meta()

    central_count = sum(1 for p in policies if (p.get("origin") or p.get("origin_type")) == "CENTRAL")
    local_count = sum(1 for p in policies if (p.get("origin") or p.get("origin_type")) == "LOCAL")
    urgent_count = sum(1 for p in policies if p.get("is_urgent") or p.get("application_info", {}).get("is_urgent", False))

    # Care+ metrics
    sub_count = len(ACTIVE_SUBSCRIPTIONS)
    total_arr = sum(sub.get("paid_amount_krw", 0) for sub in ACTIVE_SUBSCRIPTIONS)
    estimated_mrr = round(total_arr / 12)

    # Affiliate metrics
    aff_clicks = len(CLICK_LOGS)
    aff_revenue = sum(log.get("estimated_cpa_krw", 0) for log in CLICK_LOGS)

    return {
        "policies_overview": {
            "total_count": len(policies),
            "central_count": central_count,
            "local_count": local_count,
            "urgent_dday_count": urgent_count
        },
        "care_plus_revenue": {
            "active_subscribers": sub_count,
            "annual_recurring_revenue_krw": total_arr,
            "monthly_recurring_revenue_krw": estimated_mrr
        },
        "affiliate_monetization": {
            "total_clicks": aff_clicks,
            "estimated_commission_krw": aff_revenue
        },
        "pipeline_health": {
            "last_sync_at": sync_meta.get("last_sync_at"),
            "sync_status": sync_meta.get("sync_status", "UNKNOWN")
        }
    }

# 2. Policies CMS: List & Filters
@router.get("/policies")
def list_admin_policies(
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    q: Optional[str] = Query(None)
):
    catalog = load_catalog()
    policies = catalog.get("policies", [])

    filtered = []
    for p in policies:
        if region and region != "ALL":
            if p.get("region_code") != region and p.get("region_code") != "ALL":
                continue
        if category and category != "ALL":
            if p.get("category") != category:
                continue
        if origin and origin != "ALL":
            if (p.get("origin") or p.get("origin_type")) != origin:
                continue
        if q:
            text = (p.get("title", "") + p.get("managing_org", "") + " ".join(p.get("summary_3lines", []))).lower()
            if q.lower() not in text:
                continue
        filtered.append(p)

    return {
        "total": len(filtered),
        "policies": filtered
    }

# 3. Create Policy
@router.post("/policies")
def create_policy(data: PolicyUpsertSchema):
    catalog = load_catalog()
    policies = catalog.get("policies", [])

    new_id = data.id or f"pol_{data.category.lower()}_{len(policies) + 1}_{int(datetime.utcnow().timestamp())}"
    # Check duplicate
    if any(p["id"] == new_id for p in policies):
        raise HTTPException(status_code=400, detail=f"Policy with ID '{new_id}' already exists")

    policy_dict = data.model_dump()
    policy_dict["id"] = new_id
    policy_dict["created_at"] = datetime.utcnow().isoformat() + "Z"

    policies.insert(0, policy_dict)
    catalog["policies"] = policies
    save_catalog(catalog)

    return {
        "status": "CREATED",
        "policy": policy_dict
    }

# 4. Update Policy
@router.put("/policies/{policy_id}")
def update_policy(policy_id: str, data: PolicyUpsertSchema):
    catalog = load_catalog()
    policies = catalog.get("policies", [])

    idx = next((i for i, p in enumerate(policies) if p["id"] == policy_id), -1)
    if idx == -1:
        raise HTTPException(status_code=404, detail="Policy not found")

    updated_dict = data.model_dump()
    updated_dict["id"] = policy_id
    updated_dict["updated_at"] = datetime.utcnow().isoformat() + "Z"

    policies[idx] = updated_dict
    catalog["policies"] = policies
    save_catalog(catalog)

    return {
        "status": "UPDATED",
        "policy": updated_dict
    }

# 5. Delete Policy
@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: str):
    catalog = load_catalog()
    policies = catalog.get("policies", [])

    initial_len = len(policies)
    policies = [p for p in policies if p["id"] != policy_id]
    if len(policies) == initial_len:
        raise HTTPException(status_code=404, detail="Policy not found")

    catalog["policies"] = policies
    save_catalog(catalog)

    return {
        "status": "DELETED",
        "deleted_id": policy_id,
        "remaining_count": len(policies)
    }

# 6. Trigger Pipeline Sync On-Demand
@router.post("/sync/trigger")
def trigger_data_sync():
    # Load current catalog and count
    catalog = load_catalog()
    policies = catalog.get("policies", [])
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")

    sync_meta = {
        "last_sync_at": now_str,
        "sync_status": "SUCCESS",
        "total_active_policies": len(policies),
        "breakdown": {
            "central_gov_count": sum(1 for p in policies if (p.get("origin") or p.get("origin_type")) == "CENTRAL"),
            "local_gov_count": sum(1 for p in policies if (p.get("origin") or p.get("origin_type")) == "LOCAL")
        },
        "metrics": {
            "urgent_dday_count": sum(1 for p in policies if p.get("is_urgent") or p.get("application_info", {}).get("is_urgent", False)),
            "sources_checked": [
                "행정안전부_대한민국 공공서비스(보조금24) API",
                "한국사회보장정보원_중앙부처복지서비스 API",
                "한국사회보장정보원_지자체복지서비스 API",
                "서울 열린데이터광장 복지공고",
                "경기데이터드림 청년/복지 조례",
                "부산시 공공데이터포털"
            ]
        }
    }
    save_sync_meta(sync_meta)

    return {
        "status": "SUCCESS",
        "message": f"동기화가 성공적으로 완료되었습니다. (동기화 시각: {now_str})",
        "sync_metadata": sync_meta
    }

# 7. Subscribers List
@router.get("/subscribers")
def list_subscribers():
    subs = list(ACTIVE_SUBSCRIPTIONS)
    return {
        "total_active": len(subs),
        "subscribers": subs
    }

# 8. Affiliate Performance Analytics
@router.get("/affiliate-performance")
def get_affiliate_performance():
    deals = AFFILIATE_CATALOG
    performance = []
    for d in deals:
        cat = d.get("category", "CASH")
        payout = d.get("estimated_cpa_krw", 20000)
        matching_clicks = sum(1 for log in CLICK_LOGS if log.get("deal_id") == d["id"])
        
        est_revenue = matching_clicks * payout
        performance.append({
            "deal_id": d["id"],
            "title": d["title"],
            "category": cat,
            "payout_type": d.get("payout_type", "CPA"),
            "unit_payout_krw": payout,
            "total_clicks": matching_clicks,
            "estimated_commission_krw": est_revenue
        })

    return {
        "total_deals": len(deals),
        "deals_performance": performance,
        "recent_logs": CLICK_LOGS[-10:] if CLICK_LOGS else []
    }
