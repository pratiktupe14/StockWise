import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Warehouse as WarehouseIcon,
  TrendingUp,
  Sparkles,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  DollarSign,
  Layers,
  Filter,
  MapPin,
  Sliders,
  CheckCircle,
  XCircle,
  Info,
  Send,
  Activity,
  Route as RouteIcon,
  Gauge,
  GitCompare,
  Boxes,
} from 'lucide-react';

import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
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
  getProducts,
  getNetworkLocations,
  getInventory,
  getRoutes,
  getDemandForecast,
  getInventoryRisks,
  runDistributionOptimization,
  getPlanningRuns,
  getPlanningRunDetails,
  getDecisionReceipts,
  getPlanComparison,
  compareCorridors,
  simulateWhatIfScenario,
  getInventoryExpiryRisk,
  allocateInventoryFEFO,
  getRedistributionRecommendations,
  submitRedistributionProposal,
  getForecastEvaluation,
  getDistributionPerformance,
} from '../services/api';

import { useDatasetSync } from '../services/dataSync';
import { useAuth } from '../context/AuthContext';
import { ActualVsPredictedDemandChart } from '../components/ActualVsPredictedDemandChart';
import { DistributionPerformanceKPIs } from '../components/DistributionPerformanceKPIs';

import type {
  ProductItem,
  LocationItem,
  InventoryItem,
  RouteItem,
  PlanningRunResponse,
  DecisionReceipt,
  PlanComparisonResponse,
  ForecastItem,
  RiskAnalysisItem,
  CorridorComparisonResponse,
  ScenarioSimulationResponse,
  ExpiryRiskSummaryResponse,
  FEFOAllocationResponse,
  RedistributionRecommendation,
  RedistributionSummaryResponse,
  ForecastEvaluationResponse,
  DistributionPerformanceResponse,
} from '../types/api';

