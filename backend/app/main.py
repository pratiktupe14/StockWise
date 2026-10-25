import time
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("stockwise.app")
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.entities import router as entities_router
from app.api.network import router as network_router
from app.api.shipments import router as shipments_router
from app.api.planning import router as planning_router
from app.api.utsav import router as utsav_router
from app.api.redistribution import router as redistribution_router
from app.api.distributor import router as distributor_router
from app.api.retailer import router as retailer_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Attempt table creation on startup if database is accessible."""
    try:
        init_db()
    except Exception:
        # If DB is offline during startup, do not crash; health endpoint reports degraded state
        pass
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="StockWise Distribution Intelligence & Inventory Optimization API",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
)


@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    """Correlation ID and latency tracking middleware."""
    request_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:12]}"
    request.state.request_id = request_id
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            f"method={request.method} path={request.url.path} status=500 "
            f"duration_ms={duration_ms} request_id={request_id} error={exc}"
        )
        raise exc

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time"] = f"{duration_ms}ms"

    if not (request.url.path.endswith("/health") and response.status_code == 200):
        logger.info(
            f"method={request.method} path={request.url.path} status={response.status_code} "
            f"duration_ms={duration_ms} request_id={request_id}"
        )

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Standardized error responses avoiding information disclosure in production."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(f"Unhandled exception on {request.method} {request.url.path} (request_id={request_id}): {exc}")

    is_debug = settings.DEBUG and settings.ENVIRONMENT != "production"
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if is_debug else "An unexpected error occurred. Please contact system support.",
            "request_id": request_id,
            "path": request.url.path,
        },
    )


# Health routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(health_router)

# Phase 2 & Phase 3 Import, Entity, Network, Shipment, and Planning routers
app.include_router(imports_router, prefix=settings.API_V1_PREFIX)
app.include_router(entities_router, prefix=settings.API_V1_PREFIX)
app.include_router(network_router, prefix=settings.API_V1_PREFIX)
app.include_router(shipments_router, prefix=settings.API_V1_PREFIX)
app.include_router(planning_router, prefix=settings.API_V1_PREFIX)
app.include_router(utsav_router, prefix=settings.API_V1_PREFIX)
app.include_router(redistribution_router, prefix=settings.API_V1_PREFIX)
app.include_router(distributor_router, prefix=settings.API_V1_PREFIX)
app.include_router(retailer_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
def root_info() -> dict:
    """Service information and metadata."""
    return {
        "service": settings.APP_NAME,
        "tagline": settings.TAGLINE,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "docs": "/docs",
        "health": f"{settings.API_V1_PREFIX}/health",
        "imports": f"{settings.API_V1_PREFIX}/imports",
        "inventory": f"{settings.API_V1_PREFIX}/inventory",
        "products": f"{settings.API_V1_PREFIX}/products",
        "locations": f"{settings.API_V1_PREFIX}/locations",
        "routes": f"{settings.API_V1_PREFIX}/routes",
        "sales": f"{settings.API_V1_PREFIX}/sales",
        "organizations": f"{settings.API_V1_PREFIX}/organizations",
        "network_eligibility": f"{settings.API_V1_PREFIX}/network/eligibility",
        "shipments": f"{settings.API_V1_PREFIX}/shipments",
        "forecast": f"{settings.API_V1_PREFIX}/forecast",
        "risk_analysis": f"{settings.API_V1_PREFIX}/risk/analysis",
        "optimization": f"{settings.API_V1_PREFIX}/optimization/run",
        "planning_runs": f"{settings.API_V1_PREFIX}/optimization/runs",
        "redistribution": f"{settings.API_V1_PREFIX}/redistribution/recommendations",
        "distributor": f"{settings.API_V1_PREFIX}/distributor/dashboard",
        "retailer": f"{settings.API_V1_PREFIX}/retailer/dashboard",
    }
