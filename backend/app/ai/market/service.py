"""
KrishiMitra Backend – Market Price Service
===========================================
Fetches live mandi/commodity prices for Indian agricultural markets.

Data Sources (priority order):
  1. data.gov.in → Agmarknet commodity prices API (requires API key)
  2. MongoDB cache → Prices fetched within last 6 hours
  3. Deterministic seasonal fallback → Curated price ranges by season/region

Architecture rule:
  This service NEVER calls the AI Reasoning Engine.
  It returns structured price data as deterministic facts.
  The Orchestrator passes those facts to the Reasoning Engine for explanation.

Supported commodities (major Indian crops):
  Rice, Wheat, Maize, Onion, Tomato, Potato, Soybean, Cotton, Sugarcane,
  Groundnut, Mustard, Chickpea, Lentil, Tur Dal, Moong, Bajra, Jowar

Usage:
    prices = await fetch_market_prices(
        commodity="wheat",
        state="Punjab",
        max_age_hours=6,
    )
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


# ── Curated price database (₹/quintal) ─────────────────────────────────────
# Data sourced from AGMARKNET/eNAM historical averages (Kharif 2024–Rabi 2025).
# Updated quarterly. Used as fallback when live API is unavailable.
#
# Structure: { commodity: { state: { "min": int, "max": int, "modal": int } } }
#
_PRICE_DB: Dict[str, Dict[str, Dict[str, int]]] = {
    "wheat": {
        "default":      {"min": 2100, "max": 2500, "modal": 2275},
        "punjab":       {"min": 2175, "max": 2350, "modal": 2250},
        "haryana":      {"min": 2175, "max": 2380, "modal": 2275},
        "uttar pradesh":{"min": 2100, "max": 2450, "modal": 2200},
        "madhya pradesh":{"min": 2100, "max": 2400, "modal": 2200},
        "rajasthan":    {"min": 2000, "max": 2300, "modal": 2150},
    },
    "rice": {
        "default":      {"min": 2100, "max": 3200, "modal": 2600},
        "punjab":       {"min": 2200, "max": 3000, "modal": 2600},
        "andhra pradesh":{"min": 2300, "max": 3500, "modal": 2900},
        "west bengal":  {"min": 2000, "max": 3200, "modal": 2500},
        "tamil nadu":   {"min": 2500, "max": 3800, "modal": 3100},
        "telangana":    {"min": 2300, "max": 3400, "modal": 2800},
    },
    "maize": {
        "default":      {"min": 1850, "max": 2200, "modal": 2000},
        "karnataka":    {"min": 1900, "max": 2300, "modal": 2050},
        "andhra pradesh":{"min": 1850, "max": 2250, "modal": 2000},
        "maharashtra":  {"min": 1800, "max": 2200, "modal": 1950},
    },
    "onion": {
        "default":      {"min": 1200, "max": 4500, "modal": 2200},
        "maharashtra":  {"min": 1000, "max": 5000, "modal": 2400},
        "madhya pradesh":{"min": 1100, "max": 4000, "modal": 2000},
        "karnataka":    {"min": 1200, "max": 4500, "modal": 2200},
        "gujarat":      {"min": 1000, "max": 3800, "modal": 2100},
    },
    "tomato": {
        "default":      {"min": 800, "max": 8000, "modal": 2500},
        "karnataka":    {"min": 600, "max": 9000, "modal": 3000},
        "andhra pradesh":{"min": 700, "max": 8500, "modal": 2800},
        "maharashtra":  {"min": 900, "max": 7500, "modal": 2400},
    },
    "potato": {
        "default":      {"min": 900, "max": 2400, "modal": 1500},
        "uttar pradesh":{"min": 800, "max": 2200, "modal": 1400},
        "west bengal":  {"min": 900, "max": 2500, "modal": 1500},
        "punjab":       {"min": 1000, "max": 2800, "modal": 1700},
    },
    "soybean": {
        "default":      {"min": 4000, "max": 5200, "modal": 4600},
        "madhya pradesh":{"min": 4100, "max": 5400, "modal": 4700},
        "maharashtra":  {"min": 3900, "max": 5200, "modal": 4500},
        "rajasthan":    {"min": 3800, "max": 5000, "modal": 4400},
    },
    "cotton": {
        "default":      {"min": 6200, "max": 7800, "modal": 7000},
        "gujarat":      {"min": 6400, "max": 8000, "modal": 7200},
        "maharashtra":  {"min": 6200, "max": 7800, "modal": 7000},
        "telangana":    {"min": 6000, "max": 7600, "modal": 6800},
    },
    "sugarcane": {
        "default":      {"min": 315,  "max": 380,  "modal": 350},
        "uttar pradesh":{"min": 350,  "max": 380,  "modal": 365},
        "maharashtra":  {"min": 315,  "max": 370,  "modal": 340},
        "karnataka":    {"min": 305,  "max": 370,  "modal": 335},
    },
    "groundnut": {
        "default":      {"min": 5200, "max": 7000, "modal": 6000},
        "gujarat":      {"min": 5500, "max": 7200, "modal": 6200},
        "andhra pradesh":{"min": 5200, "max": 7000, "modal": 6000},
        "rajasthan":    {"min": 5000, "max": 6800, "modal": 5800},
    },
    "mustard": {
        "default":      {"min": 5100, "max": 6200, "modal": 5600},
        "rajasthan":    {"min": 5200, "max": 6400, "modal": 5800},
        "haryana":      {"min": 5100, "max": 6200, "modal": 5650},
        "madhya pradesh":{"min": 5000, "max": 6000, "modal": 5500},
    },
    "chickpea": {
        "default":      {"min": 5200, "max": 6200, "modal": 5700},
        "madhya pradesh":{"min": 5300, "max": 6400, "modal": 5800},
        "rajasthan":    {"min": 5100, "max": 6000, "modal": 5600},
        "uttar pradesh":{"min": 5000, "max": 6200, "modal": 5550},
    },
    "lentil": {
        "default":      {"min": 6000, "max": 7500, "modal": 6700},
        "madhya pradesh":{"min": 6200, "max": 7800, "modal": 7000},
        "uttar pradesh":{"min": 5800, "max": 7200, "modal": 6500},
    },
    "bajra": {
        "default":      {"min": 2100, "max": 2600, "modal": 2350},
        "rajasthan":    {"min": 2000, "max": 2500, "modal": 2250},
        "haryana":      {"min": 2150, "max": 2650, "modal": 2400},
    },
    "jowar": {
        "default":      {"min": 2900, "max": 3400, "modal": 3150},
        "maharashtra":  {"min": 2800, "max": 3400, "modal": 3100},
        "karnataka":    {"min": 2900, "max": 3500, "modal": 3200},
    },
    "turmeric": {
        "default":      {"min": 8000, "max": 18000, "modal": 12000},
        "andhra pradesh":{"min": 9000, "max": 20000, "modal": 14000},
        "telangana":    {"min": 8500, "max": 18000, "modal": 13000},
    },
    "cotton seed": {
        "default":      {"min": 900,  "max": 1400,  "modal": 1100},
    },
    "moong": {
        "default":      {"min": 6800, "max": 8500, "modal": 7500},
        "rajasthan":    {"min": 6500, "max": 8200, "modal": 7200},
        "maharashtra":  {"min": 6900, "max": 8700, "modal": 7600},
    },
}

# Aliases (normalise alternate names)
_ALIASES: Dict[str, str] = {
    "paddy": "rice", "dhan": "rice", "chawal": "rice",
    "gehun": "wheat", "makka": "maize", "corn": "maize",
    "pyaz": "onion", "tamatar": "tomato", "aloo": "potato",
    "sarson": "mustard", "chana": "chickpea", "masoor": "lentil",
    "arhar": "lentil", "tur": "lentil",
    "mungbean": "moong", "mung": "moong",
}


def _normalise(name: str) -> str:
    n = name.lower().strip()
    return _ALIASES.get(n, n)


def _state_key(state: Optional[str]) -> str:
    if not state:
        return "default"
    return state.lower().strip()


# ── Live price fetch (data.gov.in Agmarknet API) ──────────────────────────────

async def _fetch_live_prices(
    commodity: str,
    state: Optional[str],
    api_key: str,
) -> Optional[Dict[str, Any]]:
    """
    Attempt to fetch live prices from data.gov.in Agmarknet API.

    Returns None if the API key is missing, request fails, or data is
    not available for the commodity/state combination.
    """
    if not api_key or api_key in ("", "your_key_here"):
        return None

    url = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": "10",
        "filters[Commodity]": commodity.title(),
    }
    if state:
        params["filters[State]"] = state.title()

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", [])

            if not records:
                return None

            prices = []
            for r in records:
                try:
                    prices.append({
                        "mandi": r.get("Market", "Unknown"),
                        "district": r.get("District", ""),
                        "state": r.get("State", ""),
                        "min_price": int(r.get("Min Price", 0)),
                        "max_price": int(r.get("Max Price", 0)),
                        "modal_price": int(r.get("Modal Price", 0)),
                        "date": r.get("Arrival Date", ""),
                        "variety": r.get("Variety", ""),
                    })
                except (ValueError, KeyError):
                    continue

            if not prices:
                return None

            return {
                "source": "data.gov.in (Agmarknet live)",
                "commodity": commodity,
                "state": state,
                "prices": prices,
                "fetched_at": datetime.now(UTC).isoformat(),
                "is_live": True,
            }

    except httpx.TimeoutException:
        logger.warning("Agmarknet API timeout for %s/%s", commodity, state)
        return None
    except Exception as exc:
        logger.warning("Agmarknet API error: %s", exc)
        return None


# ── Cache layer ───────────────────────────────────────────────────────────────

def _cache_key(commodity: str, state: Optional[str]) -> str:
    s = (state or "all").lower().replace(" ", "_")
    return f"market:{commodity}:{s}"


async def _get_cached(commodity: str, state: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return a cached price record if within max_age_hours."""
    try:
        from app.database import get_collection
        col = get_collection("market_prices")
        key = _cache_key(commodity, state)
        doc = await col.find_one({"cache_key": key})
        if doc:
            doc.pop("_id", None)
            return doc
    except Exception as exc:
        logger.debug("Market cache miss: %s", exc)
    return None


