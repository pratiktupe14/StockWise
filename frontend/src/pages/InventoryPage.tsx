import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Boxes,
  Package,
  Search,
  Filter,
  UploadCloud,
  RefreshCw,
  ArrowRightLeft,
} from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Card } from '../components/ui/Card';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../components/ui/Table';
import { EmptyState } from '../components/ui/EmptyState';
import { getInventory, getRedistributionRecommendations, submitRedistributionProposal } from '../services/api';
import type { InventoryItem } from '../types/api';

export const InventoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLocation, setSelectedLocation] = useState('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'dispatchable' | 'zero-dispatchable' | 'has-blocked'>('all');

  const [records, setRecords] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [redistRecommendations, setRedistRecommendations] = useState<any[]>([]);
  const [loadingRedist, setLoadingRedist] = useState(false);
  const [submittingRecId, setSubmittingRecId] = useState<string | null>(null);
  const [proposalSuccess, setProposalSuccess] = useState<string | null>(null);

  const fetchRedist = async () => {
    setLoadingRedist(true);
    try {
      const data = await getRedistributionRecommendations();
      setRedistRecommendations(data.recommendations || []);
    } catch {
      // Non-blocking
    } finally {
      setLoadingRedist(false);
    }
  };

  const handleProposeTransfer = async (rec: any) => {
    setSubmittingRecId(rec.recommendation_id);
    setProposalSuccess(null);
    try {
      const res = await submitRedistributionProposal({
        sku_id: rec.sku_id,
        source_location_id: rec.source_location_id,
        destination_location_id: rec.destination_location_id,
        quantity: rec.recommended_quantity,
        batch_number: rec.batch_number,
        notes: `Authorized expiry prevention transfer: ${rec.rationale}`,
      });
      setProposalSuccess(`Shipment proposal #${res.shipment_id} created successfully! Navigate to Shipments & Logistics to review and approve.`);
      setRedistRecommendations((prev) => prev.filter((r) => r.recommendation_id !== rec.recommendation_id));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to submit proposal');
    } finally {
      setSubmittingRecId(null);
    }
  };

  const fetchRecords = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getInventory();
      setRecords(data);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to fetch inventory snapshots');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecords();
    fetchRedist();
  }, []);

  // Compute distinct locations from records
  const uniqueLocations = Array.from(new Set(records.map((r) => r.location_id))).sort();

  // Filter records
  const filteredRecords = records.filter((rec) => {
    // Search query match on SKU, product name, or location
    const query = searchQuery.toLowerCase().trim();
    if (query) {
      const matchSku = rec.sku_id.toLowerCase().includes(query);
      const matchName = (rec.product_name || '').toLowerCase().includes(query);
      const matchLoc = rec.location_id.toLowerCase().includes(query) || (rec.location_name || '').toLowerCase().includes(query);
      if (!matchSku && !matchName && !matchLoc) return false;
    }

    // Location filter
    if (selectedLocation !== 'all' && rec.location_id !== selectedLocation) {
      return false;
    }

    // Status filter
    if (statusFilter === 'dispatchable' && rec.dispatchable_stock <= 0) {
      return false;
    }
    if (statusFilter === 'zero-dispatchable' && rec.dispatchable_stock > 0) {
      return false;
    }
    if (statusFilter === 'has-blocked' && rec.blocked <= 0) {
      return false;
    }

    return true;
  });

  // Calculate aggregates
  const totalOnHand = records.reduce((sum, r) => sum + r.on_hand, 0);
  const totalReserved = records.reduce((sum, r) => sum + r.reserved, 0);
  const totalBlocked = records.reduce((sum, r) => sum + r.blocked, 0);
  const totalDispatchable = records.reduce((sum, r) => sum + r.dispatchable_stock, 0);

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">Inventory Visibility</h1>
            <Badge variant="success" size="sm">Live Persisted State</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Multi-location warehouse balances with mathematically isolated dispatchable quantities.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchRecords}
            isLoading={loading}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            leftIcon={<UploadCloud className="w-4 h-4" />}
            onClick={() => navigate('/imports')}
          >
            Import Snapshot
          </Button>
        </div>
      </div>

      {/* Accounting Formula Banner */}
      <Alert variant="info" title="PRD Section 7.4 Inventory Accounting Principle">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mt-1">
          <span>
            Dispatchable stock is computed strictly as:{' '}
            <code className="bg-blue-100/70 text-blue-900 px-1.5 py-0.5 rounded font-mono font-semibold">
              Dispatchable = max(0, On-Hand − Reserved − Blocked)
            </code>
          </span>
          <span className="text-[11px] text-blue-700">
            Incoming and in-transit units are excluded from current dispatchable stock.
          </span>
        </div>
      </Alert>

      {/* Error display */}
      {error && (
        <Alert variant="error" title="Data Sync Error">
          {error}
        </Alert>
      )}

      {/* Inventory KPI Summary Cards */}
      {records.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="p-4 bg-white border-slate-200">
            <div className="text-xs text-slate-500 font-medium">Total On-Hand</div>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {totalOnHand.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Physical gross inventory</div>
          </Card>

          <Card className="p-4 bg-white border-slate-200">
            <div className="text-xs text-slate-500 font-medium">Committed / Reserved</div>
            <div className="text-2xl font-bold text-slate-700 mt-1">
              {totalReserved.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Allocated to existing customer orders</div>
          </Card>

          <Card className="p-4 bg-white border-slate-200">
            <div className="text-xs text-slate-500 font-medium">Quality Blocked</div>
            <div className={`text-2xl font-bold mt-1 ${totalBlocked > 0 ? 'text-amber-600' : 'text-slate-700'}`}>
              {totalBlocked.toLocaleString()}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Damaged, quarantine, or QA holds</div>
          </Card>

          <Card className="p-4 bg-white border-blue-200 bg-blue-50/20">
            <div className="text-xs text-blue-800 font-medium">Current Dispatchable Stock</div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {totalDispatchable.toLocaleString()}
            </div>
            <div className="text-[11px] text-blue-700 mt-0.5 font-medium">
              Available immediately for allocation
            </div>
          </Card>
        </div>
      )}

      {/* Controls: Search & Location filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by SKU, product name, or location..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E5E7EB] bg-white text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
            <div className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-slate-400" />
              <select
                value={selectedLocation}
                onChange={(e) => setSelectedLocation(e.target.value)}
                className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600 cursor-pointer"
              >
                <option value="all">All Locations ({uniqueLocations.length})</option>
                {uniqueLocations.map((loc) => (
                  <option key={loc} value={loc}>
                    {loc}
                  </option>
                ))}
              </select>
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as any)}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600 cursor-pointer"
            >
              <option value="all">All Stock Statuses</option>
              <option value="dispatchable">Dispatchable Stock &gt; 0</option>
              <option value="zero-dispatchable">Zero Dispatchable</option>
              <option value="has-blocked">Has Blocked Units</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Main Table or Empty State */}
      {records.length === 0 && !loading ? (
        <EmptyState
          icon={Boxes}
          title="No inventory records available"
          description="The operational database has no inventory snapshot records yet. Import an inventory snapshot CSV or Excel file to populate this view."
          actionLabel="Go to Import Centre"
          onAction={() => navigate('/imports')}
        />
      ) : (
        <Card className="border-slate-200">
          <div className="p-3 border-b border-slate-100 flex items-center justify-between text-xs text-slate-500">
            <span>Showing {filteredRecords.length} of {records.length} inventory positions</span>
            <span>Formula: On-Hand − Reserved − Blocked</span>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU Identifier</TableHead>
                <TableHead>Product Description</TableHead>
                <TableHead>Facility / Storage Node</TableHead>
                <TableHead>Inventory Owner</TableHead>
                <TableHead>Batch / Expiry</TableHead>
                <TableHead className="text-right">On-Hand</TableHead>
                <TableHead className="text-right">Reserved</TableHead>
                <TableHead className="text-right">Blocked</TableHead>
                <TableHead className="text-right bg-blue-50/50">Dispatchable Stock</TableHead>
                <TableHead>Snapshot As-Of</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRecords.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="text-center py-12 text-slate-500">
                    <Package className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                    <div className="text-sm font-semibold text-slate-700">
                      {records.length === 0 ? 'No inventory records yet' : 'No matching records found'}
                    </div>
                    <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                      {records.length === 0
                        ? 'The inventory ledger is currently clean. Ingest your initial stock snapshots via the Import Centre.'
                        : `No inventory records match "${searchQuery}".`}
                    </p>
                    {records.length === 0 && (
                      <a
                        href="/imports"
                        className="inline-flex items-center gap-1.5 mt-3 text-xs font-semibold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition"
                      >
                        Go to Import Centre &rarr;
                      </a>
                    )}
                  </TableCell>
                </TableRow>
              ) : (
                filteredRecords.map((item) => (
                  <TableRow key={item.id} className="hover:bg-slate-50/60">
                    <TableCell className="font-mono text-xs font-semibold text-slate-900">
                      {item.sku_id}
                    </TableCell>
                    <TableCell className="text-xs text-slate-700">
                      <div>{item.product_name || item.sku_id}</div>
                      {item.category && (
                        <div className="text-[10px] text-slate-400">{item.category}</div>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-slate-800 font-mono">
                      {item.location_name ? (
                        <div>
                          <span>{item.location_name}</span>
                          <span className="text-[10px] text-slate-400 block">{item.location_id}</span>
                        </div>
                      ) : (
                        item.location_id
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-slate-800">
                      {item.owner_org_name || item.owner_org_id ? (
                        <span className="inline-flex items-center gap-1 font-semibold text-[11px] text-blue-800 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                          {item.owner_org_name || item.owner_org_id}
                        </span>
                      ) : (
                        <span className="text-slate-400 text-xs italic">Company Owned</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-slate-600">
                      {item.batch_number || item.expiry_date ? (
                        <div className="space-y-1">
                          <div className="font-semibold text-slate-800">{item.batch_number || 'Batch —'}</div>
                          {item.expiry_date ? (
                            (() => {
                              const exp = new Date(item.expiry_date);
                              const now = new Date();
                              const diffDays = Math.ceil((exp.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
                              if (diffDays <= 0) {
                                return (
                                  <div className="flex items-center gap-1">
                                    <span className="text-[10px] text-slate-500">Exp: {item.expiry_date}</span>
                                    <span className="inline-block text-[9px] font-bold text-rose-700 bg-rose-50 border border-rose-200 px-1 py-0.5 rounded">
                                      EXPIRED
                                    </span>
                                  </div>
                                );
                              }
                              if (diffDays <= 15) {
                                return (
                                  <div className="flex items-center gap-1">
                                    <span className="text-[10px] text-slate-500">Exp: {item.expiry_date}</span>
                                    <span className="inline-block text-[9px] font-bold text-amber-800 bg-amber-50 border border-amber-200 px-1 py-0.5 rounded">
                                      CRITICAL ({diffDays}d)
                                    </span>
                                  </div>
                                );
                              }
                              if (diffDays <= 30) {
                                return (
                                  <div className="flex items-center gap-1">
                                    <span className="text-[10px] text-slate-500">Exp: {item.expiry_date}</span>
                                    <span className="inline-block text-[9px] font-semibold text-yellow-800 bg-yellow-50 border border-yellow-200 px-1 py-0.5 rounded">
                                      NEAR EXP ({diffDays}d)
                                    </span>
                                  </div>
                                );
                              }
                              return (
                                <div className="flex items-center gap-1">
                                  <span className="text-[10px] text-slate-500">Exp: {item.expiry_date}</span>
                                  <span className="inline-block text-[9px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 px-1 py-0.5 rounded">
                                    {diffDays}d shelf life
                                  </span>
                                </div>
                              );
                            })()
                          ) : (
                            <span className="text-[10px] text-slate-400 italic block">Unknown exp</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-slate-400 text-xs italic">Unbatched</span>
                      )}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-right text-slate-800">
                      {item.on_hand.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-right text-slate-600">
                      {item.reserved > 0 ? item.reserved.toLocaleString() : '—'}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-right text-amber-700">
                      {item.blocked > 0 ? (
                        <span className="font-semibold">{item.blocked.toLocaleString()}</span>
                      ) : (
                        '—'
                      )}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-right bg-blue-50/30">
                      <span
                        className={`font-bold px-2 py-0.5 rounded text-xs ${
                          item.dispatchable_stock > 0
                            ? 'text-blue-700 bg-blue-100/60'
                            : 'text-slate-400 bg-slate-100'
                        }`}
                      >
                        {item.dispatchable_stock.toLocaleString()}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 font-mono">
                      {item.as_of_date}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Authorized Redistribution & Expiry Prevention Section */}
      <Card className="p-5 border-slate-200 bg-white">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-slate-100">
          <div>
            <div className="flex items-center gap-2">
              <ArrowRightLeft className="w-5 h-5 text-indigo-600" />
              <h2 className="text-base font-bold text-slate-900">Authorized Redistribution & Expiry Prevention</h2>
              <Badge variant="primary" size="sm">Phase 7 Engine</Badge>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Identifies near-expiry or surplus batches and pairs them with authorized facilities facing inventory shortfalls.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={fetchRedist}
            isLoading={loadingRedist}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Analyze Redistribution
          </Button>
        </div>

        {proposalSuccess && (
          <div className="mt-4">
            <Alert variant="success" title="Proposal Submitted">
              {proposalSuccess}
            </Alert>
          </div>
        )}

        <div className="mt-4">
          {redistRecommendations.length === 0 ? (
            <div className="text-center py-6 text-xs text-slate-400">
              No active redistribution recommendations found. Click &quot;Analyze Redistribution&quot; to discover opportunities to prevent stock expiry.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU / Product</TableHead>
                  <TableHead>Source WH</TableHead>
                  <TableHead>Destination</TableHead>
                  <TableHead>Batch / Shelf Life</TableHead>
                  <TableHead className="text-right">Recommended Qty</TableHead>
                  <TableHead>Lead Time & ETA</TableHead>
                  <TableHead className="text-right">Est. Freight</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {redistRecommendations.map((rec) => (
                  <TableRow key={rec.recommendation_id}>
                    <TableCell className="font-mono text-xs font-semibold text-slate-900">
                      <div>{rec.sku_id}</div>
                      <div className="text-[10px] text-slate-500 font-normal">{rec.product_name}</div>
                    </TableCell>
                    <TableCell className="text-xs text-slate-700">
                      {rec.source_location_name || rec.source_location_id}
                    </TableCell>
                    <TableCell className="text-xs text-slate-700">
                      <div>{rec.destination_location_name || rec.destination_location_id}</div>
                      <div className="text-[10px] text-slate-400">Shortfall: {rec.destination_unmet_demand} units</div>
                    </TableCell>
                    <TableCell className="text-xs font-mono text-slate-600">
                      <div>{rec.batch_number || 'Batch —'}</div>
                      <div className="text-[10px] text-amber-700">
                        {rec.days_remaining}d left ({rec.shelf_life_days_at_arrival}d on arrival)
                      </div>
                    </TableCell>
                    <TableCell className="text-xs font-mono font-bold text-right text-indigo-700">
                      {rec.recommended_quantity}
                    </TableCell>
                    <TableCell className="text-xs text-slate-600 font-mono">
                      <div>{rec.lead_time_days}d lead time</div>
                      <div className="text-[10px] text-slate-400">ETA: {rec.expected_delivery_date}</div>
                    </TableCell>
                    <TableCell className="text-xs font-mono text-right text-slate-800">
                      ₹{rec.estimated_transport_cost.toLocaleString()}
                    </TableCell>
                    <TableCell>
                      <Badge variant={rec.priority_score > 60 ? 'critical' : 'warning'} size="sm">
                        {rec.priority_score} pts
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="primary"
                        isLoading={submittingRecId === rec.recommendation_id}
                        onClick={() => handleProposeTransfer(rec)}
                      >
                        Propose
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </Card>
    </div>
  );
};
