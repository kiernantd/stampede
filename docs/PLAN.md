# Event Booking API — Architecture Plan

## Overview

REST backend for a scalable event ticketing platform. Core design focus: correctness under concurrent load for seat holds and bookings. This document is the source of truth; update it when any architectural decision changes.

## Database Schema

### users
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | gen_random_uuid() |
| cognito_sub | VARCHAR(128) UNIQUE NOT NULL | Cognito user pool subject |
| email | VARCHAR(255) NOT NULL | |
| created_at | TIMESTAMPTZ NOT NULL | default now() |

### events
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | gen_random_uuid() |
| name | VARCHAR(255) NOT NULL | |
| description | TEXT | |
| venue | VARCHAR(255) NOT NULL | |
| starts_at | TIMESTAMPTZ NOT NULL | |
| ends_at | TIMESTAMPTZ NOT NULL | |
| created_by | UUID FK(users.id) NOT NULL | |
| created_at | TIMESTAMPTZ NOT NULL | default now() |

### seats
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | gen_random_uuid() |
| event_id | UUID FK(events.id) NOT NULL | ON DELETE CASCADE |
| label | VARCHAR(64) NOT NULL | e.g. "A1", "VIP-12" |
| tier | VARCHAR(64) NOT NULL | e.g. "GA", "VIP" |
| price_cents | INTEGER NOT NULL | |
| status | VARCHAR(16) NOT NULL | 'available' / 'held' / 'booked', default 'available' |
| UNIQUE | (event_id, label) | |

### seat_holds
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | gen_random_uuid() |
| seat_id | UUID FK(seats.id) NOT NULL | |
| user_id | UUID FK(users.id) NOT NULL | |
| expires_at | TIMESTAMPTZ NOT NULL | now() + hold_ttl |
| created_at | TIMESTAMPTZ NOT NULL | default now() |

**Critical index:**
```sql
CREATE UNIQUE INDEX uix_seat_holds_active
    ON seat_holds(seat_id)
    WHERE expires_at > now();
```
This prevents two concurrent holds for the same seat at the DB level (correctness backstop).

### bookings
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | gen_random_uuid() |
| seat_id | UUID FK(seats.id) NOT NULL | |
| user_id | UUID FK(users.id) NOT NULL | |
| hold_id | UUID FK(seat_holds.id) NOT NULL | |
| payment_intent_id | VARCHAR(255) | Stripe mock ID |
| created_at | TIMESTAMPTZ NOT NULL | default now() |

### tickets
| Column | Type | Notes |
|--------|------|-------|
| id | UUID (PK) | gen_random_uuid() |
| booking_id | UUID FK(bookings.id) NOT NULL | |
| qr_token | VARCHAR(64) UNIQUE NOT NULL | HMAC-signed opaque token |
| created_at | TIMESTAMPTZ NOT NULL | default now() |

---

## Concurrency Architecture

### Core invariant
A seat can be actively held **or** booked by at most one user at a time.

### Two-layer protection

**Layer 1 — Redis distributed lock (fast path)**
- Key: `lock:seat:{seat_id}`
- Value: `{user_id}` (for owner verification)
- TTL: matches hold duration (`SEAT_HOLD_TTL_SECONDS`, default 600)
- Acquire: `SET lock:seat:{seat_id} {user_id} NX PX {ttl_ms}`
- On fail: immediate HTTP 409 — no DB round-trip
- Purpose: fast rejection under contention; protects the DB from thundering-herd

**Layer 2 — PostgreSQL (correctness backstop)**
- `SELECT seat FOR UPDATE NOWAIT` — raises immediately if row locked
- Partial unique index on `seat_holds(seat_id) WHERE expires_at > now()` — raises `IntegrityError` on duplicate insert
- If either check fails, rollback and return 409
- Purpose: prevents double-booking even if Redis lock expires during a slow transaction

