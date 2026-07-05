"""
KrishiMitra Backend – AI Orchestrator (v2 – Digital Twin Architecture)
=======================================================================
Central coordinator for EVERY user request.

Pipeline (in strict order):
  1.  Language Detection    → detect_language()
  2.  Intent Detection      → IntentDetector.detect()
  3.  Context Building      → ContextBuilder.build()   (weather + DB + satellite + ML)
  4.  Confidence Scoring    → ConfidenceEngine.compute()
  5.  Prompt Assembly       → prompt_builder.*           (structured facts only)
  6.  Reasoning Engine      → ReasoningEngine.generate() (ONLY AI call)
  7.  Response Formatting   → ResponseFormatter.format()
  8.  Chat History Persist  → _persist_chat()           (async, non-fatal)

Hard rules enforced here:
  • NO direct database queries from this file (delegated to ContextBuilder).
  • NO prompt strings constructed in this file (delegated to prompt_builder).
  • ReasoningEngine.generate() is called EXACTLY ONCE per request.
  • If any step fails, the orchestrator degrades gracefully; it NEVER crashes.

Backward compatibility:
  The public ``orchestrate()`` function signature is unchanged so that
  app/routes/chat.py does not need modification.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from app.ai.confidence_engine import ConfidenceEngine
from app.ai.context_builder import ContextBuilder
from app.ai.intent_detector import IntentDetector
from app.ai.reasoning_engine import ReasoningEngine
from app.ai.response_formatter import ResponseFormatter
from app.schemas.requests import IntentType, LanguageCode
from app.utils.language import detect_language

logger = logging.getLogger(__name__)


# ── Public entry point ────────────────────────────────────────────────────────

async def orchestrate(
    message: str,
    language: Optional[LanguageCode] = None,
    location: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    field_id: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main orchestration pipeline.  Called by every route that needs AI.

    Args:
        message:      Sanitised user input.
        language:     Pre-detected language (auto-detected if None).
        location:     Optional location string.
        session_id:   Conversation session ID (auto-generated if None).
        user_id:      Authenticated user's MongoDB ObjectId string (optional).
        field_id:     Specific field to load into context (optional).
        extra_params: Domain-specific parameters (NPK values, route origin, etc.)

    Returns:
        Canonical response dict matching the standard envelope.
    """
    start = datetime.now(UTC)
    request_id = str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())

    # ── 1. Language Detection ─────────────────────────────────────────────────
    if not language:
        detected = detect_language(message)
        language = detected if isinstance(detected, LanguageCode) else LanguageCode.EN

    logger.info(
        "[%s] Orchestrating: lang=%s session=%s user=%s",
        request_id[:8], language.value, session_id[:8], user_id or "anon",
    )

    # ── 2. Intent Detection ───────────────────────────────────────────────────
    intent = IntentDetector.detect(message)
    logger.info("[%s] Intent: %s", request_id[:8], intent.value)

    # ── 3. Context Building ───────────────────────────────────────────────────
    try:
        ctx = await ContextBuilder.build(
            request_id=request_id,
            intent=intent,
            message=message,
            language=language,
            location=location,
            user_id=user_id,
            field_id=field_id,
            extra_params=extra_params or {},
        )
    except Exception as exc:
        logger.error("[%s] Context build failed: %s", request_id[:8], exc)
        ctx = None

    # ── 4. Confidence Scoring ─────────────────────────────────────────────────
    confidence: Optional[Dict[str, Any]] = None
    if ctx is not None:
        try:
            confidence = ConfidenceEngine.compute(ctx)
        except Exception as exc:
            logger.warning("[%s] Confidence compute failed: %s", request_id[:8], exc)

    # ── 5. Prompt Assembly ────────────────────────────────────────────────────
    try:
        prompt = _build_prompt(intent, message, language, ctx)
    except Exception as exc:
        logger.error("[%s] Prompt build failed: %s", request_id[:8], exc)
        # Fallback: send raw message with language instruction only
        from app.ai import prompt_builder
        prompt = prompt_builder.build_chat_prompt(message, language)

    # ── 6. Reasoning Engine ───────────────────────────────────────────────────
    try:
        reply, ai_latency_ms = await ReasoningEngine.generate(prompt)
    except Exception as exc:
        logger.error("[%s] Reasoning engine failed: %s", request_id[:8], exc)
        reply = (
            "I'm having trouble connecting to the AI engine right now. "
            "Please try again in a moment."
        )
        ai_latency_ms = 0.0

    # ── 7. Collect structured data for response ───────────────────────────────
    context_data: Dict[str, Any] = {}
    if ctx:
        if ctx.weather:
            context_data["weather"] = ctx.weather
        if ctx.satellite:
            context_data["satellite"] = ctx.satellite
        if ctx.crop_prediction:
            context_data["crop_prediction"] = ctx.crop_prediction
        if ctx.vehicle_prediction:
            context_data["vehicle_prediction"] = ctx.vehicle_prediction

    # ── 8. Persist Chat History (non-fatal) ───────────────────────────────────
    elapsed_total_ms = (datetime.now(UTC) - start).total_seconds() * 1000
    await _persist_chat(
        user_id=user_id,
        session_id=session_id,
        user_message=message,
        assistant_reply=reply,
        intent=intent,
        language=language,
        context_data=context_data,
        latency_ms=ai_latency_ms,
    )

    # ── 9. Format & Return ────────────────────────────────────────────────────
    return ResponseFormatter.format(
        request_id=request_id,
        intent=intent,
        language=language,
        reply=reply,
        session_id=session_id,
        data=context_data or None,
        confidence=confidence,
        latency_ms=ai_latency_ms,
        total_latency_ms=elapsed_total_ms,
    )


