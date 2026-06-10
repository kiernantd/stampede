import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event
from app.schemas import EventIn, EventUpdate


async def create_event(body: EventIn, user_id: uuid.UUID, db: AsyncSession) -> Event:
    async with db.begin():
        event = Event(
            name=body.name,
            description=body.description,
            venue=body.venue,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            available_seats=body.available_seats,
            created_by=user_id,
        )
        db.add(event)
        await db.flush()
    return event


async def list_events(
    page: int,
    size: int,
    city: str | None,
    date: datetime | None,
    db: AsyncSession,
) -> list[Event]:
    stmt = select(Event).where(Event.status != "cancelled")
    if city is not None:
        stmt = stmt.where(Event.venue.ilike(f"%{city}%"))
    if date is not None:
        stmt = stmt.where(Event.starts_at >= date)
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_event(event_id: uuid.UUID, db: AsyncSession) -> Event:
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.status != "cancelled")
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="event_not_found")
    return event


async def update_event(
    event_id: uuid.UUID,
    body: EventUpdate,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Event:
    async with db.begin():
        result = await db.execute(
            select(Event).where(Event.id == event_id, Event.status != "cancelled")
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise HTTPException(status_code=404, detail="event_not_found")
        if event.created_by != user_id:
            raise HTTPException(status_code=403, detail="not_event_owner")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(event, field, value)
        await db.flush()
    return event


async def cancel_event(
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    async with db.begin():
        result = await db.execute(
            select(Event).where(Event.id == event_id, Event.status != "cancelled")
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise HTTPException(status_code=404, detail="event_not_found")
        if event.created_by != user_id:
            raise HTTPException(status_code=403, detail="not_event_owner")
        event.status = "cancelled"
