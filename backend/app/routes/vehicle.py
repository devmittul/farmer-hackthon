"""
KrishiMitra Backend – Vehicle Routes
=======================================
POST /vehicle/predict
"""
import logging

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import OptionalUser
from app.schemas.requests import VehiclePredictRequest
from app.schemas.responses import success_response
from app.services.vehicle_service import VehicleService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vehicle", tags=["Vehicle Demand"])


@router.post(
    "/predict",
    summary="Predict vehicle demand for crop transport",
    response_description="Demand level, recommended vehicles, cost estimate",
)
async def predict_vehicle(
    payload: VehiclePredictRequest,
    current_user: OptionalUser,
) -> dict:
    """
    Predict vehicle demand for transporting agricultural produce.

    **Pipeline:**
    1. Validate cargo, quantity, origin, destination, date
    2. Run scikit-learn GradientBoosting prediction
    3. Pass prediction to Gemini for logistics advisory
    4. Return demand level, vehicle types, cost range, best time window
    """
    user_id = current_user["_id"] if current_user else None

    try:
        result = await VehicleService.predict_and_explain(payload, user_id=user_id)
        return success_response(data=result, message="Vehicle demand prediction generated.")
    except Exception as exc:
        logger.exception("Vehicle prediction error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vehicle prediction failed. Please try again.",
        )
