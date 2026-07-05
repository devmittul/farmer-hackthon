"""
KrishiMitra Backend – Base Response Models
===========================================
Consistent JSON envelope for every API response.
"""
from datetime import UTC, datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """
    Standard API response envelope.

    Every endpoint returns this shape so frontends can rely on a
    consistent contract regardless of the endpoint.
    """

    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Human-readable status message")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of the response",
    )
    data: Optional[T] = Field(default=None, description="Response payload")
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Extra pagination/latency metadata"
    )


class ErrorResponse(BaseModel):
    """Standard error envelope returned on failures."""

    success: bool = Field(default=False)
    message: str = Field(..., description="User-facing error message")
    error: Optional[str] = Field(default=None, description="Internal error detail")
    code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


def success_response(
    data: Any = None,
    message: str = "OK",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Helper to build a success dict quickly."""
    return {
        "success": True,
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
        "metadata": metadata,
    }


def error_response(
    message: str,
    code: int = 400,
    error: Optional[str] = None,
) -> dict[str, Any]:
    """Helper to build an error dict quickly."""
    return {
        "success": False,
        "message": message,
        "error": error,
        "code": code,
        "timestamp": datetime.now(UTC).isoformat(),
    }
