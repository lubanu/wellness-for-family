from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.services.monetization_engine import AFFILIATE_CATALOG, MonetizationEngine

router = APIRouter()

# In-memory click tracking store (persists during process lifetime)
CLICK_LOGS: List[Dict[str, Any]] = []

class ClickTrackRequest(BaseModel):
    deal_id: str = Field(..., description="ID of the clicked affiliate deal")
    user_session_id: Optional[str] = Field("anon_guest", description="Anonymous session ID")
    referrer_page: Optional[str] = Field("dashboard", description="Origin page or widget")
    metadata: Optional[Dict[str, Any]] = None

@router.get("/deals")
def list_affiliate_deals(
    category: Optional[str] = Query(None, description="Category filter (HOUSING, CARE, CASH, VOUCHER)"),
    tag: Optional[str] = Query(None, description="User tag filter (e.g. infant, newlywed, housing)")
):
    deals = AFFILIATE_CATALOG
    if category and category != "ALL":
        deals = [d for d in deals if d.get("category") == category]
    if tag:
        deals = [d for d in deals if tag in d.get("target_tags", [])]
    return {
        "total": len(deals),
        "deals": deals
    }

@router.post("/track-click")
def track_affiliate_click(req: ClickTrackRequest):
    deal = next((d for d in AFFILIATE_CATALOG if d["id"] == req.deal_id), None)
    if not deal:
        raise HTTPException(status_code=404, detail=f"Affiliate deal '{req.deal_id}' not found")
    
    event = {
        "event_id": f"clk_{len(CLICK_LOGS) + 1}",
        "deal_id": deal["id"],
        "category": deal["category"],
        "payout_type": deal["payout_type"],
        "estimated_cpa_krw": deal["estimated_cpa_krw"],
        "user_session_id": req.user_session_id,
        "referrer_page": req.referrer_page,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "redirect_url": deal["outbound_url"]
    }
    CLICK_LOGS.append(event)
    
    return {
        "status": "TRACKED",
        "event": event,
        "redirect_url": deal["outbound_url"]
    }

@router.get("/stats")
def get_affiliate_stats():
    total_clicks = len(CLICK_LOGS)
    estimated_revenue = sum(log["estimated_cpa_krw"] for log in CLICK_LOGS)
    
    category_breakdown = {}
    for log in CLICK_LOGS:
        cat = log["category"]
        category_breakdown[cat] = category_breakdown.get(cat, 0) + 1
        
    return {
        "total_clicks": total_clicks,
        "estimated_revenue_krw": estimated_revenue,
        "category_breakdown": category_breakdown,
        "recent_clicks": CLICK_LOGS[-10:] if CLICK_LOGS else []
    }
