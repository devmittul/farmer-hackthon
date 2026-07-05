"""
KrishiMitra Backend – Authentication Routes
============================================
POST /auth/register
POST /auth/login
GET  /auth/me
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import CurrentUser
from app.schemas.requests import UserLoginRequest, UserRegisterRequest
from app.schemas.responses import error_response, success_response
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    summary="Register a new user",
    response_description="JWT tokens and user profile",
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: UserRegisterRequest) -> dict:
    """
    Register a new user account.

    - Validates email uniqueness
    - Hashes password with bcrypt
    - Returns JWT access + refresh tokens
    """
    try:
        result = await AuthService.register(payload)
        return success_response(data=result, message="Registration successful.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except Exception as exc:
        logger.exception("Registration error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        )


@router.post(
    "/login",
    summary="Login with email and password",
    response_description="JWT tokens and user profile",
)
async def login(payload: UserLoginRequest) -> dict:
    """
    Authenticate a user and return JWT tokens.

    - Verifies bcrypt password
    - Returns access token (60 min) and refresh token (30 days)
    """
    try:
        result = await AuthService.login(payload)
        return success_response(data=result, message="Login successful.")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as exc:
        logger.exception("Login error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed. Please try again.",
        )


@router.get(
    "/me",
    summary="Get current user profile",
    response_description="Authenticated user profile",
)
async def get_me(current_user: CurrentUser) -> dict:
    """
    Return the profile of the currently authenticated user.
    Requires: Authorization: Bearer <token>
    """
    profile = await AuthService.get_profile(current_user["_id"])
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return success_response(data=profile, message="Profile retrieved.")
