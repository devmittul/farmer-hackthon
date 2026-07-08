"""
Market Provider – wraps the existing market service.

Delegates to app.ai.market.service.fetch_market_prices().
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.ai.providers import BaseProvider, FreshnessLevel

logger = logging.getLogger(__name__)


class MarketProvider(BaseProvider):
    name = "market"
    freshness = FreshnessLevel.DYNAMIC
    default_ttl = 21600  # 6 hours

    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch market prices using the existing market service.

        Expected params:
            commodity (str): Crop/commodity name.
            state (str): Indian state for regional prices.
        """
        commodity = params.get("commodity")
        if not commodity:
            return None

        try:
            from app.ai.market.service import fetch_market_prices
        except ImportError:
            logger.warning("Market service not available.")
            return None

        state = params.get("state")
        prices = await fetch_market_prices(commodity=commodity, state=state)
        if prices and prices.get("prices"):
            return prices
        return None
