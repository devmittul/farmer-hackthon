"""
KrishiMitra Backend – Prompt Builder
======================================
All Gemini prompts are assembled here.
Never concatenate strings randomly in routes or services.
Every prompt follows a strict structure:
  SYSTEM → Context → Facts → User Request → Instructions → Expected Output
"""
from typing import Any, Optional

from app.schemas.requests import IntentType, LanguageCode
from app.utils.language import LANGUAGE_NAMES


# ── Base system context ────────────────────────────────────────────────────────
_SYSTEM_BASE = """You are KrishiMitra AI, an intelligent agricultural and rural mobility assistant.
You help Indian farmers with crop advice, weather insights, transport logistics, and emergency guidance.
You are empathetic, practical, and always grounded in the factual data provided to you.
CRITICAL RULES:
- NEVER invent facts. Only use the structured data provided in this prompt.
- Always reply in the user's language: {language_name}.
- Keep responses concise and actionable.
- Format replies clearly with bullet points or numbered lists when appropriate.
- If data is unavailable, honestly say so and guide the user."""


def _system_prompt(language: LanguageCode) -> str:
    lang_name = LANGUAGE_NAMES.get(language, "English")
    return _SYSTEM_BASE.format(language_name=lang_name)


# ── Intent: CHAT ─────────────────────────────────────────────────────────────
def build_chat_prompt(
    user_message: str,
    language: LanguageCode,
    context: Optional[dict[str, Any]] = None,
) -> str:
    """General-purpose conversational prompt."""
    context_block = ""
    if context:
        context_block = f"\n## Additional Context\n{_dict_to_block(context)}\n"

    return f"""{_system_prompt(language)}

## User Message
{user_message}
{context_block}
## Instructions
Provide a helpful, factual response. If the question is agricultural or mobility-related,
draw on established agronomic knowledge. Do not speculate beyond what is known.

## Expected Output
A clear, concise response in {LANGUAGE_NAMES.get(language, 'English')}.
"""


# ── Intent: WEATHER ───────────────────────────────────────────────────────────
def build_weather_prompt(
    user_message: str,
    language: LanguageCode,
    weather_data: dict[str, Any],
    advisory: str,
) -> str:
    """Weather explanation prompt with structured data injected."""
    forecast_lines = "\n".join(
        f"  • {d['date']}: {d['condition']}, {d['temp_min_c']}–{d['temp_max_c']}°C, "
        f"Rain: {d['rainfall_mm']}mm, Humidity: {d['humidity_pct']}%, Wind: {d['wind_kmh']}km/h"
        for d in weather_data.get("forecast", [])
    )

    current = weather_data.get("current", {})

    return f"""{_system_prompt(language)}

## Verified Weather Data for {weather_data.get('location', 'the requested location')}
Current: {current.get('temperature_c', 'N/A')}°C, {current.get('condition', 'N/A')}, Wind: {current.get('wind_kmh', 'N/A')} km/h

### Forecast
{forecast_lines}

### Advisory
{advisory}

## User Question
{user_message}

## Instructions
1. Interpret the weather data for a farmer's daily decisions.
2. Highlight any risks to crops or transport.
3. Give specific, actionable advice based ONLY on the data above.
4. Do NOT add weather facts not present above.

## Expected Output
A structured weather summary and farming advisory in {LANGUAGE_NAMES.get(language, 'English')}.
"""


# ── Intent: CROP ─────────────────────────────────────────────────────────────
def build_crop_prompt(
    user_message: str,
    language: LanguageCode,
    prediction: dict[str, Any],
    input_params: dict[str, Any],
) -> str:
    """Crop recommendation explanation prompt."""
    alternatives_str = ", ".join(prediction.get("alternatives", [])) or "None"

    return f"""{_system_prompt(language)}

## ML Model Prediction (Verified)
Recommended Crop: {prediction['recommended_crop'].upper()}
Confidence: {prediction['confidence']}%
Alternative crops: {alternatives_str}

## Soil & Climate Parameters Used
{_dict_to_block(input_params)}

## User Question
{user_message}

## Instructions
1. Explain WHY this crop is recommended given the specific soil and climate parameters.
2. Mention 3-5 practical farming tips for this crop.
3. Briefly explain why the alternatives were ranked lower.
4. Mention any soil amendments that could improve suitability.
5. Do NOT suggest crops not in the prediction above.

## Expected Output
A detailed crop recommendation explanation in {LANGUAGE_NAMES.get(language, 'English')} with practical tips.
"""


