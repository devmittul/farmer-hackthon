"""
KrishiMitra Backend – Courier Routes
=======================================
POST /courier/create
GET  /courier/list
"""
import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.auth.dependencies import OptionalUser
from app.schemas.requests import CourierCreateRequest
from app.schemas.responses import success_response
from app.services.courier_service import CourierService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courier", tags=["Community Courier"])


@router.post(
    "/create",
    summary="Post a new community courier request",
    response_description="Courier request ID and confirmation",
    status_code=status.HTTP_201_CREATED,
)
async def create_courier(
    payload: CourierCreateRequest,
    current_user: OptionalUser,
) -> dict:
    """
    Create a community courier request for transporting agricultural goods.

    Farmers post pickup/delivery requests that local drivers can accept.
    Requests are stored and visible to potential drivers in the area.
    """
    user_id = current_user["_id"] if current_user else None

    try:
        result = await CourierService.create_request(payload, user_id=user_id)
        return success_response(data=result, message="Courier request posted.")
    except Exception as exc:
        logger.exception("Courier create error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create courier request.",
        )


@router.get(
    "/list",
    summary="List available courier requests",
    response_description="Paginated list of courier requests",
)
async def list_couriers(
    current_user: OptionalUser,
    status_filter: str = Query(default=None, alias="status", description="Filter by status"),
    limit: int = Query(default=20, ge=1, le=50),
    skip: int = Query(default=0, ge=0),
) -> dict:
    """
    List community courier requests with optional status filtering.

    Supports pagination via `limit` and `skip` query parameters.
    Status values: pending | accepted | in_transit | delivered | cancelled
    """
    try:
        results = await CourierService.list_requests(
            status=status_filter,
            limit=limit,
            skip=skip,
        )
        return success_response(
            data=results,
            message=f"{len(results)} courier requests found.",
            metadata={"limit": limit, "skip": skip},
        )
    except Exception as exc:
        logger.exception("Courier list error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch courier requests.",
        )
