export interface DatabaseHealth {
  connected: boolean;
  status: 'connected' | 'disconnected';
  message: string;
  dialect: string;
  latency_ms: number | null;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  app_name: string;
  tagline: string;
  version: string;
  environment: string;
  timestamp: string;
  api: string;
  database: DatabaseHealth;
}

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastChecked: Date | null;
}

export type DatasetType = 'products' | 'locations' | 'inventory' | 'sales' | 'routes' | 'organizations';

export interface ImportRowError {
  id?: number | null;
  row_index: number;
  field_name?: string | null;
  rejected_value?: string | null;
  error_reason: string;
  error_code: string;
}

export interface ImportRunSummary {
  run_id: string;
  dataset_type: DatasetType;
  filename: string;
  file_format: string;
  file_size_bytes: number;
  status: 'completed' | 'partial' | 'failed' | 'preview_valid';
  total_rows: number;
  valid_rows: number;
  rejected_rows: number;
  snapshot_id?: string | null;
  created_at: string;
  errors: ImportRowError[];
}

export interface ImportRunListResponse {
  runs: ImportRunSummary[];
  total_runs: number;
}

export interface ProductItem {
  id: string;
  sku_id: string;
  name: string;
  category?: string | null;
  unit: string;
  case_pack: number;
  shelf_life_days?: number | null;
  created_at: string;
}

