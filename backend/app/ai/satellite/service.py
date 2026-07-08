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
    boundary: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """
    Calculate NDVI and crop health metrics for a given location.

    Args:
        latitude: Location latitude.
        longitude: Location longitude.
        location_name: Human-readable name for caching key.
        radius_km: Buffer radius around the point.
        boundary: Optional GeoJSON Polygon dict for precise field analysis.

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
        if boundary and boundary.get("type") == "Polygon":
            aoi = ee.Geometry.Polygon(boundary["coordinates"])
        else:
            point = ee.Geometry.Point([longitude, latitude])
            aoi = point.buffer(radius_km * 1000)  # metres

        # Use Sentinel-2 Surface Reflectance (free, 10m resolution)
        now_str = datetime.now(UTC).isoformat()
        sentinel2 = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterBounds(aoi)
            .filterDate(
                ee.Date(now_str).advance(-30, "day"),
                ee.Date(now_str),
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

        # NDWI = (Green - NIR) / (Green + NIR)
        ndwi_image = sentinel2.normalizedDifference(["B3", "B8"]).rename("NDWI")

        # EVI = 2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))
        evi_image = sentinel2.expression(
            '2.5 * ((NIR - RED) / (NIR + 6.0 * RED - 7.5 * BLUE + 1.0))', {
                'NIR': sentinel2.select('B8'),
                'RED': sentinel2.select('B4'),
                'BLUE': sentinel2.select('B2')
            }
        ).rename("EVI")

        combined_image = ndvi_image.addBands(ndwi_image).addBands(evi_image)

        stats = combined_image.reduceRegion(
            reducer=ee.Reducer.mean().combine(
                reducer2=ee.Reducer.minMax(),
                sharedInputs=True,
            ),
            geometry=aoi,
            scale=10,
            maxPixels=1e8,
        ).getInfo()

        ndvi_mean = stats.get("NDVI_mean") or 0.0
        ndvi_min = stats.get("NDVI_min") or 0.0
        ndvi_max = stats.get("NDVI_max") or 0.0

        ndwi_mean = stats.get("NDWI_mean") or 0.0
        ndwi_min = stats.get("NDWI_min") or 0.0
        ndwi_max = stats.get("NDWI_max") or 0.0

        evi_mean = stats.get("EVI_mean") or 0.0
        evi_min = stats.get("EVI_min") or 0.0
        evi_max = stats.get("EVI_max") or 0.0

        # Calculate Area Statistics in square meters
        gee_area = aoi.area(maxError=1).getInfo()

        # Interpret NDVI / EVI for health
        crop_health = _interpret_ndvi(ndvi_mean)
        vegetation_health = f"{crop_health} (EVI: {evi_mean:.2f})"
        harvest_detection = _detect_harvest_stage(ndvi_mean)

        result: dict[str, Any] = {
            "location": location_name,
            "latitude": latitude,
            "longitude": longitude,
            "ndvi": round(float(ndvi_mean), 4),
            "ndvi_min": round(float(ndvi_min), 4),
            "ndvi_max": round(float(ndvi_max), 4),
            "ndwi": round(float(ndwi_mean), 4),
            "ndwi_min": round(float(ndwi_min), 4),
            "ndwi_max": round(float(ndwi_max), 4),
            "evi": round(float(evi_mean), 4),
            "evi_min": round(float(evi_min), 4),
            "evi_max": round(float(evi_max), 4),
            "crop_health": crop_health,
            "vegetation_health": vegetation_health,
            "vegetation_index": round(float(ndvi_mean) * 100, 1),
            "harvest_detection": harvest_detection,
            "area_statistics": {
                "total_area_m2": round(gee_area, 2),
                "total_area_acres": round(gee_area * 0.000247105, 4),
                "total_area_hectares": round(gee_area / 10000.0, 4)
            },
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

        logger.info("GEE NDVI/NDWI/EVI computed for %s: NDVI=%.4f (%s)", location_name, ndvi_mean, crop_health)
        return result

    except Exception as exc:
        logger.error("GEE NDVI/NDWI/EVI computation failed: %s", exc)
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
        "ndvi_min": None,
        "ndvi_max": None,
        "ndwi": None,
        "ndwi_min": None,
        "ndwi_max": None,
        "evi": None,
        "evi_min": None,
        "evi_max": None,
        "crop_health": "Satellite analysis unavailable",
        "vegetation_health": "Satellite analysis unavailable",
        "vegetation_index": None,
        "harvest_detection": "Satellite analysis unavailable",
        "area_statistics": {
            "total_area_m2": 0.0,
            "total_area_acres": 0.0,
            "total_area_hectares": 0.0
        },
        "message": (
            "Google Earth Engine is not configured. "
            "Set GEE_SERVICE_ACCOUNT and GEE_KEY_FILE in .env to enable satellite features."
        ),
        "data_source": "N/A",
    }



async def get_soil_data(
    latitude: float,
    longitude: float,
    location_name: str = "unknown",
    boundary: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """
    Extract soil statistics (Texture, pH, Organic Carbon, Bulk Density) using Google Earth Engine.
    Uses farm polygon if provided, otherwise a 100m buffer around the centroid.
    """
    if not _init_gee():
        logger.warning("GEE not initialized, cannot fetch soil data.")
        return None

    try:
        import ee

        # Check cache first
        cache_key = f"soil_gee:{location_name.lower()}:{latitude:.3f}:{longitude:.3f}"
        col = get_collection("satellite_data") # reuse same collection for cache
        cached = await col.find_one(
            {
                "cache_key": cache_key,
                "processed_at": {
                    "$gt": datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                },
            }
        )
        if cached:
            return cached["result_data"]

        # Define area of interest
        if boundary and boundary.get("type") == "Polygon":
            aoi = ee.Geometry.Polygon(boundary["coordinates"])
        else:
            point = ee.Geometry.Point([longitude, latitude])
            aoi = point.buffer(100)  # metres

        # Load datasets (using 0cm depth / surface for consistency)
        texture_img = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0').rename('texture')
        ph_img = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02").select('b0').rename('ph')
        oc_img = ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02").select('b0').rename('oc')
        bd_img = ee.Image("OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02").select('b0').rename('bd')

        combined = texture_img.addBands(ph_img).addBands(oc_img).addBands(bd_img)

        # Use appropriate reducer (mean for continuous, mode for categorical texture)
        mean_reducer = ee.Reducer.mean()
        mode_reducer = ee.Reducer.mode()
        
        # We need to reduce each band with its appropriate reducer.
        # Since reduceRegion only takes one reducer, we can combine them and let them apply to all bands,
        # then we just extract the correct one for each band.
        combined_reducer = mean_reducer.combine(
            reducer2=mode_reducer,
            sharedInputs=True
        )

        stats = combined.reduceRegion(
            reducer=combined_reducer,
            geometry=aoi,
            scale=250,
            maxPixels=1e8
        ).getInfo()

        texture_val = stats.get('texture_mode')
        ph_val = stats.get('ph_mean')
        oc_val = stats.get('oc_mean')
        bd_val = stats.get('bd_mean')
        
        texture_classes = {
            1: "Clay", 2: "Silty Clay", 3: "Sandy Clay", 4: "Clay Loam", 
            5: "Silty Clay Loam", 6: "Sandy Clay Loam", 7: "Loam", 8: "Silt Loam", 
            9: "Sandy Loam", 10: "Silt", 11: "Loamy Sand", 12: "Sand"
        }
        
        texture_class = "Unknown"
        if texture_val is not None:
            texture_class = texture_classes.get(round(texture_val), "Unknown")
            
        # pH is typically x10
        ph_actual = float(ph_val) / 10 if ph_val is not None else None
        
        # BD is typically x100 (e.g. 150 -> 1.5 g/cm3)
        bd_actual = float(bd_val) / 100 if bd_val is not None else None
        
        # OC is typically x2 (e.g. 2 -> 1.0 g/kg or similar, but let's keep it raw if we aren't sure, or just float)
        oc_actual = float(oc_val) if oc_val is not None else None

        result = {
            "texture": texture_class,
            "ph": round(ph_actual, 2) if ph_actual else None,
            "organic_carbon": round(oc_actual, 2) if oc_actual else None,
            "bulk_density": round(bd_actual, 2) if bd_actual else None,
            "raw_response": stats,
            "metadata": {
                "dataset": "OpenLandMap / Google Earth Engine",
                "resolution": "250m",
                "source": "Google Earth Engine",
            },
            "analysis_date": datetime.now(UTC).date().isoformat(),
        }

        # Cache it
        await col.update_one(
            {"cache_key": cache_key},
            {
                "$set": {
                    "cache_key": cache_key,
                    "location": location_name,
                    "result_data": result,
                    "processed_at": datetime.now(UTC),
                }
            },
            upsert=True,
        )
        return result
    except Exception as exc:
        logger.error("GEE Soil computation failed: %s", exc)
        return None
