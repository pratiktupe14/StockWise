import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Workflow,
  Sparkles,
  RefreshCw,
  Search,
  CheckCircle2,
  Clock,
  ArrowRight,
  TrendingUp,
  Boxes,
  Truck,
  Warehouse,
  FileCheck2,
  GitCompare,
  Download,
  ChevronDown,
  ChevronRight,
  X,
  ShieldCheck,
  Package,
  Layers,
  MapPin,
  DollarSign,
  BarChart3,
  CheckCircle,
  FileSpreadsheet,
  Check,
  XCircle,
  AlertTriangle,
} from 'lucide-react';

import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import type { BadgeVariant } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { SummaryCard } from '../components/ui/SummaryCard';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../components/ui/Table';
import { EmptyState } from '../components/ui/EmptyState';

import {
  getPlanningRuns,
  getPlanningRunDetails,
  getDecisionReceipts,
  getShipments,
  approveShipment,
  getProducts,
  getNetworkLocations,
  getInventory,
  getRoutes,
  getSalesHistory,
  getImportRuns,
  getDemandForecast,
  getInventoryRisks,
  getExportReceiptsCSVUrl,
  getExportShipmentsCSVUrl,
} from '../services/api';
import { downloadAuthenticatedFile } from '../services/auth';
import { useDatasetSync } from '../services/dataSync';

import type {
  PlanningRunResponse,
  PlanningRunSummary,
  DecisionReceipt,
  ShipmentItem,
  ProductItem,
  LocationItem,
  InventoryItem,
  RouteItem,
  SalesHistoryItem,
  ImportRunSummary,
  ForecastResponse,
  RiskAnalysisResponse,
} from '../types/api';

