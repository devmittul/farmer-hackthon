"""
KrishiMitra Backend – Satellite / GEE Service
===============================================
Google Earth Engine integration for:
  - NDVI (Normalized Difference Vegetation Index)
  - Crop Health Index
  - Vegetation Analysis
  - Harvest Detection

GEE SDK is authenticated via Service Account.
Falls back gracefully when GEE credentials are not configured.
"""
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from app.config import get_settings
from app.database import get_collection

logger = logging.getLogger(__name__)

_gee_initialised = False


def _init_gee() -> bool:
    """
    Initialise Google Earth Engine with service account credentials.
    Returns True if successful, False otherwise.
    """
    global _gee_initialised
    if _gee_initialised:
        return True

    settings = get_settings()
    if not settings.gee_service_account or not settings.gee_key_file:
        logger.warning("GEE credentials not configured – satellite features disabled.")
        return False

    try:
        import ee

        credentials = ee.ServiceAccountCredentials(
            settings.gee_service_account,
            settings.gee_key_file,
        )
        ee.Initialize(credentials)
        _gee_initialised = True
        logger.info("Google Earth Engine initialised.")
        return True
    except ImportError:
        logger.warning("earthengine-api not installed. Install: pip install earthengine-api")
        return False
    except Exception as exc:
        logger.error("GEE initialisation failed: %s", exc)
        return False


async def get_ndvi(
    latitude: float,
    longitude: float,
    location_name: str = "unknown",
    radius_km: float = 2.0,
) -> Optional[dict[str, Any]]:
    """
    Calculate NDVI and crop health metrics for a given location.

    Args:
        latitude: Location latitude.
        longitude: Location longitude.
        location_name: Human-readable name for caching key.
        radius_km: Buffer radius around the point.

    Returns:
        Dict with NDVI, crop health, and vegetation index, or None.
    """
    if not _init_gee():
        return _fallback_satellite_response(location_name)

    try:
        import ee

        # Check cache first
        cache_key = f"satellite:{location_name.lower()}:{latitude:.3f}:{longitude:.3f}"
        col = get_collection("satellite_data")
        cached = await col.find_one(
            {
                "cache_key": cache_key,
                "processed_at": {
                    "$gt": datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                },
            }
        )
        if cached:
            logger.debug("Satellite cache HIT: %s", cache_key)
            return cached["result_data"]

        # Define area of interest
        point = ee.Geometry.Point([longitude, latitude])
        aoi = point.buffer(radius_km * 1000)  # metres

        # Use Sentinel-2 Surface Reflectance (free, 10m resolution)
        sentinel2 = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(
                ee.Date.now().advance(-30, "day"),
                ee.Date.now(),
            )
            .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
            .sort("CLOUDY_PIXEL_PERCENTAGE")
            .first()
        )

        if sentinel2 is None:
            logger.warning("No Sentinel-2 imagery available for %s", location_name)
            return _fallback_satellite_response(location_name)

        # NDVI = (NIR - Red) / (NIR + Red)
        ndvi_image = sentinel2.normalizedDifference(["B8", "B4"]).rename("NDVI")

        ndvi_stats = ndvi_image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.minMax(),
                sharedInputs=True,
            ),
            geometry=aoi,
            scale=10,
            maxPixels=1e8,
        ).getInfo()

        ndvi_mean = ndvi_stats.get("NDVI_mean", 0.0)
        ndvi_min = ndvi_stats.get("NDVI_min", 0.0)
        ndvi_max = ndvi_stats.get("NDVI_max", 0.0)

        # Interpret NDVI
        crop_health = _interpret_ndvi(ndvi_mean)
        harvest_detection = _detect_harvest_stage(ndvi_mean)

        result: dict[str, Any] = {
            "location": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "ndvi": round(float(ndvi_mean), 4),
            "ndvi_min": round(float(ndvi_min), 4),
            "ndvi_max": round(float(ndvi_max), 4),
            "crop_health": crop_health,
            "vegetation_index": round(float(ndvi_mean) * 100, 1),
            "harvest_detection": harvest_detection,
            "analysis_date": datetime.now(UTC).date().isoformat(),
            "data_source": "Sentinel-2 SR (GEE)",
        }

        # Persist to MongoDB
        await col.update_one(
            {"cache_key": cache_key},
            {
                "$set": {
                    "cache_key": cache_key,
                    "location": location_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "result_data": result,
                    "processed_at": datetime.now(UTC),
                }
            },
            upsert=True,
        )

        logger.info("GEE NDVI computed for %s: %.4f (%s)", location_name, ndvi_mean, crop_health)
        return result

    except Exception as exc:
        logger.error("GEE NDVI computation failed: %s", exc)
        return _fallback_satellite_response(location_name)


def _interpret_ndvi(ndvi: float) -> str:
    """Convert NDVI value to human-readable crop health label."""
    if ndvi < 0:
        return "Water / Non-vegetated surface"
    elif ndvi < 0.1:
        return "Bare soil or sparse vegetation"
    elif ndvi < 0.2:
        return "Very poor vegetation"
    elif ndvi < 0.35:
        return "Poor crop health – stress detected"
    elif ndvi < 0.5:
        return "Moderate crop health"
    elif ndvi < 0.65:
        return "Good crop health"
    elif ndvi < 0.8:
        return "Very good crop health"
    else:
        return "Excellent vegetation / Dense canopy"


def _detect_harvest_stage(ndvi: float) -> str:
    """Estimate harvest stage from NDVI value."""
    if ndvi < 0.15:
        return "Post-harvest or fallow land"
    elif ndvi < 0.30:
        return "Early growth / seedling stage"
    elif ndvi < 0.55:
        return "Vegetative growth stage"
    elif ndvi < 0.70:
        return "Reproductive / flowering stage"
    elif ndvi < 0.80:
        return "Grain fill / maturation stage"
    else:
        return "Near harvest maturity"


def _fallback_satellite_response(location_name: str) -> dict[str, Any]:
    """Return a clear fallback when GEE is unavailable."""
    return {
        "location": location_name,
        "ndvi": None,
        "crop_health": "Satellite analysis unavailable",
        "vegetation_index": None,
        "harvest_detection": "Satellite analysis unavailable",
        "message": (
            "Google Earth Engine is not configured. "
            "Set GEE_SERVICE_ACCOUNT and GEE_KEY_FILE in .env to enable satellite features."
        ),
        "data_source": "N/A",
    }
