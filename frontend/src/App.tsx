import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { PortalProvider } from './context/PortalContext';
import { AppShell } from './components/layout/AppShell';
import { RoleGuard } from './components/layout/RoleGuard';
import { OverviewPage } from './pages/OverviewPage';
import { NotFoundPage } from './pages/NotFoundPage';

// Route-level code splitting with React.lazy
const NetworkManagementPage = React.lazy(() =>
  import('./pages/NetworkManagementPage').then((m) => ({ default: m.NetworkManagementPage }))
);
const ImportCentrePage = React.lazy(() =>
  import('./pages/ImportCentrePage').then((m) => ({ default: m.ImportCentrePage }))
);
const InventoryPage = React.lazy(() =>
  import('./pages/InventoryPage').then((m) => ({ default: m.InventoryPage }))
);
const DistributorPortalPage = React.lazy(() => import('./pages/DistributorPortalPage'));
const RetailerPortalPage = React.lazy(() => import('./pages/RetailerPortalPage'));
const ShipmentsPage = React.lazy(() =>
  import('./pages/ShipmentsPage').then((m) => ({ default: m.ShipmentsPage }))
);
const RiskDemandPage = React.lazy(() =>
  import('./pages/RiskDemandPage').then((m) => ({ default: m.RiskDemandPage }))
);
const OptimizePlanPage = React.lazy(() =>
  import('./pages/OptimizePlanPage').then((m) => ({ default: m.OptimizePlanPage }))
);
const PlanComparisonPage = React.lazy(() =>
  import('./pages/PlanComparisonPage').then((m) => ({ default: m.PlanComparisonPage }))
);
const UtsavSensePage = React.lazy(() =>
  import('./pages/UtsavSensePage').then((m) => ({ default: m.UtsavSensePage }))
);
const ApprovalExportPage = React.lazy(() =>
  import('./pages/ApprovalExportPage').then((m) => ({ default: m.ApprovalExportPage }))
);
const WarehousesPage = React.lazy(() =>
  import('./pages/WarehousesPage').then((m) => ({ default: m.WarehousesPage }))
);
const PlanningResultsPage = React.lazy(() =>
  import('./pages/PlanningResultsPage').then((m) => ({ default: m.PlanningResultsPage }))
);
const DistributionIntelligencePage = React.lazy(() =>
  import('./pages/DistributionIntelligencePage').then((m) => ({ default: m.DistributionIntelligencePage }))
);
const SystemHealthPage = React.lazy(() =>
  import('./pages/SystemHealthPage').then((m) => ({ default: m.SystemHealthPage }))
);


export const App: React.FC = () => {
  return (
    <AuthProvider>
      <PortalProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppShell />}>
              <Route index element={<OverviewPage />} />
              <Route
                path="network"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner']} portalTitle="Network & Routes">
                    <NetworkManagementPage />
                  </RoleGuard>
                }
              />
              <Route
                path="warehouses"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics', 'viewer']} portalTitle="Warehouses">
                    <WarehousesPage />
                  </RoleGuard>
                }
              />
              <Route
                path="imports"
                element={
                  <RoleGuard allowedRoles={['admin']} portalTitle="Import Centre">
                    <ImportCentrePage />
                  </RoleGuard>
                }
              />
              <Route
                path="inventory"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics', 'viewer']} portalTitle="Inventory Balances">
                    <InventoryPage />
                  </RoleGuard>
                }
              />
              <Route
                path="distributor"
                element={
                  <RoleGuard allowedRoles={['admin', 'distributor']} portalTitle="Distributor Portal">
                    <DistributorPortalPage />
                  </RoleGuard>
                }
              />
              <Route
                path="retailer"
                element={
                  <RoleGuard allowedRoles={['admin', 'retailer']} portalTitle="Retail Shop Portal">
                    <RetailerPortalPage />
                  </RoleGuard>
                }
              />
              <Route
                path="shipments"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics']} portalTitle="Shipments & Logistics">
                    <ShipmentsPage />
                  </RoleGuard>
                }
              />
              <Route
                path="risk-demand"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner']} portalTitle="Risk & Demand">
                    <RiskDemandPage />
                  </RoleGuard>
                }
              />
              <Route
                path="optimize"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner']} portalTitle="Optimize Plan">
                    <OptimizePlanPage />
                  </RoleGuard>
                }
              />
              <Route
                path="comparison"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner']} portalTitle="Plan Comparison">
                    <PlanComparisonPage />
                  </RoleGuard>
                }
              />
              <Route
                path="planning-results"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics', 'viewer']} portalTitle="End-to-End Planning Results">
                    <PlanningResultsPage />
                  </RoleGuard>
                }
              />
              <Route
                path="company/planning-results"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics', 'viewer']} portalTitle="End-to-End Planning Results">
                    <PlanningResultsPage />
                  </RoleGuard>
                }
              />
              <Route
                path="company/distribution-intelligence"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner']} portalTitle="Distribution Intelligence">
                    <DistributionIntelligencePage />
                  </RoleGuard>
                }
              />
              <Route
                path="distribution-intelligence"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner']} portalTitle="Distribution Intelligence">
                    <DistributionIntelligencePage />
                  </RoleGuard>
                }
              />

              <Route
                path="utsav-sense"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner']} portalTitle="UtsavSense Planning">
                    <UtsavSensePage />
                  </RoleGuard>
                }
              />
              <Route
                path="approval"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics']} portalTitle="Approval & Export">
                    <ApprovalExportPage />
                  </RoleGuard>
                }
              />
              <Route
                path="system-health"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics', 'viewer']} portalTitle="System Health & Validation">
                    <SystemHealthPage />
                  </RoleGuard>
                }
              />
              <Route
                path="health"
                element={
                  <RoleGuard allowedRoles={['admin', 'planner', 'logistics', 'viewer']} portalTitle="System Health & Validation">
                    <SystemHealthPage />
                  </RoleGuard>
                }
              />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </PortalProvider>
    </AuthProvider>
  );
};

export default App;
