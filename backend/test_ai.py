import asyncio
import logging
from app.ai.reasoning_engine import ReasoningEngine

logging.basicConfig(level=logging.INFO)

async def test():
    try:
        reply, latency = await ReasoningEngine.generate("Hello, how are you?")
        print("Reply:", reply)
        print("Latency:", latency)
    except Exception as e:
        print("Error:", repr(e))

asyncio.run(test())
