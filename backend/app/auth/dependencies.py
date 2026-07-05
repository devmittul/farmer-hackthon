"""
KrishiMitra Backend – Auth Dependency
========================================
FastAPI dependency that validates JWT and injects the current user.
"""
import logging
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError

from app.core.security import decode_token
from app.database import get_collection

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Annotated[Optional[str], Header()] = None,
) -> dict:
    """
    FastAPI dependency that extracts and validates the bearer JWT.

    Args:
        authorization: HTTP Authorization header value.

    Returns:
        User document dict from MongoDB.

    Raises:
        HTTPException 401: If token is missing, malformed, or invalid.
        HTTPException 404: If user no longer exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not authorization or not authorization.startswith("Bearer "):
        raise credentials_exception

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = decode_token(token)
        user_id: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")

        if not user_id or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Fetch user from DB
    users = get_collection("users")
    from bson import ObjectId  # local import to avoid circular deps

    try:
        oid = ObjectId(user_id)
    except Exception:
        raise credentials_exception

    user = await users.find_one({"_id": oid, "is_active": True})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or deactivated",
        )

    user["_id"] = str(user["_id"])
    return user


# Convenience alias for Depends
CurrentUser = Annotated[dict, Depends(get_current_user)]


async def get_optional_user(
    authorization: Annotated[Optional[str], Header()] = None,
) -> Optional[dict]:
    """
    Like get_current_user but returns None instead of raising on missing token.
    Use for endpoints that allow both authenticated and anonymous access.
    """
    if not authorization:
        return None
    try:
        return await get_current_user(authorization=authorization)
    except HTTPException:
        return None


OptionalUser = Annotated[Optional[dict], Depends(get_optional_user)]
