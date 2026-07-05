"""
KrishiMitra Backend – System Status Routes
============================================
Provides health checks and connectivity status for all external APIs and services.
"""
from typing import Any, Dict

import httpx
from fastapi import APIRouter

from app.config import get_settings
from app.database import get_database
from app.schemas.responses import success_response

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """
    Check the status of all core dependencies and external APIs.
    Used by the frontend dashboard to display 'AI System Status'.
    """
    settings = get_settings()
    status_checks = {}

    # 1. MongoDB Database
    try:
        db = get_database()
        await db.command("ping")
        status_checks["mongodb"] = {"status": "Live", "message": "Connected"}
    except Exception as e:
        status_checks["mongodb"] = {"status": "Offline", "message": "Database unreachable"}

    # 2. Weather API (Open-Meteo)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast?latitude=20&longitude=79&current_weather=true")
            if resp.status_code == 200:
                status_checks["weather"] = {"status": "Live", "message": "Connected"}
            else:
                status_checks["weather"] = {"status": "Error", "message": f"HTTP {resp.status_code}"}
    except Exception:
        status_checks["weather"] = {"status": "Offline", "message": "API unreachable"}

    # 3. Location System (Nominatim / OSM)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            # Add user-agent to comply with Nominatim TOS
            headers = {"User-Agent": "KrishiMitra-HealthCheck/1.0"}
            resp = await client.get("https://nominatim.openstreetmap.org/status.php?format=json", headers=headers)
            if resp.status_code == 200:
                status_checks["location"] = {"status": "Live", "message": "Connected"}
            else:
                status_checks["location"] = {"status": "Error", "message": f"HTTP {resp.status_code}"}
    except Exception:
        status_checks["location"] = {"status": "Offline", "message": "API unreachable"}

    # 4. Google Earth Engine
    if settings.gee_service_account and settings.gee_key_file:
        status_checks["earth_engine"] = {"status": "Live", "message": "Configured"}
    else:
        status_checks["earth_engine"] = {"status": "Offline", "message": "Credentials missing"}

    # 5. Claude API (Reasoning Engine)
    if settings.claude_api_key:
        status_checks["claude_api"] = {"status": "Live", "message": f"Configured ({settings.claude_model})"}
    elif settings.openai_api_key:
        status_checks["claude_api"] = {"status": "Live", "message": "Using OpenAI fallback"}
    else:
        status_checks["claude_api"] = {"status": "Offline", "message": "Missing API Key"}

    return success_response(data=status_checks, message="System status retrieved.")
