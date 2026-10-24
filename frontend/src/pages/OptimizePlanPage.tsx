import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  Lock,
  XCircle,
  ArrowRight,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '../components/ui/Card';
import { EmptyState } from '../components/ui/EmptyState';

export const OptimizePlanPage: React.FC = () => {
  const navigate = useNavigate();

  // Honest state: prerequisites are not met yet
  const prerequisites = [
    {
      id: 'inventory',
      label: 'Validated Inventory Snapshot',
      ready: false,
      detail: '0 dispatchable warehouse records available',
      action: () => navigate('/inventory'),
    },
    {
      id: 'demand',
      label: 'Calibrated Demand Forecast',
      ready: false,
      detail: '0 destination demand estimates available',
      action: () => navigate('/risk-demand'),
    },
    {
      id: 'routes',
      label: 'Permitted Route & Rate Matrix',
      ready: false,
      detail: '0 eligible transit lanes registered',
      action: () => navigate('/imports'),
    },
    {
      id: 'leadtimes',
      label: 'Delivery Window Cutoffs',
      ready: false,
      detail: 'Transit lead time cutoffs unverified',
      action: () => navigate('/imports'),
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">
              Optimize Distribution Plan
            </h1>
            <Badge variant="neutral" size="sm">Google OR-Tools Engine</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Service-first constrained solver allocating available supply to permitted routes.
          </p>
        </div>

        {/* Disabled Run Button with honest tooltip */}
        <div className="relative group">
          <Button
            variant="primary"
            disabled
            leftIcon={<Lock className="w-4 h-4" />}
          >
            Generate Plan (Disabled)
          </Button>
          <div className="absolute right-0 top-full mt-2 hidden group-hover:block w-72 p-2 bg-slate-900 text-white text-[11px] rounded-lg shadow-xl z-20">
            Execution is locked until real inventory snapshots, demand forecasts, and permitted route constraints are available.
          </div>
        </div>
      </div>

      {/* Scope Alert */}
      <Alert variant="warning" title="Prerequisites Required for Solver Execution (PRD P0-05)">
        A distribution plan can only be generated after validated inventory positions, 7-day demand projections, and permitted transport routes are loaded. The engine enforces hard feasibility constraints and never invents synthetic allocations.
      </Alert>

      {/* Two Column Grid: Solver Parameters + Prerequisite Gates */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Solver Architecture & Settings */}
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Optimization Policy: Service-First Lexicographic</CardTitle>
                <Badge variant="primary" size="sm">PRD 7.5 Objective</Badge>
              </div>
              <CardDescription>
                To avoid artificially cheap zero-shipment solutions, the solver optimizes sequentially in two stages:
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-4 rounded-xl border border-blue-100 bg-blue-50/40 text-xs">
                <div className="font-semibold text-blue-900 mb-1">Stage 1: Maximize Fulfilled Demand</div>
                <p className="text-blue-800 leading-relaxed font-mono text-[11px]">
                  min ∑ (p_jk × u_jk)
                </p>
                <p className="text-slate-600 text-[11px] mt-1">
                  Minimizes weighted unmet demand (u_jk) across destination locations, ensuring customer service is maximized first.
                </p>
              </div>

              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/70 text-xs">
                <div className="font-semibold text-slate-800 mb-1">Stage 2: Minimize Transport Cost</div>
                <p className="text-slate-700 leading-relaxed font-mono text-[11px]">
                  min ∑ (c_ijk × x_ijk) subject to Stage 1 optimality
                </p>
                <p className="text-slate-600 text-[11px] mt-1">
                  Finds the least-cost transport route that satisfies the highest attainable service level without dropping any demand.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Planning Horizon
                  </label>
                  <select
                    disabled
                    className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-500 cursor-not-allowed"
                  >
                    <option>7 Days (Standard P0 Horizon)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Case-Pack Enforcement
                  </label>
                  <select
                    disabled
                    className="w-full text-xs px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-500 cursor-not-allowed"
                  >
                    <option>Integer case packs required</option>
                  </select>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Prerequisite Verification Status */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Prerequisite Checklist</CardTitle>
            <CardDescription>
              All four gates must be verified before solver activation.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {prerequisites.map((req) => (
              <div
                key={req.id}
                onClick={req.action}
                className="p-3 rounded-lg border border-[#E5E7EB] bg-slate-50/40 hover:bg-slate-50 hover:border-slate-300 transition-colors cursor-pointer group"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold text-slate-800 group-hover:text-blue-600 transition-colors">
                    {req.label}
                  </span>
                  <XCircle className="w-4 h-4 text-rose-500" />
                </div>
                <div className="text-[11px] text-slate-500 flex items-center justify-between">
                  <span>{req.detail}</span>
                  <ArrowRight className="w-3 h-3 text-slate-300 group-hover:text-blue-600" />
                </div>
              </div>
            ))}
          </CardContent>
          <CardFooter>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => navigate('/imports')}
            >
              Fulfill Prerequisites at Import
            </Button>
          </CardFooter>
        </Card>
      </div>

      {/* Empty State */}
      <EmptyState
        icon={Sparkles}
        title="No active plan recommendations"
        description="The optimization solver is currently idle. When all input snapshots and constraint matrices are validated, recommendations will generate here with transparent Decision Receipts."
      />
    </div>
  );
};
