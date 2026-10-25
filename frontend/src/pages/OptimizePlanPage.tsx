import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  RefreshCw,
  AlertCircle,
  Truck,
  FileText,
  X,
  History,
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
  runDistributionOptimization,
  getPlanningRuns,
  getPlanningRunDetails,
} from '../services/api';
import type {
  PlanningRunResponse,
  PlanningRunSummary,
  DecisionReceipt,
  ShipmentItem,
} from '../types/api';

export const OptimizePlanPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedHorizon, setSelectedHorizon] = useState<number>(7);
  const [objectiveStrategy] = useState<string>('service-first');
  const [solving, setSolving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activePlan, setActivePlan] = useState<PlanningRunResponse | null>(null);
  const [historyRuns, setHistoryRuns] = useState<PlanningRunSummary[]>([]);
  const [selectedReceipt, setSelectedReceipt] = useState<DecisionReceipt | null>(null);

  // Load history on mount
  const loadHistory = async () => {
    try {
      const runs = await getPlanningRuns(10, 0);
      setHistoryRuns(runs);
      if (runs.length > 0 && !activePlan) {
        // Load latest run details
        const latestDetails = await getPlanningRunDetails(runs[0].run_id);
        setActivePlan(latestDetails);
      }
    } catch {
      // Ignore initial load history error if no runs exist
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleGeneratePlan = async () => {
    setSolving(true);
    setError(null);
    try {
      const res = await runDistributionOptimization({
        horizon_days: selectedHorizon,
        objective_strategy: objectiveStrategy,
        allow_cross_region_routes: true,
        authorized_user_id: 'DIST-PLANNER-01',
      });
      setActivePlan(res);
      await loadHistory();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to execute distribution optimization solve';
      setError(msg);
    } finally {
      setSolving(false);
    }
  };

  const handleSelectHistoricalRun = async (runId: string) => {
    try {
      setSolving(true);
      const res = await getPlanningRunDetails(runId);
      setActivePlan(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load selected run');
    } finally {
      setSolving(false);
    }
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">
              Optimize Distribution Plan
            </h1>
            <Badge variant="primary" size="sm">HiGHS Lexicographic Solver</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Service-first 2-stage linear optimization allocating company supply across permitted FMCG corridors.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {historyRuns.length > 0 && (
            <div className="flex items-center gap-1.5">
              <History className="w-4 h-4 text-slate-400" />
              <select
                value={activePlan?.run_id || ''}
                onChange={(e) => handleSelectHistoricalRun(e.target.value)}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                {historyRuns.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id} ({r.service_level_percent.toFixed(1)}% service)
                  </option>
                ))}
              </select>
            </div>
          )}

          <Button
            variant="primary"
            onClick={handleGeneratePlan}
            disabled={solving}
            leftIcon={<Sparkles className={`w-4 h-4 ${solving ? 'animate-spin' : ''}`} />}
          >
            {solving ? 'Solving Linear Program...' : 'Generate Distribution Plan'}
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Optimization Error">
          {error}
        </Alert>
      )}

      {/* Scope Alert */}
      <Alert variant="info" title="PRD Section 7.5 Service-First Lexicographic Objective">
        The solver executes in two consecutive stages: <strong>Stage 1</strong> strictly minimizes weighted unmet customer demand across destination nodes; <strong>Stage 2</strong> minimizes transport cost among plans achieving that exact optimal service level. Independent distributor inventory is protected from multi-echelon company re-allocation.
      </Alert>

      {/* Control Panel: Parameters & Horizon */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-700">Planning Horizon:</span>
              <select
                value={selectedHorizon}
                onChange={(e) => setSelectedHorizon(parseInt(e.target.value, 10))}
                className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value={7}>7 Days (P0 Cutoff Window)</option>
                <option value={14}>14 Days (Extended Distribution)</option>
                <option value={30}>30 Days (Monthly Allocation)</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-700">Objective Strategy:</span>
              <span className="text-xs px-2.5 py-1 bg-slate-100 text-slate-800 rounded font-mono font-medium">
                service-first (Lexicographic LP)
              </span>
            </div>
          </div>

          {activePlan && (
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <span>Run ID: <strong className="font-mono text-slate-700">{activePlan.run_id}</strong></span>
              <span>•</span>
              <span>Solver Time: <strong className="font-mono text-slate-700">{activePlan.solve_time_ms} ms</strong></span>
              <span>•</span>
              <Badge variant={activePlan.solver_status === 'optimal' ? 'success' : 'warning'}>
                {activePlan.solver_status.toUpperCase()}
              </Badge>
            </div>
          )}
        </div>
      </Card>

      {/* Active Plan Metrics KPI Cards */}
      {activePlan && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <Card className="p-4 border-t-4 border-t-blue-600">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Fill Rate
            </div>
            <div className="text-2xl font-bold text-blue-600">
              {activePlan.service_level_percent.toFixed(1)}%
            </div>
            <div className="text-[10px] text-slate-500 mt-1">Customer Service Level</div>
          </Card>

          <Card className="p-4 border-t-4 border-t-emerald-600">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Fulfilled Units
            </div>
            <div className="text-2xl font-bold text-emerald-700">
              {activePlan.fulfilled_demand_units.toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">Cases Dispatched</div>
          </Card>

          <Card className="p-4 border-t-4 border-t-rose-600">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Unmet Demand
            </div>
            <div className="text-2xl font-bold text-rose-600">
              {activePlan.unmet_demand_units.toLocaleString()}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">Uncovered Shortfall</div>
          </Card>

          <Card className="p-4 border-t-4 border-t-indigo-600">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Est. Transport Cost
            </div>
            <div className="text-2xl font-bold text-indigo-700">
              ₹{activePlan.estimated_transport_cost.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">Route Rate Sum</div>
          </Card>

          <Card className="p-4 border-t-4 border-t-amber-600">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Stock Utilization
            </div>
            <div className="text-2xl font-bold text-amber-700">
              {activePlan.stock_utilization_percent.toFixed(1)}%
            </div>
            <div className="text-[10px] text-slate-500 mt-1">Eligible Supply Deployed</div>
          </Card>

          <Card className="p-4 border-t-4 border-t-teal-600">
            <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-1">
              Shipments Proposed
            </div>
            <div className="text-2xl font-bold text-teal-700">
              {activePlan.recommended_shipments.length}
            </div>
            <div className="text-[10px] text-slate-500 mt-1">With Decision Receipts</div>
          </Card>
        </div>
      )}

      {/* Recommended Shipments Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-[#172033]">
              Recommended Shipments & Allocation Corridors
            </h2>
            <p className="text-xs text-[#667085]">
              Every shipment below includes an evidence-based Decision Receipt with alternative rejection logs.
            </p>
          </div>
          {activePlan && activePlan.recommended_shipments.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              leftIcon={<Truck className="w-3.5 h-3.5" />}
              onClick={() => navigate('/approval')}
            >
              Go to Approval & Export
            </Button>
          )}
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU & Product</TableHead>
              <TableHead>Source Warehouse</TableHead>
              <TableHead>Destination</TableHead>
              <TableHead className="text-right">Allocated Quantity</TableHead>
              <TableHead className="text-right">Lead Time</TableHead>
              <TableHead>Estimated Arrival (ETA)</TableHead>
              <TableHead className="text-right">Transport Cost</TableHead>
              <TableHead>Decision Receipt</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {solving ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12 text-slate-500">
                  <div className="flex items-center justify-center gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
                    <span>Executing 2-stage linear program on distribution network...</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : activePlan && activePlan.recommended_shipments.length > 0 ? (
              activePlan.recommended_shipments.map((shp: ShipmentItem, idx: number) => {
                const receipt = activePlan.decision_receipts[idx] || null;
                return (
                  <TableRow key={shp.shipment_id} className="hover:bg-slate-50/70">
                    <TableCell>
                      <div className="font-mono text-xs font-semibold text-slate-900">{shp.sku_id}</div>
                      <div className="text-[11px] text-slate-500">{shp.product_name || 'FMCG SKU'}</div>
                    </TableCell>
                    <TableCell>
                      <div className="text-xs font-medium text-slate-900">{shp.source_location_name || shp.source_location_id}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{shp.source_location_id}</div>
                    </TableCell>
                    <TableCell>
                      <div className="text-xs font-medium text-slate-900">{shp.destination_location_name || shp.destination_location_id}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{shp.destination_location_id}</div>
                    </TableCell>
                    <TableCell className="text-right font-mono font-bold text-blue-700">
                      {shp.quantity.toLocaleString()} cases
                    </TableCell>
                    <TableCell className="text-right font-medium text-slate-700">
                      {receipt ? `${receipt.lead_time_days.toFixed(1)}d` : '1.0d'}
                    </TableCell>
                    <TableCell className="text-xs text-slate-700">
                      {receipt ? receipt.estimated_arrival_date : new Date(shp.estimated_arrival_date || '').toLocaleDateString()}
                    </TableCell>
                    <TableCell className="text-right font-mono font-medium text-slate-800">
                      ₹{shp.estimated_transport_cost.toFixed(2)}
                    </TableCell>
                    <TableCell>
                      {receipt ? (
                        <button
                          onClick={() => setSelectedReceipt(receipt)}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-blue-50 text-blue-700 hover:bg-blue-100 text-xs font-medium transition-colors"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          View Receipt
                        </button>
                      ) : (
                        <span className="text-xs text-slate-400">Attached</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })
            ) : (
              <TableRow>
                <TableCell colSpan={8} className="p-0">
                  <EmptyState
                    icon={Sparkles}
                    title="No distribution plan generated yet"
                    description="Click 'Generate Distribution Plan' to run the 2-stage HiGHS optimization solver across current inventory snapshots and demand forecasts."
                    actionLabel="Generate Plan Now"
                    onAction={handleGeneratePlan}
                    className="border-0 rounded-none py-12"
                  />
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Unmet Demand Breakdown (if any) */}
      {activePlan && activePlan.unmet_demand_breakdown.length > 0 && (
        <Card className="border-l-4 border-l-rose-500">
          <CardHeader>
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-rose-600" />
              <CardTitle className="text-rose-900">Unmet Demand & Infeasibility Explanations</CardTitle>
            </div>
            <CardDescription>
              The following destination shortfalls could not be satisfied under network constraints (lead time cutoffs, stock limits, or route permissions):
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activePlan.unmet_demand_breakdown.map((item, idx) => (
              <div key={idx} className="p-3.5 bg-rose-50/60 rounded-lg border border-rose-200 text-xs space-y-1.5">
                <div className="flex items-center justify-between font-semibold text-rose-950">
                  <span>{item.product_name || item.sku_id} at {item.destination_name || item.destination_id}</span>
                  <span className="font-mono bg-rose-200 text-rose-900 px-2 py-0.5 rounded">
                    Shortfall: {item.unmet_quantity.toFixed(1)} cases (of {item.total_demand_gap.toFixed(1)} gap)
                  </span>
                </div>
                <div className="text-slate-700 text-[11px]">
                  <strong>Constraint Reasons:</strong>
                  <ul className="list-disc list-inside mt-1 space-y-0.5 text-slate-600">
                    {item.reasons.map((r, rIdx) => (
                      <li key={rIdx}>{r}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Decision Receipt Modal */}
      {selectedReceipt && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-slate-200 p-6 space-y-5">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-600" />
                <h3 className="text-lg font-bold text-slate-900">Decision Receipt</h3>
                <span className="font-mono text-xs bg-slate-100 text-slate-700 px-2 py-0.5 rounded">
                  {selectedReceipt.recommendation_id}
                </span>
              </div>
              <button
                onClick={() => setSelectedReceipt(null)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Core Allocation Details */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-xs bg-slate-50 p-4 rounded-lg border border-slate-200">
              <div>
                <span className="text-slate-500">Product / SKU:</span>
                <div className="font-semibold text-slate-900">{selectedReceipt.product_name} ({selectedReceipt.sku_id})</div>
              </div>
              <div>
                <span className="text-slate-500">Allocated Quantity:</span>
                <div className="font-bold font-mono text-blue-700 text-sm">
                  {selectedReceipt.quantity.toLocaleString()} {selectedReceipt.unit}
                </div>
              </div>
              <div>
                <span className="text-slate-500">Origin Source:</span>
                <div className="font-semibold text-slate-900">{selectedReceipt.source_location_name}</div>
              </div>
              <div>
                <span className="text-slate-500">Target Destination:</span>
                <div className="font-semibold text-slate-900">{selectedReceipt.destination_location_name}</div>
              </div>
              <div>
                <span className="text-slate-500">Lead Time & Arrival:</span>
                <div className="font-medium text-slate-800">{selectedReceipt.lead_time_days.toFixed(1)} days (ETA: {selectedReceipt.estimated_arrival_date})</div>
              </div>
              <div>
                <span className="text-slate-500">Road Distance:</span>
                <div className="font-mono font-medium text-slate-900">
                  {selectedReceipt.distance_km ? `${selectedReceipt.distance_km.toFixed(0)} km` : 'Direct corridor'}
                </div>
              </div>
              <div>
                <span className="text-slate-500">Base Freight Cost:</span>
                <div className="font-mono text-slate-800">
                  ₹{(selectedReceipt.base_freight_cost ?? selectedReceipt.estimated_cost).toFixed(2)}
                </div>
              </div>
              <div>
                <span className="text-slate-500">Handling Cost:</span>
                <div className="font-mono text-slate-800">
                  ₹{(selectedReceipt.handling_cost ?? 0).toFixed(2)}
                </div>
              </div>
              <div>
                <span className="text-slate-500">Total Delivered Cost:</span>
                <div className="font-mono font-bold text-slate-900">₹{selectedReceipt.estimated_cost.toFixed(2)}</div>
              </div>
            </div>

            {/* FEFO Batch Allocation */}
            {selectedReceipt.allocated_batches && selectedReceipt.allocated_batches.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
                  FEFO Batch-Level Allocation:
                </h4>
                <div className="border border-slate-200 rounded-lg overflow-hidden text-xs">
                  <table className="w-full text-left">
                    <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                      <tr>
                        <th className="p-2">Batch #</th>
                        <th className="p-2 text-right">Allocated Qty</th>
                        <th className="p-2">Expiry Date</th>
                        <th className="p-2 text-right">Days Remaining</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {selectedReceipt.allocated_batches.map((b, bIdx) => (
                        <tr key={bIdx} className="hover:bg-slate-50">
                          <td className="p-2 font-mono font-medium text-slate-900">{b.batch_number || 'Standard Inventory'}</td>
                          <td className="p-2 text-right font-mono font-bold text-blue-700">{b.allocated_quantity.toLocaleString()} cases</td>
                          <td className="p-2 text-slate-600">{b.expiry_date || 'N/A'}</td>
                          <td className="p-2 text-right">
                            <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                              (b.days_remaining ?? 999) <= 45 ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-800'
                            }`}>
                              {b.days_remaining !== null && b.days_remaining !== undefined ? `${b.days_remaining}d` : 'Valid'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Constraints Evaluated Checklist */}
            {selectedReceipt.constraints_evaluated && selectedReceipt.constraints_evaluated.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
                  Distribution Constraints Verified:
                </h4>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                  {selectedReceipt.constraints_evaluated.map((c, cIdx) => (
                    <div key={cIdx} className="flex items-center gap-2 p-2 bg-emerald-50/60 border border-emerald-200 rounded text-emerald-950">
                      <span className="text-emerald-600 font-bold">✓</span>
                      <span>{c}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Evidence & Rationale */}
            <div>
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
                Mathematical Allocation Rationale:
              </h4>
              <div className="p-3 bg-blue-50/70 border border-blue-200 text-xs text-blue-950 rounded-lg leading-relaxed">
                {selectedReceipt.evidence}
              </div>
            </div>

            {/* Concrete Rejected Alternatives */}
            {selectedReceipt.rejected_alternatives && selectedReceipt.rejected_alternatives.length > 0 && (
              <div>
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider mb-2">
                  Rejected Alternative Source Facilities:
                </h4>
                <div className="p-3 bg-slate-100 rounded-lg border border-slate-200 text-xs text-slate-700 space-y-1.5">
                  {selectedReceipt.rejected_alternatives.map((reason, idx) => (
                    <div key={idx} className="flex items-start gap-1.5">
                      <span className="text-rose-500 font-bold">•</span>
                      <span>{reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-end pt-4 border-t border-slate-100">
              <Button variant="primary" onClick={() => setSelectedReceipt(null)}>
                Close Receipt
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
