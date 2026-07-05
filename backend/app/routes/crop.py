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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/crop", tags=["Crop Recommendation"])


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
