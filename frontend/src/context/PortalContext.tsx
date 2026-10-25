import React, { createContext, useContext, useState } from 'react';

export type PortalMode = 'company_admin' | 'distribution_intelligence' | 'warehouse_logistics' | 'distributor_portal' | 'retailer_portal' | 'all';

export interface PortalContextType {
  activePortal: PortalMode;
  setActivePortal: (portal: PortalMode) => void;
  portalName: string;
  portalBadge: string;
}

const PortalContext = createContext<PortalContextType | undefined>(undefined);

const PORTAL_META: Record<PortalMode, { name: string; badge: string }> = {
  all: {
    name: 'StockWise FMCG Platform',
    badge: 'Unified',
  },
  company_admin: {
    name: 'Company Admin Portal',
    badge: 'Admin',
  },
  distribution_intelligence: {
    name: 'Distribution Intelligence Portal',
    badge: 'Intelligence',
  },
  warehouse_logistics: {
    name: 'Warehouse & Logistics Portal',
    badge: 'Logistics',
  },
  distributor_portal: {
    name: 'Distributor Portal',
    badge: 'Distributor',
  },
  retailer_portal: {
    name: 'Retail Shop Portal',
    badge: 'Retailer',
  },
};

const STORAGE_KEY = 'stockwise_active_portal';

export const PortalProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [activePortal, setActivePortalState] = useState<PortalMode>(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as PortalMode;
    return saved && PORTAL_META[saved] ? saved : 'all';
  });

  const setActivePortal = (portal: PortalMode) => {
    setActivePortalState(portal);
    localStorage.setItem(STORAGE_KEY, portal);
  };

  const meta = PORTAL_META[activePortal] || PORTAL_META.all;

  return (
    <PortalContext.Provider
      value={{
        activePortal,
        setActivePortal,
        portalName: meta.name,
        portalBadge: meta.badge,
      }}
    >
      {children}
    </PortalContext.Provider>
  );
};

export function usePortal(): PortalContextType {
  const context = useContext(PortalContext);
  if (!context) {
    throw new Error('usePortal must be used within a PortalProvider');
  }
  return context;
}
