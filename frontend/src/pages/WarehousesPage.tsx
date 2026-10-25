import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Warehouse,
  Building2,
  Boxes,
  Search,
  Filter,
  RefreshCw,
  UploadCloud,
  X,
  AlertTriangle,
  Truck,
  Package,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import type { BadgeVariant } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { SummaryCard } from '../components/ui/SummaryCard';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../components/ui/Table';
import { EmptyState } from '../components/ui/EmptyState';
import { getNetworkLocations, getInventory, getShipments } from '../services/api';
import { useDatasetSync } from '../services/dataSync';
import type { LocationItem, InventoryItem, ShipmentItem } from '../types/api';

// Utility helper to format location types cleanly
function formatLocationType(type?: string | null): string {
  if (!type) return 'Warehouse';
  switch (type.toLowerCase()) {
    case 'company_warehouse':
      return 'Company Warehouse';
    case 'central_warehouse':
      return 'Central Warehouse';
    case 'regional_warehouse':
      return 'Regional DC';
    case 'manufacturing_plant':
      return 'Plant Warehouse';
    case 'cnf_facility':
      return 'C&F Facility';
    case '3pl_facility':
      return '3PL Facility';
    case 'distributor_warehouse':
      return 'Distributor Godown';
    case 'retail_destination':
      return 'Retail Store';
    default:
      return type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

function getLocationTypeBadgeVariant(type?: string | null): BadgeVariant {
  if (!type) return 'neutral';
  switch (type.toLowerCase()) {
    case 'company_warehouse':
    case 'central_warehouse':
      return 'primary';
    case 'regional_warehouse':
      return 'success';
    case 'manufacturing_plant':
      return 'warning';
    default:
      return 'neutral';
  }
}

export const WarehousesPage: React.FC = () => {
  const navigate = useNavigate();

  // Data states
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedRegion, setSelectedRegion] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedOwnership, setSelectedOwnership] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');

  // Detail Drawer state
  const [selectedWarehouse, setSelectedWarehouse] = useState<LocationItem | null>(null);
  const [detailTab, setDetailTab] = useState<'inventory' | 'facility' | 'shipments'>('inventory');

  // Fetch real data from backend
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [locsData, invData, shipData] = await Promise.all([
        getNetworkLocations().catch(() => []),
        getInventory().catch(() => []),
        getShipments().catch(() => []),
      ]);
      setLocations(locsData);
      setInventory(invData);
      setShipments(shipData);
    } catch (err: any) {
      setError(err?.message || 'Failed to load warehouse network records.');
    } finally {
      setLoading(false);
    }
  };

  const syncInfo = useDatasetSync(['locations', 'inventory'], fetchData);

  useEffect(() => {
    fetchData();
  }, []);

  // Compute inventory aggregation by location
  const inventoryByLocation = useMemo(() => {
    const map = new Map<
      string,
      {
        totalOnHand: number;
        totalReserved: number;
        totalBlocked: number;
        totalDispatchable: number;
        skuCount: number;
        items: InventoryItem[];
      }
    >();

    inventory.forEach((inv) => {
      const locId = inv.location_id;
      const current = map.get(locId) || {
        totalOnHand: 0,
        totalReserved: 0,
        totalBlocked: 0,
        totalDispatchable: 0,
        skuCount: 0,
        items: [],
      };

      current.totalOnHand += Number(inv.on_hand || 0);
      current.totalReserved += Number(inv.reserved || 0);
      current.totalBlocked += Number(inv.blocked || 0);
      current.totalDispatchable += Number(
        inv.dispatchable_stock ?? Math.max(0, inv.on_hand - (inv.reserved || 0) - (inv.blocked || 0))
      );
      current.skuCount += 1;
      current.items.push(inv);

      map.set(locId, current);
    });

    return map;
  }, [inventory]);

  // Derived warehouse metrics for summary cards
  const summaryMetrics = useMemo(() => {
    let companyCount = 0;
    let regionalCount = 0;
    let totalCapacity = 0;
    let totalStock = 0;
    let nearingCapacityCount = 0;
    let inactiveCount = 0;

    locations.forEach((loc) => {
      const t = (loc.location_type || '').toLowerCase();
      if (t === 'company_warehouse' || t === 'central_warehouse') companyCount++;
      if (t === 'regional_warehouse') regionalCount++;

      const cap = Number(loc.storage_capacity_units || 0);
      totalCapacity += cap;

      const locInv = inventoryByLocation.get(loc.location_id);
      const stock = locInv ? locInv.totalOnHand : 0;
      totalStock += stock;

      if (cap > 0 && stock / cap >= 0.85) {
        nearingCapacityCount++;
      }

      if (loc.is_active === false) {
        inactiveCount++;
      }
    });

    return {
      companyCount,
      regionalCount,
      totalCapacity,
      totalStock,
      nearingCapacityCount,
      inactiveCount,
    };
  }, [locations, inventoryByLocation]);

  // Unique regions for filter dropdown
  const uniqueRegions = useMemo(() => {
    const set = new Set<string>();
    locations.forEach((loc) => {
      if (loc.region) set.add(loc.region.trim());
    });
    return Array.from(set).sort();
  }, [locations]);

  // Filtered warehouses
  const filteredWarehouses = useMemo(() => {
    return locations.filter((loc) => {
      // 1. Search Query
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesId = loc.location_id.toLowerCase().includes(query);
        const matchesName = loc.name.toLowerCase().includes(query);
        const matchesCity = (loc.city || '').toLowerCase().includes(query);
        const matchesAddress = (loc.address || '').toLowerCase().includes(query);
        const matchesOwner = (loc.owner_org_name || '').toLowerCase().includes(query);
        if (!matchesId && !matchesName && !matchesCity && !matchesAddress && !matchesOwner) {
          return false;
        }
      }

      // 2. Region filter
      if (selectedRegion !== 'all') {
        if ((loc.region || '').toLowerCase() !== selectedRegion.toLowerCase()) {
          return false;
        }
      }

      // 3. Type filter
      if (selectedType !== 'all') {
        if ((loc.location_type || '').toLowerCase() !== selectedType.toLowerCase()) {
          return false;
        }
      }

      // 4. Ownership filter
      if (selectedOwnership !== 'all') {
        const isDistributor = (loc.location_type || '').toLowerCase() === 'distributor_warehouse';
        if (selectedOwnership === 'company' && isDistributor) return false;
        if (selectedOwnership === 'distributor' && !isDistributor) return false;
      }

      // 5. Status filter
      if (selectedStatus === 'active' && loc.is_active === false) return false;
      if (selectedStatus === 'inactive' && loc.is_active !== false) return false;
      if (selectedStatus === 'nearing_capacity') {
        const cap = Number(loc.storage_capacity_units || 0);
        const locInv = inventoryByLocation.get(loc.location_id);
        const stock = locInv ? locInv.totalOnHand : 0;
        if (cap <= 0 || stock / cap < 0.85) return false;
      }

      return true;
    });
  }, [locations, searchQuery, selectedRegion, selectedType, selectedOwnership, selectedStatus, inventoryByLocation]);

  // Inventory records for the selected warehouse in drawer
  const selectedWarehouseInventory = useMemo(() => {
    if (!selectedWarehouse) return [];
    return inventoryByLocation.get(selectedWarehouse.location_id)?.items || [];
  }, [selectedWarehouse, inventoryByLocation]);

  // Shipments for the selected warehouse
  const selectedWarehouseShipments = useMemo(() => {
    if (!selectedWarehouse) return [];
    const id = selectedWarehouse.location_id;
    return shipments.filter(
      (s) => s.source_location_id === id || s.destination_location_id === id
    );
  }, [selectedWarehouse, shipments]);

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-[#172033]">
              Warehouse Management
            </h1>
            <Badge variant="primary" size="sm">Company Network</Badge>
            {syncInfo.formattedSyncTime && (
              <Badge variant="neutral" size="sm">
                Synced {syncInfo.formattedSyncTime} ({syncInfo.dataset})
              </Badge>
            )}
          </div>
          <p className="text-sm text-[#667085] mt-1">
            Authorized company warehouses, storage capacities, real-time stock balances, and facility utilization.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchData}
            disabled={loading}
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/imports')}
          >
            <UploadCloud className="w-3.5 h-3.5 mr-1.5" />
            Import Data
          </Button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <Alert variant="error" title="Failed to load warehouse data">
          <div className="flex items-center justify-between w-full">
            <span>{error}</span>
            <button
              onClick={fetchData}
              className="underline font-semibold ml-2 hover:text-red-800"
            >
              Retry
            </button>
          </div>
        </Alert>
      )}

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <SummaryCard
          title="Company Warehouses"
          icon={Building2}
          value={loading ? '...' : summaryMetrics.companyCount}
          subtitle="Central & Company DCs"
          badgeText="Active Network"
          badgeVariant="primary"
        />
        <SummaryCard
          title="Regional RDCs"
          icon={Warehouse}
          value={loading ? '...' : summaryMetrics.regionalCount}
          subtitle="Regional distribution"
          badgeText="Strategic Nodes"
          badgeVariant="success"
        />
        <SummaryCard
          title="Total Storage Capacity"
          icon={Boxes}
          value={loading ? '...' : summaryMetrics.totalCapacity ? summaryMetrics.totalCapacity.toLocaleString() : 'Unset'}
          subtitle="Known capacity units"
          badgeText="Storage Cap"
          badgeVariant="neutral"
        />
        <SummaryCard
          title="Current Stock Units"
          icon={Package}
          value={loading ? '...' : summaryMetrics.totalStock ? summaryMetrics.totalStock.toLocaleString() : '0'}
          subtitle="Persisted on-hand units"
          badgeText="Real Balances"
          badgeVariant="neutral"
        />
        <SummaryCard
          title="Nearing Capacity"
          icon={AlertTriangle}
          value={loading ? '...' : summaryMetrics.nearingCapacityCount}
          subtitle="≥ 85% space utilized"
          badgeText={summaryMetrics.nearingCapacityCount > 0 ? 'High Fill' : 'Optimal'}
          badgeVariant={summaryMetrics.nearingCapacityCount > 0 ? 'warning' : 'success'}
        />
        <SummaryCard
          title="Inactive Facilities"
          icon={X}
          value={loading ? '...' : summaryMetrics.inactiveCount}
          subtitle="Offline or decommissioned"
          badgeText={summaryMetrics.inactiveCount > 0 ? 'Action Needed' : 'All Online'}
          badgeVariant={summaryMetrics.inactiveCount > 0 ? 'critical' : 'success'}
        />
      </div>

      {/* Filters & Search Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-3">
            {/* Search query */}
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Search by warehouse ID, name, city, address, or owner org..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-600 bg-white"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            {/* Region dropdown */}
            <select
              value={selectedRegion}
              onChange={(e) => setSelectedRegion(e.target.value)}
              className="px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:border-blue-600"
            >
              <option value="all">All Regions ({uniqueRegions.length})</option>
              {uniqueRegions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>

            {/* Facility Type dropdown */}
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:border-blue-600"
            >
              <option value="all">All Facility Types</option>
              <option value="company_warehouse">Company Warehouse</option>
              <option value="regional_warehouse">Regional Warehouse (RDC)</option>
              <option value="central_warehouse">Central Warehouse</option>
              <option value="manufacturing_plant">Plant Warehouse</option>
              <option value="distributor_warehouse">Distributor Godown</option>
              <option value="retail_destination">Retail Destination</option>
            </select>

            {/* Ownership dropdown */}
            <select
              value={selectedOwnership}
              onChange={(e) => setSelectedOwnership(e.target.value)}
              className="px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:border-blue-600"
            >
              <option value="all">All Ownership</option>
              <option value="company">Company Owned</option>
              <option value="distributor">Distributor Owned</option>
            </select>

            {/* Status dropdown */}
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="px-3 py-2 text-xs border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:border-blue-600"
            >
              <option value="all">All Status</option>
              <option value="active">Active Only</option>
              <option value="inactive">Inactive Only</option>
              <option value="nearing_capacity">Nearing Capacity (≥85%)</option>
            </select>

            {/* Clear Filters */}
            {(searchQuery || selectedRegion !== 'all' || selectedType !== 'all' || selectedOwnership !== 'all' || selectedStatus !== 'all') && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearchQuery('');
                  setSelectedRegion('all');
                  setSelectedType('all');
                  setSelectedOwnership('all');
                  setSelectedStatus('all');
                }}
                className="text-slate-500 hover:text-slate-700 text-xs px-2 shrink-0"
              >
                Reset
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Main Warehouses Table */}
      <Card>
        <CardHeader className="border-b border-slate-100 pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold text-slate-900">
                Warehouses & Storage Hubs
              </CardTitle>
              <CardDescription className="text-xs">
                Showing {filteredWarehouses.length} of {locations.length} total network facilities.
              </CardDescription>
            </div>
            <div className="text-xs text-slate-500 font-medium">
              Real-time snapshot stock synced
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {loading ? (
            <div className="p-12 text-center text-slate-400 text-sm flex flex-col items-center justify-center gap-3">
              <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
              <span>Loading warehouse facilities and inventory...</span>
            </div>
          ) : filteredWarehouses.length === 0 ? (
            locations.length === 0 ? (
              <EmptyState
                icon={Warehouse}
                title="No warehouses found"
                description="No warehouse locations have been configured or imported into StockWise."
                actionLabel="Import Locations Data"
                onAction={() => navigate('/imports')}
              />
            ) : (
              <EmptyState
                icon={Filter}
                title="No matching warehouses"
                description="No facilities match your selected search query and filter criteria."
                actionLabel="Clear Filters"
                onAction={() => {
                  setSearchQuery('');
                  setSelectedRegion('all');
                  setSelectedType('all');
                  setSelectedOwnership('all');
                  setSelectedStatus('all');
                }}
              />
            )
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/75 hover:bg-slate-50/75 text-[11px] uppercase tracking-wider text-slate-500 font-semibold border-b border-slate-200">
                    <TableHead className="py-3 px-4">Warehouse ID & Name</TableHead>
                    <TableHead className="py-3 px-3">Type</TableHead>
                    <TableHead className="py-3 px-3">Region & City</TableHead>
                    <TableHead className="py-3 px-3">Ownership / Operator</TableHead>
                    <TableHead className="py-3 px-3 text-right">Storage Capacity</TableHead>
                    <TableHead className="py-3 px-3 text-right">Current Stock</TableHead>
                    <TableHead className="py-3 px-3">Utilization</TableHead>
                    <TableHead className="py-3 px-3 text-right">Daily Dispatch</TableHead>
                    <TableHead className="py-3 px-3 text-center">Status</TableHead>
                    <TableHead className="py-3 px-4 text-center">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="divide-y divide-slate-100 text-xs">
                  {filteredWarehouses.map((wh) => {
                    const locInv = inventoryByLocation.get(wh.location_id);
                    const stock = locInv ? locInv.totalOnHand : 0;
                    const dispatchable = locInv ? locInv.totalDispatchable : 0;
                    const capacity = wh.storage_capacity_units ? Number(wh.storage_capacity_units) : null;
                    const availableCap = capacity !== null ? Math.max(0, capacity - stock) : null;
                    const utilizationPct = capacity && capacity > 0 ? Math.round((stock / capacity) * 100) : null;

                    return (
                      <TableRow
                        key={wh.location_id}
                        className="hover:bg-slate-50/60 transition-colors cursor-pointer group"
                        onClick={() => setSelectedWarehouse(wh)}
                      >
                        {/* ID and Name */}
                        <TableCell className="py-3.5 px-4 font-medium text-slate-900">
                          <div className="flex items-start gap-2.5">
                            <div className="w-8 h-8 rounded-lg bg-blue-50/70 border border-blue-100 flex items-center justify-center text-blue-600 shrink-0 mt-0.5">
                              <Warehouse className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                                {wh.name}
                              </div>
                              <code className="text-[11px] text-slate-500 font-mono font-normal">
                                {wh.location_id}
                              </code>
                            </div>
                          </div>
                        </TableCell>

                        {/* Type */}
                        <TableCell className="py-3.5 px-3">
                          <Badge variant={getLocationTypeBadgeVariant(wh.location_type)} size="sm">
                            {formatLocationType(wh.location_type)}
                          </Badge>
                        </TableCell>

                        {/* Region & City */}
                        <TableCell className="py-3.5 px-3 text-slate-600">
                          <div className="font-medium text-slate-800">{wh.region}</div>
                          <div className="text-[11px] text-slate-500">{wh.city || wh.address || '—'}</div>
                        </TableCell>

                        {/* Ownership / Operator */}
                        <TableCell className="py-3.5 px-3 text-slate-600">
                          <div className="text-slate-800 truncate max-w-[140px]" title={wh.owner_org_name || wh.owner_org_id || 'Company'}>
                            {wh.owner_org_name || wh.owner_org_id || 'Company Core'}
                          </div>
                          {wh.operator_org_name && (
                            <div className="text-[11px] text-slate-400 truncate max-w-[140px]" title={`Operator: ${wh.operator_org_name}`}>
                              Op: {wh.operator_org_name}
                            </div>
                          )}
                        </TableCell>

                        {/* Storage Capacity */}
                        <TableCell className="py-3.5 px-3 text-right">
                          {capacity !== null ? (
                            <div>
                              <span className="font-semibold text-slate-800">
                                {capacity.toLocaleString()}
                              </span>
                              <span className="text-[10px] text-slate-400 ml-1">units</span>
                              {availableCap !== null && (
                                <div className="text-[10px] text-emerald-600 font-medium">
                                  {availableCap.toLocaleString()} avail
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-400 italic text-[11px]">Unset</span>
                          )}
                        </TableCell>

                        {/* Current Stock */}
                        <TableCell className="py-3.5 px-3 text-right">
                          <div className="font-semibold text-slate-900">
                            {stock.toLocaleString()}
                            <span className="text-[10px] text-slate-400 font-normal ml-1">units</span>
                          </div>
                          <div className="text-[10px] text-blue-600 font-medium">
                            {dispatchable.toLocaleString()} dispatchable
                          </div>
                        </TableCell>

                        {/* Utilization Bar */}
                        <TableCell className="py-3.5 px-3">
                          {utilizationPct !== null ? (
                            <div className="w-28 space-y-1">
                              <div className="flex items-center justify-between text-[10px]">
                                <span className={`font-semibold ${
                                  utilizationPct >= 85 ? 'text-red-600' : utilizationPct >= 70 ? 'text-amber-600' : 'text-emerald-700'
                                }`}>
                                  {utilizationPct}%
                                </span>
                              </div>
                              <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${
                                    utilizationPct >= 85 ? 'bg-red-500' : utilizationPct >= 70 ? 'bg-amber-500' : 'bg-emerald-500'
                                  }`}
                                  style={{ width: `${Math.min(utilizationPct, 100)}%` }}
                                />
                              </div>
                            </div>
                          ) : (
                            <span className="text-[11px] text-slate-400 italic">No cap limit</span>
                          )}
                        </TableCell>

                        {/* Daily Dispatch Capacity */}
                        <TableCell className="py-3.5 px-3 text-right font-medium text-slate-700">
                          {wh.dispatch_capacity_daily ? (
                            <span>{Number(wh.dispatch_capacity_daily).toLocaleString()} <span className="text-[10px] text-slate-400 font-normal">/day</span></span>
                          ) : (
                            <span className="text-slate-400 italic text-[11px]">—</span>
                          )}
                        </TableCell>

                        {/* Status */}
                        <TableCell className="py-3.5 px-3 text-center">
                          {wh.is_active !== false ? (
                            <Badge variant="success" dot size="sm">Active</Badge>
                          ) : (
                            <Badge variant="critical" dot size="sm">Inactive</Badge>
                          )}
                        </TableCell>

                        {/* Action */}
                        <TableCell className="py-3.5 px-4 text-center" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs h-7 px-2.5"
                            onClick={() => setSelectedWarehouse(wh)}
                          >
                            Details
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Warehouse Detail Drawer / Modal */}
      {selectedWarehouse && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex justify-end">
          <div className="w-full max-w-2xl bg-white h-full shadow-2xl flex flex-col border-l border-slate-200 animate-in slide-in-from-right duration-200">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-100 flex items-start justify-between bg-slate-50/50">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-blue-100 border border-blue-200 flex items-center justify-center text-blue-700 shrink-0 mt-0.5">
                  <Warehouse className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-slate-900">
                      {selectedWarehouse.name}
                    </h2>
                    {selectedWarehouse.is_active !== false ? (
                      <Badge variant="success" size="sm">Active</Badge>
                    ) : (
                      <Badge variant="critical" size="sm">Inactive</Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-xs text-slate-500 font-mono">
                    <span>{selectedWarehouse.location_id}</span>
                    <span>•</span>
                    <span className="font-sans font-medium text-slate-700">
                      {formatLocationType(selectedWarehouse.location_type)}
                    </span>
                    <span>•</span>
                    <span className="font-sans text-slate-500">
                      {selectedWarehouse.region}
                    </span>
                  </div>
                </div>
              </div>

              <button
                onClick={() => setSelectedWarehouse(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Capacity Bar in Drawer */}
            <div className="px-6 py-4 bg-slate-50/80 border-b border-slate-100 grid grid-cols-3 gap-4 text-center">
              <div>
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Storage Capacity</div>
                <div className="text-base font-bold text-slate-900 mt-0.5">
                  {selectedWarehouse.storage_capacity_units
                    ? Number(selectedWarehouse.storage_capacity_units).toLocaleString()
                    : 'Unset'}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-slate-500 uppercase font-semibold">On-Hand Stock</div>
                <div className="text-base font-bold text-blue-600 mt-0.5">
                  {(inventoryByLocation.get(selectedWarehouse.location_id)?.totalOnHand || 0).toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Dispatch Capacity</div>
                <div className="text-base font-bold text-slate-800 mt-0.5">
                  {selectedWarehouse.dispatch_capacity_daily
                    ? `${Number(selectedWarehouse.dispatch_capacity_daily).toLocaleString()} /day`
                    : '—'}
                </div>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex border-b border-slate-200 px-6 bg-white shrink-0">
              <button
                className={`py-3 px-4 text-xs font-semibold border-b-2 cursor-pointer transition-colors ${
                  detailTab === 'inventory'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
                onClick={() => setDetailTab('inventory')}
              >
                Inventory by SKU ({selectedWarehouseInventory.length})
              </button>
              <button
                className={`py-3 px-4 text-xs font-semibold border-b-2 cursor-pointer transition-colors ${
                  detailTab === 'facility'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
                onClick={() => setDetailTab('facility')}
              >
                Facility Details & Ownership
              </button>
              <button
                className={`py-3 px-4 text-xs font-semibold border-b-2 cursor-pointer transition-colors ${
                  detailTab === 'shipments'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-slate-500 hover:text-slate-700'
                }`}
                onClick={() => setDetailTab('shipments')}
              >
                Shipments & Movements ({selectedWarehouseShipments.length})
              </button>
            </div>

            {/* Tab Contents */}
            <div className="flex-1 overflow-y-auto p-6">
              {/* TAB 1: Inventory by SKU */}
              {detailTab === 'inventory' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs text-slate-600">
                    <span>
                      Total SKUs stocked:{' '}
                      <strong>{selectedWarehouseInventory.length}</strong>
                    </span>
                    <span>
                      Total dispatchable stock:{' '}
                      <strong className="text-emerald-700">
                        {(inventoryByLocation.get(selectedWarehouse.location_id)?.totalDispatchable || 0).toLocaleString()}
                      </strong>{' '}
                      units
                    </span>
                  </div>

                  {selectedWarehouseInventory.length === 0 ? (
                    <EmptyState
                      icon={Boxes}
                      title="No stock records at this location"
                      description="There are currently no active inventory snapshot records associated with this warehouse."
                    />
                  ) : (
                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow className="bg-slate-50 text-[10px] uppercase font-semibold text-slate-500">
                            <TableHead className="py-2.5 px-3">SKU & Product</TableHead>
                            <TableHead className="py-2.5 px-3 text-right">On-Hand</TableHead>
                            <TableHead className="py-2.5 px-3 text-right">Reserved</TableHead>
                            <TableHead className="py-2.5 px-3 text-right">Blocked</TableHead>
                            <TableHead className="py-2.5 px-3 text-right text-emerald-700">Dispatchable</TableHead>
                            <TableHead className="py-2.5 px-3 text-center">Batch / Expiry</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody className="divide-y divide-slate-100 text-xs">
                          {selectedWarehouseInventory.map((item) => {
                            const disp = item.dispatchable_stock ?? Math.max(0, item.on_hand - (item.reserved || 0) - (item.blocked || 0));
                            return (
                              <TableRow key={item.id || `${item.sku_id}-${item.batch_number}`} className="hover:bg-slate-50/50">
                                <TableCell className="py-2.5 px-3">
                                  <div className="font-semibold text-slate-800">
                                    {item.product_name || item.sku_id}
                                  </div>
                                  <div className="text-[11px] font-mono text-slate-500">
                                    {item.sku_id}
                                  </div>
                                </TableCell>
                                <TableCell className="py-2.5 px-3 text-right font-medium text-slate-800">
                                  {Number(item.on_hand || 0).toLocaleString()}
                                </TableCell>
                                <TableCell className="py-2.5 px-3 text-right text-slate-500">
                                  {Number(item.reserved || 0).toLocaleString()}
                                </TableCell>
                                <TableCell className="py-2.5 px-3 text-right text-slate-500">
                                  {Number(item.blocked || 0).toLocaleString()}
                                </TableCell>
                                <TableCell className="py-2.5 px-3 text-right font-bold text-emerald-700">
                                  {disp.toLocaleString()}
                                </TableCell>
                                <TableCell className="py-2.5 px-3 text-center text-[11px]">
                                  {item.batch_number ? (
                                    <div>
                                      <span className="font-mono text-slate-700">{item.batch_number}</span>
                                      {item.expiry_date && (
                                        <div className="text-[10px] text-slate-400">
                                          Exp: {item.expiry_date}
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    <span className="text-slate-400">—</span>
                                  )}
                                </TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: Facility Details & Ownership */}
              {detailTab === 'facility' && (
                <div className="space-y-4">
                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-3">
                    <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Location & Geography
                    </h3>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-slate-500">Region:</span>
                        <div className="font-semibold text-slate-800 mt-0.5">{selectedWarehouse.region}</div>
                      </div>
                      <div>
                        <span className="text-slate-500">City / District:</span>
                        <div className="font-semibold text-slate-800 mt-0.5">{selectedWarehouse.city || '—'}</div>
                      </div>
                      <div className="col-span-2">
                        <span className="text-slate-500">Address:</span>
                        <div className="font-medium text-slate-800 mt-0.5">{selectedWarehouse.address || '—'}</div>
                      </div>
                      {selectedWarehouse.latitude !== undefined && selectedWarehouse.longitude !== undefined && (
                        <div className="col-span-2">
                          <span className="text-slate-500">GPS Coordinates:</span>
                          <div className="font-mono text-slate-600 mt-0.5">
                            {selectedWarehouse.latitude}, {selectedWarehouse.longitude}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-3">
                    <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Ownership & Operations
                    </h3>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-slate-500">Owner Organization:</span>
                        <div className="font-semibold text-slate-800 mt-0.5">
                          {selectedWarehouse.owner_org_name || selectedWarehouse.owner_org_id || 'Company Owned'}
                        </div>
                      </div>
                      <div>
                        <span className="text-slate-500">Operating Agency:</span>
                        <div className="font-semibold text-slate-800 mt-0.5">
                          {selectedWarehouse.operator_org_name || selectedWarehouse.operator_org_id || 'Self-Operated'}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 space-y-3">
                    <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                      Capacity & Operational Throughput
                    </h3>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div>
                        <span className="text-slate-500">Design Storage Capacity:</span>
                        <div className="font-semibold text-slate-800 mt-0.5">
                          {selectedWarehouse.storage_capacity_units
                            ? `${Number(selectedWarehouse.storage_capacity_units).toLocaleString()} units`
                            : 'Unconstrained'}
                        </div>
                      </div>
                      <div>
                        <span className="text-slate-500">Daily Dispatch Limit:</span>
                        <div className="font-semibold text-slate-800 mt-0.5">
                          {selectedWarehouse.dispatch_capacity_daily
                            ? `${Number(selectedWarehouse.dispatch_capacity_daily).toLocaleString()} units/day`
                            : 'Not set'}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: Shipments & Movements */}
              {detailTab === 'shipments' && (
                <div className="space-y-4">
                  {selectedWarehouseShipments.length === 0 ? (
                    <EmptyState
                      icon={Truck}
                      title="No shipments found"
                      description="No recorded shipments have originated from or terminated at this facility."
                    />
                  ) : (
                    <div className="space-y-2">
                      {selectedWarehouseShipments.map((s) => {
                        const isOrigin = s.source_location_id === selectedWarehouse.location_id;
                        return (
                          <div
                            key={s.shipment_id}
                            className="p-3 border border-slate-200 rounded-lg flex items-center justify-between hover:bg-slate-50/50 text-xs"
                          >
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-slate-900">{s.shipment_id}</span>
                                <Badge variant={s.status === 'delivered' ? 'success' : s.status === 'in_transit' ? 'primary' : 'warning'} size="sm">
                                  {s.status.replace(/_/g, ' ')}
                                </Badge>
                              </div>
                              <div className="text-slate-600 flex items-center gap-1.5">
                                <span>{isOrigin ? 'To' : 'From'}:</span>
                                <strong className="text-slate-800 font-semibold">
                                  {isOrigin ? s.destination_location_name || s.destination_location_id : s.source_location_name || s.source_location_id}
                                </strong>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="font-bold text-slate-900">{s.quantity?.toLocaleString()} units</div>
                              <div className="text-[11px] text-slate-400">{s.created_at ? new Date(s.created_at).toLocaleDateString() : '—'}</div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-slate-100 flex items-center justify-between bg-slate-50">
              <span className="text-xs text-slate-500 font-mono">
                {selectedWarehouse.location_id}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedWarehouse(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
