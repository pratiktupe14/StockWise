from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.network import ShipmentResponse


class ForecastItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str
    product_name: Optional[str] = None
    destination_id: str
    destination_name: Optional[str] = None
    horizon_days: int
    daily_forecast_rate: float
    total_forecast_demand: float
    forecast_method: str  # seasonal_naive, moving_average_7d, zero_baseline, insufficient_history
    data_sufficiency: str  # sufficient, insufficient_history, zero_demand
    mae: Optional[float] = None
    wape: Optional[float] = None
    training_window: Optional[str] = None
    evaluation_window: Optional[str] = None
    assumptions: str


class ForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon_days: int
    total_skus: int
    total_destinations: int
    forecasts: List[ForecastItem]
    holdout_evaluation_summary: Optional[str] = None


class RiskAnalysisItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str
    product_name: Optional[str] = None
    destination_id: str
    destination_name: Optional[str] = None
    horizon_days: int
    daily_forecast_rate: float
    total_forecast_demand: float
    on_hand: float
    reserved: float
    blocked: float
    confirmed_incoming: float
    dispatchable_stock: float
    cover_days: float
    demand_gap: float
    safety_stock_target: float
    target_stock: float = 0.0
    replenishment_need: float
    excess_stock: float = 0.0
    earliest_replenishment_lead_time_days: Optional[float] = None
    expected_stockout_window: Optional[str] = None
    unfulfillable_demand: float = 0.0
    batch_expiry_risk: Optional[str] = None
    risk_level: str  # critical, high, medium, low
    primary_risk_factor: str


class RiskAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon_days: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    items: List[RiskAnalysisItem]


class OptimizationRequest(BaseModel):
    snapshot_id: Optional[str] = None
    horizon_days: int = Field(7, ge=1, le=30, description="Planning horizon in days")
    objective_strategy: str = Field("service-first", description="service-first, cost-weighted")
    solver_type: str = Field("ortools", description="ortools (GLOP LP) or scipy_highs")
    allow_cross_region_routes: bool = True
    authorized_user_id: str = "DIST-PLANNER-01"
    planning_mode: str = Field("standard", description="standard or utsav_sense")
    festival_event_id: Optional[str] = None
    demand_overrides: Optional[Dict[str, float]] = None
    min_remaining_shelf_life_days: Optional[int] = Field(None, ge=0, description="Minimum days shelf life required at destination receipt")
    require_batch_expiry: bool = Field(False, description="When true, strictly exclude batches missing explicit expiry dates")


class DecisionReceiptSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    recommendation_id: str
    sku_id: str
    product_name: Optional[str] = None
    source_location_id: str
    source_location_name: Optional[str] = None
    destination_location_id: str
    destination_location_name: Optional[str] = None
    quantity: float
    unit: str = "cases"
    lead_time_days: float
    expected_arrival_date: str
    estimated_cost: float
    currency: str = "INR"
    evidence: str
    rejected_alternatives: List[str]
    unmet_demand_remaining: float
    solver_name: Optional[str] = None
    solver_status: Optional[str] = None
    route_id: Optional[int] = None
    distance_km: Optional[float] = None
    base_freight_cost: Optional[float] = None
    handling_cost: Optional[float] = None
    allocated_batches: Optional[List[Dict[str, Any]]] = None
    constraints_evaluated: Optional[List[str]] = None
    stockout_prevented_units: Optional[float] = None
    expiry_risk_reduction_units: Optional[float] = None


class PlanComparisonMetricsSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan_id: str
    name: str
    is_baseline: bool
    service_level_percent: float
    fulfilled_demand_units: float
    unmet_demand_units: float
    estimated_transport_cost: float
    stock_utilization_percent: float
    constraint_violations_count: int
    solve_time_seconds: float
    solver_name: Optional[str] = None


class PlanningRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    snapshot_id: Optional[str] = None
    horizon_days: int
    objective_strategy: str
    solver_name: str = "ortools_glop"
    planning_mode: str = "standard"
    festival_event_id: Optional[str] = None
    solver_status: str
    solve_time_ms: float
    total_demand_units: float
    fulfilled_demand_units: float
    unmet_demand_units: float
    service_level_percent: float
    estimated_transport_cost: float
    stock_utilization_percent: float
    recommended_shipments: List[ShipmentResponse]
    unmet_demand_breakdown: List[Dict[str, Any]]
    decision_receipts: List[DecisionReceiptSchema]
    baseline_comparison: Optional[Dict[str, Any]] = None
    created_at: datetime


class SolverBenchmarkComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    horizon_days: int
    total_demand_units: float
    ortools_metrics: PlanComparisonMetricsSchema
    highs_metrics: PlanComparisonMetricsSchema
    baseline_metrics: PlanComparisonMetricsSchema
    comparison_summary: str


class FestivalEventCreate(BaseModel):
    event_id: str
    name: str
    description: Optional[str] = None
    start_date: str
    end_date: str
    regions: List[str] = Field(default_factory=lambda: ["National"])
    applicable_categories: List[str] = Field(default_factory=lambda: ["All"])
    default_uplift_percent: float = 35.0
    is_active: bool = True


class FestivalEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: str
    name: str
    description: Optional[str] = None
    start_date: str
    end_date: str
    regions: List[str]
    applicable_categories: List[str]
    default_uplift_percent: float
    is_active: bool
    created_at: datetime


class UtsavUpliftItem(BaseModel):
    sku_id: str
    product_name: str
    category: str
    destination_id: str
    destination_name: str
    region: str
    baseline_daily_rate: float
    baseline_demand: float
    uplift_scenario: str  # conservative, expected, high, custom
    uplift_percent: float
    festival_demand: float
    incremental_units: float
    current_eligible_stock: float
    additional_stock_needed: float
    assumptions: str


class UtsavUpliftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    event_name: str
    uplift_scenario: str
    uplift_percent: float
    horizon_days: int
    total_baseline_demand: float
    total_festival_demand: float
    total_incremental_demand: float
    total_additional_stock_needed: float
    items: List[UtsavUpliftItem]


# --- Corridor Alternative Comparison ---
class CorridorAlternativeItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_location_id: str
    source_location_name: str
    source_location_type: str
    destination_location_id: str
    destination_location_name: str
    route_id: int
    distance_km: Optional[float] = None
    distance_source: str = "haversine_road_adjusted"  # osrm_open_street_map | haversine_road_adjusted | transit_time_estimate | not_available
    is_verified_road_route: bool = False
    lead_time_days: float
    cost_rate_per_unit: float
    handling_cost_per_unit: float = 0.0
    total_delivered_cost_per_unit: float
    dispatchable_stock: float
    unexpired_dispatchable_stock: float
    is_feasible: bool
    feasibility_status: str  # feasible, insufficient_stock, exceeds_horizon, inactive_route, ineligible_sku, distributor_protected
    rejection_reasons: List[str] = Field(default_factory=list)
    ranking: int = 0


class CorridorComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    destination_id: str
    destination_name: str
    sku_id: str
    product_name: str
    horizon_days: int
    demand_gap: float
    target_stock: float
    alternatives: List[CorridorAlternativeItem]
    recommended_corridor: Optional[CorridorAlternativeItem] = None


# --- What-If Scenario Simulation ---
class ScenarioSimulationRequest(BaseModel):
    snapshot_id: Optional[str] = None
    horizon_days: int = Field(7, ge=1, le=30)
    demand_multiplier: float = Field(1.0, ge=0.1, le=5.0, description="Multiplier for forecast demand (e.g., 1.2 = +20%)")
    freight_rate_multiplier: float = Field(1.0, ge=0.1, le=5.0, description="Multiplier for transport cost rates")
    source_stock_multiplier: float = Field(1.0, ge=0.0, le=5.0, description="Multiplier for source warehouse stock")
    safety_buffer_days: Optional[float] = Field(None, ge=0.0, le=30.0, description="Safety stock buffer days")
    disrupted_route_ids: List[int] = Field(default_factory=list, description="IDs of routes to simulate as unavailable")
    solver_type: str = Field("ortools", description="ortools or scipy_highs")
    min_remaining_shelf_life_days: Optional[int] = None
    authorized_user_id: str = "SIMULATION-PLANNER"


