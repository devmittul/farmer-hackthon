import asyncio
from app.ai.providers.geesoil_provider import GEESoilProvider

async def main():
    provider = GEESoilProvider()
    res = await provider.execute({
        "latitude": 21.0,
        "longitude": 79.0,
        "location_name": "Test Farm 2",
        "boundary": None
    })
    print("Available:", res.available)
    print("Data:", res.data)
    
if __name__ == "__main__":
    asyncio.run(main())
