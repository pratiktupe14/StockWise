"""
StockWise UtsavSense: Festival-Aware Inventory Planning Service (Phase 4.5 Feature 13).

Provides cultural and regional festival calendar modeling, demand uplift scenario simulation,
and festival-specific distribution planning for Indian FMCG supply chains.
"""

from datetime import datetime, date, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.entities import FestivalEvent, Product, Location, InventorySnapshot, Route
from app.schemas.planning import (
    FestivalEventCreate,
    FestivalEventResponse,
    UtsavUpliftResponse,
    UtsavUpliftItem,
    OptimizationRequest,
    PlanningRunResponse,
)
from app.services.forecast_service import compute_demand_forecast
from app.services.inventory_service import (
    compute_dispatchable_stock,
    compute_projected_available_stock,
    compute_target_stock,
    compute_replenishment_gap,
)
from app.services.optimizer_service import run_distribution_optimization


DEFAULT_FESTIVALS = [
    {
        "event_id": "FEST-DIWALI-2026",
        "name": "Diwali Festival of Lights 2026",
        "description": "Peak national FMCG consumption surge across Confectionery, Beverages, Gifting, and Personal Care.",
        "start_date": date(2026, 10, 28),
        "end_date": date(2026, 11, 4),
        "regions": ["National", "North", "West", "South", "East"],
        "applicable_categories": ["Staples", "Edible Oils", "Snacks", "Beverages", "Personal Care", "Fabric Care"],
        "default_uplift_percent": 45.0,
        "is_active": True,
    },
    {
        "event_id": "FEST-GANESH-2026",
        "name": "Ganesh Chaturthi Utsav 2026",
        "description": "High seasonal demand surge concentrated across Maharashtra and West regional retail hubs.",
        "start_date": date(2026, 9, 14),
        "end_date": date(2026, 9, 24),
        "regions": ["West", "Maharashtra"],
        "applicable_categories": ["Snacks", "Beverages", "Personal Care"],
        "default_uplift_percent": 35.0,
        "is_active": True,
    },
    {
        "event_id": "FEST-DURGA-2026",
        "name": "Durga Puja & Navratri 2026",
        "description": "Major festival surge in East and North regions driving high impulse FMCG purchases.",
        "start_date": date(2026, 10, 10),
        "end_date": date(2026, 10, 19),
        "regions": ["East", "North", "West"],
        "applicable_categories": ["Snacks", "Beverages", "Personal Care"],
        "default_uplift_percent": 40.0,
        "is_active": True,
    },
]


def ensure_default_festivals(db: Session) -> None:
    """Pre-seeds default major FMCG festivals if table is empty."""
    count = db.query(FestivalEvent).count()
    if count == 0:
        for fest in DEFAULT_FESTIVALS:
            db.add(FestivalEvent(**fest))
        db.commit()


def list_festival_events(db: Session) -> List[FestivalEventResponse]:
    """Retrieves all active festival planning events."""
    festivals = db.query(FestivalEvent).order_by(FestivalEvent.start_date.asc()).all()
    return [
        FestivalEventResponse(
            id=f.id,
            event_id=f.event_id,
            name=f.name,
            description=f.description,
            start_date=f.start_date.strftime("%Y-%m-%d"),
            end_date=f.end_date.strftime("%Y-%m-%d"),
            regions=f.regions if isinstance(f.regions, list) else [],
            applicable_categories=f.applicable_categories if isinstance(f.applicable_categories, list) else [],
            default_uplift_percent=float(f.default_uplift_percent),
            is_active=f.is_active,
            created_at=f.created_at,
        )
        for f in festivals
    ]


