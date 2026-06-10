import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id, require_organizer
from app.database import get_db
from app.schemas import VenueIn, VenueOut
from app.services.venues import create_venue, get_venue

router = APIRouter(prefix="/venues", tags=["venues"])


@router.post("", response_model=VenueOut, status_code=201)
async def create_venue_route(
    body: VenueIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    _: None = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
) -> VenueOut:
    return await create_venue(body, user_id, db)


@router.get("/{venue_id}", response_model=VenueOut)
async def get_venue_route(
    venue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> VenueOut:
    return await get_venue(venue_id, db)
