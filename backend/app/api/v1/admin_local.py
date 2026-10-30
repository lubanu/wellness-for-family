"""
backend/app/api/v1/admin_local.py
================================================================================
FastAPI Router for Local Government Welfare Management:
- Municipal Special Policy Registration (POST)
- 1-Click 3-Second Quick Budget Status Patch (PATCH /status)
- Policy Update and Deletion (PUT, DELETE)
- Scoped Policy Retrieval and Filtering (GET)
- Staged Announcement Human-in-the-Loop Approval (POST /staging/{id}/approve)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings
from app.schemas.local_policy import (
    LocalPolicyCreateSchema,
    LocalPolicyStatusPatchSchema,
)
from app.schemas.unified_policy import UnifiedWelfarePolicy
from app.services import local_welfare_service

router = APIRouter()


@router.post("", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED, include_in_schema=False)
def register_local_policy(data: LocalPolicyCreateSchema) -> Dict[str, Any]:
    """
    Registers a new municipal special policy (조례 및 특화사업).
    Performs Pydantic v2 validation and commits to master catalog with audit logging.
    """
    try:
        policy = local_welfare_service.create_local_policy(data)
        return {
            "status": "SUCCESS",
            "policy_id": policy.id,
            "fingerprint": policy.fingerprint,
            "message": f"{policy.region_name} 특화사업이 성공적으로 등록되었습니다.",
            "data": policy.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=Dict[str, Any])
@router.get("/", response_model=Dict[str, Any], include_in_schema=False)
def list_local_policies(
    region_code: Optional[str] = Query(None, description="지자체 행정코드 (예: seoul_gwanak)"),
    budget_status: Optional[str] = Query(None, description="예산 상태 필터 (PLENTY, NEAR_EXHAUSTION, EXHAUSTED 등)"),
    status: Optional[str] = Query(None, description="상태 필터 호환"),
    q: Optional[str] = Query(None, description="검색 키워드"),
) -> Dict[str, Any]:
    """
    Lists municipal policies filtered by administrative region, budget status, or query keywords.
    """
    policies = local_welfare_service.list_local_policies(
        region_code=region_code,
        budget_status=budget_status,
        status=status,
        q=q,
    )
    return {
        "total": len(policies),
        "policies": [p.model_dump() for p in policies],
    }


@router.get("/{policy_id}", response_model=Dict[str, Any])
def get_local_policy_detail(policy_id: str) -> Dict[str, Any]:
    """
    Retrieves details of a specific municipal policy by ID.
    """
    try:
        policy = local_welfare_service.get_local_policy(policy_id)
        return {
            "status": "SUCCESS",
            "policy": policy.model_dump(),
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local policy '{policy_id}' not found",
        )


@router.put("/{policy_id}", response_model=Dict[str, Any])
def update_local_policy(policy_id: str, data: LocalPolicyCreateSchema) -> Dict[str, Any]:
    """
    Updates the full specification of an existing municipal policy.
    Bumps revision version and records field-level diff into changelog.
    """
    try:
        updated = local_welfare_service.update_local_policy(policy_id, data)
        return {
            "status": "SUCCESS",
            "policy_id": updated.id,
            "message": "특화사업이 성공적으로 수정되었습니다.",
            "data": updated.model_dump(),
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local policy '{policy_id}' not found",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/{policy_id}/status", response_model=Dict[str, Any])
def patch_local_policy_status(
    policy_id: str,
    patch: LocalPolicyStatusPatchSchema,
) -> Dict[str, Any]:
    """
    ★ 1-Click 3-Second Quick Budget Status Patch for municipal civil servants:
    - Quickly marks policies NEAR_EXHAUSTION, CLOSING_SOON, or EXHAUSTED.
    - Automatically raises urgent badge (is_urgent: True) and updates dday_text.
    - Prevents futile resident visits and reduces civil complaint calls.
    """
    try:
        # Load previous status for audit response
        catalog = local_welfare_service.load_catalog()
        prev = next((p for p in catalog.get("policies", []) if p.get("id") == policy_id), None)
        prev_status = prev.get("budget_status", "OPEN") if prev else "OPEN"

        updated = local_welfare_service.patch_policy_status(policy_id, patch)
        status_val = updated.budget_status.value if hasattr(updated.budget_status, "value") else str(updated.budget_status)

        return {
            "status": "SUCCESS",
            "policy_id": updated.id,
            "previous_budget_status": prev_status,
            "current_budget_status": status_val,
            "budget_status": status_val,
            "is_urgent": updated.is_urgent,
            "dday_text": updated.dday_text,
            "updated_at": updated.updated_at,
            "version": updated.version,
            "data": updated.model_dump(),
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local policy '{policy_id}' not found",
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{policy_id}", response_model=Dict[str, Any])
def delete_local_policy(policy_id: str) -> Dict[str, Any]:
    """
    Deactivates or deletes a municipal policy from catalog with audit trail.
    """
    try:
        local_welfare_service.delete_local_policy(policy_id)
        return {
            "status": "SUCCESS",
            "policy_id": policy_id,
            "message": "정책이 성공적으로 삭제되었습니다.",
        }
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Local policy '{policy_id}' not found",
        )


@router.post("/staging/{candidate_id}/approve", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def approve_staging_announcement(candidate_id: str) -> Dict[str, Any]:
    """
    Approves a scraped municipal notice candidate from the staging queue (data/local_staging_queue.json)
    and promotes it into the active production catalog.
    """
    import os
    from pathlib import Path
    import json

    staging_path_str = os.getenv("STAGING_PATH", getattr(settings, "STAGING_PATH", str(settings.BASE_DIR / "data" / "local_staging_queue.json")))
    staging_file = Path(staging_path_str)

    if not staging_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staging queue not found")

    try:
        with open(staging_file, "r", encoding="utf-8") as f:
            staging_data = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error reading staging queue: {e}")

    policies_list = staging_data if isinstance(staging_data, list) else staging_data.get("staged_policies", [])
    candidate = next((p for p in policies_list if p.get("stg_id") == candidate_id or p.get("id") == candidate_id), None)

    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Staged candidate '{candidate_id}' not found")

    # Promote to active policy
    try:
        policy = local_welfare_service.create_local_policy(candidate)
        candidate["review_status"] = "APPROVED"

        # Update staging queue
        with open(staging_file, "w", encoding="utf-8") as f:
            json.dump(staging_data, f, ensure_ascii=False, indent=2)

        return {
            "status": "SUCCESS",
            "message": f"Staged policy candidate '{candidate_id}' approved and published to catalog.",
            "policy_id": policy.id,
            "data": policy.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to approve candidate: {e}")
