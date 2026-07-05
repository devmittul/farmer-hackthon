"""
KrishiMitra Backend – Confidence Engine
=========================================
Computes a multi-source confidence score for every AI response.

The engine NEVER involves the AI model.  It purely aggregates signal
quality from each data source and derives an overall confidence value.

Confidence Model
----------------
Each data source contributes a *base confidence* when available and a
*penalty* when unavailable.  The overall score is the weighted average
of all contributing sources, clamped to [0, 100].

Source weights (sum to 1.0):
  weather     0.25
  satellite   0.25
  ml_model    0.30
  database    0.10
  chat_hist   0.10

Usage:
    from app.ai.confidence_engine import ConfidenceEngine
    from app.ai.context_builder import StructuredContext

    scores = ConfidenceEngine.compute(ctx)
    # {
    #   "weather":   96,
    #   "satellite": 91,
    #   "ml":        89,
    #   "database":  85,
    #   "history":   70,
    #   "overall":   91,
    #   "level":     "high",
    # }
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Source confidence base values ──────────────────────────────────────────────
# These represent the inherent reliability of each source when it IS available.
_BASE: Dict[str, int] = {
    "weather":    96,   # Open-Meteo has high accuracy for 1-3 day forecasts
    "satellite":  91,   # Sentinel-2 10m; accuracy drops with cloud cover
    "ml_crop":    89,   # RandomForest on synthetic data; upgrade on real data
    "ml_vehicle": 84,
    "farmer":     98,   # DB record — authoritative when present
    "field":      97,
    "chat":       72,   # Conversational context — less precise
}

# ── Source weights for weighted average ───────────────────────────────────────
_WEIGHTS: Dict[str, float] = {
    "weather":    0.25,
    "satellite":  0.25,
    "ml_crop":    0.30,
    "ml_vehicle": 0.20,
    "farmer":     0.10,
    "field":      0.10,
    "chat":       0.05,
}


class ConfidenceEngine:
    """
    Stateless multi-source confidence scorer.

    All methods are static.  No external I/O is performed.
    Input is a StructuredContext produced by ContextBuilder.
    """

    @staticmethod
    def compute(ctx: Any) -> Dict[str, Any]:
        """
        Compute per-source and overall confidence for a StructuredContext.

        Args:
            ctx: A StructuredContext dataclass instance.

        Returns:
            Dict with individual source scores and an "overall" score.
        """
        from app.ai.context_builder import StructuredContext  # local to avoid circular
        assert isinstance(ctx, StructuredContext)

        scores: Dict[str, Optional[int]] = {}

        # ── Weather ──────────────────────────────────────────────────────────
        if ctx.weather:
            forecast_days = len(ctx.weather.get("forecast", []))
            # Confidence drops slightly for longer forecasts
            weather_conf = _BASE["weather"] - max(0, (forecast_days - 3) * 2)
            scores["weather"] = min(weather_conf, 99)
        else:
            scores["weather"] = None

        # ── Satellite ────────────────────────────────────────────────────────
        if ctx.satellite and ctx.satellite.get("ndvi") is not None:
            ndvi = ctx.satellite.get("ndvi", 0)
            # Very low / very high NDVI values are more certain
            # Moderate NDVI (0.3–0.5) has higher ambiguity → slight penalty
            penalty = 5 if 0.3 <= ndvi <= 0.5 else 0
            scores["satellite"] = _BASE["satellite"] - penalty
        else:
            scores["satellite"] = None

        # ── ML Crop ──────────────────────────────────────────────────────────
        if ctx.crop_prediction:
            # ML model's own probability score IS our confidence
            ml_raw = ctx.crop_prediction.get("confidence", 0)  # already 0-100
            scores["ml_crop"] = min(int(ml_raw), 99)
        else:
            scores["ml_crop"] = None

        # ── ML Vehicle ───────────────────────────────────────────────────────
        if ctx.vehicle_prediction:
            scores["ml_vehicle"] = _BASE["ml_vehicle"]
        else:
            scores["ml_vehicle"] = None

        # ── Database (Digital Twin) ───────────────────────────────────────────
        if ctx.farmer:
            scores["farmer"] = _BASE["farmer"]
        else:
            scores["farmer"] = None

        if ctx.field:
            scores["field"] = _BASE["field"]
        else:
            scores["field"] = None

        # ── Conversation history ──────────────────────────────────────────────
        if ctx.recent_chat:
            scores["chat"] = _BASE["chat"] + min(len(ctx.recent_chat) * 2, 15)
        else:
            scores["chat"] = None

        # ── Weighted overall ──────────────────────────────────────────────────
        total_weight = 0.0
        weighted_sum = 0.0
        for source, score in scores.items():
            if score is not None:
                w = _WEIGHTS.get(source, 0.05)
                weighted_sum += score * w
                total_weight += w

        if total_weight > 0:
            overall = round(weighted_sum / total_weight, 1)
        else:
            overall = 50.0  # no data → 50% uncertainty

        level = _confidence_level(overall)

        result: Dict[str, Any] = {
            "weather":   scores.get("weather"),
            "satellite": scores.get("satellite"),
            "ml_crop":   scores.get("ml_crop"),
            "ml_vehicle": scores.get("ml_vehicle"),
            "database":  scores.get("farmer") or scores.get("field"),
            "history":   scores.get("chat"),
            "overall":   overall,
            "level":     level,
        }

        logger.debug("Confidence scores: %s", result)
        return result

    @staticmethod
    def compute_from_dict(data_sources: Dict[str, bool]) -> Dict[str, Any]:
        """
        Lightweight scorer from a plain data_sources bool dict.

        Used by services that don't have a full StructuredContext.

        Args:
            data_sources: {"weather": True, "satellite": False, ...}

        Returns:
            Simplified confidence dict.
        """
        scores: Dict[str, int] = {}
        for source, available in data_sources.items():
            if available:
                scores[source] = _BASE.get(source, 75)

        if not scores:
            return {"overall": 50, "level": "low", "sources": {}}

        overall = round(sum(scores.values()) / len(scores), 1)
        return {
            "overall": overall,
            "level": _confidence_level(overall),
            "sources": scores,
        }


def _confidence_level(score: float) -> str:
    """Map numeric score to a human-readable confidence level."""
    if score >= 90:
        return "very_high"
    elif score >= 75:
        return "high"
    elif score >= 55:
        return "medium"
    elif score >= 35:
        return "low"
    else:
        return "very_low"
