"""
KrishiMitra Backend – Response Formatter
==========================================
Standardises every outbound AI response into the canonical envelope:

    {
      "success":     true,
      "timestamp":   "ISO-8601",
      "request_id":  "uuid",
      "message":     "Human-readable status",
      "data":        { ... domain data ... },
      "confidence":  { "overall": 92, "weather": 96, ... },
      "metadata":    { "intent": "CROP", "language": "hi", "latency_ms": 412 }
    }

Design rules:
  • This module is the LAST step before the response leaves the orchestrator.
  • It never fetches data or calls AI.
  • Confidence is always included (even if empty → null).
  • The intent, language, and latency are always part of metadata.

Usage:
    from app.ai.response_formatter import ResponseFormatter
    envelope = ResponseFormatter.format(
        request_id=ctx.request_id,
        intent=ctx.intent,
        language=ctx.language,
        reply=reply_text,
        data=ctx_data,
        confidence=confidence_scores,
        latency_ms=elapsed,
    )
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, Optional

from app.schemas.requests import IntentType, LanguageCode


class ResponseFormatter:
    """
    Stateless formatter that builds the canonical API envelope.
    All methods are static.
    """

    @staticmethod
    def format(
        *,
        request_id: str,
        intent: IntentType,
        language: LanguageCode,
        reply: str,
        session_id: str,
        data: Optional[Dict[str, Any]] = None,
        confidence: Optional[Dict[str, Any]] = None,
        latency_ms: float = 0.0,
        total_latency_ms: float = 0.0,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build the standard API response envelope.

        Args:
            request_id:       Unique request identifier.
            intent:           Detected intent (from IntentDetector).
            language:         Detected / requested language.
            reply:            Plain-text AI reasoning response.
            session_id:       Conversation session ID.
            data:             Structured domain data (weather, route, etc.).
            confidence:       Confidence dict from ConfidenceEngine.
            latency_ms:       AI call latency.
            total_latency_ms: End-to-end request latency.
            extra_metadata:   Any additional metadata to merge.

        Returns:
            Dict matching the canonical response schema.
        """
        metadata: Dict[str, Any] = {
            "intent": intent.value,
            "language": language.value,
            "session_id": session_id,
            "ai_latency_ms": round(latency_ms, 2),
            "total_latency_ms": round(total_latency_ms, 2),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        return {
            "success": True,
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "message": "Response generated.",
            "data": {
                "reply": reply,
                "intent": intent.value,
                "language": language.value,
                "session_id": session_id,
                **(data or {}),
            },
            "confidence": confidence,
            "metadata": metadata,
        }

    @staticmethod
    def format_error(
        *,
        request_id: str,
        message: str,
        code: int = 500,
        error_detail: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build a standardised error envelope.

        Args:
            request_id:    Unique request identifier.
            message:       User-facing error message.
            code:          HTTP-equivalent status code.
            error_detail:  Internal error detail (not exposed in production).
            metadata:      Optional metadata dict.

        Returns:
            Dict matching the canonical error schema.
        """
        return {
            "success": False,
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "message": message,
            "data": None,
            "confidence": None,
            "error": error_detail,
            "code": code,
            "metadata": metadata or {},
        }
