import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, Calendar, Filter, UploadCloud } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Card } from '../components/ui/Card';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../components/ui/Table';
import { EmptyState } from '../components/ui/EmptyState';
import type { RiskDemandRecord } from '../types/risk';

export const RiskDemandPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedHorizon, setSelectedHorizon] = useState('7');
  const [riskFilter, setRiskFilter] = useState('all');

  // Honest state: zero rows until sales history is ingested and forecast model is calibrated
  const riskData: RiskDemandRecord[] = [];

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">
              Risk & Demand Intelligence
            </h1>
            <Badge variant="neutral" size="sm">Baseline Forecast Models</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Forecast SKU consumption, evaluate days of cover, and isolate impending stockouts.
          </p>
        </div>

        <Button
          variant="outline"
          leftIcon={<UploadCloud className="w-4 h-4" />}
          onClick={() => navigate('/imports')}
        >
          Import Sales History
        </Button>
      </div>

      {/* PRD Risk Policy Definition Banner */}
      <Alert variant="warning" title="PRD Section 7.8 Configurable Risk Scoring Architecture">
        Stock cover is calculated as{' '}
        <code className="bg-amber-100 text-amber-900 px-1 py-0.5 rounded font-mono">
          Cover Days = (Eligible Destination Stock + Receipts by Cutoff) / Forecast Daily Demand
        </code>
        . If daily demand is 0, the system outputs <em>No Forecast Demand</em> rather than dividing by zero.
      </Alert>

      {/* Risk Level Legend Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 border-l-4 border-l-rose-500">
          <div className="text-xs font-semibold text-rose-800 uppercase tracking-wider mb-1">
            Critical Risk
          </div>
          <div className="text-xs text-slate-700 leading-snug">
            Projected stockout precedes earliest feasible replenishment delivery.
          </div>
        </Card>

        <Card className="p-4 border-l-4 border-l-amber-500">
          <div className="text-xs font-semibold text-amber-800 uppercase tracking-wider mb-1">
            High Risk
          </div>
          <div className="text-xs text-slate-700 leading-snug">
            Cover is at or below (Replenishment Lead Time + Safety Buffer).
          </div>
        </Card>

        <Card className="p-4 border-l-4 border-l-blue-500">
          <div className="text-xs font-semibold text-blue-800 uppercase tracking-wider mb-1">
            Medium Risk
          </div>
          <div className="text-xs text-slate-700 leading-snug">
            Cover is within twice the replenishment threshold.
          </div>
        </Card>

        <Card className="p-4 border-l-4 border-l-emerald-500">
          <div className="text-xs font-semibold text-emerald-800 uppercase tracking-wider mb-1">
            Low / Balanced
          </div>
          <div className="text-xs text-slate-700 leading-snug">
            Sufficient buffer exists throughout the selected planning horizon.
          </div>
        </Card>
      </div>

      {/* Horizon Controls & Filtering */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium text-slate-600 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-slate-400" />
              Planning Horizon:
            </span>
            <select
              value={selectedHorizon}
              onChange={(e) => setSelectedHorizon(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              <option value="7">7 Days (Default P0 Horizon)</option>
              <option value="14">14 Days (Extended)</option>
              <option value="30">30 Days (Monthly Outlook)</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600"
            >
              <option value="all">All Risk Tiers</option>
              <option value="critical">Critical Stockout Risk</option>
              <option value="high">High Risk</option>
              <option value="medium">Medium Risk</option>
              <option value="excess">Excess Stock</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Risk Table Layout */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>SKU</TableHead>
            <TableHead>Destination Location</TableHead>
            <TableHead className="text-right">7-Day Forecast Demand</TableHead>
            <TableHead className="text-right">Eligible Destination Stock</TableHead>
            <TableHead className="text-right">Confirmed Receipts</TableHead>
            <TableHead className="text-right">Cover (Days)</TableHead>
            <TableHead className="text-right text-rose-700 font-semibold">Replenishment Gap</TableHead>
            <TableHead>Risk Classification</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {riskData.length > 0 ? (
            riskData.map((row) => (
              <TableRow key={`${row.sku}-${row.destination}`}>
                <TableCell className="font-mono">{row.sku}</TableCell>
                <TableCell>{row.destination}</TableCell>
                <TableCell className="text-right">{row.forecastDemand}</TableCell>
                <TableCell className="text-right">{row.currentEligibleStock}</TableCell>
                <TableCell className="text-right">{row.confirmedReceipts}</TableCell>
                <TableCell className="text-right">{row.stockCoverDays}</TableCell>
                <TableCell className="text-right font-bold text-rose-600">{row.replenishmentGap}</TableCell>
                <TableCell>
                  <Badge variant={row.riskLevel === 'critical' ? 'critical' : 'warning'}>
                    {row.riskLevel}
                  </Badge>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={8} className="p-0">
                <EmptyState
                  icon={TrendingUp}
                  title="No demand forecasts or risk metrics available"
                  description="Demand calculations require 90 days of daily sales history and an active inventory snapshot. Ingest history via the Import Centre to calculate baseline demand models."
                  actionLabel="Go to Import Centre"
                  onAction={() => navigate('/imports')}
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
