"""
backend/tests/test_probe_apis.py
================================================================================
Tests for the P0 API probe. Every response is faked, so no key or network is needed.
The main promise under test: the key never reaches a saved file.
"""

import json
from pathlib import Path
import urllib.parse

import pytest

from scripts import probe_apis
from scripts.probe_apis import (
    condition_values,
    encode_key,
    fill_rates,
    filter_works,
    main,
    parse_xml,
    redact,
    run,
    xml_records,
)

KEY = "abc+def/ghi=="
WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "api_probe.yml"

SERVICES = [
    {"서비스ID": "S1", "서비스명": "부모급여", "소관기관유형": "중앙행정기관", "소관기관코드": "1352000",
     "소관기관명": "보건복지부", "부서명": "인구아동정책과", "선정기준": "만 0세", "조회수": 10},
    {"서비스ID": "S2", "서비스명": "이사비 지원", "소관기관유형": "지방자치단체", "소관기관코드": "3200000",
     "소관기관명": "서울특별시 관악구", "부서명": "청년정책과", "선정기준": "", "조회수": 7},
]
CONDITIONS = [{"서비스ID": "S1", "서비스명": "부모급여", "JA0101": "Y", "JA0102": None, "JA0110": 0, "JA0111": 1}]
LIST_XML = ("<wantedList><totalCount>2</totalCount><resultCode>0</resultCode>"
            "<servList><servId>WLF1</servId><servNm>첫째</servNm><ctpvNm>서울특별시</ctpvNm></servList>"
            "<servList><servId>WLF2</servId><servNm>둘째</servNm><ctpvNm></ctpvNm></servList></wantedList>")
DETAIL_XML = "<wantedDtl><detail><servId>WLF1</servId><servNm>첫째</servNm></detail></wantedDtl>"


def gov24_page(url):
    """Fakes the portal: page size capped at 1000, cond ignored on serviceList."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    per_page = min(int(query["perPage"][0]), 1000)
    wanted = query.get("cond[서비스ID::EQ]", [None])[0]
    if "supportConditions" in url:
        rows = CONDITIONS
    elif "serviceDetail" in url:
        rows = [row for row in SERVICES if row["서비스ID"] == wanted]
    else:
        rows = (SERVICES * 600)[:per_page]
    return json.dumps({"data": rows, "totalCount": 1200, "currentCount": len(rows)}, ensure_ascii=False)


def fake_fetch(url):
    if "api.odcloud.kr" in url:
        return 200, gov24_page(url), 0.1
    if "NationalWelfarelistV001" in url or "LcgvWelfarelist?" in url:
        return 200, LIST_XML, 0.2
    if "NationalWelfaredetailedV001" in url or "LcgvWelfaredetailed?" in url:
        return 200, DETAIL_XML, 0.2
    return 404, "<html>not found</html>", 0.1


def read_all(folder):
    return "\n".join(path.read_text(encoding="utf-8") for path in folder.iterdir())


@pytest.fixture
def out(tmp_path):
    """A clean folder. tmp_path itself also holds the shared sandbox's data/ folder."""
    return tmp_path / "probe"


def test_encode_key_quotes_a_decoded_key_once():
    assert encode_key("a+b/c==") == "a%2Bb%2Fc%3D%3D"
    assert encode_key("a%2Bb%2Fc%3D%3D") == "a%2Bb%2Fc%3D%3D"


@pytest.mark.parametrize("form", [KEY, urllib.parse.quote(KEY, safe="")])
def test_redact_removes_both_forms_of_the_key(form):
    assert form not in redact(f"error for serviceKey={form} here", KEY)
    assert "[REDACTED]" in redact(f"error for serviceKey={form} here", KEY)


def test_no_key_means_no_calls_and_no_files(out, monkeypatch):
    monkeypatch.delenv("DATA_GO_KR_API_KEY", raising=False)

    def must_not_call(url):
        raise AssertionError("no call may happen without a key")

    assert main(["--out", str(out)], fetch=must_not_call) == 2
    assert not out.exists()