export interface OrganizationItem {
  org_id: string;
  name: string;
  org_type: 'fmcg_company' | 'cnf_agency' | 'logistics_provider' | 'distributor' | 'retailer' | string;
  contact_email?: string | null;
  contact_phone?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface LocationItem {
  id?: string;
  location_id: string;
  name: string;
  location_type:
    | 'manufacturing_plant'
    | 'company_warehouse'
    | 'central_warehouse'
    | 'regional_warehouse'
    | 'cnf_facility'
    | '3pl_facility'
    | 'distributor_warehouse'
    | 'retail_destination'
    | string;
  region: string;
  city?: string | null;
  address?: string | null;
  owner_org_id?: string | null;
  owner_org_name?: string | null;
  operator_org_id?: string | null;
  operator_org_name?: string | null;
  storage_capacity_units?: number | null;
  dispatch_capacity_daily?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  is_active?: boolean;
  created_at?: string;
}

export interface InventoryItem {
  id: number | string;
  snapshot_id: string;
  as_of_date: string;
  location_id: string;
  location_name?: string | null;
  sku_id: string;
  product_name?: string | null;
  category?: string | null;
  unit?: string | null;
  on_hand: number;
  reserved: number;
  blocked: number;
  confirmed_incoming?: number;
  dispatchable_stock: number;
  owner_org_id?: string | null;
  owner_org_name?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
  created_at?: string;
}

export interface SalesHistoryItem {
  id: number | string;
  sales_date: string;
  location_id?: string;
  destination_id?: string;
  sku_id: string;
  product_name?: string | null;
  units_sold?: number;
  quantity?: number;
  created_at?: string;
}

export interface RouteItem {
  id?: number | string;
  from_location_id?: string;
  to_location_id?: string;
  from_location_name?: string | null;
  from_location_type?: string | null;
  to_location_name?: string | null;
  to_location_type?: string | null;
  source_location_id?: string;
  destination_location_id?: string;
  carrier_agency_id?: string | null;
  carrier_agency_name?: string | null;
  lead_time_days: number;
  cost_rate?: number;
  cost_per_unit?: number;
  capacity_units?: number | null;
  sku_eligibility?: string;
  pricing_basis?: string;
  min_shipment_qty?: number | null;
  max_shipment_qty?: number | null;
  is_active?: boolean;
  status_notes?: string | null;
  created_at?: string;
}

export interface RouteEligibilityCheck {
  route_id: number;
  from_location_id: string;
  from_location_name: string;
  to_location_id: string;
  to_location_name: string;
  carrier_agency_name?: string | null;
  is_eligible: boolean;
  rejection_reasons: string[];
  lead_time_days: number;
  cost_rate: number;
}

export interface UnserviceableLocationInfo {
  location_id: string;
  name: string;
  location_type: string;
  region: string;
  reason: string;
}

export interface NetworkEligibilityResponse {
  total_locations: number;
  active_locations: number;
  total_routes: number;
  active_routes: number;
  eligible_corridors: RouteEligibilityCheck[];
  unserviceable_destinations: UnserviceableLocationInfo[];
  summary_message: string;
}

export interface ShipmentItem {
  shipment_id: string;
  sku_id: string;
  product_name?: string | null;
  quantity: number;
  source_location_id: string;
  source_location_name?: string | null;
  destination_location_id: string;
  destination_location_name?: string | null;
  owner_org_id?: string | null;
  owner_org_name?: string | null;
  carrier_agency_id?: string | null;
  carrier_agency_name?: string | null;
  route_id?: number | null;
  lead_time_days?: number | null;
  estimated_dispatch_date?: string | null;
  estimated_arrival_date?: string | null;
  estimated_transport_cost: number;
  actual_transport_cost?: number | null;
  currency?: string;
  status: 'proposed' | 'approved' | 'rejected' | 'ready_for_dispatch' | 'in_transit' | 'delivered' | 'cancelled';
  planning_run_id?: string | null;
  approval_status: 'pending' | 'approved' | 'rejected';
  approved_by?: string | null;
  approval_notes?: string | null;
  carrier_contact?: string | null;
  consignment_number?: string | null;
  vehicle_number?: string | null;
  driver_contact?: string | null;
  planned_pickup_date?: string | null;
  actual_pickup_date?: string | null;
  actual_delivery_date?: string | null;
  logistics_status?: 'unassigned' | 'assigned' | 'accepted' | 'rejected' | string;
  logistics_notes?: string | null;
  exception_reason?: string | null;
  exception_notes?: string | null;
  pod_reference?: string | null;
  dispatch_checklist?: string | null;
  events_count?: number;
  created_at: string;
  updated_at?: string;
}

export interface ShipmentEventItem {
  event_id: string;
  shipment_id: string;
  from_status: string;
  to_status: string;
  actor_id: string;
  actor_role?: string | null;
  notes?: string | null;
  metadata_json?: string | null;
  created_at: string;
}

export interface ShipmentTraceabilityItem {
  shipment_id: string;
  sku_id: string;
  product_name?: string | null;
  quantity: number;
  source_location_id: string;
  source_location_name?: string | null;
  destination_location_id: string;
  destination_location_name?: string | null;
  owner_org_id?: string | null;
  owner_org_name?: string | null;
  carrier_agency_id?: string | null;
  carrier_agency_name?: string | null;
  carrier_contact?: string | null;
  route_id?: number | null;
  lead_time_days?: number | null;
  currency: string;
  estimated_transport_cost: number;
  actual_transport_cost?: number | null;
  status: string;
  approval_status: string;
  approved_by?: string | null;
  approval_notes?: string | null;
  logistics_status: string;
  consignment_number?: string | null;
  vehicle_number?: string | null;
  driver_contact?: string | null;
  planned_pickup_date?: string | null;
  actual_pickup_date?: string | null;
  actual_delivery_date?: string | null;
  exception_reason?: string | null;
  exception_notes?: string | null;
  pod_reference?: string | null;
  dispatch_checklist?: string | null;
  planning_run_id?: string | null;
  decision_rationale?: string | null;
  planning_run_metadata?: Record<string, any> | null;
  decision_receipt?: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  events: ShipmentEventItem[];
  movements: Record<string, any>[];
}

export interface DispatchPreparePayload {
  authorized_user_id: string;
  actor_role?: string;
  checklist_items: string[];
  notes?: string;
}

export interface DispatchConfirmPayload {
  authorized_user_id: string;
  actor_role?: string;
  consignment_number?: string;
  vehicle_number?: string;
  driver_contact?: string;
  actual_pickup_date?: string;
  notes?: string;
}

export interface DeliveryConfirmPayload {
  authorized_user_id: string;
  actor_role?: string;
  actual_delivery_date?: string;
  actual_transport_cost?: number;
  pod_reference?: string;
  notes?: string;
}

export interface CarrierAssignPayload {
  carrier_agency_id: string;
  carrier_contact?: string;
  planned_pickup_date?: string;
  estimated_arrival_date?: string;
  authorized_user_id: string;
  actor_role?: string;
  notes?: string;
}

export interface CarrierDecisionPayload {
  accepted: boolean;
  authorized_user_id: string;
  actor_role?: string;
  consignment_number?: string;
  vehicle_number?: string;
  driver_contact?: string;
  notes?: string;
}

export interface ExceptionPayload {
  authorized_user_id: string;
  actor_role?: string;
  exception_reason: string;
  notes?: string;
}

export interface StockMovementItem {
  movement_id: string;
  shipment_id?: string | null;
  sku_id: string;
  product_name?: string | null;
  source_location_id: string;
  source_location_name?: string | null;
  destination_location_id: string;
  destination_location_name?: string | null;
  quantity: number;
  movement_type: string;
  status: string;
  timestamp: string;
  notes?: string | null;
}

// --- Phase 3 Distribution Intelligence Engine Types ---

export interface ForecastItem {
  sku_id: string;
  product_name?: string | null;
  destination_id: string;
  destination_name?: string | null;
  horizon_days: number;
  daily_forecast_rate: number;
  total_forecast_demand: number;
  forecast_method: string;
  data_sufficiency: 'sufficient' | 'insufficient_history' | 'zero_demand' | string;
  mae?: number | null;
  wape?: number | null;
  assumptions: string;
}

export interface ForecastResponse {
  horizon_days: number;
  total_skus: number;
  total_destinations: number;
  forecasts: ForecastItem[];
  holdout_evaluation_summary?: string | null;
}

export interface RiskAnalysisItem {
  sku_id: string;
  product_name?: string | null;
  destination_id: string;
  destination_name?: string | null;
  horizon_days: number;
  daily_forecast_rate: number;
  total_forecast_demand: number;
  on_hand: number;
  reserved: number;
  blocked: number;
  confirmed_incoming: number;
  dispatchable_stock: number;
  cover_days: number;
  demand_gap: number;
  safety_stock_target: number;
  target_stock?: number;
  replenishment_need: number;
  excess_stock?: number;
  earliest_replenishment_lead_time_days?: number | null;
  risk_level: 'critical' | 'high' | 'medium' | 'low';
  primary_risk_factor: string;
}

export interface RiskAnalysisResponse {
  horizon_days: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  items: RiskAnalysisItem[];
}

export interface OptimizationRequest {
  snapshot_id?: string | null;
  horizon_days: number;
  objective_strategy: string;
  allow_cross_region_routes?: boolean;
  authorized_user_id?: string;
}

export interface DecisionReceipt {
  recommendation_id: string;
  sku_id: string;
  product_name?: string | null;
  source_location_id: string;
  source_location_name?: string | null;
  destination_location_id: string;
  destination_location_name?: string | null;
  quantity: number;
  unit: string;
  lead_time_days: number;
  estimated_arrival_date: string;
  estimated_cost: number;
  evidence: string;
  rejected_alternatives: string[];
  unmet_demand_remaining: number;
  route_id?: number | null;
  distance_km?: number | null;
  base_freight_cost?: number | null;
  handling_cost?: number | null;
  allocated_batches?: Array<{
    batch_number?: string | null;
    allocated_quantity: number;
    expiry_date?: string | null;
    days_remaining?: number | null;
  }>;
  constraints_evaluated?: string[];
  stockout_prevented_units?: number;
  expiry_risk_reduction_units?: number;
}

export interface PlanComparisonMetrics {
  name: string;
  is_baseline: boolean;
  service_level_percent: number;
  fulfilled_demand_units: number;
  unmet_demand_units: number;
  estimated_transport_cost: number;
  stock_utilization_percent: number;
  constraint_violations_count: number;
  solve_time_seconds: number;
}

export interface PlanComparisonResponse {
  optimizer: PlanComparisonMetrics;
  baseline: PlanComparisonMetrics;
}

export interface UnmetDemandItem {
  sku_id: string;
  product_name?: string | null;
  destination_id: string;
  destination_name?: string | null;
  total_demand_gap: number;
  unmet_quantity: number;
  reasons: string[];
}

export interface PlanningRunResponse {
  run_id: string;
  snapshot_id?: string | null;
  horizon_days: number;
  objective_strategy: string;
  solver_status: string;
  solve_time_ms: number;
  total_demand_units: number;
  fulfilled_demand_units: number;
  unmet_demand_units: number;
  service_level_percent: number;
  estimated_transport_cost: number;
  stock_utilization_percent: number;
  recommended_shipments: ShipmentItem[];
  unmet_demand_breakdown: UnmetDemandItem[];
  decision_receipts: DecisionReceipt[];
  solver_name?: string;
  planning_mode?: string;
  baseline_comparison?: PlanComparisonResponse | null;
  created_at: string;
}

export interface PlanningRunSummary {
  run_id: string;
  snapshot_id?: string | null;
  horizon_days: number;
  objective_strategy: string;
  solver_status: string;
  solve_time_ms: number;
  total_demand_units: number;
  fulfilled_demand_units: number;
  unmet_demand_units: number;
  service_level_percent: number;
  estimated_transport_cost: number;
  stock_utilization_percent: number;
  created_at: string;
}

export interface FestivalEventItem {
  id: number;
  event_id: string;
  name: string;
  description?: string | null;
  start_date: string;
  end_date: string;
  regions: string[];
  applicable_categories: string[];
  default_uplift_percent: number;
  is_active: boolean;
  created_at: string;
}

export interface UtsavUpliftItem {
  sku_id: string;
  product_name: string;
  category: string;
  destination_id: string;
  destination_name: string;
  region: string;
  baseline_daily_rate: number;
  baseline_demand: number;
  uplift_scenario: string;
  uplift_percent: number;
  festival_demand: number;
  incremental_units: number;
  current_eligible_stock: number;
  additional_stock_needed: number;
  assumptions: string;
}

export interface UtsavUpliftResponse {
  event_id: string;
  event_name: string;
  uplift_scenario: string;
  uplift_percent: number;
  horizon_days: number;
  total_baseline_demand: number;
  total_festival_demand: number;
  total_incremental_demand: number;
  total_additional_stock_needed: number;
  items: UtsavUpliftItem[];
}

export interface SolverBenchmarkComparisonResponse {
  horizon_days: number;
  total_demand_units: number;
  ortools_metrics: PlanComparisonMetrics;
  highs_metrics: PlanComparisonMetrics;
  baseline_metrics: PlanComparisonMetrics;
  comparison_summary: string;
}

export interface DistributorDashboardResponse {
  distributor_org_id: string;
  total_owned_skus: number;
  total_on_hand_units: number;
  total_dispatchable_units: number;
  pending_requests_count: number;
  in_transit_shipments_count: number;
  near_expiry_batches_count: number;
  recent_shipments: ShipmentItem[];
  recent_requests: ShipmentItem[];
}

export interface DistributorRequestCreatePayload {
  sku_id: string;
  quantity: number;
  destination_location_id?: string;
  source_location_id?: string;
  reason?: string;
  notes?: string;
}

export interface RetailerDashboardResponse {
  retailer_org_id: string;
  total_store_skus: number;
  total_on_hand_units: number;
  total_available_units: number;
  pending_requests_count: number;
  approved_awaiting_fulfilment_count: number;
  in_transit_shipments_count: number;
  low_stock_skus_count: number;
  recent_shipments: ShipmentItem[];
  recent_requests: ShipmentItem[];
}

export interface RetailerRequestCreatePayload {
  sku_id: string;
  quantity: number;
  preferred_source_location_id?: string;
  required_by_date?: string;
  reason?: string;
  notes?: string;
}

// --- Corridor Alternative Comparison ---
export interface CorridorAlternativeItem {
  source_location_id: string;
  source_location_name: string;
  source_location_type: string;
  destination_location_id: string;
  destination_location_name: string;
  route_id: number;
  distance_km?: number | null;
  lead_time_days: number;
  cost_rate_per_unit: number;
  handling_cost_per_unit: number;
  total_delivered_cost_per_unit: number;
  dispatchable_stock: number;
  unexpired_dispatchable_stock: number;
  is_feasible: boolean;
  feasibility_status: string;
  rejection_reasons: string[];
  ranking: number;
}

export interface CorridorComparisonResponse {
  destination_id: string;
  destination_name: string;
  sku_id: string;
  product_name: string;
  horizon_days: number;
  demand_gap: number;
  target_stock: number;
  alternatives: CorridorAlternativeItem[];
  recommended_corridor?: CorridorAlternativeItem | null;
}

// --- What-If Scenario Simulation ---
export interface ScenarioSimulationRequest {
  snapshot_id?: string | null;
  horizon_days: number;
  demand_multiplier: number;
  freight_rate_multiplier: number;
  source_stock_multiplier: number;
  safety_buffer_days?: number | null;
  disrupted_route_ids: number[];
  solver_type: string;
  min_remaining_shelf_life_days?: number | null;
  authorized_user_id?: string;
}

export interface ScenarioImpactMetrics {
  metric: string;
  baseline_value: number;
  simulated_value: number;
  delta_value: number;
  delta_percent: number;
  unit: string;
  impact_direction: 'better' | 'worse' | 'neutral';
}

export interface ScenarioSimulationResponse {
  scenario_name: string;
  simulated_at: string;
  parameters: Record<string, any>;
  baseline_plan: Record<string, any>;
  simulated_plan: Record<string, any>;
  impact_analysis: ScenarioImpactMetrics[];
  simulated_shipments: ShipmentItem[];
  simulated_receipts: DecisionReceipt[];
  is_simulation: boolean;
}

// --- Operational Performance Tracking ---
export interface PerformanceLifecycleSummary {
  status: string;
  shipment_count: number;
  total_units: number;
  total_transport_cost: number;
}

export interface OperationalPerformanceResponse {
  as_of: string;
  total_planning_runs: number;
  total_recommended_units: number;
  total_approved_units: number;
  total_dispatched_units: number;
  total_delivered_units: number;
  approval_rate_percent: number;
  dispatch_rate_percent: number;
  delivery_fulfillment_rate_percent: number;
  average_cost_per_case: number;
  lifecycle_breakdown: PerformanceLifecycleSummary[];
}

// --- Portal Completion Types ---
export interface ProductCreatePayload {
  sku_id: string;
  name: string;
  category?: string;
  unit?: string;
  case_pack?: number;
  shelf_life_days?: number | null;
}

export interface ProductUpdatePayload {
  name?: string;
  category?: string;
  unit?: string;
  case_pack?: number;
  shelf_life_days?: number | null;
}

export interface CategorySummaryItem {
  category: string;
  product_count: number;
  sku_count?: number;
}

export interface LocationUpdatePayload {
  name?: string;
  location_type?: string;
  region?: string;
  city?: string | null;
  address?: string | null;
  owner_org_id?: string | null;
  operator_org_id?: string | null;
  storage_capacity_units?: number | null;
  dispatch_capacity_daily?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  is_active?: boolean;
}

export interface AdminUserItem {
  user_id: string;
  email: string;
  role: string;
  org_id?: string | null;
  org_name?: string | null;
  tenant_org_id?: string | null;
  tenant_org_name?: string | null;
  is_active: boolean;
}

export interface ReceiptConfirmPayload {
  received_quantity: number;
  condition_status: 'intact' | 'shortage' | 'damaged' | 'excess' | string;
  discrepancy_units?: number;
  notes?: string;
}

export interface RequestCancelPayload {
  reason?: string;
}


