"""
backend/tests/test_public_page.py
================================================================================
Guards for the public site. Unfinished or invented content must not ship,
required notices must stay, and the page must follow its design system rules.
"""

from pathlib import Path
import re

import pytest

REPO_DIR = Path(__file__).resolve().parents[2]
PROTOTYPE_DIR = REPO_DIR / "prototype"
HTML = (PROTOTYPE_DIR / "index.html").read_text(encoding="utf-8")
SCRIPT = (PROTOTYPE_DIR / "app.js").read_text(encoding="utf-8")
STYLES = (PROTOTYPE_DIR / "styles.css").read_text(encoding="utf-8")
PAGE = "\n".join([HTML, SCRIPT, STYLES])
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
    assert text in HTML


@pytest.mark.parametrize("name", ["admin.html", "widget.html", "blog_posts"])
def test_deploy_leaves_out_unfinished_pages(name):
    assert name not in (WORKFLOWS_DIR / "deploy_pages.yml").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["index.html", "styles.css", "app.js"])
def test_deploy_ships_the_page_files(name):
    assert name in (WORKFLOWS_DIR / "deploy_pages.yml").read_text(encoding="utf-8")


@pytest.mark.parametrize("workflow", ["deploy_pages.yml", "welfare_sync.yml"])
def test_workflows_only_run_by_hand_for_now(workflow):
    text = (WORKFLOWS_DIR / workflow).read_text(encoding="utf-8")
    triggers = text.split("\non:\n")[1].split("\n\n")[0]
    assert triggers.strip() == "workflow_dispatch:"


def test_page_loads_nothing_from_other_sites():
    tags = re.findall(r"<(?:script|link)\b[^>]*>", HTML)
    assert tags, "expected script and link tags"
    assert [tag for tag in tags if re.search(r'(?:src|href)="https?:', tag)] == []


def test_page_has_a_strict_content_security_policy():
    assert "Content-Security-Policy" in HTML
    assert "default-src 'none'" in HTML
    assert "unsafe-inline" not in HTML


def test_catalog_text_cannot_inject_markup():
    assert "innerHTML" not in SCRIPT
    assert "insertAdjacentHTML" not in SCRIPT


def test_page_has_no_inline_handlers_or_styles():
    assert re.findall(r"\son(?:click|change|input)=", HTML) == []
    assert re.findall(r'\sstyle="', HTML) == []


def test_styles_use_tokens_instead_of_raw_colors():
    components = STYLES.split("/* Big-text mode")[1]
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b", components.replace("%23115e59", "")) == []


def test_no_text_is_smaller_than_the_minimum_size():
    sizes = re.findall(r"--text-[a-z0-9]+:\s*([0-9.]+)rem", STYLES)
    assert sizes and min(float(size) for size in sizes) >= 0.875
    assert re.findall(r"font-size:\s*[0-9.]+(?:px|rem|em)", STYLES.split("/* Big-text mode")[1]) == []


def test_touch_targets_are_at_least_44_pixels():
    assert "--control-height: 2.75rem" in STYLES
