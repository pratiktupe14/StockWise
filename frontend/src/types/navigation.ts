export interface NavItem {
  id: string;
  label: string;
  path: string;
  iconName: string;
  description: string;
  badge?: string;
}

export const NAVIGATION_ITEMS: NavItem[] = [
  {
    id: 'overview',
    label: 'Overview',
    path: '/',
    iconName: 'LayoutDashboard',
    description: 'Distribution executive summary and network health',
  },
  {
    id: 'import-centre',
    label: 'Import Centre',
    path: '/imports',
    iconName: 'UploadCloud',
    description: 'Data ingestion and validation pipeline',
  },
  {
    id: 'inventory',
    label: 'Inventory',
    path: '/inventory',
    iconName: 'Boxes',
    description: 'Dispatchable stock and multi-location balances',
  },
  {
    id: 'risk-demand',
    label: 'Risk & Demand',
    path: '/risk-demand',
    iconName: 'TrendingUp',
    description: 'Demand forecasts, cover days, and shortage warnings',
  },
  {
    id: 'optimize-plan',
    label: 'Optimize Plan',
    path: '/optimize',
    iconName: 'Sparkles',
    description: 'Constrained service-first allocation solver',
  },
  {
    id: 'plan-comparison',
    label: 'Plan Comparison',
    path: '/comparison',
    iconName: 'GitCompare',
    description: 'Benchmark optimizer vs nearest-source baseline',
  },
  {
    id: 'approval-export',
    label: 'Approval & Export',
    path: '/approval',
    iconName: 'FileCheck2',
    description: 'Governance review and dispatch proposal export',
  },
];