### Seat hold flow
```
1.  SET lock:seat:{seat_id} {user_id} NX PX {ttl_ms}
    └─ fail → 409 Conflict

2.  BEGIN TRANSACTION
3.  SELECT * FROM seats WHERE id = {seat_id} FOR UPDATE NOWAIT
    └─ LockNotAvailable → rollback, release Redis lock, 409

4.  Assert seat.status == 'available'
    └─ fail → rollback, release Redis lock, 409

5.  INSERT INTO seat_holds (seat_id, user_id, expires_at) VALUES (...)
    └─ IntegrityError (partial unique) → rollback, release Redis lock, 409

6.  UPDATE seats SET status = 'held' WHERE id = {seat_id}
7.  COMMIT
8.  Return 201 HoldOut
```

### Booking flow (convert hold → booking)
```
1.  Fetch hold; assert hold.user_id == requesting_user_id
2.  Assert hold.expires_at > now()
3.  BEGIN TRANSACTION
4.  SELECT seat FOR UPDATE
5.  Assert seat.status == 'held'
6.  INSERT INTO bookings (seat_id, user_id, hold_id, payment_intent_id)
7.  INSERT INTO tickets (booking_id, qr_token)
8.  UPDATE seats SET status = 'booked'
9.  DELETE FROM seat_holds WHERE id = {hold_id}
10. COMMIT
11. Release Redis lock: DEL lock:seat:{seat_id}
12. Return 201 BookingOut
```

### Hold expiry cleanup
Background task (APScheduler or asyncio periodic task):
- Runs every 60 seconds
- `SELECT * FROM seat_holds WHERE expires_at < now()`
- For each expired hold: `UPDATE seats SET status = 'available'`, `DEL lock:seat:{seat_id}`, delete hold row

---

## API Endpoints

### Health
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | /health | None | Checks DB + Redis; 503 if degraded |

### Users
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | /users/me | Bearer | Get-or-create user from Cognito JWT |

### Events
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | /events | None | Paginated; ?page=1&size=20 |
| POST | /events | Bearer | Create event |
| GET | /events/{id} | None | Get event detail |
| GET | /events/{id}/seats | None | List seats with status |
| POST | /events/{id}/seats | Bearer | Bulk add seats |

### Seat Holds
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | /seats/{id}/hold | Bearer | Rate-limited (10/min/user) |
| DELETE | /holds/{id} | Bearer | Only own hold |

### Bookings
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| POST | /holds/{id}/book | Bearer | Converts hold to booking |
| GET | /bookings/{id} | Bearer | Own booking only |

### Tickets
| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET | /tickets/{id} | Bearer | Own ticket only; includes QR token |

---

## Auth (Phase 2)

Cognito JWT verification via JWKS. No session state — stateless bearer token auth.

- JWKS URL: `https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/jwks.json`
- JWKS cached in-process with 1-hour TTL
- Claims used: `sub` (stable user identifier), `email`
- `GET /users/me` upserts a `users` row on first login

## QR Token (Phase 5)

HMAC-SHA256 over `ticket_id:booking_id:user_id` with `QR_SECRET` env var. Token stored as hex. Verification: recompute and compare in constant time.

## Rate Limiting (Phase 6)

Sliding-window counter in Redis:
- Key: `ratelimit:{user_id}:{epoch_minute}`
- Increment with INCR + EXPIRE
- Window: 60s, limit: 10 requests to POST /seats/*/hold or POST /holds/*/book
- HTTP 429 + `Retry-After` header on exceed

---

## Error Response Shape

All errors: `{"detail": "human-readable message"}`

| Status | Meaning |
|--------|---------|
| 400 | Validation / bad input |
| 401 | Missing or invalid token |
| 403 | Token valid, not authorized for resource |
| 404 | Resource not found |
| 409 | Seat already held or booked |
| 422 | FastAPI request validation |
| 429 | Rate limit exceeded |
| 503 | Health check degraded |

---

## Phase Checklist

- [ ] Phase 1: Foundation (Docker, Postgres, Redis, /health)
- [ ] Phase 2: Cognito auth (JWT verification, /users/me)
- [ ] Phase 3: Events & seats CRUD
- [ ] Phase 4: Seat holds (the hard one)
- [ ] Phase 5: Bookings & tickets
- [ ] Phase 6: Rate limiting
- [ ] Phase 7: Polish (README, architecture diagram, load-test numbers)
