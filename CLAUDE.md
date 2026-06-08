c# Scalable Event Booking Backend

REST API for a Ticketmaster alternative. Backend-only resume project emphasizing concurrency correctness.

## Source of truth

All architecture and implementation details live in [`docs/PLAN.md`](docs/PLAN.md). Read that file before starting any non-trivial work. If this file and the plan disagree, the plan wins — update this file to match.

## Tech stack

- Python 3.11+, FastAPI, SQLAlchemy 2.0, Alembic
- PostgreSQL 15+, Redis 7+
- AWS Cognito (JWT auth), Docker + docker-compose
- pytest + pytest-asyncio

## Running locally

```bash
docker compose up -d postgres redis
alembic upgrade head
uvicorn app.main:app --reload
```

Tests:

```bash
pytest                                    # full suite
pytest tests/test_seat_hold_concurrent.py # the critical one
```

## Core invariant

**A seat can be actively held or booked by at most one user at a time.**

This invariant is protected by two layers:

1. Redis distributed lock (fast rejection under contention)
2. Postgres partial unique index + transactional row locks (correctness backstop)

If you find yourself weakening a test to make this invariant "work," stop — the implementation is almost certainly wrong. Never relax the assertion. Fix the implementation instead.

## Directory conventions

- `app/models/` — SQLAlchemy ORM models, one file per aggregate
- `app/schemas/` — Pydantic request/response models
- `app/routers/` — FastAPI routers, kept thin; business logic lives in services
- `app/services/` — business logic, transaction boundaries, the hard stuff
- `app/auth/` — Cognito JWT verification only, no other concerns
- `alembic/versions/` — migrations, never edit once merged
- `tests/` — pytest, asyncio-first

## When to delegate to subagents

- **Seat-hold or booking logic changed** → `concurrency-tester` (runs race-condition tests)
- **Auth, QR tokens, or rate limiting changed** → `security-reviewer` (read-only audit)
- **Schema change needed** → `migration-writer` (writes safe Alembic migrations)

For unrelated tasks, work in the main session.

## Non-goals (do not build these)

- Real payments (Stripe stays mocked)
- Email delivery
- Frontend / UI
- Social auth providers
- Multi-region infra

Scope is intentionally tight. Adding features outside this list is a red flag, not a feature request.

## Current status

Update as you progress:

- [x] Phase 1: Foundation (Docker, Postgres, Redis, /health)
- [ ] Phase 2: Cognito auth (JWT verification, /users/me)
- [ ] Phase 3: Events & seats CRUD
- [ ] Phase 4: Seat holds (the hard one)
- [ ] Phase 5: Bookings & tickets
- [ ] Phase 6: Rate limiting
- [ ] Phase 7: Polish (README, architecture diagram, load-test numbers)
