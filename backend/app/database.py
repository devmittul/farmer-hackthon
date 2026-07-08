"""
KrishiMitra Backend – Database Layer
=====================================
Async MongoDB connection via Motor.
Uses lazy initialization + certifi for TLS.
"""
import logging
import certifi
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: Optional[AsyncIOMotorClient] = None  # type: ignore[type-arg]
_database: Optional[AsyncIOMotorDatabase] = None  # type: ignore[type-arg]


def _make_client(uri: str, timeout_ms: int = 8000) -> AsyncIOMotorClient:  # type: ignore[type-arg]
    """Create a Motor client."""
    return AsyncIOMotorClient(
        uri,
        serverSelectionTimeoutMS=timeout_ms,
        connectTimeoutMS=timeout_ms,
        maxPoolSize=20,
        minPoolSize=1,
        retryWrites=True,
        tls=True,
        tlsAllowInvalidCertificates=True,
    )


def _ensure_connected() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    """
    Lazily create and return the database connection.
    Works with uvicorn --reload (each worker initialises independently).
    """
    global _client, _database
    if _database is not None:
        return _database

    settings = get_settings()
    logger.info("Lazy-connecting to MongoDB …")
    _client = _make_client(settings.mongodb_uri)
    _database = _client[settings.mongodb_db_name]
    logger.info("MongoDB client created – database: %s", settings.mongodb_db_name)
    return _database


async def connect_to_mongo() -> None:
    """Eagerly open the Motor client and verify connectivity with a ping."""
    global _client, _database
    settings = get_settings()
    logger.info("Connecting to MongoDB …")
    try:
        _client = _make_client(settings.mongodb_uri, timeout_ms=10000)
        await _client.admin.command("ping")
        _database = _client[settings.mongodb_db_name]
        logger.info("MongoDB connected – database: %s", settings.mongodb_db_name)
    except Exception as exc:
        logger.error("MongoDB connection failed: %s", exc)
        _client = None
        _database = None
        raise


async def close_mongo_connection() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_database() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    return _ensure_connected()


COLLECTIONS = {
    # ── Existing collections ──────────────────────────────────────────────────
    "users": "users",
    "chat_history": "chat_history",
    "crop_predictions": "crop_predictions",
    "vehicle_predictions": "vehicle_predictions",
    "routes": "routes",
    "courier_requests": "courier_requests",
    "sos_alerts": "sos_alerts",
    "weather_cache": "weather_cache",
    "satellite_data": "satellite_data",
    "language_preferences": "language_preferences",
    # ── Digital Twin collections (legacy) ─────────────────────────────────────
    "farmer_profiles": "farmer_profiles",
    "farm_profiles": "farm_profiles",
    "field_profiles": "field_profiles",
    # ── Farm Management (geo-aware, Phase 1) ──────────────────────────────────
    "farms": "farms",
    # ── Market cache ──────────────────────────────────────────────────────────
    "market_prices": "market_prices",
    # ── Field Mapping ─────────────────────────────────────────────────────────
    "fields": "fields",
    # ── Refresh Snapshots (Provider Architecture v2) ──────────────────────────
    "refresh_snapshots": "refresh_snapshots",
}


def get_collection(name: str):  # type: ignore[return]
    db = get_database()
    if name not in COLLECTIONS:
        raise ValueError(f"Unknown collection: {name}")
    return db[COLLECTIONS[name]]