async def _set_cache(
    commodity: str,
    state: Optional[str],
    data: Dict[str, Any],
) -> None:
    """Upsert a price record into MongoDB cache."""
    try:
        from app.database import get_collection
        col = get_collection("market_prices")
        data["cache_key"] = _cache_key(commodity, state)
        data["fetched_at"] = datetime.now(UTC)
        await col.update_one(
            {"cache_key": data["cache_key"]},
            {"$set": data},
            upsert=True,
        )
    except Exception as exc:
        logger.debug("Market cache write failed: %s", exc)


# ── Seasonal adjustment ───────────────────────────────────────────────────────

def _seasonal_factor(commodity: str) -> float:
    """Return a price multiplier based on current season (simple model)."""
    month = datetime.now(UTC).month
    # Harvest months push prices down; lean season pushes up
    if commodity in ("rice", "paddy"):
        return 0.92 if month in (10, 11, 12) else 1.08 if month in (6, 7, 8) else 1.0
    elif commodity == "wheat":
        return 0.90 if month in (3, 4, 5) else 1.10 if month in (10, 11) else 1.0
    elif commodity in ("onion", "tomato"):
        # Highly volatile – wider swing
        return 0.75 if month in (1, 2, 11, 12) else 1.25 if month in (5, 6, 7) else 1.0
    return 1.0


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_market_prices(
    commodity: str,
    state: Optional[str] = None,
    max_age_hours: int = 6,
) -> Dict[str, Any]:
    """
    Fetch commodity prices for a given crop and state.

    Priority:
      1. MongoDB cache (if < max_age_hours old)
      2. data.gov.in live API (if API key configured)
      3. Curated seasonal price fallback

    Args:
        commodity:     Crop name (e.g. "wheat", "rice", "onion")
        state:         Indian state name (optional, improves accuracy)
        max_age_hours: Maximum cache age before refresh

    Returns:
        Dict with prices, source, commodity, and metadata.
    """
    commodity = _normalise(commodity)

    # ── 1. Cache check ────────────────────────────────────────────────────────
    cached = await _get_cached(commodity, state)
    if cached:
        fetched_at = cached.get("fetched_at")
        if isinstance(fetched_at, datetime):
            age = (datetime.now(UTC) - fetched_at.replace(tzinfo=UTC)).total_seconds() / 3600
            if age < max_age_hours:
                logger.debug("Market cache hit: %s/%s (%.1fh old)", commodity, state, age)
                return cached

    # ── 2. Live API ───────────────────────────────────────────────────────────
    try:
        from app.config import get_settings
        api_key = getattr(get_settings(), "data_gov_api_key", "")
        live = await _fetch_live_prices(commodity, state, api_key)
        if live:
            await _set_cache(commodity, state, live)
            return live
    except Exception as exc:
        logger.debug("Live price fetch failed: %s", exc)

    # ── 3. Curated seasonal fallback ──────────────────────────────────────────
    return _build_fallback(commodity, state)


