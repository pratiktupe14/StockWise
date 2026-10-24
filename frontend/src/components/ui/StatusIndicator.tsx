import React, { useState } from 'react';
import type { HealthResponse } from '../../types/api';
import { RefreshCw, Database, Server, CheckCircle2, AlertTriangle, XCircle, ChevronDown } from 'lucide-react';

export interface StatusIndicatorProps {
  data: HealthResponse | null;
  loading: boolean;
  error: string | null;
  lastChecked: Date | null;
  onRefresh: () => Promise<void>;
  compact?: boolean;
}

type StatusConfig = {
  label: string;
  variant: 'neutral' | 'critical' | 'success' | 'warning';
  dotColor: string;
  borderColor: string;
  bgColor: string;
  textColor: string;
  icon: React.ReactNode;
};

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  data,
  loading,
  error,
  lastChecked,
  onRefresh,
  compact = false,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefreshClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  };

  // Determine state
  const isApiOnline = !error && data?.api === 'online';
  const isDbConnected = Boolean(data?.database?.connected);

  let statusConfig: StatusConfig = {
    label: 'Connecting...',
    variant: 'neutral',
    dotColor: 'bg-slate-400',
    borderColor: 'border-slate-200',
    bgColor: 'bg-slate-50',
    textColor: 'text-slate-600',
    icon: <RefreshCw className="w-3.5 h-3.5 animate-spin text-slate-500" />,
  };

  if (error) {
    statusConfig = {
      label: 'Backend Offline',
      variant: 'critical',
      dotColor: 'bg-rose-500',
      borderColor: 'border-rose-200',
      bgColor: 'bg-rose-50',
      textColor: 'text-rose-700',
      icon: <XCircle className="w-3.5 h-3.5 text-rose-600" />,
    };
  } else if (isApiOnline && isDbConnected) {
    statusConfig = {
      label: 'System Healthy',
      variant: 'success',
      dotColor: 'bg-emerald-500',
      borderColor: 'border-emerald-200',
      bgColor: 'bg-emerald-50',
      textColor: 'text-emerald-700',
      icon: <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />,
    };
  } else if (isApiOnline && !isDbConnected) {
    statusConfig = {
      label: 'DB Disconnected',
      variant: 'warning',
      dotColor: 'bg-amber-500',
      borderColor: 'border-amber-200',
      bgColor: 'bg-amber-50',
      textColor: 'text-amber-800',
      icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />,
    };
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg border transition-all text-xs font-medium cursor-pointer ${statusConfig.bgColor} ${statusConfig.borderColor} ${statusConfig.textColor} hover:opacity-90 focus-visible:ring-2 focus-visible:ring-blue-600`}
        aria-label="System Connection Status"
        aria-expanded={isOpen}
      >
        <span className="relative flex h-2 w-2">
          {isApiOnline && (
            <span
              className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${statusConfig.dotColor}`}
            />
          )}
          <span className={`relative inline-flex rounded-full h-2 w-2 ${statusConfig.dotColor}`} />
        </span>

        {!compact && (
          <span className="truncate max-w-[140px] hidden sm:inline">{statusConfig.label}</span>
        )}

        <ChevronDown className={`w-3 h-3 transition-transform text-slate-400 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Popover Card */}
      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
          <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-lg border border-[#E5E7EB] p-4 z-50 text-left">
            <div className="flex items-center justify-between pb-3 border-b border-[#F1F5F9]">
              <div className="flex items-center gap-2">
                {statusConfig.icon}
                <span className="font-semibold text-xs text-[#172033]">Live Health Diagnostics</span>
              </div>
              <button
                onClick={handleRefreshClick}
                disabled={isRefreshing || loading}
                className="p-1 rounded-md text-slate-500 hover:text-blue-600 hover:bg-slate-100 disabled:opacity-50 cursor-pointer"
                title="Test Connection Now"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing || loading ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <div className="py-3 space-y-2.5 text-xs">
              {/* API Status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-600">
                  <Server className="w-3.5 h-3.5 text-slate-400" />
                  <span>FastAPI Service</span>
                </div>
                {error ? (
                  <span className="font-medium text-rose-600">Unreachable</span>
                ) : (
                  <span className="font-medium text-emerald-600">Online (HTTP 200)</span>
                )}
              </div>

              {/* Database Status */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-slate-600">
                  <Database className="w-3.5 h-3.5 text-slate-400" />
                  <span>Database Engine</span>
                </div>
                {data?.database?.connected ? (
                  <span className="font-medium text-emerald-600">
                    Connected ({data.database.latency_ms ?? 0}ms)
                  </span>
                ) : (
                  <span className="font-medium text-amber-700">
                    {error ? 'Unknown' : 'Disconnected'}
                  </span>
                )}
              </div>

              {/* Details / Message */}
              <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 text-[11px] text-slate-600 break-words">
                <div className="font-medium text-slate-700 mb-0.5">Diagnostic Log:</div>
                {error ? (
                  <div className="text-rose-700">{error}</div>
                ) : data?.database?.message ? (
                  <div>{data.database.message}</div>
                ) : (
                  <div>Fetching status from /api/health...</div>
                )}
              </div>
            </div>

            <div className="pt-2 border-t border-[#F1F5F9] flex items-center justify-between text-[11px] text-[#667085]">
              <span>
                Checked: {lastChecked ? lastChecked.toLocaleTimeString() : 'Never'}
              </span>
              <button
                onClick={handleRefreshClick}
                className="text-blue-600 hover:text-blue-700 font-medium cursor-pointer"
              >
                Retry Check
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
