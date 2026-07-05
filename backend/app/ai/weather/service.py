"""
KrishiMitra Backend – Weather Service
========================================
Fetches structured weather data from Open-Meteo (no API key required).
Caches results in MongoDB to reduce redundant API calls.
"""
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.database import get_collection

logger = logging.getLogger(__name__)

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"

# In-memory geocode cache (lat/lon by location string)
_geocode_cache: dict[str, Optional[tuple[float, float]]] = {}


async def geocode_location(location: str) -> Optional[tuple[float, float]]:
    """
    Convert a human-readable location string into (lat, lon) via Nominatim.

    Args:
        location: Free-text place name (e.g., "Ahmedabad, Gujarat").

    Returns:
        Tuple of (latitude, longitude) or None if not found.
    """
    key = location.lower().strip()
    if key in _geocode_cache:
        return _geocode_cache[key]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                NOMINATIM_BASE,
                params={"q": location, "format": "json", "limit": 1},
                headers={"User-Agent": "KrishiMitra/1.0 (contact@krishimitra.ai)"},
            )
            response.raise_for_status()
            results = response.json()

        if not results:
            logger.warning("Geocode: no results for '%s'", location)
            _geocode_cache[key] = None
            return None

        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
        _geocode_cache[key] = (lat, lon)
        logger.debug("Geocode '%s' → (%f, %f)", location, lat, lon)
        return (lat, lon)

    except Exception as exc:
        logger.error("Geocode error for '%s': %s", location, exc)
        return None


async def fetch_weather(
    location: str,
    days: int = 3,
    force_refresh: bool = False,
) -> Optional[dict[str, Any]]:
    """
    Fetch weather from Open-Meteo for a location string, with MongoDB caching.

    Args:
        location: Human-readable place name.
        days: Number of forecast days (1-7).

    Returns:
        Structured weather dict or None on failure.
    """
    settings = get_settings()
    cache_key = f"weather:{location.lower()}:{days}"

    # ── Check MongoDB cache ───────────────────────────────────────────────────
    cache_col = None
    try:
        cache_col = get_collection("weather_cache")
        if not force_refresh:
            cached = await cache_col.find_one(
                {"cache_key": cache_key, "expires_at": {"$gt": datetime.now(UTC)}}
            )
            if cached:
                logger.debug("Weather cache HIT: %s", cache_key)
                return cached["data"]
    except Exception as e:
        logger.warning("Could not access weather cache (DB might be down): %s", e)

    # ── Geocode location ──────────────────────────────────────────────────────
    coords = await geocode_location(location)
    if not coords:
        return None

    lat, lon = coords

    # ── Fetch from Open-Meteo ─────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                OPEN_METEO_BASE,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": [
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_sum",
                        "windspeed_10m_max",
                        "relative_humidity_2m_max",
                        "weathercode",
                    ],
                    "current_weather": "true",
                    "forecast_days": max(days, 1),
                    "timezone": "auto",
                },
            )
            resp.raise_for_status()
            raw = resp.json()
    except Exception as exc:
        logger.error("Open-Meteo fetch error: %s", exc)
        return None

    # ── Parse and structure ───────────────────────────────────────────────────
    current = raw.get("current_weather", {})
    daily = raw.get("daily", {})

    # Today's humidity and rainfall come from daily[0] (current_weather lacks them)
    today_humidity = daily.get("relative_humidity_2m_max", [None])[0]
    today_rainfall = daily.get("precipitation_sum", [0])[0] or 0

    forecast = []
    dates = daily.get("time", [])
    for i, date in enumerate(dates):
        forecast.append(
            {
                "date": date,
                "temp_min_c": daily["temperature_2m_min"][i],
                "temp_max_c": daily["temperature_2m_max"][i],
                "humidity_pct": daily["relative_humidity_2m_max"][i],
                "rainfall_mm": daily["precipitation_sum"][i],
                "wind_kmh": daily["windspeed_10m_max"][i],
                "condition": _wmo_to_condition(daily["weathercode"][i]),
            }
        )

    result: dict[str, Any] = {
        "location": location,
        "latitude": lat,
        "longitude": lon,
        "current": {
            "temperature_c": current.get("temperature"),
            "wind_kmh": current.get("windspeed"),
            "condition": _wmo_to_condition(current.get("weathercode", 0)),
            "humidity_pct": today_humidity if today_humidity is not None else 60,
            "rainfall_mm": today_rainfall,
        },
        "forecast": forecast,
    }

    # ── Store in cache ────────────────────────────────────────────────────────
    if cache_col is not None:
        try:
            expires_at = datetime.now(UTC) + timedelta(seconds=settings.weather_cache_ttl)
            await cache_col.update_one(
                {"cache_key": cache_key},
                {
                    "$set": {
                        "cache_key": cache_key,
                        "data": result,
                        "expires_at": expires_at,
                        "created_at": datetime.now(UTC),
                    }
                },
                upsert=True,
            )
        except Exception as e:
            logger.warning("Failed to store weather cache: %s", e)

    logger.info("Weather fetched and cached for '%s'", location)
    return result


def _wmo_to_condition(code: int) -> str:
    """Map WMO weather interpretation codes to human-readable strings."""
    _MAP = {
        0: "Clear Sky",
        1: "Mainly Clear",
        2: "Partly Cloudy",
        3: "Overcast",
        45: "Foggy",
        48: "Icy Fog",
        51: "Light Drizzle",
        53: "Moderate Drizzle",
        55: "Heavy Drizzle",
        61: "Light Rain",
        63: "Moderate Rain",
        65: "Heavy Rain",
        71: "Light Snow",
        73: "Moderate Snow",
        75: "Heavy Snow",
        80: "Light Showers",
        81: "Moderate Showers",
        82: "Violent Showers",
        95: "Thunderstorm",
        99: "Thunderstorm with Hail",
    }
    return _MAP.get(code, "Unknown")


def build_weather_advisory(weather: dict[str, Any]) -> str:
    """
    Generate a concise weather advisory string from structured weather data.
    Used to pass factual context into the Gemini prompt.
    """
    current = weather.get("current", {})
    forecast = weather.get("forecast", [])

    advisories = []
    temp = current.get("temperature_c")
    if temp is not None:
        if temp > 38:
            advisories.append("Extreme heat – avoid midday outdoor work.")
        elif temp < 10:
            advisories.append("Cold conditions – protect frost-sensitive crops.")

    for day in forecast:
        if day.get("rainfall_mm", 0) > 50:
            advisories.append(
                f"Heavy rain expected on {day['date']} ({day['rainfall_mm']}mm)."
            )

    return " ".join(advisories) if advisories else "Weather conditions appear normal for farming."
