import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id, require_organizer
from app.database import get_db
from app.schemas import EventIn, EventOut, EventUpdate
from app.services.events import (
    cancel_event,
    create_event,
    get_event,
    list_events,
    update_event,
)

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=201)
async def create_event_route(
    body: EventIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    _: None = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    return await create_event(body, user_id, db)


@router.get("", response_model=list[EventOut])
async def list_events_route(
    page: int = 1,
    size: int = 20,
    city: str | None = None,
    date: datetime | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[EventOut]:
    return await list_events(page, size, city, date, db)


@router.get("/{event_id}", response_model=EventOut)
async def get_event_route(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    return await get_event(event_id, db)


@router.patch("/{event_id}", response_model=EventOut)
async def update_event_route(
    event_id: uuid.UUID,
    body: EventUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    _: None = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
) -> EventOut:
    return await update_event(event_id, body, user_id, db)


@router.delete("/{event_id}", status_code=204)
async def delete_event_route(
    event_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    _: None = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
) -> None:
    await cancel_event(event_id, user_id, db)
