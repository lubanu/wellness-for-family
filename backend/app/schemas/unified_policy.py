"""
backend/app/schemas/unified_policy.py
================================================================================
Canonical Pydantic v2 schemas and domain models for WelFamily Welfare System.
Unifies Central Government, Local Government, and IT Developer perspectives.
"""

from datetime import date, datetime, timezone
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


# ==============================================================================
# Domain Enums
# ==============================================================================

class PolicyOrigin(str, Enum):
    CENTRAL = "CENTRAL"   # 중앙정부 (전국 공통)
    LOCAL = "LOCAL"       # 지방정부 (시·도 및 시·군·구 특화)


class PolicyCategory(str, Enum):
    CASH = "CASH"               # 현금지원 (수당, 급여, 출산장려금, 기본소득 등)
    VOUCHER = "VOUCHER"         # 바우처/이용권 (첫만남이용권, 아이돌봄쿠폰 등)
    DISCOUNT = "DISCOUNT"       # 요금감면 (전기요금, 도시가스, 통신비 등)
    CARE = "CARE"               # 돌봄서비스 (산모·신생아 건강관리, 가사간병 등)
    HOUSING = "HOUSING"         # 주거/금융 (이사비, 중개보수, 전세대출이자 등)
    MEDICAL = "MEDICAL"         # 의료/건강 (난임시술비, 미숙아의료비 등)
    JOB = "JOB"                 # 일자리/창업 (청년구직활동지원금 등)
    EDUCATION = "EDUCATION"     # 교육/장학 (입학준비금, 급식비 등)


class BudgetStatus(str, Enum):
    OPEN = "OPEN"                       # 접수중
    PLENTY = "PLENTY"                   # 예산 여유 (소진율 50% 미만)
    HALF_CONSUMED = "HALF_CONSUMED"     # 예산 50% 이상 소진
    NEAR_EXHAUSTION = "NEAR_EXHAUSTION" # 마감 임박 (잔여 예산 20% 미만 / 정원 임박)
    EXHAUSTED = "EXHAUSTED"             # 예산 전액 소진 / 선착순 마감
    CLOSING_SOON = "CLOSING_SOON"       # 마감 임박 상태
    ALWAYS_OPEN = "ALWAYS_OPEN"         # 상시 신청 가능 (예산 제한 없음)
    CLOSED = "CLOSED"                   # 신청 기간 만료로 인한 정상 종료


class ApplicationPeriodType(str, Enum):
    FIRST_COME_FIRST_SERVED = "FIRST_COME_FIRST_SERVED" # 선착순 / 예산소진형
    FIRST_COME = "FIRST_COME"                           # 선착순 축약
    FIXED_PERIOD = "FIXED_PERIOD"                       # 특정 기간 접수형
    REGULAR = "REGULAR"                                 # 정기 접수형
    ALWAYS_OPEN = "ALWAYS_OPEN"                         # 상시 접수형
    ALWAYS = "ALWAYS"                                   # 상시 축약


CATEGORY_NAME_MAP = {
    PolicyCategory.CASH: "현금지원",
    PolicyCategory.VOUCHER: "이용권/바우처",
    PolicyCategory.DISCOUNT: "감면/할인",
    PolicyCategory.CARE: "돌봄서비스",
    PolicyCategory.HOUSING: "주거/금융",
    PolicyCategory.MEDICAL: "의료/건강",
    PolicyCategory.JOB: "일자리/창업",
    PolicyCategory.EDUCATION: "교육/장학",
}

PHONE_PATTERN = re.compile(
    r"^(1[3-8]\d{2}|129|120|02-\d{3,4}-\d{4}|0[3-6][1-5]-\d{3,4}-\d{4}|010-\d{4}-\d{4}|070-\d{4}-\d{4})$"
)


# ==============================================================================
# Value Objects & Nested Schemas
# ==============================================================================

class RequiredDocument(BaseModel):
    name: str = Field(..., description="구비서류 명칭 (예: 주민등록등본, 건강보험자격득실확인서)")
    issuer: str = Field(default="정부24", description="발급 기관 (정부24, 국민건강보험공단, 동주민센터 등)")
    can_online: bool = Field(default=True, description="온라인 즉시 발급 가능 여부")
    download_url: Optional[str] = Field(default=None, description="온라인 신청/발급 링크")


