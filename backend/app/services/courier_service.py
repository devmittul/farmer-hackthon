"""
KrishiMitra Backend – Courier Service
=======================================
Business logic for community courier requests.
"""
import logging
from datetime import UTC, datetime
from typing import Any, List, Optional

from bson import ObjectId

from app.database import get_collection
from app.schemas.requests import CourierCreateRequest

logger = logging.getLogger(__name__)


class CourierService:
    """Handles community courier request creation and listing."""

    @staticmethod
    async def create_request(
        payload: CourierCreateRequest,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new courier request in MongoDB.

        Args:
            payload: Validated courier creation request.
            user_id: Optional authenticated user ID.

        Returns:
            Dict with the created request ID and details.
        """
        col = get_collection("courier_requests")
        now = datetime.now(UTC)

        doc = {
            "user_id": user_id,
            "pickup_location": payload.pickup_location,
            "delivery_location": payload.delivery_location,
            "cargo_description": payload.cargo_description,
            "weight_kg": payload.weight_kg,
            "preferred_date": payload.preferred_date,
            "contact_phone": payload.contact_phone,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
        }

        result = await col.insert_one(doc)
        request_id = str(result.inserted_id)
        logger.info("Courier request created: %s", request_id)

        return {
            "id": request_id,
            "pickup_location": payload.pickup_location,
            "delivery_location": payload.delivery_location,
            "cargo_description": payload.cargo_description,
            "weight_kg": payload.weight_kg,
            "preferred_date": payload.preferred_date,
            "status": "pending",
            "created_at": now.isoformat(),
            "message": "Your courier request has been posted. Drivers in the area will be notified.",
        }

    @staticmethod
    async def list_requests(
        status: Optional[str] = None,
        limit: int = 20,
        skip: int = 0,
    ) -> List[dict[str, Any]]:
        """
        List courier requests with optional status filter.

        Args:
            status: Optional filter (pending/accepted/in_transit/delivered).
            limit: Page size (max 50).
            skip: Pagination offset.

        Returns:
            List of courier request dicts.
        """
        col = get_collection("courier_requests")
        query: dict[str, Any] = {}
        if status:
            query["status"] = status

        limit = min(limit, 50)
        cursor = col.find(query).sort("created_at", -1).skip(skip).limit(limit)

        results = []
        async for doc in cursor:
            results.append(
                {
                    "id": str(doc["_id"]),
                    "pickup_location": doc["pickup_location"],
                    "delivery_location": doc["delivery_location"],
                    "cargo_description": doc["cargo_description"],
                    "weight_kg": doc["weight_kg"],
                    "preferred_date": doc["preferred_date"],
                    "status": doc["status"],
                    "created_at": doc["created_at"].isoformat()
                    if hasattr(doc.get("created_at"), "isoformat")
                    else str(doc.get("created_at")),
                }
            )

        return results

    @staticmethod
    async def update_status(
        request_id: str,
        new_status: str,
    ) -> bool:
        """Update the status of a courier request."""
        col = get_collection("courier_requests")
        try:
            result = await col.update_one(
                {"_id": ObjectId(request_id)},
                {"$set": {"status": new_status, "updated_at": datetime.now(UTC)}},
            )
            return result.modified_count > 0
        except Exception as exc:
            logger.error("Failed to update courier status: %s", exc)
            return False
