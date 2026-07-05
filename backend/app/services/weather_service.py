"""
KrishiMitra Backend – Weather Service (Application Layer)
==========================================================
Thin service layer over the weather AI module.
Adds Gemini explanation to raw weather data.
"""
import logging
from typing import Any

from app.ai.reasoning_engine import ReasoningEngine
from app.ai import prompt_builder
from app.ai.weather.service import build_weather_advisory, fetch_weather
from app.schemas.requests import WeatherRequest

logger = logging.getLogger(__name__)


class WeatherService:
    """Handles weather queries with AI explanation."""

    @staticmethod
    async def get_weather_with_advisory(payload: WeatherRequest) -> dict[str, Any]:
        """
        Fetch structured weather data + generate Gemini advisory.

        Args:
            payload: Validated weather request.

        Returns:
            Weather data dict with AI-generated explanation.

        Raises:
            ValueError: If location cannot be geocoded.
        """
        weather = await fetch_weather(payload.location, days=payload.days, force_refresh=payload.force_refresh)
        if not weather:
            raise ValueError(
                f"Could not retrieve weather for '{payload.location}'. "
                "Please check the location name."
            )

        advisory = build_weather_advisory(weather)

        # ── Gemini Advisory ───────────────────────────────────────────────────
        user_question = (
            f"What is the weather like in {payload.location} for the next "
            f"{payload.days} days and how will it affect my farming?"
        )
        prompt = prompt_builder.build_weather_prompt(
            user_message=user_question,
            language=payload.language,
            weather_data=weather,
            advisory=advisory,
        )

        try:
            explanation, _ = await ReasoningEngine.generate(prompt)
        except Exception as exc:
            logger.error("ReasoningEngine weather explanation failed: %s", exc)
            explanation = advisory

        # ── Build typed forecast list ─────────────────────────────────────────
        forecast = [
            {
                "date": d["date"],
                "temp_min_c": d["temp_min_c"],
                "temp_max_c": d["temp_max_c"],
                "humidity_pct": d["humidity_pct"],
                "rainfall_mm": d["rainfall_mm"],
                "wind_kmh": d["wind_kmh"],
                "condition": d["condition"],
            }
            for d in weather.get("forecast", [])
        ]

        return {
            "location": weather["location"],
            "latitude": weather["latitude"],
            "longitude": weather["longitude"],
            "current": weather["current"],
            "forecast": forecast,
            "advisory": advisory,
            "explanation": explanation,
        }
