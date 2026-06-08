import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.database import get_db
from app.schemas import HoldOut
from app.services.seat_hold import hold_seat

router = APIRouter(prefix="/seats", tags=["seats"])


@router.post("/{seat_id}/hold", response_model=HoldOut)
async def create_hold(
    seat_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> HoldOut:
    return await hold_seat(seat_id, user_id, db)
