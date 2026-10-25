import React from 'react';
import {
  CheckCircle2,
  DollarSign,
  AlertTriangle,
  TrendingDown,
  Calculator,
} from 'lucide-react';
import { Badge } from './ui/Badge';
import type { DistributionPerformanceResponse } from '../types/api';

interface DistributionPerformanceKPIsProps {
  performance: DistributionPerformanceResponse | null;
  loading: boolean;
}

export const DistributionPerformanceKPIs: React.FC<DistributionPerformanceKPIsProps> = ({
  performance,
  loading,
}) => {
  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-4 bg-white border border-slate-200 rounded-xl shadow-xs animate-pulse space-y-2.5"
          >
            <div className="h-3 w-28 bg-slate-200 rounded" />
            <div className="h-7 w-20 bg-slate-200 rounded" />
            <div className="h-2.5 w-36 bg-slate-200 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (!performance) {
    return null;
  }

  const isVerified = performance.data_source_mode === 'verified_operational';
  const hasRecordedShipments = performance.has_recorded_shipments;

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-bold tracking-tight text-slate-900 uppercase">
              P3: Distribution Performance (4 Core KPIs)
            </h2>
            <Badge variant={isVerified ? 'success' : 'neutral'} size="sm" dot={isVerified}>
              {isVerified ? 'Verified Operational Records' : 'Estimated (Optimization Plan)'}
            </Badge>
          </div>
          <p className="text-xs text-slate-500">
            {performance.period_label} &bull; Baseline and optimizer evaluated on equivalent demand, dates, and network constraints.
          </p>
        </div>

        <div className="flex items-center gap-2 text-[11px] text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md border border-slate-200">
          <Calculator className="w-3.5 h-3.5 text-slate-400" />
          <span>Formula-verified from operational tables</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* KPI 1: Demand fulfilment rate */}
        <div className="p-4 bg-white border border-slate-200/90 rounded-xl shadow-xs space-y-2 hover:border-blue-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              Demand Fulfilment Rate
            </span>
            <Badge
              variant={performance.demand_fulfilment_rate_percent >= 95 ? 'success' : 'warning'}
              size="sm"
            >
              {performance.demand_fulfilment_rate_percent >= 95 ? 'Optimal Service' : 'Partial Deficit'}
            </Badge>
          </div>

          <div className="flex items-baseline gap-2">
            <div className="text-2xl font-bold tracking-tight text-slate-900">
              {performance.demand_fulfilment_rate_percent.toFixed(1)}%
            </div>
            <span className="text-xs text-slate-500 font-medium">
              ({performance.fulfilled_demand_units.toLocaleString()} / {performance.eligible_demand_units.toLocaleString()} u)
            </span>
          </div>

          <div className="pt-2 border-t border-slate-100 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-mono">Formula:</span>
              <span className="font-mono text-slate-700 font-medium">fulfilled / eligible &times; 100</span>
            </div>
            <div className="text-[11px] text-slate-500 truncate" title={performance.demand_fulfilment_label}>
              Source: <span className="text-slate-700 font-medium">{isVerified ? 'Operational Dispatches' : 'Solver Optimal Allocation'}</span>
            </div>
          </div>
        </div>

        {/* KPI 2: Transportation cost */}
        <div className="p-4 bg-white border border-slate-200/90 rounded-xl shadow-xs space-y-2 hover:border-blue-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
              <DollarSign className="w-4 h-4 text-blue-600" />
              Transportation Cost
            </span>
            <Badge
              variant={hasRecordedShipments ? 'success' : 'neutral'}
              size="sm"
            >
              {hasRecordedShipments ? 'Verified Operational' : 'Estimated Plan'}
            </Badge>
          </div>

          <div className="flex items-baseline gap-2">
            <div className="text-2xl font-bold tracking-tight text-slate-900">
              ₹{Math.round(performance.transportation_cost).toLocaleString()}
            </div>
            <span className="text-xs text-slate-500 font-medium">Landed Freight</span>
          </div>

          <div className="pt-2 border-t border-slate-100 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-mono">Formula:</span>
              <span className="font-mono text-slate-700 font-medium">&sum;(distance &times; rate + handling)</span>
            </div>
            <div className="text-[11px] text-slate-500 truncate" title={performance.transportation_cost_label}>
              Record: <span className="text-slate-700 font-medium">{performance.transportation_cost_label}</span>
            </div>
          </div>
        </div>

        {/* KPI 3: Stockout rate */}
        <div className="p-4 bg-white border border-slate-200/90 rounded-xl shadow-xs space-y-2 hover:border-blue-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              Stockout Rate
            </span>
            <Badge
              variant={performance.stockout_rate_percent === 0 ? 'success' : 'critical'}
              size="sm"
            >
              {performance.stockout_rate_percent === 0 ? 'Zero Stockout' : 'Unmet Deficit'}
            </Badge>
          </div>

          <div className="flex items-baseline gap-2">
            <div className="text-2xl font-bold tracking-tight text-slate-900">
              {performance.stockout_rate_percent.toFixed(1)}%
            </div>
            <span className="text-xs text-slate-500 font-medium">
              ({performance.unmet_demand_units.toLocaleString()} u deficit)
            </span>
          </div>

          <div className="pt-2 border-t border-slate-100 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-mono">Formula:</span>
              <span className="font-mono text-slate-700 font-medium">unmet stockout / eligible &times; 100</span>
            </div>
            <div className="text-[11px] text-slate-500 truncate" title="Demand units unfulfilled because of stock unavailability / eligible demand units * 100">
              Integrity: <span className="text-slate-700 font-medium">Not inferred from current OH</span>
            </div>
          </div>
        </div>

        {/* KPI 4: Cost reduction */}
        <div className="p-4 bg-white border border-slate-200/90 rounded-xl shadow-xs space-y-2 hover:border-blue-300 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
              <TrendingDown className="w-4 h-4 text-indigo-600" />
              Cost Reduction
            </span>
            <Badge
              variant={performance.cost_reduction_percent > 0 ? 'success' : (performance.cost_reduction_percent < 0 ? 'warning' : 'neutral')}
              size="sm"
            >
              {performance.cost_reduction_percent > 0
                ? `${performance.cost_reduction_percent.toFixed(1)}% vs Baseline`
                : (performance.cost_reduction_percent < 0 ? `+${Math.abs(performance.cost_reduction_percent).toFixed(1)}% Service Premium` : 'Heuristic Baseline')}
            </Badge>
          </div>

          <div className="flex items-baseline gap-2">
            <div className={`text-2xl font-bold tracking-tight ${performance.cost_reduction_percent >= 0 ? 'text-emerald-700' : 'text-amber-700'}`}>
              {performance.cost_reduction_percent.toFixed(1)}%
            </div>
            <span className={`text-xs font-medium ${performance.cost_savings >= 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
              {performance.cost_savings > 0
                ? `(₹${Math.round(performance.cost_savings).toLocaleString()} saved)`
                : (performance.cost_savings < 0 ? `(₹${Math.round(Math.abs(performance.cost_savings)).toLocaleString()} higher cost)` : 'Reference')}
            </span>
          </div>

          <div className="pt-2 border-t border-slate-100 space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-500 font-mono">Formula:</span>
              <span className="font-mono text-slate-700 font-medium">(baseline &minus; opt) / baseline &times; 100</span>
            </div>
            <div className="text-[11px] text-slate-500 truncate" title={performance.cost_reduction_label}>
              Scope: <span className="text-slate-700 font-medium">Equal demand &amp; constraints</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
