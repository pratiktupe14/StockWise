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
  validation_summary?: SystemValidationReport | null;
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
  inserted_rows?: number;
  updated_rows?: number;
  skipped_rows?: number;
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
  case_pack_quantity?: number;
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
  destination_name?: string | null;
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
  forecast_count?: number;
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
  critical_risk_count?: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  items: RiskAnalysisItem[];
  records?: RiskAnalysisItem[];
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
    shelf_life_remaining_days?: number | null;
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
  distance_source?: 'osrm_open_street_map' | 'haversine_road_adjusted' | 'transit_time_estimate' | 'not_available' | string;
  is_verified_road_route?: boolean;
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

// --- Phase 5: Dataset Sources & Data Readiness Types ---
export interface DatasetSourceItem {
  id: string;
  name: string;
  source_url: string;
  license: string;
  license_url?: string;
  attribution: string;
  geography: string;
  data_category: string;
  is_downloaded: boolean;
  is_ingested: boolean;
  raw_total_records: number;
  accepted_records: number;
  rejected_cancellations: number;
  checksum_sha256: string;
  last_ingested_at?: string | null;
  features_powered: string[];
  missing_operational_fields: string[];
  warnings: string[];
  remediation_action: string;
}

export interface DatasetReadinessResponse {
  status: string;
  database_counts: {
    organizations: number;
    products: number;
    locations: number;
    inventory_snapshots: number;
    sales_history_points: number;
    routes: number;
  };
  benchmark_counts: {
    benchmark_products: number;
    benchmark_sales_points: number;
    benchmark_routes: number;
  };
  sources: DatasetSourceItem[];
  operational_readiness: {
    forecasting_engine: string;
    routing_engine: string;
    distribution_optimizer: string;
    fefo_expiry_protection: string;
    logistics_execution: string;
  };
  fields_requiring_authorized_company_data: Array<{
    entity: string;
    field: string;
    reason: string;
  }>;
}

export interface BenchmarkIngestResponse {
  status: string;
  authorized_user: string;
  message?: string;
  records_ingested?: number;
  results: Record<string, any>;
}

export interface RequestCancelPayload {
  reason?: string;
}

// --- Phase 6: Expiry Risk & FEFO Intelligence Types ---
export interface BatchExpiryRiskItem {
  id?: number | null;
  snapshot_id: string;
  sku_id: string;
  product_name?: string | null;
  location_id: string;
  location_name?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
  days_remaining?: number | null;
  risk_category: 'expired' | 'critical' | 'warning' | 'high_risk' | 'medium_risk' | 'upcoming' | 'healthy' | 'unknown' | string;
  on_hand: number;
  reserved: number;
  blocked: number;
  dispatchable_quantity: number;
  is_dispatchable: boolean;
  owner_org_id?: string | null;
}

export interface ExpiryRiskSummaryResponse {
  total_batches: number;
  expired_batches: number;
  expired_units: number;
  critical_batches: number;
  critical_units: number;
  high_risk_batches: number;
  high_risk_units: number;
  medium_risk_batches: number;
  medium_risk_units: number;
  healthy_batches: number;
  healthy_units: number;
  unknown_expiry_batches: number;
  unknown_expiry_units: number;
  total_dispatchable_units: number;
  items: BatchExpiryRiskItem[];
}

export interface FEFOAllocationRequest {
  sku_id: string;
  demand_quantity: number;
  source_location_id?: string | null;
  destination_location_id?: string | null;
  min_remaining_shelf_life_days?: number;
}

export interface BatchAllocationItem {
  snapshot_id: string;
  batch_number?: string | null;
  location_id: string;
  expiry_date?: string | null;
  days_remaining?: number | null;
  allocated_quantity: number;
  available_before_allocation: number;
  remaining_after_allocation: number;
}

export interface FEFOAllocationResponse {
  sku_id: string;
  demand_quantity: number;
  total_allocated: number;
  unmet_demand: number;
  is_fully_allocated: boolean;
  min_remaining_shelf_life_days: number;
  allocations: BatchAllocationItem[];
}

export interface RedistributionRecommendation {
  recommendation_id: string;
  sku_id: string;
  product_name?: string | null;
  source_location_id: string;
  source_location_name?: string | null;
  destination_location_id: string;
  destination_location_name?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
  days_remaining?: number | null;
  risk_category: string;
  source_available_units: number;
  destination_unmet_demand: number;
  recommended_quantity: number;
  lead_time_days: number;
  expected_delivery_date: string;
  shelf_life_days_at_arrival: number;
  estimated_transport_cost: number;
  priority_score: number;
  rationale: string;
  owner_org_id: string;
}

