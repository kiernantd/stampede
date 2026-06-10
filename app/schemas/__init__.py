import uuid
from datetime import datetime

from pydantic import BaseModel


class HoldOut(BaseModel):
    id: uuid.UUID
    seat_id: uuid.UUID
    user_id: uuid.UUID
    status: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Events ---

class EventIn(BaseModel):
    name: str
    description: str | None = None
    venue: str
    starts_at: datetime
    ends_at: datetime
    available_seats: int = 0


class EventUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    venue: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    available_seats: int | None = None


class EventOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    venue: str
    starts_at: datetime
    ends_at: datetime
    status: str
    available_seats: int
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Venues ---

class VenueIn(BaseModel):
    name: str
    address: str | None = None
    city: str | None = None
    capacity: int
    seat_map: str | None = None


class VenueOut(BaseModel):
    id: uuid.UUID
    name: str
    address: str | None
    city: str | None
    capacity: int
    seat_map: str | None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Tickets ---

class TicketIn(BaseModel):
    seat_hold_id: uuid.UUID


class TicketOut(BaseModel):
    id: uuid.UUID
    seat_hold_id: uuid.UUID
    user_id: uuid.UUID
    purchased_at: datetime
    amount_cents: int
    created_at: datetime

    model_config = {"from_attributes": True}