export const DistributionIntelligencePage: React.FC = () => {
  const { user } = useAuth();

  // Mode and global filter state
  const [dataMode, setDataMode] = useState<'operational' | 'benchmark'>('operational');
  const [selectedSkuId, setSelectedSkuId] = useState<string>('all');
  const [selectedRegion, setSelectedRegion] = useState<string>('all');
  const [selectedDestinationId, setSelectedDestinationId] = useState<string>('all');
  const [selectedHorizon, setSelectedHorizon] = useState<number>(7);
  const [requiredQuantity, setRequiredQuantity] = useState<string>('');
  const [deliveryDeadline, setDeliveryDeadline] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'warehouse' | 'landed_cost' | 'fefo_expiry' | 'excess_forecast'>('warehouse');

  // Core Data State
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Entities
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [inventoryList, setInventoryList] = useState<InventoryItem[]>([]);
  const [routes, setRoutes] = useState<RouteItem[]>([]);

  // Analytics & Solver State
  const [latestPlanningRun, setLatestPlanningRun] = useState<PlanningRunResponse | null>(null);
  const [decisionReceipts, setDecisionReceipts] = useState<DecisionReceipt[]>([]);
  const [baselineComparison, setBaselineComparison] = useState<PlanComparisonResponse | null>(null);
  const [riskItems, setRiskItems] = useState<RiskAnalysisItem[]>([]);
  const [forecasts, setForecasts] = useState<ForecastItem[]>([]);
  const [expirySummary, setExpirySummary] = useState<ExpiryRiskSummaryResponse | null>(null);
  const [redistributions, setRedistributions] = useState<RedistributionSummaryResponse | null>(null);

  // P1, P2 & P3: ML Forecast Evaluation and Distribution Performance State
  const [distributionPerformance, setDistributionPerformance] = useState<DistributionPerformanceResponse | null>(null);
  const [performanceLoading, setPerformanceLoading] = useState<boolean>(false);
  const [forecastEvaluation, setForecastEvaluation] = useState<ForecastEvaluationResponse | null>(null);
  const [evaluationLoading, setEvaluationLoading] = useState<boolean>(false);

  // Interactive Corridor Comparison State
  const [corridorComparison, setCorridorComparison] = useState<CorridorComparisonResponse | null>(null);
  const [corridorLoading, setCorridorLoading] = useState<boolean>(false);

  // Interactive FEFO Allocator Test State
  const [fefoDemandInput, setFefoDemandInput] = useState<number>(50);
  const [fefoMinShelfLife, setFefoMinShelfLife] = useState<number>(15);
  const [fefoResult, setFefoResult] = useState<FEFOAllocationResponse | null>(null);
  const [fefoLoading, setFefoLoading] = useState<boolean>(false);

  // What-If Simulation Modal State
  const [showSimModal, setShowSimModal] = useState<boolean>(false);
  const [simDemandMult, setSimDemandMult] = useState<number>(1.2);
  const [simFreightMult, setSimFreightMult] = useState<number>(1.0);
  const [simStockMult, setSimStockMult] = useState<number>(1.0);
  const [simHorizon, setSimHorizon] = useState<number>(7);
  const [simulating, setSimulating] = useState<boolean>(false);
  const [simResult, setSimResult] = useState<ScenarioSimulationResponse | null>(null);

  // Expiry table filter state
  const [expiryCategoryFilter, setExpiryCategoryFilter] = useState<string>('all');
  const [expiryWarehouseFilter, setExpiryWarehouseFilter] = useState<string>('all');
  const [expirySkuFilter, setExpirySkuFilter] = useState<string>('all');

  // Optimization execution state
  const [optimizing, setOptimizing] = useState<boolean>(false);

  // Initial Data Fetch
  const loadAllData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        prodsRes,
        locsRes,
        invRes,
        routesRes,
        expiryRes,
        redistRes,
        riskRes,
        forecastRes,
        runsRes,
        evalRes,
        perfRes,
      ] = await Promise.allSettled([
        getProducts(),
        getNetworkLocations(),
        getInventory(),
        getRoutes(),
        getInventoryExpiryRisk(),
        getRedistributionRecommendations({ maxExpiryDays: 60 }),
        getInventoryRisks(selectedHorizon),
        getDemandForecast(selectedHorizon),
        getPlanningRuns(5, 0),
        getForecastEvaluation(
          selectedHorizon,
          selectedSkuId !== 'all' ? selectedSkuId : undefined,
          selectedDestinationId !== 'all' ? selectedDestinationId : undefined
        ),
        getDistributionPerformance(),
      ]);

      if (prodsRes.status === 'fulfilled') setProducts(prodsRes.value);
      if (locsRes.status === 'fulfilled') setLocations(locsRes.value);
      if (invRes.status === 'fulfilled') setInventoryList(invRes.value);
      if (routesRes.status === 'fulfilled') setRoutes(routesRes.value);
      if (expiryRes.status === 'fulfilled') setExpirySummary(expiryRes.value);
      if (redistRes.status === 'fulfilled') setRedistributions(redistRes.value);
      if (riskRes.status === 'fulfilled') setRiskItems(riskRes.value.items || []);
      if (forecastRes.status === 'fulfilled') setForecasts(forecastRes.value.forecasts || []);
      if (evalRes.status === 'fulfilled') setForecastEvaluation(evalRes.value);
      if (perfRes.status === 'fulfilled') setDistributionPerformance(perfRes.value);

      // If planning runs exist, fetch details of latest
      if (runsRes.status === 'fulfilled' && runsRes.value.length > 0) {
        const latestId = runsRes.value[0].run_id;
        try {
          const [details, receipts, comparison, runPerf] = await Promise.all([
            getPlanningRunDetails(latestId),
            getDecisionReceipts(latestId),
            getPlanComparison(latestId).catch(() => null),
            getDistributionPerformance(latestId).catch(() => null),
          ]);
          setLatestPlanningRun(details);
          setDecisionReceipts(receipts);
          setBaselineComparison(comparison);
          if (runPerf) setDistributionPerformance(runPerf);
        } catch (runErr) {
          console.warn('Could not load latest run details:', runErr);
        }
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load distribution intelligence data');
    } finally {
      setLoading(false);
    }
  }, [selectedHorizon, selectedSkuId, selectedDestinationId]);

  // Reactive Data Sync Hook: automatically re-fetches when any relevant dataset is imported
  const { formattedSyncTime } = useDatasetSync(
    ['inventory', 'products', 'routes', 'locations', 'sales'],
    loadAllData
  );

  useEffect(() => {
    loadAllData();
  }, [loadAllData]);

  // Reactive fetch of ML Forecast Evaluation when scope changes
  useEffect(() => {
    let active = true;
    setEvaluationLoading(true);
    getForecastEvaluation(
      selectedHorizon,
      selectedSkuId !== 'all' ? selectedSkuId : undefined,
      selectedDestinationId !== 'all' ? selectedDestinationId : undefined
    )
      .then((res) => {
        if (active) setForecastEvaluation(res);
      })
      .catch((err) => {
        console.warn('Forecast evaluation error:', err);
        if (active) setForecastEvaluation(null);
      })
      .finally(() => {
        if (active) setEvaluationLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedHorizon, selectedSkuId, selectedDestinationId]);

  // Reactive fetch of Distribution Performance KPIs when plan changes
  useEffect(() => {
    let active = true;
    setPerformanceLoading(true);
    getDistributionPerformance(latestPlanningRun?.run_id)
      .then((res) => {
        if (active) setDistributionPerformance(res);
      })
      .catch((err) => {
        console.warn('Distribution performance error:', err);
        if (active) setDistributionPerformance(null);
      })
      .finally(() => {
        if (active) setPerformanceLoading(false);
      });

    return () => {
      active = false;
    };
  }, [latestPlanningRun?.run_id]);

  // Load Corridor Comparison when SKU or Destination is selected
  const fetchCorridorComparison = useCallback(async (destId: string, skuId: string) => {
    if (!destId || destId === 'all' || !skuId || skuId === 'all') {
      setCorridorComparison(null);
      return;
    }
    setCorridorLoading(true);
    try {
      const data = await compareCorridors(destId, skuId, selectedHorizon);
      setCorridorComparison(data);
    } catch (e: any) {
      console.warn('Corridor compare error:', e);
      setCorridorComparison(null);
    } finally {
      setCorridorLoading(false);
    }
  }, [selectedHorizon]);

  useEffect(() => {
    if (selectedDestinationId !== 'all' && selectedSkuId !== 'all') {
      fetchCorridorComparison(selectedDestinationId, selectedSkuId);
    } else {
      setCorridorComparison(null);
    }
  }, [selectedDestinationId, selectedSkuId, fetchCorridorComparison]);

  // Handle Run Distribution Optimization
  const handleRunOptimization = async () => {
    setOptimizing(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await runDistributionOptimization({
        horizon_days: selectedHorizon,
        objective_strategy: 'service_first',
        allow_cross_region_routes: true,
        authorized_user_id: user?.id || 'admin_user',
      });
      setLatestPlanningRun(result);
      setDecisionReceipts(result.decision_receipts || []);
      setBaselineComparison(result.baseline_comparison || null);
      getDistributionPerformance(result.run_id).then(setDistributionPerformance).catch(() => {});
      setSuccessMessage(`Optimization executed successfully in ${result.solve_time_ms}ms with ${result.service_level_percent}% service level.`);
      // Reload risks and expiry
      getInventoryRisks(selectedHorizon).then(r => setRiskItems(r.items || [])).catch(() => {});
      getInventoryExpiryRisk().then(e => setExpirySummary(e)).catch(() => {});
    } catch (err: any) {
      setError(err?.message || 'Optimization solver run failed');
    } finally {
      setOptimizing(false);
    }
  };

  // Handle FEFO Test Allocation
  const handleRunFEFOAllocation = async () => {
    if (selectedSkuId === 'all') {
      setError('Please select a specific SKU to test FEFO allocation');
      return;
    }
    setFefoLoading(true);
    try {
      const res = await allocateInventoryFEFO({
        sku_id: selectedSkuId,
        demand_quantity: fefoDemandInput,
        destination_location_id: selectedDestinationId !== 'all' ? selectedDestinationId : undefined,
        min_remaining_shelf_life_days: fefoMinShelfLife,
      });
      setFefoResult(res);
    } catch (err: any) {
      setError(err?.message || 'FEFO allocation failed');
    } finally {
      setFefoLoading(false);
    }
  };

  // Handle Propose Redistribution Shipment
  const handleProposeRedistribution = async (rec: RedistributionRecommendation) => {
    try {
      await submitRedistributionProposal({
        sku_id: rec.sku_id,
        source_location_id: rec.source_location_id,
        destination_location_id: rec.destination_location_id,
        quantity: rec.recommended_quantity,
        batch_number: rec.batch_number || undefined,
        notes: `Authorized FEFO redistribution proposal from Distribution Intelligence: ${rec.rationale}`,
      });
      setSuccessMessage(`Shipment proposal created for ${rec.recommended_quantity} units of ${rec.sku_id} from ${rec.source_location_name} to ${rec.destination_location_name}`);
      // Refresh recommendations
      const updated = await getRedistributionRecommendations({ maxExpiryDays: 60 });
      setRedistributions(updated);
    } catch (err: any) {
      setError(err?.message || 'Failed to submit redistribution proposal');
    }
  };

  // Handle What-If Simulation
  const handleRunSimulation = async () => {
    setSimulating(true);
    try {
      const res = await simulateWhatIfScenario({
        horizon_days: simHorizon,
        demand_multiplier: simDemandMult,
        freight_rate_multiplier: simFreightMult,
        source_stock_multiplier: simStockMult,
        disrupted_route_ids: [],
        solver_type: 'lexicographic_highs',
        authorized_user_id: user?.id || 'admin_user',
      });
      setSimResult(res);
    } catch (err: any) {
      setError(err?.message || 'Simulation run failed');
    } finally {
      setSimulating(false);
    }
  };

  // Filtered Locations (Destinations vs Sources)
  const destinationLocations = useMemo(() => {
    return locations.filter(l => l.location_type === 'distributor' || l.location_type === 'retailer');
  }, [locations]);

  const sourceWarehouses = useMemo(() => {
    return locations.filter(l => l.location_type === 'warehouse' || l.location_type === 'factory' || l.location_type === 'cf_depot');
  }, [locations]);

  // Unique regions
  const availableRegions = useMemo(() => {
    const set = new Set<string>();
    locations.forEach(l => {
      if (l.region) set.add(l.region);
    });
    return Array.from(set).sort();
  }, [locations]);

  // Filtered Decision Receipts / Allocations based on selections
  const filteredReceipts = useMemo(() => {
    return decisionReceipts.filter(rc => {
      if (selectedSkuId !== 'all' && rc.sku_id !== selectedSkuId) return false;
      if (selectedDestinationId !== 'all' && rc.destination_location_id !== selectedDestinationId) return false;
      if (selectedRegion !== 'all') {
        const dest = locations.find(l => l.location_id === rc.destination_location_id);
        if (dest && dest.region !== selectedRegion) return false;
      }
      return true;
    });
  }, [decisionReceipts, selectedSkuId, selectedDestinationId, selectedRegion, locations]);

  // Filtered Expiry Items
  const filteredExpiryItems = useMemo(() => {
    if (!expirySummary?.items) return [];
    return expirySummary.items.filter(item => {
      if (expirySkuFilter !== 'all' && item.sku_id !== expirySkuFilter) return false;
      if (expiryWarehouseFilter !== 'all' && item.location_id !== expiryWarehouseFilter) return false;
      if (selectedRegion !== 'all') {
        const loc = locations.find(l => l.location_id === item.location_id);
        if (loc && loc.region !== selectedRegion) return false;
      }
      if (expiryCategoryFilter !== 'all') {
        if (expiryCategoryFilter === 'expired' && item.risk_category !== 'expired') return false;
        if (expiryCategoryFilter === 'critical' && item.risk_category !== 'critical') return false;
        if (expiryCategoryFilter === 'warning' && item.risk_category !== 'warning' && item.risk_category !== 'high_risk') return false;
        if (expiryCategoryFilter === 'upcoming' && item.risk_category !== 'upcoming' && item.risk_category !== 'medium_risk') return false;
        if (expiryCategoryFilter === 'healthy' && item.risk_category !== 'healthy') return false;
        if (expiryCategoryFilter === 'unknown' && item.risk_category !== 'unknown') return false;
      }
      return true;
    });
  }, [expirySummary, expirySkuFilter, expiryWarehouseFilter, selectedRegion, expiryCategoryFilter, locations]);

  // Warehouses with urgent exposure (critical or warning)
  const urgentWarehouseCount = useMemo(() => {
    if (!expirySummary?.items) return 0;
    const locSet = new Set<string>();
    expirySummary.items.forEach(it => {
      if (it.risk_category === 'critical' || it.risk_category === 'warning' || it.risk_category === 'expired') {
        locSet.add(it.location_id);
      }
    });
    return locSet.size;
  }, [expirySummary]);

  // Dispatchable Inventory calculation: sum max(0, on_hand - reserved - blocked)
  const totalDispatchableStock = useMemo(() => {
    return inventoryList.reduce((acc, inv) => {
      const disp = Math.max(0, (inv.on_hand || 0) - (inv.reserved || 0) - (inv.blocked || 0));
      return acc + disp;
    }, 0);
  }, [inventoryList]);

  // Potential Excess Inventory calculation
  const totalExcessStock = useMemo(() => {
    return riskItems.reduce((acc, r) => acc + (r.excess_stock || 0), 0);
  }, [riskItems]);

  // Helper for Alert Severity badge
  const getExpiryBadge = (category: string, days?: number | null) => {
    const cat = category.toLowerCase();
    if (cat === 'expired' || (days !== undefined && days !== null && days < 0)) {
      return <Badge variant="critical">Expired ({days !== null && days !== undefined ? `${days}d` : 'Past'})</Badge>;
    }
    if (cat === 'critical' || (days !== undefined && days !== null && days <= 10)) {
      return <Badge variant="critical">Critical (&le;10d)</Badge>;
    }
    if (cat === 'warning' || cat === 'high_risk' || (days !== undefined && days !== null && days <= 30)) {
      return <Badge variant="warning">Warning (11-30d)</Badge>;
    }
    if (cat === 'upcoming' || cat === 'medium_risk' || (days !== undefined && days !== null && days <= 60)) {
      return <Badge variant="neutral">Upcoming (31-60d)</Badge>;
    }
    if (cat === 'healthy' || (days !== undefined && days !== null && days > 60)) {
      return <Badge variant="success">Healthy (&gt;60d)</Badge>;
    }
    return <Badge variant="neutral">Missing Expiry</Badge>;
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              StockWise Distribution Intelligence
            </h1>
            <Badge variant="primary" dot size="sm">
              Live Solver
            </Badge>
            <Badge variant="neutral" size="sm">
              Company Admin Portal
            </Badge>
          </div>
          <p className="mt-1 text-sm text-slate-600 max-w-3xl">
            Optimize product distribution, reduce stockouts and wastage, compare warehouses and transportation costs, and generate explainable allocation decisions.
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="secondary"
            size="sm"
            onClick={loadAllData}
            disabled={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh Data
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setShowSimModal(true)}
            leftIcon={<Sliders className="w-3.5 h-3.5" />}
          >
            What-If Simulation
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleRunOptimization}
            disabled={optimizing}
            leftIcon={<Sparkles className="w-3.5 h-3.5" />}
          >
            {optimizing ? 'Solving...' : 'Run Distribution Optimization'}
          </Button>
        </div>
      </div>

      {/* Global Sync and Stale Data Banner */}
      {formattedSyncTime && (
        <div className="flex items-center justify-between px-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-600">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Operational Data Pipeline Synced at <strong>{formattedSyncTime}</strong></span>
          </div>
          <span className="text-slate-500">Multi-tenant RBAC: <strong>ORG-FMCG-CORP</strong> &bull; {routes.length} Active Corridors</span>
        </div>
      )}

      {/* Alerts */}
      {error && (
        <Alert variant="error" title="Distribution Intelligence Notification">
          {error}
        </Alert>
      )}
      {successMessage && (
        <Alert variant="success" title="Action Completed">
          {successMessage}
        </Alert>
      )}

      {/* Global Controls Panel */}
      <Card className="border-slate-200 bg-white">
        <CardContent className="p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <Filter className="w-3.5 h-3.5" />
              Global Controls & Planning Scope
            </div>
            {/* Operational vs Benchmark Toggle */}
            <div className="flex items-center gap-1 bg-slate-100 p-0.5 rounded-lg border border-slate-200 text-xs">
              <button
                type="button"
                onClick={() => setDataMode('operational')}
                className={`px-2.5 py-1 rounded font-medium transition-all ${
                  dataMode === 'operational'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Operational Data
              </button>
              <button
                type="button"
                onClick={() => setDataMode('benchmark')}
                className={`px-2.5 py-1 rounded font-medium transition-all ${
                  dataMode === 'benchmark'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Benchmark Dataset
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 pt-1">
            {/* Product / SKU Filter */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Product / SKU</label>
              <select
                value={selectedSkuId}
                onChange={(e) => setSelectedSkuId(e.target.value)}
                className="w-full h-8 text-xs rounded-md border border-slate-300 bg-white px-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="all">All Products ({products.length})</option>
                {products.map((p) => (
                  <option key={p.sku_id} value={p.sku_id}>
                    {p.sku_id} - {p.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Region Filter */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Destination Region</label>
              <select
                value={selectedRegion}
                onChange={(e) => setSelectedRegion(e.target.value)}
                className="w-full h-8 text-xs rounded-md border border-slate-300 bg-white px-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="all">All Regions ({availableRegions.length})</option>
                {availableRegions.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>

            {/* Distributor / Retailer Destination */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Destination Facility</label>
              <select
                value={selectedDestinationId}
                onChange={(e) => setSelectedDestinationId(e.target.value)}
                className="w-full h-8 text-xs rounded-md border border-slate-300 bg-white px-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="all">All Destinations ({destinationLocations.length})</option>
                {destinationLocations.map((d) => (
                  <option key={d.location_id} value={d.location_id}>
                    {d.name} ({d.location_type}) - {d.region}
                  </option>
                ))}
              </select>
            </div>

            {/* Planning Horizon */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Planning Horizon</label>
              <select
                value={selectedHorizon}
                onChange={(e) => setSelectedHorizon(Number(e.target.value))}
                className="w-full h-8 text-xs rounded-md border border-slate-300 bg-white px-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value={7}>7 Days (Short-term)</option>
                <option value={14}>14 Days (Bi-weekly)</option>
                <option value={21}>21 Days (3-week)</option>
                <option value={30}>30 Days (Monthly)</option>
              </select>
            </div>

            {/* Required Quantity Override */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Required Qty (Units)</label>
              <input
                type="number"
                placeholder="Auto from Demand"
                value={requiredQuantity}
                onChange={(e) => setRequiredQuantity(e.target.value)}
                className="w-full h-8 text-xs rounded-md border border-slate-300 bg-white px-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            {/* Delivery Deadline */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">Delivery Deadline</label>
              <input
                type="date"
                value={deliveryDeadline}
                onChange={(e) => setDeliveryDeadline(e.target.value)}
                className="w-full h-8 text-xs rounded-md border border-slate-300 bg-white px-2 text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* P3: Four Separately Labelled Distribution Performance KPIs */}
      <DistributionPerformanceKPIs
        performance={distributionPerformance}
        loading={performanceLoading}
      />

      {/* Data-Driven KPI Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
        <SummaryCard
          title="TOTAL DEMAND"
          icon={Activity}
          value={latestPlanningRun ? `${latestPlanningRun.total_demand_units.toLocaleString()} u` : 'Unavailable'}
          subtitle={`${selectedHorizon}-day horizon`}
          badgeText="Demand Input"
          badgeVariant="neutral"
        />
        <SummaryCard
          title="FULFILLED DEMAND"
          icon={CheckCircle2}
          value={latestPlanningRun ? `${latestPlanningRun.fulfilled_demand_units.toLocaleString()} u` : 'Unavailable'}
          subtitle="Allocated from stock"
          badgeText="Solved"
          badgeVariant="success"
        />
        <SummaryCard
          title="UNMET DEMAND"
          icon={AlertTriangle}
          value={latestPlanningRun ? `${latestPlanningRun.unmet_demand_units.toLocaleString()} u` : 'Unavailable'}
          subtitle={latestPlanningRun?.unmet_demand_units === 0 ? 'Zero Stockouts' : 'Stockout risk'}
          badgeText={latestPlanningRun?.unmet_demand_units === 0 ? 'Zero Shortage' : 'Deficit'}
          badgeVariant={latestPlanningRun?.unmet_demand_units === 0 ? 'success' : 'critical'}
        />
        <SummaryCard
          title="SERVICE LEVEL"
          icon={Gauge}
          value={latestPlanningRun ? `${latestPlanningRun.service_level_percent}%` : 'Unavailable'}
          subtitle="Demand fulfillment rate"
          badgeText={latestPlanningRun && latestPlanningRun.service_level_percent >= 95 ? 'Optimal' : 'Standard'}
          badgeVariant={latestPlanningRun && latestPlanningRun.service_level_percent >= 95 ? 'success' : 'warning'}
        />
        <SummaryCard
          title="DISPATCHABLE STOCK"
          icon={Boxes}
          value={`${totalDispatchableStock.toLocaleString()} u`}
          subtitle="max(0, OH-Res-Blk)"
          badgeText="Net Available"
          badgeVariant="primary"
        />
        <SummaryCard
          title="POTENTIAL EXCESS"
          icon={Layers}
          value={`${totalExcessStock.toLocaleString()} u`}
          subtitle="Stock > Safety buffer"
          badgeText={totalExcessStock > 0 ? 'Redistribute' : 'Balanced'}
          badgeVariant={totalExcessStock > 0 ? 'warning' : 'neutral'}
        />
        <SummaryCard
          title="EST. LANDED COST"
          icon={DollarSign}
          value={latestPlanningRun ? `₹${Math.round(latestPlanningRun.estimated_transport_cost).toLocaleString()}` : 'Unavailable'}
          subtitle="Freight & Handling"
          badgeText="Cost Optimized"
          badgeVariant="neutral"
        />
        <SummaryCard
          title="EXPIRY EXPOSURE"
          icon={ShieldAlert}
          value={expirySummary ? `${expirySummary.critical_units + expirySummary.expired_units} u` : 'Unavailable'}
          subtitle="Unavailable (cost unconfigured)"
          badgeText={expirySummary && (expirySummary.critical_batches > 0 || expirySummary.expired_batches > 0) ? 'Action Required' : 'Healthy'}
          badgeVariant={expirySummary && (expirySummary.critical_batches > 0 || expirySummary.expired_batches > 0) ? 'critical' : 'success'}
        />
      </div>

      {/* Main Tab Navigation */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6 text-sm font-medium">
          <button
            type="button"
            onClick={() => setActiveTab('warehouse')}
            className={`pb-3 flex items-center gap-2 border-b-2 transition-all ${
              activeTab === 'warehouse'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <WarehouseIcon className="w-4 h-4" />
            Warehouse Allocation & Stockout Prevention
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('landed_cost')}
            className={`pb-3 flex items-center gap-2 border-b-2 transition-all ${
              activeTab === 'landed_cost'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <RouteIcon className="w-4 h-4" />
            Landed Cost & Shortest-Route Optimization
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('fefo_expiry')}
            className={`pb-3 flex items-center gap-2 border-b-2 transition-all ${
              activeTab === 'fefo_expiry'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <ShieldAlert className="w-4 h-4 text-amber-500" />
            FEFO & Warehouse Expiry Alerts (10d & 30d)
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('excess_forecast')}
            className={`pb-3 flex items-center gap-2 border-b-2 transition-all ${
              activeTab === 'excess_forecast'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            Excess Inventory & Regional Forecasting
          </button>
        </nav>
      </div>

      {/* TAB 1: WAREHOUSE SELECTION AND STOCKOUT PREVENTION */}
      {activeTab === 'warehouse' && (
        <div className="space-y-6">
          {/* Warehouse Allocation Table */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>Intelligent Warehouse Selection & Stockout Prevention</CardTitle>
                <CardDescription>
                  Evaluates dispatchable stock [max(0, on_hand - reserved - blocked)], road transit constraints, and service-first optimization objectives.
                </CardDescription>
              </div>
              <Badge variant="neutral">
                {filteredReceipts.length} Allocations Recorded
              </Badge>
            </CardHeader>
            <CardContent>
              {filteredReceipts.length === 0 ? (
                <EmptyState
                  icon={WarehouseIcon}
                  title="No Warehouse Allocations Generated Yet"
                  description="Run distribution optimization or select a planning run to view recommended source warehouses and stockout prevention decisions."
                  actionLabel="Run Distribution Optimization"
                  onAction={handleRunOptimization}
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SKU & Product</TableHead>
                        <TableHead>Destination Facility</TableHead>
                        <TableHead>Recommended Warehouse</TableHead>
                        <TableHead>Allocated Qty</TableHead>
                        <TableHead>Dispatchable Stock</TableHead>
                        <TableHead>Remaining Unmet</TableHead>
                        <TableHead>Road Transit (OSRM)</TableHead>
                        <TableHead>Status & Feasibility</TableHead>
                        <TableHead>Recommendation Explanation</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredReceipts.map((rc, idx) => {
                        const sourceLoc = locations.find(l => l.location_id === rc.source_location_id);
                        const destLoc = locations.find(l => l.location_id === rc.destination_location_id);
                        const invMatch = inventoryList.find(i => i.sku_id === rc.sku_id && i.location_id === rc.source_location_id);
                        const dispatchable = invMatch ? Math.max(0, (invMatch.on_hand || 0) - (invMatch.reserved || 0) - (invMatch.blocked || 0)) : rc.quantity;

                        return (
                          <TableRow key={rc.recommendation_id || idx} className="hover:bg-slate-50/60">
                            <TableCell className="font-medium text-slate-900">
                              <div>{rc.sku_id}</div>
                              <div className="text-xs text-slate-500 font-normal">{rc.product_name || 'FMCG SKU'}</div>
                            </TableCell>

                            <TableCell>
                              <div className="flex items-center gap-1.5">
                                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                                <span>{rc.destination_location_name || rc.destination_location_id}</span>
                              </div>
                              <div className="text-xs text-slate-500">{destLoc?.region || 'Region'} &bull; {destLoc?.location_type || 'Facility'}</div>
                            </TableCell>

                            <TableCell>
                              <div className="flex items-center gap-1.5">
                                <WarehouseIcon className="w-3.5 h-3.5 text-blue-600" />
                                <span className="font-medium text-slate-900">{rc.source_location_name || rc.source_location_id}</span>
                              </div>
                              <div className="text-xs text-slate-500">{sourceLoc?.region || 'Central'} &bull; {sourceLoc?.owner_org_name || sourceLoc?.owner_org_id || 'Company Owned'}</div>
                            </TableCell>

                            <TableCell className="font-semibold text-slate-900">
                              {rc.quantity.toLocaleString()} {rc.unit || 'units'}
                            </TableCell>

                            <TableCell>
                              <span className="text-slate-800 font-medium">{dispatchable.toLocaleString()} u</span>
                              <div className="text-[11px] text-slate-400">Available</div>
                            </TableCell>

                            <TableCell>
                              {rc.unmet_demand_remaining > 0 ? (
                                <Badge variant="critical">{rc.unmet_demand_remaining.toLocaleString()} u deficit</Badge>
                              ) : (
                                <Badge variant="success">0 u (Fulfilled)</Badge>
                              )}
                            </TableCell>

                            <TableCell>
                              <div className="text-xs text-slate-700">
                                <strong>{rc.distance_km ? `${Math.round(rc.distance_km)} km` : `${rc.lead_time_days * 350} km`}</strong>
                              </div>
                              <div className="text-xs text-slate-500">
                                ~{(rc.lead_time_days * 24).toFixed(0)}h ({rc.lead_time_days}d lead time)
                              </div>
                            </TableCell>

                            <TableCell>
                              <Badge variant="success">Eligible & Feasible</Badge>
                            </TableCell>

                            <TableCell className="max-w-xs text-xs text-slate-600">
                              <p className="line-clamp-2" title={rc.evidence}>
                                {rc.evidence || 'Optimized warehouse with shortest feasible road route and sufficient dispatchable inventory.'}
                              </p>
                              {rc.rejected_alternatives && rc.rejected_alternatives.length > 0 && (
                                <div className="mt-1 text-[11px] text-slate-400">
                                  Rejected: {rc.rejected_alternatives.slice(0, 2).join('; ')}
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Stockout Risk & Replenishment Warnings */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-rose-500" />
                  Stockout Risk Prevention Analysis
                </CardTitle>
                <CardDescription>
                  Facilities with inventory coverage below the configured safety-stock threshold.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {riskItems.filter(r => r.risk_level === 'critical' || r.risk_level === 'high').length === 0 ? (
                  <div className="p-4 text-center text-xs text-slate-500 bg-emerald-50/50 rounded-lg border border-emerald-100">
                    <CheckCircle className="w-6 h-6 text-emerald-500 mx-auto mb-1" />
                    All evaluated facilities satisfy minimum coverage requirements. Zero critical stockout risks.
                  </div>
                ) : (
                  <div className="space-y-2.5 max-h-64 overflow-y-auto pr-1">
                    {riskItems.filter(r => r.risk_level === 'critical' || r.risk_level === 'high').slice(0, 6).map((rk, idx) => (
                      <div key={idx} className="p-2.5 rounded-lg border border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
                        <div>
                          <div className="font-semibold text-slate-900">{rk.destination_name || rk.destination_id} &bull; {rk.sku_id}</div>
                          <div className="text-slate-500">
                            Cover: <strong>{rk.cover_days.toFixed(1)} days</strong> &bull; Gap: <strong>{rk.demand_gap.toLocaleString()} u</strong>
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge variant={rk.risk_level === 'critical' ? 'critical' : 'warning'}>
                            {rk.risk_level.toUpperCase()}
                          </Badge>
                          <div className="text-[11px] text-slate-400 mt-1">
                            Replenish: {rk.replenishment_need.toLocaleString()} u
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Info className="w-4 h-4 text-blue-500" />
                  Warehouse Eligibility & Allocation Policy
                </CardTitle>
                <CardDescription>
                  Configured rules enforced by the OR-Tools / HiGHS optimization engine.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-xs text-slate-600">
                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">1</span>
                  <div>
                    <strong className="text-slate-900">Dispatchable Stock Constraint:</strong> Allocations strictly bounded by net available stock: <code>dispatchable = max(0, on_hand - reserved - blocked)</code>.
                  </div>
                </div>
                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">2</span>
                  <div>
                    <strong className="text-slate-900">Corridor Permission:</strong> Shipments are only allocated along approved and active transportation lanes configured in the network graph.
                  </div>
                </div>
                <div className="flex items-start gap-2.5">
                  <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">3</span>
                  <div>
                    <strong className="text-slate-900">Service-First Optimization:</strong> Stage 1 maximizes demand fulfillment across all regions; Stage 2 minimizes total landed cost.
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* TAB 2: TOTAL LANDED COST & SHORTEST-ROUTE OPTIMIZATION */}
      {activeTab === 'landed_cost' && (
        <div className="space-y-6">
          {/* Corridor Selection & Cost Breakdown */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>Transportation & Shortest-Route Optimization</CardTitle>
                <CardDescription>
                  Select a Product and Destination Facility to compare candidate supply corridors, OSRM road distances, freight rates, and total landed cost.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="neutral">
                  Freight Model: Product Cost + Freight Rate + Handling
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Instructions banner when filters are not selected */}
              {(selectedSkuId === 'all' || selectedDestinationId === 'all') && (
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800 flex items-center gap-2">
                  <Info className="w-4 h-4 shrink-0 text-blue-600" />
                  <span>
                    Select a specific <strong>Product / SKU</strong> and <strong>Destination Facility</strong> in the Global Controls above to calculate road corridors and landed-cost breakdown.
                  </span>
                </div>
              )}

              {corridorLoading ? (
                <div className="py-8 text-center text-sm text-slate-500">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-blue-600" />
                  Querying routing engine and comparing corridor costs...
                </div>
              ) : corridorComparison ? (
                <div className="space-y-4">
                  {/* Recommended Corridor Card */}
                  {corridorComparison.recommended_corridor && (
                    <div className="p-4 bg-emerald-50/70 border border-emerald-200 rounded-lg">
                      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                        <div>
                          <Badge variant="success" size="sm">Recommended Shortest & Most Cost-Effective Corridor</Badge>
                          <h3 className="text-base font-bold text-slate-900 mt-1">
                            {corridorComparison.recommended_corridor.source_location_name} &rarr; {corridorComparison.recommended_corridor.destination_location_name}
                          </h3>
                          <p className="text-xs text-slate-600 mt-0.5">
                            Road Distance: <strong>{corridorComparison.recommended_corridor.distance_km ? `${Math.round(corridorComparison.recommended_corridor.distance_km)} km` : 'Calculated'}</strong> &bull; Lead Time: <strong>{corridorComparison.recommended_corridor.lead_time_days} days (~{(corridorComparison.recommended_corridor.lead_time_days * 24).toFixed(0)} hrs)</strong>
                          </p>
                        </div>
                        <div className="text-right">
                          <div className="text-xl font-bold text-emerald-800">
                            ₹{corridorComparison.recommended_corridor.total_delivered_cost_per_unit.toFixed(2)}
                            <span className="text-xs font-normal text-slate-500"> / unit landed</span>
                          </div>
                          <div className="text-xs text-slate-500">
                            Freight: ₹{corridorComparison.recommended_corridor.cost_rate_per_unit.toFixed(2)} &bull; Handling: ₹{corridorComparison.recommended_corridor.handling_cost_per_unit.toFixed(2)}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Corridor Comparison Table */}
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Source Facility</TableHead>
                          <TableHead>Destination</TableHead>
                          <TableHead>Road Distance (OSRM)</TableHead>
                          <TableHead>Est. Travel Time</TableHead>
                          <TableHead>Freight Rate / Unit</TableHead>
                          <TableHead>Handling Charges</TableHead>
                          <TableHead>Total Landed Cost / Unit</TableHead>
                          <TableHead>Dispatchable Stock</TableHead>
                          <TableHead>Corridor Feasibility</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {corridorComparison.alternatives.map((alt) => (
                          <TableRow key={alt.route_id} className={alt.is_feasible ? 'hover:bg-slate-50' : 'bg-slate-50/50 opacity-70'}>
                            <TableCell className="font-medium text-slate-900">
                              <div className="flex items-center gap-1.5">
                                <WarehouseIcon className="w-3.5 h-3.5 text-blue-600" />
                                {alt.source_location_name}
                              </div>
                              <div className="text-xs text-slate-400">{alt.source_location_type}</div>
                            </TableCell>

                            <TableCell>
                              {alt.destination_location_name}
                            </TableCell>

                            <TableCell className="font-medium text-slate-800">
                              <div>{alt.distance_km ? `${Math.round(alt.distance_km)} km` : `${alt.lead_time_days * 350} km`}</div>
                              <div className="text-[10px] text-slate-400 mt-0.5">
                                {alt.distance_source === 'osrm_open_street_map' ? (
                                  <span className="text-emerald-600 font-medium">OSRM Road Route</span>
                                ) : alt.distance_source === 'haversine_road_adjusted' ? (
                                  <span className="text-slate-500">Highway Est. (1.25x Winding)</span>
                                ) : alt.distance_source === 'transit_time_estimate' ? (
                                  <span className="text-amber-600">Transit Est. (350km/d)</span>
                                ) : (
                                  <span className="text-slate-400">Estimate</span>
                                )}
                              </div>
                            </TableCell>

                            <TableCell className="text-xs text-slate-600">
                              ~{(alt.lead_time_days * 24).toFixed(0)} hrs ({alt.lead_time_days}d)
                            </TableCell>

                            <TableCell className="text-xs font-medium text-slate-800">
                              ₹{alt.cost_rate_per_unit.toFixed(2)}
                            </TableCell>

                            <TableCell className="text-xs text-slate-600">
                              ₹{alt.handling_cost_per_unit.toFixed(2)}
                            </TableCell>

                            <TableCell className="font-bold text-slate-900">
                              ₹{alt.total_delivered_cost_per_unit.toFixed(2)}
                            </TableCell>

                            <TableCell>
                              <span className="font-semibold text-slate-800">{alt.dispatchable_stock.toLocaleString()} u</span>
                              {alt.unexpired_dispatchable_stock < alt.dispatchable_stock && (
                                <div className="text-[11px] text-amber-600">
                                  {alt.unexpired_dispatchable_stock} u unexpired
                                </div>
                              )}
                            </TableCell>

                            <TableCell>
                              {alt.is_feasible ? (
                                <Badge variant="success">Feasible</Badge>
                              ) : (
                                <div className="space-y-1">
                                  <Badge variant="critical">Infeasible</Badge>
                                  <div className="text-[11px] text-slate-500 line-clamp-1" title={alt.rejection_reasons.join(', ')}>
                                    {alt.rejection_reasons.join(', ') || 'Route or stock constraint'}
                                  </div>
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg">
                  Select a Product and Destination above to inspect candidate corridors and compare landed costs.
                </div>
              )}
            </CardContent>
          </Card>

          {/* Optimizer vs Baseline Heuristic Comparison */}
          {baselineComparison && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <GitCompare className="w-4 h-4 text-indigo-600" />
                  Baseline vs Optimizer Landed Cost & Service Comparison
                </CardTitle>
                <CardDescription>
                  Benchmarks the constrained service-first optimizer against the naive nearest-warehouse heuristic.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                    <span className="text-xs text-slate-500 uppercase font-semibold">Service Level</span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold text-emerald-700">{baselineComparison.optimizer.service_level_percent}%</span>
                      <span className="text-xs text-slate-400">vs {baselineComparison.baseline.service_level_percent}% baseline</span>
                    </div>
                    <div className="text-xs text-emerald-600 font-medium">
                      +{(baselineComparison.optimizer.service_level_percent - baselineComparison.baseline.service_level_percent).toFixed(1)}% improvement
                    </div>
                  </div>

                  <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                    <span className="text-xs text-slate-500 uppercase font-semibold">Fulfilled Demand</span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold text-slate-900">{baselineComparison.optimizer.fulfilled_demand_units.toLocaleString()} u</span>
                      <span className="text-xs text-slate-400">vs {baselineComparison.baseline.fulfilled_demand_units.toLocaleString()} u</span>
                    </div>
                    <div className="text-xs text-slate-500">
                      Unmet: {baselineComparison.optimizer.unmet_demand_units.toLocaleString()} u
                    </div>
                  </div>

                  <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                    <span className="text-xs text-slate-500 uppercase font-semibold">Transportation Cost</span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold text-slate-900">₹{Math.round(baselineComparison.optimizer.estimated_transport_cost).toLocaleString()}</span>
                      <span className="text-xs text-slate-400">vs ₹{Math.round(baselineComparison.baseline.estimated_transport_cost).toLocaleString()}</span>
                    </div>
                    <div className="text-xs text-slate-500">
                      {(() => {
                        const diff = Math.round(baselineComparison.baseline.estimated_transport_cost - baselineComparison.optimizer.estimated_transport_cost);
                        return diff >= 0 ? (
                          <span className="text-emerald-600 font-medium">Savings: ₹{diff.toLocaleString()}</span>
                        ) : (
                          <span className="text-amber-600 font-medium">Delta: +₹{Math.abs(diff).toLocaleString()} (Prioritized 100% Service)</span>
                        );
                      })()}
                    </div>
                  </div>

                  <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                    <span className="text-xs text-slate-500 uppercase font-semibold">Stock Utilization</span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-xl font-bold text-indigo-700">{baselineComparison.optimizer.stock_utilization_percent}%</span>
                      <span className="text-xs text-slate-400">vs {baselineComparison.baseline.stock_utilization_percent}%</span>
                    </div>
                    <div className="text-xs text-indigo-600 font-medium">
                      Balanced regional network allocation
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* TAB 3: FEFO & WAREHOUSE EXPIRY ALERTS (10-DAY & 30-DAY THRESHOLDS) */}
      {activeTab === 'fefo_expiry' && (
        <div className="space-y-6">
          {/* Expiry Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <SummaryCard
              title="EXPIRED STOCK"
              icon={XCircle}
              value={expirySummary ? `${expirySummary.expired_units.toLocaleString()} u` : 'Unavailable'}
              subtitle={`${expirySummary?.expired_batches || 0} batches expired`}
              badgeText={expirySummary && expirySummary.expired_batches > 0 ? 'Quarantine' : 'Zero Expired'}
              badgeVariant={expirySummary && expirySummary.expired_batches > 0 ? 'critical' : 'success'}
            />
            <SummaryCard
              title="EXPIRING &le; 10 DAYS"
              icon={AlertTriangle}
              value={expirySummary ? `${expirySummary.critical_units.toLocaleString()} u` : 'Unavailable'}
              subtitle={`${expirySummary?.critical_batches || 0} critical batches`}
              badgeText="Critical Alert"
              badgeVariant={expirySummary && expirySummary.critical_batches > 0 ? 'critical' : 'success'}
            />
            <SummaryCard
              title="EXPIRING 11-30 DAYS"
              icon={Clock}
              value={expirySummary ? `${expirySummary.high_risk_units.toLocaleString()} u` : 'Unavailable'}
              subtitle={`${expirySummary?.high_risk_batches || 0} warning batches`}
              badgeText="Warning Threshold"
              badgeVariant={expirySummary && expirySummary.high_risk_batches > 0 ? 'warning' : 'neutral'}
            />
            <SummaryCard
              title="QUANTITY AT RISK"
              icon={ShieldAlert}
              value={expirySummary ? `${(expirySummary.critical_units + expirySummary.high_risk_units).toLocaleString()} u` : 'Unavailable'}
              subtitle="&le; 30 days total"
              badgeText="FEFO Priority"
              badgeVariant={expirySummary && (expirySummary.critical_units + expirySummary.high_risk_units) > 0 ? 'warning' : 'success'}
            />
            <SummaryCard
              title="URGENT WAREHOUSES"
              icon={WarehouseIcon}
              value={`${urgentWarehouseCount} Facilities`}
              subtitle="With &le;30d expiry batches"
              badgeText={urgentWarehouseCount > 0 ? 'Inspect' : 'Clear'}
              badgeVariant={urgentWarehouseCount > 0 ? 'warning' : 'success'}
            />
            <SummaryCard
              title="VALUE AT RISK"
              icon={DollarSign}
              value="Unavailable"
              subtitle="Cost basis unconfigured"
              badgeText="Exposure"
              badgeVariant="neutral"
            />
          </div>

          {/* Interactive FEFO Allocator Test Widget */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600" />
                FEFO Batch Allocator (First-Expired, First-Out Engine)
              </CardTitle>
              <CardDescription>
                Simulates deterministic batch allocation prioritizing earliest valid expiry dates while strictly filtering out expired and blocked inventory.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-3">
                <div className="w-48">
                  <label className="block text-xs font-medium text-slate-700 mb-1">Target SKU</label>
                  <select
                    value={selectedSkuId}
                    onChange={(e) => setSelectedSkuId(e.target.value)}
                    className="w-full h-8 text-xs rounded border border-slate-300 bg-white px-2"
                  >
                    <option value="all">-- Select SKU --</option>
                    {products.map(p => (
                      <option key={p.sku_id} value={p.sku_id}>{p.sku_id} - {p.name}</option>
                    ))}
                  </select>
                </div>
                <div className="w-36">
                  <label className="block text-xs font-medium text-slate-700 mb-1">Demand Quantity</label>
                  <input
                    type="number"
                    min={1}
                    value={fefoDemandInput}
                    onChange={(e) => setFefoDemandInput(Number(e.target.value))}
                    className="w-full h-8 text-xs rounded border border-slate-300 px-2"
                  />
                </div>
                <div className="w-40">
                  <label className="block text-xs font-medium text-slate-700 mb-1">Min Shelf Life (Days)</label>
                  <input
                    type="number"
                    min={0}
                    value={fefoMinShelfLife}
                    onChange={(e) => setFefoMinShelfLife(Number(e.target.value))}
                    className="w-full h-8 text-xs rounded border border-slate-300 px-2"
                  />
                </div>
                <div className="pt-5">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleRunFEFOAllocation}
                    disabled={fefoLoading || selectedSkuId === 'all'}
                  >
                    {fefoLoading ? 'Allocating...' : 'Run FEFO Allocation'}
                  </Button>
                </div>
              </div>

              {fefoResult && (
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-2 mt-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-800">
                      FEFO Allocation Result for {fefoResult.sku_id}: {fefoResult.total_allocated} / {fefoResult.demand_quantity} units allocated
                    </span>
                    <Badge variant={fefoResult.is_fully_allocated ? 'success' : 'warning'}>
                      {fefoResult.is_fully_allocated ? 'Fully Allocated' : `${fefoResult.unmet_demand} u Unmet`}
                    </Badge>
                  </div>
                  {fefoResult.allocations.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse">
                        <thead>
                          <tr className="border-b border-slate-200 text-slate-500 font-medium">
                            <th className="py-1">Batch #</th>
                            <th className="py-1">Facility</th>
                            <th className="py-1">Expiry Date</th>
                            <th className="py-1">Days Left</th>
                            <th className="py-1">Allocated Qty</th>
                            <th className="py-1">Remaining in Batch</th>
                          </tr>
                        </thead>
                        <tbody>
                          {fefoResult.allocations.map((a, i) => (
                            <tr key={i} className="border-b border-slate-100">
                              <td className="py-1 font-mono font-medium">{a.batch_number || 'Default Batch'}</td>
                              <td className="py-1">{a.location_id}</td>
                              <td className="py-1">{a.expiry_date || 'No Date'}</td>
                              <td className="py-1">{a.days_remaining !== null ? `${a.days_remaining}d` : '-'}</td>
                              <td className="py-1 font-semibold text-emerald-700">{a.allocated_quantity} u</td>
                              <td className="py-1 text-slate-500">{a.remaining_after_allocation} u</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="text-slate-500">No eligible unexpired batches with &ge; {fefoMinShelfLife} days shelf life available.</p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Near-Expiry Redistribution Recommendations */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>Near-Expiry Redistribution Intelligence</CardTitle>
                <CardDescription>
                  Matches near-expiry batches at source warehouses with destinations that have demand gaps, verifying arrival shelf life and permitted corridors.
                </CardDescription>
              </div>
              <Badge variant="neutral">
                {redistributions?.recommendations_count || 0} Proposals Generated
              </Badge>
            </CardHeader>
            <CardContent>
              {!redistributions || redistributions.recommendations.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500 bg-slate-50 rounded-lg border border-slate-200">
                  <CheckCircle className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                  No near-expiry stock requires emergency inter-facility redistribution at this time.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Product / SKU</TableHead>
                        <TableHead>Source Warehouse</TableHead>
                        <TableHead>Destination Demand</TableHead>
                        <TableHead>Batch & Expiry</TableHead>
                        <TableHead>Recommended Qty</TableHead>
                        <TableHead>Shelf Life at Arrival</TableHead>
                        <TableHead>Est. Freight Cost</TableHead>
                        <TableHead>Priority Rationale</TableHead>
                        <TableHead>Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {redistributions.recommendations.map((rec) => (
                        <TableRow key={rec.recommendation_id} className="hover:bg-slate-50">
                          <TableCell className="font-medium text-slate-900">
                            <div>{rec.sku_id}</div>
                            <div className="text-xs text-slate-500">{rec.product_name || 'Product'}</div>
                          </TableCell>

                          <TableCell>
                            <div className="flex items-center gap-1">
                              <WarehouseIcon className="w-3.5 h-3.5 text-blue-600" />
                              <span>{rec.source_location_name || rec.source_location_id}</span>
                            </div>
                            <div className="text-xs text-slate-500">Available: {rec.source_available_units} u</div>
                          </TableCell>

                          <TableCell>
                            <div className="flex items-center gap-1">
                              <MapPin className="w-3.5 h-3.5 text-slate-400" />
                              <span>{rec.destination_location_name || rec.destination_location_id}</span>
                            </div>
                            <div className="text-xs text-slate-500">Unmet Gap: {rec.destination_unmet_demand} u</div>
                          </TableCell>

                          <TableCell>
                            <div className="font-mono text-xs">{rec.batch_number || 'Batch'}</div>
                            <div className="text-xs text-slate-500">{rec.expiry_date} ({rec.days_remaining}d left)</div>
                          </TableCell>

                          <TableCell className="font-bold text-slate-900">
                            {rec.recommended_quantity.toLocaleString()} u
                          </TableCell>

                          <TableCell>
                            <Badge variant={rec.shelf_life_days_at_arrival > 30 ? 'success' : 'warning'}>
                              {rec.shelf_life_days_at_arrival} days at arrival
                            </Badge>
                            <div className="text-[11px] text-slate-400 mt-0.5">Lead time: {rec.lead_time_days}d</div>
                          </TableCell>

                          <TableCell className="text-xs font-semibold text-slate-800">
                            ₹{Math.round(rec.estimated_transport_cost).toLocaleString()}
                          </TableCell>

                          <TableCell className="max-w-xs text-xs text-slate-600">
                            {rec.rationale}
                          </TableCell>

                          <TableCell>
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleProposeRedistribution(rec)}
                              leftIcon={<Send className="w-3.5 h-3.5" />}
                            >
                              Propose
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Expiry Batch Health Table */}
          <Card>
            <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-3">
              <div>
                <CardTitle>Warehouse Batch Expiry Register</CardTitle>
                <CardDescription>
                  Detailed batch-level inventory showing days remaining, alert severity, and dispatchable quantities.
                </CardDescription>
              </div>

              {/* Table Filters */}
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={expiryCategoryFilter}
                  onChange={(e) => setExpiryCategoryFilter(e.target.value)}
                  className="h-8 text-xs rounded border border-slate-300 bg-white px-2"
                >
                  <option value="all">All Alert Severities</option>
                  <option value="expired">Expired (&lt;0d)</option>
                  <option value="critical">Critical (&le;10d)</option>
                  <option value="warning">Warning (11-30d)</option>
                  <option value="upcoming">Upcoming (31-60d)</option>
                  <option value="healthy">Healthy (&gt;60d)</option>
                  <option value="unknown">Missing Expiry</option>
                </select>

                <select
                  value={expiryWarehouseFilter}
                  onChange={(e) => setExpiryWarehouseFilter(e.target.value)}
                  className="h-8 text-xs rounded border border-slate-300 bg-white px-2"
                >
                  <option value="all">All Warehouses</option>
                  {sourceWarehouses.map(w => (
                    <option key={w.location_id} value={w.location_id}>{w.name}</option>
                  ))}
                </select>

                <select
                  value={expirySkuFilter}
                  onChange={(e) => setExpirySkuFilter(e.target.value)}
                  className="h-8 text-xs rounded border border-slate-300 bg-white px-2"
                >
                  <option value="all">All SKUs</option>
                  {products.map(p => (
                    <option key={p.sku_id} value={p.sku_id}>{p.sku_id} - {p.name}</option>
                  ))}
                </select>
              </div>
            </CardHeader>
            <CardContent>
              {filteredExpiryItems.length === 0 ? (
                <EmptyState
                  icon={ShieldAlert}
                  title="No Batches Match Current Expiry Filters"
                  description="Adjust alert severity, SKU or warehouse filter to inspect other inventory batches."
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Warehouse & Region</TableHead>
                        <TableHead>Product / SKU</TableHead>
                        <TableHead>Batch / Lot #</TableHead>
                        <TableHead>Dispatchable Qty</TableHead>
                        <TableHead>Expiry Date</TableHead>
                        <TableHead>Days Remaining</TableHead>
                        <TableHead>Alert Severity</TableHead>
                        <TableHead>Recommended Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredExpiryItems.slice(0, 15).map((item, idx) => {
                        const loc = locations.find(l => l.location_id === item.location_id);
                        return (
                          <TableRow key={item.snapshot_id || idx} className="hover:bg-slate-50">
                            <TableCell className="font-medium text-slate-900">
                              <div className="flex items-center gap-1.5">
                                <WarehouseIcon className="w-3.5 h-3.5 text-blue-600" />
                                {item.location_name || item.location_id}
                              </div>
                              <div className="text-xs text-slate-500">{loc?.region || 'Region'}</div>
                            </TableCell>

                            <TableCell>
                              <div className="font-medium text-slate-900">{item.sku_id}</div>
                              <div className="text-xs text-slate-500">{item.product_name || 'SKU'}</div>
                            </TableCell>

                            <TableCell className="font-mono text-xs">
                              {item.batch_number || 'UNBATCHED'}
                            </TableCell>

                            <TableCell className="font-semibold text-slate-900">
                              {item.dispatchable_quantity.toLocaleString()} u
                              <div className="text-[11px] text-slate-400 font-normal">OH: {item.on_hand} u</div>
                            </TableCell>

                            <TableCell className="text-xs text-slate-700">
                              {item.expiry_date || 'No Expiry Recorded'}
                            </TableCell>

                            <TableCell className="text-xs font-semibold">
                              {item.days_remaining !== null && item.days_remaining !== undefined ? (
                                <span className={item.days_remaining <= 10 ? 'text-rose-600' : item.days_remaining <= 30 ? 'text-amber-600' : 'text-slate-800'}>
                                  {item.days_remaining} days
                                </span>
                              ) : (
                                <span className="text-slate-400">Unavailable</span>
                              )}
                            </TableCell>

                            <TableCell>
                              {getExpiryBadge(item.risk_category, item.days_remaining)}
                            </TableCell>

                            <TableCell className="text-xs text-slate-600">
                              {item.risk_category === 'expired' ? (
                                <span className="text-rose-700 font-medium">Quarantine & Dispose</span>
                              ) : item.days_remaining !== null && item.days_remaining !== undefined && item.days_remaining <= 10 ? (
                                <span className="text-rose-700 font-medium">Emergency FEFO Dispatch / Transfer</span>
                              ) : item.days_remaining !== null && item.days_remaining !== undefined && item.days_remaining <= 30 ? (
                                <span className="text-amber-700 font-medium">Prioritize Outbound Allocations</span>
                              ) : (
                                <span className="text-slate-500">Normal Rotation</span>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB 4: EXCESS INVENTORY REDUCTION & REGIONAL DEMAND FORECASTING */}
      {activeTab === 'excess_forecast' && (
        <div className="space-y-6">
          {/* Excess Inventory Reduction Table */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>Excess Inventory Reduction Analysis</CardTitle>
                <CardDescription>
                  Identifies surplus finished goods where warehouse stock exceeds demand forecast coverage and safety-stock buffers.
                </CardDescription>
              </div>
              <Badge variant="neutral">
                {riskItems.filter(r => (r.excess_stock || 0) > 0).length} Surplus Instances
              </Badge>
            </CardHeader>
            <CardContent>
              {riskItems.filter(r => (r.excess_stock || 0) > 0).length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500 bg-emerald-50/50 rounded-lg border border-emerald-100">
                  <CheckCircle className="w-5 h-5 text-emerald-500 mx-auto mb-1" />
                  Inventory levels are lean and balanced across all facilities. No potential excess detected.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SKU & Product</TableHead>
                        <TableHead>Facility & Region</TableHead>
                        <TableHead>On-Hand / Reserved / Blocked</TableHead>
                        <TableHead>Dispatchable Stock</TableHead>
                        <TableHead>Daily Forecast Rate</TableHead>
                        <TableHead>Cover Days</TableHead>
                        <TableHead>Safety Target</TableHead>
                        <TableHead>Potential Excess</TableHead>
                        <TableHead>Action Recommendation</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {riskItems.filter(r => (r.excess_stock || 0) > 0).map((item, idx) => (
                        <TableRow key={idx} className="hover:bg-slate-50">
                          <TableCell className="font-medium text-slate-900">
                            <div>{item.sku_id}</div>
                            <div className="text-xs text-slate-500">{item.product_name || 'SKU'}</div>
                          </TableCell>

                          <TableCell>
                            <div className="font-medium text-slate-800">{item.destination_name || item.destination_id}</div>
                          </TableCell>

                          <TableCell className="text-xs text-slate-600">
                            OH: {item.on_hand} &bull; Res: {item.reserved} &bull; Blk: {item.blocked}
                          </TableCell>

                          <TableCell className="font-semibold text-slate-900">
                            {item.dispatchable_stock.toLocaleString()} u
                          </TableCell>

                          <TableCell className="text-xs text-slate-700">
                            {item.daily_forecast_rate.toFixed(1)} u/day
                          </TableCell>

                          <TableCell className="font-medium text-amber-700">
                            {item.cover_days > 90 ? '> 90 days' : `${item.cover_days.toFixed(1)} days`}
                          </TableCell>

                          <TableCell className="text-xs text-slate-600">
                            {item.safety_stock_target} u
                          </TableCell>

                          <TableCell className="font-bold text-amber-700">
                            {(item.excess_stock || 0).toLocaleString()} u
                          </TableCell>

                          <TableCell className="text-xs text-slate-600">
                            <span className="text-blue-700 font-medium">Eligible for inter-facility redistribution</span>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* P1 & P2: ML Model Evaluation and Actual vs Predicted Demand Time-Series Chart */}
          <ActualVsPredictedDemandChart
            evaluation={forecastEvaluation}
            loading={evaluationLoading}
            selectedSkuId={selectedSkuId}
            selectedDestinationId={selectedDestinationId}
            onSkuChange={setSelectedSkuId}
            onDestinationChange={setSelectedDestinationId}
            products={products}
            locations={locations}
          />

          {/* Regional Demand Forecasting Table */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <div>
                <CardTitle>Regional Demand Forecasting & Accuracy Metrics</CardTitle>
                <CardDescription>
                  Forecasted demand by destination facility with forecasting method, data sufficiency status, and error evaluations.
                </CardDescription>
              </div>
              <Badge variant="neutral">
                {forecasts.length} Forecast Points
              </Badge>
            </CardHeader>
            <CardContent>
              {forecasts.length === 0 ? (
                <EmptyState
                  icon={TrendingUp}
                  title="No Demand Forecasts Available"
                  description="Import historical sales data or check sales history dataset to generate demand forecasts."
                />
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SKU & Product</TableHead>
                        <TableHead>Destination & Region</TableHead>
                        <TableHead>Horizon</TableHead>
                        <TableHead>Daily Forecast Rate</TableHead>
                        <TableHead>Total Forecast Demand</TableHead>
                        <TableHead>Method Used</TableHead>
                        <TableHead>Data Sufficiency</TableHead>
                        <TableHead>Model Accuracy (WAPE)</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {forecasts.slice(0, 15).map((fc, idx) => {
                        const loc = locations.find(l => l.location_id === fc.destination_id);
                        return (
                          <TableRow key={idx} className="hover:bg-slate-50">
                            <TableCell className="font-medium text-slate-900">
                              <div>{fc.sku_id}</div>
                              <div className="text-xs text-slate-500">{fc.product_name || 'SKU'}</div>
                            </TableCell>

                            <TableCell>
                              <div className="flex items-center gap-1.5">
                                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                                <span>{fc.destination_name || fc.destination_id}</span>
                              </div>
                              <div className="text-xs text-slate-500">{loc?.region || 'Region'}</div>
                            </TableCell>

                            <TableCell className="text-xs text-slate-600">
                              {fc.horizon_days} Days
                            </TableCell>

                            <TableCell className="text-xs font-semibold text-slate-800">
                              {fc.daily_forecast_rate.toFixed(1)} u/day
                            </TableCell>

                            <TableCell className="font-bold text-slate-900">
                              {fc.total_forecast_demand.toLocaleString()} units
                            </TableCell>

                            <TableCell className="text-xs text-slate-600">
                              <Badge variant="neutral">{fc.forecast_method || 'Rolling 7d'}</Badge>
                            </TableCell>

                            <TableCell>
                              <Badge variant={fc.data_sufficiency === 'sufficient' ? 'success' : 'warning'}>
                                {fc.data_sufficiency}
                              </Badge>
                            </TableCell>

                            <TableCell className="text-xs text-slate-700">
                              {fc.wape !== null && fc.wape !== undefined ? (
                                <span>WAPE: {(fc.wape * 100).toFixed(1)}%</span>
                              ) : (
                                <span className="text-slate-400">Baseline Rate</span>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* WHAT-IF SCENARIO SIMULATION MODAL */}
      {showSimModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-blue-600" />
                <h2 className="text-lg font-bold text-slate-900">What-If Scenario Simulation</h2>
                <Badge variant="neutral">In-Memory</Badge>
              </div>
              <button
                type="button"
                onClick={() => setShowSimModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-900">
              <strong>Zero-Impact Simulation:</strong> Runs the linear optimizer in-memory with scenario multipliers. Physical inventory, reservations, and shipment records are never mutated.
            </div>

            {/* Simulation Parameter Controls */}
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Demand Multiplier: {simDemandMult}x
                </label>
                <input
                  type="range"
                  min={0.5}
                  max={2.0}
                  step={0.1}
                  value={simDemandMult}
                  onChange={(e) => setSimDemandMult(Number(e.target.value))}
                  className="w-full accent-blue-600"
                />
                <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                  <span>0.5x</span>
                  <span>1.0x</span>
                  <span>2.0x</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Freight Cost Multiplier: {simFreightMult}x
                </label>
                <input
                  type="range"
                  min={0.5}
                  max={2.5}
                  step={0.1}
                  value={simFreightMult}
                  onChange={(e) => setSimFreightMult(Number(e.target.value))}
                  className="w-full accent-blue-600"
                />
                <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                  <span>0.5x</span>
                  <span>1.0x</span>
                  <span>2.5x</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Warehouse Stock Multiplier: {simStockMult}x
                </label>
                <input
                  type="range"
                  min={0.5}
                  max={1.5}
                  step={0.1}
                  value={simStockMult}
                  onChange={(e) => setSimStockMult(Number(e.target.value))}
                  className="w-full accent-blue-600"
                />
                <div className="flex justify-between text-[10px] text-slate-400 mt-0.5">
                  <span>0.5x</span>
                  <span>1.0x</span>
                  <span>1.5x</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Horizon (Days)
                </label>
                <select
                  value={simHorizon}
                  onChange={(e) => setSimHorizon(Number(e.target.value))}
                  className="w-full h-8 text-xs rounded border border-slate-300 px-2"
                >
                  <option value={7}>7 Days</option>
                  <option value={14}>14 Days</option>
                  <option value={30}>30 Days</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setShowSimModal(false)}
              >
                Close
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleRunSimulation}
                disabled={simulating}
                leftIcon={<Sparkles className="w-3.5 h-3.5" />}
              >
                {simulating ? 'Simulating Solver...' : 'Execute What-If Simulation'}
              </Button>
            </div>

            {/* Simulation Results Comparison */}
            {simResult && (
              <div className="space-y-4 pt-3 border-t border-slate-200">
                <h3 className="text-sm font-bold text-slate-900">Simulation Impact vs Baseline</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
                    <span className="text-slate-500 font-medium">Service Level</span>
                    <div className="text-lg font-bold text-slate-900">
                      {simResult.simulated_plan.service_level_percent}%
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Baseline: {simResult.baseline_plan.service_level_percent}%
                    </div>
                  </div>

                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
                    <span className="text-slate-500 font-medium">Fulfilled Units</span>
                    <div className="text-lg font-bold text-slate-900">
                      {simResult.simulated_plan.fulfilled_demand_units?.toLocaleString()} u
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Baseline: {simResult.baseline_plan.fulfilled_demand_units?.toLocaleString()} u
                    </div>
                  </div>

                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
                    <span className="text-slate-500 font-medium">Unmet Shortage</span>
                    <div className="text-lg font-bold text-slate-900">
                      {simResult.simulated_plan.unmet_demand_units?.toLocaleString()} u
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Baseline: {simResult.baseline_plan.unmet_demand_units?.toLocaleString()} u
                    </div>
                  </div>

                  <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
                    <span className="text-slate-500 font-medium">Total Landed Cost</span>
                    <div className="text-lg font-bold text-slate-900">
                      ₹{Math.round(simResult.simulated_plan.estimated_transport_cost || 0).toLocaleString()}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      Baseline: ₹{Math.round(simResult.baseline_plan.estimated_transport_cost || 0).toLocaleString()}
                    </div>
                  </div>
                </div>

                {/* Impact Metrics Table */}
                {simResult.impact_analysis && simResult.impact_analysis.length > 0 && (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-500 font-medium">
                          <th className="py-1">Metric</th>
                          <th className="py-1">Baseline</th>
                          <th className="py-1">Simulated</th>
                          <th className="py-1">Delta</th>
                          <th className="py-1">Impact</th>
                        </tr>
                      </thead>
                      <tbody>
                        {simResult.impact_analysis.map((m, idx) => (
                          <tr key={idx} className="border-b border-slate-100">
                            <td className="py-1 font-medium">{m.metric}</td>
                            <td className="py-1">{m.baseline_value} {m.unit}</td>
                            <td className="py-1 font-semibold">{m.simulated_value} {m.unit}</td>
                            <td className="py-1">
                              {m.delta_value > 0 ? `+${m.delta_value}` : m.delta_value} ({m.delta_percent}%)
                            </td>
                            <td className="py-1">
                              <Badge variant={m.impact_direction === 'better' ? 'success' : m.impact_direction === 'worse' ? 'critical' : 'neutral'}>
                                {m.impact_direction}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default DistributionIntelligencePage;
