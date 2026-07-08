"""
KrishiMitra Backend – Application Entry Point
===============================================
FastAPI application factory with:
  - Lifecycle management (startup / shutdown)
  - Middleware registration (order matters!)
  - Route registration
  - Static file serving for audio outputs
  - OpenAPI/Swagger documentation
  - Rate limiting
  - CORS

Run locally:
    uvicorn app.main:app --reload --port 8000

Production:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database import close_mongo_connection, connect_to_mongo
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.schemas.responses import error_response, success_response

# ── Logging must be configured FIRST ─────────────────────────────────────────
configure_logging()
logger = get_logger(__name__)


# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Application Lifecycle ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Manage application startup and shutdown resources.

    Startup:
      - Connect to MongoDB Atlas
      - Ensure audio output directory exists

    Shutdown:
      - Close MongoDB connection pool gracefully
    """
    settings = get_settings()
    logger.info("=" * 60)
    logger.info("Starting %s v%s [%s]", settings.app_name, settings.app_version, settings.app_env)
    logger.info("=" * 60)

    # Connect to MongoDB
    try:
        await connect_to_mongo()
        # Ensure all compound + TTL indexes exist (idempotent)
        from app.db_indexes import ensure_indexes
        await ensure_indexes()
    except Exception as exc:
        logger.error("MongoDB startup error: %s", exc)
        logger.warning("App starting without DB – some features will be unavailable.")

    # Ensure audio output directory exists
    audio_dir = Path(settings.audio_output_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Audio output directory: %s", audio_dir.resolve())

    # Ensure ML model directory exists (triggers lazy training on first call)
    ml_models_dir = Path("app/ai/ml/saved_models")
    ml_models_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Application startup complete. Ready to accept requests.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down application …")
    await close_mongo_connection()
    logger.info("Shutdown complete.")


def create_app() -> FastAPI:
    """
    Application factory.

    Returns a fully configured FastAPI instance.
    Use this pattern for testing (avoids module-level side effects).
    """
    settings = get_settings()

    app = FastAPI(
        title="KrishiMitra AI Backend",
        description="""
## 🌾 KrishiMitra – Rural Mobility & Smart Agriculture AI Platform

A production-grade FastAPI backend powering AI-driven agricultural intelligence for Indian farmers.

### Features
- **AI Chat** – Multi-intent conversational AI (weather, crops, routes, SOS, markets)
- **Crop Recommendation** – Scikit-learn ML + Gemini explanation
- **Vehicle Demand Prediction** – ML-powered logistics planning
- **Route Planning** – OSRM routing (no Google Maps)
- **Weather Intelligence** – Open-Meteo + farming advisories
- **Voice Support** – faster-whisper STT + Piper TTS (fully local)
- **Community Courier** – Peer-to-peer cargo matching
- **Emergency SOS** – Location-aware emergency alerts
- **Satellite Analytics** – Google Earth Engine NDVI/crop health
- **Multi-Language** – 10 Indian languages supported

### Authentication
All authenticated endpoints require: `Authorization: Bearer <token>`
        """,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={
            "name": "KrishiMitra Team",
            "email": "team@krishimitra.ai",
        },
        license_info={
            "name": "MIT",
        },
    )

    # ── Rate Limiter ──────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── Middleware (order: outermost first) ───────────────────────────────────
    # 1. Error handler – catch everything
    app.add_middleware(ErrorHandlerMiddleware)

    # 2. CORS – must be before request logging
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # 3. Request logging with timing
    app.add_middleware(RequestLoggingMiddleware)

    # 4. SlowAPI rate limiting
    app.add_middleware(SlowAPIMiddleware)

    # ── Static Files (audio outputs) ──────────────────────────────────────────
    audio_dir = Path(settings.audio_output_dir)
    audio_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/audio", StaticFiles(directory=str(audio_dir)), name="audio")

    # ── Routers ───────────────────────────────────────────────────────────────
    _register_routes(app)

    # ── Exception Handlers ────────────────────────────────────────────────────
    _register_exception_handlers(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routers with the application."""
    from app.routes.auth import router as auth_router
    from app.routes.chat import router as chat_router
    from app.routes.courier import router as courier_router
    from app.routes.crop import router as crop_router
    from app.routes.route import router as route_router
    from app.routes.sos import router as sos_router
    from app.routes.twin import router as twin_router
    from app.routes.vehicle import router as vehicle_router
    from app.routes.voice import router as voice_router
    from app.routes.weather import router as weather_router
    from app.routes.farm_routes import router as farm_router

    api_prefix = "/api/v1"

    app.include_router(auth_router, prefix=api_prefix)
    app.include_router(chat_router, prefix=api_prefix)
    app.include_router(voice_router, prefix=api_prefix)
    app.include_router(crop_router, prefix=api_prefix)
    app.include_router(vehicle_router, prefix=api_prefix)
    app.include_router(route_router, prefix=api_prefix)
    app.include_router(weather_router, prefix=api_prefix)
    app.include_router(farm_router, prefix=api_prefix)
    app.include_router(courier_router, prefix=api_prefix)
    app.include_router(sos_router, prefix=api_prefix)
    app.include_router(twin_router, prefix=api_prefix)   # ← Digital Twin

    from app.routes.system import router as system_router
    app.include_router(system_router, prefix=api_prefix)

    from app.routes.refresh import router as refresh_router
    app.include_router(refresh_router, prefix=api_prefix)

    logger.info("Registered %d routers under %s", 13, api_prefix)


def _register_exception_handlers(app: FastAPI) -> None:
    """Register global FastAPI exception handlers."""
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return structured validation errors."""
        errors = []
        for error in exc.errors():
            field = " → ".join(str(loc) for loc in error["loc"])
            errors.append({"field": field, "message": error["msg"]})

        return JSONResponse(
            status_code=422,
            content=error_response(
                message="Request validation failed.",
                code=422,
                error=str(errors),
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        """Return consistent JSON for HTTP errors."""
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                message=str(exc.detail),
                code=exc.status_code,
            ),
            headers=getattr(exc, "headers", None),
        )


# ── Health Check ──────────────────────────────────────────────────────────────
def _add_health_check(app: FastAPI) -> None:
    """Add /health endpoint directly to the app instance."""

    @app.get("/health", tags=["System"], summary="Health check")
    async def health_check() -> dict:
        """
        Returns application health status.
        Used by Docker HEALTHCHECK and load balancers.
        """
        settings = get_settings()
        return success_response(
            data={
                "status": "healthy",
                "version": settings.app_version,
                "environment": settings.app_env,
                "service": settings.app_name,
            },
            message="Service is running.",
        )

    @app.get("/", tags=["System"], summary="API root", include_in_schema=False)
    async def root() -> dict:
        """Redirect hint for root path."""
        return success_response(
            data={"docs": "/docs", "redoc": "/redoc", "health": "/health"},
            message="KrishiMitra AI Backend is running. Visit /docs for API documentation.",
        )


# ── Create app instance ───────────────────────────────────────────────────────
app = create_app()
_add_health_check(app)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=not settings.is_production,
        log_level=settings.log_level.lower(),
        access_log=False,  # We handle logging via middleware
    )
