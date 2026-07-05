"""
KrishiMitra Backend – Repository Layer
========================================
Clean data-access abstractions for all MongoDB collections.

The Repository Pattern isolates MongoDB operations from business logic.
Services call repositories; repositories call MongoDB.  This makes
testing trivial (mock the repository, not the DB client).

Each repository:
  • Has typed input/output (Pydantic models or plain dicts)
  • Handles ObjectId ↔ str conversion
  • Never raises outside its own error boundary
  • Is fully async

Collections covered:
  FarmerProfileRepository  →  farmer_profiles
  FarmProfileRepository    →  farm_profiles
  FieldProfileRepository   →  field_profiles
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.database import get_collection

logger = logging.getLogger(__name__)


def _str_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB _id ObjectId to string, remove from doc."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ── FarmerProfile Repository ──────────────────────────────────────────────────

class FarmerProfileRepository:
    """CRUD operations for farmer_profiles collection."""

    _COL = "farmer_profiles"

    @classmethod
    async def get_by_user_id(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """Return the farmer profile for a given user_id, or None."""
        try:
            col = get_collection(cls._COL)
            doc = await col.find_one({"user_id": user_id})
            return _str_id(doc) if doc else None
        except Exception as exc:
            logger.error("FarmerProfileRepo.get_by_user_id: %s", exc)
            return None

    @classmethod
    async def upsert(cls, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create or update the farmer profile for user_id.
        Returns the complete updated document.
        """
        try:
            col = get_collection(cls._COL)
            data.update({
                "user_id": user_id,
                "updated_at": datetime.now(UTC),
            })
            data.setdefault("created_at", datetime.now(UTC))

            result = await col.find_one_and_update(
                {"user_id": user_id},
                {"$set": data},
                upsert=True,
                return_document=True,
            )
            return _str_id(result)
        except Exception as exc:
            logger.error("FarmerProfileRepo.upsert: %s", exc)
            raise

    @classmethod
    async def add_farm_id(cls, user_id: str, farm_id: str) -> None:
        """Append a farm_id to the farmer's farm_ids list (idempotent)."""
        try:
            col = get_collection(cls._COL)
            await col.update_one(
                {"user_id": user_id},
                {
                    "$addToSet": {"farm_ids": farm_id},
                    "$set": {"updated_at": datetime.now(UTC)},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error("FarmerProfileRepo.add_farm_id: %s", exc)

    @classmethod
    async def add_field_id(cls, user_id: str, field_id: str) -> None:
        """Append a field_id to the farmer's field_ids list (idempotent)."""
        try:
            col = get_collection(cls._COL)
            await col.update_one(
                {"user_id": user_id},
                {
                    "$addToSet": {"field_ids": field_id},
                    "$set": {"updated_at": datetime.now(UTC)},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error("FarmerProfileRepo.add_field_id: %s", exc)

    @classmethod
    async def push_crop_prediction(
        cls, user_id: str, prediction: Dict[str, Any]
    ) -> None:
        """Keep the last 10 crop predictions inline for fast reads."""
        try:
            col = get_collection(cls._COL)
            await col.update_one(
                {"user_id": user_id},
                {
                    "$push": {
                        "recent_crop_predictions": {
                            "$each": [prediction],
                            "$slice": -10,
                        }
                    },
                    "$set": {"updated_at": datetime.now(UTC)},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error("FarmerProfileRepo.push_crop_prediction: %s", exc)


# ── FarmProfile Repository ────────────────────────────────────────────────────

class FarmProfileRepository:
    """CRUD operations for farm_profiles collection."""

    _COL = "farm_profiles"

    @classmethod
    async def get(cls, farm_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Return a farm profile owned by user_id, or None."""
        try:
            col = get_collection(cls._COL)
            doc = await col.find_one({"farm_id": farm_id, "user_id": user_id})
            return _str_id(doc) if doc else None
        except Exception as exc:
            logger.error("FarmProfileRepo.get: %s", exc)
            return None

    @classmethod
    async def list_for_user(cls, user_id: str) -> List[Dict[str, Any]]:
        """Return all farms owned by user_id."""
        try:
            col = get_collection(cls._COL)
            cursor = col.find({"user_id": user_id})
            return [_str_id(doc) async for doc in cursor]
        except Exception as exc:
            logger.error("FarmProfileRepo.list_for_user: %s", exc)
            return []

    @classmethod
    async def create(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new farm document and return it."""
        try:
            col = get_collection(cls._COL)
            data.setdefault("created_at", datetime.now(UTC))
            data.setdefault("updated_at", datetime.now(UTC))
            result = await col.insert_one(data)
            data["_id"] = str(result.inserted_id)
            return data
        except Exception as exc:
            logger.error("FarmProfileRepo.create: %s", exc)
            raise

    @classmethod
    async def update(
        cls, farm_id: str, user_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Patch a farm document. Returns updated doc or None."""
        try:
            col = get_collection(cls._COL)
            updates["updated_at"] = datetime.now(UTC)
            doc = await col.find_one_and_update(
                {"farm_id": farm_id, "user_id": user_id},
                {"$set": updates},
                return_document=True,
            )
            return _str_id(doc) if doc else None
        except Exception as exc:
            logger.error("FarmProfileRepo.update: %s", exc)
            return None

    @classmethod
    async def add_field_id(cls, farm_id: str, field_id: str) -> None:
        """Append a field_id to the farm's field_ids list (idempotent)."""
        try:
            col = get_collection(cls._COL)
            await col.update_one(
                {"farm_id": farm_id},
                {
                    "$addToSet": {"field_ids": field_id},
                    "$set": {"updated_at": datetime.now(UTC)},
                },
            )
        except Exception as exc:
            logger.error("FarmProfileRepo.add_field_id: %s", exc)


# ── FieldProfile Repository ───────────────────────────────────────────────────

class FieldProfileRepository:
    """CRUD operations for field_profiles collection."""

    _COL = "field_profiles"

    @classmethod
    async def get(cls, field_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Return a field owned by user_id, or None."""
        try:
            col = get_collection(cls._COL)
            doc = await col.find_one({"field_id": field_id, "user_id": user_id})
            return _str_id(doc) if doc else None
        except Exception as exc:
            logger.error("FieldProfileRepo.get: %s", exc)
            return None

    @classmethod
    async def list_for_user(cls, user_id: str) -> List[Dict[str, Any]]:
        """Return all fields owned by user_id."""
        try:
            col = get_collection(cls._COL)
            cursor = col.find({"user_id": user_id})
            return [_str_id(doc) async for doc in cursor]
        except Exception as exc:
            logger.error("FieldProfileRepo.list_for_user: %s", exc)
            return []

    @classmethod
    async def list_for_farm(cls, farm_id: str) -> List[Dict[str, Any]]:
        """Return all fields belonging to a farm."""
        try:
            col = get_collection(cls._COL)
            cursor = col.find({"farm_id": farm_id})
            return [_str_id(doc) async for doc in cursor]
        except Exception as exc:
            logger.error("FieldProfileRepo.list_for_farm: %s", exc)
            return []

    @classmethod
    async def create(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new field document and return it."""
        try:
            col = get_collection(cls._COL)
            data.setdefault("created_at", datetime.now(UTC))
            data.setdefault("updated_at", datetime.now(UTC))
            result = await col.insert_one(data)
            data["_id"] = str(result.inserted_id)
            return data
        except Exception as exc:
            logger.error("FieldProfileRepo.create: %s", exc)
            raise

    @classmethod
    async def update(
        cls, field_id: str, user_id: str, updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Patch a field document. Returns updated doc or None."""
        try:
            col = get_collection(cls._COL)
            updates["updated_at"] = datetime.now(UTC)
            doc = await col.find_one_and_update(
                {"field_id": field_id, "user_id": user_id},
                {"$set": updates},
                return_document=True,
            )
            return _str_id(doc) if doc else None
        except Exception as exc:
            logger.error("FieldProfileRepo.update: %s", exc)
            return None

    @classmethod
    async def update_satellite(
        cls, field_id: str, snapshot: Dict[str, Any]
    ) -> None:
        """
        Upsert latest satellite snapshot and append to history.
        Called by the satellite service after each GEE run.
        """
        try:
            col = get_collection(cls._COL)
            await col.update_one(
                {"field_id": field_id},
                {
                    "$set": {
                        "latest_satellite": snapshot,
                        "updated_at": datetime.now(UTC),
                    },
                    "$push": {
                        "satellite_history": {
                            "$each": [snapshot],
                            "$slice": -24,  # Keep last 24 readings
                        }
                    },
                },
            )
        except Exception as exc:
            logger.error("FieldProfileRepo.update_satellite: %s", exc)

    @classmethod
    async def push_harvest_record(
        cls, field_id: str, user_id: str, record: Dict[str, Any]
    ) -> None:
        """Append a harvest record to the field's harvest_history."""
        try:
            col = get_collection(cls._COL)
            await col.update_one(
                {"field_id": field_id, "user_id": user_id},
                {
                    "$push": {"harvest_history": record},
                    "$set": {"updated_at": datetime.now(UTC)},
                },
            )
        except Exception as exc:
            logger.error("FieldProfileRepo.push_harvest_record: %s", exc)
