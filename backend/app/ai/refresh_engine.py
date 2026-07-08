"""
KrishiMitra Backend – Refresh Policy Engine
=============================================
Centralized engine that decides:
  - Which data is stale
  - Which provider must refresh
  - Which provider can reuse cache
  - Whether to execute synchronously or asynchronously

Also implements:
  - Full Refresh (ignores all caches/TTLs)
  - Background Refresh (async, non-blocking)
  - Refresh progress tracking
  - Snapshot versioning for the Digital Twin
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from app.ai.providers import (
    BaseProvider,
    FreshnessLevel,
    ProviderResult,
    registry,
)

logger = logging.getLogger(__name__)

# ── In-memory refresh tracking ────────────────────────────────────────────────
_active_refreshes: Dict[str, Dict[str, Any]] = {}


class RefreshPolicyEngine:
    """
    The ONLY component allowed to make refresh decisions.

    It checks freshness metadata, decides which providers to execute,
    and orchestrates full or partial refreshes.
    """

    @staticmethod
    def should_refresh(
        provider_name: str,
        cached_metadata: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> bool:
        """
        Decide whether a provider's data should be refreshed.

        Args:
            provider_name: Name of the provider.
            cached_metadata: Existing metadata from a previous fetch.
            force: If True, always refresh (Full Refresh mode).

        Returns:
            True if the provider should be re-executed.
        """
        if force:
            return True

        provider = registry.get(provider_name)
        if not provider:
            return False

        # LIVE data always refreshes
        if provider.freshness == FreshnessLevel.LIVE:
            return True

        # PERMANENT data never refreshes unless forced
        if provider.freshness == FreshnessLevel.PERMANENT:
            if cached_metadata and cached_metadata.get("status") == "fresh":
                return False
            return True  # First load

        # DYNAMIC and SEMI_STATIC: check TTL
        if not cached_metadata:
            return True

        last_updated = cached_metadata.get("last_updated", "")
        ttl = cached_metadata.get("ttl_seconds", provider.default_ttl)

        if not last_updated or ttl <= 0:
            return True

        try:
            updated = datetime.fromisoformat(last_updated)
            elapsed = (datetime.now(UTC) - updated).total_seconds()
            return elapsed > ttl
        except (ValueError, TypeError):
            return True

    @staticmethod
    async def execute_providers(
        providers: List[BaseProvider],
        params: Dict[str, Any],
        force: bool = False,
    ) -> Dict[str, ProviderResult]:
        """
        Execute multiple providers concurrently.

        Args:
            providers: List of provider instances to execute.
            params: Shared parameter dict for all providers.
            force: If True, bypass all caching (Full Refresh).

        Returns:
            Dict mapping provider name → ProviderResult.
        """
        if force:
            # Full Refresh: add force flag to params
            params = {**params, "force_refresh": True}

        tasks = [p.execute(params) for p in providers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: Dict[str, ProviderResult] = {}
        for provider, result in zip(providers, results):
            if isinstance(result, Exception):
                logger.error("Provider '%s' raised: %s", provider.name, result)
                output[provider.name] = ProviderResult(
                    provider_name=provider.name,
                    available=False,
                    error=str(result),
                )
            else:
                output[provider.name] = result

        return output

    @staticmethod
    async def full_refresh(
        user_id: str,
        farm_id: Optional[str] = None,
        field_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a Full Refresh: ignore all caches, re-run every provider,
        merge results, version the snapshot, and persist to MongoDB.

        Returns:
            Dict with refresh results, version, and timing.
        """
        refresh_id = str(uuid.uuid4())
        start = datetime.now(UTC)

        # Track progress
        _active_refreshes[refresh_id] = {
            "status": "running",
            "started_at": start.isoformat(),
            "steps": [],
            "user_id": user_id,
        }

        def _step(msg: str) -> None:
            _active_refreshes[refresh_id]["steps"].append({
                "message": msg,
                "at": datetime.now(UTC).isoformat(),
            })
            logger.info("[Refresh %s] %s", refresh_id[:8], msg)

        _step("Preparing full refresh")

        params: Dict[str, Any] = {
            "user_id": user_id,
            "farm_id": farm_id,
            "field_id": field_id,
            "force_refresh": True,
        }

        # ── Phase 1: Load Digital Twin (need location for other providers) ───
        _step("Loading Digital Twin")
        dt_provider = registry.get("digital_twin")
        twin_result: Optional[ProviderResult] = None
        if dt_provider:
            twin_result = await dt_provider.execute(params)
            if twin_result and twin_result.available and twin_result.data:
                derived_loc = twin_result.data.get("derived_location")
                if derived_loc:
                    params["location"] = derived_loc

                farm = twin_result.data.get("farm")
                if farm:
                    center = farm.get("center_coordinate") or {}
                    if center.get("latitude"):
                        params["latitude"] = center["latitude"]
                        params["longitude"] = center["longitude"]
                        params["location_name"] = farm.get("name", "farm")
                        params["boundary"] = farm.get("boundary")

                field = twin_result.data.get("field")
                if field:
                    centroid = field.get("centroid") or {}
                    if centroid.get("latitude"):
                        params["latitude"] = centroid["latitude"]
                        params["longitude"] = centroid["longitude"]

        # ── Phase 2: Run all other providers in parallel ─────────────────────
        _step("Refreshing Weather")
        _step("Refreshing Satellite")
        _step("Refreshing Market")

        parallel_providers = [
            p for p in registry.all()
            if p.name not in ("digital_twin", "chat_history", "ml_inference")
        ]
        parallel_results = await RefreshPolicyEngine.execute_providers(
            parallel_providers, params, force=True
        )

        # ── Phase 3: Run ML with refreshed data ─────────────────────────────
        _step("Running predictions")

        ml_params = dict(params)
        weather_result = parallel_results.get("weather")
        if weather_result and weather_result.available and weather_result.data:
            ml_params["weather"] = weather_result.data.get("weather")

        sat_result = parallel_results.get("satellite")
        if sat_result and sat_result.available and sat_result.data:
            ml_params["satellite"] = sat_result.data

        if twin_result and twin_result.available and twin_result.data:
            ml_params["field"] = twin_result.data.get("field")
            ml_params["farm"] = twin_result.data.get("farm")

        ml_params["intent"] = "CHAT"  # Run all available predictions
        ml_params["extra_params"] = {}

        ml_provider = registry.get("ml_inference")
        ml_result: Optional[ProviderResult] = None
        if ml_provider:
            ml_result = await ml_provider.execute(ml_params)

        # ── Phase 4: Persist snapshot ────────────────────────────────────────
        _step("Updating database")

        snapshot = _build_snapshot(
            twin_result, parallel_results, ml_result, refresh_id
        )
        await _persist_refresh_snapshot(user_id, snapshot)

        # ── Phase 5: Complete ────────────────────────────────────────────────
        elapsed_ms = (datetime.now(UTC) - start).total_seconds() * 1000
        _step("Completed")

        _active_refreshes[refresh_id]["status"] = "completed"
        _active_refreshes[refresh_id]["elapsed_ms"] = round(elapsed_ms, 1)

        return {
            "refresh_id": refresh_id,
            "status": "completed",
            "elapsed_ms": round(elapsed_ms, 1),
            "steps": _active_refreshes[refresh_id]["steps"],
            "providers_refreshed": [
                {
                    "name": name,
                    "available": r.available,
                    "status": r.metadata.status if r.metadata else "unknown",
                }
                for name, r in {
                    **({"digital_twin": twin_result} if twin_result else {}),
                    **parallel_results,
                    **({"ml_inference": ml_result} if ml_result else {}),
                }.items()
            ],
            "snapshot_version": snapshot.get("version", 1),
        }

    @staticmethod
    def get_refresh_status(refresh_id: str) -> Optional[Dict[str, Any]]:
        """Get the progress of an active or completed refresh."""
        return _active_refreshes.get(refresh_id)