export interface RedistributionRejectedCandidate {
  sku_id: string;
  source_location_id: string;
  destination_location_id: string;
  batch_number?: string | null;
  rejection_reason: string;
}

export interface RedistributionSummaryResponse {
  generated_at: string;
  total_candidates_analyzed: number;
  recommendations_count: number;
  potential_units_saved: number;
  total_estimated_transport_cost: number;
  recommendations: RedistributionRecommendation[];
  rejected_candidates: RedistributionRejectedCandidate[];
}

export interface CreateRedistributionProposalRequest {
  sku_id: string;
  source_location_id: string;
  destination_location_id: string;
  quantity: number;
  batch_number?: string | null;
  notes?: string | null;
}

// --- P1 & P2: ML Model Evaluation & Demand Series ---
export interface ForecastEvaluationPoint {
  date: string;
  sku_id: string;
  destination_id: string;
  actual_demand?: number | null;
  predicted_demand: number;
  error?: number | null;
  is_holdout: boolean;
  is_future: boolean;
}

export interface ForecastEvaluationSeries {
  sku_id: string;
  product_name: string;
  destination_id: string;
  destination_name: string;
  forecast_method: string;
  data_sufficiency: 'sufficient' | 'insufficient_history' | 'zero_demand' | string;
  sample_count: number;
  total_actual_demand?: number | null;
  total_predicted_demand?: number | null;
  mae?: number | null;
  wape?: number | null;
  accuracy_percent?: number | null;
  evaluation_period?: string | null;
  evaluated_at: string;
  points: ForecastEvaluationPoint[];
}

export interface ForecastEvaluationResponse {
  evaluated_at: string;
  horizon_days: number;
  sample_count: number;
  total_actual_demand?: number | null;
  total_predicted_demand?: number | null;
  mae?: number | null;
  wape?: number | null;
  accuracy_percent?: number | null;
  evaluation_period?: string | null;
  data_sufficiency: 'sufficient' | 'insufficient_history' | 'zero_demand' | string;
  model_name?: string;
  accuracy_formula_note?: string;
  series: ForecastEvaluationSeries[];
  aligned_timeseries: ForecastEvaluationPoint[];
}

// --- P3: Distribution Performance KPIs ---
export interface DistributionPerformanceResponse {
  as_of: string;
  run_id?: string | null;
  period_label: string;
  data_source_mode: 'verified_operational' | 'estimated_plan' | 'simulated' | string;
  demand_fulfilment_rate_percent: number;
  fulfilled_demand_units: number;
  eligible_demand_units: number;
  demand_fulfilment_label: string;
  transportation_cost: number;
  transportation_cost_label: string;
  has_recorded_shipments: boolean;
  stockout_rate_percent: number;
  unmet_demand_units: number;
  stockout_rate_label: string;
  cost_reduction_percent: number;
  baseline_cost: number;
  optimized_cost: number;
  cost_savings: number;
  cost_reduction_label: string;
}

// --- System Health & Algorithm Validation Engine ---
export interface SystemValidationCheck {
  check_id: string;
  title: string;
  module_id: string;
  module_name: string;
  category: string;
  check_type: 'positive' | 'negative' | 'boundary' | 'failure_case';
  status: 'passed' | 'failed' | 'warning' | 'blocked' | 'untested';
  execution_time_ms: number;
  message: string;
  evidence: Record<string, any>;
  error_detail?: string | null;
  tested_at?: string | null;
}

export interface ModuleValidationSummary {
  module_id: string;
  name: string;
  category: string;
  description: string;
  checks: SystemValidationCheck[];
  passed_checks: number;
  executed_checks: number;
  total_in_scope_checks: number;
  failed_checks: number;
  warning_checks: number;
  blocked_checks: number;
  untested_checks: number;
  test_pass_rate_percent: number | null; // null if unexecuted ("Not Tested")
  feature_coverage_percent: number;
  verified_coverage_percent: number;
  status: 'passing' | 'degraded' | 'failing' | 'not_tested';
}

export interface SystemValidationReport {
  report_id: string;
  evaluated_at: string;
  overall_test_pass_rate_percent: number | null;
  overall_feature_coverage_percent: number;
  overall_verified_coverage_percent: number;
  total_passed: number;
  total_failed: number;
  total_warning: number;
  total_blocked: number;
  total_untested: number;
  total_executed: number;
  total_in_scope: number;
  modules: ModuleValidationSummary[];
  last_validation_timestamp: string;
}
