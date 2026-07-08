import asyncio
from app.ai.orchestrator import orchestrate
from app.schemas.requests import LanguageCode

async def main():
    try:
        res = await orchestrate(message="Hello, are you working?", language=LanguageCode.EN, session_id="test1234")
        print("Success:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