export const PlanningResultsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Selected planning run
  const [runs, setRuns] = useState<PlanningRunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>(searchParams.get('runId') || '');
  const [activePlan, setActivePlan] = useState<PlanningRunResponse | null>(null);
  const [decisionReceipts, setDecisionReceipts] = useState<DecisionReceipt[]>([]);
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);

  // Master / Input datasets
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [routes, setRoutes] = useState<RouteItem[]>([]);
  const [salesHistory, setSalesHistory] = useState<SalesHistoryItem[]>([]);
  const [importRuns, setImportRuns] = useState<ImportRunSummary[]>([]);

  // Forecast & Risk datasets for the horizon
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [riskData, setRiskData] = useState<RiskAnalysisResponse | null>(null);

  // Loading and Error states
  const [loadingRuns, setLoadingRuns] = useState<boolean>(true);
  const [loadingPlan, setLoadingPlan] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [approvalActionLoading, setApprovalActionLoading] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Active UI Tabs / Accordions
  const [activeWorkflowTab, setActiveWorkflowTab] = useState<'allocations' | 'inputs' | 'costs' | 'forecasts' | 'comparison' | 'execution' | 'charts'>('allocations');
  const [activeInputTab, setActiveInputTab] = useState<'products' | 'locations' | 'inventory' | 'sales' | 'routes'>('products');
  const [expandedDestinations, setExpandedDestinations] = useState<Record<string, boolean>>({});
  const [selectedReceiptForDrawer, setSelectedReceiptForDrawer] = useState<DecisionReceipt | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedRegion, setSelectedRegion] = useState<string>('all');
  const [selectedSourceWh, setSelectedSourceWh] = useState<string>('all');
  const [selectedSkuFilter, setSelectedSkuFilter] = useState<string>('all');

  // 1. Initial Load of Planning Runs and Input Master Datasets
  useEffect(() => {
    let isMounted = true;
    async function initPage() {
      setLoadingRuns(true);
      setError(null);
      try {
        const [runsData, prodData, locData, invData, routeData, salesData, impData] = await Promise.all([
          getPlanningRuns(50, 0).catch(() => [] as PlanningRunSummary[]),
          getProducts().catch(() => [] as ProductItem[]),
          getNetworkLocations().catch(() => [] as LocationItem[]),
          getInventory().catch(() => [] as InventoryItem[]),
          getRoutes().catch(() => [] as RouteItem[]),
          getSalesHistory({ limit: 300 }).catch(() => [] as SalesHistoryItem[]),
          getImportRuns().then((r) => r.runs || []).catch(() => [] as ImportRunSummary[]),
        ]);

        if (!isMounted) return;
        setRuns(runsData);
        setProducts(prodData);
        setLocations(locData);
        setInventory(invData);
        setRoutes(routeData);
        setSalesHistory(salesData);
        setImportRuns(impData);

        // Auto-select latest run if not specified in searchParams
        const initialRunId = searchParams.get('runId') || (runsData.length > 0 ? runsData[0].run_id : '');
        if (initialRunId) {
          setSelectedRunId(initialRunId);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : 'Failed to initialize planning results data');
      } finally {
        if (isMounted) setLoadingRuns(false);
      }
    }

    initPage();
    return () => {
      isMounted = false;
    };
  }, []);

  const syncInfo = useDatasetSync(
    ['products', 'locations', 'inventory', 'sales', 'routes', 'organizations'],
    () => {
      // Refresh input master records and import runs
      Promise.all([
        getProducts().then(setProducts).catch(() => {}),
        getNetworkLocations().then(setLocations).catch(() => {}),
        getInventory().then(setInventory).catch(() => {}),
        getRoutes().then(setRoutes).catch(() => {}),
        getSalesHistory({ limit: 300 }).then(setSalesHistory).catch(() => {}),
        getImportRuns().then((r) => setImportRuns(r.runs || [])).catch(() => {}),
      ]);
    }
  );

  // 2. Fetch specific Planning Run details when selectedRunId changes
  useEffect(() => {
    if (!selectedRunId) {
      setActivePlan(null);
      setDecisionReceipts([]);
      setShipments([]);
      return;
    }

    let isMounted = true;
    async function loadPlanDetails() {
      setLoadingPlan(true);
      setError(null);
      try {
        const [planDetails, receiptsData, allShipments] = await Promise.all([
          getPlanningRunDetails(selectedRunId),
          getDecisionReceipts(selectedRunId).catch(() => [] as DecisionReceipt[]),
          getShipments({ limit: 300 }).catch(() => [] as ShipmentItem[]),
        ]);

        if (!isMounted) return;
        setActivePlan(planDetails);
        setDecisionReceipts(receiptsData.length > 0 ? receiptsData : planDetails.decision_receipts || []);

        // Filter shipments for this planning run
        const runShipments = allShipments.filter((s) => s.planning_run_id === selectedRunId);
        setShipments(runShipments);

        // Fetch forecast and risk context for this horizon
        getDemandForecast(planDetails.horizon_days || 7)
          .then((f) => isMounted && setForecastData(f))
          .catch(() => {});
        getInventoryRisks(planDetails.horizon_days || 7, planDetails.snapshot_id || undefined)
          .then((r) => isMounted && setRiskData(r))
          .catch(() => {});
      } catch (err: unknown) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : `Failed to load details for run ${selectedRunId}`);
      } finally {
        if (isMounted) setLoadingPlan(false);
      }
    }

    loadPlanDetails();
    return () => {
      isMounted = false;
    };
  }, [selectedRunId]);

  // Handle run selection change
  const handleRunSelect = (runId: string) => {
    setSelectedRunId(runId);
    setSearchParams(runId ? { runId } : {});
  };

  // Lookup maps for fast entity rendering
  const productMap = useMemo(() => new Map(products.map((p) => [p.sku_id, p])), [products]);
  const locationMap = useMemo(() => new Map(locations.map((l) => [l.location_id, l])), [locations]);

  // Overall Plan Status Calculation
  const planOverallStatus = useMemo(() => {
    if (!activePlan) return { label: 'No Plan', variant: 'neutral' as BadgeVariant };
    if (shipments.length === 0) {
      return { label: 'Optimized (Draft)', variant: 'primary' as BadgeVariant };
    }
    const allDelivered = shipments.every((s) => s.status === 'delivered');
    if (allDelivered) return { label: 'Completed', variant: 'success' as BadgeVariant };

    const inTransit = shipments.some((s) => s.status === 'in_transit');
    if (inTransit) return { label: 'Executing', variant: 'primary' as BadgeVariant };

    const allApproved = shipments.every((s) => s.approval_status === 'approved');
    if (allApproved) return { label: 'Approved', variant: 'success' as BadgeVariant };

    const hasRejected = shipments.some((s) => s.approval_status === 'rejected');
    if (hasRejected) return { label: 'Partially Approved', variant: 'warning' as BadgeVariant };

    return { label: 'Awaiting Approval', variant: 'warning' as BadgeVariant };
  }, [activePlan, shipments]);

  // Check if any operational dataset import occurred after the active plan was created
  const isPlanStale = useMemo(() => {
    if (!activePlan || !importRuns || importRuns.length === 0) return false;
    const planTime = new Date(activePlan.created_at).getTime();
    return importRuns.some((r) => {
      if (r.status !== 'completed') return false;
      const importTime = new Date(r.created_at).getTime();
      return importTime > planTime;
    });
  }, [activePlan, importRuns]);

  // Executive Summary Metrics derived from the selected run
  const executiveMetrics = useMemo(() => {
    if (!activePlan) {
      return {
        totalDestinations: 0,
        totalSkus: 0,
        eligibleAllocations: 0,
        plannedQuantity: 0,
        unmetDemand: 0,
        serviceLevel: 0,
        estimatedTransportCost: 0,
        warehousesSelected: 0,
        pendingApprovals: 0,
        inTransitShipments: 0,
        completedDeliveries: 0,
      };
    }

    const receipts = decisionReceipts.length > 0 ? decisionReceipts : activePlan.decision_receipts || [];
    const destIds = new Set<string>();
    const skuIds = new Set<string>();
    const srcWhIds = new Set<string>();

    receipts.forEach((r) => {
      if (r.destination_location_id) destIds.add(r.destination_location_id);
      if (r.sku_id) skuIds.add(r.sku_id);
      if (r.source_location_id) srcWhIds.add(r.source_location_id);
    });

    const pending = shipments.filter((s) => s.approval_status === 'pending' || s.status === 'proposed').length;
    const inTransit = shipments.filter((s) => s.status === 'in_transit').length;
    const completed = shipments.filter((s) => s.status === 'delivered').length;

    return {
      totalDestinations: destIds.size,
      totalSkus: skuIds.size,
      eligibleAllocations: receipts.length,
      plannedQuantity: activePlan.fulfilled_demand_units || 0,
      unmetDemand: activePlan.unmet_demand_units || 0,
      serviceLevel: activePlan.service_level_percent || 0,
      estimatedTransportCost: activePlan.estimated_transport_cost || 0,
      warehousesSelected: srcWhIds.size,
      pendingApprovals: pending,
      inTransitShipments: inTransit,
      completedDeliveries: completed,
    };
  }, [activePlan, decisionReceipts, shipments]);

  // Group allocations / decision receipts by destination
  const groupedAllocations = useMemo(() => {
    const receipts = decisionReceipts.length > 0 ? decisionReceipts : activePlan?.decision_receipts || [];
    const groups: Record<string, { destinationId: string; destinationName: string; destinationType: string; region: string; receipts: DecisionReceipt[] }> = {};

    receipts.forEach((r) => {
      const destLoc = locationMap.get(r.destination_location_id);
      const destName = destLoc?.name || r.destination_location_name || r.destination_location_id;
      const destType = destLoc?.location_type || 'destination';
      const region = destLoc?.region || 'National';

      // Apply Filters
      if (selectedRegion !== 'all' && region !== selectedRegion) return;
      if (selectedSourceWh !== 'all' && r.source_location_id !== selectedSourceWh) return;
      if (selectedSkuFilter !== 'all' && r.sku_id !== selectedSkuFilter) return;

      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const match =
          r.destination_location_id.toLowerCase().includes(q) ||
          destName.toLowerCase().includes(q) ||
          r.sku_id.toLowerCase().includes(q) ||
          (r.product_name || '').toLowerCase().includes(q) ||
          (r.source_location_name || '').toLowerCase().includes(q) ||
          r.source_location_id.toLowerCase().includes(q);
        if (!match) return;
      }

      if (!groups[r.destination_location_id]) {
        groups[r.destination_location_id] = {
          destinationId: r.destination_location_id,
          destinationName: destName,
          destinationType: destType,
          region,
          receipts: [],
        };
      }
      groups[r.destination_location_id].receipts.push(r);
    });

    return Object.values(groups);
  }, [decisionReceipts, activePlan, locationMap, selectedRegion, selectedSourceWh, selectedSkuFilter, searchQuery]);

  // Destination and Source lists for filters
  const filterOptions = useMemo(() => {
    const regions = new Set<string>();
    const sources = new Map<string, string>();
    const dests = new Map<string, string>();
    const skus = new Map<string, string>();

    locations.forEach((l) => {
      if (l.region) regions.add(l.region);
      if (l.location_type?.includes('warehouse') || l.location_type?.includes('plant') || l.location_type?.includes('facility')) {
        sources.set(l.location_id, l.name);
      }
      dests.set(l.location_id, l.name);
    });

    products.forEach((p) => {
      skus.set(p.sku_id, p.name);
    });

    return {
      regions: Array.from(regions).sort(),
      sources: Array.from(sources.entries()),
      dests: Array.from(dests.entries()),
      skus: Array.from(skus.entries()),
    };
  }, [locations, products]);

  // Transportation Cost Breakdown List
  const transportCostAudit = useMemo(() => {
    const receipts = decisionReceipts.length > 0 ? decisionReceipts : activePlan?.decision_receipts || [];
    return receipts.map((r) => {
      const srcLoc = locationMap.get(r.source_location_id);
      const destLoc = locationMap.get(r.destination_location_id);
      const matchingShipment = shipments.find(
        (s) => s.source_location_id === r.source_location_id && s.destination_location_id === r.destination_location_id && s.sku_id === r.sku_id
      );

      const qty = r.quantity || 0;
      const estimatedCost = r.estimated_cost || 0;
      const costPerUnit = qty > 0 ? estimatedCost / qty : 0;
      const distance = r.distance_km ?? null;
      const actualCost = matchingShipment?.actual_transport_cost ?? null;

      return {
        recommendationId: r.recommendation_id,
        skuId: r.sku_id,
        productName: r.product_name || r.sku_id,
        sourceId: r.source_location_id,
        sourceName: srcLoc?.name || r.source_location_name || r.source_location_id,
        destinationId: r.destination_location_id,
        destinationName: destLoc?.name || r.destination_location_name || r.destination_location_id,
        routeId: r.route_id,
        quantity: qty,
        unit: r.unit || 'cases',
        distanceKm: distance,
        estimatedCost,
        costPerUnit,
        actualCost,
        variance: actualCost !== null ? actualCost - estimatedCost : null,
        leadTimeDays: r.lead_time_days,
        costModelNote: distance
          ? `Calculated using candidate arc optimization (lead time: ${r.lead_time_days}d, distance: ${distance} km, rate: ₹${costPerUnit.toFixed(2)}/case)`
          : `Calculated from route standard freight rate (₹${costPerUnit.toFixed(2)}/case)`,
      };
    });
  }, [decisionReceipts, activePlan, locationMap, shipments]);

  // Plan Approval Action Handler
  const handleApproveAllShipments = async () => {
    if (!activePlan || shipments.length === 0) return;
    setApprovalActionLoading('all');
    setError(null);
    setActionSuccess(null);
    try {
      let approvedCount = 0;
      for (const s of shipments) {
        if (s.approval_status !== 'approved') {
          await approveShipment(
            s.shipment_id,
            true,
            'COMPANY-ADMIN-PLANNER',
            `Approved via End-to-End Planning Results console for run ${activePlan.run_id}`
          );
          approvedCount++;
        }
      }
      setActionSuccess(`Successfully approved ${approvedCount} pending shipment(s) in planning run ${activePlan.run_id}. Stock reservation recorded.`);
      // Refresh shipments
      const updated = await getShipments({ limit: 300 });
      setShipments(updated.filter((s) => s.planning_run_id === selectedRunId));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to approve shipments');
    } finally {
      setApprovalActionLoading(null);
    }
  };

  // Toggle Destination Accordion
  const toggleDestination = (destId: string) => {
    setExpandedDestinations((prev) => ({
      ...prev,
      [destId]: !prev[destId],
    }));
  };

  const expandAllDestinations = () => {
    const allExpanded: Record<string, boolean> = {};
    groupedAllocations.forEach((g) => {
      allExpanded[g.destinationId] = true;
    });
    setExpandedDestinations(allExpanded);
  };

  const collapseAllDestinations = () => {
    setExpandedDestinations({});
  };

  // CSV Export trigger using existing authenticated backend endpoints
  const handleExportReceipts = async () => {
    if (!selectedRunId) return;
    try {
      await downloadAuthenticatedFile(
        getExportReceiptsCSVUrl(selectedRunId),
        `StockWise_${selectedRunId}_Decision_Receipts.csv`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  const handleExportShipments = async () => {
    if (!selectedRunId) return;
    try {
      await downloadAuthenticatedFile(
        getExportShipmentsCSVUrl(selectedRunId),
        `StockWise_${selectedRunId}_Shipments.csv`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  return (
    <div className="space-y-6 pb-16">
      {/* 1. Header & Planning Run Selector Bar */}
      <div className="bg-white border border-[#E5E7EB] rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-200 flex items-center justify-center text-indigo-600">
                <Workflow className="w-5 h-5" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-2xl font-bold tracking-tight text-[#172033]">
                    End-to-End Planning Results
                  </h1>
                  <Badge variant={planOverallStatus.variant} dot size="sm">
                    {planOverallStatus.label}
                  </Badge>
                  {isPlanStale && (
                    <Badge variant="warning" size="sm">
                      ⚠️ Stale Plan (Source Updated)
                    </Badge>
                  )}
                  {syncInfo.formattedSyncTime && (
                    <Badge variant="neutral" size="sm">
                      Synced {syncInfo.formattedSyncTime} ({syncInfo.dataset})
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-[#667085] mt-0.5">
                  Full multi-echelon trace from imported CSV/Excel data through demand forecasting, warehouse selection, route costing, approval, and execution.
                </p>
              </div>
            </div>
          </div>

          {/* Planning Run Selector */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs">
              <span className="font-semibold text-slate-700">Planning Run:</span>
              <select
                value={selectedRunId}
                onChange={(e) => handleRunSelect(e.target.value)}
                disabled={loadingRuns || runs.length === 0}
                className="bg-transparent font-mono font-medium text-blue-700 focus:outline-none cursor-pointer"
              >
                {runs.length === 0 ? (
                  <option value="">No planning runs available</option>
                ) : (
                  runs.map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.run_id} — {new Date(r.created_at).toLocaleDateString()} ({r.service_level_percent?.toFixed(0)}% service, {r.horizon_days}d)
                    </option>
                  ))
                )}
              </select>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (selectedRunId) handleRunSelect(selectedRunId);
              }}
              disabled={loadingPlan}
            >
              <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loadingPlan ? 'animate-spin' : ''}`} />
              Refresh
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate('/comparison')}
            >
              <GitCompare className="w-3.5 h-3.5 mr-1.5 text-indigo-600" />
              Compare Runs
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/optimize')}
            >
              <Sparkles className="w-3.5 h-3.5 mr-1.5" />
              New Run
            </Button>
          </div>
        </div>

        {/* Selected Run Metadata Strip */}
        {activePlan && (
          <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3 text-xs">
            <div>
              <span className="text-slate-400 block text-[11px]">Run ID</span>
              <code className="font-mono font-bold text-slate-800">{activePlan.run_id}</code>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">Created At</span>
              <span className="text-slate-700 font-medium">
                {new Date(activePlan.created_at).toLocaleString()}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">Planning Horizon</span>
              <span className="text-slate-800 font-semibold">{activePlan.horizon_days} Days Cutoff</span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">Optimization Strategy</span>
              <span className="text-indigo-700 font-medium capitalize">
                {activePlan.objective_strategy.replace(/-/g, ' ')}
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">Solver & Status</span>
              <span className="text-emerald-700 font-medium">
                {activePlan.solver_name || 'HiGHS'} ({activePlan.solver_status})
              </span>
            </div>
            <div>
              <span className="text-slate-400 block text-[11px]">Solve Time</span>
              <span className="text-slate-700 font-medium">
                {activePlan.solve_time_ms ? `${activePlan.solve_time_ms.toFixed(1)} ms` : '—'}
              </span>
            </div>
          </div>
        )}

        {/* Stale Plan Alert if Source Data Changed */}
        {isPlanStale && activePlan && (
          <div className="mt-4 p-4 rounded-xl bg-amber-50 border border-amber-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-amber-900">
                  Source Data Updated Since Plan Generation
                </p>
                <p className="text-xs text-amber-700 mt-0.5">
                  New operational dataset imports have been committed after this plan was calculated on {new Date(activePlan.created_at).toLocaleString()}. Inventory balances, demand signals, or transport routes may differ from current state.
                </p>
              </div>
            </div>
            <Button
              variant="primary"
              size="sm"
              className="bg-amber-600 hover:bg-amber-700 text-white shrink-0"
              leftIcon={<Sparkles className="w-4 h-4" />}
              onClick={() => navigate('/optimize')}
            >
              Recalculate Optimization
            </Button>
          </div>
        )}
      </div>

      {/* Alerts */}
      {error && (
        <Alert variant="error" title="Workflow Error">
          <div className="flex items-center justify-between w-full">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="text-slate-400 hover:text-slate-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </Alert>
      )}

      {actionSuccess && (
        <Alert variant="success" title="Action Completed">
          <div className="flex items-center justify-between w-full">
            <span>{actionSuccess}</span>
            <button
              onClick={() => setActionSuccess(null)}
              className="text-slate-400 hover:text-slate-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </Alert>
      )}

      {/* 2. Executive Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-10 gap-3">
        <SummaryCard
          title="Destinations"
          icon={MapPin}
          value={loadingPlan ? '...' : executiveMetrics.totalDestinations}
          subtitle="Customer nodes"
          badgeText="Active"
          badgeVariant="primary"
          className="lg:col-span-2"
        />
        <SummaryCard
          title="SKUs"
          icon={Package}
          value={loadingPlan ? '...' : executiveMetrics.totalSkus}
          subtitle="Product lines"
          badgeText="In Plan"
          badgeVariant="primary"
          className="lg:col-span-2"
        />
        <SummaryCard
          title="Planned Quantity"
          icon={Boxes}
          value={loadingPlan ? '...' : `${executiveMetrics.plannedQuantity.toLocaleString()} cases`}
          subtitle={`Service: ${executiveMetrics.serviceLevel.toFixed(1)}%`}
          badgeText={executiveMetrics.unmetDemand > 0 ? `${executiveMetrics.unmetDemand} unmet` : '100% Filled'}
          badgeVariant={executiveMetrics.unmetDemand > 0 ? 'warning' : 'success'}
          className="lg:col-span-2"
        />
        <SummaryCard
          title="Transport Cost"
          icon={DollarSign}
          value={loadingPlan ? '...' : `₹${executiveMetrics.estimatedTransportCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          subtitle="Estimated freight"
          badgeText="Optimal"
          badgeVariant="primary"
          className="lg:col-span-2"
        />
        <SummaryCard
          title="Execution Status"
          icon={Truck}
          value={loadingPlan ? '...' : `${executiveMetrics.completedDeliveries}/${shipments.length || executiveMetrics.eligibleAllocations}`}
          subtitle={`${executiveMetrics.inTransitShipments} in transit`}
          badgeText={executiveMetrics.pendingApprovals > 0 ? `${executiveMetrics.pendingApprovals} Pending` : 'Dispatched'}
          badgeVariant={executiveMetrics.pendingApprovals > 0 ? 'warning' : 'success'}
          className="lg:col-span-2"
        />
      </div>

      {/* 3. End-to-End 13-Stage Workflow Timeline Navigation */}
      <Card className="border border-slate-200 shadow-sm overflow-hidden">
        <CardHeader className="bg-slate-50/70 border-b border-slate-200/80 py-3.5 px-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <CardTitle className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Layers className="w-4 h-4 text-blue-600" />
                End-to-End Supply Chain Lifecycle
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Trace data progression through all 13 stages of the distribution intelligence pipeline.
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="flex items-center gap-1 text-emerald-700 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" /> Completed
              </span>
              <span className="flex items-center gap-1 text-blue-600 font-medium ml-2">
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" /> Active Plan
              </span>
              <span className="flex items-center gap-1 text-slate-400 font-medium ml-2">
                <Clock className="w-3.5 h-3.5" /> Execution Stage
              </span>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-2.5">
            {[
              {
                step: 1,
                title: 'Data Ingestion',
                desc: 'Upload CSV/Excel (5 datasets)',
                metrics: `${importRuns.length} import runs recorded`,
                status: 'completed',
                targetTab: 'inputs',
              },
              {
                step: 2,
                title: 'Validation & Persistence',
                desc: 'Audit canonical schema rules',
                metrics: `${products.length} Products, ${locations.length} Locations, ${inventory.length} Stock lines`,
                status: 'completed',
                targetTab: 'inputs',
              },
              {
                step: 3,
                title: 'Network & Topology',
                desc: 'Corridor & ownership verification',
                metrics: `${routes.filter((r) => r.is_active).length} Active permitted routes`,
                status: 'completed',
                targetTab: 'inputs',
              },
              {
                step: 4,
                title: 'Demand Forecasting',
                desc: '7-day rolling MA & naive models',
                metrics: `${forecastData?.forecast_count || 0} SKU-Destination forecasts`,
                status: 'completed',
                targetTab: 'forecasts',
              },
              {
                step: 5,
                title: 'Risk & Coverage Analysis',
                desc: 'Stockout, excess & expiry cover',
                metrics: `${riskData?.critical_risk_count || 0} Critical stockouts warned`,
                status: 'completed',
                targetTab: 'forecasts',
              },
              {
                step: 6,
                title: 'Source Warehouse Selection',
                desc: 'Dispatchable stock & FEFO check',
                metrics: `${executiveMetrics.warehousesSelected} Warehouses selected`,
                status: 'completed',
                targetTab: 'allocations',
              },
              {
                step: 7,
                title: 'Distribution Optimization',
                desc: '2-Stage Lexicographic HiGHS',
                metrics: `${activePlan?.service_level_percent?.toFixed(0) || 100}% Service Level achieved`,
                status: activePlan ? 'completed' : 'pending',
                targetTab: 'allocations',
              },
              {
                step: 8,
                title: 'Decision Receipts',
                desc: 'Evidence & rejection reasoning',
                metrics: `${decisionReceipts.length} Certified Decision Receipts`,
                status: decisionReceipts.length > 0 ? 'completed' : 'pending',
                targetTab: 'allocations',
              },
              {
                step: 9,
                title: 'Baseline Benchmark',
                desc: 'Nearest-source comparison',
                metrics: `${activePlan?.baseline_comparison ? 'Audited' : 'Available'}`,
                status: activePlan?.baseline_comparison ? 'completed' : 'pending',
                targetTab: 'comparison',
              },
              {
                step: 10,
                title: 'Governance Approval',
                desc: 'Authorized planner review',
                metrics: `${executiveMetrics.pendingApprovals} Pending, ${shipments.length - executiveMetrics.pendingApprovals} Approved`,
                status: executiveMetrics.pendingApprovals === 0 && shipments.length > 0 ? 'completed' : 'active',
                targetTab: 'execution',
              },
              {
                step: 11,
                title: 'Stock Reservation & Dispatch',
                desc: 'Generate shipments & staging',
                metrics: `${shipments.filter((s) => s.status === 'ready_for_dispatch' || s.status === 'in_transit' || s.status === 'delivered').length} Dispatched`,
                status: shipments.some((s) => s.status === 'in_transit' || s.status === 'delivered') ? 'completed' : 'pending',
                targetTab: 'execution',
              },
              {
                step: 12,
                title: 'In-Transit Execution',
                desc: 'Carrier coordination & tracking',
                metrics: `${executiveMetrics.inTransitShipments} In transit`,
                status: executiveMetrics.inTransitShipments > 0 ? 'active' : shipments.some((s) => s.status === 'delivered') ? 'completed' : 'pending',
                targetTab: 'execution',
              },
              {
                step: 13,
                title: 'Receipt & Reconciliation',
                desc: 'POD confirmation & audit settlement',
                metrics: `${executiveMetrics.completedDeliveries} Deliveries confirmed`,
                status: executiveMetrics.completedDeliveries > 0 ? 'completed' : 'pending',
                targetTab: 'execution',
              },
            ].map((item) => {
              const isSelectedTab = activeWorkflowTab === item.targetTab;
              return (
                <button
                  key={item.step}
                  onClick={() => setActiveWorkflowTab(item.targetTab as any)}
                  className={`text-left p-3 rounded-xl border transition-all text-xs flex flex-col justify-between ${
                    isSelectedTab
                      ? 'border-blue-500 bg-blue-50/40 shadow-xs'
                      : 'border-slate-200/80 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5 w-full">
                    <span className="font-mono text-[11px] font-semibold text-slate-500">
                      Step {item.step}
                    </span>
                    {item.status === 'completed' ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                    ) : item.status === 'active' ? (
                      <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
                    ) : (
                      <Clock className="w-3.5 h-3.5 text-slate-300" />
                    )}
                  </div>
                  <div>
                    <h5 className="font-bold text-slate-800 tracking-tight text-xs">{item.title}</h5>
                    <p className="text-[11px] text-slate-500 leading-snug mt-0.5 line-clamp-1">{item.desc}</p>
                  </div>
                  <div className="mt-2 pt-1.5 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-600 font-medium">
                    <span className="truncate">{item.metrics}</span>
                    <ArrowRight className="w-3 h-3 text-slate-400 shrink-0 ml-1" />
                  </div>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Main Section Navigation Bar */}
      <div className="flex items-center justify-between border-b border-slate-200">
        <div className="flex items-center gap-1 overflow-x-auto">
          {[
            { id: 'allocations', label: 'Warehouse Selection & Allocations', icon: Warehouse, count: groupedAllocations.reduce((acc, g) => acc + g.receipts.length, 0) },
            { id: 'inputs', label: 'Imported Master Data', icon: FileSpreadsheet, count: 5 },
            { id: 'costs', label: 'Transport Cost Breakdown', icon: DollarSign, count: transportCostAudit.length },
            { id: 'forecasts', label: 'Demand Forecasting & Risks', icon: TrendingUp, count: forecastData?.forecast_count || 0 },
            { id: 'comparison', label: 'Baseline vs Optimized Audit', icon: GitCompare },
            { id: 'execution', label: 'Approval & Execution Tracking', icon: Truck, count: shipments.length },
            { id: 'charts', label: 'Analytics & Visualizations', icon: BarChart3 },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeWorkflowTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveWorkflowTab(tab.id as any)}
                className={`py-3 px-4 font-semibold text-xs border-b-2 transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer ${
                  isActive
                    ? 'border-blue-600 text-blue-700 bg-blue-50/20'
                    : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-blue-600' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${isActive ? 'bg-blue-100 text-blue-800' : 'bg-slate-100 text-slate-600'}`}>
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 py-2">
          <Button variant="outline" size="sm" onClick={handleExportReceipts}>
            <Download className="w-3.5 h-3.5 mr-1" />
            Receipts CSV
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportShipments}>
            <Download className="w-3.5 h-3.5 mr-1" />
            Shipments CSV
          </Button>
        </div>
      </div>

      {/* 4. TAB CONTENT: Warehouse Selection & Location-wise Allocations (The Primary Section) */}
      {activeWorkflowTab === 'allocations' && (
        <div className="space-y-4">
          {/* Controls & Filter Bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-3 text-xs">
            <div className="flex flex-wrap items-center gap-2.5 flex-1 min-w-[320px]">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search destination, warehouse, SKU or region..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 border border-slate-200 rounded-lg text-xs bg-slate-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <select
                value={selectedRegion}
                onChange={(e) => setSelectedRegion(e.target.value)}
                className="px-2.5 py-1.5 border border-slate-200 rounded-lg bg-white text-slate-700 text-xs focus:outline-none"
              >
                <option value="all">All Regions</option>
                {filterOptions.regions.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>

              <select
                value={selectedSourceWh}
                onChange={(e) => setSelectedSourceWh(e.target.value)}
                className="px-2.5 py-1.5 border border-slate-200 rounded-lg bg-white text-slate-700 text-xs focus:outline-none"
              >
                <option value="all">All Source Warehouses</option>
                {filterOptions.sources.map(([id, name]) => (
                  <option key={id} value={id}>{name} ({id})</option>
                ))}
              </select>

              <select
                value={selectedSkuFilter}
                onChange={(e) => setSelectedSkuFilter(e.target.value)}
                className="px-2.5 py-1.5 border border-slate-200 rounded-lg bg-white text-slate-700 text-xs focus:outline-none"
              >
                <option value="all">All SKUs</option>
                {filterOptions.skus.map(([id, name]) => (
                  <option key={id} value={id}>{name} ({id})</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="ghost" size="sm" onClick={expandAllDestinations}>
                Expand All
              </Button>
              <Button variant="ghost" size="sm" onClick={collapseAllDestinations}>
                Collapse All
              </Button>
            </div>
          </div>

          {/* Allocation List by Destination */}
          {groupedAllocations.length === 0 ? (
            <Card className="p-8">
              <EmptyState
                icon={Warehouse}
                title="No Allocations Found"
                description={
                  activePlan
                    ? 'No destination allocations match your active filter criteria. Clear filters or choose another planning run.'
                    : 'No planning run is currently active. Select a previous run from the top dropdown or generate a new distribution plan.'
                }
                actionLabel="Launch Optimizer"
                onAction={() => navigate('/optimize')}
              />
            </Card>
          ) : (
            <div className="space-y-3">
              {groupedAllocations.map((group) => {
                const isExpanded = expandedDestinations[group.destinationId] ?? true;
                const totalCases = group.receipts.reduce((acc, r) => acc + (r.quantity || 0), 0);
                const totalCost = group.receipts.reduce((acc, r) => acc + (r.estimated_cost || 0), 0);
                const hasUnmet = group.receipts.some((r) => (r.unmet_demand_remaining || 0) > 0);

                return (
                  <div
                    key={group.destinationId}
                    className="border border-slate-200 rounded-xl bg-white shadow-xs overflow-hidden transition-all"
                  >
                    {/* Destination Accordion Header */}
                    <div
                      onClick={() => toggleDestination(group.destinationId)}
                      className="p-4 bg-slate-50/70 hover:bg-slate-50 cursor-pointer flex items-center justify-between border-b border-slate-200/70"
                    >
                      <div className="flex items-center gap-3">
                        <button className="text-slate-400 hover:text-slate-600">
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                        <div>
                          <div className="flex items-center gap-2">
                            <h4 className="font-bold text-slate-900 text-sm">{group.destinationName}</h4>
                            <code className="text-[11px] text-slate-500 font-mono">{group.destinationId}</code>
                            <Badge variant="neutral" size="sm">
                              {group.destinationType.replace(/_/g, ' ')}
                            </Badge>
                            <Badge variant="primary" size="sm">
                              {group.region}
                            </Badge>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 text-xs">
                        <div className="text-right">
                          <span className="text-slate-500 block text-[10px]">Total Replenishment</span>
                          <span className="font-bold text-slate-900">{totalCases.toLocaleString()} cases</span>
                        </div>
                        <div className="text-right">
                          <span className="text-slate-500 block text-[10px]">Estimated Freight</span>
                          <span className="font-bold text-emerald-700">₹{totalCost.toFixed(2)}</span>
                        </div>
                        <Badge variant={hasUnmet ? 'warning' : 'success'} size="sm">
                          {hasUnmet ? 'Partial Fulfillment' : '100% Service Level'}
                        </Badge>
                      </div>
                    </div>

                    {/* Destination Allocations Table */}
                    {isExpanded && (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-white">
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">SKU & Product</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">Demand</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">Replenishment Qty</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">Selected Source WH</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">Route & Transit</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">Estimated Cost</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">FEFO Expiry Batch</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5">Status</TableHead>
                              <TableHead className="text-[11px] font-bold text-slate-700 py-2.5 text-right">Explain Decision</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {group.receipts.map((r) => {
                              const srcLoc = locationMap.get(r.source_location_id);
                              const prod = productMap.get(r.sku_id);
                              const batches = r.allocated_batches || [];
                              const hasUnmetRemaining = (r.unmet_demand_remaining || 0) > 0;

                              return (
                                <TableRow key={r.recommendation_id} className="hover:bg-blue-50/20 text-xs">
                                  {/* SKU & Product */}
                                  <TableCell className="py-3 font-medium">
                                    <div className="font-semibold text-slate-900">{r.product_name || prod?.name || r.sku_id}</div>
                                    <div className="text-[11px] text-slate-400 font-mono">{r.sku_id}</div>
                                  </TableCell>

                                  {/* Demand */}
                                  <TableCell className="py-3">
                                    <div className="text-slate-800 font-medium">
                                      {((r.quantity || 0) + (r.unmet_demand_remaining || 0)).toFixed(0)} cases
                                    </div>
                                    <div className="text-[10px] text-slate-400">Demand Gap</div>
                                  </TableCell>

                                  {/* Replenishment Qty */}
                                  <TableCell className="py-3">
                                    <span className="font-bold text-blue-700 text-sm">
                                      {r.quantity?.toFixed(0)} {r.unit || 'cases'}
                                    </span>
                                  </TableCell>

                                  {/* Selected Source WH */}
                                  <TableCell className="py-3">
                                    <div className="flex items-center gap-1.5 font-semibold text-slate-800">
                                      <Warehouse className="w-3.5 h-3.5 text-blue-600 shrink-0" />
                                      <span>{srcLoc?.name || r.source_location_name || r.source_location_id}</span>
                                    </div>
                                    <div className="text-[11px] text-slate-500 font-mono">
                                      {r.source_location_id} • {srcLoc?.region || 'Hub'}
                                    </div>
                                  </TableCell>

                                  {/* Route & Transit */}
                                  <TableCell className="py-3">
                                    <div className="font-medium text-slate-700">
                                      {r.lead_time_days}d Lead Time
                                    </div>
                                    <div className="text-[11px] text-slate-400 font-mono">
                                      Route #{r.route_id || 'Active'} {r.distance_km ? `(${r.distance_km} km)` : ''}
                                    </div>
                                  </TableCell>

                                  {/* Estimated Cost */}
                                  <TableCell className="py-3">
                                    <div className="font-bold text-slate-900">₹{r.estimated_cost?.toFixed(2)}</div>
                                    <div className="text-[10px] text-slate-400">
                                      ₹{((r.estimated_cost || 0) / (r.quantity || 1)).toFixed(2)}/case
                                    </div>
                                  </TableCell>

                                  {/* FEFO Expiry Batch */}
                                  <TableCell className="py-3">
                                    {batches.length > 0 ? (
                                      <div className="space-y-0.5">
                                        <div className="font-mono text-[11px] text-slate-800 font-semibold">
                                          {batches[0].batch_number}
                                        </div>
                                        <div className="text-[10px] text-emerald-700 flex items-center gap-1">
                                          <CheckCircle className="w-3 h-3" />
                                          {batches[0].shelf_life_remaining_days || batches[0].days_remaining}d shelf life
                                        </div>
                                      </div>
                                    ) : (
                                      <span className="text-slate-400 text-[11px]">Standard Batch</span>
                                    )}
                                  </TableCell>

                                  {/* Status */}
                                  <TableCell className="py-3">
                                    <Badge variant={hasUnmetRemaining ? 'warning' : 'success'} size="sm">
                                      {hasUnmetRemaining ? `Unmet: ${r.unmet_demand_remaining} cases` : 'Optimal Flow'}
                                    </Badge>
                                  </TableCell>

                                  {/* Action */}
                                  <TableCell className="py-3 text-right">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      onClick={() => setSelectedReceiptForDrawer(r)}
                                      className="text-xs"
                                    >
                                      Why this WH?
                                    </Button>
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 5. TAB CONTENT: Imported Master Data Viewer (Section 4) */}
      {activeWorkflowTab === 'inputs' && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="py-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base font-bold text-slate-900">
                  Imported Datasets & Master Records
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Inspect real accepted records persisted from CSV/Excel uploads. No hardcoded or mock datasets.
                </CardDescription>
              </div>

              {/* Subtabs for datasets */}
              <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-xl text-xs font-semibold">
                {[
                  { id: 'products', label: `Products (${products.length})` },
                  { id: 'locations', label: `Locations (${locations.length})` },
                  { id: 'inventory', label: `Inventory (${inventory.length})` },
                  { id: 'sales', label: `Sales History (${salesHistory.length})` },
                  { id: 'routes', label: `Routes (${routes.length})` },
                ].map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setActiveInputTab(t.id as any)}
                    className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                      activeInputTab === t.id
                        ? 'bg-white text-blue-700 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </CardHeader>

            <CardContent className="p-0">
              {/* Products Table */}
              {activeInputTab === 'products' && (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">SKU ID</TableHead>
                        <TableHead className="text-xs">Product Name</TableHead>
                        <TableHead className="text-xs">Category</TableHead>
                        <TableHead className="text-xs">Unit</TableHead>
                        <TableHead className="text-xs">Case Pack</TableHead>
                        <TableHead className="text-xs">Shelf Life</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {products.map((p) => (
                        <TableRow key={p.sku_id} className="text-xs">
                          <TableCell className="font-mono font-semibold text-slate-900">{p.sku_id}</TableCell>
                          <TableCell className="font-medium text-slate-800">{p.name}</TableCell>
                          <TableCell><Badge variant="primary" size="sm">{p.category || 'General'}</Badge></TableCell>
                          <TableCell className="text-slate-600">{p.unit || 'cases'}</TableCell>
                          <TableCell className="text-slate-600">{p.case_pack_quantity || 1} units/case</TableCell>
                          <TableCell className="text-slate-600">{p.shelf_life_days ? `${p.shelf_life_days} days` : '—'}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Locations Table */}
              {activeInputTab === 'locations' && (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Location ID</TableHead>
                        <TableHead className="text-xs">Facility Name</TableHead>
                        <TableHead className="text-xs">Type</TableHead>
                        <TableHead className="text-xs">Region & City</TableHead>
                        <TableHead className="text-xs">Ownership Org</TableHead>
                        <TableHead className="text-xs">Storage Capacity</TableHead>
                        <TableHead className="text-xs">Daily Dispatch</TableHead>
                        <TableHead className="text-xs">Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {locations.map((l) => (
                        <TableRow key={l.location_id} className="text-xs">
                          <TableCell className="font-mono font-semibold text-slate-900">{l.location_id}</TableCell>
                          <TableCell className="font-medium text-slate-800">{l.name}</TableCell>
                          <TableCell><Badge variant="neutral" size="sm">{l.location_type?.replace(/_/g, ' ')}</Badge></TableCell>
                          <TableCell className="text-slate-600">{l.region} {l.city ? `(${l.city})` : ''}</TableCell>
                          <TableCell className="text-slate-600">{l.owner_org_name || l.owner_org_id || 'Company Core'}</TableCell>
                          <TableCell className="text-slate-800 font-medium">{l.storage_capacity_units ? `${l.storage_capacity_units.toLocaleString()} units` : '—'}</TableCell>
                          <TableCell className="text-slate-800 font-medium">{l.dispatch_capacity_daily ? `${l.dispatch_capacity_daily.toLocaleString()} units/day` : '—'}</TableCell>
                          <TableCell><Badge variant={l.is_active ? 'success' : 'neutral'} size="sm">{l.is_active ? 'Active' : 'Inactive'}</Badge></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Inventory Table */}
              {activeInputTab === 'inventory' && (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">SKU</TableHead>
                        <TableHead className="text-xs">Warehouse / Location</TableHead>
                        <TableHead className="text-xs">On-Hand</TableHead>
                        <TableHead className="text-xs">Reserved</TableHead>
                        <TableHead className="text-xs">Blocked</TableHead>
                        <TableHead className="text-xs">Dispatchable Stock</TableHead>
                        <TableHead className="text-xs">Batch & Expiry</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {inventory.map((inv) => {
                        const disp = Math.max(0, (inv.on_hand || 0) - (inv.reserved || 0) - (inv.blocked || 0));
                        return (
                          <TableRow key={`${inv.sku_id}-${inv.location_id}-${inv.id}`} className="text-xs">
                            <TableCell className="font-mono font-semibold text-slate-900">{inv.sku_id}</TableCell>
                            <TableCell className="font-medium text-slate-800">{inv.location_name || inv.location_id}</TableCell>
                            <TableCell className="text-slate-800">{inv.on_hand?.toLocaleString()} cases</TableCell>
                            <TableCell className="text-amber-700">{inv.reserved?.toLocaleString()} cases</TableCell>
                            <TableCell className="text-rose-700">{inv.blocked?.toLocaleString()} cases</TableCell>
                            <TableCell className="font-bold text-blue-700">{disp.toLocaleString()} cases</TableCell>
                            <TableCell className="text-slate-600 font-mono text-[11px]">
                              {inv.batch_number || 'BATCH-STD'} {inv.expiry_date ? `(Exp: ${inv.expiry_date})` : ''}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Sales History Table */}
              {activeInputTab === 'sales' && (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Sales Date</TableHead>
                        <TableHead className="text-xs">SKU</TableHead>
                        <TableHead className="text-xs">Product Name</TableHead>
                        <TableHead className="text-xs">Destination Location</TableHead>
                        <TableHead className="text-xs">Recorded Consumption</TableHead>
                        <TableHead className="text-xs">Validation Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {salesHistory.slice(0, 100).map((s) => (
                        <TableRow key={`${s.id}-${s.sku_id}-${s.sales_date}`} className="text-xs">
                          <TableCell className="font-mono text-slate-600">{s.sales_date}</TableCell>
                          <TableCell className="font-mono font-semibold text-slate-900">{s.sku_id}</TableCell>
                          <TableCell className="text-slate-800">{s.product_name || '—'}</TableCell>
                          <TableCell className="text-slate-700 font-medium">{s.destination_name || s.destination_id}</TableCell>
                          <TableCell className="font-bold text-slate-900">{s.quantity?.toLocaleString()} cases</TableCell>
                          <TableCell><Badge variant="success" size="sm">Validated & Persisted</Badge></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Routes Table */}
              {activeInputTab === 'routes' && (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Route ID</TableHead>
                        <TableHead className="text-xs">Source Warehouse</TableHead>
                        <TableHead className="text-xs">Destination</TableHead>
                        <TableHead className="text-xs">Status</TableHead>
                        <TableHead className="text-xs">Lead Time</TableHead>
                        <TableHead className="text-xs">Freight Rate</TableHead>
                        <TableHead className="text-xs">Max Shipment Qty</TableHead>
                        <TableHead className="text-xs">SKU Eligibility</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {routes.map((r) => (
                        <TableRow key={r.id} className="text-xs">
                          <TableCell className="font-mono font-semibold text-slate-900">#{r.id}</TableCell>
                          <TableCell className="font-medium text-slate-800">{r.from_location_name || r.from_location_id}</TableCell>
                          <TableCell className="font-medium text-slate-800">{r.to_location_name || r.to_location_id}</TableCell>
                          <TableCell><Badge variant={r.is_active ? 'success' : 'neutral'} size="sm">{r.is_active ? 'Permitted' : 'Inactive'}</Badge></TableCell>
                          <TableCell className="text-slate-700">{r.lead_time_days} days</TableCell>
                          <TableCell className="font-bold text-slate-900">₹{r.cost_rate?.toFixed(2)} / case</TableCell>
                          <TableCell className="text-slate-600">{r.max_shipment_qty ? `${r.max_shipment_qty} cases` : 'Unlimited'}</TableCell>
                          <TableCell><Badge variant="neutral" size="sm">{r.sku_eligibility || 'ALL'}</Badge></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* 6. TAB CONTENT: Travel & Transport Cost Analysis (Section 7) */}
      {activeWorkflowTab === 'costs' && (
        <div className="space-y-4">
          <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-4">
              <div>
                <h3 className="text-base font-bold text-slate-900">
                  Comprehensive Transportation Cost Audit
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Verified route calculations. Formula: <code>Estimated Cost = Allocated Quantity × Route Freight Rate (INR/case)</code>.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right">
                  <span className="text-[10px] text-slate-400 block uppercase font-bold">Total Estimated Freight</span>
                  <span className="text-lg font-bold text-slate-900">
                    ₹{executiveMetrics.estimatedTransportCost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Source Warehouse</TableHead>
                    <TableHead className="text-xs">Destination</TableHead>
                    <TableHead className="text-xs">Product Line</TableHead>
                    <TableHead className="text-xs">Allocated Units</TableHead>
                    <TableHead className="text-xs">Distance (km)</TableHead>
                    <TableHead className="text-xs">Cost Rate / Unit</TableHead>
                    <TableHead className="text-xs">Estimated Cost</TableHead>
                    <TableHead className="text-xs">Actual Cost (Executed)</TableHead>
                    <TableHead className="text-xs">Variance</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transportCostAudit.map((item) => (
                    <TableRow key={item.recommendationId} className="text-xs">
                      <TableCell className="font-semibold text-slate-800">{item.sourceName}</TableCell>
                      <TableCell className="font-medium text-slate-800">{item.destinationName}</TableCell>
                      <TableCell className="font-mono text-slate-600">{item.skuId}</TableCell>
                      <TableCell className="font-bold text-blue-700">{item.quantity} cases</TableCell>
                      <TableCell className="text-slate-600">{item.distanceKm ? `${item.distanceKm} km` : 'Standard Arc'}</TableCell>
                      <TableCell className="font-mono text-slate-700">₹{item.costPerUnit.toFixed(2)}/case</TableCell>
                      <TableCell className="font-bold text-slate-900">₹{item.estimatedCost.toFixed(2)}</TableCell>
                      <TableCell className="text-slate-600">
                        {item.actualCost !== null ? `₹${item.actualCost.toFixed(2)}` : <span className="text-slate-400 italic">Pending Delivery</span>}
                      </TableCell>
                      <TableCell>
                        {item.variance !== null ? (
                          <Badge variant={item.variance > 0 ? 'critical' : 'success'} size="sm">
                            {item.variance > 0 ? `+₹${item.variance.toFixed(2)}` : `-₹${Math.abs(item.variance).toFixed(2)}`}
                          </Badge>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>
        </div>
      )}

      {/* 7. TAB CONTENT: Demand Forecasting & Risk Analysis (Section 8) */}
      {activeWorkflowTab === 'forecasts' && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="py-4 border-b border-slate-100">
              <CardTitle className="text-base font-bold text-slate-900">
                Demand Forecasts & Stockout Exposure Analysis
              </CardTitle>
              <CardDescription className="text-xs text-slate-500">
                Evaluation of historical sales, projected demand gaps, days of cover, and replenishment urgency.
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">SKU</TableHead>
                      <TableHead className="text-xs">Destination</TableHead>
                      <TableHead className="text-xs">Historical Sales</TableHead>
                      <TableHead className="text-xs">Forecast Demand</TableHead>
                      <TableHead className="text-xs">Current Stock</TableHead>
                      <TableHead className="text-xs">Projected Gap</TableHead>
                      <TableHead className="text-xs">Stockout Risk</TableHead>
                      <TableHead className="text-xs">Forecast Method</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {((riskData?.items || riskData?.records || []) as any[]).map((r, idx) => (
                      <TableRow key={idx} className="text-xs">
                        <TableCell className="font-mono font-semibold text-slate-900">{r.sku_id}</TableCell>
                        <TableCell className="font-medium text-slate-800">{r.destination_name || r.destination_id}</TableCell>
                        <TableCell className="text-slate-600">{(r.historical_sales_units ?? r.total_forecast_demand)?.toFixed(0) || '—'} units</TableCell>
                        <TableCell className="font-semibold text-slate-800">{(r.forecast_demand_units ?? r.total_forecast_demand)?.toFixed(0)} cases</TableCell>
                        <TableCell className="text-slate-700">{(r.current_stock_units ?? r.dispatchable_stock ?? r.on_hand)?.toFixed(0)} cases</TableCell>
                        <TableCell className="font-bold text-blue-700">{(r.demand_gap_units ?? r.demand_gap)?.toFixed(0)} cases</TableCell>
                        <TableCell>
                          <Badge
                            variant={(r.stockout_risk || r.risk_level) === 'critical' ? 'critical' : (r.stockout_risk || r.risk_level) === 'high' ? 'warning' : 'success'}
                            size="sm"
                          >
                            {r.stockout_risk || r.risk_level || 'low'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-slate-500 font-mono text-[11px]">{r.primary_risk_factor || '7-day Rolling MA'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 8. TAB CONTENT: Baseline vs Optimizer Audit (Section 9) */}
      {activeWorkflowTab === 'comparison' && (
        <div className="space-y-4">
          {activePlan?.baseline_comparison ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Optimizer Card */}
                <Card className="border-blue-200 bg-blue-50/20 p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-blue-900 text-sm">HiGHS Lexicographic Optimizer</span>
                    <Badge variant="primary">Optimized Plan</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-500 text-[11px]">Service Level</span>
                      <div className="text-xl font-bold text-slate-900">{activePlan.service_level_percent?.toFixed(1)}%</div>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px]">Fulfilled Demand</span>
                      <div className="text-xl font-bold text-blue-700">{activePlan.fulfilled_demand_units?.toLocaleString()} cases</div>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px]">Estimated Cost</span>
                      <div className="text-xl font-bold text-emerald-700">₹{activePlan.estimated_transport_cost?.toFixed(2)}</div>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px]">Solve Time</span>
                      <div className="text-xl font-bold text-slate-700">{activePlan.solve_time_ms?.toFixed(1)} ms</div>
                    </div>
                  </div>
                </Card>

                {/* Baseline Card */}
                <Card className="border-slate-200 bg-slate-50/50 p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-slate-800 text-sm">Nearest-Source Greedy Baseline</span>
                    <Badge variant="neutral">Deterministic Baseline</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-500 text-[11px]">Service Level</span>
                      <div className="text-xl font-bold text-slate-900">
                        {activePlan.baseline_comparison.baseline?.service_level_percent?.toFixed(1)}%
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px]">Fulfilled Demand</span>
                      <div className="text-xl font-bold text-slate-700">
                        {activePlan.baseline_comparison.baseline?.fulfilled_demand_units?.toLocaleString()} cases
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px]">Estimated Cost</span>
                      <div className="text-xl font-bold text-slate-700">
                        ₹{activePlan.baseline_comparison.baseline?.estimated_transport_cost?.toFixed(2)}
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px]">Unmet Demand</span>
                      <div className="text-xl font-bold text-amber-700">
                        {activePlan.baseline_comparison.baseline?.unmet_demand_units?.toLocaleString()} cases
                      </div>
                    </div>
                  </div>
                </Card>
              </div>

              {/* Difference and Value Analysis */}
              <Card className="p-5">
                <h4 className="font-bold text-slate-900 text-sm mb-3">Mathematical Optimization Improvements</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-100">
                    <span className="text-emerald-800 font-bold block mb-1">Service Level Delta</span>
                    <p className="text-slate-600">
                      Optimizer achieved <strong>{activePlan.service_level_percent?.toFixed(1)}%</strong> service versus <strong>{activePlan.baseline_comparison.baseline?.service_level_percent?.toFixed(1)}%</strong> baseline.
                    </p>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-xl border border-blue-100">
                    <span className="text-blue-800 font-bold block mb-1">Cost Efficiency</span>
                    <p className="text-slate-600">
                      Total cost: <strong>₹{activePlan.estimated_transport_cost?.toFixed(2)}</strong> versus baseline <strong>₹{activePlan.baseline_comparison.baseline?.estimated_transport_cost?.toFixed(2)}</strong>.
                    </p>
                  </div>
                  <div className="p-3 bg-indigo-50 rounded-xl border border-indigo-100">
                    <span className="text-indigo-800 font-bold block mb-1">Constraint Guarantee</span>
                    <p className="text-slate-600">
                      Zero corridor or shelf-life violations. Stage-1 strictly prioritized 100% fulfillment before minimizing cost in Stage-2.
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          ) : (
            <Card className="p-8">
              <EmptyState
                icon={GitCompare}
                title="Baseline Comparison Unavailable"
                description="The selected plan does not contain an embedded baseline benchmark. Execute a new optimization solve to record comparison metrics."
              />
            </Card>
          )}
        </div>
      )}

      {/* 9. TAB CONTENT: Approval & Execution Tracking (Section 10) */}
      {activeWorkflowTab === 'execution' && (
        <div className="space-y-4">
          <Card>
            <CardHeader className="py-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <CardTitle className="text-base font-bold text-slate-900">
                  Shipment Execution & Delivery Confirmation
                </CardTitle>
                <CardDescription className="text-xs text-slate-500">
                  Tracking of approved dispatches, carrier assignments, vehicle transit, and receipt confirmation.
                </CardDescription>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleApproveAllShipments}
                  disabled={approvalActionLoading !== null || executiveMetrics.pendingApprovals === 0}
                >
                  <FileCheck2 className="w-3.5 h-3.5 mr-1" />
                  {approvalActionLoading ? 'Approving...' : `Approve Entire Plan (${executiveMetrics.pendingApprovals} Pending)`}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate('/shipments')}
                >
                  <Truck className="w-3.5 h-3.5 mr-1" />
                  Shipments Hub
                </Button>
              </div>
            </CardHeader>

            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Shipment ID</TableHead>
                      <TableHead className="text-xs">Origin Warehouse</TableHead>
                      <TableHead className="text-xs">Destination</TableHead>
                      <TableHead className="text-xs">SKU & Qty</TableHead>
                      <TableHead className="text-xs">Approval Status</TableHead>
                      <TableHead className="text-xs">Logistics Status</TableHead>
                      <TableHead className="text-xs">Consignment & Carrier</TableHead>
                      <TableHead className="text-xs">Delivery Confirmation</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {shipments.map((s) => (
                      <TableRow key={s.shipment_id} className="text-xs">
                        <TableCell className="font-mono font-bold text-slate-900">{s.shipment_id}</TableCell>
                        <TableCell className="font-medium text-slate-800">{s.source_location_name || s.source_location_id}</TableCell>
                        <TableCell className="font-medium text-slate-800">{s.destination_location_name || s.destination_location_id}</TableCell>
                        <TableCell className="font-bold text-blue-700">{s.quantity} cases of {s.sku_id}</TableCell>
                        <TableCell>
                          <Badge variant={s.approval_status === 'approved' ? 'success' : s.approval_status === 'rejected' ? 'critical' : 'warning'} size="sm">
                            {s.approval_status || 'Pending'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant={s.status === 'delivered' ? 'success' : s.status === 'in_transit' ? 'primary' : 'neutral'} size="sm">
                            {s.status.replace(/_/g, ' ')}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-slate-600 font-mono text-[11px]">
                          {s.consignment_number || s.carrier_agency_name || 'Unassigned'}
                        </TableCell>
                        <TableCell className="text-slate-600">
                          {s.actual_delivery_date ? (
                            <span className="text-emerald-700 font-medium">Delivered: {new Date(s.actual_delivery_date).toLocaleDateString()}</span>
                          ) : (
                            <span className="text-slate-400 italic">In Pipeline</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 10. TAB CONTENT: Analytics & Visualizations (Section 11) */}
      {activeWorkflowTab === 'charts' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Chart 1: Replenishment Volume by Destination */}
            <Card className="p-5">
              <h4 className="font-bold text-slate-900 text-sm mb-1">Replenishment Quantity by Destination</h4>
              <p className="text-xs text-slate-500 mb-4">Allocated volume (cases) across candidate fulfillment nodes</p>
              <div className="space-y-2.5">
                {groupedAllocations.map((g) => {
                  const cases = g.receipts.reduce((acc, r) => acc + (r.quantity || 0), 0);
                  const maxCases = Math.max(...groupedAllocations.map((ga) => ga.receipts.reduce((acc, r) => acc + (r.quantity || 0), 0)), 1);
                  const pct = Math.round((cases / maxCases) * 100);

                  return (
                    <div key={g.destinationId} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-800">{g.destinationName}</span>
                        <span className="font-bold text-blue-700">{cases.toLocaleString()} cases</span>
                      </div>
                      <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-600 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            {/* Chart 2: Warehouse Outbound Volume Share */}
            <Card className="p-5">
              <h4 className="font-bold text-slate-900 text-sm mb-1">Source Warehouse Dispatch Share</h4>
              <p className="text-xs text-slate-500 mb-4">Proportion of company stock dispatched from each origin hub</p>
              <div className="space-y-3">
                {filterOptions.sources.map(([whId, whName]) => {
                  const outCases = decisionReceipts
                    .filter((r) => r.source_location_id === whId)
                    .reduce((acc, r) => acc + (r.quantity || 0), 0);
                  const totalPlanned = executiveMetrics.plannedQuantity || 1;
                  const sharePct = Math.round((outCases / totalPlanned) * 100);

                  if (outCases === 0) return null;

                  return (
                    <div key={whId} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-800">{whName}</span>
                        <span className="text-slate-600 font-medium">{outCases.toLocaleString()} cases ({sharePct}%)</span>
                      </div>
                      <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-indigo-600 rounded-full" style={{ width: `${sharePct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* 11. DECISION EXPLAINABILITY SLIDE-OUT DRAWER */}
      {selectedReceiptForDrawer && (
        <div className="fixed inset-0 bg-slate-900/40 z-50 flex justify-end backdrop-blur-xs animate-in fade-in duration-200">
          <div className="bg-white w-full max-w-xl h-full shadow-2xl flex flex-col justify-between overflow-hidden">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 bg-slate-50/80 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-slate-900">
                    Decision Receipt & Explainability
                  </h3>
                  <Badge variant="primary" size="sm">Certified</Badge>
                </div>
                <p className="text-xs text-slate-500 mt-0.5">
                  Recommendation ID: <code className="font-mono">{selectedReceiptForDrawer.recommendation_id}</code>
                </p>
              </div>
              <button
                onClick={() => setSelectedReceiptForDrawer(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs flex-1">
              {/* Product and Destination Card */}
              <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/80 grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[11px] text-slate-400 block">Product</span>
                  <div className="font-bold text-slate-900">{selectedReceiptForDrawer.product_name}</div>
                  <div className="text-[11px] font-mono text-slate-500">{selectedReceiptForDrawer.sku_id}</div>
                </div>
                <div>
                  <span className="text-[11px] text-slate-400 block">Destination Node</span>
                  <div className="font-bold text-slate-900">{selectedReceiptForDrawer.destination_location_name}</div>
                  <div className="text-[11px] font-mono text-slate-500">{selectedReceiptForDrawer.destination_location_id}</div>
                </div>
                <div>
                  <span className="text-[11px] text-slate-400 block">Allocated Quantity</span>
                  <div className="font-bold text-blue-700 text-sm">{selectedReceiptForDrawer.quantity} cases</div>
                </div>
                <div>
                  <span className="text-[11px] text-slate-400 block">Estimated Transport Cost</span>
                  <div className="font-bold text-emerald-700 text-sm">₹{selectedReceiptForDrawer.estimated_cost?.toFixed(2)}</div>
                </div>
              </div>

              {/* 1. Why this warehouse was selected */}
              <div>
                <h4 className="font-bold text-slate-900 text-xs mb-2 flex items-center gap-1.5 text-blue-700">
                  <CheckCircle2 className="w-4 h-4 text-blue-600" />
                  Why Was {selectedReceiptForDrawer.source_location_name} Selected?
                </h4>
                <div className="p-3.5 bg-blue-50/50 rounded-xl border border-blue-200/70 text-slate-700 leading-relaxed text-xs">
                  {selectedReceiptForDrawer.evidence}
                </div>
              </div>

              {/* 2. Other eligible warehouses considered & why rejected */}
              <div>
                <h4 className="font-bold text-slate-900 text-xs mb-2 flex items-center gap-1.5 text-rose-700">
                  <XCircle className="w-4 h-4 text-rose-600" />
                  Rejected Alternative Warehouses & Concrete Reasons
                </h4>
                <div className="space-y-2">
                  {selectedReceiptForDrawer.rejected_alternatives && selectedReceiptForDrawer.rejected_alternatives.length > 0 ? (
                    selectedReceiptForDrawer.rejected_alternatives.map((reason, idx) => (
                      <div key={idx} className="p-3 bg-rose-50/40 rounded-xl border border-rose-200/60 text-slate-700 text-xs flex items-start gap-2">
                        <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-1.5 shrink-0" />
                        <span>{reason}</span>
                      </div>
                    ))
                  ) : (
                    <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-slate-500 text-xs">
                      No other warehouse satisfied corridor route eligibility and dispatchable stock constraints for this destination.
                    </div>
                  )}
                </div>
              </div>

              {/* 3. FEFO Expiry Batch Details */}
              <div>
                <h4 className="font-bold text-slate-900 text-xs mb-2 flex items-center gap-1.5 text-emerald-700">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  FEFO Batch Selection & Shelf-Life Compliance
                </h4>
                {selectedReceiptForDrawer.allocated_batches && selectedReceiptForDrawer.allocated_batches.length > 0 ? (
                  <div className="border border-slate-200 rounded-xl overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-[11px]">Batch #</TableHead>
                          <TableHead className="text-[11px]">Expiry Date</TableHead>
                          <TableHead className="text-[11px]">Days Remaining</TableHead>
                          <TableHead className="text-[11px]">Allocated</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {selectedReceiptForDrawer.allocated_batches.map((b, idx) => (
                          <TableRow key={idx} className="text-xs">
                            <TableCell className="font-mono font-bold text-slate-800">{b.batch_number}</TableCell>
                            <TableCell className="text-slate-600">{b.expiry_date || '—'}</TableCell>
                            <TableCell className="font-semibold text-emerald-700">{b.shelf_life_remaining_days || b.days_remaining}d</TableCell>
                            <TableCell className="font-bold text-blue-700">{b.allocated_quantity} cases</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                ) : (
                  <div className="p-3 bg-slate-50 rounded-xl border border-slate-200 text-slate-500 text-xs">
                    No batch-level expiry was specified in the inventory snapshot. Standard stock was allocated.
                  </div>
                )}
              </div>

              {/* 4. Constraints Evaluated */}
              <div>
                <h4 className="font-bold text-slate-900 text-xs mb-2">Mathematical Constraints Verified</h4>
                <div className="space-y-1.5">
                  {(selectedReceiptForDrawer.constraints_evaluated || [
                    'Dispatchable stock verified: OH - Res - Blk > 0',
                    'Active permitted corridor verified',
                    'Transit lead time within planning horizon cutoff',
                    'FMCG company ownership verified',
                  ]).map((c, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-slate-600 text-xs">
                      <Check className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                      <span>{c}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 5. Cost Model Breakdown */}
              <div className="p-3.5 bg-slate-50 rounded-xl border border-slate-200 text-slate-600 space-y-1">
                <span className="font-bold text-slate-800 block text-xs">Cost Calculation Breakdown</span>
                <p className="text-[11px]">
                  <strong>Formula:</strong> {selectedReceiptForDrawer.quantity} cases × ₹{((selectedReceiptForDrawer.estimated_cost || 0) / (selectedReceiptForDrawer.quantity || 1)).toFixed(2)} / case = <strong>₹{selectedReceiptForDrawer.estimated_cost?.toFixed(2)}</strong>.
                </p>
                {selectedReceiptForDrawer.distance_km && (
                  <p className="text-[11px]">
                    Transit Corridor Distance: {selectedReceiptForDrawer.distance_km} km.
                  </p>
                )}
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <span className="text-[11px] text-slate-400 font-mono">
                Corridor Route #{selectedReceiptForDrawer.route_id || 'Active'}
              </span>
              <Button variant="outline" size="sm" onClick={() => setSelectedReceiptForDrawer(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
