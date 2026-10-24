import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AppShell } from './components/layout/AppShell';
import { OverviewPage } from './pages/OverviewPage';
import { ImportCentrePage } from './pages/ImportCentrePage';
import { InventoryPage } from './pages/InventoryPage';
import { RiskDemandPage } from './pages/RiskDemandPage';
import { OptimizePlanPage } from './pages/OptimizePlanPage';
import { PlanComparisonPage } from './pages/PlanComparisonPage';
import { ApprovalExportPage } from './pages/ApprovalExportPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="imports" element={<ImportCentrePage />} />
          <Route path="inventory" element={<InventoryPage />} />
          <Route path="risk-demand" element={<RiskDemandPage />} />
          <Route path="optimize" element={<OptimizePlanPage />} />
          <Route path="comparison" element={<PlanComparisonPage />} />
          <Route path="approval" element={<ApprovalExportPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