# ── Intent: ROUTE ─────────────────────────────────────────────────────────────
def build_route_prompt(
    user_message: str,
    language: LanguageCode,
    route_data: dict[str, Any],
    weather_data: Optional[dict[str, Any]] = None,
    cargo: Optional[str] = None,
) -> str:
    """Route planning explanation prompt with optional weather context."""
    weather_block = ""
    if weather_data:
        current = weather_data.get("current", {})
        forecast = weather_data.get("forecast", [{}])[0]
        weather_block = f"""
## Weather Along Route
Current at origin: {current.get('condition', 'N/A')}, {current.get('temperature_c', 'N/A')}°C
Tomorrow forecast: {forecast.get('condition', 'N/A')}, Rain: {forecast.get('rainfall_mm', 0)}mm
"""

    cargo_block = f"\n## Cargo Being Transported\n{cargo}\n" if cargo else ""

    return f"""{_system_prompt(language)}

## Route Plan (Verified)
Origin: {route_data.get('origin_coords')}
Destination: {route_data.get('destination_coords')}
Total Distance: {route_data.get('total_distance_km')} km
Estimated Time: {route_data.get('total_duration_min')} minutes
{weather_block}{cargo_block}
## User Question
{user_message}

## Instructions
1. Summarise the route in plain language.
2. If cargo is perishable, comment on time-sensitivity.
3. If rain is forecast, advise on road safety and delays.
4. Mention estimated fuel cost (assume ₹12/km for trucks).
5. Do NOT add roads or distances not in the verified data above.

## Expected Output
A practical transport advisory in {LANGUAGE_NAMES.get(language, 'English')}.
"""


# ── Intent: VEHICLE ───────────────────────────────────────────────────────────
def build_vehicle_prompt(
    user_message: str,
    language: LanguageCode,
    prediction: dict[str, Any],
    request_params: dict[str, Any],
) -> str:
    """Vehicle demand explanation prompt."""
    vehicles_str = ", ".join(prediction.get("recommended_vehicles", []))
    cost = prediction.get("estimated_cost_inr", {})

    return f"""{_system_prompt(language)}

## ML Vehicle Demand Prediction (Verified)
Demand Level: {prediction['demand_level']}
Recommended Vehicles: {vehicles_str}
Estimated Cost: ₹{cost.get('min', 'N/A')} – ₹{cost.get('max', 'N/A')}
Best Time Window: {prediction.get('best_time_window', 'N/A')}

## Request Details
{_dict_to_block(request_params)}

## User Question
{user_message}

## Instructions
1. Explain the demand level and what drives it.
2. Justify the vehicle recommendations.
3. Give cost-saving tips for the farmer.
4. Advise on booking logistics.

## Expected Output
Practical vehicle booking guidance in {LANGUAGE_NAMES.get(language, 'English')}.
"""


# ── Intent: SOS ───────────────────────────────────────────────────────────────
def build_sos_prompt(
    language: LanguageCode,
    location_str: str,
    emergency_type: str,
    description: str,
) -> str:
    """Emergency SOS guidance prompt."""
    return f"""{_system_prompt(language)}

## Emergency Alert Received
Type: {emergency_type}
Location: {location_str}
Description: {description}

## Instructions
1. Acknowledge the emergency with empathy.
2. Provide immediate safety steps relevant to the emergency type.
3. List the key emergency numbers for India (112, 1962 for Kisan, etc.).
4. Stay calm and reassuring in tone.

## Expected Output
Emergency guidance in {LANGUAGE_NAMES.get(language, 'English')}. Be concise and actionable.
"""


