"""
Chat History Provider – loads recent conversations from MongoDB.

Wraps the existing chat_history collection query.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.ai.providers import BaseProvider, FreshnessLevel

logger = logging.getLogger(__name__)


class ChatHistoryProvider(BaseProvider):
    name = "chat_history"
    freshness = FreshnessLevel.LIVE
    default_ttl = 0  # Never cached

    async def fetch(self, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Load the last 5 chat exchanges for conversation continuity.

        Expected params:
            user_id (str): Authenticated user's MongoDB _id.
        """
        user_id = params.get("user_id")
        if not user_id:
            return None

        try:
            from app.database import get_collection

            col = get_collection("chat_history")
            cursor = (
                col.find({"user_id": user_id}, {"context_data": 0})
                .sort("created_at", -1)
                .limit(5)
            )
            history: List[Dict[str, Any]] = []
            async for doc in cursor:
                history.append({
                    "role": "assistant",
                    "user_said": doc.get("user_message"),
                    "assistant_replied": doc.get("assistant_reply"),
                    "intent": doc.get("intent"),
                    "created_at": str(doc.get("created_at", "")),
                })

            if history:
                return {"recent_chat": list(reversed(history))}
            return None

        except Exception as exc:
            logger.error("ChatHistoryProvider: %s", exc)
            return None
