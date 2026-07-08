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

Architecture (v2 – Provider Pattern):
  Data fetching is now delegated to independent Providers registered in
  ``app.ai.providers.registry``.  The ContextBuilder's sole responsibility
  is to orchestrate providers and assemble StructuredContext.

  The refactored build() preserves identical external behaviour:
  same StructuredContext schema, same field names, same data quality.

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

    # ── Provider metadata (v2) ────────────────────────────────────────────────
    provider_metadata: Dict[str, Dict[str, Any]] = dc_field(default_factory=dict)
    """Maps provider name → ProviderMetadata dict for refresh tracking."""
    
    provider_data: Dict[str, Any] = dc_field(default_factory=dict)
    """Maps provider name → Raw/Normalized Provider Result Data."""


# ── Register all providers ────────────────────────────────────────────────────

def _ensure_providers_registered() -> None:
    """Register all providers once at module level."""
    from app.ai.providers import registry

    if registry.names():
        return  # already registered

    from app.ai.providers.chat_history_provider import ChatHistoryProvider
    from app.ai.providers.digital_twin_provider import DigitalTwinProvider
    from app.ai.providers.market_provider import MarketProvider
    from app.ai.providers.ml_provider import MLProvider
    from app.ai.providers.satellite_provider import SatelliteProvider
    from app.ai.providers.weather_provider import WeatherProvider
    from app.ai.providers.geesoil_provider import GEESoilProvider
    
    registry.register(DigitalTwinProvider())
    registry.register(WeatherProvider())
    registry.register(SatelliteProvider())
    registry.register(MarketProvider())
    registry.register(ChatHistoryProvider())
    registry.register(MLProvider())
    registry.register(GEESoilProvider())

# ── Context Builder ───────────────────────────────────────────────────────────

