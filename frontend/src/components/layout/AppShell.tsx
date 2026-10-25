import React, { useState, Suspense } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { MobileNav } from './MobileNav';
import { useHealth } from '../../hooks/useHealth';

export const RouteLoadingFallback: React.FC = () => (
  <div className="flex flex-col items-center justify-center min-h-[400px] w-full p-8 text-center" role="status" aria-label="Loading page">
    <div className="w-10 h-10 border-3 border-blue-600 border-t-transparent rounded-full animate-spin mb-4" />
    <h3 className="text-sm font-semibold text-slate-700">Loading Workspace...</h3>
    <p className="text-xs text-slate-400 mt-1 max-w-sm">
      Preparing authenticated portal views and optimized inventory data.
    </p>
  </div>
);

export const AppShell: React.FC = () => {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const health = useHealth(30000);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F7F8FA] text-[#172033]">
      {/* Desktop Persistent Sidebar */}
      <div className="hidden lg:flex lg:shrink-0">
        <Sidebar />
      </div>

      {/* Mobile Navigation Drawer */}
      <MobileNav isOpen={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

      {/* Main App Container */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navigation Bar with live health state */}
        <TopBar
          onToggleMobileNav={() => setMobileNavOpen(true)}
          healthData={health.data}
          healthLoading={health.loading}
          healthError={health.error}
          healthLastChecked={health.lastChecked}
          onRefreshHealth={health.refetch}
        />

        {/* Scrollable Content Region */}
        <main className="flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
          <div className="max-w-7xl mx-auto w-full">
            <Suspense fallback={<RouteLoadingFallback />}>
              <Outlet context={{ health }} />
            </Suspense>
          </div>
        </main>
      </div>
    </div>
  );
};