# ── Intent: MARKET ────────────────────────────────────────────────────────────
def build_market_prompt(
    user_message: str,
    language: LanguageCode,
    prices_data: Optional[Dict[str, Any]] = None,
    crop: Optional[str] = None,
    location: Optional[str] = None,
) -> str:
    """Market insights prompt (data-grounded where available)."""
    lang_name = LANGUAGE_NAMES.get(language, "English")
    
    price_block = ""
    if prices_data:
        is_live = prices_data.get("is_live", False)
        source = prices_data.get("source", "KrishiMitra estimated")
        trend = prices_data.get("trend", "stable")
        
        prices_list = prices_data.get("prices", [])
        if prices_list:
            p = prices_list[0]
            price_block = f"""
## Market Prices (Data Source: {source})
Status: {"Live (data.gov.in)" if is_live else "Curated historical estimate"}
Commodity: {prices_data.get("commodity", crop or "Unknown")}
Location: {prices_data.get("state", location or p.get("state") or p.get("district") or "India")}

Price Range: ₹{p.get("min_price", "?")} – ₹{p.get("max_price", "?")} per quintal
Modal Price: ₹{p.get("modal_price", "?")} per quintal
Market Trend: {trend.upper()}
Advice: {prices_data.get("advice", "")}
"""
    
    crop_block = f"\nCrop of interest: {crop}" if crop and not prices_data else ""
    loc_block = f"\nMarket region: {location}" if location and not prices_data else ""

    return f"""{_system_prompt(language)}

## Market Query
{user_message}
{crop_block}{loc_block}{price_block}

## Instructions
1. Answer the farmer's question regarding market prices.
2. If real 'Market Prices' data is provided above, use those EXACT numbers. Do NOT fabricate or estimate prices.
3. If prices are historical/estimated, clearly state that these are seasonal estimates and they should verify at the local mandi.
4. Mention the market trend (rising/falling) if available and provide the actionable advice given in the data.
5. Remind the user to use eNAM or local mandi boards for trading.
6. Keep the response concise and supportive.

## Expected Output
Market insight guidance in {lang_name}.
"""


# ── Helper ────────────────────────────────────────────────────────────────────
def _dict_to_block(d: dict[str, Any]) -> str:
    """Convert a dict to a readable key: value block."""
    return "\n".join(f"  {k}: {v}" for k, v in d.items())


