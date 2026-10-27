# 🏠 웰패밀리 (WelFamily) - 우리 가족 맞춤형 복지비서

> **"몰라서 놓치는 정부·지자체 혜택 제로(Zero)! 내가 설정한 맞춤형 조건에 따라 실시간으로 알려주는 가족 복지 레이더"**

대한민국 243개 지방자치단체와 중앙정부의 1만여 개 복지·지원금 정보를 가족 단위로 통합 분석하고, 자격 조건에 부합하는 정책을 능동적으로 찾아 알려주는 **AI 기반 거브테크(GovTech) 맞춤형 복지 큐레이션 서비스** 기획 및 프로토타입 프로젝트입니다.

---

## 📌 목차 (Table of Contents)

1. [기획 문서 일람 (Documentation Index)](#1-기획-문서-일람-documentation-index)
2. [핵심 차별화 및 경쟁력 (Key Differentiators)](#2-핵심-차별화-및-경쟁력-key-differentiators)
3. [주요 서비스 기능 (Core Features)](#3-주요-서비스-기능-core-features)
4. [시스템 아키텍처 및 파이프라인 (Architecture & Data Pipeline)](#4-시스템-아키텍처-및-파이프라인-architecture--data-pipeline)
5. [인터랙티브 프로토타입 체험 (Interactive Prototype)](#5-인터랙티브-프로토타입-체험-interactive-prototype)
6. [비즈니스 모델 및 로드맵 (BM & Roadmap)](#6-비즈니스-모델-및-로드맵-bm--roadmap)

---

## 1. 기획 문서 일람 (Documentation Index)

프로젝트 루트의 `docs/` 디렉토리에 상세 기획서가 체계적으로 작성되어 있습니다.

| 번호 | 문서명 | 주요 내용 |
| :--- | :--- | :--- |
| **01** | [시장 분석 및 벤치마킹 보고서](docs/01_market_and_competitor_analysis.md) | 복지로(복지멤버십), 보조금24, 웰로(Wello), 토스 심층 비교 및 사각지대 분석 |
| **02** | [서비스 기획서 및 기능 정의서](docs/02_service_planning_and_features.md) | 타깃 페르소나, 초개인화 가구 프로필 엔진, 3단계 매칭 등급 및 알림 명세 |
| **03** | [시스템 아키텍처 및 데이터 파이프라인](docs/03_system_architecture_and_data_pipeline.md) | 243개 지자체 고시공고 HWP/PDF LLM 파싱, PostgreSQL ERD, 매칭 알고리즘 |
| **04** | [UI/UX 화면 설계서 및 사용자 플로우](docs/04_ui_ux_wireframes_and_user_flows.md) | 모바일 퍼스트 와이어프레임, 정보 구조도(IA), 1분 온보딩 및 서류 체크리스트 |
| **05** | [사업화 전략 및 MVP 로드맵](docs/05_mvp_roadmap_and_business_model.md) | B2C Care+ 구독, B2B 임직원 복지 SaaS, 3단계 개발 로드맵 및 핵심 KPI |
| **06** | [100% 무료 인프라 자동 최신화 가이드](docs/06_free_tier_infrastructure_and_automation.md) | GitHub Actions + GitOps DB + Gemini Flash + 텔레그램 무료 알림 파이프라인 |
| **07** | [광고 및 블로그 제휴 마케팅 연계 전략](docs/07_advertising_and_blog_affiliate_strategy.md) | SEO 복지 블로그 자동 발행, 애드센스 슬롯, 쿠팡 파트너스, 블로그 임베드 위젯 |
| **08** | [백엔드 시스템 아키텍처 및 구현 명세서](docs/08_backend_implementation_architecture_and_plan.md) | FastAPI 비동기 서버, PostgreSQL ERD, 3단계 스마트 매칭 알고리즘, REST API |
| **09** | [배리어프리 포용적 웹 표준 디자인 명세서](docs/09_inclusive_frontend_design_and_web_standards.md) | KWCAG 2.2 / WCAG 2.2 AAA, 큰글씨/간편 모드, 네이티브 dialog, ARIA Live |
| **10** | [웰패밀리 종합 서비스 구현 계획서](docs/10_master_service_implementation_plan.md) | 5대 구현 축 통합, 4단계 스프린트 WBS, 100% 무료 인프라 엔드투엔드 구축 |

---

## 2. 핵심 차별화 및 경쟁력 (Key Differentiators)

기존 복지로, 보조금24, 토스, 웰로 등과의 4대 차별화 공식:

1. **가구(Household) 중심 복합 시너지 매칭**:
   - 개인 1인의 조회가 아닌, 배우자·자녀·노부모를 결합한 **'우리 집 전체 수혜액(연간 최대 수백만 원)'**을 한눈에 산출.
2. **지자체 특화 조례 공고 실시간 AI Ingestion**:
   - 중앙부처 공통 혜택뿐 아니라 전국 243개 시·군·구청에 HWP/PDF 형태로 흩어져 있는 **'지역 전용 지원금(이사비, 출산지원금, 청년수당 등)'**을 LLM이 실시간 수집·정제.
3. **생애주기 & 마감 D-Day 트리거 알림**:
   - "신청하라고 해서 들어갔더니 이미 마감"되는 사태를 방지하는 실시간 D-Day 푸시 및 아이 나이 변화(만 1세, 만 8세 등)에 따른 선제적 알림.
4. **구비서류 체크리스트 & 원스톱 딥링크**:
   - 어려운 행정 용어를 '3줄 요약'하고, 주민센터 방문 전 챙겨야 할 서류를 스마트폰 체크리스트로 제공.

---

## 3. 주요 서비스 기능 (Core Features)

```
┌─────────────────────────────────────────────────────────────┐
│                       WelFamily 핵심 기능                    │
├─────────────────────────────────────────────────────────────┤
│ 1. [가구 프로필] 거주지(시군구) + 가구원 + 간이소득 1분 설정 │
│ 2. [복지 대시보드] 연간 예상 수혜액 및 미신청 혜택 발굴      │
│ 3. [지자체 특화 배지] 내 동네만의 전용 혜택 실시간 필터링   │
│ 4. [복지 캘린더] 매월 25일 정기 입금일 & 신청 마감 D-Day     │
│ 5. [알림톡 시뮬레이션] 내 조건에 딱 맞는 신규 공고 즉시 전송 │
│ 6. [서류 체크리스트] 정부24 온라인 발급 링크 & 주민센터 안내 │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 100% 무료 인프라 기반 자동 최신화 파이프라인 (Zero-Cost Online Infrastructure)

본 서비스는 서버 호스팅 비용과 DB 유지비가 **영구히 0원($0/월)**인 100% 무료 온라인 인프라에서 구동되도록 완전히 구현되었습니다.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                 WelFamily 100% 무료 온라인 인프라 스택 ($0/월)               │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. [스케줄링 & 연산] GitHub Actions : 매일 새벽 04:00 KST 자동 실행 (무료)   │
│ 2. [데이터 수집 & AI] 공공데이터포털 API + Google Gemini Flash 무료 티어    │
│ 3. [영구 DB & 스토리지] GitOps Flat JSON DB (data/welfare_catalog.json)      │
│ 4. [선택 클라우드 DB] Supabase Free Tier (500MB PostgreSQL 지원)             │
│ 5. [글로벌 웹 호스팅] GitHub Pages / Cloudflare Pages (무료 SSL 및 CDN)      │
│ 6. [무제한 모바일 알림] Telegram Bot API + Discord Webhook (100% 무료 푸시) │
│ 7. [클라이언트 프라이버시] Browser LocalStorage (서버 DB $0 & 개인정보 완벽 보호)│
└─────────────────────────────────────────────────────────────────────────────┘
```

### 🚀 일일 자동 최신화 동작 방식
1. **GitHub Actions 스케줄러 (`.github/workflows/welfare_sync.yml`)**:
   - 매일 새벽 04:00 KST (또는 수동 실행)에 가상 컨테이너 실행.
2. **수집 및 정규화 (`scripts/collector.py`)**:
   - 보조금24 API 및 지자체 공고를 수집하고, 비정형 텍스트는 Gemini Flash가 3줄 요약/구비서류 JSON으로 정제.
   - `data/welfare_catalog.json` 및 `data/latest_sync.json`에 저장 후 GitHub에 자동 커밋.
3. **SEO 블로그 글 자동 생성 (`scripts/blog_generator.py`)**:
   - 최신 정책 데이터를 바탕으로 애드센스 인아티클 광고 코드와 쿠팡 파트너스/이사 제휴 박스가 포함된 Markdown 블로그 포스팅(`blog_posts/`) 자동 생성.
4. **무료 푸시 알림 디스패치 (`scripts/notifier.py`)**:
   - D-3 마감 임박 정책 및 신규 조례 발생 시 텔레그램/디스코드로 즉시 모바일 푸시 발송.
5. **웹 자동 배포 (`.github/workflows/deploy_pages.yml`)**:
   - 변경된 데이터, 블로그 포스팅, 그리고 블로거용 위젯(`widget.html`)이 GitHub Pages로 자동 배포되어 전 세계 사용자가 실시간 최신 정보 확인.

---

## 5. 광고 및 광고 블로그 연계 모델 (Advertising & Affiliate Strategy)

1. **SEO 블로그 자동 생성 엔진 (`scripts/blog_generator.py`)**:
   - 네이버 블로그, 티스토리, 워드프레스용 최적화 포스팅 자동 생성.
   - 고단가 키워드(부모급여, 청년월세, 이사비 등) 공략으로 구글 애드센스 및 카카오 애드핏 광고 수익 극대화.
2. **카테고리별 맥락 맞춤형 제휴 커머스**:
   - 주거/이사 지원금 ➔ 포장이사 무료 견적 비교(CPA ₩15,000~₩30,000) 및 인터넷 신규 가입 제휴(₩40,000~₩70,000).
   - 출산/영유아 지원금 ➔ 쿠팡 파트너스 기저귀·분유 로켓배송 특가 및 국민행복카드 신규 발급 캐시백.
   - 청년 금융 지원 ➔ 1금융권 고금리 파킹통장/CMA 계좌 개설 제휴.
3. **외부 블로거용 무료 복지 계산기 위젯 (`prototype/widget.html`)**:
   - 블로거가 포스팅에 1줄 아이프레임(`<iframe>`)으로 삽입하여 독자 체류 시간을 높이고, WelFamily로 무료 바이럴 백링크 유입 유도.

---

## 6. 인터랙티브 프로토타입 체험 (Interactive Prototype)

본 저장소의 `prototype/index.html` 파일을 브라우저로 열면 다음 기능을 직접 체험해 볼 수 있습니다:
- **프로필 동적 변경**: 거주지(서울 관악구, 경기 성남시, 부산 해운대구 등) 및 가구 구성(신혼부부, 영유아, 청년 1인가구) 변경에 따른 실시간 복지 목록 재계산.
- **예상 수혜액 계산기**: 가구 조건에 따른 연간 지원금 총액 시뮬레이션.
- **복지 캘린더 타임라인**: 월별 입금일 및 신청 마감 D-Day 인터랙션.
- **카카오 알림톡 프리뷰**: 실제 사용자에게 전송될 맞춤형 알림톡 메시지 렌더링.

```bash
# 로컬에서 프로토타입 확인 (간이 웹서버 구동 예시)
cd prototype
python3 -m http.server 8080
# 브라우저에서 http://localhost:8080 접속
```

---

## 6. 라이선스 및 문의 (License & Contact)

- **프로젝트**: 웰패밀리 (WelFamily)
- **버전**: v1.0.0 (기획 & 프로토타입 릴리즈)
- **라이선스**: MIT License
