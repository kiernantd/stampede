import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_health_shape(client: AsyncClient):
    response = await client.get("/health")
    data = response.json()
    assert set(data.keys()) == {"status", "db", "redis"}


@pytest.mark.asyncio
async def test_health_db_down(monkeypatch):
    """When Postgres is unreachable, status degrades gracefully."""
    from app.routers import health as health_module
    from sqlalchemy.ext.asyncio import AsyncSession

    class _BrokenSession:
        async def execute(self, *_):
            raise OSError("connection refused")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    class _BrokenSessionFactory:
        def __call__(self):
            return _BrokenSession()

    monkeypatch.setattr(health_module, "AsyncSessionLocal", _BrokenSessionFactory())

    async with AsyncClient(
        transport=__import__("httpx").ASGITransport(app=__import__("app.main", fromlist=["app"]).app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["db"] == "error"
    assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_redis_down(monkeypatch):
    """When Redis is unreachable, status degrades gracefully."""
    from app.routers import health as health_module

    async def _broken_redis():
        class _FakeRedis:
            async def ping(self):
                raise OSError("connection refused")

        return _FakeRedis()

    monkeypatch.setattr(health_module, "get_redis", _broken_redis)

    async with AsyncClient(
        transport=__import__("httpx").ASGITransport(app=__import__("app.main", fromlist=["app"]).app),
        base_url="http://test",
    ) as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["redis"] == "error"
    assert data["status"] == "degraded"
