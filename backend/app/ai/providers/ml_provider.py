"""
ML Provider – wraps all Scikit-learn model inference.

Delegates to app.ai.ml.models.  Models are only executed based on
intent and data availability, never unconditionally.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from app.ai.providers import BaseProvider, FreshnessLevel

logger = logging.getLogger(__name__)


class MLProvider(BaseProvider):
    name = "ml_inference"
    freshness = FreshnessLevel.DYNAMIC
    default_ttl = 3600  # 1 hour (re-run if inputs change)

    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Execute ML models based on intent and available data.

        Expected params:
            intent (str): Detected intent type value.
            extra_params (dict): Domain-specific params (NPK values, etc.).
            weather (dict, optional): Current weather data.
            satellite (dict, optional): Satellite data with NDVI.
            field (dict, optional): Field profile data.
            farm (dict, optional): Farm profile data.
        """
        from app.schemas.requests import IntentType

        intent_str = params.get("intent", "")
        extra = params.get("extra_params", {})
        weather = params.get("weather")
        satellite = params.get("satellite")
        field_data = params.get("field")
        farm_data = params.get("farm")

        result: Dict[str, Any] = {}

        # ── Intent-gated: Crop recommendation ────────────────────────────────
        if intent_str == IntentType.CROP.value and _has_soil_params(extra):
            try:
                from app.ai.ml.models import predict_crop
                crop_result = await asyncio.to_thread(
                    predict_crop,
                    nitrogen=float(extra.get("nitrogen", 40)),
                    phosphorus=float(extra.get("phosphorus", 40)),
                    potassium=float(extra.get("potassium", 40)),
                    temperature=float(extra.get("temperature", 25)),
                    humidity=float(extra.get("humidity", 60)),
                    ph=float(extra.get("ph", 6.5)),
                    rainfall=float(extra.get("rainfall", 80)),
                )
                result["crop_prediction"] = crop_result
            except Exception as exc:
                logger.error("MLProvider: crop prediction error: %s", exc)

        # ── Intent-gated: Vehicle demand ─────────────────────────────────────
        elif intent_str == IntentType.VEHICLE.value and _has_vehicle_params(extra):
            try:
                from app.ai.ml.models import predict_vehicle_demand
                vehicle_result = await asyncio.to_thread(
                    predict_vehicle_demand,
                    quantity_tonnes=float(extra.get("quantity_tonnes", 1)),
                    destination=str(extra.get("destination", "")),
                    crop_type=str(extra.get("crop_type", "")),
                    date=str(extra.get("date", datetime.now(UTC).date().isoformat())),
                )
                result["vehicle_prediction"] = vehicle_result
            except Exception as exc:
                logger.error("MLProvider: vehicle prediction error: %s", exc)

        # ── Advanced intelligence (only when sufficient data exists) ──────────
        target = field_data or farm_data
        if (target and weather and satellite
                and satellite.get("ndvi") is not None):
            ndvi = float(satellite.get("ndvi", 0.4))
            weather_cur = weather.get("current", {})
            weather_fc = weather.get("forecast", [{}])
            temp = float(weather_cur.get("temperature_c") or 25)
            humidity = float(weather_cur.get("humidity_pct") or 60)
            rainfall_7d = sum(
                float(d.get("rainfall_mm") or 0)
                for d in weather_fc[:7]
            )

            # Yield prediction
            try:
                from app.ai.ml.models import predict_yield
                area_ha = float(target.get("area_ha") or target.get("area_hectares") or 1.0)
                yield_result = await asyncio.to_thread(
                    predict_yield,
                    ndvi=ndvi,
                    rainfall_mm=rainfall_7d,
                    temperature_c=temp,
                    soil_ph=float(target.get("soil_ph") or 6.5),
                    nitrogen_kg_ha=float(target.get("nitrogen_kg_ha") or 40),
                    humidity_pct=humidity,
                    area_ha=area_ha,
                )
                result["yield_prediction"] = yield_result
            except Exception as exc:
                logger.error("MLProvider: yield prediction error: %s", exc)

            # Disease risk prediction
            try:
                from app.ai.ml.models import predict_disease_risk
                disease_result = await asyncio.to_thread(
                    predict_disease_risk,
                    humidity_pct=humidity,
                    temperature_c=temp,
                    rainfall_mm=float(weather_cur.get("rainfall_mm") or 0),
                    ndvi=ndvi,
                )
                result["disease_risk"] = disease_result
            except Exception as exc:
                logger.error("MLProvider: disease risk error: %s", exc)

            # Water stress (deterministic rule-based)
            try:
                from app.ai.ml.models import predict_water_stress
                water_result = predict_water_stress(
                    ndvi=ndvi,
                    rainfall_mm_7d=rainfall_7d,
                    temperature_c=temp,
                    humidity_pct=humidity,
                    soil_type=str(target.get("soil_type") or "loamy"),
                )
                result["water_stress"] = water_result
            except Exception as exc:
                logger.error("MLProvider: water stress error: %s", exc)

        return result if result else None


# ── Parameter presence helpers ────────────────────────────────────────────────

def _has_soil_params(params: Dict[str, Any]) -> bool:
    """Return True if enough soil parameters are present to run crop ML."""
    required = {"nitrogen", "phosphorus", "potassium", "temperature",
                "humidity", "ph", "rainfall"}
    return all(params.get(k) is not None for k in required)


def _has_vehicle_params(params: Dict[str, Any]) -> bool:
    """Return True if vehicle demand params are present."""
    return bool(
        params.get("quantity_tonnes")
        and params.get("destination")
        and params.get("crop_type")
    )