def test_key_comes_from_the_environment(out, monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_API_KEY", KEY)
    assert main(["--out", str(out)], fetch=fake_fetch) == 0


def test_full_run_saves_samples_and_findings(out):
    assert run(KEY, out, fake_fetch) == 0
    names = {path.name for path in out.iterdir()}
    assert names == {
        "FINDINGS.md", "gov24_service_list.json", "gov24_service_detail.json", "gov24_support_conditions.json",
        "bokjiro_central_list.xml", "bokjiro_central_detail.xml", "bokjiro_local_list.xml", "bokjiro_local_detail.xml",
    }


def test_samples_stay_small(out):
    run(KEY, out, fake_fetch)
    rows = json.loads((out / "gov24_service_list.json").read_text(encoding="utf-8"))["data"]
    assert len(rows) == probe_apis.SAMPLE_ROWS


def test_findings_answer_the_p0_questions(out):
    run(KEY, out, fake_fetch)
    findings = (out / "FINDINGS.md").read_text(encoding="utf-8")
    assert "Total records: 1200" in findings
    assert "{100: 100, 1000: 1000, 5000: 1000}" in findings  # the page size cap
    assert "`cond[서비스ID::EQ]` on serviceList: ignored or failed" in findings
    assert "`cond[서비스ID::EQ]` on serviceDetail: works" in findings
    assert "Eligibility flag values, sampled: {'Y': 1}" in findings
    assert "JA0110 sample values: ['0']" in findings
    assert "`지방자치단체`: 500 of 500 blank" in findings  # 선정기준 is blank on local records
    assert "`3200000` 서울특별시 관악구 / 청년정책과" in findings  # region mapping examples
    assert "`ctpvNm`: 50%" in findings  # field names and fill rates for Bokjiro


def test_key_never_reaches_a_file_even_if_a_server_echoes_it(out):
    def leaky_fetch(url):
        status, body, seconds = fake_fetch(url)
        echo = f"<!-- {url} -->" if body.startswith("<") else None
        if echo:
            body = body.replace("<totalCount>", f"<note>{KEY}</note><totalCount>")
            return status, body + echo, seconds
        payload = json.loads(body)
        payload["requested"] = url
        return status, json.dumps(payload, ensure_ascii=False), seconds

    run(KEY, out, leaky_fetch)
    saved = read_all(out)
    assert KEY not in saved
    assert encode_key(KEY) not in saved


def test_failure_message_cannot_leak_the_key(out):
    def rejected(url):
        return 401, f"bad key {url}", 0.1

    assert run(KEY, out, rejected) == 1
    saved = read_all(out)
    assert encode_key(KEY) not in saved
    assert "HTTP 401" in saved


def test_one_failed_api_does_not_lose_the_others(out):
    def central_down(url):
        if "NationalWelfare" in url:
            return 0, "connection timed out", 30.0
        return fake_fetch(url)

    assert run(KEY, out, central_down) == 1
    assert (out / "gov24_service_list.json").exists()
    assert (out / "bokjiro_local_list.xml").exists()
    assert not (out / "bokjiro_central_list.xml").exists()
    assert "Status: FAILED" in (out / "FINDINGS.md").read_text(encoding="utf-8")


def test_key_errors_are_reported_in_plain_words(out):
    gateway_error = (
        "<OpenAPI_ServiceResponse><cmmMsgHeader><errMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</errMsg>"
        "<returnAuthMsg>등록되지 않은 서비스키</returnAuthMsg></cmmMsgHeader></OpenAPI_ServiceResponse>"
    )

    def not_approved(url):
        if "apis.data.go.kr" in url:
            return 403, gateway_error, 0.1
        return fake_fetch(url)

    assert run(KEY, out, not_approved) == 1
    findings = (out / "FINDINGS.md").read_text(encoding="utf-8")
    assert "HTTP 403: SERVICE_KEY_IS_NOT_REGISTERED_ERROR / 등록되지 않은 서비스키" in findings


def test_html_error_page_is_a_failure_not_a_crash(out):
    def html_only(url):
        return 200, "<html><body><p>점검 중</p></body>", 0.1

    assert run(KEY, out, html_only) == 1


def test_fill_rates_count_blank_values():
    assert fill_rates([{"a": "x", "b": ""}, {"a": None, "b": " "}]) == {"a": 50, "b": 0}


def test_condition_values_read_only_ja_codes():
    values = condition_values([{"서비스ID": "S1", "JA0101": "Y", "JA0102": None}])
    assert list(values) == ["JA0101"]


def test_filter_needs_rows_that_all_match():
    assert filter_works([{"서비스ID": "S1"}], "S1")
    assert not filter_works([{"서비스ID": "S1"}, {"서비스ID": "S2"}], "S1")
    assert not filter_works([], "S1")


def test_xml_records_finds_the_repeated_element_by_shape():
    nested = "<response><header><code>0</code></header><body><items><item><a>1</a></item><item><a>2</a></item></items></body></response>"
    assert xml_records(parse_xml(nested)) == [{"a": "1"}, {"a": "2"}]


def test_probe_workflow_only_runs_by_hand_and_reads_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    triggers = text.split("\non:\n")[1].split("\n\n")[0]
    assert triggers.strip() == "workflow_dispatch:"
    assert "contents: read" in text
    assert "git push" not in text
