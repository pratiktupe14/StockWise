import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, Calendar, Filter, UploadCloud, RefreshCw, ShieldCheck, Search } from 'lucide-react';
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
import { getInventoryRisks, getDemandForecast } from '../services/api';
import type { RiskAnalysisItem, RiskAnalysisResponse, ForecastResponse } from '../types/api';

export const RiskDemandPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedHorizon, setSelectedHorizon] = useState('7');
  const [riskFilter, setRiskFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [riskData, setRiskData] = useState<RiskAnalysisItem[]>([]);
  const [riskSummary, setRiskSummary] = useState<RiskAnalysisResponse | null>(null);
  const [forecastSummary, setForecastSummary] = useState<ForecastResponse | null>(null);

  const fetchData = async (horizon: number) => {
    setLoading(true);
    setError(null);
    try {
      const [riskRes, fcRes] = await Promise.all([
        getInventoryRisks(horizon),
        getDemandForecast(horizon),
      ]);
      setRiskSummary(riskRes);
      setRiskData(riskRes.items);
      setForecastSummary(fcRes);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load risk and forecast data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(parseInt(selectedHorizon, 10));
  }, [selectedHorizon]);

  const filteredData = riskData.filter((item) => {
    if (riskFilter !== 'all' && item.risk_level !== riskFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchSku = item.sku_id.toLowerCase().includes(q);
      const matchProd = (item.product_name || '').toLowerCase().includes(q);
      const matchDest = (item.destination_name || item.destination_id).toLowerCase().includes(q);
      return matchSku || matchProd || matchDest;
    }
    return true;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">
              Risk & Demand Intelligence
            </h1>
            <Badge variant="primary" size="sm">Phase 3 Live Models</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Forecast SKU consumption, evaluate days of cover, and isolate impending stockouts.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="primary"
            leftIcon={<TrendingUp className="w-4 h-4" />}
            onClick={() => navigate('/optimize')}
          >
            Optimize Stockouts
          </Button>
          <Button
            variant="outline"
            leftIcon={<RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />}
            onClick={() => fetchData(parseInt(selectedHorizon, 10))}
            disabled={loading}
          >
            Refresh Data
          </Button>
          <Button
            variant="outline"
            leftIcon={<UploadCloud className="w-4 h-4" />}
            onClick={() => navigate('/imports')}
          >
            Import Sales / Inventory
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="error" title="Error Loading Risk Intelligence">
          {error}
        </Alert>
      )}

      {/* Forecast Accuracy & Holdout Evaluation Summary Banner */}
      {forecastSummary?.holdout_evaluation_summary && (
        <Alert variant="info" title="Chronological Holdout Model Evaluation">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span>{forecastSummary.holdout_evaluation_summary}</span>
            <span className="text-xs font-semibold bg-blue-100 text-blue-900 px-2 py-0.5 rounded">
              Verified Out-of-Sample
            </span>
          </div>
        </Alert>
      )}

      {/* PRD Risk Policy Definition Banner */}
      <Alert variant="warning" title="PRD Section 7.8 Configurable Risk Scoring Architecture">
        Stock cover is calculated as{' '}
        <code className="bg-amber-100 text-amber-900 px-1 py-0.5 rounded font-mono">
          Cover Days = (Eligible Destination Stock + Receipts by Cutoff) / Forecast Daily Demand
        </code>
        . If daily demand is 0, the system outputs <em>Adequate / Zero Demand</em> without dividing by zero.
      </Alert>

      {/* Live Risk Level Counts */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4 border-l-4 border-l-rose-500">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-rose-800 uppercase tracking-wider">
              Critical Risk
            </span>
            <span className="text-xl font-bold text-rose-700">
              {riskSummary?.critical_count ?? 0}
            </span>
          </div>
          <div className="text-xs text-slate-700 leading-snug">
            Stockout precedes earliest feasible replenishment delivery ($L_{'{min}'}$).
          </div>
        </Card>

        <Card className="p-4 border-l-4 border-l-amber-500">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-amber-800 uppercase tracking-wider">
              High Risk
            </span>
            <span className="text-xl font-bold text-amber-700">
              {riskSummary?.high_count ?? 0}
            </span>
          </div>
          <div className="text-xs text-slate-700 leading-snug">
            Cover is at or below (Replenishment Lead Time + 2d Safety Buffer).
          </div>
        </Card>

        <Card className="p-4 border-l-4 border-l-blue-500">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-blue-800 uppercase tracking-wider">
              Medium Risk
            </span>
            <span className="text-xl font-bold text-blue-700">
              {riskSummary?.medium_count ?? 0}
            </span>
          </div>
          <div className="text-xs text-slate-700 leading-snug">
            Cover is within standard reorder cycle or has sparse sales history.
          </div>
        </Card>

        <Card className="p-4 border-l-4 border-l-emerald-500">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-emerald-800 uppercase tracking-wider">
              Low / Balanced
            </span>
            <span className="text-xl font-bold text-emerald-700">
              {riskSummary?.low_count ?? 0}
            </span>
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
              className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600 font-medium"
            >
              <option value="7">7 Days (Default P0 Horizon)</option>
              <option value="14">14 Days (Extended Horizon)</option>
              <option value="30">30 Days (Monthly Strategic Outlook)</option>
            </select>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search SKU or destination..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="text-xs pl-8 pr-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-600 w-56"
              />
            </div>

            <div className="flex items-center gap-2">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={riskFilter}
                onChange={(e) => setRiskFilter(e.target.value)}
                className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600"
              >
                <option value="all">All Risk Tiers ({riskData.length})</option>
                <option value="critical">Critical Risk ({riskSummary?.critical_count ?? 0})</option>
                <option value="high">High Risk ({riskSummary?.high_count ?? 0})</option>
                <option value="medium">Medium Risk ({riskSummary?.medium_count ?? 0})</option>
                <option value="low">Low Risk ({riskSummary?.low_count ?? 0})</option>
              </select>
            </div>
          </div>
        </div>
      </Card>

      {/* Risk Table Layout */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>SKU & Product</TableHead>
            <TableHead>Destination</TableHead>
            <TableHead className="text-right">Forecast ({selectedHorizon}d)</TableHead>
            <TableHead className="text-right">Eligible Stock</TableHead>
            <TableHead className="text-right">Incoming</TableHead>
            <TableHead className="text-right">Cover (Days)</TableHead>
            <TableHead className="text-right">Earliest Lead Time</TableHead>
            <TableHead className="text-right text-rose-700 font-semibold">Demand Gap</TableHead>
            <TableHead>Risk Classification</TableHead>
            <TableHead>Primary Risk Factor</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={10} className="text-center py-12 text-slate-500">
                <div className="flex items-center justify-center gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
                  <span>Computing demand forecasts and evaluating inventory risk positions...</span>
                </div>
              </TableCell>
            </TableRow>
          ) : filteredData.length > 0 ? (
            filteredData.map((row) => (
              <TableRow key={`${row.sku_id}-${row.destination_id}`} className="hover:bg-slate-50/60">
                <TableCell>
                  <div className="font-mono text-xs font-semibold text-slate-900">{row.sku_id}</div>
                  <div className="text-[11px] text-slate-500">{row.product_name || 'Standard SKU'}</div>
                </TableCell>
                <TableCell>
                  <div className="text-xs font-medium text-slate-900">{row.destination_name || row.destination_id}</div>
                  <div className="text-[10px] text-slate-400 font-mono">{row.destination_id}</div>
                </TableCell>
                <TableCell className="text-right font-medium">
                  {row.total_forecast_demand.toFixed(1)} <span className="text-[10px] text-slate-400">cases</span>
                </TableCell>
                <TableCell className="text-right">
                  <div>{row.dispatchable_stock.toFixed(0)} <span className="text-[10px] text-slate-400">cases</span></div>
                  {(row.excess_stock ?? 0) > 0 && (
                    <span className="text-[10px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-1.5 py-0.5 rounded inline-block mt-0.5">
                      +{(row.excess_stock ?? 0).toFixed(0)} excess
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  {row.confirmed_incoming > 0 ? (
                    <span className="text-blue-600 font-medium">+{row.confirmed_incoming.toFixed(0)}</span>
                  ) : (
                    <span className="text-slate-400">0</span>
                  )}
                </TableCell>
                <TableCell className="text-right font-semibold">
                  {row.cover_days >= 999 ? '∞' : `${row.cover_days.toFixed(1)}d`}
                </TableCell>
                <TableCell className="text-right text-slate-600">
                  {row.earliest_replenishment_lead_time_days !== null && row.earliest_replenishment_lead_time_days !== undefined
                    ? `${row.earliest_replenishment_lead_time_days.toFixed(1)}d`
                    : 'N/A'}
                </TableCell>
                <TableCell className="text-right font-bold text-rose-600">
                  {row.demand_gap > 0 ? (
                    <span className="bg-rose-50 text-rose-700 px-2 py-0.5 rounded font-mono">
                      {row.demand_gap.toFixed(1)}
                    </span>
                  ) : (
                    <span className="text-emerald-600 text-xs flex items-center justify-end gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> 0.0
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <Badge
                    variant={
                      row.risk_level === 'critical'
                        ? 'critical'
                        : row.risk_level === 'high'
                        ? 'warning'
                        : row.risk_level === 'medium'
                        ? 'primary'
                        : 'success'
                    }
                  >
                    {row.risk_level.toUpperCase()}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs text-slate-600 max-w-xs truncate" title={row.primary_risk_factor}>
                  {row.primary_risk_factor}
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={10} className="p-0">
                <EmptyState
                  icon={TrendingUp}
                  title="No demand forecasts or risk metrics available"
                  description="Demand calculations require sales history observations and an active inventory snapshot. Ingest history via the Import Centre to calculate baseline demand models."
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
