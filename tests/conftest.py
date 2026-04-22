import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.redis_client import close_redis


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    # Reset the Redis singleton between tests
    await close_redis()
