"""Tests for /venues endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from unittest.mock import MagicMock

from app.auth import get_current_groups, get_current_user_id
from app.main import app

USER_ID = uuid.uuid4()
VENUE_ID = uuid.uuid4()
_CREATED = datetime(2026, 1, 1, tzinfo=timezone.utc)

_CREATE_BODY = {
    "name": "Madison Square Garden",
    "address": "4 Pennsylvania Plaza",
    "city": "New York",
    "capacity": 20000,
    "seat_map": '{"sections": ["floor", "lower", "upper"]}',
}


def _fake_venue(**overrides) -> MagicMock:
    v = MagicMock()
    v.id = VENUE_ID
    v.name = "Madison Square Garden"
    v.address = "4 Pennsylvania Plaza"
    v.city = "New York"
    v.capacity = 20000
    v.seat_map = '{"sections": ["floor", "lower", "upper"]}'
    v.created_by = USER_ID
    v.created_at = _CREATED
    for k, val in overrides.items():
        setattr(v, k, val)
    return v


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /venues
# ---------------------------------------------------------------------------

async def test_create_venue_happy_path(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: ["organizer"]

    with patch("app.routers.venues.create_venue", new=AsyncMock(return_value=_fake_venue())):
        response = await client.post("/venues", json=_CREATE_BODY)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Madison Square Garden"
    assert data["capacity"] == 20000
    assert data["seat_map"] is not None


async def test_create_venue_missing_organizer_role(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: []

    response = await client.post("/venues", json=_CREATE_BODY)

    assert response.status_code == 403
    assert response.json()["detail"] == "organizer_role_required"


# ---------------------------------------------------------------------------
# GET /venues/{id}
# ---------------------------------------------------------------------------

async def test_get_venue_happy_path(client: AsyncClient):
    with patch("app.routers.venues.get_venue", new=AsyncMock(return_value=_fake_venue())):
        response = await client.get(f"/venues/{VENUE_ID}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(VENUE_ID)
    assert data["seat_map"] is not None


async def test_get_venue_not_found(client: AsyncClient):
    with patch(
        "app.routers.venues.get_venue",
        new=AsyncMock(side_effect=HTTPException(404, detail="venue_not_found")),
    ):
        response = await client.get(f"/venues/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "venue_not_found"
