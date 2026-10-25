import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert, ArrowLeft, ArrowRight, UserCheck } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { usePortal } from '../../context/PortalContext';
import { isDemoAllowed, type UserRole } from '../../services/auth';
import { DEFAULT_PORTAL_BY_ROLE } from './TopBar';

export interface RoleGuardProps {
  allowedRoles: UserRole[];
  portalTitle: string;
  children: React.ReactNode;
}

export const RoleGuard: React.FC<RoleGuardProps> = ({
  allowedRoles,
  portalTitle,
  children,
}) => {
  const { role, user, switchRole } = useAuth();
  const { setActivePortal } = usePortal();
  const navigate = useNavigate();

  const isAuthorized = allowedRoles.includes(role);

  if (isAuthorized) {
    return <>{children}</>;
  }

  const handleDemoSwitch = (targetRole: UserRole) => {
    switchRole(targetRole);
    if (DEFAULT_PORTAL_BY_ROLE[targetRole]) {
      setActivePortal(DEFAULT_PORTAL_BY_ROLE[targetRole]);
    }
  };

  return (
    <div className="min-h-[500px] flex items-center justify-center p-4 sm:p-8">
      <div className="max-w-xl w-full bg-white rounded-2xl border border-rose-200/80 shadow-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Top Warning Strip */}
        <div className="bg-rose-50 border-b border-rose-100 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-rose-800">
            <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0" />
            <span className="text-xs font-bold uppercase tracking-wider">
              HTTP 403 &mdash; Insufficient Privileges
            </span>
          </div>
          <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-sm bg-rose-200/60 text-rose-800 font-mono">
            Role: {role}
          </span>
        </div>

        {/* Content Body */}
        <div className="p-6 sm:p-8 space-y-5">
          <div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              Access to {portalTitle} Restricted
            </h2>
            <div className="mt-2 p-3 rounded-lg bg-rose-50/70 border border-rose-200/60 font-mono text-xs text-rose-700 leading-relaxed">
              Forbidden: Insufficient privileges. Required role: {allowedRoles.join(', ')} (current: &apos;{role}&apos;)
            </div>
          </div>

          <div className="text-xs text-slate-600 space-y-2 leading-relaxed">
            <p>
              StockWise enforces strict multi-tenant and role-based access control (RBAC). The{' '}
              <strong className="text-slate-800">{portalTitle}</strong> is restricted to accounts
              provisioned with <strong className="text-slate-800">{allowedRoles.join(' or ')}</strong> privileges
              and verified organization membership.
            </p>
            <p className="text-slate-500 text-[11px]">
              Current verified session: <span className="font-mono text-slate-700">{user.email || user.id}</span>{' '}
              (Organization: <span className="font-mono text-slate-700">{user.orgId || 'None'}</span>).
            </p>
          </div>

          {/* Demo Mode Persona Switcher */}
          {isDemoAllowed() && user.isDemo && (
            <div className="p-4 rounded-xl bg-amber-50/80 border border-amber-200 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-900">
                  <UserCheck className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>Demo Mode Quick Role Switch</span>
                </div>
                <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-amber-200/70 text-amber-800">
                  Dev Authenticated
                </span>
              </div>
              <p className="text-[11px] text-amber-800 leading-snug">
                You are currently in local demonstration mode. Switch to an authorized persona below to inspect{' '}
                {portalTitle} workflows with verified organizational context:
              </p>
              <div className="flex flex-wrap gap-2 pt-1">
                {allowedRoles.map((r) => (
                  <button
                    key={r}
                    onClick={() => handleDemoSwitch(r)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-amber-600 hover:bg-amber-700 text-white shadow-xs transition-colors cursor-pointer"
                  >
                    <span>Switch to {r.charAt(0).toUpperCase() + r.slice(1)} Persona</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Navigation Actions */}
          <div className="pt-2 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100">
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Return to Overview</span>
            </button>

            {role === 'planner' && (
              <button
                onClick={() => navigate('/optimize')}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 transition-colors cursor-pointer"
              >
                <span>Open Planner Workspaces</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
