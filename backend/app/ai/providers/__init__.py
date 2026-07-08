"""
KrishiMitra Backend – Provider Architecture
=============================================
Base classes for the data provider pattern.

Every external data source is wrapped in a Provider that:
  - Has a single responsibility (fetch ONE type of data)
  - Never communicates with other providers
  - Returns standardised output with freshness metadata
  - Supports caching via the Refresh Policy Engine

Freshness levels:
  PERMANENT   – Only refreshes when the user edits the resource (polygon, soil type)
  SEMI_STATIC – Refreshes occasionally (historical NDVI, crop history)
  DYNAMIC     – Refreshes based on TTL (weather, market prices, predictions)
  LIVE        – Never cached (chat, prompt, intent)
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field as dc_field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FreshnessLevel(str, Enum):
    """Data freshness classification."""
    PERMANENT = "permanent"
    SEMI_STATIC = "semi_static"
    DYNAMIC = "dynamic"
    LIVE = "live"


@dataclass
class ProviderMetadata:
    """
    Metadata attached to every provider output.

    The Refresh Policy Engine uses this to decide whether data is stale.
    """
    source: str                                        # e.g. "open_meteo", "gee", "mongodb"
    last_updated: str = ""                             # ISO-8601
    ttl_seconds: int = 0                               # 0 = no TTL (permanent or live)
    freshness: FreshnessLevel = FreshnessLevel.DYNAMIC
    version: int = 1
    status: str = "fresh"                              # fresh | stale | error | unavailable

    def is_stale(self) -> bool:
        """Check if data has exceeded its TTL."""
        if self.freshness in (FreshnessLevel.PERMANENT, FreshnessLevel.LIVE):
            return False
        if not self.last_updated or self.ttl_seconds <= 0:
            return True
        try:
            updated = datetime.fromisoformat(self.last_updated)
            elapsed = (datetime.now(UTC) - updated).total_seconds()
            return elapsed > self.ttl_seconds
        except (ValueError, TypeError):
            return True


@dataclass
class ProviderResult:
    """
    Standardised output from any provider.

    Every provider returns this, regardless of what data it fetches.
    """
    provider_name: str
    data: Optional[Dict[str, Any]] = None
    metadata: ProviderMetadata = dc_field(default_factory=lambda: ProviderMetadata(source="unknown"))
    available: bool = False
    error: Optional[str] = None


class BaseProvider(ABC):
    """
    Abstract base class for all data providers.

    Subclasses implement ``fetch()`` which performs the actual data retrieval.
    The provider registry calls ``execute()`` which wraps ``fetch()`` with
    error handling and metadata assignment.
    """

    name: str = "base"
    freshness: FreshnessLevel = FreshnessLevel.DYNAMIC
    default_ttl: int = 3600  # seconds

    @abstractmethod
    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch data from the external source.

        Args:
            params: Provider-specific parameters (user_id, location, field_id, etc.)

        Returns:
            Raw data dict, or None if unavailable.
        """
        ...

    async def execute(self, params: Dict[str, Any]) -> ProviderResult:
        """
        Execute the provider with full error handling and metadata.

        This is the public API called by the ContextBuilder.
        Subclasses should NOT override this; override ``fetch()`` instead.
        """
        try:
            data = await self.fetch(params)
            if data is not None:
                return ProviderResult(
                    provider_name=self.name,
                    data=data,
                    metadata=ProviderMetadata(
                        source=self.name,
                        last_updated=datetime.now(UTC).isoformat(),
                        ttl_seconds=self.default_ttl,
                        freshness=self.freshness,
                        version=1,
                        status="fresh",
                    ),
                    available=True,
                )
            else:
                return ProviderResult(
                    provider_name=self.name,
                    metadata=ProviderMetadata(
                        source=self.name,
                        last_updated=datetime.now(UTC).isoformat(),
                        freshness=self.freshness,
                        status="unavailable",
                    ),
                    available=False,
                )
        except Exception as exc:
            logger.error("Provider '%s' failed: %s", self.name, exc)
            return ProviderResult(
                provider_name=self.name,
                metadata=ProviderMetadata(
                    source=self.name,
                    last_updated=datetime.now(UTC).isoformat(),
                    freshness=self.freshness,
                    status="error",
                ),
                available=False,
                error=str(exc),
            )


class ProviderRegistry:
    """
    Central registry of all data providers.

    The ContextBuilder uses this to discover and execute providers.
    Providers are registered at import time.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        """Register a provider instance."""
        self._providers[provider.name] = provider
        logger.info("Provider registered: %s (freshness=%s, ttl=%ds)",
                     provider.name, provider.freshness.value, provider.default_ttl)

    def get(self, name: str) -> Optional[BaseProvider]:
        """Get a provider by name."""
        return self._providers.get(name)

    def all(self) -> List[BaseProvider]:
        """Return all registered providers."""
        return list(self._providers.values())

    def names(self) -> List[str]:
        """Return names of all registered providers."""
        return list(self._providers.keys())


# ── Global registry singleton ────────────────────────────────────────────────
registry = ProviderRegistry()