class TargetEligibility(BaseModel):
    min_age: int = Field(default=0, ge=0, le=120, description="최소 대상 연령 (만 나이)")
    max_age: int = Field(default=120, ge=0, le=120, description="최대 대상 연령 (만 나이)")
    income_limit_ratio: int = Field(default=999, ge=0, description="기준 중위소득 상한 비율 (%, 100=중위 100%, 999=소득무관)")
    required_tags: List[str] = Field(default_factory=list, description="필수 자격 태그 (infant, newlywed, multichild 등)")
    residence_condition: Optional[str] = Field(default=None, description="거주 요건 (예: 관악구 전입 1년 이내 무주택자)")
    housing_types: List[str] = Field(default_factory=list, description="주거 요건 (RENTAL_MONTHLY, JEONSE 등)")

    @model_validator(mode="after")
    def validate_age_boundaries(self):
        if self.min_age > self.max_age:
            raise ValueError(f"최소 연령({self.min_age})은 최대 연령({self.max_age})보다 클 수 없습니다.")
        return self


# ==============================================================================
# Canonical Standard Domain Model (UnifiedWelfarePolicy)
# ==============================================================================

class UnifiedWelfarePolicy(BaseModel):
    id: str = Field(..., description="정규화된 고유 정책 식별자 (예: pol_seoul_gwanak_cash_1730200000)")
    fingerprint: Optional[str] = Field(default=None, description="16자리 SHA-256 결정론적 중복 방지 지문 해시 (미지정 시 자동 생성)")
    source_id: Optional[str] = Field(default=None, description="원천 공공데이터 식별자 (Bojo24 SVC_ID 등)")
    source_type: str = Field(default="SYSTEM", description="출처 유형 (BOJO24, BOKJIRO, LOCAL_OFFICER, LOCAL_SCRAPER)")

    title: str = Field(..., min_length=2, max_length=150, description="정규화된 정책 공식 명칭")
    origin: PolicyOrigin = Field(..., description="중앙정부(CENTRAL) vs 지방정부(LOCAL)")
    region_code: str = Field(..., description="전국 공통(ALL) 또는 243개 지자체 행정코드 (예: seoul_gwanak)")
    region_name: str = Field(..., description="지역 표시 명칭 (예: 서울특별시 관악구, 대한민국 전국 공통)")
    managing_org: str = Field(..., description="소관 부처 또는 지자체 관할 부서 (예: 보건복지부, 관악구 청년정책과)")
    local_ordinance_basis: Optional[str] = Field(default=None, description="지자체 근거 조례 (지자체 특화사업 전용)")

    category: PolicyCategory = Field(..., description="표준 8대 복지 카테고리 코드")
    category_name: Optional[str] = Field(default=None, description="카테고리 한글 명칭")

    amount_value: int = Field(default=0, ge=0, description="연간 환산 최대 지원 금액 (KRW 단위, 일시금 포함)")
    amount_text: str = Field(..., description="사용자 친화적 금액 안내 문구 (예: 월 100만 원 (연 최대 1,200만 원))")

    target_eligibility: TargetEligibility = Field(default_factory=TargetEligibility)
    certainty_score: int = Field(default=90, ge=0, le=100, description="데이터 정합성 및 수혜 확실성 점수")

    application_period_type: ApplicationPeriodType = Field(
        default=ApplicationPeriodType.FIXED_PERIOD,
        description="접수 유형 (선착순/예산소진형, 고정기간형, 상시접수형)"
    )
    start_date: Optional[Union[str, date]] = Field(default=None, description="접수 시작일 (ISO 8601: YYYY-MM-DD 또는 date 객체)")
    end_date: Optional[Union[str, date]] = Field(default=None, description="접수 마감일 (ISO 8601: YYYY-MM-DD 또는 date 객체)")

    is_budget_limited: bool = Field(default=False, description="선착순/예산 소진형 사업 여부")
    budget_status: BudgetStatus = Field(default=BudgetStatus.OPEN, description="현재 예산/정원 소진 상태")
    slot_capacity: Optional[int] = Field(default=None, ge=1, description="선착순 총 모집 정원 (가구/인원)")
    current_applicant_count: Optional[int] = Field(default=None, ge=0, description="현재 누적 신청 인원")

    is_urgent: bool = Field(default=False, description="마감 임박 여부 (D-3 이내 또는 잔여 예산 20% 미만)")
    dday_text: Optional[str] = Field(default="상시 신청", description="D-Day 또는 마감 일정 표기 문구")

    summary_3lines: List[str] = Field(..., description="누가/얼마/어떻게 3줄 요약 문장 배열")
    required_documents: List[Union[RequiredDocument, Dict[str, Any], str]] = Field(default_factory=list)
    application_url: Optional[str] = Field(default="https://www.bokjiro.go.kr", description="온라인 신청 공식 링크")
    contact_phone: Optional[str] = Field(default="129", description="담당 부서 문의 전화번호")

    # 버전 관리 및 감사 메타데이터 (하위 호환 default_factory 제공)
    version: int = Field(default=1, ge=1, description="정책 개정 버전 번호 (최초 1)")
    created_at: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="최초 등록 일시 (ISO 8601 KST/UTC)"
    )
    updated_at: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="최근 변경 일시 (ISO 8601 KST/UTC)"
    )
    last_verified_at: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="파이프라인 최신 동기화 검증 일시 (ISO 8601 KST/UTC)"
    )

    @field_validator("summary_3lines")
    @classmethod
    def validate_summary_lines_count(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list) or len(v) != 3:
            raise ValueError(f"summary_3lines는 정확히 3개의 요약 문장으로 구성되어야 합니다 (현재: {len(v) if isinstance(v, list) else 'not a list'}개)")
        for idx, line in enumerate(v):
            if not isinstance(line, str) or len(line.strip()) < 2:
                raise ValueError(f"summary_3lines[{idx}] 요약 문장이 비어있거나 너무 짧습니다.")
        return [line.strip() for line in v]

    @field_validator("contact_phone")
    @classmethod
    def sanitize_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip()

    @field_validator("application_url")
    @classmethod
    def sanitize_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip()

    @field_validator("dday_text")
    @classmethod
    def sanitize_dday(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip()

    @model_validator(mode="after")
    def harmonize_dates_and_fingerprint(self):
        # 1. start_date / end_date가 date 객체일 경우 ISO 포맷 문자열로 상호 호환 정규화
        if isinstance(self.start_date, date):
            self.start_date = self.start_date.isoformat()
        if isinstance(self.end_date, date):
            self.end_date = self.end_date.isoformat()

        # 2. category_name 자동 보완
        if not self.category_name:
            self.category_name = CATEGORY_NAME_MAP.get(self.category, "복지혜택")

        # 3. fingerprint 누락 시 자동 생성
        if not self.fingerprint:
            min_a = self.target_eligibility.min_age if self.target_eligibility else 0
            max_a = self.target_eligibility.max_age if self.target_eligibility else 120
            cat_val = self.category.value if hasattr(self.category, "value") else str(self.category)
            from app.services.deduplication import generate_policy_fingerprint
            self.fingerprint = generate_policy_fingerprint(
                region_code=self.region_code,
                category=cat_val,
                title=self.title,
                managing_org=self.managing_org,
                min_age=min_a,
                max_age=max_a,
            )
        return self

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item)

    def keys(self):
        return self.model_dump().keys()

    def values(self):
        return self.model_dump().values()

    def items(self):
        return self.model_dump().items()


