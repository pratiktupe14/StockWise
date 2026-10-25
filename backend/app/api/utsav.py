"""
StockWise UtsavSense API: Festival-Aware Inventory Planning (Phase 4.5 Feature 13).

Endpoints for managing cultural festival calendars, computing multi-scenario demand uplifts,
and executing festival-constrained distribution optimization.
"""

import io
import csv
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.planning import (
    FestivalEventCreate,
    FestivalEventResponse,
    UtsavUpliftResponse,
    PlanningRunResponse,
)
from app.services.utsav_service import (
    list_festival_events,
    create_festival_event,
    estimate_festival_demand_uplift,
    run_festival_optimization_plan,
)
from app.core.security import AuthenticatedUser, require_roles


router = APIRouter(prefix="/utsav", tags=["UtsavSense: Festival-Aware Planning"])


class UtsavUpliftPayload(BaseModel):
    event_id: str
    scenario: str = Field("expected", description="conservative, expected, high, custom")
    custom_uplift_percent: Optional[float] = None
    horizon_days: int = Field(7, ge=1, le=30)


class UtsavPlanPayload(BaseModel):
    event_id: str
    scenario: str = Field("expected", description="conservative, expected, high, custom")
    custom_uplift_percent: Optional[float] = None
    horizon_days: int = Field(7, ge=1, le=30)
    authorized_user_id: str = "UTSAV-PLANNER-01"


@router.get("/events", response_model=List[FestivalEventResponse], summary="List festival calendar events")
def get_festival_events(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves all registered cultural and regional festival events."""
    return list_festival_events(db)


@router.post("/events", response_model=FestivalEventResponse, status_code=status.HTTP_201_CREATED, summary="Create a new festival event")
def add_festival_event(
    payload: FestivalEventCreate,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """Registers a new regional or cultural festival event in the planning calendar."""
    try:
        return create_festival_event(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/forecast-uplift", response_model=UtsavUpliftResponse, summary="Compute festival demand uplift scenarios")
def get_festival_uplift_post(
    payload: UtsavUpliftPayload,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Simulates demand uplift scenarios (Conservative, Expected, High, Custom) across
    matching regional destinations and SKU categories without double-counting baseline forecasts.
    """
    try:
        return estimate_festival_demand_uplift(
            db,
            event_id=payload.event_id,
            scenario=payload.scenario,
            custom_uplift_percent=payload.custom_uplift_percent,
            horizon_days=payload.horizon_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/forecast-uplift", response_model=UtsavUpliftResponse, summary="Compute festival demand uplift scenarios via query params")
def get_festival_uplift_get(
    event_id: str = Query(..., description="Festival Event ID"),
    scenario: str = Query("expected", description="conservative, expected, high, custom"),
    custom_uplift_percent: Optional[float] = Query(None),
    horizon_days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """GET query-params endpoint for festival demand uplift scenarios."""
    try:
        return estimate_festival_demand_uplift(
            db,
            event_id=event_id,
            scenario=scenario,
            custom_uplift_percent=custom_uplift_percent,
            horizon_days=horizon_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))



@router.post("/optimize", response_model=PlanningRunResponse, status_code=status.HTTP_201_CREATED, summary="Run festival-aware distribution optimization")
def execute_festival_optimization(
    payload: UtsavPlanPayload,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Feeds festival-adjusted demand into the 2-stage optimization solver,
    generating recommended transfers and Decision Receipts linked to the festival.
    """
    try:
        # Use verified server-side authenticated user identity and tenant context
        actor_id = current_user.user_id if current_user else payload.authorized_user_id
        org_id = current_user.org_id if current_user else None
        return run_festival_optimization_plan(
            db,
            event_id=payload.event_id,
            scenario=payload.scenario,
            custom_uplift_percent=payload.custom_uplift_percent,
            horizon_days=payload.horizon_days,
            authorized_user_id=actor_id,
            org_id=org_id,
            created_by_user_id=current_user.user_id if current_user else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/events/{event_id}/export.csv", summary="Export festival demand and stock analysis as CSV")
def export_festival_uplift_csv(
    event_id: str,
    scenario: str = Query("expected"),
    custom_uplift_percent: Optional[float] = Query(None),
    horizon_days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Downloads festival uplift breakdown, incremental units, and additional stock requirements as CSV."""
    try:
        uplift_res = estimate_festival_demand_uplift(
            db,
            event_id=event_id,
            scenario=scenario,
            custom_uplift_percent=custom_uplift_percent,
            horizon_days=horizon_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "event_id", "event_name", "scenario", "sku_id", "product_name", "category",
        "destination_id", "destination_name", "region", "baseline_daily_rate",
        "baseline_demand", "uplift_percent", "festival_demand", "incremental_units",
        "current_eligible_stock", "additional_stock_needed", "assumptions"
    ])

    for itm in uplift_res.items:
        writer.writerow([
            uplift_res.event_id, uplift_res.event_name, uplift_res.uplift_scenario,
            itm.sku_id, itm.product_name, itm.category, itm.destination_id,
            itm.destination_name, itm.region, itm.baseline_daily_rate,
            itm.baseline_demand, itm.uplift_percent, itm.festival_demand,
            itm.incremental_units, itm.current_eligible_stock,
            itm.additional_stock_needed, itm.assumptions
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=StockWise_{event_id}_{scenario}_uplift.csv"}
    )
