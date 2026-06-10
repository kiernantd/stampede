import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, Seat, SeatHold, Ticket


async def purchase_ticket(
    seat_hold_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Ticket:
    async with db.begin():
        result = await db.execute(
            select(SeatHold).where(SeatHold.id == seat_hold_id).with_for_update()
        )
        hold = result.scalar_one_or_none()

        if hold is None:
            raise HTTPException(status_code=404, detail="hold_not_found")
        if hold.user_id != user_id:
            raise HTTPException(status_code=403, detail="not_hold_owner")
        if hold.status != "held":
            raise HTTPException(status_code=409, detail="hold_not_active")
        if hold.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="hold_expired")

        result = await db.execute(select(Seat).where(Seat.id == hold.seat_id))
        seat = result.scalar_one()

        # Lock the event row for atomic available_seats decrement.
        result = await db.execute(
            select(Event).where(Event.id == seat.event_id).with_for_update()
        )
        event = result.scalar_one()

        hold.status = "confirmed"
        event.available_seats = max(0, event.available_seats - 1)

        ticket = Ticket(
            seat_hold_id=seat_hold_id,
            user_id=user_id,
            amount_cents=seat.price_cents,
        )
        db.add(ticket)
        await db.flush()
        return ticket
