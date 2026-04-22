from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://eventbooking:eventbooking@localhost:5432/eventbooking"
    redis_url: str = "redis://localhost:6379"
    cognito_region: str = "us-east-1"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    seat_hold_ttl_seconds: int = 600
    qr_secret: str = "dev-secret"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
