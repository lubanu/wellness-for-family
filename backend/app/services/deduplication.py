"""
backend/app/services/deduplication.py
================================================================================
Hardened Composite Fingerprint Hash Deduplication Engine for Welfare Policies.
Neutralizes typography noise, word permutations, sub-department suffixes,
and eliminates collisions via lifecycle age discrimination.
"""

import hashlib
import re
from typing import Any, Dict, List, Optional, Set, Union


STOP_WORDS = {
    "사업", "지원사업", "지원", "안내", "공고", "신청", "대한민국", "정부",
    "2024년", "2025년", "2026년", "2027년", "2028년", "2026", "2025", "2024",
    "2024년도", "2025년도", "2026년도", "2027년도", "2028년도", "년도", "상반기", "하반기"
}

YEAR_PATTERN = re.compile(r"^\d{4}(년|년도)?$")
SUB_DEPT_PATTERN = re.compile(
    r"(인구아동정책과|기초생활보장과|청년정책과|주거복지지원과|복지정책과|보건복지국|여성가족실|[\w]+과)$"
)


def _extract_org_stopwords(org_clean: str) -> Set[str]:
    """Extract municipal and administrative tokens from cleaned org name."""
    words = set(re.findall(r"[\w가-힣]+", org_clean))
    expanded = set(words)
    for w in words:
        if len(w) >= 3 and (w.endswith("구") or w.endswith("시") or w.endswith("군") or w.endswith("도")):
            expanded.add(w[:-1])
        if "특별시" in w:
            expanded.add(w.replace("특별시", "시"))
            expanded.add(w.replace("특별시", ""))
        if "광역시" in w:
            expanded.add(w.replace("광역시", "시"))
            expanded.add(w.replace("광역시", ""))
    return {x for x in expanded if len(x) > 1}


def generate_policy_fingerprint(
    *args,
    region_code: Optional[str] = None,
    category: Optional[str] = None,
    title: Optional[str] = None,
    managing_org: Optional[str] = None,
    min_age: int = 0,
    max_age: int = 120,
    **kwargs
) -> str:
    """
    Generate a deterministic 16-character SHA-256 composite fingerprint.

    Supports dual invocation:
    1. Single dictionary or model argument: generate_policy_fingerprint(policy_dict)
    2. Explicit arguments: generate_policy_fingerprint(region_code, category, title, managing_org, min_age, max_age)

    Hardening Mechanisms:
    - Selective typography bracket stripping ([ ], 【 】, etc.) preserving age info in parentheses
    - Set-based token sorting and deduplication
    - Suffix canonicalization of managing org sub-departments
    - Age discriminator (age_min_max) to guarantee zero collisions between age tiers (e.g. parent allowance 0 vs 1)
    """
    # 1. Parse arguments (Dict vs positional vs kwargs)
    if len(args) == 1 and (isinstance(args[0], dict) or hasattr(args[0], "__dict__")):
        p = args[0]
        if hasattr(p, "model_dump"):
            p = p.model_dump()
        elif hasattr(p, "__dict__") and not isinstance(p, dict):
            p = p.__dict__

        title = p.get("title", "")
        region_code = p.get("region_code", "")
        category = p.get("category", "")
        managing_org = p.get("managing_org", "")

        t_elig = p.get("target_eligibility") or {}
        if isinstance(t_elig, dict):
            min_age = t_elig.get("min_age", p.get("min_age", 0))
            max_age = t_elig.get("max_age", p.get("max_age", 120))
        else:
            min_age = getattr(t_elig, "min_age", getattr(p, "min_age", 0))
            max_age = getattr(t_elig, "max_age", getattr(p, "max_age", 120))
    elif len(args) >= 4:
        region_code = args[0]
        category = args[1]
        title = args[2]
        managing_org = args[3]
        if len(args) >= 5:
            min_age = args[4]
        if len(args) >= 6:
            max_age = args[5]

    # Kwargs overrides
    title = kwargs.get("title", title or "")
    region_code = kwargs.get("region_code", region_code or "")
    category = kwargs.get("category", category or "")
    managing_org = kwargs.get("managing_org", managing_org or "")
    min_age = kwargs.get("min_age", min_age)
    max_age = kwargs.get("max_age", max_age)

    # Normalize category string
    if hasattr(category, "value"):
        category = category.value
    category_str = str(category).strip().upper()

    # 2. Typography bracket stripping (removes [ ], 【 】, 《 》, etc., preserves parentheses)
    cleaned_title = re.sub(r"\[.*?\]|【.*?】|〈.*?〉|《.*?》|「.*?」|『.*?』", " ", str(title))

    # 3. Clean managing organization sub-departments
    org_clean = SUB_DEPT_PATTERN.sub("", str(managing_org).strip())
    org_stopwords = _extract_org_stopwords(org_clean)

    # 4. Extract words & filter noise/stop words
    words = re.findall(r"[\w가-힣]+", cleaned_title)
    tokens: List[str] = []
    for w in words:
        if w in STOP_WORDS:
            continue
        if YEAR_PATTERN.match(w):
            continue
        if w in org_stopwords:
            continue
        if len(w) <= 1:
            continue
        tokens.append(w)

    # 5. Fallback guard if title only consisted of stop words
    if not tokens:
        fallback_words = [w for w in words if len(w) > 1]
        tokens = fallback_words if fallback_words else [cleaned_title.strip()[:20]]

    sorted_tokens = "_".join(sorted(list(set(tokens))))

    # 6. Build canonical keys
    reg_key = str(region_code).strip().lower()
    org_key = re.sub(r"\s+", "", org_clean.lower())
    age_key = f"age_{min_age}_{max_age}"

    composite_raw = f"{reg_key}:{category_str}:{sorted_tokens}:{age_key}:{org_key}"
    return hashlib.sha256(composite_raw.encode("utf-8")).hexdigest()[:16]


# Alias for backwards compatibility with tests
generate_composite_hash = generate_policy_fingerprint
