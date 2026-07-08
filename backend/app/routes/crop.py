"""
KrishiMitra Backend – Crop Routes
====================================
POST /crop/predict
"""
import logging

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import OptionalUser
from app.schemas.requests import CropPredictRequest
from app.schemas.responses import success_response
from app.services.crop_service import CropService
from app.ai.weather.service import geocode_location
from app.ai.providers.geesoil_provider import GEESoilProvider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crop", tags=["Crop Recommendation"])


@router.get(
    "/soil",
    summary="Get soil pH based on location",
    response_description="Soil pH and texture from Google Earth Engine",
)
async def get_soil_by_location(location: str) -> dict:
    """Geocodes location and fetches GEE soil profile."""
    coords = await geocode_location(location)
    if not coords:
        raise HTTPException(status_code=404, detail="Location not found")
        
    lat, lon = coords
    provider = GEESoilProvider()
    res = await provider.execute({
        "latitude": lat,
        "longitude": lon,
        "location_name": location,
        "boundary": None
    })
    
    if not res.available or not res.data:
        raise HTTPException(status_code=404, detail="Soil data unavailable")
        
    return success_response(data=res.data, message="Soil data fetched")


@router.post(
    "/predict",
    summary="Get AI-powered crop recommendation",
    response_description="Recommended crop with confidence and Gemini explanation",
)
async def predict_crop(
    payload: CropPredictRequest,
    current_user: OptionalUser,
) -> dict:
    """
    Predict the best crop for given soil and climate conditions.

    **Pipeline:**
    1. Validate soil NPK, temperature, humidity, pH, rainfall
    2. Run scikit-learn RandomForest prediction
    3. Pass ML output to Gemini for farmer-friendly explanation
    4. Return crop name, confidence, alternatives, tips

    Authentication optional – predictions stored with user ID if logged in.
    """
    user_id = current_user["_id"] if current_user else None

    try:
        result = await CropService.predict_and_explain(payload, user_id=user_id)
        return success_response(data=result, message="Crop recommendation generated.")
    except Exception as exc:
        logger.exception("Crop prediction error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Crop prediction failed. Please try again.",
        )
