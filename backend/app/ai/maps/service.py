"""
KrishiMitra Backend – Maps & Routing Service
=============================================
Geocoding via Nominatim (OpenStreetMap).
Routing via OSRM public demo server.
No Google Maps. No API keys required.
"""
import logging
from typing import Any, List, Optional

import httpx

from app.ai.weather.service import geocode_location  # reuse geocoder

logger = logging.getLogger(__name__)

OSRM_BASE = "https://router.project-osrm.org/route/v1"


async def plan_route(
    origin: str,
    destination: str,
    vehicle_type: str = "car",
) -> Optional[dict[str, Any]]:
    """
    Plan a driving route between two locations using OSRM.

    Args:
        origin: Free-text origin location.
        destination: Free-text destination location.
        vehicle_type: "car" | "bike" | "foot".

    Returns:
        Structured route dict with steps, distance, and duration, or None.
    """
    origin_coords = await geocode_location(origin)
    dest_coords = await geocode_location(destination)

    if not origin_coords or not dest_coords:
        logger.warning("Could not geocode route endpoints: %s → %s", origin, destination)
        return None

    o_lat, o_lon = origin_coords
    d_lat, d_lon = dest_coords

    # OSRM profile mapping
    profile_map = {"car": "driving", "bike": "cycling", "foot": "walking"}
    profile = profile_map.get(vehicle_type.lower(), "driving")

    url = f"{OSRM_BASE}/{profile}/{o_lon},{o_lat};{d_lon},{d_lat}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                url,
                params={
                    "steps": "true",
                    "geometries": "geojson",
                    "overview": "full",
                    "annotations": "false",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.error("OSRM routing error: %s", exc)
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        logger.warning("OSRM returned no routes: %s", data.get("code"))
        return None

    route = data["routes"][0]
    legs = route.get("legs", [{}])

    steps: List[dict[str, Any]] = []
    for leg in legs:
        for step in leg.get("steps", []):
            maneuver = step.get("maneuver", {})
            steps.append(
                {
                    "instruction": _osrm_instruction(maneuver),
                    "distance_km": round(step.get("distance", 0) / 1000, 2),
                    "duration_min": round(step.get("duration", 0) / 60, 1),
                }
            )

    return {
        "origin_coords": {"lat": o_lat, "lon": o_lon},
        "destination_coords": {"lat": d_lat, "lon": d_lon},
        "total_distance_km": round(route.get("distance", 0) / 1000, 2),
        "total_duration_min": round(route.get("duration", 0) / 60, 1),
        "steps": steps,
        "geometry": route.get("geometry"),
    }


def _osrm_instruction(maneuver: dict[str, Any]) -> str:
    """Convert OSRM maneuver dict to a human-readable instruction string."""
    mtype = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")
    if modifier:
        return f"{mtype.replace('-', ' ').title()} {modifier}".strip()
    return mtype.replace("-", " ").title() or "Continue"