class ScenarioImpactMetrics(BaseModel):
    metric: str
    baseline_value: float
    simulated_value: float
    delta_value: float
    delta_percent: float
    unit: str
    impact_direction: str  # "better", "worse", "neutral"


class ScenarioSimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_name: str
    simulated_at: datetime
    parameters: Dict[str, Any]
    baseline_plan: Dict[str, Any]
    simulated_plan: Dict[str, Any]
    impact_analysis: List[ScenarioImpactMetrics]
    simulated_shipments: List[ShipmentResponse]
    simulated_receipts: List[DecisionReceiptSchema]
    is_simulation: bool = True


# --- Operational Performance Tracking ---
class PerformanceLifecycleSummary(BaseModel):
    status: str
    shipment_count: int
    total_units: float
    total_transport_cost: float


class OperationalPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    as_of: datetime
    total_planning_runs: int
    total_recommended_units: float
    total_approved_units: float
    total_dispatched_units: float
    total_delivered_units: float
    approval_rate_percent: float
    dispatch_rate_percent: float
    delivery_fulfillment_rate_percent: float
    average_cost_per_case: float
    lifecycle_breakdown: List[PerformanceLifecycleSummary]
    recent_plan_compliance: List[Dict[str, Any]]


# --- ML Model Evaluation & Time-Series Schemas ---
class ForecastEvaluationPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: str
    sku_id: str
    destination_id: str
    actual_demand: Optional[float] = None
    predicted_demand: float
    error: Optional[float] = None
    is_holdout: bool = True
    is_future: bool = False


class ForecastEvaluationSeries(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku_id: str
    product_name: str
    destination_id: str
    destination_name: str
    forecast_method: str
    data_sufficiency: str
    sample_count: int
    total_actual_demand: Optional[float] = None
    total_predicted_demand: Optional[float] = None
    mae: Optional[float] = None
    wape: Optional[float] = None
    accuracy_percent: Optional[float] = None
    evaluation_period: Optional[str] = None
    evaluated_at: datetime
    points: List[ForecastEvaluationPoint]


class ForecastEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluated_at: datetime
    horizon_days: int
    sample_count: int
    total_actual_demand: Optional[float] = None
    total_predicted_demand: Optional[float] = None
    mae: Optional[float] = None
    wape: Optional[float] = None
    accuracy_percent: Optional[float] = None
    evaluation_period: Optional[str] = None
    data_sufficiency: str
    model_name: str = "Baseline Statistical Forecast (7-day Rolling Moving Average / Seasonal Naive)"
    accuracy_formula_note: str = "Forecast accuracy is defined as 100 - WAPE (%). Clamped to 0.0% when WAPE exceeds 100%."
    series: List[ForecastEvaluationSeries]
    aligned_timeseries: List[ForecastEvaluationPoint]


# --- Distribution Performance KPIs ---
class DistributionPerformanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    as_of: datetime
    run_id: Optional[str] = None
    period_label: str
    data_source_mode: str  # 'verified_operational' | 'estimated_plan' | 'simulated'

    # KPI 1: Demand fulfilment rate = fulfilled demand units / eligible demand units * 100
    demand_fulfilment_rate_percent: float
    fulfilled_demand_units: float
    eligible_demand_units: float
    demand_fulfilment_label: str

    # KPI 2: Transportation cost = recorded transportation cost for the selected period
    transportation_cost: float
    transportation_cost_label: str
    has_recorded_shipments: bool

    # KPI 3: Stockout rate = demand units unfulfilled because of stock unavailability / eligible demand units * 100
    stockout_rate_percent: float
    unmet_demand_units: float
    stockout_rate_label: str

    # KPI 4: Cost reduction = (baseline cost - optimized cost) / baseline cost * 100
    cost_reduction_percent: float
    baseline_cost: float
    optimized_cost: float
    cost_savings: float
    cost_reduction_label: str

