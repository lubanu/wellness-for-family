#!/usr/bin/env python3
"""
scripts/blog_generator.py
WelFamily Automated SEO Blog Post & Affiliate Content Generator.
Generates high-converting, SEO-optimized blog articles for Tistory, Naver Blog, and WordPress.
Includes AdSense ad unit markers, Coupang Partners / affiliate disclosures, and WelFamily widget CTAs.
Runs with zero external dependencies (Python standard library only).
"""

import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_PATH = os.path.join(ROOT_DIR, "data", "welfare_catalog.json")
BLOG_DIR = os.path.join(ROOT_DIR, "blog_posts")


def log(msg: str):
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    print(f"[{now_str}] {msg}", flush=True)


def get_affiliate_callout(category: str) -> dict:
    """Returns contextual affiliate recommendation based on policy category."""
    if category == "HOUSING":
        return {
            "title": "📦 [이사/입주 필수 제휴] 무료 포장이사 & 인터넷 현금지원 비교",
            "desc": "이사비 지원금 신청 전, 관내 검증된 이사업체 무료 방문 견적과 인터넷 이전/신규 가입 최대 사은품 혜택을 먼저 확인해보세요.",
            "link_text": "포장이사 실시간 무료 비교견적 받기",
            "link_url": "https://example.com/affiliate/moving",
            "disclosure": "※ 이 영역은 제휴마케팅 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다."
        }
    elif category == "CARE" or category == "VOUCHER":
        return {
            "title": "👶 [육아용품 특가 제휴] 국민행복카드 바우처 전액 사용 가능처",
            "desc": "바우처 지급 즉시 사용 가능한 기저귀, 친환경 분유, 필수 신생아 용품 로켓배송 최저가 기획전을 확인해보세요.",
            "link_text": "로켓배송 영유아 인기 필수템 모아보기",
            "link_url": "https://link.coupang.com/example_affiliate",
            "disclosure": "※ 이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
        }
    else:
        return {
            "title": "💰 [스마트 금융 꿀팁] 2026 청년·가족 우대 고금리 파킹통장",
            "desc": "지원금 입금 통장으로 연 최대 3.5%~4.0% 금리를 제공하는 무서류 비대면 파킹통장 개설 혜택을 확인해보세요.",
            "link_text": "1금융권 고금리 수시입출금 통장 비교하기",
            "link_url": "https://example.com/affiliate/finance",
            "disclosure": "※ 이 영역은 제휴마케팅 활동의 일환으로 일정액의 수수료를 제공받을 수 있습니다."
        }


