"""
KrishiMitra Backend – Digital Twin Routes
==========================================
REST endpoints for managing the farmer's Digital Twin:

  Farmer Profile
  GET  /twin/farmer          → Load my Digital Twin summary
  PUT  /twin/farmer          → Update profile (language, location, etc.)

  Farm Management
  GET  /twin/farms           → List my farms
  POST /twin/farms           → Create a new farm
  GET  /twin/farms/{farm_id} → Get a specific farm

  Field Management
  GET  /twin/fields          → List all my fields
  POST /twin/fields          → Register a new field
  GET  /twin/fields/{field_id}           → Get a specific field
  PATCH /twin/fields/{field_id}          → Update field (soil, crop, etc.)
  POST  /twin/fields/{field_id}/harvest  → Record a harvest event
  GET   /twin/fields/{field_id}/satellite → Get latest satellite reading

Authentication required on all endpoints.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import CurrentUser
from app.repositories import (
    FarmProfileRepository,
    FarmerProfileRepository,
    FieldProfileRepository,
)
from app.schemas.requests import LanguageCode
from app.schemas.responses import success_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twin", tags=["Digital Twin"])


# ── Request Bodies ────────────────────────────────────────────────────────────

class FarmerProfileUpdate(BaseModel):
    preferred_language: Optional[LanguageCode] = None
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    preferred_units: Optional[str] = None
    gps_home: Optional[Dict[str, float]] = Field(
        default=None,
        description='{"latitude": 23.0, "longitude": 72.5}'
    )


class FarmCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    total_area_ha: Optional[float] = Field(default=None, gt=0)
    primary_crops: Optional[list[str]] = None


class FieldCreateRequest(BaseModel):
    farm_id: str = Field(..., description="Parent farm ID")
    name: Optional[str] = Field(default=None, max_length=100)
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    area_ha: Optional[float] = Field(default=None, gt=0)

    # GPS
    centroid_lat: Optional[float] = Field(default=None, ge=-90, le=90)
    centroid_lon: Optional[float] = Field(default=None, ge=-180, le=180)

    # Soil
    soil_type: Optional[str] = None
    soil_ph: Optional[float] = Field(default=None, ge=0, le=14)
    nitrogen_kg_ha: Optional[float] = Field(default=None, ge=0)
    phosphorus_kg_ha: Optional[float] = Field(default=None, ge=0)
    potassium_kg_ha: Optional[float] = Field(default=None, ge=0)

    # Irrigation
    irrigation_type: Optional[str] = None
    water_source: Optional[str] = None

    # Current crop
    current_crop: Optional[str] = None
    current_variety: Optional[str] = None
    sowing_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    expected_harvest_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")


class FieldUpdateRequest(BaseModel):
    name: Optional[str] = None
    soil_type: Optional[str] = None
    soil_ph: Optional[float] = Field(default=None, ge=0, le=14)
    nitrogen_kg_ha: Optional[float] = Field(default=None, ge=0)
    phosphorus_kg_ha: Optional[float] = Field(default=None, ge=0)
    potassium_kg_ha: Optional[float] = Field(default=None, ge=0)
    irrigation_type: Optional[str] = None
    water_source: Optional[str] = None
    current_crop: Optional[str] = None
    current_variety: Optional[str] = None
    sowing_date: Optional[str] = None
    expected_harvest_date: Optional[str] = None
    growth_stage: Optional[str] = None


class HarvestRecordRequest(BaseModel):
    season: str = Field(..., description="e.g. Kharif 2025")
    crop: str
    variety: Optional[str] = None
    yield_kg_per_ha: Optional[float] = Field(default=None, gt=0)
    total_yield_kg: Optional[float] = Field(default=None, gt=0)
    harvest_date: Optional[str] = Field(default=None, description="YYYY-MM-DD")
    notes: Optional[str] = None


# ── Farmer Profile Endpoints ──────────────────────────────────────────────────

@router.get(
    "/farmer",
    summary="Get my Digital Twin farmer profile",
)
async def get_farmer_profile(current_user: CurrentUser) -> dict:
    """
    Load the authenticated farmer's complete Digital Twin profile.

    Returns profile including:
    - Identity and location
    - Language preference
    - Farm and field lists
    - Recent crop prediction history
    """
    user_id = current_user["_id"]
    profile = await FarmerProfileRepository.get_by_user_id(user_id)

    if not profile:
        # Auto-create a minimal profile from the user record
        profile = await FarmerProfileRepository.upsert(user_id, {
            "name": current_user.get("name", ""),
            "phone": current_user.get("phone"),
            "preferred_language": current_user.get("language", "en"),
            "village": current_user.get("location"),
            "farm_ids": [],
            "field_ids": [],
        })

    return success_response(
        data=profile,
        message="Farmer profile loaded.",
    )


@router.put(
    "/farmer",
    summary="Update my farmer profile",
)
async def update_farmer_profile(
    payload: FarmerProfileUpdate,
    current_user: CurrentUser,
) -> dict:
    """Update language, location, GPS, or unit preferences."""
    user_id = current_user["_id"]
    updates: Dict[str, Any] = {
        k: v for k, v in payload.model_dump().items() if v is not None
    }

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )

    profile = await FarmerProfileRepository.upsert(user_id, updates)
    return success_response(data=profile, message="Profile updated.")


# ── Farm Endpoints ────────────────────────────────────────────────────────────

@router.get("/farms", summary="List my farms")
async def list_farms(current_user: CurrentUser) -> dict:
    """Return all farms owned by the authenticated user."""
    user_id = current_user["_id"]
    farms = await FarmProfileRepository.list_for_user(user_id)
    return success_response(
        data=farms,
        message=f"{len(farms)} farms found.",
        metadata={"total": len(farms)},
    )


@router.post("/farms", summary="Register a new farm")
async def create_farm(
    payload: FarmCreateRequest,
    current_user: CurrentUser,
) -> dict:
    """
    Create a new farm record and link it to the farmer's Digital Twin.

    Auto-generates a unique farm_id (UUID).
    """
    user_id = current_user["_id"]
    farm_id = str(uuid.uuid4())

    farm_data: Dict[str, Any] = {
        "farm_id": farm_id,
        "user_id": user_id,
        "name": payload.name,
        "village": payload.village,
        "district": payload.district,
        "state": payload.state,
        "total_area_ha": payload.total_area_ha,
        "primary_crops": payload.primary_crops or [],
        "field_ids": [],
    }

    farm = await FarmProfileRepository.create(farm_data)
    # Link farm to farmer profile
    await FarmerProfileRepository.add_farm_id(user_id, farm_id)

    logger.info("Farm created: %s for user=%s", farm_id, user_id)
    return success_response(data=farm, message="Farm registered.")


@router.get("/farms/{farm_id}", summary="Get a specific farm")
async def get_farm(farm_id: str, current_user: CurrentUser) -> dict:
    """Return a single farm with all its field IDs."""
    user_id = current_user["_id"]
    farm = await FarmProfileRepository.get(farm_id, user_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm '{farm_id}' not found.",
        )

    # Also load the associated fields
    fields = await FieldProfileRepository.list_for_farm(farm_id)

    return success_response(
        data={"farm": farm, "fields": fields},
        message="Farm loaded.",
    )


# ── Field Endpoints ───────────────────────────────────────────────────────────

@router.get("/fields", summary="List all my fields")
async def list_fields(current_user: CurrentUser) -> dict:
    """Return all fields owned by the authenticated user."""
    user_id = current_user["_id"]
    fields = await FieldProfileRepository.list_for_user(user_id)
    return success_response(
        data=fields,
        message=f"{len(fields)} fields found.",
        metadata={"total": len(fields)},
    )


@router.post("/fields", summary="Register a new field")
async def create_field(
    payload: FieldCreateRequest,
    current_user: CurrentUser,
) -> dict:
    """
    Register a new agricultural field and link it to a farm and farmer.

    Auto-generates a unique field_id (UUID).
    Centroid lat/lon are used by ContextBuilder for weather + satellite queries.
    """
    user_id = current_user["_id"]

    # Verify the farm exists and belongs to this user
    farm = await FarmProfileRepository.get(payload.farm_id, user_id)
    if not farm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farm '{payload.farm_id}' not found.",
        )

    field_id = str(uuid.uuid4())

    centroid = None
    if payload.centroid_lat is not None and payload.centroid_lon is not None:
        centroid = {
            "latitude": payload.centroid_lat,
            "longitude": payload.centroid_lon,
        }

    field_data: Dict[str, Any] = {
        "field_id": field_id,
        "farm_id": payload.farm_id,
        "user_id": user_id,
        "name": payload.name,
        "village": payload.village,
        "district": payload.district,
        "state": payload.state,
        "area_ha": payload.area_ha,
        "centroid": centroid,
        # Soil
        "soil_type": payload.soil_type,
        "soil_ph": payload.soil_ph,
        "nitrogen_kg_ha": payload.nitrogen_kg_ha,
        "phosphorus_kg_ha": payload.phosphorus_kg_ha,
        "potassium_kg_ha": payload.potassium_kg_ha,
        # Irrigation
        "irrigation_type": payload.irrigation_type,
        "water_source": payload.water_source,
        # Current crop
        "current_crop": payload.current_crop,
        "current_variety": payload.current_variety,
        "sowing_date": payload.sowing_date,
        "expected_harvest_date": payload.expected_harvest_date,
        # History
        "harvest_history": [],
        "disease_history": [],
        "irrigation_history": [],
        "market_history": [],
        "satellite_history": [],
        "latest_satellite": None,
    }

    field = await FieldProfileRepository.create(field_data)

    # Link field to farm and farmer
    await FarmProfileRepository.add_field_id(payload.farm_id, field_id)
    await FarmerProfileRepository.add_field_id(user_id, field_id)

    logger.info("Field created: %s for user=%s farm=%s", field_id, user_id, payload.farm_id)
    return success_response(data=field, message="Field registered.")


@router.get("/fields/{field_id}", summary="Get a specific field")
async def get_field(field_id: str, current_user: CurrentUser) -> dict:
    """Return a single field's full Digital Twin data."""
    user_id = current_user["_id"]
    field = await FieldProfileRepository.get(field_id, user_id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_id}' not found.",
        )
    return success_response(data=field, message="Field loaded.")


