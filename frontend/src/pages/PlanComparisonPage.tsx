import React from 'react';
import { useNavigate } from 'react-router-dom';
import { GitCompare, Sparkles } from 'lucide-react';
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
import type { PlanComparisonMetrics } from '../types/optimization';

export const PlanComparisonPage: React.FC = () => {
  const navigate = useNavigate();

  // Honest state: zero runs exist yet
  const comparisonPlans: PlanComparisonMetrics[] = [];

  const comparisonMetricsDefinition = [
    {
      metric: 'Service Level (Fill Rate %)',
      description: 'Fulfilled customer demand / total modeled demand under identical cutoffs.',
      formula: '(fulfilled_units / modeled_demand) × 100',
    },
    {
      metric: 'Unmet Demand (Shortfall Units)',
      description: 'Demand that could not be served by current stock or feasible replenishment.',
      formula: '∑ max(0, demand − existing_stock − transfers)',
    },
    {
      metric: 'Estimated Transport Cost',
      description: 'Calculated using identical carrier rates per lane, not straight-line distance.',
      formula: '∑ (unit_rate × units_shipped)',
    },
    {
      metric: 'Constraint Violations',
      description: 'Allocations exceeding source stock, forbidden routes, or missed deadlines.',
      formula: 'Strict zero-tolerance policy (0 hard violations)',
    },
    {
      metric: 'Stock Utilization Efficiency',
      description: 'Percentage of dispatchable warehouse inventory productively allocated.',
      formula: '(allocated_stock / total_dispatchable) × 100',
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">Plan Comparison</h1>
            <Badge variant="neutral" size="sm">Fair Baseline Benchmark</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Benchmark the service-first optimizer against a deterministic nearest-eligible-source policy.
          </p>
        </div>

        <Button
          variant="outline"
          leftIcon={<Sparkles className="w-4 h-4" />}
          onClick={() => navigate('/optimize')}
        >
          View Plan Solver
        </Button>
      </div>

      {/* PRD Fair Benchmark Policy */}
      <Alert variant="info" title="PRD Section 7.6 Fair Baseline Standard">
        The baseline policy is <strong>nearest eligible warehouse</strong>, allocating limited source stock across destinations proportionally to uncovered demand. Both plans are evaluated on the exact same snapshot, delivery cutoffs, and transport rate tables. A lower-cost plan that serves fewer customers must show that trade-off prominently.
      </Alert>

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

      {/* Comparison Table Layout */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Comparison Metric</TableHead>
            <TableHead className="text-right">Optimized Plan (OR-Tools)</TableHead>
            <TableHead className="text-right">Baseline (Nearest Eligible)</TableHead>
            <TableHead className="text-right">Net Variance</TableHead>
            <TableHead>Operational Trade-off</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {comparisonPlans.length > 0 ? (
            comparisonPlans.map((plan) => (
              <TableRow key={plan.planId}>
                <TableCell>{plan.name}</TableCell>
                <TableCell className="text-right font-mono">{plan.serviceLevelPercent}%</TableCell>
                <TableCell className="text-right font-mono">{plan.fulfilledDemandUnits}</TableCell>
                <TableCell className="text-right font-mono">{plan.estimatedTransportCost}</TableCell>
                <TableCell>
                  <Badge variant="success">Optimized</Badge>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={5} className="p-0">
                <EmptyState
                  icon={GitCompare}
                  title="No plan comparison runs available"
                  description="Comparative analysis requires at least one completed optimization solve. When a plan is generated, it will be automatically benchmarked against the nearest-source policy."
                  actionLabel="Go to Optimizer"
                  onAction={() => navigate('/optimize')}
                  className="border-0 rounded-none py-12"
                />
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
};
