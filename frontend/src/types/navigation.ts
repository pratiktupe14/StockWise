import type { UserRole } from '../services/auth';

export interface NavItem {
  id: string;
  label: string;
  path: string;
  iconName: string;
  description: string;
  badge?: string;
  portals?: ('company_admin' | 'distribution_intelligence' | 'warehouse_logistics' | 'distributor_portal' | 'retailer_portal')[];
  roles?: UserRole[];
}

export const NAVIGATION_ITEMS: NavItem[] = [
  {
    id: 'overview',
    label: 'Overview',
    path: '/',
    iconName: 'LayoutDashboard',
    description: 'Distribution executive summary and network health',
    portals: ['company_admin', 'distribution_intelligence', 'warehouse_logistics', 'distributor_portal', 'retailer_portal'],
    roles: ['admin', 'planner', 'logistics', 'distributor', 'retailer', 'viewer'],
  },
  {
    id: 'distributor-portal',
    label: 'Distributor Portal',
    path: '/distributor',
    iconName: 'Store',
    description: 'Distributor-owned inventory, replenishment requests, and incoming shipments',
    badge: 'Phase 8',
    portals: ['distributor_portal', 'company_admin'],
    roles: ['admin', 'distributor'],
  },
  {
    id: 'retailer-portal',
    label: 'Retail Shop Portal',
    path: '/retailer',
    iconName: 'ShoppingBag',
    description: 'Store inventory shelf availability, replenishment requests & deliveries',
    badge: 'Phase 9',
    portals: ['retailer_portal', 'company_admin'],
    roles: ['admin', 'retailer'],
  },
  {
    id: 'network-design',
    label: 'Network & Routes',
    path: '/network',
    iconName: 'Network',
    description: 'Organizations, facilities, permitted routes, and corridor eligibility',
    badge: 'Phase 2',
    portals: ['company_admin', 'distribution_intelligence'],
    roles: ['admin', 'planner'],
  },
  {
    id: 'import-centre',
    label: 'Import Centre',
    path: '/imports',
    iconName: 'UploadCloud',
    description: 'Data ingestion and validation pipeline',
    portals: ['company_admin'],
    roles: ['admin'],
  },
  {
    id: 'warehouses',
    label: 'Warehouses',
    path: '/warehouses',
    iconName: 'Warehouse',
    description: 'Company warehouse capacities, dispatchable stock, and facility utilization',
    portals: ['company_admin', 'warehouse_logistics'],
    roles: ['admin', 'planner', 'logistics', 'viewer'],
  },
  {
    id: 'inventory',
    label: 'Inventory Balances',
    path: '/inventory',
    iconName: 'Boxes',
    description: 'Ownership, C&F storage, dispatchable stock and multi-location balances',
    portals: ['company_admin', 'distribution_intelligence', 'warehouse_logistics'],
    roles: ['admin', 'planner', 'logistics', 'viewer'],
  },
  {
    id: 'shipments',
    label: 'Shipments & Logistics',
    path: '/shipments',
    iconName: 'Truck',
    description: 'Shipment proposals, governance approvals, and stock movement audit log',
    badge: 'Phase 2',
    portals: ['warehouse_logistics', 'company_admin'],
    roles: ['admin', 'planner', 'logistics'],
  },
  {
    id: 'risk-demand',
    label: 'Risk & Demand',
    path: '/risk-demand',
    iconName: 'TrendingUp',
    description: 'Demand forecasts, cover days, and shortage warnings',
    portals: ['distribution_intelligence'],
    roles: ['admin', 'planner'],
  },
  {
    id: 'optimize-plan',
    label: 'Optimize Plan',
    path: '/optimize',
    iconName: 'Sparkles',
    description: 'Constrained service-first allocation solver',
    portals: ['distribution_intelligence'],
    roles: ['admin', 'planner'],
  },
  {
    id: 'plan-comparison',
    label: 'Plan Comparison',
    path: '/comparison',
    iconName: 'GitCompare',
    description: 'Benchmark optimizer vs nearest-source baseline',
    portals: ['distribution_intelligence'],
    roles: ['admin', 'planner'],
  },
  {
    id: 'utsav-sense',
    label: 'UtsavSense Planning',
    path: '/utsav-sense',
    iconName: 'Flame',
    description: 'Festival-aware demand surge and regional inventory allocation',
    badge: 'UtsavSense',
    portals: ['distribution_intelligence'],
    roles: ['admin', 'planner'],
  },
  {
    id: 'approval-export',
    label: 'Approval & Export',
    path: '/approval',
    iconName: 'FileCheck2',
    description: 'Governance review and dispatch proposal export',
    portals: ['company_admin', 'warehouse_logistics', 'distribution_intelligence'],
    roles: ['admin', 'planner', 'logistics'],
  },
];
