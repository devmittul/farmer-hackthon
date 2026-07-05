"""
KrishiMitra Backend – SOS Route
==================================
POST /sos
"""
import logging

from fastapi import APIRouter, HTTPException, status

from app.auth.dependencies import OptionalUser
from app.schemas.requests import LanguageCode, SOSRequest
from app.schemas.responses import success_response
from app.services.sos_service import SOSService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Emergency SOS"])


@router.post(
    "/sos",
    summary="Send an emergency SOS alert",
    response_description="Alert ID, immediate guidance, and emergency contacts",
    status_code=status.HTTP_201_CREATED,
)
async def send_sos(
    payload: SOSRequest,
    current_user: OptionalUser,
) -> dict:
    """
    Send an emergency SOS alert.

    **Immediate Actions:**
    1. Alert persisted to MongoDB (priority: data safety first)
    2. Gemini generates context-aware emergency guidance
    3. Returns Indian emergency numbers + nearest help centre

    **Emergency Types:** fire | flood | accident | medical | general

    ⚠️ This system supplements but does NOT replace calling 112.
    Always call emergency services for life-threatening situations.
    """
    user_id = current_user["_id"] if current_user else None
    language = LanguageCode(current_user.get("language", "en")) if current_user else LanguageCode.EN

    try:
        result = await SOSService.create_alert(
            payload=payload,
            user_id=user_id,
            language=language,
        )
        return success_response(data=result, message="SOS alert received. Help is being coordinated.")
    except Exception as exc:
        logger.exception("SOS processing error")
        # Even on error, ensure we return something useful
        return success_response(
            data={
                "alert_id": "emergency",
                "message": "CALL 112 IMMEDIATELY for emergency help.",
                "emergency_contacts": ["112 – National Emergency", "108 – Ambulance"],
            },
            message="SOS alert logged. Please call 112.",
        )