# ── Prompt dispatch ───────────────────────────────────────────────────────────

def _build_prompt(
    intent: IntentType,
    message: str,
    language: LanguageCode,
    ctx: Optional[Any],
) -> str:
    """
    Dispatch prompt building to the correct prompt_builder function
    based on intent and available context.

    This is the ONLY place where prompt functions are called.
    It reads from StructuredContext; it does not fetch any data itself.
    """
    from app.ai import prompt_builder

    # ── Weather ───────────────────────────────────────────────────────────────
    if intent == IntentType.WEATHER:
        if ctx and ctx.weather:
            advisory = ctx.weather_advisory or "Normal conditions."
            return prompt_builder.build_weather_prompt(
                message, language, ctx.weather, advisory
            )
        return prompt_builder.build_chat_prompt(
            message, language,
            context={"note": "Weather data unavailable for this location."},
        )

    # ── Crop ──────────────────────────────────────────────────────────────────
    elif intent == IntentType.CROP:
        if ctx and ctx.crop_prediction:
            input_params = _field_soil_params(ctx)
            return prompt_builder.build_crop_prompt(
                message, language, ctx.crop_prediction, input_params
            )
        # No ML data — give agronomic general advice
        return prompt_builder.build_chat_prompt(
            message, language,
            context={"domain": "crop_advice"},
        )

    # ── Route ─────────────────────────────────────────────────────────────────
    elif intent == IntentType.ROUTE:
        if ctx and ctx.extra.get("route"):
            return prompt_builder.build_route_prompt(
                message, language,
                route_data=ctx.extra["route"],
                weather_data=ctx.weather,
                cargo=ctx.extra.get("cargo"),
            )
        return prompt_builder.build_chat_prompt(
            message, language,
            context={"note": "Route planning requires origin and destination."},
        )

    # ── Vehicle ───────────────────────────────────────────────────────────────
    elif intent == IntentType.VEHICLE:
        if ctx and ctx.vehicle_prediction:
            request_params = {k: v for k, v in ctx.extra.items()
                              if k in ("location", "destination", "crop_type",
                                       "quantity_tonnes", "date")}
            return prompt_builder.build_vehicle_prompt(
                message, language, ctx.vehicle_prediction, request_params
            )
        return prompt_builder.build_chat_prompt(
            message, language,
            context={"domain": "vehicle_booking"},
        )

    # ── Market ────────────────────────────────────────────────────────────────
    elif intent == IntentType.MARKET:
        return prompt_builder.build_market_prompt(
            message, language,
            prices_data=ctx.extra.get("market_prices") if ctx else None,
            crop=ctx.extra.get("crop") if ctx else None,
            location=ctx.location if ctx else None,
        )

    # ── SOS ───────────────────────────────────────────────────────────────────
    elif intent == IntentType.SOS:
        loc_str = (ctx.location or "Unknown location") if ctx else "Unknown location"
        emergency_type = _classify_emergency(message)
        return prompt_builder.build_sos_prompt(language, loc_str, emergency_type, message)

    # ── Courier ───────────────────────────────────────────────────────────────
    elif intent == IntentType.COURIER:
        return prompt_builder.build_chat_prompt(
            message, language,
            context={"request_type": "community_courier",
                     "location": ctx.location if ctx else None},
        )

    # ── Default: general chat (or full Digital Twin if field is loaded) ───────
    else:
        # If a field is loaded → use the richest possible Digital Twin prompt
        if ctx and ctx.field:
            return prompt_builder.build_digital_twin_prompt_from_context(
                message, language, ctx
            )
        # No field → personalise with farmer metadata if available
        farmer_ctx = {}
        if ctx and ctx.farmer:
            farmer_ctx = {
                "farmer_name": ctx.farmer.get("name"),
                "district": ctx.farmer.get("district"),
                "primary_crops": ctx.farmer.get("primary_crops"),
            }
        return prompt_builder.build_chat_prompt(
            message, language, context=farmer_ctx or None
        )


