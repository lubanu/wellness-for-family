from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import json
import os
from app.core.config import settings
from app.services.matching_engine import MatchingEngine
from app.services.monetization_engine import MonetizationEngine

router = APIRouter()

def load_catalog():
    if os.path.exists(settings.CATALOG_PATH):
        with open(settings.CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"policies": []}

class MemberSchema(BaseModel):
    relation: str = "SELF"
    age_years: int = 30
    age_months: int = 0
    is_pregnant: bool = False
    is_disabled: bool = False

class HouseholdRequest(BaseModel):
    sido: str = Field(default="seoul", description="시/도 코드")
    sigungu: str = Field(default="gwanak", description="시/군/구 코드")
    income_bracket: str = Field(default="under_150", description="중위소득 구간 (under_50, under_100, under_150, under_180, over_180)")
    housing_type: str = Field(default="RENTAL_MONTHLY", description="주거 점유 형태")
    tags: List[str] = Field(default=["newlywed", "infant", "housing"], description="가구 특성 태그")
    members: Optional[List[MemberSchema]] = None
    claimed_policy_ids: Optional[List[str]] = None

@router.post("/dashboard")
def calculate_dashboard(req: HouseholdRequest):
    catalog = load_catalog()
    policies = catalog.get("policies", [])
    
    household_dict = req.model_dump()
    result = MatchingEngine.evaluate_catalog(policies, household_dict)
    
    # Calculate Care+ ROI
    care_plus = MonetizationEngine.calculate_care_plus_roi(result["unclaimed_annual_amount"])
    
    # Extract categories of matched policies to get contextual affiliate deals
    matched_cats = list(set([p.get("category", "CASH") for p in result["policies"]]))
    deals = MonetizationEngine.get_contextual_deals(req.tags, matched_cats)
    
    return {
        "status": "SUCCESS",
        "household_summary": {
            "region": f"{req.sido}_{req.sigungu}",
            "income_bracket": req.income_bracket,
            "tags": req.tags
        },
        "financial_metrics": {
            "total_annual_amount_krw": result["total_annual_amount"],
            "claimed_annual_amount_krw": result["claimed_annual_amount"],
            "unclaimed_annual_amount_krw": result["unclaimed_annual_amount"],
            "matched_policy_count": result["matched_count"],
            "urgent_dday_count": result["urgent_dday_count"]
        },
        "care_plus_plan": care_plus,
        "monetization_deals": deals,
        "matched_policies": result["policies"]
    }

@router.get("/calendar")
def get_calendar_events(year: int = 2026, month: int = 11):
    events = [
        {
            "id": "evt_disability",
            "date": f"{year}-{month:02d}-20",
            "day": 20,
            "type": "PAYMENT",
            "title": "장애인연금 정기 입금일",
            "amount_krw": 403180,
            "badge_color": "blue",
            "is_urgent": False
        },
        {
            "id": "evt_regular_payout",
            "date": f"{year}-{month:02d}-25",
            "day": 25,
            "type": "PAYMENT",
            "title": "정부 공통 부모급여 + 아동수당 계좌 입금일",
            "amount_krw": 600000,
            "badge_color": "emerald",
            "is_urgent": False
        },
        {
            "id": "evt_gwanak_moving_dday",
            "date": f"{year}-{month:02d}-30",
            "day": 30,
            "type": "DEADLINE",
            "title": "관악구 청년·신혼부부 이사비 및 중개보수 지원 마감 (선착순)",
            "amount_krw": 400000,
            "badge_color": "orange",
            "is_urgent": True
        }
    ]
    return {
        "year": year,
        "month": month,
        "total_events": len(events),
        "events": events
    }
