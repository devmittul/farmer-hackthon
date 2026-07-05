"""
KrishiMitra Backend – Context Builder
=======================================
Gathers every piece of factual context for a request BEFORE the AI
Reasoning Engine is called.

Responsibilities:
  1. Load FarmerProfile + FarmProfile + FieldProfile from MongoDB
  2. Fetch live weather (with caching)
  3. Fetch satellite data (NDVI / crop health)
  4. Load recent chat history for conversation continuity
  5. Run ML model predictions (crop / vehicle demand)
  6. Assemble everything into a single StructuredContext object

Hard rules:
  • This module NEVER calls the AI Reasoning Engine.
  • Each data source is fetched independently; failure of one must never
    block the others (graceful degradation with None values).
  • All heavy I/O is async.
  • CPU-bound ML inference is wrapped in asyncio.to_thread() so the
    FastAPI event loop is never blocked.

Usage:
    ctx = await ContextBuilder.build(
        intent=intent,
        message=message,
        language=language,
        location=location,
        user_id=user_id,
        field_id=field_id,
        extra_params=request_body_dict,
    )
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field as dc_field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from app.schemas.requests import IntentType, LanguageCode

logger = logging.getLogger(__name__)


# ── Structured Context dataclass ──────────────────────────────────────────────

@dataclass
class StructuredContext:
    """
    Immutable snapshot of all factual data for a single request.

    The Context Builder produces this; the Prompt Builder consumes it.
    The Reasoning Engine NEVER modifies this object.
    """
    # ── Request metadata ──────────────────────────────────────────────────────
    request_id: str
    timestamp: str
    intent: IntentType
    language: LanguageCode
    raw_message: str
    location: Optional[str]

    # ── Farmer / Farm / Field Digital Twin ───────────────────────────────────
    farmer: Optional[Dict[str, Any]] = None
    farm: Optional[Dict[str, Any]] = None
    field: Optional[Dict[str, Any]] = None

    # ── Live data ─────────────────────────────────────────────────────────────
    weather: Optional[Dict[str, Any]] = None
    weather_advisory: Optional[str] = None
    satellite: Optional[Dict[str, Any]] = None

    # ── ML predictions ────────────────────────────────────────────────────────
    crop_prediction: Optional[Dict[str, Any]] = None
    vehicle_prediction: Optional[Dict[str, Any]] = None

    # ── History ───────────────────────────────────────────────────────────────
    recent_chat: List[Dict[str, Any]] = dc_field(default_factory=list)
    recent_predictions: List[Dict[str, Any]] = dc_field(default_factory=list)

    # ── Data source confidence contributions ─────────────────────────────────
    data_sources: Dict[str, bool] = dc_field(default_factory=dict)
    """Maps source name → True (available) / False (unavailable)."""

    # ── Extra domain-specific params ──────────────────────────────────────────
    extra: Dict[str, Any] = dc_field(default_factory=dict)
    """Route params, courier params, SOS coords – anything intent-specific."""


# ── Context Builder ───────────────────────────────────────────────────────────

class ContextBuilder:
    """
    Assembles a StructuredContext for every inbound request.

    All gathering is concurrent where possible (asyncio.gather).
    Each source is independently try/except guarded.
    """

    @classmethod
    async def build(
        cls,
        *,
        request_id: str,
        intent: IntentType,
        message: str,
        language: LanguageCode,
        location: Optional[str] = None,
        user_id: Optional[str] = None,
        field_id: Optional[str] = None,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> StructuredContext:
        """
        Build a complete StructuredContext for a request.

        Args:
            request_id:   Unique ID for this request (injected by orchestrator).
            intent:       Pre-detected intent.
            message:      Sanitised raw user message.
            language:     Detected / provided language code.
            location:     Optional location string (place name or "lat,lon").
            user_id:      Authenticated user's MongoDB ObjectId string.
            field_id:     Optional specific field to load.
            extra_params: Domain-specific payload (crop NPK, route origin, etc.)

        Returns:
            A populated StructuredContext.
        """
        logger.info(
            "ContextBuilder.build: request_id=%s intent=%s lang=%s user=%s",
            request_id, intent, language, user_id or "anon",
        )

        ctx = StructuredContext(
            request_id=request_id,
            timestamp=datetime.now(UTC).isoformat(),
            intent=intent,
            language=language,
            raw_message=message,
            location=location,
            extra=extra_params or {},
        )

        # ── Run concurrent I/O fetches ────────────────────────────────────────
        tasks = [
            cls._load_digital_twin(ctx, user_id, field_id),
            cls._fetch_weather(ctx),
            cls._fetch_satellite(ctx),
            cls._fetch_market_prices(ctx),
            cls._load_chat_history(ctx, user_id),
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        # ── Run ML predictions synchronously in thread pool ───────────────────
        await cls._run_ml(ctx, intent, extra_params or {})

        logger.info(
            "Context ready: sources=%s",
            {k: v for k, v in ctx.data_sources.items()},
        )
        return ctx

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _load_digital_twin(
        ctx: StructuredContext,
        user_id: Optional[str],
        field_id: Optional[str],
    ) -> None:
        """Load FarmerProfile, FarmProfile, FieldProfile from MongoDB."""
        if not user_id:
            ctx.data_sources["digital_twin"] = False
            return

        try:
            from app.database import get_collection

            # Farmer profile
            farmer_col = get_collection("farmer_profiles")
            farmer_doc = await farmer_col.find_one({"user_id": user_id})
            if farmer_doc:
                farmer_doc.pop("_id", None)
                ctx.farmer = farmer_doc
                ctx.data_sources["farmer_profile"] = True
            else:
                ctx.data_sources["farmer_profile"] = False

            # If a specific field is requested, load it
            if field_id:
                field_col = get_collection("field_profiles")
                field_doc = await field_col.find_one(
                    {"field_id": field_id, "user_id": user_id}
                )
                if field_doc:
                    field_doc.pop("_id", None)
                    ctx.field = field_doc
                    ctx.data_sources["field_profile"] = True

                    # Also load the parent farm
                    farm_id = field_doc.get("farm_id")
                    if farm_id:
                        farm_col = get_collection("farm_profiles")
                        farm_doc = await farm_col.find_one(
                            {"farm_id": farm_id, "user_id": user_id}
                        )
                        if farm_doc:
                            farm_doc.pop("_id", None)
                            ctx.farm = farm_doc
                            ctx.data_sources["farm_profile"] = True

        except Exception as exc:
            logger.error("ContextBuilder: digital twin load error: %s", exc)
            ctx.data_sources["digital_twin"] = False

    @staticmethod
    async def _fetch_weather(ctx: StructuredContext) -> None:
        """Fetch weather from Open-Meteo (with cache) based on context location."""
        loc = ctx.location
        if not loc and ctx.field:
            # Derive location from field centroid if no explicit location
            centroid = ctx.field.get("centroid")
            if centroid:
                loc = f"{centroid.get('latitude')},{centroid.get('longitude')}"

        if not loc:
            ctx.data_sources["weather"] = False
            return

        try:
            from app.ai.weather.service import build_weather_advisory, fetch_weather

            weather = await fetch_weather(loc, days=7)
            if weather:
                ctx.weather = weather
                ctx.weather_advisory = build_weather_advisory(weather)
                ctx.data_sources["weather"] = True
            else:
                ctx.data_sources["weather"] = False
        except Exception as exc:
            logger.error("ContextBuilder: weather fetch error: %s", exc)
            ctx.data_sources["weather"] = False

    @staticmethod
    async def _fetch_satellite(ctx: StructuredContext) -> None:
        """Fetch NDVI / crop health from GEE for the field location."""
        lat, lon, name = None, None, "unknown"

        if ctx.field:
            centroid = ctx.field.get("centroid") or {}
            lat = centroid.get("latitude")
            lon = centroid.get("longitude")
            name = ctx.field.get("name") or ctx.location or "field"
        elif ctx.weather:
            lat = ctx.weather.get("latitude")
            lon = ctx.weather.get("longitude")
            name = ctx.location or "location"

        if lat is None or lon is None:
            ctx.data_sources["satellite"] = False
            return

        try:
            from app.ai.satellite.service import get_ndvi

            sat = await get_ndvi(lat, lon, location_name=name)
            if sat and sat.get("ndvi") is not None:
                ctx.satellite = sat
                ctx.data_sources["satellite"] = True
            else:
                ctx.data_sources["satellite"] = False
        except Exception as exc:
            logger.error("ContextBuilder: satellite fetch error: %s", exc)
            ctx.data_sources["satellite"] = False

    @staticmethod
    async def _fetch_market_prices(ctx: StructuredContext) -> None:
        """Fetch market/mandi prices for MARKET intent queries."""
        if ctx.intent != IntentType.MARKET:
            return

        commodity = (
            ctx.extra.get("crop")
            or ctx.extra.get("commodity")
            or (ctx.field.get("current_crop") if ctx.field else None)
            or _extract_commodity(ctx.raw_message)
        )
        if not commodity:
            ctx.data_sources["market"] = False
            return

        try:
            from app.ai.market.service import fetch_market_prices

            state = (
                ctx.extra.get("state")
                or (ctx.farmer.get("state") if ctx.farmer else None)
                or ctx.location
            )
            prices = await fetch_market_prices(
                commodity=commodity,
                state=state,
            )
            ctx.extra["market_prices"] = prices
            ctx.data_sources["market"] = bool(prices.get("prices"))
        except Exception as exc:
            logger.error("ContextBuilder: market price fetch error: %s", exc)
            ctx.data_sources["market"] = False

    @staticmethod
    async def _load_chat_history(
        ctx: StructuredContext,
        user_id: Optional[str],
    ) -> None:
        """Load the last 5 chat exchanges for conversation continuity."""
        if not user_id:
            ctx.data_sources["chat_history"] = False
            return

        try:
            from app.database import get_collection

            col = get_collection("chat_history")
            cursor = (
                col.find({"user_id": user_id}, {"context_data": 0})
                .sort("created_at", -1)
                .limit(5)
            )
            history: List[Dict[str, Any]] = []
            async for doc in cursor:
                history.append({
                    "role": "assistant",
                    "user_said": doc.get("user_message"),
                    "assistant_replied": doc.get("assistant_reply"),
                    "intent": doc.get("intent"),
                    "created_at": str(doc.get("created_at", "")),
                })
            ctx.recent_chat = list(reversed(history))  # chronological order
            ctx.data_sources["chat_history"] = bool(history)
        except Exception as exc:
            logger.error("ContextBuilder: chat history load error: %s", exc)
            ctx.data_sources["chat_history"] = False

    @staticmethod
    async def _run_ml(
        ctx: StructuredContext,
        intent: IntentType,
        params: Dict[str, Any],
    ) -> None:
        """
        Execute ML predictions in a thread pool (CPU-bound, non-blocking).

        Crop & vehicle predictions are intent-gated.
        Yield, disease risk, and water stress run whenever enough data is present.
        """
        # ── Crop recommendation (explicit soil params required) ───────────────
        if intent == IntentType.CROP and _has_soil_params(params):
            try:
                from app.ai.ml.models import predict_crop
                result = await asyncio.to_thread(
                    predict_crop,
                    nitrogen=float(params.get("nitrogen", 40)),
                    phosphorus=float(params.get("phosphorus", 40)),
                    potassium=float(params.get("potassium", 40)),
                    temperature=float(params.get("temperature", 25)),
                    humidity=float(params.get("humidity", 60)),
                    ph=float(params.get("ph", 6.5)),
                    rainfall=float(params.get("rainfall", 80)),
                )
                ctx.crop_prediction = result
                ctx.data_sources["ml_crop"] = True
            except Exception as exc:
                logger.error("ContextBuilder: crop ML error: %s", exc)
                ctx.data_sources["ml_crop"] = False

        # ── Vehicle demand (explicit params required) ─────────────────────────
        elif intent == IntentType.VEHICLE and _has_vehicle_params(params):
            try:
                from app.ai.ml.models import predict_vehicle_demand
                result = await asyncio.to_thread(
                    predict_vehicle_demand,
                    quantity_tonnes=float(params.get("quantity_tonnes", 1)),
                    destination=str(params.get("destination", "")),
                    crop_type=str(params.get("crop_type", "")),
                    date=str(params.get("date", datetime.now(UTC).date().isoformat())),
                )
                ctx.vehicle_prediction = result
                ctx.data_sources["ml_vehicle"] = True
            except Exception as exc:
                logger.error("ContextBuilder: vehicle ML error: %s", exc)
                ctx.data_sources["ml_vehicle"] = False

        # ── Advanced field intelligence (run when field + weather + satellite available)
        if ctx.field and ctx.weather and ctx.satellite and ctx.satellite.get("ndvi") is not None:
            ndvi = float(ctx.satellite.get("ndvi", 0.4))
            weather_cur = ctx.weather.get("current", {})
            weather_fc = ctx.weather.get("forecast", [{}])
            temp = float(weather_cur.get("temperature_c") or 25)
            humidity = float(weather_cur.get("humidity_pct") or 60)
            rainfall_7d = sum(
                float(d.get("rainfall_mm") or 0)
                for d in weather_fc[:7]
            )

            # Yield prediction
            try:
                from app.ai.ml.models import predict_yield
                yield_result = await asyncio.to_thread(
                    predict_yield,
                    ndvi=ndvi,
                    rainfall_mm=rainfall_7d,
                    temperature_c=temp,
                    soil_ph=float(ctx.field.get("soil_ph") or 6.5),
                    nitrogen_kg_ha=float(ctx.field.get("nitrogen_kg_ha") or 40),
                    humidity_pct=humidity,
                    area_ha=float(ctx.field.get("area_ha") or 1.0),
                )
                ctx.extra["yield_prediction"] = yield_result
                ctx.data_sources["ml_yield"] = True
            except Exception as exc:
                logger.error("ContextBuilder: yield ML error: %s", exc)
                ctx.data_sources["ml_yield"] = False

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
                ctx.extra["disease_risk"] = disease_result
                ctx.data_sources["ml_disease"] = True
            except Exception as exc:
                logger.error("ContextBuilder: disease ML error: %s", exc)
                ctx.data_sources["ml_disease"] = False

            # Water stress (deterministic rule-based)
            try:
                from app.ai.ml.models import predict_water_stress
                water_result = predict_water_stress(
                    ndvi=ndvi,
                    rainfall_mm_7d=rainfall_7d,
                    temperature_c=temp,
                    humidity_pct=humidity,
                    soil_type=str(ctx.field.get("soil_type") or "loamy"),
                )
                ctx.extra["water_stress"] = water_result
                ctx.data_sources["ml_water"] = True
            except Exception as exc:
                logger.error("ContextBuilder: water stress error: %s", exc)
                ctx.data_sources["ml_water"] = False


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


def _extract_commodity(message: str) -> Optional[str]:
    """
    Extract a commodity name from a free-text user message.

    Looks for known crop names embedded in the message text.
    Returns the first match or None.
    """
    _CROPS = [
        "wheat", "rice", "maize", "corn", "onion", "tomato", "potato",
        "soybean", "cotton", "sugarcane", "groundnut", "mustard",
        "chickpea", "lentil", "bajra", "jowar", "turmeric", "moong",
        # Hindi aliases
        "gehun", "dhan", "paddy", "pyaz", "tamatar", "aloo", "sarson",
        "chana", "masoor", "arhar", "tur", "makka",
    ]
    msg_lower = message.lower()
    for crop in _CROPS:
        if crop in msg_lower:
            return crop
    return None

