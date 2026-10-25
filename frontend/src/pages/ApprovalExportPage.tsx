import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileCheck2,
  Download,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Filter,
  FileSpreadsheet,
  RotateCcw,
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
  getShipments,
  approveShipment,
  getPlanningRuns,
  getExportShipmentsCSVUrl,
  getExportReceiptsCSVUrl,
  getExportUnmetDemandCSVUrl,
  getExportRiskAnalysisCSVUrl,
} from '../services/api';
import { downloadAuthenticatedFile } from '../services/auth';
import type { ShipmentItem, PlanningRunSummary } from '../types/api';

export const ApprovalExportPage: React.FC = () => {
  const navigate = useNavigate();
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);
  const [planningRuns, setPlanningRuns] = useState<PlanningRunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStalePlanError, setIsStalePlanError] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [filterApproval, setFilterApproval] = useState<string>('pending');

  const fetchShipmentsAndRuns = async () => {
    setLoading(true);
    setError(null);
    setIsStalePlanError(false);
    try {
      const [shipmentData, runData] = await Promise.all([
        getShipments({
          approvalStatus: filterApproval !== 'all' ? filterApproval : undefined,
        }),
        getPlanningRuns(10, 0).catch(() => [] as PlanningRunSummary[]),
      ]);
      setShipments(shipmentData);
      setPlanningRuns(runData);
      if (runData.length > 0 && !selectedRunId) {
        setSelectedRunId(runData[0].run_id);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch shipment proposals');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchShipmentsAndRuns();
  }, [filterApproval]);

  const handleDecision = async (shipmentId: string, approved: boolean) => {
    setActionLoading(shipmentId);
    setError(null);
    setIsStalePlanError(false);
    setSuccessMsg(null);
    try {
      await approveShipment(
        shipmentId,
        approved,
        'HUMAN-PLANNER-01',
        approved ? 'Approved by distribution planning authority' : 'Rejected by planner review'
      );
      setSuccessMsg(`Shipment ${shipmentId} successfully marked as ${approved ? 'APPROVED' : 'REJECTED'}.`);
      await fetchShipmentsAndRuns();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Action failed';
      setError(msg);
      if (msg.includes('Insufficient dispatchable stock') || msg.includes('409') || msg.includes('inactive')) {
        setIsStalePlanError(true);
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleExportClientCSV = () => {
    if (shipments.length === 0) return;

    const headers = [
      'shipment_id',
      'sku_id',
      'product_name',
      'source_location_id',
      'source_location_name',
      'destination_location_id',
      'destination_location_name',
      'quantity',
      'lead_time_days',
      'estimated_arrival_date',
      'estimated_transport_cost_inr',
      'status',
      'approval_status',
      'approved_by',
      'approval_notes',
      'created_at',
    ];

    const rows = shipments.map((s) => [
      s.shipment_id,
      s.sku_id,
      `"${s.product_name || ''}"`,
      s.source_location_id,
      `"${s.source_location_name || ''}"`,
      s.destination_location_id,
      `"${s.destination_location_name || ''}"`,
      s.quantity,
      s.lead_time_days ?? 1.0,
      s.estimated_arrival_date || '',
      s.estimated_transport_cost.toFixed(2),
      s.status,
      s.approval_status,
      s.approved_by || '',
      `"${s.approval_notes || ''}"`,
      s.created_at,
    ]);

    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `stockwise_distribution_plan_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">
              Approval & Export
            </h1>
            <Badge variant="primary" size="sm">Human-in-the-Loop Governance</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Review evidence-backed shipment recommendations, record approval decisions, and download auditable CSV exports.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            leftIcon={<RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />}
            onClick={fetchShipmentsAndRuns}
            disabled={loading}
          >
            Refresh
          </Button>

          <Button
            variant="primary"
            onClick={handleExportClientCSV}
            disabled={shipments.length === 0}
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export Visible Table (CSV)
          </Button>
        </div>
      </div>

      {isStalePlanError && (
        <Alert variant="error" title="Live Stock Revalidation Conflict (Stale Plan)">
          <div className="space-y-2">
            <p>
              <strong>Revalidation check failed:</strong> Dispatchable stock at the source warehouse is no longer sufficient to fulfill this proposed shipment, or the route has been disabled since the plan was solved.
            </p>
            <div className="flex items-center gap-2 pt-1">
              <Button
                size="sm"
                variant="primary"
                leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
                onClick={() => navigate('/optimize')}
              >
                Re-run Optimization Solver
              </Button>
            </div>
          </div>
        </Alert>
      )}

      {error && !isStalePlanError && (
        <Alert variant="error" title="Action Error">
          {error}
        </Alert>
      )}

      {successMsg && (
        <Alert variant="success" title="Decision Recorded">
          {successMsg}
        </Alert>
      )}

      {/* Critical Scope Boundary Alert */}
      <Alert variant="warning" title="PRD Section 2.2 Operational Dispatch Boundary">
        <p>
          <strong>Physical dispatch is outside application scope:</strong> StockWise produces recommendations to support human distribution planners. Approving a proposal records an authorized governance decision—it does <em>not</em> trigger real-time vehicle dispatch, communicate with GPS units, or silently decrement ERP stock balances.
        </p>
      </Alert>

      {/* Feature 12: Direct Export Hub Card */}
      <Card className="border-blue-200 bg-gradient-to-r from-blue-50/50 via-white to-slate-50 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-blue-100 gap-3">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-blue-600" />
            <div>
              <h2 className="text-base font-bold text-slate-900">Auditable CSV Export Hub</h2>
              <p className="text-xs text-slate-500">Download officially formatted CSV datasets with consistent column schemas in INR (₹).</p>
            </div>
          </div>

          {planningRuns.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-600 font-medium">Export Plan Run:</span>
              <select
                value={selectedRunId}
                onChange={(e) => setSelectedRunId(e.target.value)}
                className="text-xs px-2.5 py-1 rounded border border-blue-200 bg-white font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                {planningRuns.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id} ({r.service_level_percent.toFixed(1)}% service)
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <button
            type="button"
            onClick={() => {
              if (selectedRunId) {
                downloadAuthenticatedFile(
                  getExportShipmentsCSVUrl(selectedRunId),
                  `StockWise_Proposed_Shipments_${selectedRunId}.csv`
                );
              }
            }}
            disabled={!selectedRunId}
            className={`p-3 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between text-left cursor-pointer ${!selectedRunId ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <div>
              <span className="text-xs font-bold text-slate-900 block">Proposed Shipments</span>
              <span className="text-[11px] text-slate-500 block mt-0.5">Recommended inter-facility stock transfers</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 pt-2">
              <Download className="w-3.5 h-3.5" /> Download CSV
            </div>
          </button>

          <button
            type="button"
            onClick={() => {
              if (selectedRunId) {
                downloadAuthenticatedFile(
                  getExportReceiptsCSVUrl(selectedRunId),
                  `StockWise_Decision_Receipts_${selectedRunId}.csv`
                );
              }
            }}
            disabled={!selectedRunId}
            className={`p-3 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between text-left cursor-pointer ${!selectedRunId ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <div>
              <span className="text-xs font-bold text-slate-900 block">Decision Receipts</span>
              <span className="text-[11px] text-slate-500 block mt-0.5">Auditable mathematical rationale & rejected alternatives</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 pt-2">
              <Download className="w-3.5 h-3.5" /> Download CSV
            </div>
          </button>

          <button
            type="button"
            onClick={() => {
              if (selectedRunId) {
                downloadAuthenticatedFile(
                  getExportUnmetDemandCSVUrl(selectedRunId),
                  `StockWise_Unmet_Demand_${selectedRunId}.csv`
                );
              }
            }}
            disabled={!selectedRunId}
            className={`p-3 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between text-left cursor-pointer ${!selectedRunId ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <div>
              <span className="text-xs font-bold text-slate-900 block">Unmet Demand Slack</span>
              <span className="text-[11px] text-slate-500 block mt-0.5">Infeasible shortages under transit lead times</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 pt-2">
              <Download className="w-3.5 h-3.5" /> Download CSV
            </div>
          </button>

          <button
            type="button"
            onClick={() => {
              downloadAuthenticatedFile(
                getExportRiskAnalysisCSVUrl(7),
                `StockWise_Stockout_Risk_Analysis_7d.csv`
              );
            }}
            className="p-3 rounded-lg border border-slate-200 bg-white hover:border-blue-400 hover:shadow-sm transition-all flex flex-col justify-between text-left cursor-pointer"
          >
            <div>
              <span className="text-xs font-bold text-slate-900 block">Stockout Risk Analysis</span>
              <span className="text-[11px] text-slate-500 block mt-0.5">Network-wide cover days, critical flags & gap</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 pt-2">
              <Download className="w-3.5 h-3.5" /> Download CSV
            </div>
          </button>
        </div>
      </Card>

      {/* Decision Receipt Architecture Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Decision Receipt Standard (PRD Section 7.7)</CardTitle>
            <Badge variant="neutral" size="sm">Governed Evidence</Badge>
          </div>
          <CardDescription>
            Every shipment proposal was generated with structured mathematical proof and alternative-source rejection logs.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 space-y-2">
            <div className="font-semibold text-[#172033]">Auditable Governance Workflow:</div>
            <p className="text-slate-600 leading-relaxed">
              When an optimization solve is executed, proposed movements are staged with status <code className="bg-amber-100 text-amber-900 px-1 py-0.5 rounded font-mono">proposed</code> and approval status <code className="bg-amber-100 text-amber-900 px-1 py-0.5 rounded font-mono">pending</code>. Planners review quantities, transit lead times, and transport costs before recording approvals or downloading dispatch manifests.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Filter Toolbar */}
      <Card className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-xs font-semibold text-slate-700">Filter Approval Status:</span>
            <select
              value={filterApproval}
              onChange={(e) => setFilterApproval(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-800 font-medium focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              <option value="pending">Pending Review Only</option>
              <option value="approved">Approved Proposals</option>
              <option value="rejected">Rejected Proposals</option>
              <option value="all">All Proposals</option>
            </select>
          </div>

          <span className="text-xs text-slate-500">
            Showing <strong>{shipments.length}</strong> shipment proposals
          </span>
        </div>
      </Card>

      {/* Proposed Movements Table Layout */}
      <div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Shipment ID & SKU</TableHead>
              <TableHead>Source Warehouse</TableHead>
              <TableHead>Destination</TableHead>
              <TableHead className="text-right">Quantity</TableHead>
              <TableHead>Expected ETA</TableHead>
              <TableHead className="text-right">Est. Cost</TableHead>
              <TableHead>Approval Status</TableHead>
              <TableHead className="text-center">Governance Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={8} className="text-center py-12 text-slate-500">
                  <div className="flex items-center justify-center gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
                    <span>Loading shipment proposals...</span>
                  </div>
                </TableCell>
              </TableRow>
            ) : shipments.length > 0 ? (
              shipments.map((item) => (
                <TableRow key={item.shipment_id} className="hover:bg-slate-50/70">
                  <TableCell>
                    <div className="font-mono text-xs font-bold text-slate-900">{item.shipment_id}</div>
                    <div className="text-[11px] text-slate-500">{item.sku_id} • {item.product_name || 'FMCG SKU'}</div>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs font-medium text-slate-900">{item.source_location_name || item.source_location_id}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{item.source_location_id}</div>
                  </TableCell>
                  <TableCell>
                    <div className="text-xs font-medium text-slate-900">{item.destination_location_name || item.destination_location_id}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{item.destination_location_id}</div>
                  </TableCell>
                  <TableCell className="text-right font-mono font-bold text-blue-700">
                    {item.quantity.toLocaleString()} cases
                  </TableCell>
                  <TableCell className="text-xs text-slate-700">
                    {item.estimated_arrival_date ? new Date(item.estimated_arrival_date).toLocaleString() : 'N/A'}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs font-medium text-slate-800">
                    ₹{item.estimated_transport_cost.toFixed(2)}
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        item.approval_status === 'approved'
                          ? 'success'
                          : item.approval_status === 'rejected'
                          ? 'critical'
                          : 'warning'
                      }
                    >
                      {item.approval_status.toUpperCase()}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    {item.approval_status === 'pending' ? (
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => handleDecision(item.shipment_id, true)}
                          disabled={actionLoading === item.shipment_id}
                          leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                        >
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleDecision(item.shipment_id, false)}
                          disabled={actionLoading === item.shipment_id}
                          leftIcon={<XCircle className="w-3.5 h-3.5 text-rose-600" />}
                        >
                          Reject
                        </Button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400 font-mono">
                        {item.approved_by || 'Decision Recorded'}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={8} className="p-0">
                  <EmptyState
                    icon={FileCheck2}
                    title="No shipment proposals found"
                    description={`There are currently no shipment proposals with status '${filterApproval}'. Run a distribution solve to generate new proposals.`}
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
