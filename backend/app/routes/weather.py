"""
KrishiMitra Backend – Weather Routes
=======================================
POST /weather
"""
import logging

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import OptionalUser
from app.schemas.requests import WeatherRequest
from app.schemas.responses import success_response
from app.services.weather_service import WeatherService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Weather Intelligence"])


@router.post(
    "/weather",
    summary="Get weather forecast with AI farming advisory",
    response_description="Current weather, forecast, and Gemini farming advisory",
)
async def get_weather(
    payload: WeatherRequest,
    current_user: OptionalUser,
) -> dict:
    """
    Get structured weather data + AI farming advisory.

    **Data Sources:**
    - Geocoding: Nominatim (OpenStreetMap) – no API key
    - Weather: Open-Meteo – no API key
    - Advisory: Gemini AI with verified weather context

    **Features:**
    - Cached in MongoDB (30-minute TTL)
    - Supports 1-7 day forecasts
    - Returns farming-specific advisories
    """
    try:
        result = await WeatherService.get_weather_with_advisory(payload)
        return success_response(data=result, message="Weather data retrieved.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.exception("Weather fetch error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve weather data. Please try again.",
        )
