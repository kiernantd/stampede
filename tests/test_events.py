"""Tests for /events endpoints."""

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
EVENT_ID = uuid.uuid4()

_STARTS = datetime(2027, 6, 1, 20, 0, tzinfo=timezone.utc)
_ENDS = datetime(2027, 6, 1, 23, 0, tzinfo=timezone.utc)
_CREATED = datetime(2026, 1, 1, tzinfo=timezone.utc)

_CREATE_BODY = {
    "name": "Test Concert",
    "venue": "Madison Square Garden",
    "starts_at": _STARTS.isoformat(),
    "ends_at": _ENDS.isoformat(),
    "available_seats": 500,
}


def _fake_event(**overrides) -> MagicMock:
    e = MagicMock()
    e.id = EVENT_ID
    e.name = "Test Concert"
    e.description = None
    e.venue = "Madison Square Garden"
    e.starts_at = _STARTS
    e.ends_at = _ENDS
    e.status = "active"
    e.available_seats = 500
    e.created_by = USER_ID
    e.created_at = _CREATED
    for k, v in overrides.items():
        setattr(e, k, v)
    return e


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /events
# ---------------------------------------------------------------------------

async def test_create_event_happy_path(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: ["organizer"]

    with patch("app.routers.events.create_event", new=AsyncMock(return_value=_fake_event())):
        response = await client.post("/events", json=_CREATE_BODY)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Concert"
    assert data["status"] == "active"
    assert data["available_seats"] == 500


async def test_create_event_missing_organizer_role(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: []

    response = await client.post("/events", json=_CREATE_BODY)

    assert response.status_code == 403
    assert response.json()["detail"] == "organizer_role_required"


# ---------------------------------------------------------------------------
# GET /events
# ---------------------------------------------------------------------------

async def test_list_events_happy_path(client: AsyncClient):
    events = [_fake_event(), _fake_event(id=uuid.uuid4(), name="Second Show")]

    with patch("app.routers.events.list_events", new=AsyncMock(return_value=events)):
        response = await client.get("/events")

    assert response.status_code == 200
    assert len(response.json()) == 2


# ---------------------------------------------------------------------------
# GET /events/{id}
# ---------------------------------------------------------------------------

async def test_get_event_happy_path(client: AsyncClient):
    with patch("app.routers.events.get_event", new=AsyncMock(return_value=_fake_event())):
        response = await client.get(f"/events/{EVENT_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == str(EVENT_ID)


async def test_get_event_not_found(client: AsyncClient):
    with patch(
        "app.routers.events.get_event",
        new=AsyncMock(side_effect=HTTPException(404, detail="event_not_found")),
    ):
        response = await client.get(f"/events/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "event_not_found"


# ---------------------------------------------------------------------------
# PATCH /events/{id}
# ---------------------------------------------------------------------------

async def test_update_event_happy_path(client: AsyncClient):
    updated = _fake_event(name="Updated Name")
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: ["organizer"]

    with patch("app.routers.events.update_event", new=AsyncMock(return_value=updated)):
        response = await client.patch(f"/events/{EVENT_ID}", json={"name": "Updated Name"})

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


async def test_update_event_missing_organizer_role(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: []

    response = await client.patch(f"/events/{EVENT_ID}", json={"name": "x"})

    assert response.status_code == 403


async def test_update_event_not_found(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: ["organizer"]

    with patch(
        "app.routers.events.update_event",
        new=AsyncMock(side_effect=HTTPException(404, detail="event_not_found")),
    ):
        response = await client.patch(f"/events/{uuid.uuid4()}", json={"name": "x"})

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /events/{id}
# ---------------------------------------------------------------------------

async def test_delete_event_happy_path(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: ["organizer"]

    with patch("app.routers.events.cancel_event", new=AsyncMock(return_value=None)):
        response = await client.delete(f"/events/{EVENT_ID}")

    assert response.status_code == 204


async def test_delete_event_missing_organizer_role(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: []

    response = await client.delete(f"/events/{EVENT_ID}")

    assert response.status_code == 403


async def test_delete_event_not_found(client: AsyncClient):
    app.dependency_overrides[get_current_user_id] = lambda: USER_ID
    app.dependency_overrides[get_current_groups] = lambda: ["organizer"]

    with patch(
        "app.routers.events.cancel_event",
        new=AsyncMock(side_effect=HTTPException(404, detail="event_not_found")),
    ):
        response = await client.delete(f"/events/{uuid.uuid4()}")

    assert response.status_code == 404
