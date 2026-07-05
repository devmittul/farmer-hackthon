"""
KrishiMitra Backend – Intent Detector
=======================================
Classifies a raw user message into one of the supported IntentType values
using a keyword-priority tree.

Design decisions:
  • Completely deterministic — no AI, no network, no I/O.
  • New intents can be added by appending to INTENT_RULES without changing
    any other module.
  • Priority order is defined explicitly via the PRIORITY list so the most
    urgent intents (SOS) are always evaluated first.
  • Each keyword entry can be a plain string (case-insensitive substring) or
    a compiled regex pattern for richer matching.

Usage:
    from app.ai.intent_detector import IntentDetector
    intent = IntentDetector.detect("mausam kaisa rahega kal")
    # → IntentType.WEATHER
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Pattern, Union

from app.schemas.requests import IntentType

logger = logging.getLogger(__name__)

# ── Type alias ─────────────────────────────────────────────────────────────────
Keyword = Union[str, Pattern[str]]


# ── Keyword rule sets ─────────────────────────────────────────────────────────
# Each entry may be a plain substring (case-insensitive) OR a compiled regex.
# To add a new intent: add it to IntentType enum, add a rule set here,
# and insert it at the correct position in PRIORITY_ORDER.

INTENT_RULES: Dict[IntentType, List[Keyword]] = {

    IntentType.SOS: [
        "emergency", "help me", "sos", "accident", "fire", "flood",
        "danger", "injury", "injured", "dying", "trapped",
        # Hindi / regional
        "madad", "bachao", "khatara", "aafat", "aag lagi", "baadh",
        "durghatna",
    ],

    IntentType.WEATHER: [
        "weather", "rain", "temperature", "forecast", "humidity",
        "wind", "monsoon", "drought", "fog", "hail", "storm",
        "barish", "mausam", "tapman", "baarish", "varshaad",
        "varsha", "aandhi", "toofan",
        re.compile(r"\bhow\s+hot\b", re.IGNORECASE),
        re.compile(r"\bwill\s+it\s+rain\b", re.IGNORECASE),
    ],

    IntentType.CROP: [
        "crop", "plant", "grow", "soil", "fertilizer", "seed",
        "harvest", "sow", "sowing", "irrigation", "pesticide",
        "insect", "disease", "fungus", "yield", "fasal",
        "beej", "ugaana", "khet", "kheti", "buwai", "kisan",
        "fasal rog", "keetnaashak", "upaj",
        re.compile(r"\bwhat\s+crop\b", re.IGNORECASE),
        re.compile(r"\bwhich\s+crop\b", re.IGNORECASE),
    ],

    IntentType.VEHICLE: [
        "vehicle", "truck", "tractor", "transport", "lorry",
        "book vehicle", "load", "booking",
        "gaadi", "truck book", "transport karna",
        re.compile(r"\bhow\s+many\s+trucks\b", re.IGNORECASE),
    ],

    IntentType.ROUTE: [
        "route", "road", "path", "direction", "drive", "travel",
        "navigate", "how to reach", "distance",
        "rasta", "marg", "safar", "pahuncha", "kaise jaana",
        re.compile(r"\bfrom\s+\w+\s+to\s+\w+\b", re.IGNORECASE),
    ],

    IntentType.MARKET: [
        "price", "market", "mandi", "sell", "buy", "rate",
        "bhav", "daam", "bechna", "khareedna", "market price",
        "enam", "apmc", "sabzi mandi",
        re.compile(r"\bprice\s+of\s+\w+\b", re.IGNORECASE),
        re.compile(r"\btoday('s)?\s+rate\b", re.IGNORECASE),
    ],

    IntentType.COURIER: [
        "courier", "delivery", "send", "package", "parcel",
        "transport goods", "courier service", "deliver",
        "bhejana", "parcel bhejo",
    ],

    IntentType.VOICE: [
        "speak", "voice", "audio", "listen", "say it",
        "bolna", "sunao", "awaaz",
    ],

    IntentType.IMAGE: [
        "image", "photo", "picture", "scan", "identify plant",
        "leaf image", "plant disease photo",
        "tasveer", "foto",
    ],
}


# ── Evaluation priority (first match wins) ─────────────────────────────────────
PRIORITY_ORDER: List[IntentType] = [
    IntentType.SOS,
    IntentType.WEATHER,
    IntentType.CROP,
    IntentType.VEHICLE,
    IntentType.ROUTE,
    IntentType.MARKET,
    IntentType.COURIER,
    IntentType.VOICE,
    IntentType.IMAGE,
]


class IntentDetector:
    """
    Stateless intent classifier.

    All methods are class-methods / static-methods so no instantiation
    is required — simply call ``IntentDetector.detect(message)``.
    """

    @staticmethod
    def detect(message: str) -> IntentType:
        """
        Classify *message* into the highest-priority matching IntentType.

        Args:
            message: Raw user input string.

        Returns:
            Matched IntentType, or IntentType.CHAT if nothing matches.
        """
        lower = message.lower().strip()

        for intent in PRIORITY_ORDER:
            for kw in INTENT_RULES.get(intent, []):
                if isinstance(kw, str):
                    if kw in lower:
                        logger.debug("Intent='%s' matched keyword='%s'", intent, kw)
                        return intent
                else:
                    # compiled regex
                    if kw.search(lower):
                        logger.debug("Intent='%s' matched regex='%s'", intent, kw.pattern)
                        return intent

        logger.debug("No keyword matched – defaulting to CHAT")
        return IntentType.CHAT

    @classmethod
    def detect_with_scores(cls, message: str) -> Dict[IntentType, int]:
        """
        Return a match-count score for every intent.

        Useful for debugging and for the ConfidenceEngine to understand
        how ambiguous the message is.

        Args:
            message: Raw user input string.

        Returns:
            Dict mapping each IntentType to the number of keywords matched.
        """
        lower = message.lower()
        scores: Dict[IntentType, int] = {}

        for intent, keywords in INTENT_RULES.items():
            count = 0
            for kw in keywords:
                if isinstance(kw, str):
                    if kw in lower:
                        count += 1
                else:
                    if kw.search(lower):
                        count += 1
            scores[intent] = count

        return scores
