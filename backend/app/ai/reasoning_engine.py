"""
KrishiMitra Backend – Reasoning Engine
========================================
Model-agnostic AI reasoning layer.

This module is the ONLY place in the entire codebase that communicates
with an AI language model.  All other modules prepare facts; this module
explains those facts via the configured LLM.

Design decisions:
  • Provider-agnostic interface: switch between Claude, Gemini, DeepSeek,
    Llama, Qwen, or any OpenAI-compatible endpoint by changing config only.
  • Currently backed by Anthropic Claude via the aerolink proxy.
  • Gemini support is wired but disabled until a valid Gemini API key is set.
  • Retry logic with exponential backoff on rate-limit errors.
  • Hard token limit enforced on the prompt side via prompt_builder.
  • Response is always plain text — the formatter handles structure.

To switch the AI provider:
  1. Set AI_PROVIDER = "gemini" | "claude" | "openai" in .env
  2. No other file needs to change.

Public API:
    from app.ai.reasoning_engine import ReasoningEngine
    reply, latency_ms = await ReasoningEngine.generate(prompt)
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Provider enum string constants ─────────────────────────────────────────────
PROVIDER_CLAUDE = "claude"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"  # any OpenAI-compatible API

# ── Singleton client holders ───────────────────────────────────────────────────
_claude_client = None
_gemini_model = None
_openai_client = None


# ── Client factory ─────────────────────────────────────────────────────────────

def _get_claude_client():
    """Lazy-initialise the Anthropic client."""
    global _claude_client
    if _claude_client is not None:
        return _claude_client
    try:
        import anthropic
        settings = get_settings()
        _claude_client = anthropic.AsyncAnthropic(
            api_key=settings.claude_api_key,
            base_url="https://capi.aerolink.lat/",
        )
        logger.info("ReasoningEngine: Claude client initialised (model=%s)",
                    settings.claude_model)
    except ImportError:
        raise RuntimeError(
            "anthropic package not installed. Run: pip install anthropic"
        )
    return _claude_client


def _get_gemini_model():
    """Lazy-initialise the Google Generative AI model."""
    global _gemini_model
    if _gemini_model is not None:
        return _gemini_model
    try:
        import google.generativeai as genai
        settings = get_settings()
        genai.configure(api_key=getattr(settings, "gemini_api_key", ""))
        _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        logger.info("ReasoningEngine: Gemini model initialised")
    except ImportError:
        raise RuntimeError(
            "google-generativeai package not installed."
        )
    return _gemini_model


# ── Main interface ─────────────────────────────────────────────────────────────

class ReasoningEngine:
    """
    Model-agnostic reasoning facade.

    Call ``ReasoningEngine.generate(prompt)`` anywhere in the codebase
    without caring which model is active.
    """

    @staticmethod
    async def generate(
        prompt: str,
        max_tokens: int = 2000,
        max_retries: int = 2,
        provider: Optional[str] = None,
    ) -> tuple[str, float]:
        """
        Send a pre-built factual prompt to the configured LLM and return
        the plain-text reasoning response.

        Args:
            prompt:      Fully assembled prompt (from prompt_builder).
            max_tokens:  Maximum tokens in the response.
            max_retries: Number of retry attempts on transient errors.
            provider:    Override the configured provider (testing only).

        Returns:
            Tuple of (response_text, latency_ms).

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        settings = get_settings()
        active_provider = provider or getattr(settings, "ai_provider", PROVIDER_CLAUDE)

        if active_provider == PROVIDER_GEMINI:
            return await ReasoningEngine._call_gemini(prompt, max_tokens, max_retries)
        elif active_provider == PROVIDER_OPENAI:
            return await ReasoningEngine._call_openai(prompt, max_tokens, max_retries)
        else:
            return await ReasoningEngine._call_claude(prompt, max_tokens, max_retries)

    # ── Claude ────────────────────────────────────────────────────────────────
    @staticmethod
    async def _call_claude(
        prompt: str,
        max_tokens: int,
        max_retries: int,
    ) -> tuple[str, float]:
        client = _get_claude_client()
        settings = get_settings()
        model_name = settings.claude_model
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                start = time.perf_counter()
                response = await client.messages.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                elapsed_ms = (time.perf_counter() - start) * 1000

                parts = [
                    getattr(block, "text", "")
                    for block in response.content
                    if getattr(block, "type", "") == "text"
                ]
                text = "\n".join(parts).strip()

                logger.info(
                    "ReasoningEngine [Claude]: %.1fms attempt=%d tokens=%d",
                    elapsed_ms, attempt + 1, max_tokens,
                )
                return text, round(elapsed_ms, 2)

            except Exception as exc:
                last_error = exc
                err = str(exc).lower()
                logger.warning("Claude attempt %d/%d failed: %s", attempt + 1,
                               max_retries + 1, exc)

                if "429" in err or "rate limit" in err:
                    wait = 2.0 * (attempt + 1)
                    await asyncio.sleep(wait)
                elif attempt < max_retries:
                    await asyncio.sleep(1.0)
                else:
                    break

        raise RuntimeError(
            f"Claude reasoning failed after {max_retries + 1} attempts. "
            f"Last error: {last_error}"
        )

    # ── Gemini ────────────────────────────────────────────────────────────────
    @staticmethod
    async def _call_gemini(
        prompt: str,
        max_tokens: int,
        max_retries: int,
    ) -> tuple[str, float]:
        model = _get_gemini_model()
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                start = time.perf_counter()
                # google-generativeai is sync; wrap in thread
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                text = response.text.strip()
                logger.info("ReasoningEngine [Gemini]: %.1fms", elapsed_ms)
                return text, round(elapsed_ms, 2)

            except Exception as exc:
                last_error = exc
                logger.warning("Gemini attempt %d failed: %s", attempt + 1, exc)
                await asyncio.sleep(1.5 * (attempt + 1))

        raise RuntimeError(f"Gemini reasoning failed. Last error: {last_error}")

    # ── OpenAI-compatible ─────────────────────────────────────────────────────
    @staticmethod
    async def _call_openai(
        prompt: str,
        max_tokens: int,
        max_retries: int,
    ) -> tuple[str, float]:
        """Supports any OpenAI-compatible API (local Llama, Qwen, DeepSeek, etc.)."""
        global _openai_client
        if _openai_client is None:
            try:
                from openai import AsyncOpenAI
                settings = get_settings()
                _openai_client = AsyncOpenAI(
                    api_key=getattr(settings, "openai_api_key", ""),
                    base_url=getattr(settings, "openai_base_url", ""),
                )
            except ImportError:
                raise RuntimeError("openai package not installed.")

        last_error: Optional[Exception] = None
        settings = get_settings()
        model_name = getattr(settings, "openai_model", "gpt-4o-mini")

        for attempt in range(max_retries + 1):
            try:
                start = time.perf_counter()
                resp = await _openai_client.chat.completions.create(
                    model=model_name,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                text = resp.choices[0].message.content.strip()
                logger.info("ReasoningEngine [OpenAI-compat]: %.1fms", elapsed_ms)
                return text, round(elapsed_ms, 2)

            except Exception as exc:
                last_error = exc
                logger.warning("OpenAI attempt %d failed: %s", attempt + 1, exc)
                await asyncio.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"OpenAI reasoning failed. Last error: {last_error}")


# ── Backward-compat shim ───────────────────────────────────────────────────────
# Preserves the old gemini_client.generate_response() call signature so that
# any existing service that hasn't been migrated yet continues to work.
async def generate_response(prompt: str, max_retries: int = 2) -> tuple[str, float]:
    """
    Backward-compatible shim.
    Old code: from app.ai import gemini_client; gemini_client.generate_response(p)
    Should gradually be replaced with ReasoningEngine.generate(p).
    """
    return await ReasoningEngine.generate(prompt, max_retries=max_retries)
