import React, { useState, useEffect, useMemo } from 'react';
import {
  Store,
  Boxes,
  Truck,
  Send,
  Clock,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Search,
  ShieldCheck,
  Calendar,
  AlertCircle,
  Package,
  ArrowRight,
  Info,
} from 'lucide-react';
import {
  getDistributorDashboard,
  getDistributorInventory,
  getDistributorRequests,
  submitDistributorRequest,
  getDistributorShipments,
  getProducts,
  confirmDistributorReceipt,
  cancelDistributorRequest,
} from '../services/api';

import type {
  DistributorDashboardResponse,
  InventoryItem,
  ShipmentItem,
  ProductItem,
} from '../types/api';
import { useAuth } from '../context/AuthContext';

export const DistributorPortalPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'dashboard' | 'inventory' | 'requests' | 'shipments'>('dashboard');

  // Dashboard Data
  const [dashboard, setDashboard] = useState<DistributorDashboardResponse | null>(null);
  const [dashboardLoading, setDashboardLoading] = useState<boolean>(true);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  // Inventory Data
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [inventoryLoading, setInventoryLoading] = useState<boolean>(false);
  const [invSearchQuery, setInvSearchQuery] = useState<string>('');

  // Requests Data
  const [requests, setRequests] = useState<ShipmentItem[]>([]);
  const [requestsLoading, setRequestsLoading] = useState<boolean>(false);

  // Shipments Data
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);
  const [shipmentsLoading, setShipmentsLoading] = useState<boolean>(false);
  const [shipmentStatusFilter, setShipmentStatusFilter] = useState<string>('all');

  // Request Submission Form State
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [selectedSku, setSelectedSku] = useState<string>('');
  const [requestQty, setRequestQty] = useState<number>(50);
  const [requestReason, setRequestReason] = useState<string>('Stockout prevention & local demand surge');
  const [requestNotes, setRequestNotes] = useState<string>('');
  const [submittingRequest, setSubmittingRequest] = useState<boolean>(false);
  const [submissionSuccess, setSubmissionSuccess] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  // Receipt Confirmation Modal State
  const [receiptShipment, setReceiptShipment] = useState<ShipmentItem | null>(null);
  const [showReceiptModal, setShowReceiptModal] = useState<boolean>(false);
  const [receivedQty, setReceivedQty] = useState<number>(0);
  const [conditionStatus, setConditionStatus] = useState<string>('intact');
  const [discrepancyUnits, setDiscrepancyUnits] = useState<number>(0);
  const [receiptNotes, setReceiptNotes] = useState<string>('');
  const [submittingReceipt, setSubmittingReceipt] = useState<boolean>(false);
  const [receiptError, setReceiptError] = useState<string | null>(null);

  // Request Cancellation State
  const [cancelTargetShipment, setCancelTargetShipment] = useState<ShipmentItem | null>(null);
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>('');
  const [cancellingRequest, setCancellingRequest] = useState<boolean>(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  // Handle Receipt Confirmation
  const handleConfirmReceipt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!receiptShipment) return;
    setSubmittingReceipt(true);
    setReceiptError(null);
    try {
      await confirmDistributorReceipt(receiptShipment.shipment_id, {
        received_quantity: Number(receivedQty),
        condition_status: conditionStatus,
        discrepancy_units: Number(discrepancyUnits) || 0,
        notes: receiptNotes || undefined,
      });
      setSubmissionSuccess(`Receipt confirmed for shipment ${receiptShipment.shipment_id}. Stock credited.`);
      setShowReceiptModal(false);
      setReceiptShipment(null);
      // Refresh relevant data
      fetchShipments();
      fetchInventory();
      fetchDashboard();
    } catch (err: any) {
      setReceiptError(err.message || 'Failed to confirm receipt.');
    } finally {
      setSubmittingReceipt(false);
    }
  };

  // Handle Request Cancellation
  const handleCancelRequestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelTargetShipment) return;
    setCancellingRequest(true);
    setCancelError(null);
    try {
      await cancelDistributorRequest(cancelTargetShipment.shipment_id, {
        reason: cancelReason || undefined,
      });
      setSubmissionSuccess(`Transfer request ${cancelTargetShipment.shipment_id} cancelled.`);
      setShowCancelModal(false);
      setCancelTargetShipment(null);
      fetchRequests();
      fetchDashboard();
    } catch (err: any) {
      setCancelError(err.message || 'Failed to cancel request.');
    } finally {
      setCancellingRequest(false);
    }
  };

  // Fetch Dashboard

  const fetchDashboard = async () => {
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      const data = await getDistributorDashboard();
      setDashboard(data);
    } catch (err: any) {
      setDashboardError(err.message || 'Failed to load distributor dashboard data.');
    } finally {
      setDashboardLoading(false);
    }
  };

  // Fetch Inventory
  const fetchInventory = async () => {
    setInventoryLoading(true);
    try {
      const data = await getDistributorInventory();
      setInventory(data);
    } catch (err: any) {
      console.error('Failed to load distributor inventory', err);
    } finally {
      setInventoryLoading(false);
    }
  };

  // Fetch Requests
  const fetchRequests = async () => {
    setRequestsLoading(true);
    try {
      const data = await getDistributorRequests();
      setRequests(data);
    } catch (err: any) {
      console.error('Failed to load distributor requests', err);
    } finally {
      setRequestsLoading(false);
    }
  };

  // Fetch Shipments
  const fetchShipments = async () => {
    setShipmentsLoading(true);
    try {
      const data = await getDistributorShipments(
        shipmentStatusFilter !== 'all' ? shipmentStatusFilter : undefined
      );
      setShipments(data);
    } catch (err: any) {
      console.error('Failed to load distributor shipments', err);
    } finally {
      setShipmentsLoading(false);
    }
  };

  // Fetch Products for Request Dropdown
  const fetchProductList = async () => {
    try {
      const prods = await getProducts();
      setProducts(prods);
      if (prods.length > 0 && !selectedSku) {
        setSelectedSku(prods[0].sku_id);
      }
    } catch (err) {
      console.error('Failed to load products list', err);
    }
  };

  useEffect(() => {
    fetchDashboard();
    fetchProductList();
  }, []);

  useEffect(() => {
    if (activeTab === 'inventory') fetchInventory();
    if (activeTab === 'requests') fetchRequests();
    if (activeTab === 'shipments') fetchShipments();
  }, [activeTab, shipmentStatusFilter]);

  const handleRequestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmissionError(null);
    setSubmissionSuccess(null);

    if (requestQty <= 0) {
      setSubmissionError('Requested quantity must be greater than zero.');
      return;
    }
    if (!selectedSku) {
      setSubmissionError('Please select a valid product SKU.');
      return;
    }

    setSubmittingRequest(true);
    try {
      const result = await submitDistributorRequest({
        sku_id: selectedSku,
        quantity: requestQty,
        reason: requestReason,
        notes: requestNotes,
      });

      setSubmissionSuccess(
        `Request #${result.shipment_id} successfully submitted in proposed status. Awaiting planner authorization.`
      );
      setRequestNotes('');
      // Refresh requests and dashboard
      fetchRequests();
      fetchDashboard();
    } catch (err: any) {
      setSubmissionError(err.message || 'Failed to submit transfer request.');
    } finally {
      setSubmittingRequest(false);
    }
  };

  const filteredInventory = useMemo(() => {
    if (!invSearchQuery) return inventory;
    const q = invSearchQuery.toLowerCase();
    return inventory.filter(
      (i) =>
        i.sku_id.toLowerCase().includes(q) ||
        (i.product_name && i.product_name.toLowerCase().includes(q)) ||
        (i.batch_number && i.batch_number.toLowerCase().includes(q)) ||
        (i.location_name && i.location_name.toLowerCase().includes(q))
    );
  }, [inventory, invSearchQuery]);

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      {/* Top Banner / Breadcrumb */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-50 text-indigo-700 rounded-lg">
              <Store className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">Distributor Portal</h1>
              <p className="text-xs text-slate-500">
                Authorized regional partner portal: Stock visibility, replenishment requests, and shipment delivery tracking.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs font-medium flex items-center gap-1.5 shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
            <span>Org: <strong>{dashboard?.distributor_org_id || user?.orgId || 'ORG-DIST-WEST'}</strong></span>
          </div>

          <button
            onClick={() => {
              fetchDashboard();
              if (activeTab === 'inventory') fetchInventory();
              if (activeTab === 'requests') fetchRequests();
              if (activeTab === 'shipments') fetchShipments();
            }}
            className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium flex items-center gap-1.5 transition-colors shadow-2xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-slate-200 gap-1">
        <button
          onClick={() => setActiveTab('dashboard')}
          className={`px-4 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'dashboard'
              ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Store className="w-4 h-4" />
          Distributor Dashboard
        </button>

        <button
          onClick={() => setActiveTab('inventory')}
          className={`px-4 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'inventory'
              ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Boxes className="w-4 h-4" />
          My Owned Inventory
        </button>

        <button
          onClick={() => setActiveTab('requests')}
          className={`px-4 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'requests'
              ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Send className="w-4 h-4" />
          Stock Requests
          {dashboard?.pending_requests_count ? (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-100 text-amber-800 font-bold">
              {dashboard.pending_requests_count}
            </span>
          ) : null}
        </button>

        <button
          onClick={() => setActiveTab('shipments')}
          className={`px-4 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'shipments'
              ? 'border-indigo-600 text-indigo-700 bg-indigo-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Truck className="w-4 h-4" />
          Shipment Tracking
          {dashboard?.in_transit_shipments_count ? (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-blue-100 text-blue-800 font-bold">
              {dashboard.in_transit_shipments_count}
            </span>
          ) : null}
        </button>
      </div>

      {/* TAB 1: DASHBOARD */}
      {activeTab === 'dashboard' && (
        <div className="space-y-6">
          {dashboardError && (
            <div className="p-4 rounded-lg bg-red-50 border border-red-200 text-red-800 text-xs flex items-center gap-3">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
              <span>{dashboardError}</span>
            </div>
          )}

          {/* Metric KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-medium uppercase tracking-wider">Total On-Hand</span>
                <Boxes className="w-4 h-4 text-indigo-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">
                {dashboardLoading ? '...' : (dashboard?.total_on_hand_units.toLocaleString() ?? '0')}
              </div>
              <div className="mt-1 text-[11px] text-slate-500 flex items-center gap-1">
                <span>{dashboard?.total_owned_skus ?? 0} Distinct SKUs in possession</span>
              </div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-medium uppercase tracking-wider">Dispatchable Units</span>
                <Package className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">
                {dashboardLoading ? '...' : (dashboard?.total_dispatchable_units.toLocaleString() ?? '0')}
              </div>
              <div className="mt-1 text-[11px] text-emerald-600 flex items-center gap-1">
                <span>Available for immediate dispatch</span>
              </div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-medium uppercase tracking-wider">Pending Requests</span>
                <Clock className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-2xl font-bold text-amber-700">
                {dashboardLoading ? '...' : (dashboard?.pending_requests_count ?? 0)}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                Replenishment requests awaiting approval
              </div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-medium uppercase tracking-wider">In-Transit Shipments</span>
                <Truck className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-blue-700">
                {dashboardLoading ? '...' : (dashboard?.in_transit_shipments_count ?? 0)}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                Active consignments en route to facility
              </div>
            </div>
          </div>

          {/* Near-Expiry Warning Callout */}
          {(dashboard?.near_expiry_batches_count ?? 0) > 0 && (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
                <div>
                  <h4 className="text-xs font-bold text-amber-900">
                    {dashboard?.near_expiry_batches_count} Near-Expiry Batches in Distributor Inventory
                  </h4>
                  <p className="text-[11px] text-amber-700">
                    Batches expiring within 90 days. Recommend prioritizing FEFO liquidation or submitting a redistribution request.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setActiveTab('inventory')}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded-lg transition-colors"
              >
                Inspect Batches
              </button>
            </div>
          )}

          {/* Recent Shipments & Recent Requests Tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Recent Incoming Shipments */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Recent Shipments</h3>
                </div>
                <button
                  onClick={() => setActiveTab('shipments')}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  View All &rarr;
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold">ID</th>
                      <th className="py-2.5 px-3 font-semibold">SKU</th>
                      <th className="py-2.5 px-3 font-semibold">Qty</th>
                      <th className="py-2.5 px-3 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {dashboard?.recent_shipments && dashboard.recent_shipments.length > 0 ? (
                      dashboard.recent_shipments.slice(0, 5).map((s) => (
                        <tr key={s.shipment_id} className="hover:bg-slate-50/50">
                          <td className="py-2.5 px-3 font-mono font-medium text-slate-900 truncate max-w-[100px]">
                            {s.shipment_id}
                          </td>
                          <td className="py-2.5 px-3 font-medium">{s.sku_id}</td>
                          <td className="py-2.5 px-3 font-bold">{s.quantity.toLocaleString()}</td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                                s.status === 'delivered'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : s.status === 'in_transit'
                                  ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                  : 'bg-slate-100 text-slate-700 border border-slate-200'
                              }`}
                            >
                              {s.status}
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-slate-400">
                          No shipments found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Recent Requests */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Send className="w-4 h-4 text-amber-600" />
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Recent Stock Requests</h3>
                </div>
                <button
                  onClick={() => setActiveTab('requests')}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
                >
                  View All &rarr;
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold">Request ID</th>
                      <th className="py-2.5 px-3 font-semibold">SKU</th>
                      <th className="py-2.5 px-3 font-semibold">Qty</th>
                      <th className="py-2.5 px-3 font-semibold">Approval Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {dashboard?.recent_requests && dashboard.recent_requests.length > 0 ? (
                      dashboard.recent_requests.slice(0, 5).map((r) => (
                        <tr key={r.shipment_id} className="hover:bg-slate-50/50">
                          <td className="py-2.5 px-3 font-mono font-medium text-slate-900 truncate max-w-[120px]">
                            {r.shipment_id}
                          </td>
                          <td className="py-2.5 px-3 font-medium">{r.sku_id}</td>
                          <td className="py-2.5 px-3 font-bold">{r.quantity.toLocaleString()}</td>
                          <td className="py-2.5 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                                r.approval_status === 'approved'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : r.approval_status === 'pending'
                                  ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                  : 'bg-red-50 text-red-700 border border-red-200'
                              }`}
                            >
                              {r.approval_status}
                            </span>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan={4} className="py-6 text-center text-slate-400">
                          No pending requests found.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: MY OWNED INVENTORY */}
      {activeTab === 'inventory' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search SKU, product, batch or facility..."
                value={invSearchQuery}
                onChange={(e) => setInvSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
            </div>
            <div className="text-xs text-slate-500">
              Showing <strong>{filteredInventory.length}</strong> owned inventory records
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="py-3 px-4 font-semibold">SKU & Product</th>
                    <th className="py-3 px-4 font-semibold">Facility / Location</th>
                    <th className="py-3 px-4 font-semibold">Batch #</th>
                    <th className="py-3 px-4 font-semibold">Expiry Date</th>
                    <th className="py-3 px-4 font-semibold text-right">On Hand</th>
                    <th className="py-3 px-4 font-semibold text-right">Dispatchable</th>
                    <th className="py-3 px-4 font-semibold">Ownership Org</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {inventoryLoading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500" />
                        Loading authorized inventory...
                      </td>
                    </tr>
                  ) : filteredInventory.length > 0 ? (
                    filteredInventory.map((item) => (
                      <tr key={item.snapshot_id} className="hover:bg-slate-50/50">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900">{item.product_name || item.sku_id}</div>
                          <div className="text-[10px] font-mono text-slate-400">{item.sku_id}</div>
                        </td>
                        <td className="py-3 px-4">
                          <div className="text-slate-800">{item.location_name || item.location_id}</div>
                          <div className="text-[10px] text-slate-400">Distributor Facility</div>
                        </td>
                        <td className="py-3 px-4 font-mono font-medium text-slate-600">
                          {item.batch_number || 'BATCH-STD-01'}
                        </td>
                        <td className="py-3 px-4">
                          {item.expiry_date ? (
                            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-slate-700">
                              <Calendar className="w-3 h-3 text-slate-400" />
                              {item.expiry_date}
                            </span>
                          ) : (
                            <span className="text-slate-400">N/A</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right font-bold text-slate-900">
                          {item.on_hand.toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right font-bold text-emerald-600">
                          {item.dispatchable_stock.toLocaleString()}
                        </td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                            {item.owner_org_id} (Distributor)
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        No authorized inventory records found for this distributor organization.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: STOCK REQUESTS */}
      {activeTab === 'requests' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Submission Form */}
          <div className="lg:col-span-1 bg-white rounded-xl border border-slate-200 p-5 shadow-2xs h-fit space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Send className="w-4 h-4 text-indigo-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Submit Replenishment Request
              </h3>
            </div>

            <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-[11px] text-blue-800 flex items-start gap-2">
              <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <span>
                Submission creates a <strong>proposed shipment</strong>. It does not mutate physical stock or dispatch goods until authorized by an administrator or planner.
              </span>
            </div>

            {submissionSuccess && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-800 flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>{submissionSuccess}</span>
              </div>
            )}

            {submissionError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                <span>{submissionError}</span>
              </div>
            )}

            <form onSubmit={handleRequestSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Product SKU <span className="text-red-500">*</span>
                </label>
                <select
                  value={selectedSku}
                  onChange={(e) => setSelectedSku(e.target.value)}
                  required
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-indigo-500"
                >
                  {products.length === 0 ? (
                    <option value="" disabled>No products available (Import products first)</option>
                  ) : (
                    products.map((p) => (
                      <option key={p.sku_id} value={p.sku_id}>
                        {p.name} ({p.sku_id})
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Requested Quantity (Units) <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={requestQty}
                  onChange={(e) => setRequestQty(parseInt(e.target.value) || 0)}
                  required
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-indigo-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Business Reason</label>
                <input
                  type="text"
                  value={requestReason}
                  onChange={(e) => setRequestReason(e.target.value)}
                  placeholder="e.g. Festival demand surge, low stock cover..."
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Optional Notes</label>
                <textarea
                  rows={2}
                  value={requestNotes}
                  onChange={(e) => setRequestNotes(e.target.value)}
                  placeholder="Delivery timing preferences, dock instructions..."
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-indigo-500"
                />
              </div>

              <button
                type="submit"
                disabled={submittingRequest}
                className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-2 transition-colors shadow-2xs"
              >
                {submittingRequest ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                <span>Submit Replenishment Request</span>
              </button>
            </form>
          </div>

          {/* List of Requests */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-500" />
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Submitted Transfer & Replenishment Requests
                </h3>
              </div>
              <button
                onClick={fetchRequests}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" />
                Refresh
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Request ID</th>
                    <th className="py-2.5 px-3 font-semibold">SKU</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Requested Qty</th>
                    <th className="py-2.5 px-3 font-semibold">Destination</th>
                    <th className="py-2.5 px-3 font-semibold">Status</th>
                    <th className="py-2.5 px-3 font-semibold">Notes</th>
                    <th className="py-2.5 px-3 font-semibold text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {requestsLoading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500" />
                        Loading requests...
                      </td>
                    </tr>
                  ) : requests.length > 0 ? (
                    requests.map((r) => (
                      <tr key={r.shipment_id} className="hover:bg-slate-50/50">
                        <td className="py-2.5 px-3 font-mono font-medium text-slate-900">
                          {r.shipment_id}
                        </td>
                        <td className="py-2.5 px-3 font-medium">{r.sku_id}</td>
                        <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                          {r.quantity.toLocaleString()}
                        </td>
                        <td className="py-2.5 px-3 text-slate-600">
                          {r.destination_location_name || r.destination_location_id}
                        </td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                              r.approval_status === 'approved'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : r.approval_status === 'pending'
                                ? 'bg-amber-50 text-amber-700 border border-amber-200'
                                : 'bg-red-50 text-red-700 border border-red-200'
                            }`}
                          >
                            {r.approval_status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-500 max-w-[160px] truncate">
                          {r.approval_notes || 'None'}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {r.approval_status === 'pending' && r.status === 'proposed' ? (
                            <button
                              onClick={() => {
                                setCancelTargetShipment(r);
                                setCancelReason('');
                                setCancelError(null);
                                setShowCancelModal(true);
                              }}
                              className="px-2 py-1 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded text-[11px] font-medium transition-colors"
                            >
                              Cancel
                            </button>
                          ) : (
                            <span className="text-slate-400 text-[11px]">—</span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        No replenishment requests submitted yet. Use the form on the left to request stock.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: SHIPMENT TRACKING */}
      {activeTab === 'shipments' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-600">Filter Status:</span>
              <select
                value={shipmentStatusFilter}
                onChange={(e) => setShipmentStatusFilter(e.target.value)}
                className="text-xs bg-white border border-slate-200 rounded-lg p-1.5 focus:ring-1 focus:ring-indigo-500"
              >
                <option value="all">All Statuses</option>
                <option value="in_transit">In Transit</option>
                <option value="dispatched">Dispatched</option>
                <option value="allocated">Allocated</option>
                <option value="approved">Approved</option>
                <option value="delivered">Delivered</option>
                <option value="proposed">Proposed</option>
              </select>
            </div>

            <div className="text-xs text-slate-500">
              Showing <strong>{shipments.length}</strong> authorized shipments
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="py-3 px-4 font-semibold">Shipment ID</th>
                    <th className="py-3 px-4 font-semibold">Route (Source &rarr; Destination)</th>
                    <th className="py-3 px-4 font-semibold">Product SKU</th>
                    <th className="py-3 px-4 font-semibold text-right">Quantity</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                    <th className="py-3 px-4 font-semibold">Carrier / Vehicle</th>
                    <th className="py-3 px-4 font-semibold">Dispatched / Delivery Date</th>
                    <th className="py-3 px-4 font-semibold text-center">Receipt Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {shipmentsLoading ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-indigo-500" />
                        Loading shipments...
                      </td>
                    </tr>
                  ) : shipments.length > 0 ? (
                    shipments.map((s) => (
                      <tr key={s.shipment_id} className="hover:bg-slate-50/50">
                        <td className="py-3 px-4 font-mono font-medium text-slate-900">
                          {s.shipment_id}
                        </td>
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-1.5 font-medium text-slate-800">
                            <span>{s.source_location_name || s.source_location_id}</span>
                            <ArrowRight className="w-3 h-3 text-slate-400" />
                            <span>{s.destination_location_name || s.destination_location_id}</span>
                          </div>
                        </td>
                        <td className="py-3 px-4 font-medium">{s.sku_id}</td>
                        <td className="py-3 px-4 text-right font-bold text-slate-900">
                          {s.quantity.toLocaleString()}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2.5 py-0.5 rounded-full text-[10px] font-semibold uppercase ${
                              s.status === 'delivered'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : s.status === 'in_transit'
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : s.status === 'ready_for_dispatch'
                                ? 'bg-purple-50 text-purple-700 border border-purple-200'
                                : 'bg-slate-100 text-slate-700 border border-slate-200'
                            }`}
                          >
                            {s.status}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-slate-600">
                          {s.carrier_agency_name || s.vehicle_number || 'Unassigned'}
                        </td>
                        <td className="py-3 px-4 text-slate-600">
                          {s.actual_pickup_date || s.estimated_dispatch_date || 'Pending Dispatch'}
                        </td>
                        <td className="py-3 px-4 text-center">
                          {s.status === 'in_transit' ? (
                            <button
                              onClick={() => {
                                setReceiptShipment(s);
                                setReceivedQty(s.quantity);
                                setConditionStatus('intact');
                                setDiscrepancyUnits(0);
                                setReceiptNotes('');
                                setReceiptError(null);
                                setShowReceiptModal(true);
                              }}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-semibold flex items-center justify-center gap-1 shadow-2xs transition-colors mx-auto"
                            >
                              <CheckCircle2 className="w-3 h-3" />
                              Confirm Receipt
                            </button>
                          ) : s.status === 'delivered' ? (
                            <span className="text-[11px] text-emerald-600 font-semibold flex items-center justify-center gap-1">
                              <CheckCircle2 className="w-3.5 h-3.5" /> Confirmed
                            </span>
                          ) : (
                            <span className="text-slate-400 text-[11px]">—</span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-400">
                        No shipments found matching the selected filter.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* RECEIPT CONFIRMATION & DISCREPANCY REPORTING MODAL */}
      {showReceiptModal && receiptShipment && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full overflow-hidden animate-in fade-in zoom-in duration-150">
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  Confirm Delivery Receipt & Discrepancies
                </h3>
              </div>
              <button
                onClick={() => setShowReceiptModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleConfirmReceipt} className="p-5 space-y-4">
              {receiptError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <span>{receiptError}</span>
                </div>
              )}

              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Shipment ID:</span>
                  <span className="font-mono font-bold text-slate-800">{receiptShipment.shipment_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">SKU / Product:</span>
                  <span className="font-medium text-slate-800">{receiptShipment.sku_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Expected Dispatch Quantity:</span>
                  <span className="font-bold text-slate-900">{receiptShipment.quantity.toLocaleString()} units</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Destination Facility:</span>
                  <span className="text-slate-700">{receiptShipment.destination_location_name || receiptShipment.destination_location_id}</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Actually Received Quantity (Units) <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  value={receivedQty}
                  onChange={(e) => setReceivedQty(parseFloat(e.target.value) || 0)}
                  required
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2.5 focus:ring-1 focus:ring-emerald-500 font-mono text-sm font-bold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Goods Condition Status <span className="text-red-500">*</span>
                </label>
                <select
                  value={conditionStatus}
                  onChange={(e) => setConditionStatus(e.target.value)}
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2.5 focus:ring-1 focus:ring-emerald-500"
                >
                  <option value="intact">Intact / Full Order Received</option>
                  <option value="shortage">Shortage / Incomplete Delivery</option>
                  <option value="damaged">Damaged Goods / Broken Cases</option>
                  <option value="excess">Excess Goods / Extra Cases</option>
                </select>
              </div>

              {conditionStatus !== 'intact' && (
                <div>
                  <label className="block text-xs font-semibold text-amber-800 mb-1">
                    Discrepancy Units (Shortage / Damaged / Excess)
                  </label>
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={discrepancyUnits}
                    onChange={(e) => setDiscrepancyUnits(parseFloat(e.target.value) || 0)}
                    className="w-full text-xs bg-white border border-amber-300 rounded-lg p-2 focus:ring-1 focus:ring-amber-500 font-mono"
                  />
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Receiving Notes & Discrepancy Remarks
                </label>
                <textarea
                  rows={2}
                  value={receiptNotes}
                  onChange={(e) => setReceiptNotes(e.target.value)}
                  placeholder="Notes on packaging condition, batch seal, driver signature..."
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-emerald-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowReceiptModal(false)}
                  className="px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingReceipt}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-2xs transition-colors"
                >
                  {submittingReceipt ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  )}
                  <span>Confirm Receipt & Credit Stock</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* REQUEST CANCELLATION MODAL */}
      {showCancelModal && cancelTargetShipment && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full overflow-hidden animate-in fade-in zoom-in duration-150">
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600" />
                <h3 className="text-sm font-bold text-slate-900">Cancel Replenishment Request</h3>
              </div>
              <button
                onClick={() => setShowCancelModal(false)}
                className="text-slate-400 hover:text-slate-600 text-sm font-bold p-1"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCancelRequestSubmit} className="p-5 space-y-4">
              {cancelError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-800 flex items-start gap-2">
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <span>{cancelError}</span>
                </div>
              )}

              <p className="text-xs text-slate-600">
                Are you sure you want to cancel request{' '}
                <strong className="font-mono text-slate-900">{cancelTargetShipment.shipment_id}</strong> for{' '}
                <strong>{cancelTargetShipment.quantity} units</strong> of <strong>{cancelTargetShipment.sku_id}</strong>?
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Cancellation Reason
                </label>
                <input
                  type="text"
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  placeholder="e.g. Demand covered locally, duplicate order..."
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-red-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCancelModal(false)}
                  className="px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Keep Request
                </button>
                <button
                  type="submit"
                  disabled={cancellingRequest}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-2xs transition-colors"
                >
                  {cancellingRequest ? (
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5" />
                  )}
                  <span>Confirm Cancellation</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default DistributorPortalPage;

