"""
KrishiMitra Backend – Voice Route
====================================
POST /voice – Speech-to-text + AI response + text-to-speech
"""
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.ai.orchestrator import orchestrate
from app.ai.voice.service import speech_to_text, text_to_speech
from app.auth.dependencies import OptionalUser
from app.schemas.requests import LanguageCode
from app.schemas.responses import success_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Voice"])

MAX_AUDIO_SIZE_MB = 10


@router.post(
    "/voice",
    summary="Process voice input and return AI response with audio",
    response_description="Transcribed text, AI reply, and audio URL",
)
async def voice_chat(
    audio: UploadFile = File(..., description="Audio file (webm, wav, mp3, ogg)"),
    language: str = Form(default="en"),
    location: str = Form(default=None),
    session_id: str = Form(default=None),
    current_user: OptionalUser = None,
) -> dict:
    """
    Full voice pipeline:
    1. Receive audio upload
    2. Transcribe with faster-whisper (local STT)
    3. Pass transcription through AI Orchestrator
    4. Generate audio reply with Piper TTS
    5. Return JSON with transcription, reply, and audio URL

    Supports: webm, wav, mp3, ogg, m4a
    Max file size: 10 MB
    """
    # ── Validate file size ────────────────────────────────────────────────────
    audio_bytes = await audio.read()
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_AUDIO_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Audio file too large ({size_mb:.1f}MB). Maximum is {MAX_AUDIO_SIZE_MB}MB.",
        )

    # ── Validate language ─────────────────────────────────────────────────────
    try:
        lang_code = LanguageCode(language)
    except ValueError:
        lang_code = LanguageCode.EN

    user_id = current_user["_id"] if current_user else None

    # ── Step 1: Speech to Text ────────────────────────────────────────────────
    try:
        transcribed_text = await speech_to_text(
            audio_bytes=audio_bytes,
            mime_type=audio.content_type or "audio/webm",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    if not transcribed_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not transcribe audio. Please speak clearly and try again.",
        )

    logger.info("Voice STT: '%s...'", transcribed_text[:60])

    # ── Step 2: Orchestrate AI Response ──────────────────────────────────────
    try:
        ai_result = await orchestrate(
            message=transcribed_text,
            language=lang_code,
            location=location,
            session_id=session_id,
            user_id=user_id,
        )
    except Exception as exc:
        logger.exception("Voice orchestration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI processing failed. Please try again.",
        )

    inner_data = ai_result.get("data", {})
    reply_text: str = inner_data.get("reply", "")

    # ── Step 3: Text to Speech ────────────────────────────────────────────────
    audio_url = await text_to_speech(
        text=reply_text,
        language_code=lang_code.value,
    )

    return success_response(
        data={
            "transcription": transcribed_text,
            "reply": reply_text,
            "intent": inner_data.get("intent"),
            "language": inner_data.get("language"),
            "audio_url": audio_url,
            "session_id": inner_data.get("session_id"),
            # Remove any recursive 'data' field to avoid confusion or extract specific fields if needed
        },
        message="Voice processed successfully.",
        metadata=ai_result.get("metadata"),
    )