# ==============================================================================
# Local Government Admin API Schemas
# ==============================================================================

class LocalPolicyCreateSchema(BaseModel):
    title: str = Field(..., min_length=2, max_length=120, description="지자체 정책명")
    region_code: str = Field(..., description="지자체 행정구역 코드 (예: seoul_gwanak)")
    region_name: str = Field(..., description="지역 표시 명칭 (예: 서울특별시 관악구)")
    managing_org: str = Field(..., description="담당 부서 (예: 관악구 청년정책과)")
    local_ordinance_basis: Optional[str] = Field(default=None, description="근거 조례명")
    category: PolicyCategory = Field(default=PolicyCategory.CASH, description="복지 분야")
    amount_value: int = Field(default=0, ge=0, description="연간 환산 최대 지원 금액 (원)")
    amount_text: str = Field(..., description="지원 금액 노출 문구 (예: 최대 40만 원 실비 지원)")

    application_period_type: ApplicationPeriodType = Field(
        default=ApplicationPeriodType.FIRST_COME_FIRST_SERVED,
        description="접수 방식"
    )
    start_date: Optional[Union[str, date]] = None
    end_date: Optional[Union[str, date]] = None

    is_budget_limited: bool = Field(default=True, description="예산 소진형 여부")
    budget_status: BudgetStatus = Field(default=BudgetStatus.OPEN, description="초기 예산 상태")
    slot_capacity: Optional[int] = Field(default=None, ge=1, description="계획 정원")
    current_applicant_count: Optional[int] = Field(default=0, ge=0, description="초기 접수자 수")

    target_eligibility: TargetEligibility = Field(default_factory=TargetEligibility)
    summary_3lines: List[str] = Field(..., description="3줄 요약")
    required_documents: List[Union[RequiredDocument, Dict[str, Any], str]] = Field(default_factory=list)
    application_url: str = Field(..., description="온라인 신청 공식 링크")
    contact_phone: str = Field(..., description="문의 전화번호")

    @field_validator("summary_3lines")
    @classmethod
    def validate_summary_lines_count(cls, v: List[str]) -> List[str]:
        if not isinstance(v, list) or len(v) != 3:
            raise ValueError(f"summary_3lines는 정확히 3개의 요약 문장으로 구성되어야 합니다 (현재: {len(v) if isinstance(v, list) else 'not a list'}개)")
        for idx, line in enumerate(v):
            if not isinstance(line, str) or len(line.strip()) < 2:
                raise ValueError(f"summary_3lines[{idx}] 요약 문장이 비어있거나 너무 짧습니다.")
        return [line.strip() for line in v]

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        clean = v.strip()
        if not PHONE_PATTERN.match(clean):
            raise ValueError(f"유효하지 않은 대한민국 전화번호 형식입니다: '{clean}' (예: 02-879-5931, 129, 120, 1350, 070-1234-5678)")
        return clean

    @model_validator(mode="after")
    def validate_dates_and_capacity(self):
        if self.start_date and self.end_date:
            sd = self.start_date if isinstance(self.start_date, str) else self.start_date.isoformat()
            ed = self.end_date if isinstance(self.end_date, str) else self.end_date.isoformat()
            if ed < sd:
                raise ValueError(f"마감일({ed})은 시작일({sd})보다 이전일 수 없습니다.")
        if self.slot_capacity and self.current_applicant_count:
            if self.current_applicant_count > self.slot_capacity * 1.5:
                raise ValueError("현재 접수 인원이 계획 정원의 150%를 초과할 수 없습니다.")
        return self


