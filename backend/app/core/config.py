import os
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "StockWise"
    TAGLINE: str = "The right stock. At the right place. Before it is too late."
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    ALLOWED_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    DATABASE_URL: str = "postgresql+psycopg2://stockwise_user:stockwise_password@localhost:5432/stockwise"
    DB_CONNECT_TIMEOUT_SECONDS: int = 10

    # Supabase & Auth Configuration
    SUPABASE_URL: str = "https://irhunosgwyvgdhcnzbki.supabase.co"
    SUPABASE_PUBLISHABLE_KEY: Union[str, None] = None
    SUPABASE_JWT_SECRET: Union[str, None] = None
    SUPABASE_JWT_ALGORITHM: str = "HS256"
    SUPABASE_JWT_AUDIENCE: Union[str, None] = None
    REQUIRE_AUTH: bool = False
    ALLOW_DEMO_AUTH: bool = True

    # Security & Logging
    LOG_LEVEL: str = "INFO"
    ENABLE_IDEMPOTENCY: bool = True
    MAX_FILE_UPLOAD_SIZE_MB: int = 10

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def is_demo_allowed(self) -> bool:
        return self.ALLOW_DEMO_AUTH and not self.is_production()


settings = Settings()