def create_festival_event(db: Session, payload: FestivalEventCreate) -> FestivalEventResponse:
    """Registers a new regional or cultural festival event."""
    existing = db.query(FestivalEvent).filter(FestivalEvent.event_id == payload.event_id.strip()).first()
    if existing:
        raise ValueError(f"Festival event '{payload.event_id}' already exists.")

    start_d = datetime.strptime(payload.start_date, "%Y-%m-%d").date()
    end_d = datetime.strptime(payload.end_date, "%Y-%m-%d").date()

    event = FestivalEvent(
        event_id=payload.event_id.strip(),
        name=payload.name.strip(),
        description=payload.description,
        start_date=start_d,
        end_date=end_d,
        regions=payload.regions,
        applicable_categories=payload.applicable_categories,
        default_uplift_percent=payload.default_uplift_percent,
        is_active=payload.is_active,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return FestivalEventResponse(
        id=event.id,
        event_id=event.event_id,
        name=event.name,
        description=event.description,
        start_date=event.start_date.strftime("%Y-%m-%d"),
        end_date=event.end_date.strftime("%Y-%m-%d"),
        regions=event.regions,
        applicable_categories=event.applicable_categories,
        default_uplift_percent=float(event.default_uplift_percent),
        is_active=event.is_active,
        created_at=event.created_at,
    )


def estimate_festival_demand_uplift(
    db: Session,
    event_id: str,
    scenario: str = "expected",
    custom_uplift_percent: Optional[float] = None,
    horizon_days: int = 7,
) -> UtsavUpliftResponse:
    """
    Computes baseline vs festival-adjusted demand by SKU and destination corridor.
    Scenarios:
    - conservative: 0.5x default uplift
    - expected: 1.0x default uplift
    - high: 1.5x default uplift
    - custom: uses custom_uplift_percent
    """
    event = db.query(FestivalEvent).filter(FestivalEvent.event_id == event_id.strip()).first()
    if not event:
        raise ValueError(f"Festival event '{event_id}' not found.")

    # Determine uplift factor
    default_pct = float(event.default_uplift_percent)
    if scenario == "conservative":
        applied_pct = round(default_pct * 0.5, 1)
    elif scenario == "high":
        applied_pct = round(default_pct * 1.5, 1)
    elif scenario == "custom" and custom_uplift_percent is not None:
        applied_pct = max(0.0, float(custom_uplift_percent))
    else:
        applied_pct = default_pct

    # Baseline forecasts across target nodes
    forecast_resp = compute_demand_forecast(db, horizon_days=horizon_days)

    products = {p.sku_id: p for p in db.query(Product).all()}
    locations = {l.location_id: l for l in db.query(Location).all()}

    # Inventory snapshots
    inv_records = db.query(InventorySnapshot).all()
    inv_by_node: Dict[tuple, InventorySnapshot] = {
        (rec.sku_id, rec.location_id): rec for rec in inv_records
    }

    event_regions = set(event.regions) if isinstance(event.regions, list) else set()
    event_categories = set(event.applicable_categories) if isinstance(event.applicable_categories, list) else set()

    is_national = "National" in event_regions
    is_all_cats = "All" in event_categories

    items: List[UtsavUpliftItem] = []
    total_base = 0.0
    total_fest = 0.0
    total_inc = 0.0
    total_needed = 0.0

    for fc in forecast_resp.forecasts:
        s_id = fc.sku_id
        d_id = fc.destination_id
        prod = products.get(s_id)
        loc = locations.get(d_id)

        prod_name = prod.name if prod else fc.product_name
        cat = prod.category if prod else "General"
        dest_name = loc.name if loc else fc.destination_name
        region = loc.region if loc else "National"

        # Check applicability
        region_matches = is_national or (region in event_regions)
        category_matches = is_all_cats or (cat in event_categories)

        if region_matches and category_matches:
            uplift_rate = applied_pct / 100.0
            uplift_label = f"+{applied_pct:.1f}% ({scenario.capitalize()} Scenario)"
            assumptions = f"{event.name} uplift assumption for {cat} in {region} corridor."
        else:
            uplift_rate = 0.0
            uplift_label = "0.0% (Outside Target Scope)"
            assumptions = f"Corridor {region}/{cat} not configured for {event.name} surge."

        base_rate = fc.daily_forecast_rate
        base_demand = fc.total_forecast_demand
        fest_demand = round(base_demand * (1.0 + uplift_rate), 1)
        inc_units = round(fest_demand - base_demand, 1)

        # Inventory balance at destination
        inv = inv_by_node.get((s_id, d_id))
        on_hand = float(inv.on_hand) if inv else 0.0
        reserved = float(inv.reserved) if inv else 0.0
        blocked = float(inv.blocked) if inv else 0.0
        confirmed_inc = float(inv.confirmed_incoming) if inv else 0.0

        disp = compute_dispatchable_stock(on_hand, reserved, blocked)
        eligible_stock, _ = compute_projected_available_stock(on_hand, reserved, blocked, confirmed_inc)

        # Target stock under festival demand (including 3-day safety buffer)
        fest_daily_rate = round(fest_demand / max(1, horizon_days), 2)
        fest_target = compute_target_stock(fest_daily_rate, horizon_days=horizon_days, buffer_days=3.0)
        needed = compute_replenishment_gap(fest_target, eligible_stock)

        total_base += base_demand
        total_fest += fest_demand
        total_inc += inc_units
        total_needed += needed

        items.append(
            UtsavUpliftItem(
                sku_id=s_id,
                product_name=prod_name or s_id,
                category=cat,
                destination_id=d_id,
                destination_name=dest_name or d_id,
                region=region,
                baseline_daily_rate=base_rate,
                baseline_demand=base_demand,
                uplift_scenario=scenario,
                uplift_percent=applied_pct if (region_matches and category_matches) else 0.0,
                festival_demand=fest_demand,
                incremental_units=inc_units,
                current_eligible_stock=eligible_stock,
                additional_stock_needed=needed,
                assumptions=assumptions,
            )
        )

    return UtsavUpliftResponse(
        event_id=event.event_id,
        event_name=event.name,
        uplift_scenario=scenario,
        uplift_percent=applied_pct,
        horizon_days=horizon_days,
        total_baseline_demand=round(total_base, 1),
        total_festival_demand=round(total_fest, 1),
        total_incremental_demand=round(total_inc, 1),
        total_additional_stock_needed=round(total_needed, 1),
        items=items,
    )


def run_festival_optimization_plan(
    db: Session,
    event_id: str,
    scenario: str = "expected",
    custom_uplift_percent: Optional[float] = None,
    horizon_days: int = 7,
    authorized_user_id: str = "UTSAV-PLANNER-01",
    org_id: Optional[str] = None,
    created_by_user_id: Optional[str] = None,
) -> PlanningRunResponse:
    """
    Feeds festival-adjusted demand into the 2-stage optimization solver.
    Retains explicit planning_mode='utsav_sense' and festival_event_id linkage.
    """
    # 1. Compute festival uplift
    uplift_res = estimate_festival_demand_uplift(
        db,
        event_id=event_id,
        scenario=scenario,
        custom_uplift_percent=custom_uplift_percent,
        horizon_days=horizon_days,
    )

    # 2. Build demand gap overrides based on additional stock needed
    overrides: Dict[str, float] = {}
    for item in uplift_res.items:
        if item.additional_stock_needed > 0:
            key = f"{item.sku_id}:{item.destination_id}"
            overrides[key] = item.additional_stock_needed

    # 3. Formulate optimization request with UtsavSense metadata
    opt_req = OptimizationRequest(
        snapshot_id=None,
        horizon_days=horizon_days,
        objective_strategy="service-first",
        solver_type="ortools",
        allow_cross_region_routes=True,
        authorized_user_id=authorized_user_id,
        planning_mode="utsav_sense",
        festival_event_id=event_id,
        demand_overrides=overrides,
    )

    return run_distribution_optimization(
        db,
        opt_req,
        org_id=org_id,
        created_by_user_id=created_by_user_id,
    )