class ContextBuilder:
    """
    Assembles a StructuredContext for every inbound request.

    v2: Delegates data fetching to registered Providers.
    Preserves identical StructuredContext output.
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
        farm_id: Optional[str] = None,
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
            farm_id:      Optional specific farm (or loads active farm if omitted).
            extra_params: Domain-specific payload (crop NPK, route origin, etc.)

        Returns:
            A populated StructuredContext.
        """
        logger.info(
            "ContextBuilder.build: request_id=%s intent=%s lang=%s user=%s",
            request_id, intent, language, user_id or "anon",
        )

        _ensure_providers_registered()

        ctx = StructuredContext(
            request_id=request_id,
            timestamp=datetime.now(UTC).isoformat(),
            intent=intent,
            language=language,
            raw_message=message,
            location=location,
            extra=extra_params or {},
        )

        params: Dict[str, Any] = {
            "user_id": user_id,
            "field_id": field_id,
            "farm_id": farm_id,
            "location": location,
            "intent": intent.value,
            "extra_params": extra_params or {},
        }

        # ── Phase 1: Load Digital Twin (needed for derived location) ──────────
        await cls._run_digital_twin(ctx, params)

        # ── Phase 2: Concurrent data fetching (Weather, Satellite, Market, Chat)
        await cls._run_concurrent_providers(ctx, params)

        # ── Phase 3: ML Inference (depends on Phase 1 + 2 outputs) ────────────
        await cls._run_ml_provider(ctx, params)

        logger.info(
            "Context ready: sources=%s",
            {k: v for k, v in ctx.data_sources.items()},
        )
        return ctx

    # ── Phase 1: Digital Twin ─────────────────────────────────────────────────

    @staticmethod
    async def _run_digital_twin(
        ctx: StructuredContext,
        params: Dict[str, Any],
    ) -> None:
        """Load the Digital Twin first (provides location for other providers)."""
        from app.ai.providers import registry

        provider = registry.get("digital_twin")
        if not provider or not params.get("user_id"):
            ctx.data_sources["digital_twin"] = False
            return

        result = await provider.execute(params)

        if result.available and result.data:
            ctx.farmer = result.data.get("farmer")
            ctx.farm = result.data.get("farm")
            ctx.field = result.data.get("field")

            ctx.data_sources["farmer_profile"] = ctx.farmer is not None
            ctx.data_sources["farm_profile"] = ctx.farm is not None
            ctx.data_sources["field_profile"] = ctx.field is not None

            # Derive location from twin if not explicitly provided
            derived = result.data.get("derived_location")
            if derived and not ctx.location:
                ctx.location = derived
                params["location"] = derived
                logger.debug("ContextBuilder: derived location from twin: %s", ctx.location)

            # Propagate lat/lon for satellite provider
            if ctx.farm:
                center = ctx.farm.get("center_coordinate") or {}
                if center.get("latitude"):
                    params["latitude"] = center["latitude"]
                    params["longitude"] = center["longitude"]
                    params["location_name"] = ctx.farm.get("name", "farm")
                    params["boundary"] = ctx.farm.get("boundary")
            elif ctx.field:
                centroid = ctx.field.get("centroid") or {}
                if centroid.get("latitude"):
                    params["latitude"] = centroid["latitude"]
                    params["longitude"] = centroid["longitude"]
                    params["location_name"] = ctx.field.get("name") or ctx.location or "field"

            # Store provider metadata for refresh tracking
            ctx.provider_metadata["digital_twin"] = {
                "source": result.metadata.source,
                "last_updated": result.metadata.last_updated,
                "ttl_seconds": result.metadata.ttl_seconds,
                "freshness": result.metadata.freshness.value,
                "status": result.metadata.status,
            }
            ctx.provider_data["digital_twin"] = result.data
        else:
            ctx.data_sources["digital_twin"] = False
            ctx.data_sources["farmer_profile"] = False
            ctx.data_sources["farm_profile"] = False

    # ── Phase 2: Concurrent providers ─────────────────────────────────────────

    @staticmethod
    async def _run_concurrent_providers(
        ctx: StructuredContext,
        params: Dict[str, Any],
    ) -> None:
        """Run Weather, Satellite, Market, and ChatHistory concurrently."""
        from app.ai.providers import registry

        tasks = []
        provider_names = []

        for provider in registry.all():
            name = provider.name
            if name in ("digital_twin", "ml_inference"):
                continue

            # Market (only for MARKET intent)
            if name == "market":
                if ctx.intent == IntentType.MARKET:
                    commodity = (
                        ctx.extra.get("crop")
                        or ctx.extra.get("commodity")
                        or (ctx.field.get("current_crop") if ctx.field else None)
                        or _extract_commodity(ctx.raw_message)
                    )
                    if commodity:
                        market_params = dict(params)
                        market_params["commodity"] = commodity
                        market_params["state"] = (
                            ctx.extra.get("state")
                            or (ctx.farmer.get("state") if ctx.farmer else None)
                            or ctx.location
                        )
                        tasks.append(provider.execute(market_params))
                        provider_names.append(name)
            
            # Satellite (needs lat/lon)
            elif name == "satellite":
                if params.get("latitude") is not None:
                    tasks.append(provider.execute(params))
                    provider_names.append(name)

            # Chat history (needs user_id)
            elif name == "chat_history":
                if params.get("user_id"):
                    tasks.append(provider.execute(params))
                    provider_names.append(name)
                    
            # All other dynamic providers (weather, geesoil, etc.)
            else:
                tasks.append(provider.execute(params))
                provider_names.append(name)

        if not tasks:
            return

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(provider_names, results):
            if isinstance(result, Exception):
                logger.error("Provider '%s' raised: %s", name, result)
                ctx.data_sources[name] = False
                continue

            if result.available and result.data:
                ctx.data_sources[name] = True
                ctx.provider_metadata[name] = {
                    "source": result.metadata.source,
                    "last_updated": result.metadata.last_updated,
                    "ttl_seconds": result.metadata.ttl_seconds,
                    "freshness": result.metadata.freshness.value,
                    "status": result.metadata.status,
                }
                ctx.provider_data[name] = result.data

                # Map provider data back to StructuredContext explicit fields for backward compatibility
                if name == "weather":
                    ctx.weather = result.data.get("weather")
                    ctx.weather_advisory = result.data.get("weather_advisory")
                elif name == "satellite":
                    ctx.satellite = result.data
                elif name == "market":
                    ctx.extra["market_prices"] = result.data
                elif name == "chat_history":
                    ctx.recent_chat = result.data.get("recent_chat", [])
            else:
                ctx.data_sources[name] = False

    # ── Phase 3: ML Inference ─────────────────────────────────────────────────

    @staticmethod
    async def _run_ml_provider(
        ctx: StructuredContext,
        params: Dict[str, Any],
    ) -> None:
        """Run ML models with intent-gated execution."""
        from app.ai.providers import registry

        ml_prov = registry.get("ml_inference")
        if not ml_prov:
            return

        # Pass assembled context data to ML provider
        ml_params = dict(params)
        ml_params["weather"] = ctx.weather
        ml_params["satellite"] = ctx.satellite
        ml_params["field"] = ctx.field
        ml_params["farm"] = ctx.farm

        result = await ml_prov.execute(ml_params)

        if result.available and result.data:
            # Map ML outputs to StructuredContext (identical field names)
            if "crop_prediction" in result.data:
                ctx.crop_prediction = result.data["crop_prediction"]
                ctx.data_sources["ml_crop"] = True
            if "vehicle_prediction" in result.data:
                ctx.vehicle_prediction = result.data["vehicle_prediction"]
                ctx.data_sources["ml_vehicle"] = True
            if "yield_prediction" in result.data:
                ctx.extra["yield_prediction"] = result.data["yield_prediction"]
                ctx.data_sources["ml_yield"] = True
            if "disease_risk" in result.data:
                ctx.extra["disease_risk"] = result.data["disease_risk"]
                ctx.data_sources["ml_disease"] = True
            if "water_stress" in result.data:
                ctx.extra["water_stress"] = result.data["water_stress"]
                ctx.data_sources["ml_water"] = True

            ctx.provider_metadata["ml_inference"] = {
                "source": result.metadata.source,
                "last_updated": result.metadata.last_updated,
                "ttl_seconds": result.metadata.ttl_seconds,
                "freshness": result.metadata.freshness.value,
                "status": result.metadata.status,
            }
            ctx.provider_data["ml_inference"] = result.data


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
