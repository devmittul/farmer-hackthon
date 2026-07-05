import asyncio
import sys
import os

sys.path.append(os.path.abspath('backend'))
from app.config import Settings
from app.ai.reasoning_engine import ReasoningEngine
import logging

logging.basicConfig(level=logging.INFO)

async def test_claude():
    try:
        reply, latency = await ReasoningEngine.generate("Hello, are you working?", max_retries=1)
        print("Success:", reply, "Latency:", latency)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test_claude())
