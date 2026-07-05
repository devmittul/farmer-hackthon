"""
Pytest conftest for KrishiMitra backend tests.
Patches environment variables before any app module is imported.
"""
import os
import pytest

# ── Patch env before module imports ───────────────────────────────────────────
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
os.environ.setdefault("MONGODB_DB_NAME", "krishimitra_test")
os.environ.setdefault(
    "SECRET_KEY",
    "test_secret_key_that_is_definitely_long_enough_for_hs256_please"
)
os.environ.setdefault("GEMINI_API_KEY", "test_gemini_api_key")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default asyncio event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
