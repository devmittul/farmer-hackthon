"""
KrishiMitra Backend – Database Index Manager
=============================================
Creates all compound indexes required for production performance.

Indexes are created idempotently (CREATE IF NOT EXISTS) via motor.
This module is called once at application startup.

Index design principles:
  - Every query pattern has a covering index
  - Compound indexes ordered by (equality → sort → range)
  - TTL indexes for auto-expiry of weather cache and sessions
  - Unique indexes where data integrity requires it

Collections & their query patterns:
  users              → email lookup, phone lookup
  chat_history       → user + created_at (pagination)
  crop_predictions   → user + created_at
  vehicle_predictions→ user + created_at
  routes             → user + created_at
  sos_alerts         → status + created_at (admin view)
  weather_cache      → cache_key (exact lookup) + expires_at (TTL)
  satellite_data     → location + processed_at
  farmer_profiles    → user_id (unique)
  farm_profiles      → user_id + farm_id
  field_profiles     → user_id + field_id, farm_id + field_id
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from pymongo import ASCENDING, DESCENDING, TEXT, IndexModel

from app.database import get_database

logger = logging.getLogger(__name__)

# ── Index definitions ────────────────────────────────────────────────────────
# Format: { "collection": [ IndexModel(...), ... ] }

INDEXES: Dict[str, List[IndexModel]] = {

    # ── Users ──────────────────────────────────────────────────────────────────
    "users": [
        IndexModel([("email", ASCENDING)], unique=True, name="unique_email"),
        IndexModel([("phone", ASCENDING)], name="idx_phone"),
        IndexModel([("is_active", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_active_created"),
    ],

    # ── Chat History ──────────────────────────────────────────────────────────
    "chat_history": [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_user_created"),
        IndexModel([("session_id", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_session_created"),
        IndexModel([("user_id", ASCENDING), ("intent", ASCENDING)],
                   name="idx_user_intent"),
        # Auto-delete chat history older than 180 days
        IndexModel([("created_at", ASCENDING)],
                   expireAfterSeconds=15_552_000,
                   name="ttl_chat_180d"),
    ],

    # ── Crop Predictions ──────────────────────────────────────────────────────
    "crop_predictions": [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_user_created"),
        IndexModel([("recommended_crop", ASCENDING)], name="idx_crop"),
    ],

    # ── Vehicle Predictions ───────────────────────────────────────────────────
    "vehicle_predictions": [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_user_created"),
    ],

    # ── Routes ────────────────────────────────────────────────────────────────
    "routes": [
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_user_created"),
        IndexModel([("origin", ASCENDING), ("destination", ASCENDING)],
                   name="idx_origin_dest"),
    ],

    # ── Courier Requests ──────────────────────────────────────────────────────
    "courier_requests": [
        IndexModel([("user_id", ASCENDING), ("status", ASCENDING)],
                   name="idx_user_status"),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_status_created"),
    ],

    # ── SOS Alerts ────────────────────────────────────────────────────────────
    "sos_alerts": [
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_status_created"),
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)],
                   name="idx_user_created"),
    ],

    # ── Weather Cache ─────────────────────────────────────────────────────────
    "weather_cache": [
        IndexModel([("cache_key", ASCENDING)], unique=True, name="unique_cache_key"),
        # Auto-delete expired cache entries
        IndexModel([("expires_at", ASCENDING)],
                   expireAfterSeconds=0,
                   name="ttl_expires_at"),
    ],

    # ── Satellite Data ────────────────────────────────────────────────────────
    "satellite_data": [
        IndexModel([("location", ASCENDING), ("processed_at", DESCENDING)],
                   name="idx_location_date"),
    ],

    # ── Digital Twin: Farmer Profiles ─────────────────────────────────────────
    "farmer_profiles": [
        IndexModel([("user_id", ASCENDING)], unique=True, name="unique_user_id"),
        IndexModel([("district", ASCENDING), ("state", ASCENDING)],
                   name="idx_district_state"),
    ],

    # ── Digital Twin: Farm Profiles ───────────────────────────────────────────
    "farm_profiles": [
        IndexModel([("farm_id", ASCENDING)], unique=True, name="unique_farm_id"),
        IndexModel([("user_id", ASCENDING)], name="idx_user_id"),
        IndexModel([("user_id", ASCENDING), ("farm_id", ASCENDING)],
                   name="idx_user_farm"),
    ],

    # ── Digital Twin: Field Profiles ──────────────────────────────────────────
    "field_profiles": [
        IndexModel([("field_id", ASCENDING)], unique=True, name="unique_field_id"),
        IndexModel([("user_id", ASCENDING)], name="idx_user_id"),
        IndexModel([("farm_id", ASCENDING)], name="idx_farm_id"),
        IndexModel([("user_id", ASCENDING), ("field_id", ASCENDING)],
                   name="idx_user_field"),
        IndexModel([("user_id", ASCENDING), ("current_crop", ASCENDING)],
                   name="idx_user_crop"),
    ],

    # ── Market Price Cache (new collection) ───────────────────────────────────
    "market_prices": [
        IndexModel([("commodity", ASCENDING), ("state", ASCENDING),
                    ("fetched_at", DESCENDING)],
                   name="idx_commodity_state_date"),
        IndexModel([("cache_key", ASCENDING)], unique=True, name="unique_cache_key"),
        # Auto-delete market prices older than 24 hours
        IndexModel([("fetched_at", ASCENDING)],
                   expireAfterSeconds=86_400,
                   name="ttl_market_24h"),
    ],
}


async def ensure_indexes() -> None:
    """
    Create all database indexes idempotently.

    Called once at application startup. Motor handles conflicts gracefully
    (existing indexes are not recreated).

    Any failure is logged but never propagates — the application must start
    even if the DB is temporarily unreachable.
    """
    db = get_database()
    created_total = 0
    failed: List[str] = []

    for collection_name, index_list in INDEXES.items():
        try:
            col = db[collection_name]
            result = await col.create_indexes(index_list)
            count = len(result)
            created_total += count
            logger.info(
                "Indexes: %-25s → %d index(es) ensured",
                collection_name, count,
            )
        except Exception as exc:
            failed.append(collection_name)
            logger.warning(
                "Index creation failed for '%s': %s",
                collection_name, exc,
            )

    if failed:
        logger.warning("Index creation failed for collections: %s", failed)
    else:
        logger.info(
            "All indexes ensured (%d total across %d collections).",
            created_total, len(INDEXES),
        )
