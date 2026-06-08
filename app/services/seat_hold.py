import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Seat, SeatHold
from app.redis_client import get_redis

_LOCK_TTL_MS = 5_000
_HOLD_MINUTES = 10


async def hold_seat(seat_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> SeatHold:
    redis = await get_redis()
    lock_key = f"seat:{seat_id}"

    # Layer 1: Redis distributed lock — fast rejection under contention.
    acquired = await redis.set(lock_key, str(user_id), nx=True, px=_LOCK_TTL_MS)
    if not acquired:
        raise HTTPException(status_code=409, detail="seat_unavailable")

    try:
        return await _db_hold(seat_id, user_id, db)
    except Exception:
        # Release the lock on any DB-layer failure so the seat stays acquirable.
        await redis.delete(lock_key)
        raise


async def _db_hold(seat_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> SeatHold:
    try:
        async with db.begin():
            # FOR UPDATE NOWAIT: immediate OperationalError if another tx holds the row lock.
            result = await db.execute(
                select(Seat).where(Seat.id == seat_id).with_for_update(nowait=True)
            )
            seat = result.scalar_one_or_none()

            if seat is None:
                raise HTTPException(status_code=404, detail="seat_not_found")
            if seat.status != "available":
                raise HTTPException(status_code=409, detail="seat_unavailable")

            expires_at = datetime.now(timezone.utc) + timedelta(minutes=_HOLD_MINUTES)
            hold = SeatHold(
                seat_id=seat_id,
                user_id=user_id,
                status="held",
                expires_at=expires_at,
            )
            db.add(hold)
            seat.status = "held"
            # flush triggers the INSERT and populates server-generated id/created_at via RETURNING.
            await db.flush()
            return hold
    except IntegrityError:
        # Partial unique index udx_one_active_hold fired — another hold slipped through.
        raise HTTPException(status_code=409, detail="seat_unavailable")
    except OperationalError:
        # FOR UPDATE NOWAIT raised lock_not_available (PostgreSQL 55P03).
        raise HTTPException(status_code=409, detail="seat_unavailable")
