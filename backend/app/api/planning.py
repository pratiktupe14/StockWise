import json
import io
import csv
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models.entities import PlanningRun, Shipment, Product, Location
from app.schemas.planning import (
    ForecastResponse,
    RiskAnalysisResponse,
    OptimizationRequest,
    PlanningRunResponse,
    DecisionReceiptSchema,
    SolverBenchmarkComparisonResponse,
    CorridorComparisonResponse,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
    OperationalPerformanceResponse,
    ForecastEvaluationResponse,
    DistributionPerformanceResponse,
)
from app.schemas.network import ShipmentResponse
from app.services.forecast_service import (
    compute_demand_forecast,
    compute_forecast_evaluation,
)
from app.services.risk_service import analyze_inventory_risks
from app.services.optimizer_service import (
    run_distribution_optimization,
    benchmark_solvers,
    compare_corridors_for_destination_sku,
    simulate_what_if_scenario,
    compute_operational_performance_metrics,
    compute_distribution_performance_kpis,
)
from app.core.security import AuthenticatedUser, require_roles

router = APIRouter(prefix="", tags=["Distribution Intelligence & Planning"])


@router.get("/forecast", response_model=ForecastResponse, summary="Compute or retrieve demand forecasts")
def get_demand_forecast(
    horizon_days: int = Query(7, ge=1, le=30, description="Planning horizon in days"),
    sku_id: Optional[str] = Query(None, description="Optional SKU ID filter"),
    destination_id: Optional[str] = Query(None, description="Optional destination location ID filter"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Computes demand forecasts across target distribution nodes using historical sales.
    - Uses 7-day rolling moving average and seasonal-naive approaches.
    - Evaluates chronological out-of-sample holdout accuracy (MAE & WAPE).
    - Classifies data sufficiency (sufficient, insufficient_history, zero_demand).
    - Strictly avoids future data leakage.
    """
    return compute_demand_forecast(
        db,
        horizon_days=horizon_days,
        sku_id=sku_id,
        destination_id=destination_id,
    )


@router.get(
    "/forecast/evaluation",
    response_model=ForecastEvaluationResponse,
    summary="Evaluate ML forecast model against historical holdout data",
)
def get_forecast_evaluation(
    horizon_days: int = Query(7, ge=1, le=30, description="Planning horizon in days"),
    sku_id: Optional[str] = Query(None, description="Optional SKU ID filter"),
    destination_id: Optional[str] = Query(None, description="Optional destination location ID filter"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """
    ML Model Evaluation and Actual vs Predicted Demand Comparison:
    - Compares actual demand and predicted demand using matched SKU, location, and date records.
    - Evaluates chronological holdout split preventing data leakage.
    - Computes MAE (mean absolute error), WAPE (weighted absolute percentage error), and forecast accuracy (100 - WAPE).
    - Future dates strictly contain predicted demand with actual demand marked pending (no invented observations).
    - Returns data sufficiency classification (sufficient, insufficient_history, zero_demand).
    """
    return compute_forecast_evaluation(
        db,
        horizon_days=horizon_days,
        sku_id=sku_id,
        destination_id=destination_id,
    )



@router.get("/risk/analysis", response_model=RiskAnalysisResponse, summary="Analyze inventory risks and stockout exposure")
@router.get("/inventory-risk", response_model=RiskAnalysisResponse, summary="Analyze inventory risks (alias)")
def get_inventory_risk_analysis(
    horizon_days: int = Query(7, ge=1, le=30, description="Planning horizon in days"),
    snapshot_id: Optional[str] = Query(None, description="Optional inventory snapshot ID filter"),
    destination_id: Optional[str] = Query(None, description="Optional destination location ID filter"),
    sku_id: Optional[str] = Query(None, description="Optional SKU ID filter"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Evaluates destination stock positions, days of cover, demand gaps, and stockout risks.
    - Enforces Phase 2 inventory accounting: Dispatchable = max(0, OH - Res - Blk).
    - Checks earliest replenishment lead times from active permitted inbound routes.
    - Identifies critical stockout exposure where cover days < earliest lead time.
    """
    return analyze_inventory_risks(
        db,
        horizon_days=horizon_days,
        snapshot_id=snapshot_id,
        destination_id=destination_id,
        sku_id=sku_id,
    )


@router.post("/optimization/run", response_model=PlanningRunResponse, status_code=status.HTTP_201_CREATED, summary="Execute service-first distribution optimization")
def execute_distribution_optimization(
    payload: OptimizationRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Executes Phase 3 Distribution Intelligence Engine:
    - 2-Stage Lexicographic Optimization:
        Stage 1: Minimize weighted unmet customer demand.
        Stage 2: Minimize transport cost while strictly preserving optimal service level.
    - Candidate Corridor Filtering:
        - Only active permitted routes.
        - Excludes routes exceeding planning horizon cutoff.
        - Company-owned stock only (independent distributor inventory protected).
    - Deterministic Nearest-Eligible-Source Baseline on identical input snapshots and constraints.
    - Generates evidence-based Decision Receipts for every recommended shipment.
    - Persists PlanningRun and creates proposed Shipment records scoped to tenant organization.
    """
    return run_distribution_optimization(
        db,
        payload,
        org_id=current_user.org_id,
        created_by_user_id=current_user.user_id,
    )


@router.get("/optimization/runs", response_model=List[Dict[str, Any]], summary="List historical planning runs")
def list_planning_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves list of previous planning runs with key summary performance metrics scoped to tenant."""
    query = db.query(PlanningRun).order_by(desc(PlanningRun.created_at))
    if current_user.role != "admin":
        if current_user.org_id:
            query = query.filter(PlanningRun.org_id == current_user.org_id)
        else:
            return []

    runs = query.offset(offset).limit(limit).all()

    return [
        {
            "run_id": r.run_id,
            "snapshot_id": r.snapshot_id,
            "horizon_days": r.horizon_days,
            "objective_strategy": r.objective_strategy,
            "solver_status": r.solver_status,
            "solve_time_ms": r.solve_time_ms,
            "total_demand_units": r.total_demand_units,
            "fulfilled_demand_units": r.fulfilled_demand_units,
            "unmet_demand_units": r.unmet_demand_units,
            "service_level_percent": r.service_level_percent,
            "estimated_transport_cost": r.estimated_transport_cost,
            "stock_utilization_percent": r.stock_utilization_percent,
            "created_at": r.created_at,
        }
        for r in runs
    ]


@router.get("/optimization/runs/{run_id}", response_model=PlanningRunResponse, summary="Retrieve a planning run by ID")
def get_planning_run_details(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves complete details of a planning run including recommended shipments and receipts with tenant isolation."""
    run = db.query(PlanningRun).filter(PlanningRun.run_id == run_id.strip()).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planning run '{run_id}' not found."
        )

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planning run '{run_id}' not found."
        )

    # Fetch associated shipments
    shipments = (
        db.query(Shipment)
        .filter(Shipment.planning_run_id == run_id.strip())
        .all()
    )

    products = {p.sku_id: p.name for p in db.query(Product).all()}
    locations = {l.location_id: l.name for l in db.query(Location).all()}

    shipment_responses = [
        ShipmentResponse(
            shipment_id=s.shipment_id,
            sku_id=s.sku_id,
            product_name=products.get(s.sku_id, s.sku_id),
            source_location_id=s.source_location_id,
            source_location_name=locations.get(s.source_location_id, s.source_location_id),
            destination_location_id=s.destination_location_id,
            destination_location_name=locations.get(s.destination_location_id, s.destination_location_id),
            owner_org_id=s.owner_org_id,
            carrier_agency_id=s.carrier_agency_id,
            route_id=s.route_id,
            quantity=float(s.quantity),
            estimated_dispatch_date=s.estimated_dispatch_date,
            estimated_arrival_date=s.estimated_arrival_date,
            estimated_transport_cost=float(s.estimated_transport_cost),
            status=s.status,
            approval_status=s.approval_status,
            approved_by=s.approved_by,
            approval_notes=s.approval_notes,
            created_at=s.created_at,
            updated_at=s.updated_at,
            movement_count=len(s.movements) if s.movements else 0,
        )
        for s in shipments
    ]

    unmet_breakdown = json.loads(run.unmet_demand_breakdown) if run.unmet_demand_breakdown else []
    baseline_comp = json.loads(run.baseline_comparison) if run.baseline_comparison else None
    receipts_raw = json.loads(run.decision_receipts) if run.decision_receipts else []
    receipts = [DecisionReceiptSchema(**r) for r in receipts_raw]

    return PlanningRunResponse(
        run_id=run.run_id,
        snapshot_id=run.snapshot_id,
        horizon_days=run.horizon_days,
        objective_strategy=run.objective_strategy,
        solver_status=run.solver_status,
        solve_time_ms=run.solve_time_ms,
        total_demand_units=run.total_demand_units,
        fulfilled_demand_units=run.fulfilled_demand_units,
        unmet_demand_units=run.unmet_demand_units,
        service_level_percent=run.service_level_percent,
        estimated_transport_cost=run.estimated_transport_cost,
        stock_utilization_percent=run.stock_utilization_percent,
        recommended_shipments=shipment_responses,
        unmet_demand_breakdown=unmet_breakdown,
        decision_receipts=receipts,
        baseline_comparison=baseline_comp,
        created_at=run.created_at,
    )


@router.get("/optimization/runs/{run_id}/receipts", response_model=List[DecisionReceiptSchema], summary="Retrieve decision receipts for a planning run")
def get_planning_run_receipts(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves evidence-based decision receipts for all proposed movements in the specified plan with tenant isolation."""
    run = db.query(PlanningRun).filter(PlanningRun.run_id == run_id.strip()).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planning run '{run_id}' not found."
        )

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planning run '{run_id}' not found."
        )

    receipts_raw = json.loads(run.decision_receipts) if run.decision_receipts else []
    return [DecisionReceiptSchema(**r) for r in receipts_raw]


@router.get("/optimization/runs/{run_id}/comparison", summary="Retrieve baseline vs optimizer comparison")
def get_planning_run_comparison(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Retrieves 6-dimension benchmark comparison with tenant isolation."""
    run = db.query(PlanningRun).filter(PlanningRun.run_id == run_id.strip()).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planning run '{run_id}' not found."
        )

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planning run '{run_id}' not found."
        )

    if not run.baseline_comparison:
        return {}
    return json.loads(run.baseline_comparison)


@router.post(
    "/optimization/benchmark",
    response_model=SolverBenchmarkComparisonResponse,
    summary="Benchmark OR-Tools GLOP vs SciPy HiGHS on deterministic snapshot",
)
def run_solver_benchmark(
    payload: OptimizationRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """Executes side-by-side solver benchmark on the exact same snapshot and constraints."""
    return benchmark_solvers(db, payload)


@router.get("/optimization/runs/{run_id}/export", summary="Export recommended shipments as CSV (alias)")
@router.get("/optimization/runs/{run_id}/export/shipments.csv", summary="Export recommended shipments as CSV")
def export_plan_shipments_csv(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Downloads recommended shipments for a planning run as formatted CSV with tenant isolation."""
    run = db.query(PlanningRun).filter(PlanningRun.run_id == run_id.strip()).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planning run '{run_id}' not found.")

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planning run '{run_id}' not found.")

    shipments = db.query(Shipment).filter(Shipment.planning_run_id == run_id.strip()).all()
    products = {p.sku_id: p.name for p in db.query(Product).all()}
    locations = {l.location_id: l.name for l in db.query(Location).all()}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "shipment_id", "planning_run_id", "sku_id", "product_name",
        "source_location_id", "source_location_name", "destination_location_id", "destination_location_name",
        "quantity", "unit", "estimated_transport_cost", "currency", "status", "approval_status"
    ])

    for s in shipments:
        writer.writerow([
            s.shipment_id, s.planning_run_id, s.sku_id, products.get(s.sku_id, s.sku_id),
            s.source_location_id, locations.get(s.source_location_id, s.source_location_id),
            s.destination_location_id, locations.get(s.destination_location_id, s.destination_location_id),
            s.quantity, "cases", s.estimated_transport_cost, "INR", s.status, s.approval_status
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=StockWise_plan_shipments_{run_id}.csv"}
    )


@router.get("/optimization/runs/{run_id}/export/receipts.csv", summary="Export decision receipts as CSV")
def export_plan_receipts_csv(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Downloads structured decision receipts with grounded rationale as CSV with tenant isolation."""
    run = db.query(PlanningRun).filter(PlanningRun.run_id == run_id.strip()).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planning run '{run_id}' not found.")

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planning run '{run_id}' not found.")

    receipts_raw = json.loads(run.decision_receipts) if run.decision_receipts else []

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "recommendation_id", "planning_run_id", "sku_id", "product_name",
        "source_location_id", "destination_location_id", "quantity", "lead_time_days",
        "expected_arrival_date", "estimated_cost", "currency", "solver_name", "solver_status", "evidence", "rejected_alternatives"
    ])

    for r in receipts_raw:
        rej_str = " | ".join(r.get("rejected_alternatives", []))
        writer.writerow([
            r.get("recommendation_id"), run_id, r.get("sku_id"), r.get("product_name"),
            r.get("source_location_id"), r.get("destination_location_id"), r.get("quantity"),
            r.get("lead_time_days"), r.get("expected_arrival_date") or r.get("estimated_arrival_date"),
            r.get("estimated_cost"), r.get("currency", "INR"), r.get("solver_name", "ortools_glop"),
            r.get("solver_status", "optimal"), r.get("evidence"), rej_str
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=StockWise_decision_receipts_{run_id}.csv"}
    )


@router.get("/optimization/runs/{run_id}/export/unmet-demand.csv", summary="Export unmet demand breakdown as CSV")
def export_plan_unmet_demand_csv(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Downloads unmet demand breakdown and constraint explanation as CSV with tenant isolation."""
    run = db.query(PlanningRun).filter(PlanningRun.run_id == run_id.strip()).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planning run '{run_id}' not found.")

    if current_user.role != "admin" and run.org_id and run.org_id != current_user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Planning run '{run_id}' not found.")

    unmet_raw = json.loads(run.unmet_demand_breakdown) if run.unmet_demand_breakdown else []

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["planning_run_id", "sku_id", "product_name", "destination_id", "destination_name", "total_demand_gap", "unmet_quantity", "constraint_reasons"])

    for u in unmet_raw:
        reasons_str = " | ".join(u.get("reasons", []))
        writer.writerow([
            run_id, u.get("sku_id"), u.get("product_name"), u.get("destination_id"),
            u.get("destination_name"), u.get("total_demand_gap"), u.get("unmet_quantity"), reasons_str
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=StockWise_unmet_demand_{run_id}.csv"}
    )


@router.get("/risk/export/analysis.csv", summary="Export inventory risk analysis as CSV")
def export_risk_analysis_csv(
    horizon_days: int = Query(7, ge=1, le=30),
    snapshot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """Downloads multi-location inventory risk, cover days, and gap analysis as CSV."""
    risk_resp = analyze_inventory_risks(db, horizon_days=horizon_days, snapshot_id=snapshot_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "sku_id", "product_name", "destination_id", "destination_name", "horizon_days",
        "daily_forecast_rate", "total_forecast_demand", "on_hand", "reserved", "blocked",
        "confirmed_incoming", "dispatchable_stock", "cover_days", "demand_gap",
        "safety_stock_target", "target_stock", "replenishment_need", "excess_stock",
        "earliest_replenishment_lead_time_days", "risk_level", "primary_risk_factor"
    ])

    for itm in risk_resp.items:
        writer.writerow([
            itm.sku_id, itm.product_name, itm.destination_id, itm.destination_name, itm.horizon_days,
            itm.daily_forecast_rate, itm.total_forecast_demand, itm.on_hand, itm.reserved, itm.blocked,
            itm.confirmed_incoming, itm.dispatchable_stock, itm.cover_days, itm.demand_gap,
            itm.safety_stock_target, itm.target_stock, itm.replenishment_need, itm.excess_stock,
            itm.earliest_replenishment_lead_time_days, itm.risk_level, itm.primary_risk_factor
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=StockWise_risk_analysis_{horizon_days}d.csv"}
    )


@router.get(
    "/corridors/compare",
    response_model=CorridorComparisonResponse,
    summary="Compare corridors and supply routes for a destination and SKU",
)
def compare_corridors(
    destination_id: str = Query(..., description="Target destination facility ID"),
    sku_id: str = Query(..., description="Target SKU/Product ID"),
    horizon_days: int = Query(7, ge=1, le=30, description="Planning horizon in days"),
    snapshot_id: Optional[str] = Query(None, description="Optional snapshot ID"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """
    Evaluates all connected and alternative corridors for a specific destination and product,
    ranking them by feasibility, lead time, total delivered cost, and stock availability.
    Includes itemized freight and handling costs and explicit rejection reasons.
    """
    return compare_corridors_for_destination_sku(
        db=db,
        destination_id=destination_id,
        sku_id=sku_id,
        horizon_days=horizon_days,
        snapshot_id=snapshot_id,
    )


@router.post(
    "/optimization/simulate",
    response_model=ScenarioSimulationResponse,
    summary="Simulate what-if scenario distribution plan in-memory without database side effects",
)
def simulate_scenario(
    request: ScenarioSimulationRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner"])),
):
    """
    Performs an in-memory optimization simulation under hypothetical parameter variations
    (demand surge, freight rate spike, stock cut, route disruptions).
    Leaves actual inventory, reservations, and shipment records completely unchanged.
    """
    return simulate_what_if_scenario(
        db=db,
        request=request,
        org_id=current_user.org_id,
        user_id=current_user.user_id,
    )


@router.get(
    "/optimization/performance-metrics",
    response_model=OperationalPerformanceResponse,
    summary="Calculate operational distribution performance metrics across shipment lifecycles",
)
def get_operational_performance(
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """
    Tracks operational KPIs comparing recommended quantities to approved, reserved, dispatched,
    and delivered quantities, including stockout frequency, forecast variance, and delivered cost per unit.
    """
    return compute_operational_performance_metrics(
        db=db,
        org_id=current_user.org_id,
    )


@router.get(
    "/optimization/distribution-performance",
    response_model=DistributionPerformanceResponse,
    summary="Compute four core distribution performance KPIs",
)
def get_distribution_performance_kpis(
    run_id: Optional[str] = Query(None, description="Optional planning run ID filter"),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_roles(["admin", "planner", "logistics", "viewer"])),
):
    """
    Computes four core Distribution Performance KPIs:
    1. Demand fulfilment rate = fulfilled demand units / eligible demand units * 100
    2. Transportation cost = recorded transportation cost for the selected period
    3. Stockout rate = demand units unfulfilled because of stock unavailability / eligible demand units * 100
    4. Cost reduction = (baseline cost - optimized cost) / baseline cost * 100
    
    Distinguishes verified operational execution records from estimated optimization plans.
    Compares baseline and optimized plan over equivalent demand, dates, and constraints.
    """
    return compute_distribution_performance_kpis(
        db=db,
        run_id=run_id,
        org_id=current_user.org_id,
    )



