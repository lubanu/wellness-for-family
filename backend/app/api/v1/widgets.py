from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import json
from app.core.config import settings
from app.services.matching_engine import MatchingEngine
from app.services.monetization_engine import MonetizationEngine

router = APIRouter()

def load_catalog():
    if os.path.exists(settings.CATALOG_PATH):
        with open(settings.CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"policies": []}

class WidgetCalculationRequest(BaseModel):
    sido: str = Field(default="seoul", description="시/도")
    sigungu: str = Field(default="gwanak", description="시/군/구")
    family_type: str = Field(default="newlywed", description="newlywed, infant, youth, senior, single_parent")
    income_level: str = Field(default="medium", description="low (under 50), medium (under 150), high (over 180)")

@router.post("/calculate")
def calculate_widget_result(req: WidgetCalculationRequest):
    catalog = load_catalog()
    policies = catalog.get("policies", [])
    
    # Map widget simplified input to full household schema
    tag_map = {
        "newlywed": ["newlywed", "infant", "housing"],
        "infant": ["infant", "newlywed"],
        "youth": ["youth", "housing", "single"],
        "senior": ["senior"],
        "single_parent": ["single_parent", "infant"]
    }
    income_map = {
        "low": "under_50",
        "medium": "under_150",
        "high": "over_180"
    }
    
    tags = tag_map.get(req.family_type, ["newlywed"])
    income_bracket = income_map.get(req.income_level, "under_150")
    
    household_dict = {
        "sido": req.sido,
        "sigungu": req.sigungu,
        "income_bracket": income_bracket,
        "housing_type": "RENTAL_MONTHLY",
        "tags": tags,
        "claimed_policy_ids": []
    }
    
    result = MatchingEngine.evaluate_catalog(policies, household_dict)
    matched = result["policies"]
    
    # Top 3 policies
    top_policies = [
        {
            "id": p["id"],
            "title": p["title"],
            "managing_org": p["managing_org"],
            "amount_summary": p.get("financial_value", {}).get("display_amount", "지원금 확인 필요"),
            "category": p.get("category", "CASH")
        }
        for p in matched[:3]
    ]
    
    # Contextual deal
    deals = MonetizationEngine.get_contextual_deals(tags, [p.get("category", "CASH") for p in matched])
    featured_deal = deals[0] if deals else None
    
    return {
        "estimated_annual_krw": result["total_annual_amount"],
        "matched_count": result["matched_count"],
        "urgent_dday_count": result["urgent_dday_count"],
        "top_policies": top_policies,
        "featured_deal": featured_deal,
        "cta_deep_link": f"https://welfamily.kr/app?sido={req.sido}&sigungu={req.sigungu}&type={req.family_type}&ref=partner_widget"
    }

@router.get("/embed-code")
def get_embed_code():
    iframe_code = (
        '<iframe src="https://welfamily.kr/widget.html" '
        'width="100%" height="480" frameborder="0" '
        'style="border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;" '
        'title="WelFamily 우리 가족 맞춤 복지 간편 계산기"></iframe>'
    )
    return {
        "iframe_snippet": iframe_code,
        "recommended_width": "100%",
        "recommended_height": "480px",
        "supported_platforms": ["Tistory", "Naver Blog (Link Embed)", "Wordpress", "Velog", "Medium"]
    }
