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
