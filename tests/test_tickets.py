"""Tests for POST /tickets (seat hold → confirmed ticket)."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from unittest.mock import MagicMock

from app.auth import get_current_user_id
from app.main import app

USER_ID = uuid.uuid4()
HOLD_ID = uuid.uuid4()
TICKET_ID = uuid.uuid4()
_NOW = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)


def _fake_ticket(**overrides) -> MagicMock:
    t = MagicMock()
    t.id = TICKET_ID
    t.seat_hold_id = HOLD_ID
    t.user_id = USER_ID
    t.purchased_at = _NOW
    t.amount_cents = 5000
    t.created_at = _NOW
    for k, v in overrides.items():
        setattr(t, k, v)
    return t


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /tickets — happy path
# ---------------------------------------------------------------------------

async def test_purchase_ticket_happy_path(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID

    with patch(
        "app.routers.tickets.purchase_ticket",
        new=AsyncMock(return_value=_fake_ticket()),
    ):
        response = await client.post("/tickets", json={"seat_hold_id": str(HOLD_ID)})

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == str(TICKET_ID)
    assert data["seat_hold_id"] == str(HOLD_ID)
    assert data["amount_cents"] == 5000


# ---------------------------------------------------------------------------
# POST /tickets — 403 (hold belongs to a different user)
# ---------------------------------------------------------------------------

async def test_purchase_ticket_not_hold_owner(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID

    with patch(
        "app.routers.tickets.purchase_ticket",
        new=AsyncMock(side_effect=HTTPException(403, detail="not_hold_owner")),
    ):
        response = await client.post("/tickets", json={"seat_hold_id": str(HOLD_ID)})

    assert response.status_code == 403
    assert response.json()["detail"] == "not_hold_owner"


# ---------------------------------------------------------------------------
# POST /tickets — 404 (hold does not exist)
# ---------------------------------------------------------------------------

async def test_purchase_ticket_hold_not_found(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID

    with patch(
        "app.routers.tickets.purchase_ticket",
        new=AsyncMock(side_effect=HTTPException(404, detail="hold_not_found")),
    ):
        response = await client.post("/tickets", json={"seat_hold_id": str(uuid.uuid4())})

    assert response.status_code == 404
    assert response.json()["detail"] == "hold_not_found"


# ---------------------------------------------------------------------------
# POST /tickets — 409 (hold already confirmed — duplicate purchase attempt)
# ---------------------------------------------------------------------------

async def test_purchase_ticket_already_confirmed(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID

    with patch(
        "app.routers.tickets.purchase_ticket",
        new=AsyncMock(side_effect=HTTPException(409, detail="hold_not_active")),
    ):
        response = await client.post("/tickets", json={"seat_hold_id": str(HOLD_ID)})

    assert response.status_code == 409
    assert response.json()["detail"] == "hold_not_active"
