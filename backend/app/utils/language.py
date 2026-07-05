"""
KrishiMitra Backend – Language Detection Utility
=================================================
Detects the language of a text string and maps it to a LanguageCode.
"""
import logging
from typing import Optional

from app.schemas.requests import LanguageCode

logger = logging.getLogger(__name__)

# Map langdetect ISO codes → our LanguageCode
_LANG_MAP: dict[str, LanguageCode] = {
    "en": LanguageCode.EN,
    "hi": LanguageCode.HI,
    "gu": LanguageCode.GU,
    "pa": LanguageCode.PA,
    "mr": LanguageCode.MR,
    "ta": LanguageCode.TA,
    "te": LanguageCode.TE,
    "kn": LanguageCode.KN,
    "ml": LanguageCode.ML,
    "bn": LanguageCode.BN,
}


def detect_language(text: str) -> LanguageCode:
    """
    Detect the language of *text* and return a LanguageCode.
    Falls back to English if detection fails or the language is unsupported.

    Args:
        text: Input string from user.

    Returns:
        Detected LanguageCode.
    """
    try:
        from langdetect import detect  # lazy import

        iso_code: str = detect(text)
        lang = _LANG_MAP.get(iso_code)
        if lang:
            return lang
        # Try prefix match (e.g., "zh-cn" → "zh")
        prefix = iso_code.split("-")[0]
        return _LANG_MAP.get(prefix, LanguageCode.EN)
    except Exception as exc:
        logger.debug("Language detection failed: %s – defaulting to EN", exc)
        return LanguageCode.EN


LANGUAGE_NAMES: dict[LanguageCode, str] = {
    LanguageCode.EN: "English",
    LanguageCode.HI: "Hindi",
    LanguageCode.GU: "Gujarati",
    LanguageCode.PA: "Punjabi",
    LanguageCode.MR: "Marathi",
    LanguageCode.TA: "Tamil",
    LanguageCode.TE: "Telugu",
    LanguageCode.KN: "Kannada",
    LanguageCode.ML: "Malayalam",
    LanguageCode.BN: "Bengali",
}
