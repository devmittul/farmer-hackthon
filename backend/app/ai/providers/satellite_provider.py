"""
Satellite Provider – wraps the existing GEE satellite service.

Delegates to app.ai.satellite.service.get_ndvi().
No satellite logic is duplicated here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.ai.providers import BaseProvider, FreshnessLevel

logger = logging.getLogger(__name__)


class SatelliteProvider(BaseProvider):
    name = "satellite"
    freshness = FreshnessLevel.DYNAMIC
    default_ttl = 43200  # 12 hours (satellite imagery updates infrequently)

    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch satellite data using the existing GEE service.

        Expected params:
            latitude (float): Latitude.
            longitude (float): Longitude.
            location_name (str): Human-readable name.
            boundary (dict): Optional GeoJSON Polygon.
        """
        lat = params.get("latitude")
        lon = params.get("longitude")
        if lat is None or lon is None:
            return None

        from app.ai.satellite.service import get_ndvi

        name = params.get("location_name", "unknown")
        boundary = params.get("boundary")

        sat = await get_ndvi(lat, lon, location_name=name, boundary=boundary)
        if sat and sat.get("ndvi") is not None:
            return sat
        return None
