"""
KrishiMitra Backend – Authentication Service
=============================================
Business logic for user registration and login.
Completely separated from routes.
"""
import logging
from datetime import UTC, datetime
from typing import Any, Optional

from bson import ObjectId

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.database import get_collection
from app.schemas.requests import UserLoginRequest, UserRegisterRequest

logger = logging.getLogger(__name__)


class AuthService:
    """Handles all authentication business logic."""

    @staticmethod
    async def register(payload: UserRegisterRequest) -> dict[str, Any]:
        """
        Register a new user.

        Args:
            payload: Validated registration request.

        Returns:
            Dict with user info and JWT tokens.

        Raises:
            ValueError: If email already exists.
        """
        users = get_collection("users")

        # Uniqueness check
        existing = await users.find_one({"email": payload.email})
        if existing:
            raise ValueError("A user with this email already exists.")

        now = datetime.now(UTC)
        user_doc = {
            "name": payload.name,
            "email": payload.email,
            "phone": payload.phone,
            "hashed_password": hash_password(payload.password),
            "language": payload.language.value,
            "location": payload.location,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        result = await users.insert_one(user_doc)
        user_id = str(result.inserted_id)

        # Save language preference
        lang_col = get_collection("language_preferences")
        await lang_col.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "language": payload.language.value, "updated_at": now}},
            upsert=True,
        )

        logger.info("New user registered: %s (id=%s)", payload.email, user_id)

        access_token = create_access_token(user_id, extra_claims={"email": payload.email})
        refresh_token = create_refresh_token(user_id)

        from app.config import get_settings
        settings = get_settings()

        return {
            "user": {
                "id": user_id,
                "name": payload.name,
                "email": payload.email,
                "language": payload.language.value,
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }

    @staticmethod
    async def login(payload: UserLoginRequest) -> dict[str, Any]:
        """
        Authenticate a user and return JWT tokens.

        Args:
            payload: Validated login request.

        Returns:
            Dict with user info and JWT tokens.

        Raises:
            ValueError: If credentials are invalid.
        """
        users = get_collection("users")
        user = await users.find_one({"email": payload.email, "is_active": True})

        if not user or not verify_password(payload.password, user["hashed_password"]):
            # Generic message prevents user enumeration
            raise ValueError("Invalid email or password.")

        user_id = str(user["_id"])
        logger.info("User logged in: %s", payload.email)

        access_token = create_access_token(
            user_id, extra_claims={"email": user["email"]}
        )
        refresh_token = create_refresh_token(user_id)

        from app.config import get_settings
        settings = get_settings()

        return {
            "user": {
                "id": user_id,
                "name": user["name"],
                "email": user["email"],
                "language": user.get("language", "en"),
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }

    @staticmethod
    async def get_profile(user_id: str) -> Optional[dict[str, Any]]:
        """Fetch public profile fields for a user by ID."""
        users = get_collection("users")
        try:
            user = await users.find_one({"_id": ObjectId(user_id), "is_active": True})
        except Exception:
            return None

        if not user:
            return None

        return {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "phone": user["phone"],
            "language": user.get("language", "en"),
            "location": user.get("location"),
            "created_at": user.get("created_at"),
        }
