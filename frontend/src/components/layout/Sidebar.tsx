import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  Boxes,
  LayoutDashboard,
  UploadCloud,
  TrendingUp,
  Sparkles,
  GitCompare,
  FileCheck2,
  PackageCheck,
  ShieldAlert,
} from 'lucide-react';
import { NAVIGATION_ITEMS } from '../../types/navigation';

const iconMap: Record<string, React.ReactNode> = {
  LayoutDashboard: <LayoutDashboard className="w-4 h-4 shrink-0" />,
  UploadCloud: <UploadCloud className="w-4 h-4 shrink-0" />,
  Boxes: <Boxes className="w-4 h-4 shrink-0" />,
  TrendingUp: <TrendingUp className="w-4 h-4 shrink-0" />,
  Sparkles: <Sparkles className="w-4 h-4 shrink-0" />,
  GitCompare: <GitCompare className="w-4 h-4 shrink-0" />,
  FileCheck2: <FileCheck2 className="w-4 h-4 shrink-0" />,
};

export interface SidebarProps {
  onNavClick?: () => void;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({ onNavClick, className = '' }) => {
  return (
    <aside
      className={`w-64 bg-white border-r border-[#E5E7EB] flex flex-col h-full select-none ${className}`}
    >
      {/* Branding Header */}
      <div className="p-5 border-b border-[#F1F5F9]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-xs">
            <PackageCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-base tracking-tight text-[#172033]">StockWise</span>
              <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-blue-50 text-blue-700 border border-blue-200">
                P1
              </span>
            </div>
            <p className="text-[11px] font-medium text-[#667085] tracking-tight">
              Distribution Intelligence
            </p>
          </div>
        </div>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        <div className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Core Workflows
        </div>
        {NAVIGATION_ITEMS.map((item) => {
          return (
            <NavLink
              key={item.id}
              to={item.path}
              onClick={onNavClick}
              className={({ isActive }) =>
                `flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-semibold shadow-2xs border border-blue-100'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div className="flex items-center gap-2.5 truncate">
                    <span className={isActive ? 'text-blue-600' : 'text-slate-400'}>
                      {iconMap[item.iconName] ?? <Boxes className="w-4 h-4 shrink-0" />}
                    </span>
                    <span className="truncate">{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-600 font-normal">
                      {item.badge}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </div>

      {/* Footer / PRD Guarantees */}
      <div className="p-4 border-t border-[#F1F5F9] bg-[#F8FAFC]/70 text-[11px] space-y-2">
        <div className="flex items-start gap-2 text-slate-600">
          <ShieldAlert className="w-3.5 h-3.5 text-blue-600 mt-0.5 shrink-0" />
          <div className="leading-snug">
            <span className="font-semibold text-slate-800">Dispatch Boundary:</span> Recommendations require human approval. No direct vehicle dispatch.
          </div>
        </div>
        <div className="text-[10px] text-slate-600 italic">
          "The right stock. At the right place. Before it is too late."
        </div>
      </div>
    </aside>
  );
};
