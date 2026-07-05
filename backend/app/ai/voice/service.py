"""
KrishiMitra Backend – Voice Service
=====================================
Speech-to-Text: faster-whisper (local, no API key)
Text-to-Speech: Piper TTS (local, no API key)

Both models are lazy-loaded on first use to keep startup fast.
Audio files are written to AUDIO_OUTPUT_DIR and served statically.
"""
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Lazy-loaded Whisper model
_whisper_model = None


def _get_whisper_model():
    """Lazy-load faster-whisper model on first STT call."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    try:
        from faster_whisper import WhisperModel

        settings = get_settings()
        logger.info("Loading Whisper model: %s", settings.whisper_model_size)
        _whisper_model = WhisperModel(
            settings.whisper_model_size,
            device="cpu",
            compute_type="int8",
        )
        logger.info("Whisper model loaded.")
        return _whisper_model
    except ImportError:
        logger.warning(
            "faster-whisper not installed. STT unavailable. "
            "Install with: pip install faster-whisper"
        )
        return None


async def speech_to_text(audio_bytes: bytes, mime_type: str = "audio/webm") -> Optional[str]:
    """
    Transcribe audio bytes to text using faster-whisper.

    Args:
        audio_bytes: Raw audio file bytes.
        mime_type: Audio MIME type (informational).

    Returns:
        Transcribed text string, or None if transcription fails.
    """
    model = _get_whisper_model()
    if not model:
        raise RuntimeError(
            "Speech-to-Text is unavailable. faster-whisper is not installed."
        )

    # Write to temp file (faster-whisper requires a file path)
    tmp_path = Path(f"/tmp/km_audio_{uuid.uuid4().hex}.webm")
    try:
        tmp_path.write_bytes(audio_bytes)
        segments, info = model.transcribe(
            str(tmp_path),
            beam_size=5,
            language=None,  # Auto-detect language
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = " ".join(seg.text for seg in segments).strip()
        logger.info(
            "STT: transcribed %d chars (lang=%s, prob=%.2f)",
            len(text),
            info.language,
            info.language_probability,
        )
        return text if text else None
    except Exception as exc:
        logger.error("Whisper transcription error: %s", exc)
        return None
    finally:
        tmp_path.unlink(missing_ok=True)


async def text_to_speech(
    text: str,
    language_code: str = "en",
    output_filename: Optional[str] = None,
) -> Optional[str]:
    """
    Convert text to speech using Piper TTS.

    Args:
        text: Text to synthesise.
        language_code: Language code (e.g., "en", "hi").
        output_filename: Optional filename for the output audio.

    Returns:
        Relative path to the generated audio file, or None on failure.
    """
    settings = get_settings()
    output_dir = Path(settings.audio_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = output_filename or f"tts_{uuid.uuid4().hex}.wav"
    output_path = output_dir / filename

    # Map language codes to Piper model paths
    model_map = {
        "en": "en_US-lessac-medium.onnx",
        "hi": "hi_IN-dhruva-medium.onnx",
        "gu": "gu_IN-generic.onnx",
        "mr": "mr_IN-generic.onnx",
        "te": "te_IN-generic.onnx",
        "ta": "ta_IN-generic.onnx",
        "kn": "kn_IN-generic.onnx",
        "ml": "ml_IN-generic.onnx",
        "bn": "bn_IN-generic.onnx",
    }

    model_file = model_map.get(language_code, model_map["en"])
    model_path = Path(settings.piper_model_path) / model_file

    if not model_path.exists():
        logger.warning(
            "Piper model not found: %s. TTS unavailable for lang=%s.",
            model_path,
            language_code,
        )
        return None

    try:
        import subprocess

        # Use Piper CLI: echo text | piper --model <model> --output_file <file>
        result = subprocess.run(
            ["piper", "--model", str(model_path), "--output_file", str(output_path)],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error("Piper TTS error: %s", result.stderr.decode())
            return None

        logger.info("TTS generated: %s (%d bytes)", filename, output_path.stat().st_size)
        return f"/audio/{filename}"

    except FileNotFoundError:
        logger.warning("Piper TTS binary not found. Install from https://github.com/rhasspy/piper")
        return None
    except subprocess.TimeoutExpired:
        logger.error("Piper TTS timed out for text length %d", len(text))
        return None
    except Exception as exc:
        logger.error("TTS error: %s", exc)
        return None