@router.patch("/fields/{field_id}", summary="Update field data")
async def update_field(
    field_id: str,
    payload: FieldUpdateRequest,
    current_user: CurrentUser,
) -> dict:
    """
    Update soil data, crop information, or irrigation type for a field.
    Only provided fields are updated (PATCH semantics).
    """
    user_id = current_user["_id"]
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields provided to update.",
        )

    field = await FieldProfileRepository.update(field_id, user_id, updates)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_id}' not found.",
        )
    return success_response(data=field, message="Field updated.")


@router.post("/fields/{field_id}/harvest", summary="Record a harvest event")
async def record_harvest(
    field_id: str,
    payload: HarvestRecordRequest,
    current_user: CurrentUser,
) -> dict:
    """
    Append a harvest record to the field's history.
    This permanently updates the field's Digital Twin with yield data.
    """
    user_id = current_user["_id"]

    # Verify field ownership
    field = await FieldProfileRepository.get(field_id, user_id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_id}' not found.",
        )

    record = payload.model_dump()
    await FieldProfileRepository.push_harvest_record(field_id, user_id, record)

    logger.info(
        "Harvest recorded: field=%s crop=%s yield=%.1f kg/ha",
        field_id, payload.crop, payload.yield_kg_per_ha or 0,
    )
    return success_response(
        data={"field_id": field_id, "record": record},
        message="Harvest recorded successfully.",
    )