class LocalPolicyStatusPatchSchema(BaseModel):
    """3초 원클릭 상태 변경 전용 경량 스키마"""
    budget_status: Optional[BudgetStatus] = Field(default=None, description="변경할 예산 상태 (OPEN, PLENTY, HALF_CONSUMED, NEAR_EXHAUSTION, EXHAUSTED)")
    current_applicant_count: Optional[int] = Field(default=None, ge=0, description="현재 접수 인원 수")
    dday_text: Optional[str] = Field(default=None, description="사용자 표시용 긴급 마감 문구 (미입력 시 시스템 자동 생성)")
    is_urgent: Optional[bool] = Field(default=None, description="마감 임박 긴급 배지 강제 지정 여부")
    closure_reason: Optional[str] = Field(default=None, description="조기 마감 또는 중단 사유")
    status: Optional[str] = Field(default=None, description="레거시 상태 호환 필드 (CLOSING_SOON, EXHAUSTED 등)")

    @model_validator(mode="before")
    @classmethod
    def harmonize_status_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            bs = data.get("budget_status")
            st = data.get("status")
            if not bs and st:
                if st in BudgetStatus.__members__:
                    data["budget_status"] = st
                elif st == "CLOSING_SOON":
                    data["budget_status"] = "NEAR_EXHAUSTION"
                else:
                    data["budget_status"] = st
            elif bs and not st:
                data["status"] = bs.value if hasattr(bs, "value") else str(bs)
        return data

    @model_validator(mode="after")
    def ensure_status_present(self):
        if self.budget_status is None and self.status is None:
            raise ValueError("budget_status 또는 status 중 하나는 반드시 지정되어야 합니다.")
        if self.budget_status is None and self.status:
            try:
                self.budget_status = BudgetStatus(self.status)
            except ValueError:
                self.budget_status = BudgetStatus.NEAR_EXHAUSTION
        return self

