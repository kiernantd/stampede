from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.redis_client import close_redis
from app.routers import health, seats


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(title="Event Booking API", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(seats.router)
