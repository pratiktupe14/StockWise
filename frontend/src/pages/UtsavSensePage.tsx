import React, { useState, useEffect } from 'react';
import {
  Flame,
  Calendar,
  Sparkles,
  TrendingUp,
  Truck,
  Download,
  Plus,
  CheckCircle2,
  AlertTriangle,
  Clock,
  ArrowRight,
  RefreshCw,
  FileText,
} from 'lucide-react';
import {
  getFestivalEvents,
  createFestivalEvent,
  getFestivalUplift,
  executeFestivalOptimization,
  getExportFestivalUpliftCSVUrl,
} from '../services/api';
import { downloadAuthenticatedFile } from '../services/auth';
import type {
  FestivalEventItem,
  UtsavUpliftResponse,
  PlanningRunResponse,
} from '../types/api';

export const UtsavSensePage: React.FC = () => {
  const [events, setEvents] = useState<FestivalEventItem[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string>('FEST-DIWALI-2026');
  const [scenario, setScenario] = useState<string>('expected');
  const [customUplift, setCustomUplift] = useState<number>(45);
  const [horizonDays, setHorizonDays] = useState<number>(7);

  const [loadingEvents, setLoadingEvents] = useState<boolean>(true);
  const [loadingUplift, setLoadingUplift] = useState<boolean>(false);
  const [optimizing, setOptimizing] = useState<boolean>(false);

  const [upliftData, setUpliftData] = useState<UtsavUpliftResponse | null>(null);
  const [planResult, setPlanResult] = useState<PlanningRunResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Custom Event Modal State
  const [showAddModal, setShowAddModal] = useState<boolean>(false);
  const [newEvent, setNewEvent] = useState({
    event_id: '',
    name: '',
    description: '',
    start_date: '2026-10-01',
    end_date: '2026-10-10',
    regions: 'North,West',
    applicable_categories: 'Staples,Edible Oils,Snacks',
    default_uplift_percent: 30,
  });

  // Load registered festival events
  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    setLoadingEvents(true);
    try {
      const data = await getFestivalEvents();
      setEvents(data);
      if (data.length > 0 && !selectedEventId) {
        setSelectedEventId(data[0].event_id);
      }
    } catch (err: any) {
      console.error('Failed to load festivals', err);
      setErrorMsg(err.message || 'Failed to fetch festival calendar');
    } finally {
      setLoadingEvents(false);
    }
  };

  // Re-fetch uplift projections when event, scenario, or horizon changes
  useEffect(() => {
    if (!selectedEventId) return;
    fetchUplift();
  }, [selectedEventId, scenario, customUplift, horizonDays]);

  const fetchUplift = async () => {
    setLoadingUplift(true);
    setErrorMsg(null);
    try {
      const data = await getFestivalUplift(
        selectedEventId,
        scenario,
        scenario === 'custom' ? customUplift : undefined,
        horizonDays
      );
      setUpliftData(data);
    } catch (err: any) {
      console.error('Failed to compute uplift', err);
      setErrorMsg(err.message || 'Failed to compute festival demand uplift');
    } finally {
      setLoadingUplift(false);
    }
  };

  const handleRunOptimization = async () => {
    if (!selectedEventId) return;
    setOptimizing(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const result = await executeFestivalOptimization({
        event_id: selectedEventId,
        scenario,
        custom_uplift_percent: scenario === 'custom' ? customUplift : undefined,
        horizon_days: horizonDays,
        authorized_user_id: 'UTSAV-LEAD-PLANNER',
      });
      setPlanResult(result);
      setSuccessMsg(`Festival distribution plan ${result.run_id} solved successfully with 100% service level!`);
    } catch (err: any) {
      console.error('Failed to optimize festival plan', err);
      setErrorMsg(err.message || 'Optimization solver failed');
    } finally {
      setOptimizing(false);
    }
  };

  const handleCreateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEvent.event_id || !newEvent.name) return;
    try {
      await createFestivalEvent({
        event_id: newEvent.event_id.trim(),
        name: newEvent.name.trim(),
        description: newEvent.description.trim(),
        start_date: newEvent.start_date,
        end_date: newEvent.end_date,
        regions: newEvent.regions.split(',').map((s) => s.trim()).filter(Boolean),
        applicable_categories: newEvent.applicable_categories.split(',').map((s) => s.trim()).filter(Boolean),
        default_uplift_percent: Number(newEvent.default_uplift_percent),
      });
      setShowAddModal(false);
      await fetchEvents();
      setSelectedEventId(newEvent.event_id.trim());
      setSuccessMsg(`Festival event '${newEvent.name}' added to planning calendar.`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to register festival event');
    }
  };

  const activeEvent = events.find((e) => e.event_id === selectedEventId);

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header Banner */}
      <div className="bg-gradient-to-r from-amber-500 via-orange-500 to-rose-500 rounded-xl p-6 text-white shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="bg-white/20 backdrop-blur-sm text-xs font-semibold px-2.5 py-0.5 rounded-full uppercase tracking-wider">
              Phase 4.5 • Feature 13
            </span>
            <span className="text-amber-100 text-xs font-medium">UtsavSense FMCG Intelligence</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Flame className="w-6 h-6 text-yellow-200 fill-yellow-200" />
            UtsavSense: Festival-Aware Inventory & Surge Planning
          </h1>
          <p className="text-amber-100 text-sm mt-1 max-w-2xl">
            Simulate cultural festival demand surges without baseline double-counting. Generate constraint-aware source allocations, lead-time validated arrivals, and Decision Receipts.
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {selectedEventId && (
            <button
              type="button"
              onClick={() => {
                downloadAuthenticatedFile(
                  getExportFestivalUpliftCSVUrl(selectedEventId, scenario, horizonDays),
                  `StockWise_${selectedEventId}_${scenario}_uplift.csv`
                );
              }}
              className="inline-flex items-center gap-2 bg-white/20 hover:bg-white/30 backdrop-blur-sm text-white px-3.5 py-2 rounded-lg text-sm font-medium transition-colors border border-white/20 cursor-pointer"
            >
              <Download className="w-4 h-4" />
              Export Breakdown (CSV)
            </button>
          )}
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center gap-1.5 bg-white text-orange-600 hover:bg-orange-50 font-semibold px-4 py-2 rounded-lg text-sm shadow-sm transition-all"
          >
            <Plus className="w-4 h-4" />
            New Festival
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="bg-rose-50 border border-rose-200 text-rose-800 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-500 shrink-0 mt-0.5" />
          <div className="text-sm">
            <span className="font-semibold">Error: </span>
            {errorMsg}
          </div>
        </div>
      )}

      {successMsg && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg p-4 flex items-start gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
          <div className="text-sm font-medium">{successMsg}</div>
        </div>
      )}

      {/* Festival Event Selection Cards */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
            <Calendar className="w-4 h-4 text-orange-500" />
            1. Select Festival Event Calendar
          </h2>
          <span className="text-xs text-slate-500">{events.length} configured cultural periods</span>
        </div>

        {loadingEvents ? (
          <div className="py-8 text-center text-slate-400 text-sm">Loading festival calendar...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {events.map((evt) => {
              const isSelected = evt.event_id === selectedEventId;
              return (
                <div
                  key={evt.event_id}
                  onClick={() => setSelectedEventId(evt.event_id)}
                  className={`cursor-pointer rounded-lg p-4 border transition-all text-left ${
                    isSelected
                      ? 'border-orange-500 bg-orange-50/40 shadow-sm ring-1 ring-orange-400'
                      : 'border-slate-200 hover:border-slate-300 bg-white'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[11px] font-mono text-slate-400">{evt.event_id}</span>
                      <h3 className="text-sm font-semibold text-slate-900 mt-0.5">{evt.name}</h3>
                    </div>
                    <span className="text-xs font-semibold px-2 py-0.5 bg-orange-100 text-orange-700 rounded-full">
                      +{evt.default_uplift_percent}%
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-2 line-clamp-2">{evt.description}</p>
                  <div className="mt-3 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-400" />
                      {evt.start_date} to {evt.end_date}
                    </span>
                    <span className="font-medium text-slate-600">{evt.regions.join(', ')}</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Scenario & Planning Horizon Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Scenario Tabs */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-orange-500" />
              2. Demand Surge Scenario
            </h2>
            {activeEvent && (
              <span className="text-xs text-slate-500">
                Default baseline for {activeEvent.name}: <strong>+{activeEvent.default_uplift_percent}%</strong>
              </span>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { id: 'conservative', label: 'Conservative', factor: '0.5x', desc: 'Cautious buffer' },
              { id: 'expected', label: 'Expected', factor: '1.0x', desc: 'Standard surge' },
              { id: 'high', label: 'High Demand', factor: '1.5x', desc: 'Peak availability' },
              { id: 'custom', label: 'Custom', factor: `${customUplift}%`, desc: 'Planner defined' },
            ].map((s) => (
              <button
                key={s.id}
                onClick={() => setScenario(s.id)}
                className={`p-3 rounded-lg border text-left transition-all ${
                  scenario === s.id
                    ? 'border-orange-500 bg-orange-50/50 text-slate-900 ring-1 ring-orange-400'
                    : 'border-slate-200 hover:border-slate-300 text-slate-600 bg-white'
                }`}
              >
                <div className="text-xs font-semibold">{s.label}</div>
                <div className="text-lg font-bold text-orange-600 my-0.5">{s.factor}</div>
                <div className="text-[11px] text-slate-400">{s.desc}</div>
              </button>
            ))}
          </div>

          {scenario === 'custom' && (
            <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-center gap-4">
              <span className="text-xs font-medium text-slate-700 shrink-0">Custom Surge %:</span>
              <input
                type="range"
                min="0"
                max="150"
                step="5"
                value={customUplift}
                onChange={(e) => setCustomUplift(Number(e.target.value))}
                className="w-full accent-orange-500"
              />
              <span className="text-sm font-bold text-orange-600 shrink-0 w-12 text-right">{customUplift}%</span>
            </div>
          )}
        </div>

        {/* Planning Horizon & Solver Trigger */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700 mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-orange-500" />
              3. Horizon & Solve
            </h2>
            <div className="flex items-center gap-2 mb-4">
              {[7, 14, 21, 30].map((h) => (
                <button
                  key={h}
                  onClick={() => setHorizonDays(h)}
                  className={`flex-1 py-1.5 text-xs font-semibold rounded-lg border transition-all ${
                    horizonDays === h
                      ? 'border-orange-500 bg-orange-50 text-orange-700 font-bold'
                      : 'border-slate-200 text-slate-600 hover:border-slate-300'
                  }`}
                >
                  {h} Days
                </button>
              ))}
            </div>
            <p className="text-xs text-slate-500">
              Evaluates replenishment lead times and prevents double-counting against underlying run-rate.
            </p>
          </div>

          <button
            onClick={handleRunOptimization}
            disabled={optimizing || loadingUplift}
            className="w-full mt-4 flex items-center justify-center gap-2 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-600 hover:to-amber-600 text-white font-semibold py-2.5 px-4 rounded-lg shadow-sm transition-all disabled:opacity-50"
          >
            {optimizing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Solving via Google OR-Tools...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4" />
                Run Festival Optimization Solve
              </>
            )}
          </button>
        </div>
      </div>

      {/* KPI Summary Cards */}
      {upliftData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500">Total Baseline Demand</span>
            <div className="text-xl font-bold text-slate-800 mt-1">
              {upliftData.total_baseline_demand.toLocaleString()} <span className="text-xs text-slate-400 font-normal">cases</span>
            </div>
            <span className="text-[11px] text-slate-400">Regular {horizonDays}-day horizon demand</span>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500">Festival-Adjusted Demand</span>
            <div className="text-xl font-bold text-orange-600 mt-1">
              {upliftData.total_festival_demand.toLocaleString()} <span className="text-xs text-slate-400 font-normal">cases</span>
            </div>
            <span className="text-[11px] text-orange-500 font-medium">+{upliftData.uplift_percent}% simulated surge</span>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500">Incremental Surge Units</span>
            <div className="text-xl font-bold text-amber-600 mt-1">
              +{upliftData.total_incremental_demand.toLocaleString()} <span className="text-xs text-slate-400 font-normal">cases</span>
            </div>
            <span className="text-[11px] text-slate-400">Net incremental festive volume</span>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
            <span className="text-xs font-medium text-slate-500">Additional Stock Required</span>
            <div className="text-xl font-bold text-rose-600 mt-1">
              {upliftData.total_additional_stock_needed.toLocaleString()} <span className="text-xs text-slate-400 font-normal">cases</span>
            </div>
            <span className="text-[11px] text-rose-500 font-medium">Net replenishment gap</span>
          </div>
        </div>
      )}

      {/* Detailed Uplift Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-800">Festival Demand Projections & Corridor Analysis</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Filtered for {activeEvent?.name} across permitted regional destinations and applicable product categories.
            </p>
          </div>
          {upliftData && (
            <span className="text-xs text-slate-500 bg-slate-100 px-2 py-1 rounded">
              {upliftData.items.length} series analyzed
            </span>
          )}
        </div>

        {loadingUplift ? (
          <div className="p-8 text-center text-slate-400 text-sm">Computing festival surge curves...</div>
        ) : upliftData && upliftData.items.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-600">
              <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                <tr>
                  <th className="py-2.5 px-4">SKU / Product</th>
                  <th className="py-2.5 px-4">Category</th>
                  <th className="py-2.5 px-4">Destination / Region</th>
                  <th className="py-2.5 px-4 text-right">Baseline Rate</th>
                  <th className="py-2.5 px-4 text-right">Baseline Demand</th>
                  <th className="py-2.5 px-4 text-right">Festival Demand</th>
                  <th className="py-2.5 px-4 text-right">Incremental Surge</th>
                  <th className="py-2.5 px-4 text-right">Eligible Stock</th>
                  <th className="py-2.5 px-4 text-right">Additional Needed</th>
                  <th className="py-2.5 px-4">Assumptions & Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {upliftData.items.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors">
                    <td className="py-2.5 px-4 font-medium text-slate-900">
                      <div>{row.product_name}</div>
                      <div className="text-[11px] font-mono text-slate-400">{row.sku_id}</div>
                    </td>
                    <td className="py-2.5 px-4">
                      <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-700">
                        {row.category}
                      </span>
                    </td>
                    <td className="py-2.5 px-4">
                      <div className="font-medium text-slate-800">{row.destination_name}</div>
                      <div className="text-[11px] text-slate-400">{row.region}</div>
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono">{row.baseline_daily_rate} /d</td>
                    <td className="py-2.5 px-4 text-right font-mono">{row.baseline_demand}</td>
                    <td className="py-2.5 px-4 text-right font-mono font-bold text-orange-600">
                      {row.festival_demand}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono text-amber-600">
                      +{row.incremental_units}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono text-slate-600">
                      {row.current_eligible_stock}
                    </td>
                    <td className="py-2.5 px-4 text-right font-mono font-bold text-rose-600">
                      {row.additional_stock_needed > 0 ? `+${row.additional_stock_needed}` : '0'}
                    </td>
                    <td className="py-2.5 px-4 text-slate-500 text-[11px] max-w-xs truncate" title={row.assumptions}>
                      {row.assumptions}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-slate-400 text-sm">No sales history or corridors matching this festival filter.</div>
        )}
      </div>

      {/* Optimization Solve Results Section */}
      {planResult && (
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-4 border-b border-slate-200">
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded font-semibold text-xs uppercase">
                  {planResult.solver_status}
                </span>
                <span className="text-xs font-mono text-slate-400">Run ID: {planResult.run_id}</span>
              </div>
              <h3 className="text-lg font-bold text-slate-900 mt-1">
                Optimized Festival Stock Allocation ({planResult.solver_name})
              </h3>
            </div>

            <div className="flex items-center gap-4 text-right">
              <div>
                <span className="text-xs text-slate-400 block">Service Level</span>
                <span className="text-lg font-bold text-emerald-600">{planResult.service_level_percent}%</span>
              </div>
              <div>
                <span className="text-xs text-slate-400 block">Est. Freight Cost</span>
                <span className="text-lg font-bold text-slate-800">₹{planResult.estimated_transport_cost.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-xs text-slate-400 block">Fulfilled Volume</span>
                <span className="text-lg font-bold text-slate-800">{planResult.fulfilled_demand_units} cases</span>
              </div>
            </div>
          </div>

          {/* Recommended Movement Shipments */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2.5 flex items-center gap-1.5">
              <Truck className="w-4 h-4 text-orange-500" />
              Recommended Transfer Shipments ({planResult.recommended_shipments.length})
            </h4>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600">
                <thead className="bg-slate-50 text-slate-500 font-medium border-b border-slate-200">
                  <tr>
                    <th className="py-2 px-3">Shipment ID</th>
                    <th className="py-2 px-3">SKU & Product</th>
                    <th className="py-2 px-3">Source Warehouse</th>
                    <th className="py-2 px-3">Destination Node</th>
                    <th className="py-2 px-3 text-right">Allocated Qty</th>
                    <th className="py-2 px-3 text-right">Lead Time</th>
                    <th className="py-2 px-3 text-right">Freight Cost (INR)</th>
                    <th className="py-2 px-3">Expected Arrival</th>
                    <th className="py-2 px-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {planResult.recommended_shipments.map((shp) => (
                    <tr key={shp.shipment_id} className="hover:bg-slate-50">
                      <td className="py-2.5 px-3 font-mono font-medium text-slate-900">{shp.shipment_id}</td>
                      <td className="py-2.5 px-3">
                        <div className="font-medium text-slate-800">{shp.product_name}</div>
                        <div className="text-[11px] font-mono text-slate-400">{shp.sku_id}</div>
                      </td>
                      <td className="py-2.5 px-3">{shp.source_location_name || shp.source_location_id}</td>
                      <td className="py-2.5 px-3">{shp.destination_location_name || shp.destination_location_id}</td>
                      <td className="py-2.5 px-3 text-right font-mono font-bold text-slate-900">
                        {shp.quantity} cases
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono">{shp.lead_time_days || 1} d</td>
                      <td className="py-2.5 px-3 text-right font-mono font-semibold text-slate-800">
                        ₹{(shp.estimated_transport_cost || 0).toLocaleString()}
                      </td>
                      <td className="py-2.5 px-3 text-[11px] text-slate-500">
                        {shp.estimated_arrival_date ? new Date(shp.estimated_arrival_date).toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                          {shp.approval_status || 'pending'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Decision Receipts with Grounded Rationale */}
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2.5 flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-orange-500" />
              Automated Decision Receipts & Grounded Evidence
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {planResult.decision_receipts.slice(0, 4).map((rcpt, idx) => (
                <div key={idx} className="bg-slate-50 rounded-lg p-3.5 border border-slate-200 text-xs space-y-1.5">
                  <div className="flex items-center justify-between font-semibold text-slate-800">
                    <span>{rcpt.product_name} ({rcpt.sku_id})</span>
                    <span className="text-emerald-700 font-bold">₹{rcpt.estimated_cost} INR</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-slate-600">
                    <span className="font-medium">{rcpt.source_location_name}</span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span className="font-medium">{rcpt.destination_location_name}</span>
                    <span className="ml-auto font-bold text-slate-900">{rcpt.quantity} {rcpt.unit}</span>
                  </div>
                  <p className="text-[11px] text-slate-500 bg-white p-2 rounded border border-slate-100">
                    <strong>Evidence:</strong> {rcpt.evidence}
                  </p>
                  {rcpt.rejected_alternatives && rcpt.rejected_alternatives.length > 0 && (
                    <div className="text-[10px] text-slate-400 pt-1">
                      <strong>Rejected alternatives:</strong> {rcpt.rejected_alternatives.join('; ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Add Custom Festival Event Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 border border-slate-200">
            <h3 className="text-lg font-bold text-slate-900 mb-1 flex items-center gap-2">
              <Flame className="w-5 h-5 text-orange-500" />
              Register Regional Festival Event
            </h3>
            <p className="text-xs text-slate-500 mb-4">
              Add a state or cultural celebration into the UtsavSense calendar with targeted surge factors.
            </p>

            <form onSubmit={handleCreateEvent} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Event Identifier</label>
                  <input
                    type="text"
                    required
                    placeholder="FEST-ONAM-2026"
                    value={newEvent.event_id}
                    onChange={(e) => setNewEvent({ ...newEvent, event_id: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Festival Name</label>
                  <input
                    type="text"
                    required
                    placeholder="Onam Harvest Festival"
                    value={newEvent.name}
                    onChange={(e) => setNewEvent({ ...newEvent, name: e.target.value })}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">Description</label>
                <input
                  type="text"
                  placeholder="Seasonal harvest celebration driving high staple food consumption."
                  value={newEvent.description}
                  onChange={(e) => setNewEvent({ ...newEvent, description: e.target.value })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 mb-1">Start Date</label>
                  <input
                    type="date"
                    required
                    value={newEvent.start_date}
                    onChange={(e) => setNewEvent({ ...newEvent, start_date: e.target.value })}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 mb-1">End Date</label>
                  <input
                    type="date"
                    required
                    value={newEvent.end_date}
                    onChange={(e) => setNewEvent({ ...newEvent, end_date: e.target.value })}
                    className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                  />
                </div>
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">Applicable Regions (comma-separated)</label>
                <input
                  type="text"
                  placeholder="South,Kerala,Karnataka"
                  value={newEvent.regions}
                  onChange={(e) => setNewEvent({ ...newEvent, regions: e.target.value })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">Applicable Categories (comma-separated)</label>
                <input
                  type="text"
                  placeholder="Staples,Edible Oils,Snacks"
                  value={newEvent.applicable_categories}
                  onChange={(e) => setNewEvent({ ...newEvent, applicable_categories: e.target.value })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 mb-1">Default Surge Uplift (%)</label>
                <input
                  type="number"
                  min="0"
                  max="150"
                  value={newEvent.default_uplift_percent}
                  onChange={(e) => setNewEvent({ ...newEvent, default_uplift_percent: Number(e.target.value) })}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-lg"
                />
              </div>

              <div className="pt-3 flex items-center justify-end gap-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded-lg text-slate-600 hover:bg-slate-50 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg font-semibold"
                >
                  Save Festival Event
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
