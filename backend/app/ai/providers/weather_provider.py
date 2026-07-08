"""
Weather Provider – wraps the existing weather service.

Delegates to app.ai.weather.service.fetch_weather() and
app.ai.weather.service.build_weather_advisory().
No weather logic is duplicated here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.ai.providers import BaseProvider, FreshnessLevel

logger = logging.getLogger(__name__)


class WeatherProvider(BaseProvider):
    name = "weather"
    freshness = FreshnessLevel.DYNAMIC
    default_ttl = 1800  # 30 minutes (matches existing weather_cache_ttl)

    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch weather data using the existing weather service.

        Expected params:
            location (str): Location string or "lat,lon".
            days (int): Forecast days (default 7).
            force_refresh (bool): Bypass cache.
        """
        location = params.get("location")
        if not location:
            return None

        from app.ai.weather.service import build_weather_advisory, fetch_weather

        days = params.get("days", 7)
        force_refresh = params.get("force_refresh", False)

        weather = await fetch_weather(location, days=days, force_refresh=force_refresh)
        if not weather:
            return None

        advisory = build_weather_advisory(weather)
        return {
            "weather": weather,
            "weather_advisory": advisory,
        }
