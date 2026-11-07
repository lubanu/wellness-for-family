#!/usr/bin/env python3
"""
scripts/probe_apis.py
================================================================================
P0 probe. Calls each public welfare API a few times, saves small real samples,
and writes FINDINGS.md with the facts the importer (P3) needs.

It only reads from the APIs. It never touches the catalog in data/.

Usage:
    read -rs DATA_GO_KR_API_KEY && export DATA_GO_KR_API_KEY
    python3 scripts/probe_apis.py

Exit codes: 0 all APIs answered, 1 some failed, 2 no key was given.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT_DIR / "backend" / "tests" / "fixtures" / "real"

GOV24_BASE = "https://api.odcloud.kr/api/gov24/v3"
CENTRAL_BASE = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"
LOCAL_BASE = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"

# The spec pages don't list operation names. These were confirmed against the live gateway:
# a real operation answers SERVICE_KEY_IS_NOT_REGISTERED_ERROR to a bad key, and a wrong name
# answers NO_OPENAPI_SERVICE_ERROR.
CENTRAL_LIST = "NationalWelfarelistV001"
CENTRAL_DETAIL = "NationalWelfaredetailedV001"
LOCAL_LIST = "LcgvWelfarelist"
LOCAL_DETAIL = "LcgvWelfaredetailed"

PAGE_SIZES = (100, 1000, 5000)
BOKJIRO_MAX_ROWS = 500
SAMPLE_ROWS = 5
TIMEOUT_SECONDS = 30
REDACTED = "[REDACTED]"

Fetch = Callable[[str], Tuple[int, str, float]]
Section = Dict[str, Any]


# ------------------------------------------------------------------------------
# Network and key safety
# ------------------------------------------------------------------------------

def encode_key(key: str) -> str:
    """data.go.kr issues an encoded and a decoded key. Only the decoded one needs quoting."""
    return key if "%" in key else urllib.parse.quote(key, safe="")


def redact(text: str, key: str) -> str:
    for secret in {key, encode_key(key), urllib.parse.unquote(key)}:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def http_get(url: str, retries: int = 2) -> Tuple[int, str, float]:
    """Returns (status, body, seconds). Status is 0 on a network failure. Never raises."""
    started = time.monotonic()
    for attempt in range(retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "WelFamily-Probe/1.0"})
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8", "replace")
                return response.status, body, time.monotonic() - started
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            if error.code < 500 or attempt == retries:
                return error.code, body, time.monotonic() - started
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError) as error:
            if attempt == retries:
                return 0, str(error), time.monotonic() - started
        time.sleep(2 ** attempt)
    return 0, "No attempts were made", time.monotonic() - started


class Client:
    """Every response passes through here, so the key can't reach a saved file."""

    def __init__(self, key: str, fetch: Fetch):
        self.key = key
        self.fetch = fetch
        self.calls: List[Dict[str, Any]] = []

    def get(self, label: str, base: str, params: Dict[str, Any]) -> Tuple[int, str]:
        query = urllib.parse.urlencode(params)
        status, body, seconds = self.fetch(f"{base}?serviceKey={encode_key(self.key)}&{query}")
        self.calls.append({"label": label, "status": status, "seconds": round(seconds, 1)})
        return status, redact(body, self.key)


def describe_failure(status: int, body: str) -> str:
    """Prefers the gateway's own error fields, which say whether the key or the request is wrong."""
    root = parse_xml(body)
    if root is not None:
        reason = " / ".join(filter(None, [xml_text(root, "errMsg"), xml_text(root, "returnAuthMsg")]))
        if reason:
            return f"HTTP {status}: {reason}"
    text = re.sub(r"\s+", " ", body).strip()
    return f"HTTP {status}: {text[:160]}"


# ------------------------------------------------------------------------------
# Analysis helpers
# ------------------------------------------------------------------------------

