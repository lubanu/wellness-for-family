"""
backend/tests/test_public_page.py
================================================================================
Guards for the public site. Unfinished or invented content must not ship,
and the required notices must stay on the page.
"""

from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
PAGE = (REPO_DIR / "prototype" / "index.html").read_text(encoding="utf-8")
WORKFLOWS_DIR = REPO_DIR / ".github" / "workflows"


@pytest.mark.parametrize("text", [
    "localhost",        # calls a server that public users don't have
    "쿠팡", "ca-pub", "애드센스", "제휴",  # ads and affiliate links stay hidden until real
    "Care+", "VIP",     # paid features are not built
    "5,400,000", "8,920,000", "1,800,000",  # fixed totals that were never calculated
    "환불 보장", "보장제", "실시간", "243개", "AI 매칭",  # claims the service can't back up
    "김민준", "홍길동",  # made-up people
    "02-879-5931",      # one office's phone number, shown for every policy
])
def test_public_page_has_no_unfinished_content(text):
    assert text not in PAGE


@pytest.mark.parametrize("text", [
    "공식 결정이 아니며",
    "정부나 지방자치단체가 운영하는 서비스가 아닙니다",
    "데이터 출처",
    "https://www.bokjiro.go.kr",
    "https://www.gov.kr",
    "확인 필요",
])
def test_public_page_keeps_required_notices(text):
    assert text in PAGE


@pytest.mark.parametrize("name", ["admin.html", "widget.html", "blog_posts"])
def test_deploy_leaves_out_unfinished_pages(name):
    assert name not in (WORKFLOWS_DIR / "deploy_pages.yml").read_text(encoding="utf-8")


@pytest.mark.parametrize("workflow", ["deploy_pages.yml", "welfare_sync.yml"])
def test_workflows_only_run_by_hand_for_now(workflow):
    text = (WORKFLOWS_DIR / workflow).read_text(encoding="utf-8")
    triggers = text.split("\non:\n")[1].split("\n\n")[0]
    assert triggers.strip() == "workflow_dispatch:"
