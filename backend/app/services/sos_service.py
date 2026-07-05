"""
KrishiMitra Backend – SOS Service
=====================================
Emergency alert handling and persistence.
"""
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from app.ai.reasoning_engine import ReasoningEngine
from app.ai import prompt_builder
from app.database import get_collection
from app.schemas.requests import SOSRequest

logger = logging.getLogger(__name__)

# Emergency helpline numbers (India)
EMERGENCY_CONTACTS = [
    "112 – National Emergency Number",
    "1962 – Kisan Call Centre (Farmers Helpline)",
    "108 – Ambulance Service",
    "101 – Fire Service",
    "1800-180-1551 – PM-Kisan Helpline",
]


class SOSService:
    """Handles emergency SOS alerts."""

    @staticmethod
    async def create_alert(
        payload: SOSRequest,
        user_id: Optional[str] = None,
        language: Any = None,
    ) -> dict[str, Any]:
        """
        Persist an SOS alert and generate immediate guidance via Gemini.

        Args:
            payload: Validated SOS request.
            user_id: Optional authenticated user.
            language: LanguageCode for Gemini response.

        Returns:
            Alert ID, guidance, and emergency contacts.
        """
        from app.schemas.requests import LanguageCode

        lang = language or LanguageCode.EN
        location_str = f"Lat: {payload.latitude}, Lon: {payload.longitude}"

        # ── Persist to MongoDB first (non-blocking for user) ──────────────────
        col = get_collection("sos_alerts")
        doc = {
            "user_id": user_id,
            "latitude": payload.latitude,
            "longitude": payload.longitude,
            "description": payload.description,
            "emergency_type": payload.emergency_type,
            "contact_phone": payload.contact_phone,
            "status": "active",
            "created_at": datetime.now(UTC),
        }
        result = await col.insert_one(doc)
        alert_id = str(result.inserted_id)
        logger.warning("SOS alert created: %s | type=%s | %s", alert_id, payload.emergency_type, location_str)

        # ── Gemini Guidance ───────────────────────────────────────────────────
        prompt = prompt_builder.build_sos_prompt(
            language=lang,
            location_str=location_str,
            emergency_type=payload.emergency_type,
            description=payload.description,
        )

        try:
            guidance, _ = await ReasoningEngine.generate(prompt)
        except Exception as exc:
            logger.error("ReasoningEngine SOS guidance failed: %s", exc)
            guidance = (
                "EMERGENCY: Please call 112 immediately. Stay calm and stay safe. "
                "Help is on the way."
            )

        return {
            "alert_id": alert_id,
            "message": guidance,
            "nearest_help": _get_nearest_help(payload.emergency_type),
            "emergency_contacts": EMERGENCY_CONTACTS,
        }


def _get_nearest_help(emergency_type: str) -> str:
    """Map emergency type to the most relevant helpline."""
    mapping = {
        "fire": "101 – Fire Service",
        "medical": "108 – Ambulance",
        "flood": "112 – National Emergency",
        "accident": "112 + 108 – Emergency + Ambulance",
        "general": "112 – National Emergency Number",
    }
    return mapping.get(emergency_type.lower(), "112 – National Emergency Number")
