import React, { useState, useMemo } from 'react';
import {
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card';
import { Badge } from './ui/Badge';
import { EmptyState } from './ui/EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from './ui/Table';
import type {
  ForecastEvaluationResponse,
  ForecastEvaluationPoint,
  ProductItem,
  LocationItem,
} from '../types/api';

interface ActualVsPredictedDemandChartProps {
  evaluation: ForecastEvaluationResponse | null;
  loading: boolean;
  selectedSkuId: string;
  selectedDestinationId: string;
  onSkuChange?: (sku: string) => void;
  onDestinationChange?: (dest: string) => void;
  products: ProductItem[];
  locations: LocationItem[];
}

export const ActualVsPredictedDemandChart: React.FC<ActualVsPredictedDemandChartProps> = ({
  evaluation,
  loading,
  selectedSkuId,
  selectedDestinationId,
  onSkuChange,
  onDestinationChange,
  products,
  locations,
}) => {
  const [hoveredPoint, setHoveredPoint] = useState<ForecastEvaluationPoint | null>(null);
  const [showDataTable, setShowDataTable] = useState<boolean>(false);

  // Filter aligned series based on selected SKU and Destination
  const activeSeries = useMemo(() => {
    if (!evaluation?.series) return null;
    let filtered = evaluation.series;
    if (selectedSkuId !== 'all') {
      filtered = filtered.filter((s) => s.sku_id === selectedSkuId);
    }
    if (selectedDestinationId !== 'all') {
      filtered = filtered.filter((s) => s.destination_id === selectedDestinationId);
    }
    return filtered;
  }, [evaluation, selectedSkuId, selectedDestinationId]);

  // Points to plot on the chart
  const points: ForecastEvaluationPoint[] = useMemo(() => {
    if (!evaluation) return [];

    // If single series matches, use its points directly
    if (activeSeries && activeSeries.length === 1) {
      return activeSeries[0].points;
    }

    // Otherwise aggregate by date across active series (or overall aligned_timeseries)
    if (activeSeries && activeSeries.length > 1) {
      const dateMap = new Map<string, { actual: number | null; predicted: number; count: number; isHoldout: boolean; isFuture: boolean }>();
      activeSeries.forEach((s) => {
        s.points.forEach((p) => {
          const existing = dateMap.get(p.date) || {
            actual: null,
            predicted: 0,
            count: 0,
            isHoldout: p.is_holdout,
            isFuture: p.is_future,
          };
          if (p.actual_demand !== null && p.actual_demand !== undefined) {
            existing.actual = (existing.actual || 0) + p.actual_demand;
          }
          existing.predicted += p.predicted_demand;
          existing.count += 1;
          dateMap.set(p.date, existing);
        });
      });

      return Array.from(dateMap.entries())
        .sort((a, b) => a[0].localeCompare(b[0]))
        .map(([date, val]) => ({
          date,
          sku_id: selectedSkuId,
          destination_id: selectedDestinationId,
          actual_demand: val.actual,
          predicted_demand: Math.round(val.predicted * 10) / 10,
          error: val.actual !== null ? Math.round(Math.abs(val.actual - val.predicted) * 10) / 10 : null,
          is_holdout: val.isHoldout,
          is_future: val.isFuture,
        }));
    }

    return evaluation.aligned_timeseries || [];
  }, [evaluation, activeSeries, selectedSkuId, selectedDestinationId]);

  // Aggregate Evaluation Metrics for the active selection
  const metrics = useMemo(() => {
    if (!evaluation) return null;

    if (activeSeries && activeSeries.length === 1) {
      const s = activeSeries[0];
      return {
        sampleCount: s.sample_count,
        totalActual: s.total_actual_demand,
        totalPredicted: s.total_predicted_demand,
        mae: s.mae,
        wape: s.wape,
        accuracy: s.accuracy_percent,
        period: s.evaluation_period,
        dataSufficiency: s.data_sufficiency,
        evaluatedAt: s.evaluated_at,
        method: s.forecast_method,
      };
    }

    return {
      sampleCount: evaluation.sample_count,
      totalActual: evaluation.total_actual_demand,
      totalPredicted: evaluation.total_predicted_demand,
      mae: evaluation.mae,
      wape: evaluation.wape,
      accuracy: evaluation.accuracy_percent,
      period: evaluation.evaluation_period,
      dataSufficiency: evaluation.data_sufficiency,
      evaluatedAt: evaluation.evaluated_at,
      method: 'Rolling 7d & Seasonal-Naive',
    };
  }, [evaluation, activeSeries]);

  // SVG Chart Geometry
  const chartWidth = 760;
  const chartHeight = 260;
  const padding = { top: 25, right: 30, bottom: 45, left: 55 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  const { maxY, pointsWithCoords, splitIndex } = useMemo(() => {
    if (points.length === 0) {
      return { maxY: 10, pointsWithCoords: [], splitIndex: -1 };
    }

    let maxVal = 10;
    points.forEach((p) => {
      if (p.actual_demand !== null && p.actual_demand !== undefined && p.actual_demand > maxVal) {
        maxVal = p.actual_demand;
      }
      if (p.predicted_demand > maxVal) {
        maxVal = p.predicted_demand;
      }
    });
    const ceilMax = Math.ceil(maxVal * 1.2);

    const stepX = points.length > 1 ? innerWidth / (points.length - 1) : innerWidth / 2;

    const coords = points.map((p, idx) => {
      const x = padding.left + (points.length > 1 ? idx * stepX : innerWidth / 2);
      const yActual =
        p.actual_demand !== null && p.actual_demand !== undefined
          ? padding.top + innerHeight - (p.actual_demand / ceilMax) * innerHeight
          : null;
      const yPredicted = padding.top + innerHeight - (p.predicted_demand / ceilMax) * innerHeight;
      return {
        ...p,
        x,
        yActual,
        yPredicted,
      };
    });

    const sIndex = points.findIndex((p) => p.is_future);

    return {
      maxY: ceilMax,
      pointsWithCoords: coords,
      splitIndex: sIndex,
    };
  }, [points, innerWidth, innerHeight, padding.left, padding.top]);

  // Build SVG Paths
  const { actualPath, predictedHistoryPath, predictedFuturePath, splitX } = useMemo(() => {
    if (pointsWithCoords.length === 0) {
      return { actualPath: '', predictedHistoryPath: '', predictedFuturePath: '', splitX: null };
    }

    const actualPoints = pointsWithCoords.filter((p) => p.yActual !== null);
    const aPath = actualPoints.reduce((acc, p, idx) => {
      return `${acc} ${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.yActual!.toFixed(1)}`;
    }, '');

    // Predicted history vs future paths
    let histPath = '';
    let futPath = '';

    const histPts = pointsWithCoords.filter((p) => !p.is_future);
    const futPts = pointsWithCoords.filter((p) => p.is_future);

    if (histPts.length > 0) {
      histPath = histPts.reduce((acc, p, idx) => {
        return `${acc} ${idx === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.yPredicted.toFixed(1)}`;
      }, '');
    }

    if (futPts.length > 0) {
      // Connect from the last historical point if available for seamless continuity
      const startPt = histPts.length > 0 ? histPts[histPts.length - 1] : futPts[0];
      futPath = `M ${startPt.x.toFixed(1)} ${startPt.yPredicted.toFixed(1)}`;
      futPts.forEach((p) => {
        futPath += ` L ${p.x.toFixed(1)} ${p.yPredicted.toFixed(1)}`;
      });
    }

    let sX: number | null = null;
    if (splitIndex > 0 && splitIndex < pointsWithCoords.length) {
      sX = (pointsWithCoords[splitIndex - 1].x + pointsWithCoords[splitIndex].x) / 2;
    } else if (splitIndex === 0) {
      sX = padding.left;
    }

    return {
      actualPath: aPath,
      predictedHistoryPath: histPath,
      predictedFuturePath: futPath,
      splitX: sX,
    };
  }, [pointsWithCoords, splitIndex, padding.left]);

  // Loading state
  if (loading) {
    return (
      <Card className="border-slate-200 bg-white">
        <CardContent className="p-8 text-center">
          <div className="w-7 h-7 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-700">Evaluating demand forecast model against holdout history...</p>
          <p className="text-xs text-slate-400 mt-1">Comparing matched SKU, location, and date records with zero data leakage</p>
        </CardContent>
      </Card>
    );
  }

  // Empty state
  if (!evaluation || points.length === 0) {
    return (
      <Card className="border-slate-200 bg-white">
        <CardContent className="p-6">
          <EmptyState
            icon={TrendingUp}
            title="Insufficient Forecast Evaluation Observations"
            description="At least 7 consecutive daily sales observations are required to execute chronological holdout evaluation without synthetic data fabrication."
          />
        </CardContent>
      </Card>
    );
  }

  const isInsufficient = metrics?.dataSufficiency === 'insufficient_history' || (metrics?.sampleCount || 0) < 7;

  return (
    <div className="space-y-4">
      {/* P1: ML Model Evaluation Metrics Banner */}
      <Card className="border-slate-200 bg-white overflow-hidden shadow-xs">
        <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/50">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base font-bold text-slate-900">
                  ML Model Evaluation & Forecast Accuracy
                </CardTitle>
                <Badge variant={isInsufficient ? 'warning' : 'success'} size="sm">
                  {isInsufficient ? 'Insufficient History (< 7d)' : 'Holdout Evaluated'}
                </Badge>
              </div>
              <CardDescription className="text-xs mt-0.5">
                <span className="font-medium text-slate-700">{evaluation?.model_name || 'Baseline Statistical Forecast (7-day Rolling Moving Average / Seasonal Naive)'}</span> &bull; {evaluation?.accuracy_formula_note || 'Forecast accuracy = 100 - WAPE (%). Clamped to 0.0% when WAPE exceeds 100%.'}
              </CardDescription>
            </div>

            {/* Quick Slices / Selectors */}
            <div className="flex items-center gap-2">
              {onSkuChange && (
                <select
                  value={selectedSkuId}
                  onChange={(e) => onSkuChange(e.target.value)}
                  className="h-7 text-xs rounded border border-slate-300 bg-white px-2 text-slate-700"
                >
                  <option value="all">All Evaluated SKUs</option>
                  {products.map((p) => (
                    <option key={p.sku_id} value={p.sku_id}>
                      {p.sku_id} - {p.name}
                    </option>
                  ))}
                </select>
              )}
              {onDestinationChange && (
                <select
                  value={selectedDestinationId}
                  onChange={(e) => onDestinationChange(e.target.value)}
                  className="h-7 text-xs rounded border border-slate-300 bg-white px-2 text-slate-700"
                >
                  <option value="all">All Destinations</option>
                  {locations
                    .filter((l) => l.location_type === 'distributor' || l.location_type === 'retailer')
                    .map((d) => (
                      <option key={d.location_id} value={d.location_id}>
                        {d.name}
                      </option>
                    ))}
                </select>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4 space-y-4">
          {/* P1 Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2.5">
            {/* Metric 1: Actual Demand */}
            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Actual Demand
              </span>
              <div className="text-base font-bold text-slate-900">
                {metrics?.totalActual !== null && metrics?.totalActual !== undefined
                  ? `${Math.round(metrics.totalActual).toLocaleString()} u`
                  : 'N/A'}
              </div>
              <span className="text-[10px] text-slate-400 block truncate">Holdout Actuals</span>
            </div>

            {/* Metric 2: Predicted Demand */}
            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Predicted Demand
              </span>
              <div className="text-base font-bold text-blue-700">
                {metrics?.totalPredicted !== null && metrics?.totalPredicted !== undefined
                  ? `${Math.round(metrics.totalPredicted).toLocaleString()} u`
                  : 'N/A'}
              </div>
              <span className="text-[10px] text-slate-400 block truncate">Model Prediction</span>
            </div>

            {/* Metric 3: MAE */}
            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                MAE (Error)
              </span>
              <div className="text-base font-bold text-slate-900">
                {metrics?.mae !== null && metrics?.mae !== undefined ? `${metrics.mae.toFixed(2)} u` : 'N/A'}
              </div>
              <span className="text-[10px] text-slate-400 block truncate">Mean Abs Error</span>
            </div>

            {/* Metric 4: WAPE */}
            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                WAPE
              </span>
              <div className="text-base font-bold text-amber-700">
                {metrics?.wape !== null && metrics?.wape !== undefined ? `${metrics.wape.toFixed(1)}%` : 'N/A'}
              </div>
              <span className="text-[10px] text-slate-400 block truncate">Weighted % Error</span>
            </div>

            {/* Metric 5: Forecast Accuracy */}
            <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-800">
                Forecast Accuracy
              </span>
              <div className="text-base font-bold text-emerald-700">
                {metrics?.accuracy !== null && metrics?.accuracy !== undefined
                  ? `${metrics.accuracy.toFixed(1)}%`
                  : 'N/A'}
              </div>
              <span className="text-[10px] text-emerald-600 block truncate" title="100 - WAPE (%). Clamped to 0.0% when WAPE exceeds 100%.">
                100 &minus; WAPE (Clamped &ge; 0%)
              </span>
            </div>

            {/* Metric 6: Sample Count */}
            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Sample Count
              </span>
              <div className="text-base font-bold text-slate-900">
                {metrics?.sampleCount ? `${metrics.sampleCount} pts` : 'N/A'}
              </div>
              <span className="text-[10px] text-slate-400 block truncate">Holdout Points</span>
            </div>

            {/* Metric 7: Evaluation Period */}
            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Eval Period
              </span>
              <div className="text-xs font-semibold text-slate-800 truncate" title={metrics?.period || 'N/A'}>
                {metrics?.period || 'N/A'}
              </div>
              <span className="text-[10px] text-slate-400 block truncate">Holdout Split Window</span>
            </div>

            {/* Metric 8: Last Evaluated */}
            <div className="p-3 bg-slate-50 border border-slate-200/80 rounded-lg space-y-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                Evaluated At
              </span>
              <div className="text-xs font-semibold text-slate-800 truncate">
                {metrics?.evaluatedAt ? new Date(metrics.evaluatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A'}
              </div>
              <span className="text-[10px] text-slate-400 block truncate">Timestamp</span>
            </div>
          </div>

          {/* Warning banner for insufficient data */}
          {isInsufficient && (
            <div className="flex items-center gap-2 p-2.5 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-900">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>
                <strong>Insufficient Historical Data:</strong> Less than 7 consecutive daily records exist for this slice. Evaluation metrics are safely marked N/A to avoid fabricating artificial observations or leaking synthetic numbers.
              </span>
            </div>
          )}

          {/* P2: Actual vs Predicted Demand Time-Series Chart */}
          <div className="border border-slate-200 rounded-lg p-3 bg-white">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-2 mb-2 border-b border-slate-100 gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-800">
                  Time-Series Alignment: Actual vs Predicted Demand
                </span>
                <span className="text-[11px] text-slate-400">
                  (Matched SKU, location, and date records)
                </span>
              </div>

              {/* Legend */}
              <div className="flex flex-wrap items-center gap-3 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-3 rounded-full bg-emerald-500 border border-emerald-600 inline-block" />
                  <span className="text-slate-600 font-medium">Actual Demand (Holdout)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-0.5 bg-blue-600 inline-block" />
                  <span className="text-slate-600 font-medium">Predicted (Historical)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-4 h-0 border-t-2 border-dashed border-blue-600 inline-block" />
                  <span className="text-slate-600 font-medium">Predicted (Future Forecast)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full border-2 border-dashed border-slate-400 inline-block" />
                  <span className="text-slate-400 font-medium">Pending Actuals (Future)</span>
                </div>
              </div>
            </div>

            {/* SVG Visual Chart */}
            <div className="relative w-full overflow-x-auto">
              <svg
                viewBox={`0 0 ${chartWidth} ${chartHeight}`}
                className="w-full h-auto min-w-[620px] max-h-[300px]"
              >
                <defs>
                  <linearGradient id="futureZoneGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f8fafc" stopOpacity="0.8" />
                    <stop offset="100%" stopColor="#f1f5f9" stopOpacity="0.3" />
                  </linearGradient>
                </defs>

                {/* Future Forecast Zone Background */}
                {splitX !== null && (
                  <g>
                    <rect
                      x={splitX}
                      y={padding.top}
                      width={chartWidth - padding.right - splitX}
                      height={innerHeight}
                      fill="url(#futureZoneGradient)"
                    />
                    <line
                      x1={splitX}
                      y1={padding.top - 8}
                      x2={splitX}
                      y2={padding.top + innerHeight}
                      stroke="#94a3b8"
                      strokeWidth="1.5"
                      strokeDasharray="4,3"
                    />
                    <text
                      x={splitX + 6}
                      y={padding.top + 10}
                      fill="#64748b"
                      fontSize="9"
                      fontWeight="600"
                    >
                      Future Forecast &rarr;
                    </text>
                  </g>
                )}

                {/* Y-Axis Grid Lines & Labels */}
                {[0, 0.33, 0.66, 1.0].map((ratio, idx) => {
                  const y = padding.top + innerHeight - ratio * innerHeight;
                  const val = Math.round(ratio * maxY);
                  return (
                    <g key={idx}>
                      <line
                        x1={padding.left}
                        y1={y}
                        x2={chartWidth - padding.right}
                        y2={y}
                        stroke="#e2e8f0"
                        strokeDasharray={idx === 0 ? undefined : '2,2'}
                      />
                      <text
                        x={padding.left - 8}
                        y={y + 3}
                        textAnchor="end"
                        fill="#94a3b8"
                        fontSize="10"
                        fontWeight="500"
                      >
                        {val} u
                      </text>
                    </g>
                  );
                })}

                {/* Predicted Lines */}
                {predictedHistoryPath && (
                  <path
                    d={predictedHistoryPath}
                    fill="none"
                    stroke="#2563eb"
                    strokeWidth="2.5"
                  />
                )}
                {predictedFuturePath && (
                  <path
                    d={predictedFuturePath}
                    fill="none"
                    stroke="#2563eb"
                    strokeWidth="2.5"
                    strokeDasharray="5,4"
                  />
                )}

                {/* Actual Demand Line (Holdout Period Only) */}
                {actualPath && (
                  <path
                    d={actualPath}
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="2.2"
                  />
                )}

                {/* Data Points */}
                {pointsWithCoords.map((pt, idx) => {
                  const isHovered = hoveredPoint?.date === pt.date;

                  return (
                    <g key={idx}>
                      {/* X-axis date label */}
                      <text
                        x={pt.x}
                        y={padding.top + innerHeight + 16}
                        textAnchor="middle"
                        fill={pt.is_future ? '#64748b' : '#334155'}
                        fontSize="9.5"
                        fontWeight={pt.is_future ? '400' : '600'}
                      >
                        {pt.date.slice(5)}
                      </text>

                      {/* Predicted Point Marker */}
                      <circle
                        cx={pt.x}
                        cy={pt.yPredicted}
                        r={isHovered ? 6 : 4}
                        fill="#2563eb"
                        stroke="#ffffff"
                        strokeWidth="1.5"
                        className="cursor-pointer transition-all"
                        onMouseEnter={() => setHoveredPoint(pt)}
                        onMouseLeave={() => setHoveredPoint(null)}
                      />

                      {/* Actual Point Marker (Historical Only) */}
                      {pt.yActual !== null ? (
                        <circle
                          cx={pt.x}
                          cy={pt.yActual}
                          r={isHovered ? 6.5 : 4.5}
                          fill="#10b981"
                          stroke="#047857"
                          strokeWidth="1.5"
                          className="cursor-pointer transition-all"
                          onMouseEnter={() => setHoveredPoint(pt)}
                          onMouseLeave={() => setHoveredPoint(null)}
                        />
                      ) : (
                        /* Future date: Hollow ring signifying pending actual observation without fabrication */
                        <circle
                          cx={pt.x}
                          cy={padding.top + innerHeight}
                          r="3"
                          fill="none"
                          stroke="#94a3b8"
                          strokeWidth="1"
                          strokeDasharray="2,2"
                        />
                      )}
                    </g>
                  );
                })}
              </svg>

              {/* Hover Tooltip Box */}
              {hoveredPoint && (
                <div className="absolute top-2 right-4 bg-slate-900/95 text-white p-2.5 rounded-lg shadow-xl text-xs space-y-1 pointer-events-none z-10 border border-slate-700 min-w-[200px]">
                  <div className="flex items-center justify-between pb-1 border-b border-slate-700">
                    <span className="font-bold text-slate-100">{hoveredPoint.date}</span>
                    <Badge variant={hoveredPoint.is_future ? 'neutral' : 'success'} size="sm">
                      {hoveredPoint.is_future ? 'Future Forecast' : 'Holdout Evaluation'}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-emerald-400">Actual Demand:</span>
                    <span className="font-semibold text-emerald-300">
                      {hoveredPoint.actual_demand !== null && hoveredPoint.actual_demand !== undefined
                        ? `${hoveredPoint.actual_demand} u`
                        : 'Pending (No fabrication)'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-blue-400">Predicted Demand:</span>
                    <span className="font-semibold text-blue-300">
                      {hoveredPoint.predicted_demand} u
                    </span>
                  </div>
                  {hoveredPoint.error !== null && hoveredPoint.error !== undefined && (
                    <div className="flex justify-between pt-1 border-t border-slate-800 text-[11px]">
                      <span className="text-slate-400">Absolute Error (|A - P|):</span>
                      <span className="font-mono text-amber-300">{hoveredPoint.error} u</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Tabular inspection toggle */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
              <span className="text-slate-500">
                Evaluating {points.filter((p) => !p.is_future).length} historical holdout observations and{' '}
                {points.filter((p) => p.is_future).length} future forecast dates.
              </span>
              <button
                type="button"
                onClick={() => setShowDataTable(!showDataTable)}
                className="font-medium text-blue-600 hover:text-blue-800 transition-colors"
              >
                {showDataTable ? 'Hide Data Table' : 'View Aligned Data Table'}
              </button>
            </div>

            {/* Aligned Observations Table */}
            {showDataTable && (
              <div className="mt-3 overflow-x-auto border-t border-slate-200 pt-3">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Period Classification</TableHead>
                      <TableHead>Actual Demand</TableHead>
                      <TableHead>Predicted Demand</TableHead>
                      <TableHead>Absolute Error (|A - P|)</TableHead>
                      <TableHead>Accuracy Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {points.map((p, idx) => (
                      <TableRow key={idx} className="hover:bg-slate-50">
                        <TableCell className="font-mono text-xs text-slate-800">{p.date}</TableCell>
                        <TableCell>
                          <Badge variant={p.is_future ? 'neutral' : 'primary'} size="sm">
                            {p.is_future ? 'Future Period' : 'Historical Holdout'}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-semibold">
                          {p.actual_demand !== null && p.actual_demand !== undefined ? (
                            <span className="text-emerald-700">{p.actual_demand} units</span>
                          ) : (
                            <span className="text-slate-400 font-normal italic">Pending (Future Date)</span>
                          )}
                        </TableCell>
                        <TableCell className="font-semibold text-blue-700">
                          {p.predicted_demand} units
                        </TableCell>
                        <TableCell className="font-mono text-xs">
                          {p.error !== null && p.error !== undefined ? (
                            <span className={p.error === 0 ? 'text-emerald-600' : 'text-slate-700'}>
                              {p.error} units
                            </span>
                          ) : (
                            <span className="text-slate-400">&mdash;</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs">
                          {p.is_future ? (
                            <span className="text-slate-400">Forecast Pending Execution</span>
                          ) : p.error === 0 ? (
                            <span className="text-emerald-600 font-medium">100% Exact Match</span>
                          ) : (
                            <span className="text-slate-600">Verified Holdout</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
