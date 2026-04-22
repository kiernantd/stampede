from fastapi import APIRouter
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.redis_client import get_redis

router = APIRouter()


@router.get("/health")
async def health_check():
    result = {"status": "ok", "db": "ok", "redis": "ok"}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        result["db"] = "error"
        result["status"] = "degraded"

    try:
        r = await get_redis()
        await r.ping()
    except Exception:
        result["redis"] = "error"
        result["status"] = "degraded"

    return result
