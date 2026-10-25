import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GitCompare,
  RefreshCw,
  ShieldCheck,
  Cpu,
  Sliders,
  MapPin,
  Activity,
  CheckCircle2,
  Play,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
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
  getPlanComparison,
  getSolverBenchmark,
  compareCorridors,
  simulateWhatIfScenario,
  getOperationalPerformanceMetrics,
  getInventoryRisks,
} from '../services/api';
import type {
  PlanningRunSummary,
  PlanComparisonResponse,
  SolverBenchmarkComparisonResponse,
  CorridorComparisonResponse,
  ScenarioSimulationResponse,
  OperationalPerformanceResponse,
  RiskAnalysisItem,
} from '../types/api';

type TabMode = 'benchmark' | 'corridors' | 'simulation' | 'performance';

export const PlanComparisonPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabMode>('benchmark');

  // --- Tab 1: Plan & Benchmark State ---
  const [runs, setRuns] = useState<PlanningRunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [comparison, setComparison] = useState<PlanComparisonResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Live 3-Way Solver Benchmark state
  const [benchmarkLoading, setBenchmarkLoading] = useState<boolean>(false);
  const [benchmarkData, setBenchmarkData] = useState<SolverBenchmarkComparisonResponse | null>(null);
  const [benchmarkError, setBenchmarkError] = useState<string | null>(null);

  // --- Tab 2: Corridor Comparator State ---
  const [networkRisks, setNetworkRisks] = useState<RiskAnalysisItem[]>([]);
  const [selectedDestinationId, setSelectedDestinationId] = useState<string>('');
  const [selectedSkuId, setSelectedSkuId] = useState<string>('');
  const [corridorData, setCorridorData] = useState<CorridorComparisonResponse | null>(null);
  const [corridorLoading, setCorridorLoading] = useState<boolean>(false);
  const [corridorError, setCorridorError] = useState<string | null>(null);

  // --- Tab 3: What-If Scenario State ---
  const [simDemandMult, setSimDemandMult] = useState<number>(1.2);
  const [simFreightMult, setSimFreightMult] = useState<number>(1.15);
  const [simStockMult, setSimStockMult] = useState<number>(0.85);
  const [simHorizonDays, setSimHorizonDays] = useState<number>(7);
  const [simulationData, setSimulationData] = useState<ScenarioSimulationResponse | null>(null);
  const [simulationLoading, setSimulationLoading] = useState<boolean>(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);

  // --- Tab 4: Operational Performance State ---
  const [perfData, setPerfData] = useState<OperationalPerformanceResponse | null>(null);
  const [perfLoading, setPerfLoading] = useState<boolean>(false);
  const [perfError, setPerfError] = useState<string | null>(null);

  const loadRuns = async () => {
    setLoading(true);
    setError(null);
    try {
      const runList = await getPlanningRuns(10, 0);
      setRuns(runList);
      if (runList.length > 0) {
        const defaultId = runList[0].run_id;
        setSelectedRunId(defaultId);
        await loadComparisonForRun(defaultId);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load planning runs');
    } finally {
      setLoading(false);
    }
  };

  const loadComparisonForRun = async (runId: string) => {
    setLoading(true);
    setError(null);
    try {
      const comp = await getPlanComparison(runId);
      setComparison(comp);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to load comparison for ${runId}`);
    } finally {
      setLoading(false);
    }
  };

  const runLiveSolverBenchmark = async () => {
    setBenchmarkLoading(true);
    setBenchmarkError(null);
    try {
      const data = await getSolverBenchmark({ horizon_days: 7, objective_strategy: 'service_first' });
      setBenchmarkData(data);
    } catch (err: unknown) {
      setBenchmarkError(err instanceof Error ? err.message : 'Failed to execute solver benchmark');
    } finally {
      setBenchmarkLoading(false);
    }
  };

  // Load candidate destinations & SKUs from risk analysis for Corridor Comparator
  const loadNetworkEntities = async () => {
    try {
      const res = await getInventoryRisks(7);
      if (res && res.items && res.items.length > 0) {
        setNetworkRisks(res.items);
        setSelectedDestinationId(res.items[0].destination_id);
        setSelectedSkuId(res.items[0].sku_id);
      }
    } catch {
      // Fallback
    }
  };

  const handleCompareCorridors = async (destId?: string, skuId?: string) => {
    const targetDest = destId || selectedDestinationId;
    const targetSku = skuId || selectedSkuId;
    if (!targetDest || !targetSku) return;

    setCorridorLoading(true);
    setCorridorError(null);
    try {
      const data = await compareCorridors(targetDest, targetSku, 7);
      setCorridorData(data);
    } catch (err: unknown) {
      setCorridorError(err instanceof Error ? err.message : 'Failed to compare corridors');
    } finally {
      setCorridorLoading(false);
    }
  };

  const handleRunSimulation = async () => {
    setSimulationLoading(true);
    setSimulationError(null);
    try {
      const res = await simulateWhatIfScenario({
        horizon_days: simHorizonDays,
        demand_multiplier: simDemandMult,
        freight_rate_multiplier: simFreightMult,
        source_stock_multiplier: simStockMult,
        disrupted_route_ids: [],
        solver_type: 'ortools',
      });
      setSimulationData(res);
    } catch (err: unknown) {
      setSimulationError(err instanceof Error ? err.message : 'Failed to execute what-if simulation');
    } finally {
      setSimulationLoading(false);
    }
  };

  const loadOperationalPerformance = async () => {
    setPerfLoading(true);
    setPerfError(null);
    try {
      const res = await getOperationalPerformanceMetrics();
      setPerfData(res);
    } catch (err: unknown) {
      setPerfError(err instanceof Error ? err.message : 'Failed to load operational performance metrics');
    } finally {
      setPerfLoading(false);
    }
  };

  useEffect(() => {
    loadRuns();
    loadNetworkEntities();
  }, []);

  useEffect(() => {
    if (activeTab === 'corridors' && selectedDestinationId && selectedSkuId && !corridorData) {
      handleCompareCorridors(selectedDestinationId, selectedSkuId);
    } else if (activeTab === 'performance' && !perfData) {
      loadOperationalPerformance();
    }
  }, [activeTab, selectedDestinationId, selectedSkuId]);

  const handleSelectRun = (runId: string) => {
    setSelectedRunId(runId);
    loadComparisonForRun(runId);
  };

  const comparisonMetricsDefinition = [
    {
      metric: 'Customer Demand Fill Rate (%)',
      description: 'Fulfilled customer demand / total modeled demand under identical cutoff rules.',
      formula: '(fulfilled_units / modeled_demand) × 100',
    },
    {
      metric: 'Unmet Demand Shortfall (Cases)',
      description: 'Demand that could not be served by current stock or feasible replenishment.',
      formula: '∑ max(0, demand − existing_stock − transfers)',
    },
    {
      metric: 'Estimated Transport Cost (₹)',
      description: 'Calculated using identical carrier rates per lane in INR (₹), not straight-line distance.',
      formula: '∑ (cost_rate × units_shipped)',
    },
    {
      metric: 'Stock Utilization Efficiency (%)',
      description: 'Percentage of dispatchable warehouse inventory productively allocated.',
      formula: '(allocated_stock / total_dispatchable) × 100',
    },
    {
      metric: 'Hard Constraint Violations',
      description: 'Allocations exceeding source stock, forbidden routes, or missed delivery cutoffs.',
      formula: 'Zero-tolerance audit (0 hard violations allowed)',
    },
    {
      metric: 'Solver Execution Time (Seconds)',
      description: 'Algorithm runtime to reach provable global optimality vs heuristic.',
      formula: 'Google OR-Tools GLOP vs SciPy HiGHS simplex vs greedy loop',
    },
  ];

  // Unique options for Corridor Comparator
  const uniqueDestinations = Array.from(
    new Map(networkRisks.map((item) => [item.destination_id, item.destination_name || item.destination_id])).entries()
  );
  const uniqueSkus = Array.from(
    new Map(networkRisks.map((item) => [item.sku_id, item.product_name || item.sku_id])).entries()
  );

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">Plan Comparison & Route Intelligence</h1>
            <Badge variant="primary" size="sm">Distribution Intelligence</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Audit multi-warehouse optimization against baselines, evaluate alternative corridors, and simulate what-if network disruptions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {activeTab === 'benchmark' && runs.length > 0 && (
            <select
              value={selectedRunId}
              onChange={(e) => handleSelectRun(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              {runs.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  Plan {r.run_id} ({r.service_level_percent.toFixed(1)}% service)
                </option>
              ))}
            </select>
          )}

          {activeTab === 'benchmark' && (
            <Button
              variant="outline"
              leftIcon={<RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />}
              onClick={() => selectedRunId && loadComparisonForRun(selectedRunId)}
              disabled={loading || !selectedRunId}
            >
              Refresh Plan
            </Button>
          )}

          {activeTab === 'benchmark' && (
            <Button
              variant="primary"
              leftIcon={<Cpu className={`w-4 h-4 ${benchmarkLoading ? 'animate-spin' : ''}`} />}
              onClick={runLiveSolverBenchmark}
              disabled={benchmarkLoading}
            >
              {benchmarkLoading ? 'Solving...' : 'Run 3-Way Solver Benchmark'}
            </Button>
          )}
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-200">
        <button
          onClick={() => setActiveTab('benchmark')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'benchmark'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <GitCompare className="w-4 h-4" />
          Plan Benchmark & Solvers
        </button>

        <button
          onClick={() => setActiveTab('corridors')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'corridors'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <MapPin className="w-4 h-4" />
          Corridor & Route Alternatives
        </button>

        <button
          onClick={() => setActiveTab('simulation')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'simulation'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Sliders className="w-4 h-4" />
          What-If Scenario Simulation
        </button>

        <button
          onClick={() => setActiveTab('performance')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'performance'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Activity className="w-4 h-4" />
          Operational Performance
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: Plan Benchmark & 3-Way Solvers (Preserved)                         */}
      {/* ========================================================================= */}
      {activeTab === 'benchmark' && (
        <div className="space-y-6">
          {error && (
            <Alert variant="error" title="Comparison Load Error">
              {error}
            </Alert>
          )}

          {benchmarkError && (
            <Alert variant="error" title="Solver Benchmark Error">
              {benchmarkError}
            </Alert>
          )}

          {/* 3-Way Solver Benchmark Section */}
          {benchmarkData && (
            <Card className="border-2 border-indigo-200 bg-gradient-to-br from-indigo-50/40 via-white to-blue-50/30 p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-indigo-100 gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <Cpu className="w-5 h-5 text-indigo-600" />
                    <h2 className="text-lg font-bold text-slate-900">Live 3-Way Optimization Benchmark</h2>
                    <Badge variant="primary">Deterministic Inputs</Badge>
                  </div>
                  <p className="text-xs text-slate-600 mt-1">
                    Deterministic comparison across identical snapshot, demand requirements ({benchmarkData.total_demand_units.toLocaleString()} cases), and transit cutoffs.
                  </p>
                </div>
                <div className="text-xs font-mono bg-white px-3 py-1.5 rounded-lg border border-indigo-200 text-indigo-900">
                  Horizon: {benchmarkData.horizon_days} Days
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {/* Column 1: Google OR-Tools */}
                <div className="p-4 rounded-xl border-2 border-blue-500 bg-white shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-slate-900">Google OR-Tools</h3>
                      <span className="text-[11px] text-blue-600 font-medium">GLOP (Primary LP)</span>
                    </div>
                    <Badge variant="primary" size="sm">PRODUCTION</Badge>
                  </div>

                  <div className="space-y-2 text-xs pt-1">
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Service Level:</span>
                      <span className="text-base font-bold text-blue-700">
                        {benchmarkData.ortools_metrics.service_level_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Fulfilled Demand:</span>
                      <span className="font-semibold text-slate-800">
                        {benchmarkData.ortools_metrics.fulfilled_demand_units.toLocaleString()} cases
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Unmet Shortfall:</span>
                      <span className="font-semibold text-rose-600">
                        {benchmarkData.ortools_metrics.unmet_demand_units.toLocaleString()} cases
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Transport Freight:</span>
                      <span className="font-bold font-mono text-slate-900">
                        ₹{benchmarkData.ortools_metrics.estimated_transport_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Stock Utilization:</span>
                      <span className="font-medium text-slate-800">
                        {benchmarkData.ortools_metrics.stock_utilization_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Violations:</span>
                      <span className="font-medium text-emerald-700">
                        {benchmarkData.ortools_metrics.constraint_violations_count}
                      </span>
                    </div>
                    <div className="flex justify-between items-center pt-1 text-[11px]">
                      <span className="text-slate-500">Solve Time:</span>
                      <span className="font-mono text-slate-700 font-semibold">
                        {(benchmarkData.ortools_metrics.solve_time_seconds * 1000).toFixed(1)} ms
                      </span>
                    </div>
                  </div>
                </div>

                {/* Column 2: SciPy HiGHS */}
                <div className="p-4 rounded-xl border border-slate-300 bg-white shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-slate-800">SciPy HiGHS</h3>
                      <span className="text-[11px] text-slate-500 font-medium">Dual Simplex (Benchmark LP)</span>
                    </div>
                    <Badge variant="neutral" size="sm">VALIDATED</Badge>
                  </div>

                  <div className="space-y-2 text-xs pt-1">
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Service Level:</span>
                      <span className="text-base font-bold text-slate-900">
                        {benchmarkData.highs_metrics.service_level_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Fulfilled Demand:</span>
                      <span className="font-semibold text-slate-800">
                        {benchmarkData.highs_metrics.fulfilled_demand_units.toLocaleString()} cases
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Unmet Shortfall:</span>
                      <span className="font-semibold text-rose-600">
                        {benchmarkData.highs_metrics.unmet_demand_units.toLocaleString()} cases
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Transport Freight:</span>
                      <span className="font-bold font-mono text-slate-900">
                        ₹{benchmarkData.highs_metrics.estimated_transport_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Stock Utilization:</span>
                      <span className="font-medium text-slate-800">
                        {benchmarkData.highs_metrics.stock_utilization_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-100">
                      <span className="text-slate-500">Violations:</span>
                      <span className="font-medium text-emerald-700">
                        {benchmarkData.highs_metrics.constraint_violations_count}
                      </span>
                    </div>
                    <div className="flex justify-between items-center pt-1 text-[11px]">
                      <span className="text-slate-500">Solve Time:</span>
                      <span className="font-mono text-slate-700 font-semibold">
                        {(benchmarkData.highs_metrics.solve_time_seconds * 1000).toFixed(1)} ms
                      </span>
                    </div>
                  </div>
                </div>

                {/* Column 3: Nearest-Source Baseline */}
                <div className="p-4 rounded-xl border border-slate-300 bg-slate-50/70 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-sm font-bold text-slate-700">Nearest-Source</h3>
                      <span className="text-[11px] text-slate-500 font-medium">Greedy Heuristic Baseline</span>
                    </div>
                    <Badge variant="neutral" size="sm">BASELINE</Badge>
                  </div>

                  <div className="space-y-2 text-xs pt-1">
                    <div className="flex justify-between items-center py-1 border-b border-slate-200">
                      <span className="text-slate-500">Service Level:</span>
                      <span className="text-base font-bold text-slate-700">
                        {benchmarkData.baseline_metrics.service_level_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200">
                      <span className="text-slate-500">Fulfilled Demand:</span>
                      <span className="font-semibold text-slate-800">
                        {benchmarkData.baseline_metrics.fulfilled_demand_units.toLocaleString()} cases
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200">
                      <span className="text-slate-500">Unmet Shortfall:</span>
                      <span className="font-semibold text-rose-600">
                        {benchmarkData.baseline_metrics.unmet_demand_units.toLocaleString()} cases
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200">
                      <span className="text-slate-500">Transport Freight:</span>
                      <span className="font-bold font-mono text-slate-900">
                        ₹{benchmarkData.baseline_metrics.estimated_transport_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200">
                      <span className="text-slate-500">Stock Utilization:</span>
                      <span className="font-medium text-slate-800">
                        {benchmarkData.baseline_metrics.stock_utilization_percent.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1 border-b border-slate-200">
                      <span className="text-slate-500">Violations:</span>
                      <span className="font-medium text-emerald-700">
                        {benchmarkData.baseline_metrics.constraint_violations_count}
                      </span>
                    </div>
                    <div className="flex justify-between items-center pt-1 text-[11px]">
                      <span className="text-slate-500">Solve Time:</span>
                      <span className="font-mono text-slate-700 font-semibold">
                        {(benchmarkData.baseline_metrics.solve_time_seconds * 1000).toFixed(1)} ms
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-3.5 bg-white rounded-lg border border-indigo-100 text-xs text-indigo-950 flex items-start gap-2">
                <ShieldCheck className="w-4 h-4 text-indigo-600 mt-0.5 shrink-0" />
                <div>
                  <strong className="font-semibold">Mathematical Solver Audit: </strong>
                  {benchmarkData.comparison_summary}
                </div>
              </div>
            </Card>
          )}

          {/* Side-by-Side Plan Benchmark Cards */}
          {comparison && comparison.optimizer && comparison.baseline ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Card 1: Service-First Optimizer */}
              <Card className="border-t-4 border-t-blue-600 p-6 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                  <div>
                    <h3 className="text-base font-bold text-slate-900">Service-First Optimizer</h3>
                    <span className="text-xs text-blue-600 font-medium">Lexicographic Linear Program (OR-Tools / HiGHS)</span>
                  </div>
                  <Badge variant="primary">OPTIMAL SOLVE</Badge>
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div className="p-3 bg-blue-50/60 rounded-lg border border-blue-100">
                    <span className="text-slate-500 block mb-0.5">Customer Fill Rate</span>
                    <span className="text-2xl font-bold text-blue-700">
                      {comparison.optimizer.service_level_percent.toFixed(1)}%
                    </span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-slate-500 block mb-0.5">Unmet Demand</span>
                    <span className="text-2xl font-bold text-rose-600">
                      {comparison.optimizer.unmet_demand_units.toLocaleString()} <span className="text-xs font-normal text-slate-500">cases</span>
                    </span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-slate-500 block mb-0.5">Estimated Transport Cost</span>
                    <span className="text-lg font-bold font-mono text-slate-900">
                      ₹{comparison.optimizer.estimated_transport_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
                    <span className="text-slate-500 block mb-0.5">Stock Utilization</span>
                    <span className="text-lg font-bold text-slate-900">
                      {comparison.optimizer.stock_utilization_percent.toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="pt-2 flex items-center justify-between text-xs text-slate-500 border-t border-slate-100">
                  <span className="flex items-center gap-1 text-emerald-700 font-medium">
                    <ShieldCheck className="w-4 h-4" /> 0 Constraint Violations
                  </span>
                  <span>Runtime: <strong className="font-mono text-slate-800">{comparison.optimizer.solve_time_seconds.toFixed(4)}s</strong></span>
                </div>
              </Card>

              {/* Card 2: Nearest-Source Deterministic Baseline */}
              <Card className="border-t-4 border-t-slate-400 p-6 space-y-4 bg-slate-50/40">
                <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                  <div>
                    <h3 className="text-base font-bold text-slate-800">Deterministic Baseline</h3>
                    <span className="text-xs text-slate-500 font-medium">Nearest-Eligible-Source Policy</span>
                  </div>
                  <Badge variant="neutral">COMPARISON BENCHMARK</Badge>
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div className="p-3 bg-white rounded-lg border border-slate-200">
                    <span className="text-slate-500 block mb-0.5">Customer Fill Rate</span>
                    <span className="text-2xl font-bold text-slate-800">
                      {comparison.baseline.service_level_percent.toFixed(1)}%
                    </span>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-slate-200">
                    <span className="text-slate-500 block mb-0.5">Unmet Demand</span>
                    <span className="text-2xl font-bold text-slate-700">
                      {comparison.baseline.unmet_demand_units.toLocaleString()} <span className="text-xs font-normal text-slate-500">cases</span>
                    </span>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-slate-200">
                    <span className="text-slate-500 block mb-0.5">Estimated Transport Cost</span>
                    <span className="text-lg font-bold font-mono text-slate-900">
                      ₹{comparison.baseline.estimated_transport_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="p-3 bg-white rounded-lg border border-slate-200">
                    <span className="text-slate-500 block mb-0.5">Stock Utilization</span>
                    <span className="text-lg font-bold text-slate-900">
                      {comparison.baseline.stock_utilization_percent.toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="pt-2 flex items-center justify-between text-xs text-slate-500 border-t border-slate-200">
                  <span className="flex items-center gap-1 text-slate-700 font-medium">
                    <ShieldCheck className="w-4 h-4 text-slate-400" /> 0 Constraint Violations
                  </span>
                  <span>Runtime: <strong className="font-mono text-slate-800">{comparison.baseline.solve_time_seconds.toFixed(4)}s</strong></span>
                </div>
              </Card>
            </div>
          ) : !loading && (
            <Card className="p-8 text-center">
              <EmptyState
                icon={GitCompare}
                title="No optimization plan selected for benchmark"
                description="Generate a distribution plan to compare its multi-echelon service outcome and transport cost against the nearest-source baseline."
                actionLabel="Generate Plan Now"
                onAction={() => navigate('/optimize')}
                className="border-0 rounded-none py-6"
              />
            </Card>
          )}

          {/* Metric Framework Specification Card */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Evaluation Dimensions</CardTitle>
                <span className="text-xs text-slate-500">Transparent Methodology</span>
              </div>
              <CardDescription>
                The five key dimensions audited whenever a plan run is completed.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
                {comparisonMetricsDefinition.map((m) => (
                  <div key={m.metric} className="p-3.5 rounded-lg border border-[#E5E7EB] bg-slate-50/50 flex flex-col justify-between">
                    <div>
                      <div className="font-semibold text-[#172033] mb-1">{m.metric}</div>
                      <p className="text-slate-600 text-[11px] mb-2">{m.description}</p>
                    </div>
                    <code className="text-[10px] bg-white px-2 py-1 rounded border border-slate-200 text-slate-700 font-mono">
                      {m.formula}
                    </code>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: Corridor & Route Alternative Comparator                            */}
      {/* ========================================================================= */}
      {activeTab === 'corridors' && (
        <div className="space-y-6">
          {/* Controls Bar */}
          <Card className="p-4 bg-slate-50/70 border-slate-200">
            <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4">
              <div className="flex-1 w-full">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Destination:</label>
                <select
                  value={selectedDestinationId}
                  onChange={(e) => {
                    setSelectedDestinationId(e.target.value);
                    handleCompareCorridors(e.target.value, selectedSkuId);
                  }}
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white font-medium text-slate-900"
                >
                  {uniqueDestinations.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name} ({id})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex-1 w-full">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Target Product / SKU:</label>
                <select
                  value={selectedSkuId}
                  onChange={(e) => {
                    setSelectedSkuId(e.target.value);
                    handleCompareCorridors(selectedDestinationId, e.target.value);
                  }}
                  className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white font-medium text-slate-900"
                >
                  {uniqueSkus.map(([id, name]) => (
                    <option key={id} value={id}>
                      {name} ({id})
                    </option>
                  ))}
                </select>
              </div>

              <Button
                variant="primary"
                leftIcon={<RefreshCw className={`w-4 h-4 ${corridorLoading ? 'animate-spin' : ''}`} />}
                onClick={() => handleCompareCorridors()}
                disabled={corridorLoading}
              >
                {corridorLoading ? 'Comparing...' : 'Compare Corridors'}
              </Button>
            </div>
          </Card>

          {corridorError && (
            <Alert variant="error" title="Corridor Evaluation Error">
              {corridorError}
            </Alert>
          )}

          {corridorData && (
            <div className="space-y-6">
              {/* Top Banner with Recommended Corridor */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <Card className="p-4 border-l-4 border-l-blue-600">
                  <div className="text-xs text-slate-500 font-medium">Destination Demand Gap</div>
                  <div className="text-xl font-bold font-mono text-blue-700 mt-1">
                    {corridorData.demand_gap.toLocaleString()} cases
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    Target stock: {corridorData.target_stock.toLocaleString()}
                  </div>
                </Card>

                <Card className="p-4 border-l-4 border-l-indigo-600">
                  <div className="text-xs text-slate-500 font-medium">Corridors Evaluated</div>
                  <div className="text-xl font-bold font-mono text-indigo-700 mt-1">
                    {corridorData.alternatives.length} supply lanes
                  </div>
                  <div className="text-[11px] text-slate-500 mt-0.5">
                    {corridorData.alternatives.filter((a) => a.is_feasible).length} feasible under cutoffs
                  </div>
                </Card>

                <Card className="p-4 border-l-4 border-l-emerald-600">
                  <div className="text-xs text-slate-500 font-medium">Top Recommended Corridor</div>
                  <div className="text-sm font-bold text-emerald-900 mt-1 truncate">
                    {corridorData.recommended_corridor ? corridorData.recommended_corridor.source_location_name : 'No feasible corridor'}
                  </div>
                  <div className="text-[11px] font-mono text-emerald-700 mt-0.5">
                    {corridorData.recommended_corridor ? `₹${corridorData.recommended_corridor.total_delivered_cost_per_unit.toFixed(2)}/case delivered` : 'Stockout unavoidable'}
                  </div>
                </Card>
              </div>

              {/* Ranked Alternatives Table */}
              <Card>
                <CardHeader>
                  <CardTitle>Ranked Sourcing Alternatives & Corridors</CardTitle>
                  <CardDescription>
                    All candidate warehouses and routes ranked by service feasibility, lead time, delivered cost, and stock availability.
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Rank & Status</TableHead>
                        <TableHead>Source Warehouse</TableHead>
                        <TableHead className="text-right">Distance</TableHead>
                        <TableHead className="text-right">Lead Time</TableHead>
                        <TableHead className="text-right">Freight Rate</TableHead>
                        <TableHead className="text-right">Handling</TableHead>
                        <TableHead className="text-right">Delivered / Unit</TableHead>
                        <TableHead className="text-right">Available Stock</TableHead>
                        <TableHead>Feasibility Rationale</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {corridorData.alternatives.map((alt) => (
                        <TableRow key={alt.route_id} className={alt.is_feasible ? 'hover:bg-slate-50/70' : 'bg-slate-50/40 text-slate-400'}>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-xs font-bold text-slate-700">#{alt.ranking}</span>
                              {alt.is_feasible ? (
                                <Badge variant="success" size="sm">FEASIBLE</Badge>
                              ) : (
                                <Badge variant="neutral" size="sm">{alt.feasibility_status.toUpperCase()}</Badge>
                              )}
                            </div>
                          </TableCell>

                          <TableCell>
                            <div className="text-xs font-semibold text-slate-900">{alt.source_location_name}</div>
                            <div className="text-[10px] text-slate-500 font-mono capitalize">{alt.source_location_type.replace('_', ' ')}</div>
                          </TableCell>

                          <TableCell className="text-right font-mono text-xs text-slate-700">
                            {alt.distance_km ? `${alt.distance_km.toFixed(0)} km` : '—'}
                          </TableCell>

                          <TableCell className="text-right font-medium text-xs text-slate-800">
                            {alt.lead_time_days.toFixed(1)}d
                          </TableCell>

                          <TableCell className="text-right font-mono text-xs text-slate-800">
                            ₹{alt.cost_rate_per_unit.toFixed(2)}
                          </TableCell>

                          <TableCell className="text-right font-mono text-xs text-slate-600">
                            ₹{alt.handling_cost_per_unit.toFixed(2)}
                          </TableCell>

                          <TableCell className="text-right font-mono font-bold text-xs text-slate-900">
                            ₹{alt.total_delivered_cost_per_unit.toFixed(2)}
                          </TableCell>

                          <TableCell className="text-right font-mono text-xs">
                            <span className={alt.dispatchable_stock > 0 ? 'text-blue-700 font-bold' : 'text-slate-400'}>
                              {alt.dispatchable_stock.toLocaleString()}
                            </span>
                            <div className="text-[10px] text-slate-400">
                              {alt.unexpired_dispatchable_stock.toLocaleString()} unexpired
                            </div>
                          </TableCell>

                          <TableCell className="text-xs">
                            {alt.is_feasible ? (
                              <span className="text-emerald-700 font-medium flex items-center gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" /> All constraints satisfied
                              </span>
                            ) : (
                              <ul className="text-rose-600 text-[11px] list-disc list-inside space-y-0.5">
                                {alt.rejection_reasons.map((r, rIdx) => (
                                  <li key={rIdx}>{r}</li>
                                ))}
                              </ul>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: What-If Scenario Simulator                                         */}
      {/* ========================================================================= */}
      {activeTab === 'simulation' && (
        <div className="space-y-6">
          {/* Safety Callout */}
          <div className="p-4 rounded-xl border border-blue-200 bg-blue-50/50 flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
            <div className="text-xs text-blue-950 leading-relaxed">
              <strong>Dry-Run Scenario Simulator (Zero Database Side-Effects): </strong>
              Simulations evaluate hypothetical distribution stress tests in memory using the production OR-Tools linear program.
              Simulations <strong>never alter</strong> actual physical stock, confirmed incoming transfers, database shipment records, or inventory reservations.
            </div>
          </div>

          {/* Interactive Parameters Form */}
          <Card className="p-6 space-y-6">
            <div className="border-b border-slate-100 pb-3">
              <h3 className="text-base font-bold text-slate-900">Scenario Perturbation Parameters</h3>
              <p className="text-xs text-slate-500">
                Adjust demand multipliers, transport fuel surcharges, or source warehouse shortages.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              {/* Slider 1: Demand Multiplier */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-slate-800">Demand Multiplier:</span>
                  <span className="font-mono font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                    {simDemandMult.toFixed(2)}x ({simDemandMult >= 1 ? `+${Math.round((simDemandMult - 1) * 100)}%` : `${Math.round((simDemandMult - 1) * 100)}%`})
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="2.5"
                  step="0.05"
                  value={simDemandMult}
                  onChange={(e) => setSimDemandMult(parseFloat(e.target.value))}
                  className="w-full accent-blue-600 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>-50% Dip</span>
                  <span>1.0x Normal</span>
                  <span>+150% Surge</span>
                </div>
              </div>

              {/* Slider 2: Freight Rate Multiplier */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-slate-800">Freight Rate Multiplier:</span>
                  <span className="font-mono font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                    {simFreightMult.toFixed(2)}x ({simFreightMult >= 1 ? `+${Math.round((simFreightMult - 1) * 100)}%` : `${Math.round((simFreightMult - 1) * 100)}%`})
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="2.5"
                  step="0.05"
                  value={simFreightMult}
                  onChange={(e) => setSimFreightMult(parseFloat(e.target.value))}
                  className="w-full accent-indigo-600 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>-50% Subsidy</span>
                  <span>1.0x Standard</span>
                  <span>+150% Fuel Hike</span>
                </div>
              </div>

              {/* Slider 3: Warehouse Stock Multiplier */}
              <div className="space-y-2">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-slate-800">Warehouse Stock Level:</span>
                  <span className="font-mono font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    {simStockMult.toFixed(2)}x ({simStockMult >= 1 ? `+${Math.round((simStockMult - 1) * 100)}%` : `${Math.round((simStockMult - 1) * 100)}%`})
                  </span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="2.0"
                  step="0.05"
                  value={simStockMult}
                  onChange={(e) => setSimStockMult(parseFloat(e.target.value))}
                  className="w-full accent-amber-600 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-slate-400">
                  <span>0% Outage</span>
                  <span>1.0x Full</span>
                  <span>+100% Buffer</span>
                </div>
              </div>
            </div>

            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-700">Simulated Horizon:</span>
                <select
                  value={simHorizonDays}
                  onChange={(e) => setSimHorizonDays(parseInt(e.target.value, 10))}
                  className="text-xs px-3 py-1.5 rounded-lg border border-slate-300 bg-white font-medium text-slate-800"
                >
                  <option value="7">7 Days (Standard)</option>
                  <option value="14">14 Days (Extended)</option>
                  <option value="21">21 Days (Multi-Week)</option>
                  <option value="28">28 Days (Monthly)</option>
                </select>
              </div>

              <Button
                variant="primary"
                leftIcon={<Play className={`w-4 h-4 ${simulationLoading ? 'animate-spin' : ''}`} />}
                onClick={handleRunSimulation}
                disabled={simulationLoading}
              >
                {simulationLoading ? 'Simulating...' : 'Run Scenario Simulation'}
              </Button>
            </div>
          </Card>

          {simulationError && (
            <Alert variant="error" title="Simulation Execution Error">
              {simulationError}
            </Alert>
          )}

          {/* Simulation Results Display */}
          {simulationData && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">{simulationData.scenario_name}</h3>
                  <p className="text-xs text-slate-500">
                    Simulated at {new Date(simulationData.simulated_at).toLocaleTimeString()} · In-Memory Dry Run
                  </p>
                </div>
                <Badge variant="primary">DRY RUN COMPLETE</Badge>
              </div>

              {/* Impact Comparison Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                {simulationData.impact_analysis.map((m, idx) => (
                  <Card key={idx} className="p-4 border-t-4 border-t-blue-600">
                    <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                      {m.metric}
                    </div>
                    <div className="text-lg font-bold text-slate-900">
                      {m.simulated_value.toLocaleString()} <span className="text-xs font-normal text-slate-500">{m.unit}</span>
                    </div>
                    <div className="mt-2 text-xs font-mono flex items-center justify-between">
                      <span className="text-slate-400">Base: {m.baseline_value}</span>
                      <span className={
                        m.impact_direction === 'better'
                          ? 'text-emerald-700 font-bold'
                          : m.impact_direction === 'worse'
                          ? 'text-rose-600 font-bold'
                          : 'text-slate-500'
                      }>
                        {m.delta_value > 0 ? `+${m.delta_value}` : m.delta_value} ({m.delta_percent > 0 ? `+${m.delta_percent}%` : `${m.delta_percent}%`})
                      </span>
                    </div>
                  </Card>
                ))}
              </div>

              {/* Simulated Shipments Table */}
              <Card>
                <CardHeader>
                  <CardTitle>Simulated Recommended Allocations ({simulationData.simulated_shipments.length})</CardTitle>
                  <CardDescription>
                    Optimal shipments calculated under the simulated scenario constraints.
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>SKU & Product</TableHead>
                        <TableHead>Origin Source</TableHead>
                        <TableHead>Target Destination</TableHead>
                        <TableHead className="text-right">Simulated Quantity</TableHead>
                        <TableHead className="text-right">Simulated Freight Cost</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {simulationData.simulated_shipments.map((s, idx) => (
                        <TableRow key={idx}>
                          <TableCell>
                            <span className="font-mono text-xs font-semibold text-slate-900">{s.sku_id}</span>
                            <div className="text-[11px] text-slate-500">{s.product_name}</div>
                          </TableCell>
                          <TableCell className="text-xs text-slate-800">{s.source_location_name || s.source_location_id}</TableCell>
                          <TableCell className="text-xs text-slate-800">{s.destination_location_name || s.destination_location_id}</TableCell>
                          <TableCell className="text-right font-mono font-bold text-xs text-blue-700">
                            {s.quantity.toLocaleString()} cases
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs text-slate-900">
                            ₹{s.estimated_transport_cost.toFixed(2)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 4: Operational Distribution Performance                               */}
      {/* ========================================================================= */}
      {activeTab === 'performance' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Operational Distribution Funnel & Compliance</h2>
              <p className="text-xs text-slate-500">
                Tracks recommended allocation quantities through approval, dispatch, and physical delivery.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${perfLoading ? 'animate-spin' : ''}`} />}
              onClick={loadOperationalPerformance}
              disabled={perfLoading}
            >
              Refresh Metrics
            </Button>
          </div>

          {perfError && (
            <Alert variant="error" title="Performance Metric Error">
              {perfError}
            </Alert>
          )}

          {perfData && (
            <div className="space-y-6">
              {/* Funnel KPI Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <Card className="p-4 border-t-4 border-t-blue-600">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Recommended Units
                  </div>
                  <div className="text-2xl font-bold font-mono text-blue-700">
                    {perfData.total_recommended_units.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">From Optimizer Runs</div>
                </Card>

                <Card className="p-4 border-t-4 border-t-indigo-600">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Approved Units
                  </div>
                  <div className="text-2xl font-bold font-mono text-indigo-700">
                    {perfData.total_approved_units.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-indigo-600 mt-1 font-semibold">
                    {perfData.approval_rate_percent.toFixed(1)}% Approval Rate
                  </div>
                </Card>

                <Card className="p-4 border-t-4 border-t-amber-600">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Dispatched Units
                  </div>
                  <div className="text-2xl font-bold font-mono text-amber-700">
                    {perfData.total_dispatched_units.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-amber-600 mt-1 font-semibold">
                    {perfData.dispatch_rate_percent.toFixed(1)}% Dispatched
                  </div>
                </Card>

                <Card className="p-4 border-t-4 border-t-emerald-600">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Delivered Units
                  </div>
                  <div className="text-2xl font-bold font-mono text-emerald-700">
                    {perfData.total_delivered_units.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-emerald-600 mt-1 font-semibold">
                    {perfData.delivery_fulfillment_rate_percent.toFixed(1)}% Delivery Rate
                  </div>
                </Card>

                <Card className="p-4 border-t-4 border-t-slate-600">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
                    Delivered Unit Cost
                  </div>
                  <div className="text-2xl font-bold font-mono text-slate-900">
                    ₹{perfData.average_cost_per_case.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-slate-400 mt-1">Avg Freight / Case</div>
                </Card>
              </div>

              {/* Status Breakdown Table */}
              <Card>
                <CardHeader>
                  <CardTitle>Shipment Lifecycle Execution Breakdown</CardTitle>
                  <CardDescription>
                    Real-time operational status of all planned distribution movements across the supply network.
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-0">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Lifecycle Status</TableHead>
                        <TableHead className="text-right">Shipment Consignments</TableHead>
                        <TableHead className="text-right">Total Units (Cases)</TableHead>
                        <TableHead className="text-right">Total Freight Cost</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {perfData.lifecycle_breakdown.map((row, idx) => (
                        <TableRow key={idx}>
                          <TableCell>
                            <Badge
                              variant={
                                row.status === 'delivered'
                                  ? 'success'
                                  : row.status === 'in_transit' || row.status === 'ready_for_dispatch'
                                  ? 'primary'
                                  : row.status === 'approved'
                                  ? 'neutral'
                                  : 'warning'
                              }
                              size="sm"
                            >
                              {row.status.toUpperCase()}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs font-semibold text-slate-800">
                            {row.shipment_count}
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs font-bold text-slate-900">
                            {row.total_units.toLocaleString()} cases
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs text-slate-800">
                            ₹{row.total_transport_cost.toFixed(2)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
