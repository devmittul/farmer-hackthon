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
- If data is unavailable, honestly say so and guide the user.

==========================================================
REASONING RULES
==========================================================
- Every recommendation must explain WHY it was generated using the real context already available in the data provided.
- Reference the actual data used (e.g. weather, soil, NDVI, satellite, market).
- Never produce generic advice when supporting data exists.

==========================================================
STANDARD RESPONSE FORMAT
==========================================================
Every single AI response MUST strictly follow the layout below. 
Do NOT dump raw JSON. Use markdown, icons, headings, and bullet points. 
Omit any section under "Analysis Based On" if that specific data is not available in your prompt context.
Do NOT fabricate any value. If confidence cannot be reliably determined, display Medium. Do NOT invent percentages.
Determine field status only from available data.

[Field Status Emoji (🟢/🟡/🔴)] Field Status: [Healthy | Needs Attention | High Risk]

────────────────────────────

🌾 Recommendation

[Main recommendation]

────────────────────────────

🧠 Why This Recommendation?

[Provide 3–6 concise bullet points referencing ONLY actual data available in the prompt]

────────────────────────────

✅ Suggested Action

[Provide clear actionable steps]

────────────────────────────

⚠ Things to Monitor

[Mention important observations and risks supported by data]

────────────────────────────

📊 Analysis Based On

--------------------------------------------------
[Display ONLY the sections below if data exists. Omit the entire section and separator if empty.]

🛰 Satellite
[e.g. NDVI, EVI, Crop Health, Last Updated]

--------------------------------------------------

🌦 Weather
[e.g. Temperature, Humidity, Rain Forecast, Last Updated]

--------------------------------------------------

🌱 Soil
[e.g. Soil Type, pH, Water Holding Capacity, Source, Last Updated]

--------------------------------------------------

💹 Market
[e.g. Recommended Market, Current Price, Trend]

--------------------------------------------------

📍 Farm
[e.g. Field Area, Crop, Growth Stage]

--------------------------------------------------

🎯 Confidence
[High | Medium | Low]

--------------------------------------------------

📡 Data Sources Used
[List all providers that successfully contributed data. Do NOT hardcode provider names. Derive this dynamically from the Provider/Source or Data Source information provided in the prompt context. If a provider is unavailable or not listed, do not display it.]
✅ [Provider Name]
Status: Available
Last Updated: [Freshness]

"""


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
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {LANGUAGE_NAMES.get(language, 'English')}.
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
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {LANGUAGE_NAMES.get(language, 'English')}.
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
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {LANGUAGE_NAMES.get(language, 'English')}.
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
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {LANGUAGE_NAMES.get(language, 'English')}.
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
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {LANGUAGE_NAMES.get(language, 'English')}.
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
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {LANGUAGE_NAMES.get(language, 'English')}.
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
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {lang_name}.
"""


# ── Helper ────────────────────────────────────────────────────────────────────
def _dict_to_block(d: dict[str, Any]) -> str:
    """Convert a dict to a readable key: value block."""
    return "\n".join(f"  {k}: {v}" for k, v in d.items())


# ── Intent: FIELD INTELLIGENCE (Digital Twin) ─────────────────────────────────
# ── Intent: FIELD INTELLIGENCE (Digital Twin) ─────────────────────────────────
def _format_value(val: Any, indent: int = 0) -> str:
    """Format any nested dictionary or list cleanly."""
    spaces = " " * indent
    if isinstance(val, dict):
        lines = []
        for k, v in val.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{spaces}{k.replace('_', ' ').title()}:")
                lines.append(_format_value(v, indent + 2))
            else:
                lines.append(f"{spaces}{k.replace('_', ' ').title()}: {v}")
        return "\n".join(lines)
    elif isinstance(val, list):
        if not val:
            return f"{spaces}None"
        if isinstance(val[0], (dict, list)):
            return "\n".join(f"{spaces}- \n" + _format_value(item, indent + 2) for item in val)
        else:
            return spaces + ", ".join(str(item) for item in val)
    else:
        return f"{spaces}{val}"


def build_digital_twin_prompt_from_context(
    user_message: str,
    language: LanguageCode,
    ctx: Any,
) -> str:
    """
    Full Digital Twin context prompt.
    Automatically iterates through every available StructuredContext section.
    """
    lang_name = LANGUAGE_NAMES.get(language, "English")
    blocks = []
    
    # Iterate through all available provider data
    provider_data_dict = getattr(ctx, "provider_data", {})
    provider_metadata_dict = getattr(ctx, "provider_metadata", {})
    
    for provider_name, data in provider_data_dict.items():
        if not data:
            continue
            
        metadata = provider_metadata_dict.get(provider_name, {})
        title = provider_name.replace("_", " ").title()
        
        # Determine source
        source = "Unknown"
        if isinstance(metadata, dict):
            source = metadata.get("source", "Unknown")
        elif hasattr(metadata, "source"):
            source = getattr(metadata, "source")
            
        # Determine freshness
        freshness = "Unknown"
        if isinstance(metadata, dict):
            freshness = metadata.get("freshness", "Unknown")
        elif hasattr(metadata, "freshness"):
            freshness = getattr(metadata, "freshness")
        
        # Look for confidence
        confidence_str = ""
        if isinstance(data, dict):
            conf = data.get("confidence")
            if conf is None:
                for v in data.values():
                    if isinstance(v, dict) and "confidence" in v:
                        conf = v["confidence"]
                        break
            if conf is not None:
                confidence_str = f" | Confidence: {conf}%"
                
        # Handle chat history specially for cleaner output
        if provider_name == "chat_history" and isinstance(data, dict) and "recent_chat" in data:
            content_str = "\n".join(
                f"  Farmer: {m.get('user_said', '')}\n  Assistant: {m.get('assistant_replied', '')}"
                for m in data["recent_chat"][-3:]
            )
            if not content_str:
                continue
        else:
            content_str = _format_value(data)
            
        block = f"## {title}\nProvider/Source: {source}\nFreshness: {str(freshness).upper()}{confidence_str}\n\n{content_str}\n"
        blocks.append(block)

    all_blocks = "\n".join(blocks)

    return f"""{_system_prompt(language)}
{all_blocks}
## Farmer's Question
{user_message}

## Instructions
1. Address the farmer by name if known from the Digital Twin data.
2. Base your answer STRICTLY on the verified data above – never invent values.
3. If yield is below average or poor, explain why based on the data.
4. If disease risk is MODERATE or above, emphasise the preventive actions.
5. If water stress requires immediate irrigation, make this the first recommendation.
6. Reference the specific field/farm name and crop where relevant.
7. Keep the response actionable and practical for a smallholder farmer.
8. Make sure EVERY recommendation explains WHY it was generated using the available data (e.g., NDVI, Weather, Soil).

## Expected Output
Your entire response MUST strictly follow the STANDARD RESPONSE FORMAT described in the system instructions. Write in {lang_name}.
"""