def _build_fallback(
    commodity: str,
    state: Optional[str],
) -> Dict[str, Any]:
    """Build a deterministic price estimate from the curated price database."""
    db_entry = _PRICE_DB.get(commodity, {})
    state_key = _state_key(state)
    prices = db_entry.get(state_key) or db_entry.get("default")

    if not prices:
        return {
            "commodity": commodity,
            "state": state,
            "source": "Not available",
            "is_live": False,
            "prices": [],
            "note": (
                f"Price data for '{commodity}' is not available in our database. "
                "Please check eNAM (https://enam.gov.in) or your local mandi board."
            ),
        }

    factor = _seasonal_factor(commodity)
    min_p = round(prices["min"] * factor)
    max_p = round(prices["max"] * factor)
    modal_p = round(prices["modal"] * factor)

    trend = _price_trend(commodity)
    season_note = _season_note(commodity)

    return {
        "commodity": commodity.title(),
        "state": state or "All India",
        "source": "KrishiMitra curated (AGMARKNET historical)",
        "is_live": False,
        "prices": [
            {
                "mandi": "Regional average",
                "district": state or "Pan-India",
                "min_price": min_p,
                "max_price": max_p,
                "modal_price": modal_p,
                "date": datetime.now(UTC).strftime("%Y-%m-%d"),
                "variety": "Mixed",
            }
        ],
        "price_range_inr_per_quintal": {
            "min": min_p,
            "max": max_p,
            "modal": modal_p,
        },
        "trend": trend,
        "season_note": season_note,
        "advice": _market_advice(commodity),
        "fetched_at": datetime.now(UTC).isoformat(),
        "note": (
            "Estimated prices. For exact prices, check eNAM (https://enam.gov.in) "
            "or agmarknet.gov.in."
        ),
    }


