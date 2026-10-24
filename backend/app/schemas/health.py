from typing import Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    connected: bool = Field(..., description="Whether database query succeeded")
    status: str = Field(..., description="'connected' or 'disconnected'")
    message: str = Field(..., description="Detailed status message or error summary")
    dialect: str = Field(..., description="Database dialect, e.g. postgresql")
    latency_ms: Optional[float] = Field(None, description="Round-trip check duration in milliseconds")


class HealthResponse(BaseModel):
    status: str = Field(..., description="'healthy' when all systems operational, 'degraded' when DB offline")
    app_name: str = Field("StockWise", description="Application name")
    tagline: str = Field("The right stock. At the right place. Before it is too late.", description="Application tagline")
    version: str = Field("0.1.0", description="Backend service version")
    environment: str = Field(..., description="Runtime environment: development, staging, production")
    timestamp: str = Field(..., description="UTC ISO-8601 timestamp of health evaluation")
    api: str = Field("online", description="API server availability state")
    database: DatabaseHealth = Field(..., description="Live database connectivity assessment")
