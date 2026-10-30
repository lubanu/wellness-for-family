"""
backend/app/services/local_welfare_service.py
================================================================================
Local Government Welfare Management Service:
- Lifecycle CRUD for Municipal Ordinance & Special Benefits.
- 1-Click 3-Second Quick Budget Status Patch with is_urgent & D-Day automation.
- GitOps Change Log integration and atomic persistence.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import uuid

from app.core.config import settings
from app.schemas.unified_policy import (
    ApplicationPeriodType,
    BudgetStatus,
    PolicyCategory,
    PolicyOrigin,
    RequiredDocument,
    TargetEligibility,
    UnifiedWelfarePolicy,
)
from app.schemas.local_policy import (
    LocalPolicyCreateSchema,
    LocalPolicyStatusPatchSchema,
)
from app.services.deduplication import generate_policy_fingerprint
from app.services.versioning import track_policy_change


def _get_catalog_path(catalog_path: Optional[str] = None) -> Path:
    if catalog_path:
        return Path(catalog_path)
    env_path = os.getenv("CATALOG_PATH")
    if env_path:
        return Path(env_path)
    return Path(getattr(settings, "CATALOG_PATH", settings.BASE_DIR / "data" / "welfare_catalog.json"))


def load_catalog(catalog_path: Optional[str] = None) -> Dict[str, Any]:
    c_path = _get_catalog_path(catalog_path)
    if c_path.exists():
        try:
            with open(c_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "policies" in data:
                    return data
        except Exception as e:
            raise RuntimeError(f"Critical: Failed to load existing catalog ({e}). Aborting to prevent data wipeout.")
    return {"version": "1.0.0", "policies": []}


def save_catalog(catalog: Dict[str, Any], catalog_path: Optional[str] = None) -> None:
    c_path = _get_catalog_path(catalog_path)
    c_path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = c_path.with_suffix(f".tmp_{uuid.uuid4().hex[:6]}")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, c_path)


def create_local_policy(
    data: Union[LocalPolicyCreateSchema, Dict[str, Any]],
    catalog_path: Optional[str] = None,
) -> UnifiedWelfarePolicy:
    """
    Registers a new municipal special policy into the catalog.
    Validates against LocalPolicyCreateSchema and persists with origin=LOCAL.
    Logs NEW_LOCAL_POLICY change event into monthly changelog.
    """
    if isinstance(data, dict):
        validated = LocalPolicyCreateSchema(**data)
    else:
        validated = data

    cat_str = validated.category.value if hasattr(validated.category, "value") else str(validated.category)
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()

    # Compute deterministic fingerprint
    min_a = validated.target_eligibility.min_age if validated.target_eligibility else 0
    max_a = validated.target_eligibility.max_age if validated.target_eligibility else 120
    fp = generate_policy_fingerprint(
        region_code=validated.region_code,
        category=cat_str,
        title=validated.title,
        managing_org=validated.managing_org,
        min_age=min_a,
        max_age=max_a,
    )

    policy_id = f"pol_{validated.region_code}_{cat_str.lower()}_{fp[:8]}"

    # Normalize required documents
    norm_docs: List[RequiredDocument] = []
    for doc in validated.required_documents:
        if isinstance(doc, RequiredDocument):
            norm_docs.append(doc)
        elif isinstance(doc, dict):
            norm_docs.append(RequiredDocument(**doc))
        elif isinstance(doc, str):
            norm_docs.append(RequiredDocument(name=doc, issuer="정부24", can_online=True))

    unified = UnifiedWelfarePolicy(
        id=policy_id,
        fingerprint=fp,
        source_id=None,
        source_type="LOCAL_OFFICER",
        title=validated.title,
        origin=PolicyOrigin.LOCAL,
        region_code=validated.region_code,
        region_name=validated.region_name,
        managing_org=validated.managing_org,
        local_ordinance_basis=validated.local_ordinance_basis,
        category=validated.category,
        amount_value=validated.amount_value,
        amount_text=validated.amount_text,
        target_eligibility=validated.target_eligibility,
        certainty_score=95,
        application_period_type=validated.application_period_type,
        start_date=validated.start_date,
        end_date=validated.end_date,
        is_budget_limited=validated.is_budget_limited,
        budget_status=validated.budget_status,
        slot_capacity=validated.slot_capacity,
        current_applicant_count=validated.current_applicant_count,
        is_urgent=False,
        dday_text=f"{validated.end_date} 마감" if validated.end_date else "선착순 접수",
        summary_3lines=validated.summary_3lines,
        required_documents=norm_docs,
        application_url=validated.application_url,
        contact_phone=validated.contact_phone,
        version=1,
        created_at=now_iso,
        updated_at=now_iso,
        last_verified_at=now_iso,
    )

    # Persist into catalog
    catalog = load_catalog(catalog_path)
    policies = catalog.get("policies", [])

    # Check duplicate ID or fingerprint
    existing_idx = next((i for i, p in enumerate(policies) if p.get("id") == policy_id or p.get("fingerprint") == fp), -1)
    policy_dict = unified.model_dump()
    if existing_idx >= 0:
        policies[existing_idx] = policy_dict
    else:
        policies.insert(0, policy_dict)

    catalog["policies"] = policies
    catalog["total_policies"] = len(policies)
    catalog["last_updated"] = now_iso
    save_catalog(catalog, catalog_path)

    # Record audit changelog
    track_policy_change(
        old_policy=None,
        new_policy=policy_dict,
        author="local_officer",
        change_type="NEW_LOCAL_POLICY",
    )

    return unified


def update_local_policy(
    policy_id: str,
    data: Union[LocalPolicyCreateSchema, Dict[str, Any]],
    catalog_path: Optional[str] = None,
) -> UnifiedWelfarePolicy:
    """
    Updates all attributes of an existing municipal policy.
    Bumps version and records field-level diff into changelog.
    """
    if isinstance(data, dict):
        validated = LocalPolicyCreateSchema(**data)
    else:
        validated = data

    catalog = load_catalog(catalog_path)
    policies = catalog.get("policies", [])
    idx = next((i for i, p in enumerate(policies) if p.get("id") == policy_id), -1)
    if idx == -1:
        raise KeyError(f"Local policy '{policy_id}' not found in catalog")

    old_policy = policies[idx]
    now_iso = datetime.now(timezone.utc).isoformat()
    new_version = old_policy.get("version", 1) + 1

    # Normalize documents
    norm_docs: List[RequiredDocument] = []
    for doc in validated.required_documents:
        if isinstance(doc, RequiredDocument):
            norm_docs.append(doc)
        elif isinstance(doc, dict):
            norm_docs.append(RequiredDocument(**doc))
        elif isinstance(doc, str):
            norm_docs.append(RequiredDocument(name=doc, issuer="정부24", can_online=True))

    unified = UnifiedWelfarePolicy(
        id=policy_id,
        fingerprint=old_policy.get("fingerprint"),
        source_id=old_policy.get("source_id"),
        source_type=old_policy.get("source_type", "LOCAL_OFFICER"),
        title=validated.title,
        origin=PolicyOrigin.LOCAL,
        region_code=validated.region_code,
        region_name=validated.region_name,
        managing_org=validated.managing_org,
        local_ordinance_basis=validated.local_ordinance_basis,
        category=validated.category,
        amount_value=validated.amount_value,
        amount_text=validated.amount_text,
        target_eligibility=validated.target_eligibility,
        certainty_score=old_policy.get("certainty_score", 95),
        application_period_type=validated.application_period_type,
        start_date=validated.start_date,
        end_date=validated.end_date,
        is_budget_limited=validated.is_budget_limited,
        budget_status=validated.budget_status,
        slot_capacity=validated.slot_capacity,
        current_applicant_count=validated.current_applicant_count,
        is_urgent=old_policy.get("is_urgent", False),
        dday_text=validated.amount_text if old_policy.get("dday_text") is None else old_policy.get("dday_text"),
        summary_3lines=validated.summary_3lines,
        required_documents=norm_docs,
        application_url=validated.application_url,
        contact_phone=validated.contact_phone,
        version=new_version,
        created_at=old_policy.get("created_at", now_iso),
        updated_at=now_iso,
        last_verified_at=now_iso,
    )

    policy_dict = unified.model_dump()
    policies[idx] = policy_dict
    catalog["policies"] = policies
    catalog["last_updated"] = now_iso
    save_catalog(catalog, catalog_path)

    track_policy_change(
        old_policy=old_policy,
        new_policy=policy_dict,
        author="local_officer",
        change_type="POLICY_UPDATED",
    )

    return unified


def patch_policy_status(
    policy_id: str,
    patch: Union[LocalPolicyStatusPatchSchema, Dict[str, Any]],
    catalog_path: Optional[str] = None,
) -> UnifiedWelfarePolicy:
    """
    1-Click 3-Second Quick Budget Status Patch for municipal civil servants:
    - Transitions budget_status (OPEN, PLENTY, HALF_CONSUMED, NEAR_EXHAUSTION, EXHAUSTED, CLOSING_SOON).
    - When budget_status transitions to NEAR_EXHAUSTION, CLOSING_SOON, or when is_urgent is requested,
      automatically activates is_urgent: True and formats urgent D-Day text.
    - When transitioning to EXHAUSTED, automatically sets is_budget_limited: True.
    - Saves updated state atomically to catalog and records changelog audit entry.
    """
    if isinstance(patch, dict):
        patch_model = LocalPolicyStatusPatchSchema(**patch)
    else:
        patch_model = patch

    catalog = load_catalog(catalog_path)
    policies = catalog.get("policies", [])
    idx = next((i for i, p in enumerate(policies) if p.get("id") == policy_id), -1)
    if idx == -1:
        raise KeyError(f"Local policy '{policy_id}' not found in catalog")

    target = policies[idx]
    old_target = dict(target)

    # Determine status string
    b_status = patch_model.budget_status
    if hasattr(b_status, "value"):
        b_status_str = b_status.value
    elif b_status:
        b_status_str = str(b_status)
    else:
        b_status_str = patch_model.status or "OPEN"

    target["budget_status"] = b_status_str

    # Update applicant count if provided
    if patch_model.current_applicant_count is not None:
        target["current_applicant_count"] = patch_model.current_applicant_count

    # Auto-adjust is_urgent:
    if patch_model.is_urgent is not None:
        target["is_urgent"] = patch_model.is_urgent
    elif b_status_str in ("NEAR_EXHAUSTION", "CLOSING_SOON"):
        target["is_urgent"] = True
    elif b_status_str == "EXHAUSTED":
        target["is_urgent"] = False

    # Auto-adjust is_budget_limited:
    if b_status_str == "EXHAUSTED":
        target["is_budget_limited"] = True
    elif b_status_str in ("NEAR_EXHAUSTION", "HALF_CONSUMED"):
        target["is_budget_limited"] = True

    # Auto-adjust dday_text:
    if patch_model.dday_text:
        target["dday_text"] = patch_model.dday_text
    else:
        if b_status_str in ("NEAR_EXHAUSTION", "CLOSING_SOON"):
            target["dday_text"] = "선착순 마감임박!"
        elif b_status_str == "EXHAUSTED":
            target["dday_text"] = "선착순 예산 전액 소진 마감"
        elif b_status_str == "HALF_CONSUMED":
            target["dday_text"] = "예산 50% 소진"
        elif b_status_str in ("PLENTY", "OPEN"):
            target["dday_text"] = target.get("dday_text") or "상시 접수"

    if patch_model.closure_reason:
        target["closure_reason"] = patch_model.closure_reason

    # Bump version and timestamps
    now_iso = datetime.now(timezone.utc).isoformat()
    target["version"] = target.get("version", 1) + 1
    target["updated_at"] = now_iso
    target["last_verified_at"] = now_iso

    policies[idx] = target
    catalog["policies"] = policies
    catalog["last_updated"] = now_iso
    save_catalog(catalog, catalog_path)

    # Record changelog
    track_policy_change(
        old_policy=old_target,
        new_policy=target,
        author="local_officer",
        change_type="STATUS_CHANGED",
    )

    return UnifiedWelfarePolicy(**target)


def get_local_policy(policy_id: str, catalog_path: Optional[str] = None) -> UnifiedWelfarePolicy:
    """Retrieves a single local policy by ID."""
    catalog = load_catalog(catalog_path)
    policies = catalog.get("policies", [])
    target = next((p for p in policies if p.get("id") == policy_id), None)
    if not target:
        raise KeyError(f"Policy '{policy_id}' not found")
    return UnifiedWelfarePolicy(**target)


def list_local_policies(
    region_code: Optional[str] = None,
    budget_status: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
    catalog_path: Optional[str] = None,
) -> List[UnifiedWelfarePolicy]:
    """Lists municipal policies with optional region, status, and keyword filtering."""
    catalog = load_catalog(catalog_path)
    policies = catalog.get("policies", [])

    effective_status = budget_status or status
    results: List[UnifiedWelfarePolicy] = []

    for p in policies:
        # Filter origin (only local policies in municipal admin view)
        origin_val = p.get("origin") or p.get("origin_type")
        if origin_val != "LOCAL" and (region_code and region_code != "ALL" and p.get("region_code") != region_code):
            continue

        if region_code and region_code != "ALL":
            if p.get("region_code") != region_code:
                continue

        if effective_status and effective_status != "ALL":
            p_status = p.get("budget_status") or p.get("status")
            if p_status != effective_status:
                continue

        if q:
            q_clean = q.strip().lower()
            text = (
                str(p.get("title", "")) +
                str(p.get("managing_org", "")) +
                " ".join(p.get("summary_3lines", []))
            ).lower()
            if q_clean not in text:
                continue

        try:
            results.append(UnifiedWelfarePolicy(**p))
        except Exception:
            # Fallback construct if legacy dictionary
            min_a = p.get("target_eligibility", {}).get("min_age", 0) if isinstance(p.get("target_eligibility"), dict) else 0
            max_a = p.get("target_eligibility", {}).get("max_age", 120) if isinstance(p.get("target_eligibility"), dict) else 120
            p["target_eligibility"] = TargetEligibility(min_age=min_a, max_age=max_a)
            if not p.get("summary_3lines"):
                p["summary_3lines"] = ["안내 1", "안내 2", "안내 3"]
            results.append(UnifiedWelfarePolicy(**p))

    return results


def delete_local_policy(policy_id: str, catalog_path: Optional[str] = None) -> bool:
    """Deletes / retires a municipal policy from catalog."""
    catalog = load_catalog(catalog_path)
    policies = catalog.get("policies", [])
    idx = next((i for i, p in enumerate(policies) if p.get("id") == policy_id), -1)
    if idx == -1:
        raise KeyError(f"Policy '{policy_id}' not found")

    removed = policies.pop(idx)
    catalog["policies"] = policies
    catalog["total_policies"] = len(policies)
    catalog["last_updated"] = datetime.now(timezone.utc).isoformat()
    save_catalog(catalog, catalog_path)

    track_policy_change(
        old_policy=removed,
        new_policy={"id": policy_id, "version": removed.get("version", 1) + 1, "status": "DELETED"},
        author="local_officer",
        change_type="POLICY_DELETED",
    )
    return True
