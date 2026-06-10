from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.redis_client import close_redis
from app.routers import health, seats
from app.routers.events import router as events_router
from app.routers.tickets import router as tickets_router
from app.routers.venues import router as venues_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(title="Event Booking API", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(seats.router)
app.include_router(events_router)
app.include_router(venues_router)
app.include_router(tickets_router)