# ── Utilities ─────────────────────────────────────────────────────────────────

def _field_soil_params(ctx: Any) -> Dict[str, Any]:
    """Extract soil parameters from context for crop prompt."""
    params: Dict[str, Any] = {}
    if ctx.field:
        params.update({
            "Nitrogen (N)": f"{ctx.field.get('nitrogen_kg_ha', 'N/A')} kg/ha",
            "Phosphorus (P)": f"{ctx.field.get('phosphorus_kg_ha', 'N/A')} kg/ha",
            "Potassium (K)": f"{ctx.field.get('potassium_kg_ha', 'N/A')} kg/ha",
            "Soil pH": ctx.field.get("soil_ph", "N/A"),
            "Soil Type": ctx.field.get("soil_type", "N/A"),
            "Area (ha)": ctx.field.get("area_ha", "N/A"),
        })
    if ctx.weather:
        current = ctx.weather.get("current", {})
        params["Temperature (°C)"] = current.get("temperature_c", "N/A")
        params["Humidity (%)"] = current.get("humidity_pct", "N/A")
    if ctx.extra:
        params.update({
            k: v for k, v in ctx.extra.items()
            if k in ("nitrogen", "phosphorus", "potassium",
                     "temperature", "humidity", "ph", "rainfall")
        })
    return params


def _classify_emergency(message: str) -> str:
    """Simple keyword-based emergency type classifier."""
    lower = message.lower()
    if any(w in lower for w in ["fire", "aag", "jalaa"]):
        return "fire"
    if any(w in lower for w in ["flood", "baadh", "pani"]):
        return "flood"
    if any(w in lower for w in ["accident", "durghatna", "crash"]):
        return "accident"
    if any(w in lower for w in ["medical", "hospital", "sick", "bimaar"]):
        return "medical"
    return "general"


async def _persist_chat(
    user_id: Optional[str],
    session_id: str,
    user_message: str,
    assistant_reply: str,
    intent: IntentType,
    language: LanguageCode,
    context_data: Dict[str, Any],
    latency_ms: float,
) -> None:
    """Persist the chat exchange to MongoDB asynchronously (non-fatal)."""
    try:
        from app.database import get_collection

        col = get_collection("chat_history")
        await col.insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "user_message": user_message,
            "assistant_reply": assistant_reply,
            "intent": intent.value,
            "language": language.value,
            "context_data": context_data,
            "latency_ms": latency_ms,
            "created_at": datetime.now(UTC),
        })
    except Exception as exc:
        logger.error("Failed to persist chat history: %s", exc)


# ── Backward-compat: expose detect_intent for any legacy imports ──────────────
def detect_intent(message: str) -> IntentType:
    """Backward-compatible wrapper for old code that imported detect_intent directly."""
    return IntentDetector.detect(message)
