import React from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, User, ChevronRight } from 'lucide-react';
import { StatusIndicator } from '../ui/StatusIndicator';
import type { HealthResponse } from '../../types/api';
import { NAVIGATION_ITEMS } from '../../types/navigation';

export interface TopBarProps {
  onToggleMobileNav: () => void;
  healthData: HealthResponse | null;
  healthLoading: boolean;
  healthError: string | null;
  healthLastChecked: Date | null;
  onRefreshHealth: () => Promise<void>;
}

export const TopBar: React.FC<TopBarProps> = ({
  onToggleMobileNav,
  healthData,
  healthLoading,
  healthError,
  healthLastChecked,
  onRefreshHealth,
}) => {
  const location = useLocation();

  // Find active nav item
  const currentNav = NAVIGATION_ITEMS.find((item) => item.path === location.pathname) || {
    label: 'Overview',
    description: 'Distribution executive summary',
  };

  return (
    <header className="h-16 bg-white border-b border-[#E5E7EB] px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Left: Mobile trigger & Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleMobileNav}
          className="lg:hidden p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors cursor-pointer"
          aria-label="Toggle navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div>
          <div className="flex items-center gap-1.5 text-xs text-[#667085]">
            <span className="hover:text-slate-800">StockWise</span>
            <ChevronRight className="w-3 h-3 text-slate-400" />
            <span className="font-medium text-[#172033]">{currentNav.label}</span>
          </div>
          <h1 className="text-sm font-semibold text-[#172033] tracking-tight hidden sm:block">
            {currentNav.label}
          </h1>
        </div>
      </div>

      {/* Right: Real Backend Health Indicator & Honest Non-authenticated profile placeholder */}
      <div className="flex items-center gap-3">
        {/* Backend Connectivity Status Indicator */}
        <StatusIndicator
          data={healthData}
          loading={healthLoading}
          error={healthError}
          lastChecked={healthLastChecked}
          onRefresh={onRefreshHealth}
        />

        {/* Profile Placeholder explicitly labelled non-authenticated */}
        <div
          className="flex items-center gap-2 pl-3 border-l border-slate-200 select-none text-slate-600"
          title="StockWise Phase 1 Preview — Non-authenticated UI Shell"
        >
          <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-600">
            <User className="w-4 h-4" />
          </div>
          <div className="hidden md:block text-left text-xs leading-tight">
            <div className="font-medium text-[#172033]">Planner View</div>
            <div className="text-[10px] text-[#667085]">Non-authenticated preview</div>
          </div>
        </div>
      </div>
    </header>
  );
};
