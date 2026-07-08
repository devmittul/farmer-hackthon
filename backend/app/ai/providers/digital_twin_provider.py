"""
Digital Twin Provider – loads Farmer/Farm/Field profiles from MongoDB.

Wraps the existing repository pattern. No database logic is duplicated.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.ai.providers import BaseProvider, FreshnessLevel

logger = logging.getLogger(__name__)


class DigitalTwinProvider(BaseProvider):
    name = "digital_twin"
    freshness = FreshnessLevel.PERMANENT
    default_ttl = 0  # Permanent: refreshes only on user edit

    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Load the complete Digital Twin (Farmer, Farm, Field) from MongoDB.

        Expected params:
            user_id (str): Authenticated user's MongoDB _id.
            field_id (str, optional): Specific field to load.
            farm_id (str, optional): Specific farm to load.
        """
        user_id = params.get("user_id")
        if not user_id:
            return None

        field_id = params.get("field_id")
        farm_id = params.get("farm_id")
        result: Dict[str, Any] = {}

        try:
            from app.database import get_collection
            from app.repositories import FarmRepository

            # ── Farmer profile ──────────────────────────────────────────────
            farmer_col = get_collection("farmer_profiles")
            farmer_doc = await farmer_col.find_one({"user_id": user_id})
            if farmer_doc:
                farmer_doc.pop("_id", None)
                result["farmer"] = farmer_doc

            # ── Farm (geo-aware, new system) ─────────────────────────────────
            farm_doc = None
            if farm_id:
                farm_doc = await FarmRepository.get(farm_id, user_id)
            if not farm_doc:
                farm_doc = await FarmRepository.get_any(user_id)

            if farm_doc:
                farm_doc.pop("_id", None)
                result["farm"] = farm_doc

                # Derive location from farm center coordinate
                center = farm_doc.get("center_coordinate") or {}
                if center.get("latitude"):
                    result["derived_location"] = f"{center['latitude']},{center['longitude']}"

            # ── Fallback location from farmer profile ────────────────────────
            if "derived_location" not in result and farmer_doc and farmer_doc.get("location"):
                result["derived_location"] = farmer_doc.get("location")

            # ── Field (if requested) ─────────────────────────────────────────
            if field_id:
                fields_col = get_collection("fields")
                from bson import ObjectId
                field_doc = None
                try:
                    field_doc = await fields_col.find_one(
                        {"_id": ObjectId(field_id), "ownerId": user_id}
                    )
                except Exception:
                    pass

                if not field_doc:
                    try:
                        field_doc = await fields_col.find_one(
                            {"_id": field_id, "ownerId": user_id}
                        )
                    except Exception:
                        pass

                if field_doc:
                    centroid_data = None
                    poly = field_doc.get("polygon") or {}
                    coords = poly.get("coordinates")
                    if coords:
                        from app.utils.geo import polygon_centroid
                        centroid_data = polygon_centroid(coords)

                    result["field"] = {
                        "field_id": str(field_doc["_id"]),
                        "name": field_doc.get("fieldName"),
                        "soil_ph": field_doc.get("soil_ph", 6.5),
                        "nitrogen_kg_ha": field_doc.get("nitrogen_kg_ha", 40),
                        "area_ha": field_doc.get("areaHectare", 1.0),
                        "centroid": centroid_data or {"latitude": 0.0, "longitude": 0.0},
                    }
                    if centroid_data and centroid_data.get("latitude"):
                        result["derived_location"] = f"{centroid_data['latitude']},{centroid_data['longitude']}"
                else:
                    # Fallback to legacy field_profiles
                    field_col = get_collection("field_profiles")
                    field_doc = await field_col.find_one(
                        {"field_id": field_id, "user_id": user_id}
                    )
                    if field_doc:
                        field_doc.pop("_id", None)
                        result["field"] = field_doc
                        centroid = field_doc.get("centroid") or {}
                        if centroid.get("latitude"):
                            result["derived_location"] = f"{centroid['latitude']},{centroid['longitude']}"

            return result if result else None

        except Exception as exc:
            logger.error("DigitalTwinProvider: %s", exc)
            return None
