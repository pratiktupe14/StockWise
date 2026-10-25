import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, User, ChevronRight, Layers, ChevronDown, Check, ShieldCheck, LogOut } from 'lucide-react';
import { StatusIndicator } from '../ui/StatusIndicator';
import type { HealthResponse } from '../../types/api';
import { NAVIGATION_ITEMS } from '../../types/navigation';
import { usePortal, type PortalMode } from '../../context/PortalContext';
import { useAuth } from '../../context/AuthContext';
import { isDemoAllowed, type UserRole } from '../../services/auth';

export interface TopBarProps {
  onToggleMobileNav: () => void;
  healthData: HealthResponse | null;
  healthLoading: boolean;
  healthError: string | null;
  healthLastChecked: Date | null;
  onRefreshHealth: () => Promise<void>;
}

const PORTALS: { id: PortalMode; label: string; desc: string; color: string; badgeBg: string; badgeText: string; roles: UserRole[] }[] = [
  {
    id: 'company_admin',
    label: 'Company Admin Portal',
    desc: 'Master data, facilities, C&F/3PL partners, permitted routes & imports',
    color: 'border-indigo-500 text-indigo-700',
    badgeBg: 'bg-indigo-50 border-indigo-200',
    badgeText: 'text-indigo-700',
    roles: ['admin'],
  },
  {
    id: 'distribution_intelligence',
    label: 'Distribution Intelligence Portal',
    desc: 'Corridor eligibility, multi-echelon inventory, risk and optimization',
    color: 'border-blue-500 text-blue-700',
    badgeBg: 'bg-blue-50 border-blue-200',
    badgeText: 'text-blue-700',
    roles: ['admin', 'planner'],
  },
  {
    id: 'warehouse_logistics',
    label: 'Warehouse & Logistics Portal',
    desc: 'Location balances, proposed dispatches, approvals & stock movements',
    color: 'border-emerald-500 text-emerald-700',
    badgeBg: 'bg-emerald-50 border-emerald-200',
    badgeText: 'text-emerald-700',
    roles: ['admin', 'planner', 'logistics'],
  },
  {
    id: 'distributor_portal',
    label: 'Distributor Portal',
    desc: 'Distributor-owned inventory, stock requests & incoming shipment tracking',
    color: 'border-amber-500 text-amber-700',
    badgeBg: 'bg-amber-50 border-amber-200',
    badgeText: 'text-amber-700',
    roles: ['admin', 'distributor'],
  },
  {
    id: 'retailer_portal',
    label: 'Retail Shop Portal',
    desc: 'Retail store inventory, shelf availability & replenishment requests',
    color: 'border-pink-500 text-pink-700',
    badgeBg: 'bg-pink-50 border-pink-200',
    badgeText: 'text-pink-700',
    roles: ['admin', 'retailer'],
  },
  {
    id: 'all',
    label: 'Unified FMCG Platform',
    desc: 'Cross-portal integrated FMCG distribution view',
    color: 'border-slate-500 text-slate-700',
    badgeBg: 'bg-slate-100 border-slate-200',
    badgeText: 'text-slate-700',
    roles: ['admin', 'planner', 'logistics', 'distributor', 'retailer', 'viewer'],
  },
];

export const DEFAULT_PORTAL_BY_ROLE: Record<UserRole, PortalMode> = {
  admin: 'company_admin',
  planner: 'distribution_intelligence',
  logistics: 'warehouse_logistics',
  distributor: 'distributor_portal',
  retailer: 'retailer_portal',
  viewer: 'all',
};

const ROLES: { id: UserRole; title: string; badgeBg: string; badgeText: string }[] = [
  { id: 'admin', title: 'Company Admin', badgeBg: 'bg-purple-50 border-purple-200', badgeText: 'text-purple-700' },
  { id: 'planner', title: 'Demand & Supply Planner', badgeBg: 'bg-blue-50 border-blue-200', badgeText: 'text-blue-700' },
  { id: 'logistics', title: 'Logistics & Warehouse Lead', badgeBg: 'bg-emerald-50 border-emerald-200', badgeText: 'text-emerald-700' },
  { id: 'distributor', title: 'Authorized Distributor', badgeBg: 'bg-amber-50 border-amber-200', badgeText: 'text-amber-700' },
  { id: 'retailer', title: 'Authorized Retailer', badgeBg: 'bg-pink-50 border-pink-200', badgeText: 'text-pink-700' },
  { id: 'viewer', title: 'Auditor & Read-Only Viewer', badgeBg: 'bg-slate-100 border-slate-200', badgeText: 'text-slate-700' },
];

