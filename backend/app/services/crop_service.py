"""
KrishiMitra Backend – Crop Service (v2 – Pure Domain Layer)
=============================================================
Responsibility:
  Run ML crop prediction and persist the result.

This service NO LONGER builds prompts or calls the AI reasoning engine.
Those responsibilities moved to the AI Orchestrator / Context Builder.

The service returns a structured dict of deterministic facts.
The Orchestrator passes those facts to the Reasoning Engine for explanation.

Pattern:
  Route → CropService.predict() → (ML result dict)
  Route → ContextBuilder → ReasoningEngine → explanation
  OR
  Direct /crop/predict call → CropService.predict_and_explain() for
  backward compat (still calls ReasoningEngine internally but cleanly).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Dict, Optional

from app.ai.reasoning_engine import ReasoningEngine
from app.ai import prompt_builder
from app.ai.confidence_engine import ConfidenceEngine
from app.database import get_collection
from app.schemas.requests import CropPredictRequest

logger = logging.getLogger(__name__)


class CropService:
    """Handles crop recommendation ML prediction and persistence."""

    @staticmethod
    async def predict(
        payload: CropPredictRequest,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run ML crop prediction only.  Returns raw ML output dict.
        Does NOT call the Reasoning Engine.

        Use this when the caller already has an orchestrator context.
        """
        from app.ai.ml.models import predict_crop

        logger.info("CropService.predict: user=%s", user_id or "anon")

        # ── ML (offloaded to thread pool; non-blocking) ───────────────────────
        ml_result = await asyncio.to_thread(
            predict_crop,
            nitrogen=payload.nitrogen,
            phosphorus=payload.phosphorus,
            potassium=payload.potassium,
            temperature=payload.temperature,
            humidity=payload.humidity,
            ph=payload.ph,
            rainfall=payload.rainfall,
        )

        # ── Persist in background ─────────────────────────────────────────────
        input_params = _build_input_params(payload)
        await _persist_prediction(user_id, input_params, ml_result, explanation="")

        logger.info(
            "CropService.predict: %s (%.1f%%)",
            ml_result["recommended_crop"],
            ml_result["confidence"],
        )
        return ml_result

    @staticmethod
    async def predict_and_explain(
        payload: CropPredictRequest,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full pipeline: ML prediction + Reasoning Engine explanation.

        Used by the /crop/predict direct endpoint (backward compat).
        The orchestrator path uses predict() only.
        """
        from app.ai.ml.models import predict_crop

        logger.info("CropService.predict_and_explain: user=%s", user_id or "anon")

        # ── Step 1: ML Prediction ─────────────────────────────────────────────
        ml_result = await asyncio.to_thread(
            predict_crop,
            nitrogen=payload.nitrogen,
            phosphorus=payload.phosphorus,
            potassium=payload.potassium,
            temperature=payload.temperature,
            humidity=payload.humidity,
            ph=payload.ph,
            rainfall=payload.rainfall,
        )

        input_params = _build_input_params(payload)

        # ── Step 2: Build structured prompt (facts → Reasoning Engine) ────────
        user_question = (
            "Based on my soil and climate conditions, what crop should I grow "
            "and what are the best farming practices?"
        )
        prompt = prompt_builder.build_crop_prompt(
            user_message=user_question,
            language=payload.language,
            prediction=ml_result,
            input_params=input_params,
        )

        # ── Step 3: Reasoning Engine explanation ──────────────────────────────
        try:
            explanation, latency_ms = await ReasoningEngine.generate(prompt)
        except Exception as exc:
            logger.error("ReasoningEngine crop explanation failed: %s", exc)
            explanation = (
                f"Recommended crop: {ml_result['recommended_crop'].title()}. "
                "AI explanation temporarily unavailable."
            )
            latency_ms = 0.0

        # ── Step 4: Confidence ────────────────────────────────────────────────
        confidence = ConfidenceEngine.compute_from_dict({"ml_crop": True})

        # ── Step 5: Persist ───────────────────────────────────────────────────
        tips = _extract_tips(explanation)
        result = {
            "recommended_crop": ml_result["recommended_crop"],
            "confidence_score": ml_result["confidence"],
            "alternatives": ml_result["alternatives"],
            "explanation": explanation,
            "tips": tips,
            "input_params": input_params,
        }
        await _persist_prediction(user_id, input_params, ml_result, explanation)

        logger.info(
            "CropService.predict_and_explain: %s (%.1f%%) in %.0fms",
            ml_result["recommended_crop"],
            ml_result["confidence"],
            latency_ms,
        )
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_input_params(payload: CropPredictRequest) -> Dict[str, Any]:
    return {
        "Nitrogen (N)": f"{payload.nitrogen} kg/ha",
        "Phosphorus (P)": f"{payload.phosphorus} kg/ha",
        "Potassium (K)": f"{payload.potassium} kg/ha",
        "Temperature": f"{payload.temperature}°C",
        "Humidity": f"{payload.humidity}%",
        "pH": payload.ph,
        "Rainfall": f"{payload.rainfall} mm/year",
        "Soil Type": payload.soil_type.value if payload.soil_type else "Not specified",
        "Location": payload.location or "Not specified",
    }


def _extract_tips(explanation: str) -> list[str]:
    """Extract bullet points from the explanation text as tips."""
    tips = []
    for line in explanation.split("\n"):
        line = line.strip()
        if line.startswith(("•", "-", "*", "1.", "2.", "3.", "4.", "5.")):
            cleaned = line.lstrip("•-*0123456789. ").strip()
            if cleaned:
                tips.append(cleaned)
    return tips[:5]


async def _persist_prediction(
    user_id: Optional[str],
    input_params: Dict[str, Any],
    ml_result: Dict[str, Any],
    explanation: str,
) -> None:
    """Persist crop prediction to MongoDB (non-fatal)."""
    try:
        col = get_collection("crop_predictions")
        await col.insert_one({
            "user_id": user_id,
            "input_features": input_params,
            "recommended_crop": ml_result["recommended_crop"],
            "confidence": ml_result["confidence"],
            "alternatives": ml_result["alternatives"],
            "explanation": explanation,
            "created_at": datetime.now(UTC),
        })
    except Exception as exc:
        logger.error("Failed to persist crop prediction: %s", exc)
