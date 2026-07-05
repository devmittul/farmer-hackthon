"""
KrishiMitra Backend – Route Planning Routes
============================================
POST /route/plan
"""
import logging

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import OptionalUser
from app.schemas.requests import RoutePlanRequest
from app.schemas.responses import success_response
from app.services.route_service import RouteService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/route", tags=["Route Planning"])


@router.post(
    "/plan",
    summary="Plan a transport route with AI advisory",
    response_description="Route steps, distance, ETA, weather advisory",
)
async def plan_route(
    payload: RoutePlanRequest,
    current_user: OptionalUser,
) -> dict:
    """
    Plan an optimal transport route for agricultural produce.

    **Pipeline:**
    1. Geocode origin + destination via Nominatim (OpenStreetMap)
    2. Compute route via OSRM (open-source routing)
    3. Fetch weather for origin via Open-Meteo
    4. Build combined prompt → Gemini route advisory
    5. Return steps, distance, ETA, weather advisory

    No Google Maps. No paid APIs.
    """
    user_id = current_user["_id"] if current_user else None

    try:
        result = await RouteService.plan_and_explain(payload, user_id=user_id)
        return success_response(data=result, message="Route planned successfully.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Route planning error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route planning failed. Please try again.",
        )
