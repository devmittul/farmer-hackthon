"""
KrishiMitra Backend – Chat Route
===================================
POST /chat  – Main AI chat endpoint via orchestrator
GET  /history – Retrieve chat history for authenticated user
"""
import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.ai.orchestrator import orchestrate
from app.auth.dependencies import CurrentUser, OptionalUser
from app.database import get_collection
from app.schemas.requests import ChatRequest
from app.schemas.responses import success_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI Chat"])


@router.post(
    "/chat",
    summary="Send a message to the AI assistant",
    response_description="AI response with intent, data, and optional audio URL",
)
async def chat(
    payload: ChatRequest,
    current_user: OptionalUser,
) -> dict:
    """
    Main chat endpoint. All messages pass through the AI Orchestrator.

    **Flow:**
    1. Detect language (auto if not provided)
    2. Detect intent (CHAT/WEATHER/CROP/ROUTE/COURIER/SOS/MARKET)
    3. Collect relevant context (weather, ML predictions, route data)
    4. Build structured prompt
    5. Call Gemini for explanation
    6. Persist to chat history
    7. Return structured JSON response

    Authentication is optional – anonymous users get full AI access.
    """
    user_id = current_user["_id"] if current_user else None

    try:
        result = await orchestrate(
            message=payload.message,
            language=payload.language,
            location=payload.location,
            session_id=payload.session_id,
            user_id=user_id,
            field_id=payload.field_id,        # ← Digital Twin field context
        )
        return result
    except Exception as exc:
        logger.exception("Chat orchestration error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process your message. Please try again.",
        )


@router.get(
    "/history",
    summary="Get chat history for the current user",
    response_description="List of past chat exchanges",
)
async def get_history(
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    session_id: str = Query(default=None),
) -> dict:
    """
    Retrieve paginated chat history for the authenticated user.

    - Supports filtering by session_id
    - Returns newest messages first
    - Requires authentication
    """
    col = get_collection("chat_history")
    query: dict = {"user_id": current_user["_id"]}
    if session_id:
        query["session_id"] = session_id

    cursor = col.find(query, {"context_data": 0}).sort("created_at", -1).skip(skip).limit(limit)
    total = await col.count_documents(query)

    history = []
    async for doc in cursor:
        history.append(
            {
                "id": str(doc["_id"]),
                "session_id": doc.get("session_id"),
                "user_message": doc.get("user_message"),
                "assistant_reply": doc.get("assistant_reply"),
                "intent": doc.get("intent"),
                "language": doc.get("language"),
                "latency_ms": doc.get("latency_ms"),
                "created_at": doc.get("created_at"),
            }
        )

    return success_response(
        data=history,
        message=f"{len(history)} messages retrieved.",
        metadata={"total": total, "skip": skip, "limit": limit},
    )
