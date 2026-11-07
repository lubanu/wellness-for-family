from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from app.services.monetization_engine import MonetizationEngine

router = APIRouter()

# In-memory subscriptions store
ACTIVE_SUBSCRIPTIONS: List[Dict[str, Any]] = []

class CarePlusRoiRequest(BaseModel):
    unclaimed_amount_krw: int = Field(..., description="Amount of unclaimed benefits in KRW")
    household_size: int = Field(default=3, description="Number of household members")

class CarePlusSubscribeRequest(BaseModel):
    user_name: str = Field(default="홍길동", description="User or head of household name")
    phone_number: str = Field(default="010-1234-5678", description="Contact phone for instant alerts")
    billing_cycle: str = Field(default="ANNUAL", description="'ANNUAL' (39,000 KRW) or 'MONTHLY' (3,900 KRW)")
    payment_method: str = Field(default="KAKAO_PAY", description="KAKAO_PAY, TOSS_PAY, NAVER_PAY, or CARD")

@router.get("/summary")
def get_care_plus_summary():
    return {
        "tier": "WelFamily Care+ (복지 케어 플러스 프리미엄)",
        "pricing": {
            "monthly_krw": 3900,
            "annual_krw": 39000,
            "annual_discount_percentage": 17,
            "daily_equivalent_krw": 107
        },
        "guarantee": "가입 후 1년 내 미수령 복지금 1건 이상 미발견 시 100% 전액 환불 보장제",
        "key_features": [
            {
                "id": "feat_instant_alert",
                "title": "⚡ 선착순 지자체 공고 0초 즉시 알림",
                "desc": "예산 소진형 지자체 지원 사업 등록 시 대기 없이 카카오 알림톡/SMS 즉시 발송 (일반 회원은 24시간 후 발송)"
            },
            {
                "id": "feat_doc_pack",
                "title": "📄 정부24 필수서류 원클릭 자동완성 팩",
                "desc": "주민등록등본, 건강보험료 납부확인서, 가족관계증명서 등 필수 서류를 번거로운 수기 발급 없이 PDF 패키지로 자동 결합"
            },
            {
                "id": "feat_qna",
                "title": "⚖️ 복지 전문 행정사 1:1 비대면 자문",
                "desc": "복잡한 소득인정액(재산의 소득환산율) 모의계산 및 이의신청 전담 행정사 검토 지원"
            },
            {
                "id": "feat_refund_tracker",
                "title": "🔍 숨은 환급금·바우처 잔액 자동 추적",
                "desc": "지자체 조례별 숨은 환급금(출산축하금, 청년교통비 등) 및 유효기간 임박 바우처 푸시 알림"
            }
        ]
    }

@router.post("/calculate-roi")
def calculate_roi(req: CarePlusRoiRequest):
    return MonetizationEngine.calculate_care_plus_roi(req.unclaimed_amount_krw)

@router.post("/subscribe")
def subscribe_care_plus(req: CarePlusSubscribeRequest):
    if req.billing_cycle not in ["ANNUAL", "MONTHLY"]:
        raise HTTPException(status_code=400, detail="billing_cycle must be ANNUAL or MONTHLY")
        
    price = 39000 if req.billing_cycle == "ANNUAL" else 3900
    sub_id = f"sub_vip_{len(ACTIVE_SUBSCRIPTIONS) + 1:04d}"
    now = datetime.utcnow()
    expires_at = now + timedelta(days=365 if req.billing_cycle == "ANNUAL" else 30)
    
    subscription = {
        "subscription_id": sub_id,
        "user_name": req.user_name,
        "phone_number": req.phone_number,
        "billing_cycle": req.billing_cycle,
        "paid_amount_krw": price,
        "payment_method": req.payment_method,
        "status": "ACTIVE",
        "created_at": now.isoformat() + "Z",
        "expires_at": expires_at.isoformat() + "Z",
        "vip_benefits_activated": True
    }
    ACTIVE_SUBSCRIPTIONS.append(subscription)
    
    return {
        "status": "SUCCESS",
        "message": f"축하합니다! WelFamily Care+ 프리미엄 혜택이 활성화되었습니다. (회원번호: {sub_id})",
        "subscription": subscription
    }