def _price_trend(commodity: str) -> str:
    month = datetime.now(UTC).month
    if commodity in ("onion", "tomato", "potato"):
        if month in (5, 6, 7):
            return "rising"
        elif month in (11, 12, 1):
            return "falling"
    elif commodity == "wheat":
        if month in (3, 4, 5):
            return "falling"
        elif month in (9, 10, 11):
            return "rising"
    elif commodity == "rice":
        if month in (10, 11, 12):
            return "falling"
        elif month in (6, 7, 8):
            return "rising"
    return "stable"


def _season_note(commodity: str) -> str:
    month = datetime.now(UTC).month
    if commodity in ("onion", "tomato", "potato") and month in (5, 6, 7):
        return "Lean season – prices typically elevated. Supply constrained."
    elif commodity == "wheat" and month in (3, 4, 5):
        return "Rabi harvest season – expect lower prices due to fresh arrivals."
    elif commodity == "rice" and month in (10, 11, 12):
        return "Kharif harvest season – prices typically lower due to new crop arrivals."
    return "Off-peak period – prices near seasonal average."


def _market_advice(commodity: str) -> str:
    advices = {
        "wheat":   "Consider storing 20–30% of produce if prices are below MSP. Check FCI procurement centres.",
        "rice":    "Check PM-AASHA scheme for MSP support. eNAM provides pan-India buyer access.",
        "onion":   "Highly volatile – stagger sales over 2–3 weeks. Use NAFED buffer when prices collapse.",
        "tomato":  "Perishable – sell within 5–7 days. Consider processing unit for surplus.",
        "potato":  "Cold storage can help wait for better prices. Check PM Kisan FPO network.",
        "soybean": "MSP assured procurement available. Check local NAFED/MP Agro outlets.",
        "cotton":  "CCI procurement at MSP available. Check nearest Cotton Corporation office.",
        "default": (
            "Sell at mandi during peak arrival to get competitive prices. "
            "Register on eNAM for direct buyer access across India."
        ),
    }
    return advices.get(commodity, advices["default"])


def get_supported_commodities() -> List[str]:
    """Return list of all commodities with curated price data."""
    return sorted(_PRICE_DB.keys())


def get_price_summary(prices_data: Dict[str, Any]) -> str:
    """Build a one-line price summary for prompt injection."""
    if not prices_data.get("prices"):
        return prices_data.get("note", "Price data unavailable.")

    p = prices_data["prices"][0]
    commodity = prices_data.get("commodity", "Commodity")
    state = prices_data.get("state", "India")
    trend = prices_data.get("trend", "stable")
    live = "Live" if prices_data.get("is_live") else "Estimated"

    return (
        f"{commodity} | {state} | ₹{p['min_price']}–₹{p['max_price']}/quintal "
        f"(Modal: ₹{p['modal_price']}) | Trend: {trend} | Source: {live}"
    )
