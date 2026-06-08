"""
Concurrency correctness test for POST /seats/{seat_id}/hold.

Requires Docker containers running:
  docker compose up -d postgres redis
  alembic upgrade head
"""

import uuid

import anyio
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 — registers all models on Base.metadata
from app.auth import get_current_user_id
from app.config import settings
from app.database import Base
from app.main import app
from app.redis_client import get_redis


@pytest_asyncio.fixture
async def seat_contention_setup():
    """
    Create isolated test data (user → event → seat), yield (user_id, seat_id),
    then delete all rows and release the Redis lock.
    """
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    seat_id = uuid.uuid4()

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text(
                    "INSERT INTO users (id, cognito_sub, email) "
                    "VALUES (:id, :sub, :email)"
                ),
                {"id": str(user_id), "sub": f"conc-{user_id}", "email": f"{user_id}@test.com"},
            )
            await session.execute(
                text(
                    "INSERT INTO events (id, name, venue, starts_at, ends_at, created_by) "
                    "VALUES (:id, :name, :venue, now(), now() + interval '2 hours', :by)"
                ),
                {
                    "id": str(event_id),
                    "name": "Contention Test Event",
                    "venue": "Test Venue",
                    "by": str(user_id),
                },
            )
            await session.execute(
                text(
                    "INSERT INTO seats (id, event_id, label, tier, price_cents, status) "
                    "VALUES (:id, :event_id, :label, :tier, :price, :status)"
                ),
                {
                    "id": str(seat_id),
                    "event_id": str(event_id),
                    "label": "A1",
                    "tier": "GA",
                    "price": 1000,
                    "status": "available",
                },
            )

    yield user_id, seat_id

    # Teardown: delete in reverse FK order.
    async with session_factory() as session:
        async with session.begin():
            await session.execute(
                text("DELETE FROM seat_holds WHERE seat_id = :id"), {"id": str(seat_id)}
            )
            await session.execute(
                text("DELETE FROM seats WHERE id = :id"), {"id": str(seat_id)}
            )
            await session.execute(
                text("DELETE FROM events WHERE id = :id"), {"id": str(event_id)}
            )
            await session.execute(
                text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)}
            )

    # Release Redis lock in case the winning request's TTL has not expired yet.
    redis = await get_redis()
    await redis.delete(f"seat:{seat_id}")

    await engine.dispose()


async def test_exactly_one_hold_under_contention(seat_contention_setup):
    user_id, seat_id = seat_contention_setup

    app.dependency_overrides[get_current_user_id] = lambda: user_id

    try:
        results: list[int] = []

        async def send_hold() -> None:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    f"/seats/{seat_id}/hold",
                    headers={"Authorization": "Bearer fake-token"},
                )
                results.append(resp.status_code)

        async with anyio.create_task_group() as tg:
            for _ in range(100):
                tg.start_soon(send_hold)

    finally:
        app.dependency_overrides.pop(get_current_user_id, None)

    assert results.count(200) == 1, (
        f"Expected exactly 1 success; got {results.count(200)}. "
        f"All codes: {sorted(results)}"
    )
    assert results.count(409) == 99, (
        f"Expected 99 conflicts; got {results.count(409)}. "
        f"All codes: {sorted(results)}"
    )