# ── Intent: FIELD INTELLIGENCE (Digital Twin) ─────────────────────────────────
def build_field_intelligence_prompt(
    user_message: str,
    language: LanguageCode,
    farmer: Optional[dict[str, Any]],
    field: Optional[dict[str, Any]],
    weather: Optional[dict[str, Any]],
    satellite: Optional[dict[str, Any]],
    yield_prediction: Optional[dict[str, Any]] = None,
    disease_risk: Optional[dict[str, Any]] = None,
    water_stress: Optional[dict[str, Any]] = None,
    recent_chat: Optional[list] = None,
) -> str:
    """
    Full Digital Twin context prompt.

    Injects farmer identity, field profile, weather, satellite NDVI,
    yield prediction, disease risk, and water stress into a single
    structured prompt for comprehensive field-specific responses.
    """
    lang_name = LANGUAGE_NAMES.get(language, "English")

    # ── Farmer block ──────────────────────────────────────────────────────────
    farmer_block = ""
    if farmer:
        farmer_block = f"""
## Farmer Profile
Name: {farmer.get("name", "Unknown")}
Language: {farmer.get("preferred_language", "en")}
District: {farmer.get("district", "Unknown")}
State: {farmer.get("state", "Unknown")}
Primary Crops: {", ".join(farmer.get("primary_crops", [])) or "Not specified"}
"""

    # ── Field block ───────────────────────────────────────────────────────────
    field_block = ""
    if field:
        field_block = f"""
## Field Profile
Field: {field.get("name", "Unknown")} | Area: {field.get("area_ha", "?")} ha
Soil Type: {field.get("soil_type", "Unknown")} | pH: {field.get("soil_ph", "?")}
Nutrients: N={field.get("nitrogen_kg_ha", "?")} P={field.get("phosphorus_kg_ha", "?")} K={field.get("potassium_kg_ha", "?")} kg/ha
Irrigation: {field.get("irrigation_type", "Unknown")} | Water source: {field.get("water_source", "Unknown")}
Current Crop: {field.get("current_crop", "Unknown")} ({field.get("current_variety", "")})
Sowing Date: {field.get("sowing_date", "Unknown")} | Expected Harvest: {field.get("expected_harvest_date", "Unknown")}
Growth Stage: {field.get("growth_stage", "Unknown")}
"""

    # ── Weather block ─────────────────────────────────────────────────────────
    weather_block = ""
    if weather:
        cur = weather.get("current", {})
        forecast_lines = "\n".join(
            f"  • {d['date']}: {d.get('condition','?')}, "
            f"{d.get('temp_min_c','?')}–{d.get('temp_max_c','?')}°C, "
            f"Rain: {d.get('rainfall_mm', 0)}mm"
            for d in weather.get("forecast", [])[:3]
        )
        weather_block = f"""
## Live Weather (Verified – Open-Meteo)
Current: {cur.get("temperature_c", "?")}°C, {cur.get("condition", "?")}, Humidity: {cur.get("humidity_pct", "?")}%
3-Day Forecast:
{forecast_lines}
"""

    # ── Satellite block ───────────────────────────────────────────────────────
    satellite_block = ""
    if satellite and satellite.get("ndvi") is not None:
        satellite_block = f"""
## Satellite Data (Verified – Sentinel-2/GEE)
NDVI: {satellite.get("ndvi", "?")} | Crop Health: {satellite.get("crop_health", "?")}
Vegetation Index: {satellite.get("vegetation_index", "?")}%
Harvest Stage: {satellite.get("harvest_detection", "?")}
Analysis Date: {satellite.get("analysis_date", "?")}
"""

    # ── ML Intelligence block ─────────────────────────────────────────────────
    intelligence_block = ""
    if yield_prediction:
        intelligence_block += f"""
## ML Yield Prediction (Verified)
Expected Yield: {yield_prediction.get("yield_kg_per_ha", "?")} kg/ha
Total Field Yield: {yield_prediction.get("total_yield_kg", "?")} kg
Category: {yield_prediction.get("category", "?").upper()} | Confidence: {yield_prediction.get("confidence", "?")}%
"""

    if disease_risk:
        intelligence_block += f"""
## ML Disease Risk Assessment (Verified)
Risk Level: {disease_risk.get("risk_level", "?")} | Risk Score: {disease_risk.get("risk_score", "?")}%
Common Diseases: {", ".join(disease_risk.get("common_diseases", [])) or "None detected"}
Recommended Actions: {" | ".join(disease_risk.get("preventive_actions", [])[:2])}
"""

    if water_stress:
        intelligence_block += f"""
## Water Stress Assessment (Verified)
Stress Level: {water_stress.get("stress_level", "?").upper()} | Irrigate Now: {water_stress.get("irrigate_now", False)}
Water Need: {water_stress.get("water_need_mm", 0)}mm | ET Estimate (7d): {water_stress.get("et_estimate_mm", "?")}mm
Recommendation: {water_stress.get("recommendation", "")}
"""

    # ── Conversation history ──────────────────────────────────────────────────
    history_block = ""
    if recent_chat:
        history_lines = "\n".join(
            f"  Farmer: {m.get('user_said', '')}\n  Assistant: {m.get('assistant_replied', '')}"
            for m in recent_chat[-3:]
        )
        history_block = f"\n## Recent Conversation\n{history_lines}\n"

    return f"""{_system_prompt(language)}
{farmer_block}{field_block}{weather_block}{satellite_block}{intelligence_block}{history_block}
## Farmer's Question
{user_message}

## Instructions
1. Address the farmer by name if known.
2. Base your answer STRICTLY on the verified data above – never invent values.
3. If yield is below_average or poor, explain why based on the data.
4. If disease risk is MODERATE or above, emphasise the preventive actions.
5. If water stress requires immediate irrigation, make this the first recommendation.
6. Reference the specific field name and crop where relevant.
7. Keep the response actionable and practical for a smallholder farmer.

## Expected Output
A personalised, field-specific advisory in {lang_name}. Be concise. Use bullet points.
"""


# ── Digital Twin context builder helper ───────────────────────────────────────
def build_digital_twin_prompt_from_context(
    user_message: str,
    language: LanguageCode,
    ctx: Any,
) -> str:
    """
    Convenience wrapper: build the full Digital Twin prompt directly
    from a StructuredContext object.

    Args:
        user_message: Raw user input.
        language:     Detected language.
        ctx:          StructuredContext produced by ContextBuilder.

    Returns:
        Fully assembled prompt string.
    """
    return build_field_intelligence_prompt(
        user_message=user_message,
        language=language,
        farmer=getattr(ctx, "farmer", None),
        field=getattr(ctx, "field", None),
        weather=getattr(ctx, "weather", None),
        satellite=getattr(ctx, "satellite", None),
        yield_prediction=ctx.extra.get("yield_prediction") if hasattr(ctx, "extra") else None,
        disease_risk=ctx.extra.get("disease_risk") if hasattr(ctx, "extra") else None,
        water_stress=ctx.extra.get("water_stress") if hasattr(ctx, "extra") else None,
        recent_chat=getattr(ctx, "recent_chat", None),
    )

