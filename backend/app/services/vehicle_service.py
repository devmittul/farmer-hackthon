"""
KrishiMitra Backend – Vehicle Demand Service
=============================================
Business logic for vehicle demand prediction.
"""
import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from app.ai.reasoning_engine import ReasoningEngine
from app.ai import prompt_builder
from app.ai.ml.models import predict_vehicle_demand
from app.database import get_collection
from app.schemas.requests import VehiclePredictRequest

logger = logging.getLogger(__name__)


class VehicleService:
    """Handles vehicle demand prediction and Gemini explanation."""

    @staticmethod
    async def predict_and_explain(
        payload: VehiclePredictRequest,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Run ML vehicle demand prediction then explain via Gemini.

        Args:
            payload: Validated vehicle prediction request.
            user_id: Optional authenticated user ID.

        Returns:
            Structured response with prediction + explanation.
        """
        # ── ML Prediction ─────────────────────────────────────────────────────
        logger.info("Running vehicle demand prediction for %s", payload.location)
        ml_result = await asyncio.to_thread(
            predict_vehicle_demand,
            quantity_tonnes=payload.quantity_tonnes,
            destination=payload.destination,
            crop_type=payload.crop_type,
            date=payload.date,
        )

        request_params = {
            "Pickup Location": payload.location,
            "Destination": payload.destination,
            "Cargo": payload.crop_type,
            "Quantity": f"{payload.quantity_tonnes} tonnes",
            "Date": payload.date,
        }

        # ── Build Prompt ──────────────────────────────────────────────────────
        user_question = (
            f"I need to transport {payload.quantity_tonnes} tonnes of "
            f"{payload.crop_type} from {payload.location} to {payload.destination} "
            f"on {payload.date}. What vehicle should I use and what will it cost?"
        )
        prompt = prompt_builder.build_vehicle_prompt(
            user_message=user_question,
            language=payload.language,
            prediction=ml_result,
            request_params=request_params,
        )

        # ── Gemini Explanation ────────────────────────────────────────────────
        try:
            explanation, latency_ms = await ReasoningEngine.generate(prompt)
        except Exception as exc:
            logger.error("ReasoningEngine vehicle explanation failed: %s", exc)
            explanation = (
                f"Demand level: {ml_result['demand_level']}. "
                f"AI explanation temporarily unavailable."
            )
            latency_ms = 0.0
        # ── Persist ───────────────────────────────────────────────────────────
        await _persist_prediction(user_id, request_params, ml_result)

        return {
            "demand_level": ml_result["demand_level"],
            "recommended_vehicles": ml_result["recommended_vehicles"],
            "estimated_cost_inr": ml_result["estimated_cost_inr"],
            "best_time_window": ml_result["best_time_window"],
            "explanation": explanation,
        }


async def _persist_prediction(
    user_id: Optional[str],
    request_params: dict[str, Any],
    ml_result: dict[str, Any],
) -> None:
    try:
        col = get_collection("vehicle_predictions")
        await col.insert_one(
            {
                "user_id": user_id,
                **request_params,
                **ml_result,
                "created_at": datetime.now(UTC),
            }
        )
    except Exception as exc:
        logger.error("Failed to persist vehicle prediction: %s", exc)
