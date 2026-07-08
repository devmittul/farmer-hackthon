"""
KrishiMitra Backend – GEE Soil Provider
==========================================
Retrieves soil data using Google Earth Engine OpenLandMap datasets.
"""
import logging
from datetime import datetime, UTC
from typing import Any, Dict, Optional

from app.ai.providers import BaseProvider, FreshnessLevel
from app.models.digital_twin import DerivedSoilIntelligence, SoilProfile
from app.ai.satellite.service import get_soil_data

logger = logging.getLogger(__name__)


class GEESoilProvider(BaseProvider):
    name: str = "geesoil"
    freshness: FreshnessLevel = FreshnessLevel.SEMI_STATIC
    default_ttl: int = 86400 * 30  # 30 days cache

    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        lon = params.get("longitude")
        lat = params.get("latitude")
        boundary = params.get("boundary")
        loc_name = params.get("location_name") or "unknown"

        if lon is None or lat is None:
            logger.debug("GEESoilProvider: Missing lat/lon")
            return None

        # Fetch soil data from GEE
        soil_stats = await get_soil_data(
            latitude=lat,
            longitude=lon,
            location_name=loc_name,
            boundary=boundary
        )
        
        if not soil_stats:
            return None

        # Normalize into SoilProfile
        profile = SoilProfile(
            texture_class=soil_stats.get("texture"),
            ph_h2o=soil_stats.get("ph"),
            soc_dg_kg=soil_stats.get("organic_carbon"),
            bulk_density_cg_cm3=soil_stats.get("bulk_density"),
            raw_response=soil_stats.get("raw_response"),
            timestamp=datetime.now(UTC).isoformat(),
            provider_source="Google Earth Engine",
            metadata=soil_stats.get("metadata")
        )
        
        # Derive Soil Intelligence
        profile.derived_intelligence = self._derive_intelligence(profile)
        
        return profile.model_dump()

    def _derive_intelligence(self, profile: SoilProfile) -> DerivedSoilIntelligence:
        """Create Derived Soil Intelligence based on scientifically supported rules."""
        
        def safe_float(val):
            return float(val) if val is not None else None

        ph = safe_float(profile.ph_h2o)
        bd = safe_float(profile.bulk_density_cg_cm3)
        oc = safe_float(profile.soc_dg_kg)
        texture = profile.texture_class
        
        # Water Holding Capacity (WHC) & Drainage Behaviour
        whc = "Unknown"
        whc_reason = "Insufficient texture data."
        drainage = "Unknown"
        drain_reason = "Insufficient texture data."
        
        if texture:
            if "Clay" in texture and "Loam" not in texture:
                whc = "High"
                whc_reason = f"High clay content ({texture}) retains water effectively."
                drainage = "Slow"
                drain_reason = f"Heavy clay ({texture}) restricts downward water flow."
            elif "Sand" in texture and "Loam" not in texture:
                whc = "Low"
                whc_reason = f"High sand content ({texture}) causes rapid drainage."
                drainage = "Fast"
                drain_reason = f"Sandy texture ({texture}) promotes rapid water movement."
            else:
                whc = "Medium"
                whc_reason = f"Balanced texture ({texture}) provides moderate water retention."
                drainage = "Moderate"
                drain_reason = f"Loamy texture ({texture}) allows balanced drainage."

        # Nutrient Retention (CEC Proxy via Texture & OC)
        nutrient = "Unknown"
        nut_reason = "Insufficient data."
        if texture and oc is not None:
            if ("Clay" in texture or "Loam" in texture) and oc > 10:
                nutrient = "High"
                nut_reason = "High organic carbon and clay/loam texture indicate good nutrient retention."
            elif "Sand" in texture and oc < 5:
                nutrient = "Low"
                nut_reason = "Sandy texture and low organic carbon indicate poor nutrient retention."
            else:
                nutrient = "Medium"
                nut_reason = "Moderate texture and carbon levels."

        # Root Penetration (Bulk Density)
        root = "Unknown"
        root_reason = "Insufficient bulk density data."
        if bd is not None:
            if bd < 1.3:
                root = "Easy"
                root_reason = "Low bulk density allows unrestricted root growth."
            elif bd > 1.6:
                root = "Restricted"
                root_reason = "High bulk density may cause soil compaction and restrict roots."
            else:
                root = "Moderate"
                root_reason = "Average bulk density poses minimal restriction to roots."
                
        # Drought Sensitivity
        drought = "Unknown"
        drought_reason = "Insufficient WHC data."
        if whc == "Low":
            drought = "High"
            drought_reason = "Low water holding capacity makes crops highly sensitive to dry spells."
        elif whc == "High":
            drought = "Low"
            drought_reason = "High water retention buffers against short-term drought."
        elif whc == "Medium":
            drought = "Moderate"
            drought_reason = "Moderate water retention provides some buffer against dry spells."
            
        # Irrigation Suitability
        irrigation = "Unknown"
        irrigation_reason = "Insufficient drainage data."
        if drainage == "Fast":
            irrigation = "High Frequency (Drip/Sprinkler)"
            irrigation_reason = "Fast drainage requires frequent, low-volume irrigation."
        elif drainage == "Slow":
            irrigation = "Careful Management (Avoid Waterlogging)"
            irrigation_reason = "Slow drainage increases waterlogging risk; avoid over-irrigation."
        elif drainage == "Moderate":
            irrigation = "Highly Suitable (Any Method)"
            irrigation_reason = "Moderate drainage is suitable for most irrigation methods."

        # Soil Fertility & Organic Matter
        fertility = "Unknown"
        fertility_reason = "Insufficient data."
        om_status = "Unknown"
        
        if oc is not None:
            if oc > 15:
                om_status = "High"
            elif oc < 5:
                om_status = "Low"
            else:
                om_status = "Moderate"
                
        if oc is not None and ph is not None:
            if oc > 15 and 6.0 <= ph <= 7.5:
                fertility = "High"
                fertility_reason = "Optimal pH and high organic carbon indicate fertile soil."
            elif oc < 5 or ph < 5.5 or ph > 8.0:
                fertility = "Low"
                fertility_reason = "Suboptimal pH or low organic carbon limits fertility."
            else:
                fertility = "Moderate"
                fertility_reason = "Average organic carbon and pH levels."
                
        # Compaction Risk
        compaction = "Unknown"
        if bd is not None and texture:
            if bd > 1.6:
                compaction = "High"
            elif bd > 1.4 and "Clay" in texture:
                compaction = "High (Clay-heavy)"
            else:
                compaction = "Low/Moderate"
                
        # Soil Health Summary
        health_summary = f"Texture: {texture or 'Unknown'}. pH: {ph or 'Unknown'}. Organic Carbon: {om_status}. Compaction Risk: {compaction}."

        # Confidence score based on available data
        data_points = sum(1 for v in [texture, ph, bd, oc] if v is not None)
        confidence = (data_points / 4) * 100 if data_points > 0 else 0.0

        return DerivedSoilIntelligence(
            water_holding_capacity=whc,
            drainage_behaviour=drainage,
            nutrient_retention=nutrient,
            root_penetration=root,
            irrigation_suitability=irrigation,
            drought_sensitivity=drought,
            soil_fertility=fertility,
            compaction_risk=compaction,
            organic_matter_status=om_status,
            soil_health_summary=health_summary,
            reason=f"WHC: {whc_reason} Drainage: {drain_reason}",
            confidence=confidence,
            source="Google Earth Engine Derived Rules"
        )