export const TopBar: React.FC<TopBarProps> = ({
  onToggleMobileNav,
  healthData,
  healthLoading,
  healthError,
  healthLastChecked,
  onRefreshHealth,
}) => {
  const location = useLocation();
  const { activePortal, setActivePortal, portalBadge } = usePortal();
  const { user, role, switchRole, logout, isSupabaseConfigured } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Ensure activePortal is always valid for the current role
  useEffect(() => {
    const isAllowed = PORTALS.find((p) => p.id === activePortal)?.roles.includes(role);
    if (!isAllowed) {
      setActivePortal(DEFAULT_PORTAL_BY_ROLE[role] || 'all');
    }
  }, [role, activePortal, setActivePortal]);

  // Find active nav item
  const currentNav = NAVIGATION_ITEMS.find((item) => item.path === location.pathname) || {
    label: 'Overview',
    description: 'Distribution executive summary',
  };

  const availablePortals = PORTALS.filter((p) => p.roles.includes(role));
  const currentPortalMeta = PORTALS.find((p) => p.id === activePortal) || availablePortals[0] || PORTALS[5];
  const currentRoleMeta = ROLES.find((r) => r.id === role) || ROLES[1];

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

      {/* Center: Interactive Portal Switcher */}
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all cursor-pointer shadow-2xs hover:bg-slate-50 ${currentPortalMeta.badgeBg} ${currentPortalMeta.badgeText}`}
          title="Switch Active FMCG Portal"
        >
          <Layers className="w-3.5 h-3.5 shrink-0" />
          <span className="truncate max-w-[150px] sm:max-w-xs">{currentPortalMeta.label}</span>
          <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-sm bg-white/80 border border-slate-200">
            {portalBadge}
          </span>
          <ChevronDown className="w-3 h-3 text-slate-400 shrink-0" />
        </button>

        {dropdownOpen && (
          <div className="absolute left-1/2 -translate-x-1/2 mt-1 w-80 sm:w-96 bg-white rounded-xl shadow-xl border border-slate-200 py-1.5 z-50">
            <div className="px-3 py-2 border-b border-slate-100">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                FMCG Distribution Portals
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                Switch role-based portal context to filter workflows and permissions.
              </p>
            </div>
            <div className="py-1">
              {availablePortals.map((portal) => (
                <button
                  key={portal.id}
                  onClick={() => {
                    setActivePortal(portal.id);
                    setDropdownOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 flex items-start justify-between hover:bg-slate-50 transition-colors cursor-pointer ${
                    activePortal === portal.id ? 'bg-slate-50/80' : ''
                  }`}
                >
                  <div className="pr-2">
                    <div className="flex items-center gap-2">
                      <span className={`font-semibold text-xs text-slate-800`}>{portal.label}</span>
                      <span
                        className={`text-[9px] font-semibold uppercase px-1.5 py-0.2 rounded-sm border ${portal.badgeBg} ${portal.badgeText}`}
                      >
                        {portal.id === 'all' ? 'All' : portal.id.split('_')[0]}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-0.5 leading-tight">{portal.desc}</p>
                  </div>
                  {activePortal === portal.id && (
                    <Check className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Right: Real Backend Health Indicator & Authenticated User Profile */}
      <div className="flex items-center gap-3">
        {/* Backend Connectivity Status Indicator */}
        <StatusIndicator
          data={healthData}
          loading={healthLoading}
          error={healthError}
          lastChecked={healthLastChecked}
          onRefresh={onRefreshHealth}
        />

        {/* Authenticated User Menu */}
        <div className="relative" ref={userMenuRef}>
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2 pl-3 border-l border-slate-200 select-none text-slate-600 hover:text-slate-900 transition-colors cursor-pointer"
            title="Account & Role Authorization"
          >
            <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200/80 flex items-center justify-center text-slate-600 shadow-2xs">
              <User className="w-4 h-4" />
            </div>
            <div className="hidden md:block text-left text-xs leading-tight">
              <div className="flex items-center gap-1.5 font-medium text-[#172033]">
                <span>{user.email.split('@')[0]}</span>
                <span className={`text-[9px] font-bold uppercase px-1.5 py-0.2 rounded-sm border ${currentRoleMeta.badgeBg} ${currentRoleMeta.badgeText}`}>
                  {user.role}
                </span>
              </div>
              <div className="text-[10px] text-[#667085] flex items-center gap-1">
                <span>{user.orgId || 'ORG-FMCG-CORP'}</span>
                {isSupabaseConfigured && !user.isDemo && (
                  <ShieldCheck className="w-3 h-3 text-emerald-500" />
                )}
              </div>
            </div>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-white rounded-xl shadow-xl border border-slate-200 py-2 z-50 animate-in fade-in slide-in-from-top-1">
              <div className="px-3 py-2 border-b border-slate-100">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-slate-800">{user.email}</p>
                  <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded-sm border ${currentRoleMeta.badgeBg} ${currentRoleMeta.badgeText}`}>
                    {user.role}
                  </span>
                </div>
                <p className="text-[10px] text-slate-500 font-mono mt-0.5">ID: {user.id}</p>
                <div className="flex items-center gap-1 mt-1 text-[10px] text-slate-500">
                  <ShieldCheck className="w-3 h-3 text-emerald-600" />
                  <span>{user.isDemo ? 'Dev Authenticated Token' : 'Supabase Verified Session'}</span>
                </div>
              </div>

              {isDemoAllowed() && user.isDemo && (
                <div className="px-3 py-2">
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                      Demo Persona Selector
                    </p>
                    <span className="text-[9px] font-bold text-amber-700 bg-amber-50 border border-amber-200 px-1 py-0.2 rounded-xs">
                      DEV MODE
                    </span>
                  </div>
                  <div className="space-y-1">
                    {ROLES.map((r) => (
                      <button
                        key={r.id}
                        onClick={() => {
                          switchRole(r.id);
                          setActivePortal(DEFAULT_PORTAL_BY_ROLE[r.id]);
                          setUserMenuOpen(false);
                        }}
                        className={`w-full text-left px-2 py-1.5 rounded-lg text-xs flex items-center justify-between transition-colors cursor-pointer ${
                          role === r.id ? 'bg-slate-100 font-semibold text-slate-900' : 'text-slate-600 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className={`text-[9px] uppercase font-bold px-1 py-0.5 rounded-xs border ${r.badgeBg} ${r.badgeText}`}>
                            {r.id}
                          </span>
                          <span>{r.title}</span>
                        </div>
                        {role === r.id && <Check className="w-3.5 h-3.5 text-blue-600" />}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="border-t border-slate-100 pt-1 px-1">
                <button
                  onClick={() => {
                    logout();
                    setUserMenuOpen(false);
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 rounded-lg flex items-center gap-2 cursor-pointer transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Reset / Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

