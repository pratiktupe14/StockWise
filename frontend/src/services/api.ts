import type {
  HealthResponse,
  ImportRunSummary,
  ImportRunListResponse,
  ImportRowError,
  InventoryItem,
  ProductItem,
  LocationItem,
  RouteItem,
  SalesHistoryItem,
  DatasetType,
  OrganizationItem,
  NetworkEligibilityResponse,
  ShipmentItem,
  StockMovementItem,
  ShipmentEventItem,
  ShipmentTraceabilityItem,
  DispatchPreparePayload,
  DispatchConfirmPayload,
  DeliveryConfirmPayload,
  CarrierAssignPayload,
  CarrierDecisionPayload,
  ExceptionPayload,
  ForecastResponse,
  RiskAnalysisResponse,
  OptimizationRequest,
  PlanningRunResponse,
  PlanningRunSummary,
  DecisionReceipt,
  PlanComparisonResponse,
  FestivalEventItem,
  UtsavUpliftResponse,
  SolverBenchmarkComparisonResponse,
  DistributorDashboardResponse,
  DistributorRequestCreatePayload,
  RetailerDashboardResponse,
  RetailerRequestCreatePayload,
  CorridorComparisonResponse,
  ScenarioSimulationRequest,
  ScenarioSimulationResponse,
  OperationalPerformanceResponse,
  ProductCreatePayload,
  ProductUpdatePayload,
  CategorySummaryItem,
  LocationUpdatePayload,
  AdminUserItem,
  RequestCancelPayload,
  ReceiptConfirmPayload,
  DatasetReadinessResponse,
  DatasetSourceItem,
  BenchmarkIngestResponse,
  ExpiryRiskSummaryResponse,
  FEFOAllocationRequest,
  FEFOAllocationResponse,
  RedistributionSummaryResponse,
  CreateRedistributionProposalRequest,
  ForecastEvaluationResponse,
  DistributionPerformanceResponse,
  SystemValidationReport,
} from '../types/api';
import { getAuthHeaders } from './auth';


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export class ApiError extends Error {
  status?: number;
  data?: unknown;
  constructor(message: string, status?: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Fetches the backend system and database health status.
 * Evaluates live API availability and actual database query connectivity.
 */
export async function getSystemHealth(): Promise<HealthResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 6000);

  try {
    const response = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw new ApiError(`Health check failed with HTTP ${response.status}`, response.status);
    }

    const data: HealthResponse = await response.json();
    return data;
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof ApiError) {
      throw err;
    }
    if (err instanceof Error) {
      if (err.name === 'AbortError') {
        throw new ApiError('Health check request timed out after 6 seconds');
      }
      throw new ApiError(err.message || 'Network connection failed');
    }
    throw new ApiError('An unexpected network error occurred');
  }
}

/**
 * Uploads a CSV or Excel file for a specific dataset type.
 */
export async function uploadDataset(
  datasetType: DatasetType,
  file: File
): Promise<ImportRunSummary> {
  const formData = new FormData();
  formData.append('file', file);

  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/imports/${datasetType}`, {
    method: 'POST',
    headers: {
      ...authHeaders,
    },
    body: formData,
  });

  const body = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Upload failed with HTTP ${response.status}`;
    throw new ApiError(errorMsg, response.status, body);
  }

  return body as ImportRunSummary;
}

/**
 * Retrieves the history of import runs.
 */