@router.get("/fields/{field_id}/satellite", summary="Get latest satellite data")
async def get_field_satellite(field_id: str, current_user: CurrentUser) -> dict:
    """
    Return the latest satellite snapshot (NDVI, crop health) for this field.
    Triggers a fresh GEE fetch if the field has GPS coordinates.
    """
    user_id = current_user["_id"]
    field = await FieldProfileRepository.get(field_id, user_id)
    if not field:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Field '{field_id}' not found.",
        )

    centroid = field.get("centroid")
    if not centroid:
        return success_response(
            data={"message": "No GPS centroid on record. Add lat/lon to enable satellite."},
            message="Satellite unavailable – no GPS.",
        )

    # Trigger live GEE fetch
    try:
        from app.ai.satellite.service import get_ndvi
        sat = await get_ndvi(
            latitude=centroid["latitude"],
            longitude=centroid["longitude"],
            location_name=field.get("name") or field_id,
        )

        if sat and sat.get("ndvi") is not None:
            # Persist snapshot back to field
            snapshot = {
                "captured_at": sat.get("analysis_date"),
                "ndvi": sat.get("ndvi"),
                "crop_health": sat.get("crop_health"),
                "vegetation_index": sat.get("vegetation_index"),
                "harvest_stage": sat.get("harvest_detection"),
                "data_source": sat.get("data_source"),
            }
            await FieldProfileRepository.update_satellite(field_id, snapshot)

        return success_response(
            data=sat,
            message="Satellite data refreshed.",
        )
    except Exception as exc:
        logger.error("Satellite fetch failed for field=%s: %s", field_id, exc)
        return success_response(
            data=field.get("latest_satellite"),
            message="Using cached satellite data.",
        )