def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def fill_rates(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Percent of rows where each field has a value."""
    if not rows:
        return {}
    fields = sorted({field for row in rows for field in row})
    return {field: round(100 * sum(not is_blank(row.get(field)) for row in rows) / len(rows)) for field in fields}


def blank_rate_by_group(rows: List[Dict[str, Any]], group_field: str, value_field: str) -> Dict[str, str]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(group_field) or "(blank)"), []).append(row)
    result = {}
    for name, members in sorted(groups.items()):
        blanks = sum(is_blank(row.get(value_field)) for row in members)
        result[name] = f"{blanks} of {len(members)} blank"
    return result


def agency_examples(rows: List[Dict[str, Any]], per_type: int = 4) -> Dict[str, List[Tuple[Any, Any, Any]]]:
    """A few distinct agencies for each agency type."""
    examples: Dict[str, List[Tuple[Any, Any, Any]]] = {}
    for row in rows:
        group = examples.setdefault(str(row.get("소관기관유형")), [])
        entry = (row.get("소관기관코드"), row.get("소관기관명"), row.get("부서명"))
        if len(group) < per_type and entry not in group:
            group.append(entry)
    return examples


def condition_values(rows: List[Dict[str, Any]]) -> Dict[str, Counter]:
    """Distinct values per JA eligibility code, which shows how the codes are encoded."""
    values: Dict[str, Counter] = {}
    for row in rows:
        for field, value in row.items():
            if re.fullmatch(r"JA\d{4}", field) and not is_blank(value):
                values.setdefault(field, Counter())[str(value)] += 1
    return values


def filter_works(rows: List[Dict[str, Any]], service_id: str) -> bool:
    return bool(rows) and all(str(row.get("서비스ID")) == service_id for row in rows)


def parse_json(text: str) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def parse_xml(text: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


def xml_records(root: ET.Element) -> List[Dict[str, str]]:
    """Finds the repeated record element without assuming its name."""
    groups = Counter(element.tag for element in root.iter() if len(element) and element is not root)
    if not groups:
        return []
    tag = max(reversed(list(groups)), key=groups.get)  # on a tie, prefer the deepest element
    return [{child.tag: (child.text or "").strip() for child in element} for element in root.iter(tag)]


def xml_text(root: ET.Element, *tags: str) -> str:
    for tag in tags:
        element = root.find(f".//{tag}")
        if element is not None and (element.text or "").strip():
            return element.text.strip()
    return ""


def bullets(mapping: Dict[str, Any], suffix: str = "") -> List[str]:
    return [f"  - `{name}`: {value}{suffix}" for name, value in mapping.items()]


def write_sample(out: Path, name: str, text: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / name).write_text(text, encoding="utf-8")


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


# ------------------------------------------------------------------------------
# 보조금24 (JSON)
# ------------------------------------------------------------------------------

def probe_gov24(client: Client, out: Path) -> Section:
    section: Section = {"title": "보조금24 (15113968)", "ok": False, "lines": []}
    lines = section["lines"]

    rows: List[Dict[str, Any]] = []
    total: Any = None
    sizes: Dict[int, int] = {}
    first_payload: Optional[Dict[str, Any]] = None
    for size in PAGE_SIZES:
        status, body = client.get(f"serviceList perPage={size}", f"{GOV24_BASE}/serviceList", {"page": 1, "perPage": size})
        payload = parse_json(body)
        if status != 200 or payload is None or "data" not in payload:
            if not sizes:
                lines.append(f"- serviceList failed. {describe_failure(status, body)}")
                return section
            lines.append(f"- perPage={size} failed. {describe_failure(status, body)}")
            break
        first_payload = first_payload or payload
        page = payload["data"]
        sizes[size] = len(page)
        total = payload.get("totalCount", total)
        if len(page) > len(rows):
            rows = page
        if len(page) < size:
            break

    write_sample(out, "gov24_service_list.json", dump({**first_payload, "data": rows[:SAMPLE_ROWS]}))
    section["ok"] = True

    lines.append(f"- Total records: {total}")
    lines.append(f"- Rows returned per requested page size: {sizes}")
    lines.append(f"- Field fill rate, from a sample of {len(rows)} rows:")
    lines.extend(bullets(fill_rates(rows), "%"))

    lines.append("- Records by 소관기관유형:")
    lines.extend(bullets(dict(Counter(str(row.get("소관기관유형")) for row in rows).most_common())))
    lines.append("- Blank 선정기준 by 소관기관유형:")
    lines.extend(bullets(blank_rate_by_group(rows, "소관기관유형", "선정기준")))

    code_lengths = Counter(len(str(row.get("소관기관코드") or "")) for row in rows)
    lines.append(f"- 소관기관코드 lengths: {dict(code_lengths)}")
    # The agency type values aren't documented, so show examples for every type found.
    lines.append("- Agency code examples, for region mapping:")
    for agency_type, examples in agency_examples(rows).items():
        lines.append(f"  - {agency_type}")
        lines.extend(f"    - `{code}` {name} / {department}" for code, name, department in examples)

    service_id = str(rows[0].get("서비스ID")) if rows else ""
    if not service_id:
        lines.append("- No 서비스ID found, so detail and condition checks were skipped.")
        return section
    id_filter = {"cond[서비스ID::EQ]": service_id}

    status, body = client.get("serviceList with cond", f"{GOV24_BASE}/serviceList", {"page": 1, "perPage": 10, **id_filter})
    payload = parse_json(body)
    filtered = filter_works(payload.get("data", []), service_id) if payload else False
    lines.append(f"- `cond[서비스ID::EQ]` on serviceList: {'works' if filtered else 'ignored or failed'}")

    status, body = client.get("serviceDetail", f"{GOV24_BASE}/serviceDetail", {"page": 1, "perPage": 10, **id_filter})
    payload = parse_json(body)
    if status == 200 and payload and payload.get("data"):
        filtered = filter_works(payload["data"], service_id)
        write_sample(out, "gov24_service_detail.json", dump({**payload, "data": payload["data"][:SAMPLE_ROWS]}))
        lines.append(f"- `cond[서비스ID::EQ]` on serviceDetail: {'works' if filtered else 'ignored'}")
        lines.append(f"- serviceDetail total records: {payload.get('totalCount')}")
        lines.append("- serviceDetail fields:")
        lines.extend(bullets(fill_rates(payload["data"]), "%"))
    else:
        section["ok"] = False
        lines.append(f"- serviceDetail failed. {describe_failure(status, body)}")

    status, body = client.get("supportConditions", f"{GOV24_BASE}/supportConditions", {"page": 1, "perPage": 1000})
    payload = parse_json(body)
    if status == 200 and payload and payload.get("data"):
        conditions = payload["data"]
        write_sample(out, "gov24_support_conditions.json", dump({**payload, "data": conditions[:SAMPLE_ROWS]}))
        values = condition_values(conditions)
        flags = Counter()
        for code, counter in values.items():
            if code not in ("JA0110", "JA0111"):
                flags.update(counter)
        lines.append(f"- supportConditions total records: {payload.get('totalCount')}")
        lines.append(f"- Eligibility flag values, sampled: {dict(flags.most_common(5))}")
        for code in ("JA0110", "JA0111"):
            lines.append(f"- {code} sample values: {list(values.get(code, Counter()))[:8]}")
        status, body = client.get("supportConditions with cond", f"{GOV24_BASE}/supportConditions",
                                  {"page": 1, "perPage": 10, **id_filter})
        payload = parse_json(body)
        filtered = filter_works(payload.get("data", []), service_id) if payload else False
        lines.append(f"- `cond[서비스ID::EQ]` on supportConditions: {'works' if filtered else 'ignored or failed'}")
    else:
        section["ok"] = False
        lines.append(f"- supportConditions failed. {describe_failure(status, body)}")

    return section


# ------------------------------------------------------------------------------
# Bokjiro (XML)
# ------------------------------------------------------------------------------

def get_records(client: Client, label: str, url: str,
                params: Dict[str, Any]) -> Tuple[Optional[ET.Element], str, str]:
    """Returns (parsed XML, raw text, failure message)."""
    status, body = client.get(label, url, params)
    root = parse_xml(body)
    if status == 200 and root is not None and xml_records(root):
        return root, body, ""
    return None, "", describe_failure(status, body)


def probe_bokjiro(client: Client, out: Path, title: str, prefix: str, base: str, list_path: str,
                  list_params: Dict[str, Any], detail_path: str, detail_params: Dict[str, Any]) -> Section:
    section: Section = {"title": title, "ok": False, "lines": []}
    lines = section["lines"]
    list_url = f"{base}/{list_path}"

    root, body, failure = get_records(client, list_path, list_url, {**list_params, "numOfRows": SAMPLE_ROWS})
    if root is None:
        lines.append(f"- List failed. {failure}")
        return section

    records = xml_records(root)
    write_sample(out, f"{prefix}_list.xml", body)
    section["ok"] = True
    lines.append(f"- Total records: {xml_text(root, 'totalCount') or 'not reported'}")

    big_root, _, failure = get_records(client, f"{list_path} numOfRows={BOKJIRO_MAX_ROWS}", list_url,
                                       {**list_params, "numOfRows": BOKJIRO_MAX_ROWS})
    if big_root is not None:
        records = xml_records(big_root)
        lines.append(f"- Rows returned for numOfRows={BOKJIRO_MAX_ROWS}: {len(records)}")
    else:
        lines.append(f"- numOfRows={BOKJIRO_MAX_ROWS} failed. {failure}")

    lines.append(f"- List fields, from a sample of {len(records)} rows:")
    lines.extend(bullets(fill_rates(records), "%"))

    service_id = next((record["servId"] for record in records if record.get("servId")), "")
    if not service_id:
        lines.append("- No `servId` found, so the detail check was skipped.")
        return section

    root, body, failure = get_records(client, detail_path, f"{base}/{detail_path}",
                                      {**detail_params, "servId": service_id})
    if root is None:
        section["ok"] = False
        lines.append(f"- Detail failed. {failure}")
        return section

    write_sample(out, f"{prefix}_detail.xml", body)
    fields = sorted({element.tag for element in root.iter() if not len(element)})
    lines.append(f"- Detail fields: {', '.join(fields)}")
    return section


# ------------------------------------------------------------------------------
# Report
# ------------------------------------------------------------------------------

def write_findings(out: Path, sections: List[Section], calls: List[Dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = ["# API probe findings", "", f"Generated by `scripts/probe_apis.py` on {now}.", ""]
    for section in sections:
        lines += [f"## {section['title']}", "", f"Status: {'OK' if section['ok'] else 'FAILED'}", ""]
        lines += section["lines"] + [""]
    slowest = max((call["seconds"] for call in calls), default=0)
    lines += ["## Calls", "", f"{len(calls)} calls. Slowest: {slowest}s.", "",
              "| Call | Status | Seconds |", "| :--- | :--- | :--- |"]
    lines += [f"| {call['label']} | {call['status']} | {call['seconds']} |" for call in calls]
    write_sample(out, "FINDINGS.md", "\n".join(lines) + "\n")


def run(key: str, out: Path, fetch: Fetch = http_get) -> int:
    client = Client(key, fetch)
    sections = [
        probe_gov24(client, out),
        probe_bokjiro(
            client, out, "Bokjiro central (15090532)", "bokjiro_central", CENTRAL_BASE,
            CENTRAL_LIST, {"callTp": "L", "pageNo": 1, "srchKeyCode": "003"},
            CENTRAL_DETAIL, {"callTp": "D"},
        ),
        probe_bokjiro(
            client, out, "Bokjiro local (15108347)", "bokjiro_local", LOCAL_BASE,
            LOCAL_LIST, {"pageNo": 1}, LOCAL_DETAIL, {},
        ),
    ]
    write_findings(out, sections, client.calls)
    for section in sections:
        print(f"{'OK    ' if section['ok'] else 'FAILED'} {section['title']}")
    print(f"Findings: {out / 'FINDINGS.md'}")
    return 0 if all(section["ok"] for section in sections) else 1


def main(argv: Optional[List[str]] = None, fetch: Fetch = http_get) -> int:
    parser = argparse.ArgumentParser(description="Probe the public welfare APIs.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="folder for samples and FINDINGS.md")
    args = parser.parse_args(argv)

    key = os.getenv("DATA_GO_KR_API_KEY", "").strip()
    if not key:
        print("DATA_GO_KR_API_KEY is not set. Nothing was called or written.", file=sys.stderr)
        return 2
    return run(key, args.out, fetch)


if __name__ == "__main__":
    sys.exit(main())
