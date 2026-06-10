import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Venue
from app.schemas import VenueIn


async def create_venue(body: VenueIn, user_id: uuid.UUID, db: AsyncSession) -> Venue:
    async with db.begin():
        venue = Venue(
            name=body.name,
            address=body.address,
            city=body.city,
            capacity=body.capacity,
            seat_map=body.seat_map,
            created_by=user_id,
        )
        db.add(venue)
        await db.flush()
    return venue


async def get_venue(venue_id: uuid.UUID, db: AsyncSession) -> Venue:
    result = await db.execute(select(Venue).where(Venue.id == venue_id))
    venue = result.scalar_one_or_none()
    if venue is None:
        raise HTTPException(status_code=404, detail="venue_not_found")
    return venue
