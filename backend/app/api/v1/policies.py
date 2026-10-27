from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import json
import os
from app.core.config import settings
from app.services.monetization_engine import MonetizationEngine

router = APIRouter()

def load_catalog():
    if os.path.exists(settings.CATALOG_PATH):
        with open(settings.CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"policies": []}

@router.get("/")
def get_policies(
    region: Optional[str] = Query(None, description="Region code e.g. seoul_gwanak or ALL"),
    category: Optional[str] = Query(None, description="Category filter e.g. CASH, HOUSING"),
    q: Optional[str] = Query(None, description="Search keyword")
):
    catalog = load_catalog()
    policies = catalog.get("policies", [])
    
    filtered = []
    for p in policies:
        if region and region != "ALL":
            p_reg = p.get("region_code", "ALL")
            if p_reg != "ALL" and p_reg != region and not region.startswith(p_reg):
                continue
        if category and category != "ALL":
            if p.get("category") != category:
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

@router.get("/{policy_id}")
def get_policy_detail(policy_id: str):
    catalog = load_catalog()
    for p in catalog.get("policies", []):
        if p.get("id") == policy_id:
            cat = p.get("category", "CASH")
            tags = p.get("target_eligibility", {}).get("required_tags", [])
            deals = MonetizationEngine.get_contextual_deals(tags, [cat])
            return {
                "policy": p,
                "recommended_deals": deals
            }
    raise HTTPException(status_code=404, detail="Policy not found")
