import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileCheck2,
  Download,
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
import type { DecisionReceipt } from '../types/optimization';

export const ApprovalExportPage: React.FC = () => {
  const navigate = useNavigate();

  // Honest state: zero pending proposals until optimization runs exist
  const pendingReceipts: DecisionReceipt[] = [];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">
              Approval & Export
            </h1>
            <Badge variant="neutral" size="sm">Human-in-the-Loop Governance</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Review evidence-backed shipment recommendations, record approval, and export plan files.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            disabled
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export Proposed Plan (CSV)
          </Button>
        </div>
      </div>

      {/* Critical Scope Boundary Alert */}
      <Alert variant="warning" title="PRD Section 2.2 Operational Dispatch Boundary">
        <div className="space-y-1">
          <p>
            <strong>Physical dispatch is outside application scope:</strong> StockWise produces recommendations to support human planners. Approving a proposal records an authorized governance decision—it does <em>not</em> trigger real-time vehicle dispatch, communicate with GPS units, or silently decrement ERP stock balances.
          </p>
        </div>
      </Alert>

      {/* Decision Receipt Architecture Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Decision Receipt Standard (PRD Section 7.7)</CardTitle>
            <Badge variant="primary" size="sm">Key Differentiator</Badge>
          </div>
          <CardDescription>
            Every shipment proposal includes structured mathematical evidence, not black-box predictions.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-2">
            <div className="font-semibold text-[#172033]">Illustrative Decision Receipt Format:</div>
            <div className="font-mono text-[11px] p-3 rounded-lg bg-white border border-slate-200 text-slate-800 leading-relaxed">
              <strong>Proposed: Send 40 units of SKU A from Warehouse West to Distributor North.</strong><br />
              • Demand gap: 40 units across the selected 7-day horizon.<br />
              • Warehouse East excluded: 0 eligible dispatchable units (100 on-hand, 80 reserved, 20 blocked).<br />
              • Warehouse West selected: 100 eligible units; permitted lane and delivery window verified.<br />
              • Quantity allocated: 40 cases; Estimated transport cost: ₹2,400 (configured rate: ₹60/case).<br />
              • Remaining service gap: 0 units if shipment arrives by day 4 cutoff.
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Proposed Movements Table Layout */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-[#172033]">Proposed Shipment Recommendations</h2>
          <span className="text-xs text-[#667085]">Awaiting Manager Review</span>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>SKU</TableHead>
              <TableHead>Source Warehouse</TableHead>
              <TableHead>Destination</TableHead>
              <TableHead className="text-right">Quantity</TableHead>
              <TableHead>Expected ETA</TableHead>
              <TableHead className="text-right">Est. Cost</TableHead>
              <TableHead>Evidence / Decision Receipt</TableHead>
              <TableHead className="text-center">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {pendingReceipts.length > 0 ? (
              pendingReceipts.map((item) => (
                <TableRow key={item.recommendationId}>
                  <TableCell className="font-mono">{item.sku}</TableCell>
                  <TableCell>{item.source}</TableCell>
                  <TableCell>{item.destination}</TableCell>
                  <TableCell className="text-right font-mono font-bold">{item.quantity} {item.unit}</TableCell>
                  <TableCell>{item.estimatedArrivalDate}</TableCell>
                  <TableCell className="text-right font-mono">₹{item.estimatedCost.toLocaleString()}</TableCell>
                  <TableCell className="text-xs text-slate-600 max-w-xs truncate">{item.evidence}</TableCell>
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <Button size="sm" variant="outline">Approve</Button>
                      <Button size="sm" variant="ghost">Reject</Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={8} className="p-0">
                  <EmptyState
                    icon={FileCheck2}
                    title="No proposed distribution plans awaiting review"
                    description="When an optimization solve is executed, proposed movements with auditable Decision Receipts will appear here for manager review, approval/rejection, and CSV export."
                    actionLabel="View Plan Solver"
                    onAction={() => navigate('/optimize')}
                    className="border-0 rounded-none py-12"
                  />
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
