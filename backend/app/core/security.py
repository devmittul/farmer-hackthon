"""
KrishiMitra Backend – Security Utilities
==========================================
JWT creation/verification, password hashing.
All cryptographic details stay here – nowhere else.
"""
import hashlib
import hmac
import logging
import os
import base64
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from jose import JWTError, jwt

from app.config import get_settings

logger = logging.getLogger(__name__)


# ── Password hashing (PBKDF2-SHA256 – stdlib, no C-extension deps) ────────────
def hash_password(plain: str) -> str:
    """Return a PBKDF2-SHA256 hash of *plain* with a random salt."""
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 260_000)
    encoded = base64.b64encode(salt + dk).decode()
    return f"pbkdf2:sha256:{encoded}"


def verify_password(plain: str, stored: str) -> bool:
    """Return True if *plain* matches the stored hash."""
    try:
        if not stored.startswith("pbkdf2:sha256:"):
            return False
        encoded = stored.removeprefix("pbkdf2:sha256:")
        raw = base64.b64decode(encoded.encode())
        salt, dk_stored = raw[:32], raw[32:]
        dk_new = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 260_000)
        return hmac.compare_digest(dk_new, dk_stored)
    except Exception:
        return False





# ── JWT ───────────────────────────────────────────────────────────────────────
def create_access_token(
    subject: str,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """
    Create a signed JWT access token.

    Args:
        subject: Typically the user's MongoDB _id as a string.
        extra_claims: Optional additional payload fields.

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str) -> str:
    """Create a longer-lived refresh token."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
        JWTError: If token is invalid, expired, or tampered.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError as exc:
        logger.warning("JWT decode error: %s", exc)
        raise


def extract_user_id(token: str) -> Optional[str]:
    """
    Safely extract the 'sub' (user_id) from a token.
    Returns None on any error.
    """
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except JWTError:
        return None