def generate_markdown_post(policy: dict) -> str:
    title = policy.get("title", "")
    managing_org = policy.get("managing_org", "정부·지자체")
    region_name = policy.get("region_name", "전국")
    amount_text = policy.get("amount_text", "")
    summary = policy.get("summary_3lines", ["", "", ""])
    docs = policy.get("required_documents", [])
    app_url = policy.get("application_url", "https://www.gov.kr")
    phone = policy.get("contact_phone", "129")
    affiliate = get_affiliate_callout(policy.get("category", "CASH"))

    doc_list_str = "\n".join([f"- [ ] **{d.get('name')}** ({d.get('issuer')}) {'- *온라인 즉시발급*' if d.get('can_online') else ''}" for d in docs])

    md = f"""---
title: "[2026 최신] {region_name} {title} 신청 자격 및 필수 서류 총정리"
date: "{datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}"
categories: ["정부지원금", "복지정책", "{region_name}"]
tags: ["{title}", "복지혜택", "정부지원금", "{region_name}", "신청방법"]
---

# [2026 최신] {region_name} {title} 신청 자격 및 필수 서류 총정리

안녕하세요! 2026년 최신 정부·지자체 복지 정책 정보를 빠르고 정확하게 전달해 드립니다.

오늘 소개해 드릴 지원 제도는 **{managing_org}**에서 시행하는 **「{title}」**입니다. 지원 금액이 무려 **{amount_text}**에 달해 대상자에 해당하신다면 절대 놓치지 마시고 신청하셔야 합니다!

---

## 📌 1. 바쁜 분들을 위한 3줄 핵심 요약

> 💡 **{title} 요약**
> - **누가 받나요:** {summary[0]}
> - **얼마를 받나요:** {summary[1]}
> - **어떻게 받나요:** {summary[2]}

---

<!-- ============================================== -->
<!-- 애드센스 인아티클 상단 반응형 광고 슬롯 -->
<!-- ============================================== -->
<div align="center" style="margin: 25px 0;">
  <!-- 구글 애드센스 코드 (In-Article Responsive) -->
  <ins class="adsbygoogle"
       style="display:block; text-align:center;"
       data-ad-layout="in-article"
       data-ad-format="fluid"
       data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
       data-ad-slot="YYYYYYYYYY"></ins>
  <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>

---

## 📋 2. 상세 지원 자격 및 대상자 조건

이 제도는 **{region_name}** 거주자 또는 특정 조건을 충족하는 가구를 대상으로 합니다.

- **관할 부서:** {managing_org}
- **지원 규모:** **{amount_text}**
- **대상 요건:** {summary[0]}

> ⚠️ **주의사항:** 선착순 예산 소진형 공고이거나 마감 기한이 정해진 사업의 경우, 예산이 조기 소진되면 접수가 마감될 수 있으니 공고 확인 즉시 신청을 권장합니다.

---

## 📝 3. 신청 전 필수 구비서류 체크리스트

주민센터나 온라인 접수 시 서류가 미비하면 반려되어 소중한 시간을 낭비할 수 있습니다. 아래 서류 목록을 미리 체크해보세요:

{doc_list_str}

*※ 정부24 무료 발급 표시가 있는 서류는 공인인증서/간편인증 로그인 후 PDF로 즉시 무료 발급이 가능합니다.*

---

## 🚀 4. 온라인 및 방문 신청 방법

- **온라인 신청:** [공식 신청 페이지 바로가기]({app_url})
- **문의 전화:** ☎️ {phone} (담당 부서 직통)

---

<!-- ============================================== -->
<!-- 맥락 맞춤형 제휴 추천 박스 (Coupang / Moving / Finance) -->
<!-- ============================================== -->
<div style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 12px; padding: 18px; margin: 30px 0;">
  <h3 style="margin-top: 0; color: #1e3a8a; font-size: 16px;">{affiliate['title']}</h3>
  <p style="font-size: 13px; color: #475569; line-height: 1.6;">{affiliate['desc']}</p>
  <div style="margin-top: 12px;">
    <a href="{affiliate['link_url']}" target="_blank" rel="noopener noreferrer" 
       style="display: inline-block; background-color: #2563eb; color: #ffffff; padding: 8px 16px; border-radius: 8px; font-weight: bold; text-decoration: none; font-size: 13px;">
      👉 {affiliate['link_text']}
    </a>
  </div>
  <p style="font-size: 11px; color: #94a3b8; margin-top: 8px; margin-bottom: 0;">{affiliate['disclosure']}</p>
</div>

---

<!-- ============================================== -->
<!-- WelFamily 맞춤 복지 계산기 위젯 CTA 배너 -->
<!-- ============================================== -->
<div style="background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; border-radius: 14px; padding: 22px; text-align: center; margin: 35px 0;">
  <h3 style="color: white; margin-top: 0; font-size: 18px;">🏠 우리 가족이 받을 수 있는 다른 혜택은 얼마일까요?</h3>
  <p style="font-size: 13px; color: #e0e7ff; margin-bottom: 16px;">
    나, 배우자, 아이, 부모님 조건까지 결합하여 1분 만에 숨은 지원금을 계산하고 실시간 알림을 받아보세요.
  </p>
  <a href="https://welfamily.github.io" target="_blank"
     style="display: inline-block; background-color: #ffffff; color: #1e40af; font-weight: 800; padding: 10px 22px; border-radius: 10px; text-decoration: none; font-size: 14px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
    우리 가족 복지 1분 만에 계산하기 →
  </a>
</div>

---

<!-- ============================================== -->
<!-- 하단 애드센스 디스플레이 광고 슬롯 -->
<!-- ============================================== -->
<div align="center" style="margin: 25px 0;">
  <ins class="adsbygoogle"
       style="display:block"
       data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
       data-ad-slot="ZZZZZZZZZZ"
       data-ad-format="auto"
       data-full-width-responsive="true"></ins>
  <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>
"""
    return md


def main():
    log("=== Starting WelFamily Automated SEO Blog Post Generator ===")
    if not os.path.exists(CATALOG_PATH):
        log(f"Catalog file not found at {CATALOG_PATH}")
        return

    os.makedirs(BLOG_DIR, exist_ok=True)

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    policies = catalog.get("policies", [])
    log(f"Generating SEO blog posts for {len(policies)} policies...")

    generated_count = 0
    for p in policies:
        pid = p.get("id")
        md_content = generate_markdown_post(p)
        file_path = os.path.join(BLOG_DIR, f"{pid}.md")

        with open(file_path, "w", encoding="utf-8") as out:
            out.write(md_content)
        generated_count += 1

    log(f"Successfully generated {generated_count} SEO blog articles in '{BLOG_DIR}'!")
    log("=== Blog Generation Complete (AdSense, Coupang, and WelFamily CTA Embedded) ===")


if __name__ == "__main__":
    main()