export async function getImportRuns(datasetType?: string): Promise<ImportRunListResponse> {
  const url = datasetType
    ? `${API_BASE_URL}/imports?dataset_type=${encodeURIComponent(datasetType)}`
    : `${API_BASE_URL}/imports`;

  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch import runs (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Retrieves row-level errors for a specific import run.
 */
export async function getImportRunErrors(runId: string): Promise<ImportRowError[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/imports/${runId}/errors`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch import errors (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Generates direct download URL for sample templates.
 */
export function getTemplateDownloadUrl(datasetType: DatasetType, format: 'csv' | 'xlsx'): string {
  return `${API_BASE_URL}/imports/templates/${datasetType}?format=${format}`;
}

/**
 * Retrieves persisted inventory records.
 */
export async function getInventory(params?: {
  snapshotId?: string;
  locationId?: string;
  skuId?: string;
  ownerOrgId?: string;
  includeBenchmark?: boolean;
}): Promise<InventoryItem[]> {
  const query = new URLSearchParams();
  if (params?.snapshotId) query.append('snapshot_id', params.snapshotId);
  if (params?.locationId) query.append('location_id', params.locationId);
  if (params?.skuId) query.append('sku_id', params.skuId);
  if (params?.ownerOrgId) query.append('owner_org_id', params.ownerOrgId);
  if (params?.includeBenchmark) query.append('include_benchmark', 'true');

  const url = `${API_BASE_URL}/inventory${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch inventory records (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Retrieves expiry risk analytics and batch health summary.
 */
export async function getInventoryExpiryRisk(params?: {
  skuId?: string;
  locationId?: string;
}): Promise<ExpiryRiskSummaryResponse> {
  const query = new URLSearchParams();
  if (params?.skuId) query.append('sku_id', params.skuId);
  if (params?.locationId) query.append('location_id', params.locationId);

  const url = `${API_BASE_URL}/inventory/expiry-risk${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch expiry risk (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Executes deterministic FEFO batch allocation for requested demand.
 */
export async function allocateInventoryFefo(payload: FEFOAllocationRequest): Promise<FEFOAllocationResponse> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/inventory/fefo-allocate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new ApiError(`FEFO allocation failed (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

export const allocateInventoryFEFO = allocateInventoryFefo;

/**
 * Retrieves authorized redistribution recommendations for near-expiry and surplus stock.
 */
export async function getRedistributionRecommendations(params?: {
  skuId?: string;
  sourceLocationId?: string;
  maxExpiryDays?: number;
}): Promise<RedistributionSummaryResponse> {
  const query = new URLSearchParams();
  if (params?.skuId) query.append('sku_id', params.skuId);
  if (params?.sourceLocationId) query.append('source_location_id', params.sourceLocationId);
  if (params?.maxExpiryDays) query.append('max_expiry_days', String(params.maxExpiryDays));

  const url = `${API_BASE_URL}/redistribution/recommendations${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch redistribution recommendations (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Submits an authorized redistribution recommendation as a formal shipment proposal.
 */
export async function submitRedistributionProposal(payload: CreateRedistributionProposalRequest): Promise<ShipmentItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/redistribution/propose`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const msg = body?.detail || `Failed to submit redistribution proposal (HTTP ${response.status})`;
    throw new ApiError(msg, response.status, body);
  }


  return response.json();
}



/**
 * Retrieves list of master products.
 */
export async function getProducts(): Promise<ProductItem[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/products`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch products (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Retrieves list of master locations.
 */
export async function getLocations(): Promise<LocationItem[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/locations`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch locations (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Retrieves permitted routes.
 */
export async function getRoutes(): Promise<RouteItem[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/routes`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch routes (HTTP ${response.status})`, response.status);
  }

  return response.json();
}

/**
 * Retrieves historical sales / consumption records.
 */
export async function getSalesHistory(params?: {
  skuId?: string;
  destinationId?: string;
  limit?: number;
}): Promise<SalesHistoryItem[]> {
  const query = new URLSearchParams();
  if (params?.skuId) query.append('sku_id', params.skuId);
  if (params?.destinationId) query.append('destination_id', params.destinationId);
  if (params?.limit) query.append('limit', String(params.limit));

  const url = `${API_BASE_URL}/sales${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch sales history (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Retrieves master organizations (FMCG companies, C&F agencies, 3PLs, distributors).
 */
export async function getOrganizations(params?: { orgType?: string; isActive?: boolean }): Promise<OrganizationItem[]> {
  const query = new URLSearchParams();
  if (params?.orgType) query.append('org_type', params.orgType);
  if (params?.isActive !== undefined) query.append('is_active', String(params.isActive));

  const url = `${API_BASE_URL}/organizations${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch organizations (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Registers an organization.
 */
export async function createOrganization(payload: Partial<OrganizationItem>): Promise<OrganizationItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/organizations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to create organization (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as OrganizationItem;
}

/**
 * Retrieves network facilities and locations with owner/operator organizations.
 */
export async function getNetworkLocations(params?: { locationType?: string; region?: string }): Promise<LocationItem[]> {
  const query = new URLSearchParams();
  if (params?.locationType) query.append('location_type', params.locationType);
  if (params?.region) query.append('region', params.region);

  const url = `${API_BASE_URL}/network/locations${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch network locations (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Creates a network location/facility.
 */
export async function createNetworkLocation(payload: Partial<LocationItem>): Promise<LocationItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/network/locations`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to create location (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as LocationItem;
}

/**
 * Retrieves permitted routes with carrier agency details.
 */
export async function getNetworkRoutes(isActive?: boolean): Promise<RouteItem[]> {
  const query = new URLSearchParams();
  if (isActive !== undefined) query.append('is_active', String(isActive));

  const url = `${API_BASE_URL}/network/routes${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch network routes (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Creates or configures a permitted distribution route.
 */
export async function createNetworkRoute(payload: Partial<RouteItem>): Promise<RouteItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/network/routes`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to save route (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as RouteItem;
}

/**
 * Analyzes network eligibility, evaluating corridors and unserviceable destinations.
 */
export async function getNetworkEligibility(): Promise<NetworkEligibilityResponse> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/network/eligibility`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'Cache-Control': 'no-cache',
      ...authHeaders,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch network eligibility (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Retrieves recorded and proposed shipments.
 */
export async function getShipments(params?: {
  status?: string;
  approvalStatus?: string;
  skuId?: string;
  sourceLocationId?: string;
  destinationLocationId?: string;
  limit?: number;
}): Promise<ShipmentItem[]> {
  const query = new URLSearchParams();
  if (params?.status) query.append('status', params.status);
  if (params?.approvalStatus) query.append('approval_status', params.approvalStatus);
  if (params?.skuId) query.append('sku_id', params.skuId);
  if (params?.sourceLocationId) query.append('source_location_id', params.sourceLocationId);
  if (params?.destinationLocationId) query.append('destination_location_id', params.destinationLocationId);
  if (params?.limit) query.append('limit', params.limit.toString());

  const url = `${API_BASE_URL}/shipments${query.toString() ? `?${query.toString()}` : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch shipments (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Proposes a new shipment with route and stock verification.
 */
export async function proposeShipment(payload: {
  sku_id: string;
  source_location_id: string;
  destination_location_id: string;
  quantity: number;
  owner_org_id?: string;
  carrier_agency_id?: string;
  notes?: string;
}): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/propose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to propose shipment (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Records governance decision (approval or rejection) for a proposed shipment.
 */
export async function approveShipment(
  shipmentId: string,
  approved: boolean,
  authorizedUserId: string,
  notes?: string
): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({
      approved,
      authorized_user_id: authorizedUserId,
      notes,
    }),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Approval failed (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Updates operational or simulated shipment status.
 */
export async function updateShipmentStatus(
  shipmentId: string,
  status: string,
  notes?: string
): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({
      status,
      notes,
    }),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Status update failed (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Prepares warehouse dispatch, reconciles stock, and saves readiness checklist.
 */
export async function prepareShipmentDispatch(shipmentId: string, payload: DispatchPreparePayload): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/prepare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Dispatch preparation failed (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Confirms physical vehicle dispatch into transit, deducting physical warehouse stock.
 */
export async function confirmShipmentDispatch(shipmentId: string, payload: DispatchConfirmPayload): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/dispatch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Dispatch confirmation failed (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Confirms physical destination delivery receipt, crediting destination stock.
 */
export async function confirmShipmentDelivery(shipmentId: string, payload: DeliveryConfirmPayload): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/deliver`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Delivery confirmation failed (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Assigns a logistics provider / carrier agency to an approved shipment.
 */
export async function assignShipmentCarrier(shipmentId: string, payload: CarrierAssignPayload): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/assign-carrier`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Carrier assignment failed (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Records carrier coordinator acceptance or rejection of a shipment allocation.
 */
export async function recordCarrierDecision(shipmentId: string, payload: CarrierDecisionPayload): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/carrier-decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Carrier decision update failed (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Logs delay reasons, breakdown, weather disruption, or delivery exceptions.
 */
export async function recordShipmentException(shipmentId: string, payload: ExceptionPayload): Promise<ShipmentItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/exception`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Exception logging failed (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Cancels shipment and reverses warehouse reservations before dispatch.
 */
export async function cancelShipmentExecution(shipmentId: string, authorizedUserId: string, notes?: string): Promise<ShipmentItem> {
  const query = new URLSearchParams({ authorized_user_id: authorizedUserId });
  if (notes) query.append('notes', notes);

  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/cancel?${query.toString()}`, {
    method: 'POST',
    headers: { 'Accept': 'application/json' },
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Cancellation failed (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 4: Retrieves chronological immutable audit trail of events for a shipment.
 */
export async function getShipmentEvents(shipmentId: string): Promise<ShipmentEventItem[]> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/events`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch shipment events (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Phase 4: Retrieves full end-to-end plan-to-execution traceability.
 */
export async function getShipmentTraceability(shipmentId: string): Promise<ShipmentTraceabilityItem> {
  const response = await fetch(`${API_BASE_URL}/shipments/${encodeURIComponent(shipmentId)}/traceability`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch traceability details (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Retrieves traceable stock movement audit history.
 */
export async function getStockMovements(params?: { shipmentId?: string; skuId?: string }): Promise<StockMovementItem[]> {
  const query = new URLSearchParams();
  if (params?.shipmentId) query.append('shipment_id', params.shipmentId);
  if (params?.skuId) query.append('sku_id', params.skuId);

  const url = `${API_BASE_URL}/shipments/movements${query.toString() ? `?${query.toString()}` : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch stock movements (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

// --- Phase 3 Distribution Intelligence Engine API Methods ---

/**
 * Computes or retrieves demand forecast across SKUs and destinations.
 */
export async function getDemandForecast(
  horizonDays: number = 7,
  skuId?: string,
  destinationId?: string
): Promise<ForecastResponse> {
  const query = new URLSearchParams();
  query.append('horizon_days', horizonDays.toString());
  if (skuId) query.append('sku_id', skuId);
  if (destinationId) query.append('destination_id', destinationId);

  const response = await fetch(`${API_BASE_URL}/forecast?${query.toString()}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch demand forecasts (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * P1 & P2: Evaluates ML forecast model against historical holdout data.
 * Computes MAE, WAPE, and Forecast Accuracy without data leakage.
 * Returns aligned historical and future demand time-series without fabricated actuals.
 */
export async function getForecastEvaluation(
  horizonDays: number = 7,
  skuId?: string,
  destinationId?: string
): Promise<ForecastEvaluationResponse> {
  const query = new URLSearchParams();
  query.append('horizon_days', horizonDays.toString());
  if (skuId) query.append('sku_id', skuId);
  if (destinationId) query.append('destination_id', destinationId);

  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/forecast/evaluation?${query.toString()}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch forecast evaluation (HTTP ${response.status})`, response.status);
  }
  return response.json();
}


/**
 * Evaluates destination stock positions, days of cover, demand gaps, and stockout risks.
 */
export async function getInventoryRisks(
  horizonDays: number = 7,
  snapshotId?: string,
  destinationId?: string,
  skuId?: string
): Promise<RiskAnalysisResponse> {
  const query = new URLSearchParams();
  query.append('horizon_days', horizonDays.toString());
  if (snapshotId) query.append('snapshot_id', snapshotId);
  if (destinationId) query.append('destination_id', destinationId);
  if (skuId) query.append('sku_id', skuId);

  const response = await fetch(`${API_BASE_URL}/risk/analysis?${query.toString()}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch inventory risk analysis (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Executes 2-stage linear optimization to generate optimal, constraint-aware distribution plans.
 */
export async function runDistributionOptimization(
  request: OptimizationRequest
): Promise<PlanningRunResponse> {
  const response = await fetch(`${API_BASE_URL}/optimization/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(request),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Optimization failed (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as PlanningRunResponse;
}

/**
 * Retrieves the list of historical planning runs.
 */
export async function getPlanningRuns(
  limit: number = 20,
  offset: number = 0
): Promise<PlanningRunSummary[]> {
  const response = await fetch(`${API_BASE_URL}/optimization/runs?limit=${limit}&offset=${offset}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch planning runs (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Retrieves full details of a specific planning run.
 */
export async function getPlanningRunDetails(runId: string): Promise<PlanningRunResponse> {
  const response = await fetch(`${API_BASE_URL}/optimization/runs/${encodeURIComponent(runId)}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch planning run ${runId} (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Retrieves decision receipts for all proposed movements in a planning run.
 */
export async function getDecisionReceipts(runId: string): Promise<DecisionReceipt[]> {
  const response = await fetch(`${API_BASE_URL}/optimization/runs/${encodeURIComponent(runId)}/receipts`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch decision receipts (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Retrieves baseline vs optimizer 6-dimension benchmark comparison.
 */
export async function getPlanComparison(runId: string): Promise<PlanComparisonResponse> {
  const response = await fetch(`${API_BASE_URL}/optimization/runs/${encodeURIComponent(runId)}/comparison`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch plan comparison (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Compares corridors and supply routes for a destination and SKU.
 */
export async function compareCorridors(
  destinationId: string,
  skuId: string,
  horizonDays: number = 7,
  snapshotId?: string
): Promise<CorridorComparisonResponse> {
  const params = new URLSearchParams({
    destination_id: destinationId,
    sku_id: skuId,
    horizon_days: String(horizonDays),
  });
  if (snapshotId) {
    params.set('snapshot_id', snapshotId);
  }

  const response = await fetch(`${API_BASE_URL}/corridors/compare?${params.toString()}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to compare corridors (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Simulates a what-if scenario distribution plan in-memory without database side effects.
 */
export async function simulateWhatIfScenario(
  payload: ScenarioSimulationRequest
): Promise<ScenarioSimulationResponse> {
  const response = await fetch(`${API_BASE_URL}/optimization/simulate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to simulate scenario (HTTP ${response.status})`, response.status);
  }
  return body as ScenarioSimulationResponse;
}

/**
 * Calculates operational distribution performance metrics across shipment lifecycles.
 */
export async function getOperationalPerformanceMetrics(): Promise<OperationalPerformanceResponse> {
  const response = await fetch(`${API_BASE_URL}/optimization/performance-metrics`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch operational performance metrics (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * P3: Computes four core distribution performance KPIs:
 * 1. Demand fulfilment rate (%)
 * 2. Transportation cost (₹)
 * 3. Stockout rate (%)
 * 4. Cost reduction (%)
 * Differentiates verified operational execution records from estimated optimization plans.
 */
export async function getDistributionPerformance(
  runId?: string
): Promise<DistributionPerformanceResponse> {
  const query = new URLSearchParams();
  if (runId) query.append('run_id', runId);

  const authHeaders = await getAuthHeaders();
  const url = `${API_BASE_URL}/optimization/distribution-performance${query.toString() ? `?${query.toString()}` : ''}`;
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch distribution performance KPIs (HTTP ${response.status})`, response.status);
  }
  return response.json();
}


/**
 * Previews and validates dataset file before committing.
 */
export async function previewDataset(datasetType: DatasetType, file: File): Promise<ImportRunSummary> {
  const formData = new FormData();
  formData.append('file', file);

  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/imports/${encodeURIComponent(datasetType)}/preview`, {
    method: 'POST',
    headers: {
      ...authHeaders,
    },
    body: formData,
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to preview ${datasetType} (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as ImportRunSummary;
}

/**
 * Returns downloadable error CSV report URL for an import run.
 */
export function getImportErrorsCSVUrl(runId: string): string {
  return `${API_BASE_URL}/imports/${encodeURIComponent(runId)}/errors.csv`;
}

/**
 * Executes side-by-side solver benchmark on the exact same snapshot and constraints.
 */
export async function getSolverBenchmark(payload: {
  snapshot_id?: string;
  horizon_days?: number;
  objective_strategy?: string;
}): Promise<SolverBenchmarkComparisonResponse> {
  const response = await fetch(`${API_BASE_URL}/optimization/benchmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new ApiError(`Failed to execute solver benchmark (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Fetches all cultural and regional festival calendar events.
 */
export async function getFestivalEvents(): Promise<FestivalEventItem[]> {
  const response = await fetch(`${API_BASE_URL}/utsav/events`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new ApiError(`Failed to fetch festival events (HTTP ${response.status})`, response.status);
  }
  return response.json();
}

/**
 * Creates a new regional or cultural festival event in planning calendar.
 */
export async function createFestivalEvent(payload: {
  event_id: string;
  name: string;
  description?: string;
  start_date: string;
  end_date: string;
  regions: string[];
  applicable_categories: string[];
  default_uplift_percent: number;
}): Promise<FestivalEventItem> {
  const response = await fetch(`${API_BASE_URL}/utsav/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to create festival event (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as FestivalEventItem;
}

/**
 * Computes festival demand uplift and additional stock requirements.
 */
export async function getFestivalUplift(
  eventId: string,
  scenario: string = 'expected',
  customUpliftPercent?: number,
  horizonDays: number = 7
): Promise<UtsavUpliftResponse> {
  const params = new URLSearchParams({
    event_id: eventId,
    scenario,
    horizon_days: String(horizonDays),
  });
  if (customUpliftPercent !== undefined) {
    params.set('custom_uplift_percent', String(customUpliftPercent));
  }

  const response = await fetch(`${API_BASE_URL}/utsav/forecast-uplift?${params.toString()}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to calculate festival uplift (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as UtsavUpliftResponse;
}

/**
 * Runs distribution optimization with festival-adjusted demand.
 */
export async function executeFestivalOptimization(payload: {
  event_id: string;
  scenario?: string;
  custom_uplift_percent?: number;
  horizon_days?: number;
  authorized_user_id?: string;
}): Promise<PlanningRunResponse> {
  const response = await fetch(`${API_BASE_URL}/utsav/optimize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const errorMsg = body?.detail || body?.message || `Failed to run festival optimization (HTTP ${response.status})`;
    throw new ApiError(errorMsg, response.status, body);
  }
  return body as PlanningRunResponse;
}

/**
 * CSV Export download URLs.
 */
export function getExportShipmentsCSVUrl(runId: string): string {
  return `${API_BASE_URL}/optimization/runs/${encodeURIComponent(runId)}/export/shipments.csv`;
}

export function getExportReceiptsCSVUrl(runId: string): string {
  return `${API_BASE_URL}/optimization/runs/${encodeURIComponent(runId)}/export/receipts.csv`;
}

export function getExportUnmetDemandCSVUrl(runId: string): string {
  return `${API_BASE_URL}/optimization/runs/${encodeURIComponent(runId)}/export/unmet-demand.csv`;
}

export function getExportRiskAnalysisCSVUrl(horizonDays: number = 7): string {
  return `${API_BASE_URL}/risk/export/analysis.csv?horizon_days=${horizonDays}`;
}

export function getExportFestivalUpliftCSVUrl(eventId: string, scenario: string = 'expected', horizonDays: number = 7): string {
  return `${API_BASE_URL}/utsav/events/${encodeURIComponent(eventId)}/export.csv?scenario=${encodeURIComponent(scenario)}&horizon_days=${horizonDays}`;
}

/**
 * Distributor Portal API Clients
 */

export async function getDistributorDashboard(): Promise<DistributorDashboardResponse> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/distributor/dashboard`, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch distributor dashboard (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function getDistributorInventory(params?: { skuId?: string; locationId?: string }): Promise<InventoryItem[]> {
  const query = new URLSearchParams();
  if (params?.skuId) query.append('sku_id', params.skuId);
  if (params?.locationId) query.append('location_id', params.locationId);

  const url = `${API_BASE_URL}/distributor/inventory${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch distributor inventory (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function getDistributorRequests(): Promise<ShipmentItem[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/distributor/requests`, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch distributor requests (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function submitDistributorRequest(payload: DistributorRequestCreatePayload): Promise<ShipmentItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/distributor/requests`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to submit distributor request (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function getDistributorShipments(statusFilter?: string): Promise<ShipmentItem[]> {
  const query = new URLSearchParams();
  if (statusFilter) query.append('status_filter', statusFilter);

  const url = `${API_BASE_URL}/distributor/shipments${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch distributor shipments (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

/**
 * Retail Shop Portal API Clients
 */

export async function getRetailerDashboard(): Promise<RetailerDashboardResponse> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/retailer/dashboard`, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch retailer dashboard (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function getRetailerInventory(params?: { skuId?: string; locationId?: string }): Promise<InventoryItem[]> {
  const query = new URLSearchParams();
  if (params?.skuId) query.append('sku_id', params.skuId);
  if (params?.locationId) query.append('location_id', params.locationId);

  const url = `${API_BASE_URL}/retailer/inventory${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch retailer inventory (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function getRetailerRequests(): Promise<ShipmentItem[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/retailer/requests`, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch retailer requests (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function submitRetailerRequest(payload: RetailerRequestCreatePayload): Promise<ShipmentItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/retailer/requests`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to submit retailer request (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

export async function getRetailerShipments(statusFilter?: string): Promise<ShipmentItem[]> {
  const query = new URLSearchParams();
  if (statusFilter) query.append('status_filter', statusFilter);

  const url = `${API_BASE_URL}/retailer/shipments${query.toString() ? `?${query.toString()}` : ''}`;
  const authHeaders = await getAuthHeaders();
  const response = await fetch(url, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch retailer shipments (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

/**
 * Company Admin Portal - Product & Category Management
 */
export async function createProduct(payload: ProductCreatePayload): Promise<ProductItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/products`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to create product (HTTP ${response.status})`, response.status, body);
  }
  return body as ProductItem;
}

export async function updateProduct(skuId: string, payload: ProductUpdatePayload): Promise<ProductItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/products/${encodeURIComponent(skuId)}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to update product (HTTP ${response.status})`, response.status, body);
  }
  return body as ProductItem;
}

export async function deleteProduct(skuId: string): Promise<{ message: string; sku_id: string }> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/products/${encodeURIComponent(skuId)}`, {
    method: 'DELETE',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to delete product (HTTP ${response.status})`, response.status, body);
  }
  return body;
}

export async function getProductCategories(): Promise<CategorySummaryItem[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/categories`, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch categories (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

/**
 * Company Admin Portal - Facility Management & Admin Users
 */
export async function updateNetworkLocation(locationId: string, payload: LocationUpdatePayload): Promise<LocationItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/network/locations/${encodeURIComponent(locationId)}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to update location (HTTP ${response.status})`, response.status, body);
  }
  return body as LocationItem;
}

export async function getAdminUsers(): Promise<AdminUserItem[]> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/admin/users`, {
    method: 'GET',
    headers: { 'Accept': 'application/json', ...authHeaders },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.detail || `Failed to fetch admin users (HTTP ${response.status})`, response.status, body);
  }
  return response.json();
}

/**
 * Distributor Portal - Receipt Confirmation & Request Cancellation
 */
export async function confirmDistributorReceipt(shipmentId: string, payload: ReceiptConfirmPayload): Promise<ShipmentItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/distributor/shipments/${encodeURIComponent(shipmentId)}/confirm-receipt`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to confirm distributor delivery (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

export async function cancelDistributorRequest(shipmentId: string, payload?: RequestCancelPayload): Promise<ShipmentItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/distributor/requests/${encodeURIComponent(shipmentId)}/cancel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload || {}),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to cancel request (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Retailer Portal - Store Receipt Confirmation & Request Cancellation
 */
export async function confirmRetailerReceipt(shipmentId: string, payload: ReceiptConfirmPayload): Promise<ShipmentItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/retailer/shipments/${encodeURIComponent(shipmentId)}/confirm-receipt`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to confirm store delivery (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

export async function cancelRetailerRequest(shipmentId: string, payload?: RequestCancelPayload): Promise<ShipmentItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/retailer/requests/${encodeURIComponent(shipmentId)}/cancel`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
      ...authHeaders,
    },
    body: JSON.stringify(payload || {}),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to cancel store replenishment request (HTTP ${response.status})`, response.status, body);
  }
  return body as ShipmentItem;
}

/**
 * Phase 5: Dataset Sources & Data Readiness Service Methods
 */
export async function getDatasetReadiness(): Promise<DatasetReadinessResponse> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/imports/readiness`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to fetch dataset readiness (HTTP ${response.status})`, response.status, body);
  }
  return body as DatasetReadinessResponse;
}

export async function ingestBenchmarkDataset(datasetId: string = 'all', forceReload: boolean = false): Promise<BenchmarkIngestResponse> {
  const authHeaders = await getAuthHeaders();
  const query = new URLSearchParams({
    dataset_id: datasetId,
    force_reload: forceReload ? 'true' : 'false',
  });
  const response = await fetch(`${API_BASE_URL}/imports/benchmarks/ingest?${query.toString()}`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to ingest benchmark dataset (HTTP ${response.status})`, response.status, body);
  }
  return body as BenchmarkIngestResponse;
}

export async function getBenchmarkSourceDetail(sourceId: string): Promise<DatasetSourceItem> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/imports/benchmarks/sources/${encodeURIComponent(sourceId)}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to fetch dataset source detail (HTTP ${response.status})`, response.status, body);
  }
  return body as DatasetSourceItem;
}

// --- System Health & Algorithm Validation Endpoints ---
export async function getSystemValidation(): Promise<SystemValidationReport> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/system-validation`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to fetch system validation report (HTTP ${response.status})`, response.status, body);
  }
  return body as SystemValidationReport;
}

export async function runSystemValidation(): Promise<SystemValidationReport> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(`${API_BASE_URL}/system-validation/run`, {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(body?.detail || `Failed to execute system validation (HTTP ${response.status})`, response.status, body);
  }
  return body as SystemValidationReport;
}

export function getSystemValidationExportUrl(): string {
  return `${API_BASE_URL}/system-validation/export`;
}

export async function exportSystemValidationReport(): Promise<void> {
  const authHeaders = await getAuthHeaders();
  const response = await fetch(getSystemValidationExportUrl(), {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
    },
  });
  if (!response.ok) {
    throw new ApiError(`Failed to export validation report (HTTP ${response.status})`, response.status);
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `stockwise_validation_report_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}