def _build_snapshot(
    twin_result: Optional[ProviderResult],
    parallel_results: Dict[str, ProviderResult],
    ml_result: Optional[ProviderResult],
    refresh_id: str,
) -> Dict[str, Any]:
    """Build a versioned snapshot from provider results."""
    snapshot: Dict[str, Any] = {
        "refresh_id": refresh_id,
        "version": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "sources": {},
    }

    if twin_result and twin_result.available:
        snapshot["digital_twin"] = twin_result.data
        snapshot["sources"]["digital_twin"] = {
            "status": twin_result.metadata.status,
            "last_updated": twin_result.metadata.last_updated,
        }

    for name, result in parallel_results.items():
        if result.available and result.data:
            snapshot[name] = result.data
        snapshot["sources"][name] = {
            "status": result.metadata.status if result.metadata else "error",
            "last_updated": result.metadata.last_updated if result.metadata else "",
        }

    if ml_result and ml_result.available:
        snapshot["ml_predictions"] = ml_result.data
        snapshot["sources"]["ml_inference"] = {
            "status": ml_result.metadata.status,
            "last_updated": ml_result.metadata.last_updated,
        }

    return snapshot


async def _persist_refresh_snapshot(
    user_id: str,
    snapshot: Dict[str, Any],
) -> None:
    """Persist a refresh snapshot to MongoDB (never overwrites historical)."""
    try:
        from app.database import get_collection

        col = get_collection("refresh_snapshots")

        # Get current version for this user
        latest = await col.find_one(
            {"user_id": user_id},
            sort=[("version", -1)],
            projection={"version": 1},
        )
        version = (latest["version"] + 1) if latest else 1
        snapshot["version"] = version
        snapshot["user_id"] = user_id

        await col.insert_one(snapshot)
        logger.info("Refresh snapshot v%d persisted for user=%s", version, user_id)
    except Exception as exc:
        logger.error("Failed to persist refresh snapshot: %s", exc)
