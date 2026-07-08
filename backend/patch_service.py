import re

def update_service():
    with open('app/ai/satellite/service.py', 'r') as f:
        content = f.read()

    soil_code = """
async def get_soil_data(
    latitude: float,
    longitude: float,
    location_name: str = "unknown",
    boundary: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    \"\"\"
    Extract soil statistics (Texture, pH, Organic Carbon, Bulk Density) using Google Earth Engine.
    Uses farm polygon if provided, otherwise a 100m buffer around the centroid.
    \"\"\"
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
        # We can just use mean for all, and round texture, or use two reducers.
        # To keep it efficient, we use mean for all. Texture class is categorical but mean rounded works well enough for small fields, or we use ee.Reducer.mean() 
        stats = combined.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=250,
            maxPixels=1e8
        ).getInfo()

        texture_val = stats.get('texture')
        ph_val = stats.get('ph')
        oc_val = stats.get('oc')
        bd_val = stats.get('bd')
        
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
"""

    if "get_soil_data" not in content:
        content = content + "\n\n" + soil_code
        with open('app/ai/satellite/service.py', 'w') as f:
            f.write(content)
        print("Patched service.py successfully.")
    else:
        print("Already patched.")

if __name__ == "__main__":
    update_service()
