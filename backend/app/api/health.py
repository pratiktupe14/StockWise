from datetime import datetime, timezone
import json
from fastapi import APIRouter, status, Response
from app.core.config import settings
from app.core.database import check_database_connection
from app.schemas.health import (
    HealthResponse,
    DatabaseHealth,
    SystemValidationReport,
)
from app.services.system_validation_service import (
    get_latest_system_validation_report,
    execute_full_system_validation,
)

router = APIRouter(tags=["Health & Validation"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System and Database Health Check",
    description="Returns live API status, database connectivity, and algorithm validation summary.",
)
def get_system_health() -> HealthResponse:
    """
    Evaluates backend and database health in real time.
    Distinguishes API availability from database connectivity,
    and includes latest system validation metrics.
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

    val_report = None
    try:
        val_report = get_latest_system_validation_report()
    except Exception:
        pass

    return HealthResponse(
        status=overall_status,
        app_name=settings.APP_NAME,
        tagline=settings.TAGLINE,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        api="online",
        database=database_health,
        validation_summary=val_report,
    )


@router.get(
    "/system-validation",
    response_model=SystemValidationReport,
    status_code=status.HTTP_200_OK,
    summary="Get Latest System Validation & Test Pass Rate Report",
    description="Returns verifiable test results across all 16 core distribution intelligence modules.",
)
def get_system_validation() -> SystemValidationReport:
    """Returns the latest persisted system validation report."""
    return get_latest_system_validation_report()


@router.post(
    "/system-validation/run",
    response_model=SystemValidationReport,
    status_code=status.HTTP_200_OK,
    summary="Run Full System Check & Algorithm Validation",
    description="Executes all positive, negative, boundary, and failure-case tests live and recalculates scores.",
)
def run_system_validation() -> SystemValidationReport:
    """Executes live verification tests and updates stored report."""
    return execute_full_system_validation()


@router.get(
    "/system-validation/export",
    summary="Export System Validation Report",
    description="Downloads the complete validation evidence and test audit trail as a formatted JSON document.",
)
def export_system_validation():
    """Generates an exportable JSON test report attachment."""
    report = get_latest_system_validation_report()
    report_json = report.model_dump_json(indent=2)
    filename = f"stockwise_validation_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=report_json,
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/ready",
    summary="Kubernetes & Container Readiness Probe",
    description="Returns 200 OK only when the service and database pool are operational and ready for traffic.",
)
def get_readiness():
    db_check = check_database_connection()
    if not db_check["connected"]:
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
