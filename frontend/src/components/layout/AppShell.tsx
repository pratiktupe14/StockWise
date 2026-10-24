import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { MobileNav } from './MobileNav';
import { useHealth } from '../../hooks/useHealth';

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
            <Outlet context={{ health }} />
          </div>
        </main>
      </div>
    </div>
  );
};
