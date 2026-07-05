"""
KrishiMitra Backend – Error Handling Middleware
================================================
Catches unhandled exceptions and returns consistent JSON error bodies.
"""
import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.schemas.responses import error_response

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global exception handler middleware.

    Ensures the app never returns a raw 500 stack trace to the client.
    All unhandled exceptions are caught and formatted as JSON.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                "Unhandled server error",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "traceback": traceback.format_exc(),
                },
            )
            body = error_response(
                message="An unexpected server error occurred. Please try again.",
                code=500,
                error=str(exc) if logger.isEnabledFor(logging.DEBUG) else None,
            )
            return JSONResponse(status_code=500, content=body)
