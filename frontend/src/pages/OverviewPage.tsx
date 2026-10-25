import React from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import {
  Boxes,
  AlertTriangle,
  TrendingUp,
  FileText,
  UploadCloud,
  CheckCircle2,
  ArrowRight,
  Database,
  Server,
  Activity,
  Clock,
  Sparkles,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { SummaryCard } from '../components/ui/SummaryCard';
import { EmptyState } from '../components/ui/EmptyState';
import { Badge } from '../components/ui/Badge';
import type { UseHealthReturn } from '../hooks/useHealth';

interface OutletContextType {
  health: UseHealthReturn;
}

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { health } = useOutletContext<OutletContextType>();

  const isApiOnline = !health.error && health.data?.api === 'online';
  const isDbConnected = Boolean(health.data?.database?.connected);

  const workflowSteps = [
    {
      num: '01',
      title: 'Import',
      description: 'Upload CSV/Excel templates for products, stock, sales, and route networks.',
      path: '/imports',
      active: false,
    },
    {
      num: '02',
      title: 'Validate',
      description: 'Isolate invalid rows with specific error codes before any snapshot is accepted.',
      path: '/imports',
      active: false,
    },
    {
      num: '03',
      title: 'Forecast',
      description: 'Estimate 7-day SKU demand by destination using transparent baselines.',
      path: '/risk-demand',
      active: false,
    },
    {
      num: '04',
      title: 'Optimize',
      description: 'Service-first allocation solver matching available stock to permitted routes.',
      path: '/optimize',
      active: false,
    },
    {
      num: '05',
      title: 'Review',
      description: 'Inspect Decision Receipts and compare metrics fairly against nearest-source baseline.',
      path: '/comparison',
      active: false,
    },
    {
      num: '06',
      title: 'Export',
      description: 'Export authorized shipment recommendations for operational dispatch systems.',
      path: '/approval',
      active: false,
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">
              Distribution Overview
            </h1>
            <Badge variant="primary" size="sm">Phase 1 Foundation</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Understand stock availability and prepare smarter distribution decisions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            leftIcon={<UploadCloud className="w-4 h-4" />}
            onClick={() => navigate('/imports')}
          >
            Import Data
          </Button>
        </div>
      </div>

      {/* Summary Cards Grid (Honest zero-data state) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        <SummaryCard
          title="Inventory Health"
          icon={Boxes}
          value="Not available yet"
          subtitle="Awaiting inventory snapshot"
          badgeText="Pending Import"
          badgeVariant="neutral"
          actionText="Go to Import"
          onAction={() => navigate('/imports')}
        />
        <SummaryCard
          title="At-Risk Locations"
          icon={AlertTriangle}
          value="Not available yet"
          subtitle="Stock-cover calculation pending"
          badgeText="Pending Forecast"
          badgeVariant="neutral"
          actionText="View Risk Engine"
          onAction={() => navigate('/risk-demand')}
        />
        <SummaryCard
          title="Forecast Demand"
          icon={TrendingUp}
          value="Not available yet"
          subtitle="7-day demand model uncalibrated"
          badgeText="No Active Run"
          badgeVariant="neutral"
          actionText="View Forecasts"
          onAction={() => navigate('/risk-demand')}
        />
        <SummaryCard
          title="Pending Plans"
          icon={FileText}
          value="Not available yet"
          subtitle="No plans generated yet"
          badgeText="Unscheduled"
          badgeVariant="neutral"
          actionText="Plan Solver"
          onAction={() => navigate('/optimize')}
        />
      </div>

      {/* Main Grid: Getting Started + Planning Workflow */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Getting Started Checklist */}
        <Card className="lg:col-span-1">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Getting Started</CardTitle>
              <Badge variant="neutral" size="sm">Phase 1 Readiness</Badge>
            </div>
            <CardDescription>
              Key milestones for initializing the StockWise distribution intelligence system.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3 p-3 rounded-lg bg-emerald-50/60 border border-emerald-100">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
              <div>
                <div className="text-xs font-semibold text-emerald-900">1. UI & Project Foundation</div>
                <div className="text-[11px] text-emerald-700">Light-theme design system, routing, and live backend health connection active.</div>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <Clock className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
              <div>
                <div className="text-xs font-semibold text-slate-800">2. Ingest Dataset (Phase 2)</div>
                <div className="text-[11px] text-slate-600">Provide SKUs, inventory snapshot, 90-day sales history, locations, and permitted lanes.</div>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <Clock className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
              <div>
                <div className="text-xs font-semibold text-slate-800">3. Run 7-Day Optimization</div>
                <div className="text-[11px] text-slate-600">Google OR-Tools solver resolves shortages while respecting permitted lanes and cutoffs.</div>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
              <Clock className="w-4 h-4 text-slate-400 mt-0.5 shrink-0" />
              <div>
                <div className="text-xs font-semibold text-slate-800">4. Review & Export Receipts</div>
                <div className="text-[11px] text-slate-600">Inspect transparent Decision Receipts and export proposed movements for approval.</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Planning Workflow Visual Progression */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>End-to-End Planning Workflow</CardTitle>
              <span className="text-xs text-[#667085]">P0 Architecture Flow</span>
            </div>
            <CardDescription>
              StockWise executes a sequential pipeline: from raw file validation to constrained human-in-the-loop dispatch approval.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
              {workflowSteps.map((step) => (
                <div
                  key={step.num}
                  onClick={() => navigate(step.path)}
                  className="p-3.5 rounded-lg border border-[#E5E7EB] bg-white hover:border-blue-300 hover:shadow-2xs transition-all cursor-pointer group flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-bold text-blue-600">{step.num}</span>
                      <ArrowRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-blue-600 transition-colors" />
                    </div>
                    <div className="text-xs font-semibold text-[#172033] mb-1 group-hover:text-blue-600 transition-colors">
                      {step.title}
                    </div>
                    <p className="text-[11px] text-[#667085] leading-relaxed">
                      {step.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 p-3 rounded-lg bg-blue-50/60 border border-blue-100 flex items-center justify-between text-xs text-blue-900">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-blue-600 shrink-0" />
                <span>
                  <strong>Strict Integrity Rule:</strong> The engine never invents stock or conceals unmet demand.
                </span>
              </div>
              <Button size="sm" variant="outline" onClick={() => navigate('/imports')}>
                Start at Import
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Two Column Lower Section: System Status + Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Real System Status */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-600" />
                <CardTitle>System & Database Status</CardTitle>
              </div>
              <Button
                variant="outline"
                size="sm"
                isLoading={health.loading}
                onClick={health.refetch}
              >
                Run Diagnostics
              </Button>
            </div>
            <CardDescription>
              Live runtime status evaluated via backend health endpoint <code className="text-slate-700 bg-slate-100 px-1 py-0.5 rounded">/api/health</code>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* API Service Row */}
            <div className="flex items-center justify-between p-3 rounded-lg border border-[#E5E7EB] bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-600">
                  <Server className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-[#172033]">FastAPI Service</div>
                  <div className="text-[11px] text-[#667085]">
                    {health.data?.environment ? `Env: ${health.data.environment}` : 'Local service port 8000'}
                  </div>
                </div>
              </div>
              <div>
                {isApiOnline ? (
                  <Badge variant="success" dot size="sm">Online</Badge>
                ) : (
                  <Badge variant="critical" dot size="sm">Unreachable</Badge>
                )}
              </div>
            </div>

            {/* Database Engine Row */}
            <div className="flex items-center justify-between p-3 rounded-lg border border-[#E5E7EB] bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-600">
                  <Database className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-[#172033]">PostgreSQL Database</div>
                  <div className="text-[11px] text-[#667085]">
                    {health.data?.database?.dialect ? `Dialect: ${health.data.database.dialect}` : 'PostgreSQL 16'}
                  </div>
                </div>
              </div>
              <div>
                {isDbConnected ? (
                  <Badge variant="success" dot size="sm">
                    Connected ({health.data?.database?.latency_ms ?? 0}ms)
                  </Badge>
                ) : (
                  <Badge variant="warning" dot size="sm">
                    {health.error ? 'Unknown' : 'Disconnected'}
                  </Badge>
                )}
              </div>
            </div>

            {/* Algorithm Validation Engine Row */}
            <div className="flex items-center justify-between p-3 rounded-lg border border-[#E5E7EB] bg-slate-50/50">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-emerald-600">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-semibold text-[#172033]">Algorithm Validation (16 Modules)</div>
                  <div className="text-[11px] text-[#667085]">
                    {health.data?.validation_summary ? (
                      <span>
                        Coverage: {health.data.validation_summary.overall_feature_coverage_percent.toFixed(0)}% • {health.data.validation_summary.total_passed} checks verified
                      </span>
                    ) : (
                      'Automated regression engine'
                    )}
                  </div>
                </div>
              </div>
              <div>
                {health.data?.validation_summary?.overall_test_pass_rate_percent != null ? (
                  <Badge variant="success" dot size="sm">
                    {health.data.validation_summary.overall_test_pass_rate_percent.toFixed(1)}% Pass Rate
                  </Badge>
                ) : (
                  <Badge variant="neutral" size="sm">Active</Badge>
                )}
              </div>
            </div>

            {/* Message detail */}
            <div className="p-3 rounded-lg bg-white border border-[#E5E7EB] text-xs text-slate-600">
              <div className="font-medium text-[#172033] mb-1">Database Health Check Log:</div>
              <p className="text-[11px] text-slate-600 font-mono bg-slate-50 p-2 rounded border border-slate-100">
                {health.error
                  ? `Connection error: ${health.error}`
                  : health.data?.database?.message || 'Evaluating system health...'}
              </p>
            </div>

            <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
              <span>Last checked: {health.lastChecked ? health.lastChecked.toLocaleTimeString() : 'Never'}</span>
              <button
                type="button"
                onClick={() => navigate('/system-health')}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
              >
                <span>View Full Validation Report</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Honest Recent Activity State */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent Activity</CardTitle>
              <Badge variant="neutral" size="sm">Audit Log</Badge>
            </div>
            <CardDescription>
              Recorded optimization runs, import batches, and approval actions.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Activity}
              title="No planning activity recorded yet"
              description="No datasets have been imported or optimization runs executed. Connect and validate your dataset to initiate your first distribution planning cycle."
              actionLabel="Import Data"
              onAction={() => navigate('/imports')}
              className="border-dashed"
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
