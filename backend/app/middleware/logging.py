"""
KrishiMitra Backend – Request Logging Middleware
=================================================
Logs every request with timing and structured metadata.
"""
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that logs every incoming request and its response.

    Adds:
    - Unique X-Request-ID header to every response.
    - Structured log with method, path, status, and latency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Attach request_id to request state for downstream use
        request.state.request_id = request_id

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                "Unhandled exception",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": round(elapsed, 2),
                    "error": str(exc),
                },
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "Request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_ms": round(elapsed, 2),
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

        return response
