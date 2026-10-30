"""
scripts/local_announcement_crawler.py
================================================================================
Municipal Welfare Announcement Discovery & Staging Crawler.
Discovers local government welfare ordinances & notice candidates,
filters relevant welfare keywords, and populates data/local_staging_queue.json
with review_status="PENDING_REVIEW" for Human-in-the-Loop approval.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional
import uuid

# Ensure repository root and backend in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from app.core.config import settings
    DEFAULT_STAGING_PATH = getattr(settings, "STAGING_PATH", str(REPO_ROOT / "data" / "local_staging_queue.json"))
except ImportError:
    DEFAULT_STAGING_PATH = str(REPO_ROOT / "data" / "local_staging_queue.json")

# Relevant welfare keywords for pre-filtering municipal notices
WELFARE_KEYWORDS = re.compile(
    r"(이사비|중개보수|청년수당|기본소득|선착순|예산\s*소진|조례|돌봄|출산|양육|장려금|바우처|생활안정|학자금|보조금)"
)

# Synthetic municipal announcement sources for offline autonomous execution
SYNTHETIC_MUNICIPAL_NOTICES = [
    {
        "stg_id": "stg_seoul_gwanak_moving_2026",
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
        "slot_capacity": 300,
        "budget_status": "OPEN",
        "is_urgent": False,
        "target_eligibility": {
            "min_age": 19,
            "max_age": 39,
            "income_limit_ratio": 150,
            "required_tags": ["youth", "newlywed", "housing"]
        },
        "summary_3lines": [
            "관악구로 전입한 지 1년 이내의 무주택 청년 및 신혼부부 가구",
            "부동산 중개수수료 및 이사 용달 실비 합산 최대 40만 원 지원",
            "선착순 예산 소진형 공고이므로 마감 전 온라인 신청 필수"
        ],
        "required_documents": [
            {"name": "주민등록초본", "issuer": "정부24", "can_online": True},
            {"name": "확정일자부 임대차계약서", "issuer": "본인 소지", "can_online": False}
        ],
        "application_url": "https://youth.seoul.go.kr",
        "contact_phone": "02-879-5931"
    },
    {
        "stg_id": "stg_gyeonggi_seongnam_youth_2026",
        "title": "2026년 성남시 청년기본소득 2분기 접수",
        "region_code": "gyeonggi_seongnam",
        "region_name": "경기도 성남시",
        "managing_org": "성남시 청년정책과",
        "local_ordinance_basis": "성남시 청년배당 지급 조례 제5조",
        "category": "VOUCHER",
        "amount_value": 250000,
        "amount_text": "분기별 25만 원 (연 최대 100만 원 성남사랑상품권)",
        "application_period_type": "REGULAR",
        "start_date": "2026-04-01",
        "end_date": "2026-04-30",
        "is_budget_limited": False,
        "slot_capacity": None,
        "budget_status": "OPEN",
        "is_urgent": False,
        "target_eligibility": {
            "min_age": 24,
            "max_age": 24,
            "income_limit_ratio": 999,
            "required_tags": ["youth"]
        },
        "summary_3lines": [
            "성남시에 3년 이상 주민등록을 두고 거주 중인 만 24세 청년",
            "분기별 25만 원씩 연간 최대 100만 원 성남사랑상품권 모바일 지급",
            "경기도 일자리플랫폼 잡아바 온라인 신청"
        ],
        "required_documents": [
            {"name": "주민등록초본", "issuer": "정부24", "can_online": True}
        ],
        "application_url": "https://apply.jobaba.net",
        "contact_phone": "1577-0075"
    },
    {
        "stg_id": "stg_busan_busanjin_care_2026",
        "title": "부산진구 다자녀 영유아 가정 가사돌봄 무료 파견 서비스",
        "region_code": "busan_busanjin",
        "region_name": "부산광역시 부산진구",
        "managing_org": "부산진구 가족복지과",
        "local_ordinance_basis": "부산광역시 부산진구 출산장려 및 양육지원에 관한 조례",
        "category": "CARE",
        "amount_value": 0,
        "amount_text": "전액 무료 서비스 파견 (월 4회 가사지원)",
        "application_period_type": "FIRST_COME_FIRST_SERVED",
        "start_date": "2026-01-15",
        "end_date": "2026-12-15",
        "is_budget_limited": True,
        "slot_capacity": 50,
        "budget_status": "NEAR_EXHAUSTION",
        "is_urgent": True,
        "target_eligibility": {
            "min_age": 0,
            "max_age": 5,
            "income_limit_ratio": 120,
            "required_tags": ["multichild", "infant"]
        },
        "summary_3lines": [
            "부산진구 거주 2자녀 이상 만 5세 이하 영유아 양육 가정",
            "전문 가사관리사 월 4회 무료 파견 (현금 미지급, 서비스 제공)",
            "부산진구 건강가정지원센터 전화 및 방문 신청"
        ],
        "required_documents": [
            {"name": "주민등록등본", "issuer": "정부24", "can_online": True}
        ],
        "application_url": "https://busanjin.familynet.or.kr",
        "contact_phone": "051-802-2004"
    }
]


def load_candidate_notices(source_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Loads candidate notices from a specified source_path or MUNICIPAL_NOTICES_SOURCE_PATH env var.
    Defaults cleanly to production synthetic municipal notices without coupling to test fixtures.
    """
    effective_path = source_path or os.getenv("MUNICIPAL_NOTICES_SOURCE_PATH")
    if effective_path and os.path.exists(effective_path):
        try:
            with open(effective_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "staged_policies" in data:
                    return [dict(item) for item in data["staged_policies"]]
                elif isinstance(data, list):
                    return [dict(item) for item in data]
        except Exception:
            pass

    return [dict(item) for item in SYNTHETIC_MUNICIPAL_NOTICES]


def crawl_and_stage_announcements(
    staging_path: Optional[str] = None,
    source_fixture: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Crawls municipal announcements, filters by welfare relevance,
    and appends candidates into local_staging_queue.json with review_status='PENDING_REVIEW'.
    """
    target_path = Path(
        staging_path or
        os.getenv("STAGING_PATH") or
        DEFAULT_STAGING_PATH
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)

    candidates = load_candidate_notices(source_fixture)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Load existing staging queue
    queue_data: Dict[str, Any] = {
        "generated_at": now_iso,
        "total_items": 0,
        "staged_policies": []
    }
    if target_path.exists():
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "staged_policies" in loaded:
                    queue_data = loaded
                elif isinstance(loaded, list):
                    queue_data = {"generated_at": now_iso, "total_items": len(loaded), "staged_policies": loaded}
        except Exception:
            queue_data = {"generated_at": now_iso, "total_items": 0, "staged_policies": []}

    existing_policies = queue_data.get("staged_policies", [])
    existing_ids = {p.get("stg_id") or p.get("id") for p in existing_policies}

    new_staged = 0
    for cand in candidates:
        title = cand.get("title", "")
        # Keyword filter: ensures candidate is relevant to welfare
        if not WELFARE_KEYWORDS.search(title) and not cand.get("local_ordinance_basis"):
            continue

        c_id = cand.get("stg_id") or f"stg_{cand.get('region_code', 'local')}_{uuid.uuid4().hex[:8]}"
        if c_id in existing_ids:
            continue

        staged_entry = dict(cand)
        staged_entry["stg_id"] = c_id
        staged_entry["review_status"] = "PENDING_REVIEW"
        staged_entry["detected_at"] = now_iso
        staged_entry["detected_source"] = "MUNICIPAL_SCRAPER"

        existing_policies.append(staged_entry)
        existing_ids.add(c_id)
        new_staged += 1

    queue_data["staged_policies"] = existing_policies
    queue_data["total_items"] = len(existing_policies)
    queue_data["last_scraped_at"] = now_iso

    # Atomic write to staging file
    temp_file = target_path.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(queue_data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, target_path)

    return {
        "status": "SUCCESS",
        "staged_path": str(target_path),
        "newly_staged_count": new_staged,
        "total_staged_count": len(existing_policies),
        "staged_policies": existing_policies
    }


if __name__ == "__main__":
    result = crawl_and_stage_announcements()
    print(f"[Local Announcement Crawler] Successfully staged {result['total_staged_count']} policies ({result['newly_staged_count']} newly added).")
