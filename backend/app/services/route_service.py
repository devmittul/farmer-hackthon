"""
KrishiMitra Backend – Route Service
=====================================
Business logic for route planning.
"""
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from app.ai.reasoning_engine import ReasoningEngine
from app.ai import prompt_builder
from app.ai.maps.service import plan_route
from app.ai.weather.service import build_weather_advisory, fetch_weather
from app.database import get_collection
from app.schemas.requests import RoutePlanRequest

logger = logging.getLogger(__name__)


class RouteService:
    """Handles route planning with weather context and Gemini advisory."""

    @staticmethod
    async def plan_and_explain(
        payload: RoutePlanRequest,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Plan a route using OSRM, fetch weather context, then explain via Gemini.

        Args:
            payload: Validated route planning request.
            user_id: Optional authenticated user ID.

        Returns:
            Structured response with route data + advisory.
        """
        logger.info("Planning route: %s → %s", payload.origin, payload.destination)

        # ── Route Data ────────────────────────────────────────────────────────
        route = await plan_route(
            origin=payload.origin,
            destination=payload.destination,
            vehicle_type=payload.vehicle_type or "car",
        )
        if not route:
            raise ValueError(
                f"Could not plan route from '{payload.origin}' to '{payload.destination}'. "
                "Please check the location names and try again."
            )

        # ── Weather Context (origin location) ─────────────────────────────────
        weather = await fetch_weather(payload.origin, days=2)
        advisory = build_weather_advisory(weather) if weather else "Weather data unavailable."

        # ── Build Prompt ──────────────────────────────────────────────────────
        user_question = (
            f"Plan my route from {payload.origin} to {payload.destination}. "
            f"I'm transporting {payload.cargo or 'general goods'} via {payload.vehicle_type}."
        )
        prompt = prompt_builder.build_route_prompt(
            user_message=user_question,
            language=payload.language,
            route_data=route,
            weather_data=weather,
            cargo=payload.cargo,
        )

        # ── Reasoning Engine Explanation ─────────────────────────────────────
        try:
            explanation, _ = await ReasoningEngine.generate(prompt)
        except Exception as exc:
            logger.error("ReasoningEngine route explanation failed: %s", exc)
            explanation = (
                f"Route: {route['total_distance_km']}km, "
                f"~{route['total_duration_min']:.0f} min. "
                "AI advisory temporarily unavailable."
            )

        # ── Build step models ─────────────────────────────────────────────────
        steps = [
            {
                "instruction": s["instruction"],
                "distance_km": s["distance_km"],
                "duration_min": s["duration_min"],
            }
            for s in route.get("steps", [])[:20]  # Limit to 20 turns
        ]

        # ── Persist ───────────────────────────────────────────────────────────
        await _persist_route(user_id, payload, route)

        return {
            "origin_coords": route["origin_coords"],
            "destination_coords": route["destination_coords"],
            "total_distance_km": route["total_distance_km"],
            "total_duration_min": route["total_duration_min"],
            "steps": steps,
            "road_quality_advisory": advisory,
            "explanation": explanation,
        }


async def _persist_route(
    user_id: Optional[str],
    payload: RoutePlanRequest,
    route: dict[str, Any],
) -> None:
    try:
        col = get_collection("routes")
        await col.insert_one(
            {
                "user_id": user_id,
                "origin": payload.origin,
                "destination": payload.destination,
                "total_distance_km": route["total_distance_km"],
                "total_duration_min": route["total_duration_min"],
                "route_data": route,
                "created_at": datetime.now(UTC),
            }
        )
    except Exception as exc:
        logger.error("Failed to persist route: %s", exc)
