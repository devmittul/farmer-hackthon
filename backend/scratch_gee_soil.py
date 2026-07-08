import asyncio
from app.ai.satellite.service import _init_gee

async def test_soil():
    if not _init_gee():
        return
    import ee
    aoi = ee.Geometry.Point([-119.5, 36.5]).buffer(100) # California (should have high OC)
    
    # 1. Texture
    texture_img = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02").select('b0').rename('texture')
    # 2. pH
    ph_img = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A2A_M/v02").select('b0').rename('ph')
    # 3. Organic Carbon
    oc_img = ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-6A1C_M/v02").select('b0').rename('oc')
    # 4. Bulk Density
    bd_img = ee.Image("OpenLandMap/SOL/SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02").select('b0').rename('bd')
    
    combined = texture_img.addBands(ph_img).addBands(oc_img).addBands(bd_img)
    stats = combined.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=250,
        maxPixels=1e8
    ).getInfo()
    print("California:", stats)

if __name__ == "__main__":
    asyncio.run(test_soil())
