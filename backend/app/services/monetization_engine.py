from typing import List, Dict, Any

AFFILIATE_CATALOG = [
    {
        "id": "aff_moving_quote",
        "category": "HOUSING",
        "title": "📦 [이사 필수 제휴] 검증된 포장이사 1분 무료 비교견적",
        "description": "이사비 지원금 신청 전, 관내 평점 4.9점 우수 이사업체들의 견적을 무료로 비교하고 최대 10만원 절약하세요.",
        "payout_type": "CPA",
        "estimated_cpa_krw": 25000,
        "badge": "이사비 지원 대상자 추천",
        "target_tags": ["housing", "newlywed"],
        "cta_text": "무료 방문견적 1분 신청",
        "outbound_url": "https://example.com/affiliate/moving",
        "ftc_notice": "※ 본 추천은 제휴마케팅 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다."
    },
    {
        "id": "aff_internet_cashback",
        "category": "HOUSING",
        "title": "🌐 [전입 혜택] 인터넷+IPTV 개통 시 최대 47만 원 당일 현금 지급",
        "description": "이사 또는 전입 시 인터넷 통신사 신규 가입/이전으로 국가 공시 최대 사은품 47만 원을 당일 계좌로 지급받으세요.",
        "payout_type": "CPA",
        "estimated_cpa_krw": 65000,
        "badge": "전입자 필수 혜택",
        "target_tags": ["housing", "newlywed", "youth"],
        "cta_text": "통신 3사 사은품 실시간 비교",
        "outbound_url": "https://example.com/affiliate/internet",
        "ftc_notice": "※ 본 추천은 제휴마케팅 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다."
    },
    {
        "id": "aff_national_card",
        "category": "CARE",
        "title": "💳 [출산·임산부] 국민행복카드 신규 발급 시 15만 원 현금 캐시백",
        "description": "첫만남이용권(200만원) 및 바우처 수령 필수 카드! 신규 발급 후 10만원 이상 이용 시 15만원 현금 캐시백을 드립니다.",
        "payout_type": "CPA",
        "estimated_cpa_krw": 120000,
        "badge": "바우처 필수 연계",
        "target_tags": ["infant", "newlywed"],
        "cta_text": "15만 원 캐시백 신청하기",
        "outbound_url": "https://example.com/affiliate/card",
        "ftc_notice": "※ 본 추천은 제휴마케팅 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다."
    },
    {
        "id": "aff_coupang_baby",
        "category": "VOUCHER",
        "title": "👶 [바우처 사용처] 로켓배송 친환경 기저귀·분유 최저가 기획전",
        "description": "부모급여 및 첫만남이용권 바우처로 즉시 결제 가능한 필수 영유아 기저귀, 분유, 물티슈 모음전입니다.",
        "payout_type": "CPS",
        "estimated_cpa_krw": 5000,
        "badge": "바우처 사용 가능",
        "target_tags": ["infant"],
        "cta_text": "로켓배송 육아 필수템 특가 보기",
        "outbound_url": "https://link.coupang.com/example",
        "ftc_notice": "※ 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
    },
    {
        "id": "aff_parking_account",
        "category": "CASH",
        "title": "💰 [지원금 입금용] 연 최대 4.0% 비대면 고금리 파킹통장",
        "description": "아동수당, 부모급여, 청년수당 입금 통장으로 하루만 맡겨도 연 4.0% 이자가 쌓이는 수수료 무제한 면제 통장을 개설하세요.",
        "payout_type": "CPA",
        "estimated_cpa_krw": 20000,
        "badge": "수당 전용 우대 금리",
        "target_tags": ["youth", "infant"],
        "cta_text": "1금융권 파킹통장 1분 개설",
        "outbound_url": "https://example.com/affiliate/banking",
        "ftc_notice": "※ 본 추천은 제휴마케팅 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다."
    }
]

class MonetizationEngine:
    @staticmethod
    def get_contextual_deals(user_tags: List[str], categories: List[str]) -> List[Dict[str, Any]]:
        deals = []
        user_tag_set = set(user_tags)
        for deal in AFFILIATE_CATALOG:
            # Match by category or tags
            match_cat = deal["category"] in categories
            match_tag = bool(user_tag_set.intersection(set(deal["target_tags"])))
            if match_cat or match_tag:
                deals.append(deal)
        return deals if deals else AFFILIATE_CATALOG[:2]

    @staticmethod
    def calculate_care_plus_roi(unclaimed_amount: int) -> Dict[str, Any]:
        annual_fee = 39000
        roi_ratio = round((unclaimed_amount / annual_fee) * 100, 1) if unclaimed_amount > 0 else 0.0

        return {
            "tier_name": "WelFamily Care+ (복지 케어 플러스)",
            "monthly_price_krw": 3900,
            "annual_price_krw": annual_fee,
            "estimated_unclaimed_benefit_krw": unclaimed_amount,
            "expected_roi_percentage": f"{roi_ratio}%",
            "features": [
                {"title": "선착순 공고 0초 즉시 알림", "desc": "예산 소진형 지자체 지원 사업 등록 시 대기 없이 카카오 알림톡/SMS 즉시 전송"},
                {"title": "정부24 연계 서류 자동완성 팩", "desc": "주민등록등본, 건보료 확인서 등 필수 서류를 클릭 한 번에 일괄 PDF 압축 패키징"},
                {"title": "복지 전문 행정사 1:1 전담 Q&A", "desc": "복잡한 소득인정액 모의계산 및 이의신청 실시간 전문 자문 제공"},
                {"title": "우리 가족 숨은 환급금 추적", "desc": "미청구 공공 지원금 및 지자체 조례 숨은 환급금 자동 스캔"}
            ]
        }
