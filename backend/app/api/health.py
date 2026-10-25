from datetime import datetime, timezone
from fastapi import APIRouter, status
from app.core.config import settings
from app.core.database import check_database_connection
from app.schemas.health import HealthResponse, DatabaseHealth

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System and Database Health Check",
    description="Returns live API status and runs an actual database query to verify connectivity.",
)
def get_system_health() -> HealthResponse:
    """
    Evaluates backend and database health in real time.
    Distinguishes API availability from database connectivity.
    """
    db_check = check_database_connection()
    is_db_connected = db_check["connected"]

    database_health = DatabaseHealth(
        connected=is_db_connected,
        status="connected" if is_db_connected else "disconnected",
        message=db_check["message"],
        dialect=db_check["dialect"],
        latency_ms=db_check["latency_ms"],
    )

    overall_status = "healthy" if is_db_connected else "degraded"

    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        tagline=settings.TAGLINE,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        api="online",
        database=database_health,
    )


@router.get(
    "/ready",
    summary="Kubernetes & Container Readiness Probe",
    description="Returns 200 OK only when the service and database pool are operational and ready for traffic.",
)
def get_readiness():
    db_check = check_database_connection()
    if not db_check["connected"]:
        from fastapi import Response
        return Response(
            content='{"status": "not_ready", "error": "Database unavailable"}',
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )
    return {
        "status": "ready",
        "service": settings.APP_NAME,
        "database": "connected",
        "dialect": db_check["dialect"],
        "latency_ms": db_check["latency_ms"],
        "version": settings.VERSION,
    }
