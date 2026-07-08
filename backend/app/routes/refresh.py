"""
KrishiMitra Backend – Refresh Routes
======================================
POST /refresh/full    – Full refresh: re-run every provider, ignore all caches
GET  /refresh/status  – Get refresh progress/status
GET  /refresh/latest  – Get the latest refresh snapshot for the user
"""
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser
from app.schemas.responses import success_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/refresh", tags=["Data Refresh"])


class FullRefreshRequest(BaseModel):
    farm_id: Optional[str] = Field(None, description="Optional farm ID to refresh")
    field_id: Optional[str] = Field(None, description="Optional field ID to refresh")


@router.post(
    "/full",
    summary="Full refresh: re-run every provider, ignore all caches",
    response_description="Refresh results with provider status and snapshot version",
)
async def full_refresh(
    payload: FullRefreshRequest,
    current_user: CurrentUser,
) -> dict:
    """
    Trigger a Full Refresh for the authenticated user.

    - Ignores every cache and TTL
    - Re-runs every available provider (Weather, Satellite, Market, ML)
    - Persists a versioned snapshot to MongoDB
    - Returns progress steps and provider status
    """
    user_id = current_user["_id"]
    try:
        from app.ai.refresh_engine import RefreshPolicyEngine

        result = await RefreshPolicyEngine.full_refresh(
            user_id=user_id,
            farm_id=payload.farm_id,
            field_id=payload.field_id,
        )
        return success_response(
            data=result,
            message="Full refresh completed successfully.",
        )
    except Exception as exc:
        logger.exception("Full refresh error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Refresh failed: {exc}",
        )


@router.get(
    "/status/{refresh_id}",
    summary="Get refresh progress",
    response_description="Current status of a refresh operation",
)
async def get_refresh_status(
    refresh_id: str,
    current_user: CurrentUser,
) -> dict:
    """Get the progress of an active or completed refresh."""
    from app.ai.refresh_engine import RefreshPolicyEngine

    status_data = RefreshPolicyEngine.get_refresh_status(refresh_id)
    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh ID not found.",
        )
    return success_response(data=status_data, message="Refresh status retrieved.")


@router.get(
    "/latest",
    summary="Get the latest refresh snapshot",
    response_description="Most recent versioned refresh snapshot",
)
async def get_latest_snapshot(
    current_user: CurrentUser,
) -> dict:
    """Return the most recent versioned refresh snapshot for the user."""
    user_id = current_user["_id"]
    try:
        from app.database import get_collection

        col = get_collection("refresh_snapshots")
        doc = await col.find_one(
            {"user_id": user_id},
            sort=[("version", -1)],
        )
        if doc:
            doc.pop("_id", None)
            return success_response(data=doc, message="Latest snapshot retrieved.")
        return success_response(data=None, message="No snapshots found.")
    except Exception as exc:
        logger.error("Failed to fetch latest snapshot: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch snapshot.",
        )
