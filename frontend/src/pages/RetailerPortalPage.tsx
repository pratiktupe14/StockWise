import React, { useState, useEffect, useMemo } from 'react';
import {
  ShoppingBag,
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
  getRetailerDashboard,
  getRetailerInventory,
  getRetailerRequests,
  submitRetailerRequest,
  getRetailerShipments,
  getProducts,
  confirmRetailerReceipt,
  cancelRetailerRequest,
} from '../services/api';

import type {
  RetailerDashboardResponse,
  InventoryItem,
  ShipmentItem,
  ProductItem,
} from '../types/api';
import { useAuth } from '../context/AuthContext';

export const RetailerPortalPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'dashboard' | 'inventory' | 'requests' | 'shipments'>('dashboard');

  // Dashboard Data
  const [dashboard, setDashboard] = useState<RetailerDashboardResponse | null>(null);
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
  const [requestQty, setRequestQty] = useState<number>(20);
  const [preferredSource, setPreferredSource] = useState<string>('');
  const [requiredByDate, setRequiredByDate] = useState<string>('');
  const [requestReason, setRequestReason] = useState<string>('Standard store shelf replenishment');
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

  // Order Cancellation State
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
      await confirmRetailerReceipt(receiptShipment.shipment_id, {
        received_quantity: Number(receivedQty),
        condition_status: conditionStatus,
        discrepancy_units: Number(discrepancyUnits) || 0,
        notes: receiptNotes || undefined,
      });
      setSubmissionSuccess(`Store delivery confirmed for ${receiptShipment.shipment_id}. Shelf inventory credited.`);
      setShowReceiptModal(false);
      setReceiptShipment(null);
      // Refresh relevant data
      fetchShipments();
      fetchInventory();
      fetchDashboard();
    } catch (err: any) {
      setReceiptError(err.message || 'Failed to confirm store delivery receipt.');
    } finally {
      setSubmittingReceipt(false);
    }
  };

  // Handle Order Cancellation
  const handleCancelRequestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cancelTargetShipment) return;
    setCancellingRequest(true);
    setCancelError(null);
    try {
      await cancelRetailerRequest(cancelTargetShipment.shipment_id, {
        reason: cancelReason || undefined,
      });
      setSubmissionSuccess(`Store replenishment order ${cancelTargetShipment.shipment_id} cancelled.`);
      setShowCancelModal(false);
      setCancelTargetShipment(null);
      fetchRequests();
      fetchDashboard();
    } catch (err: any) {
      setCancelError(err.message || 'Failed to cancel store order.');
    } finally {
      setCancellingRequest(false);
    }
  };

  // Fetch Dashboard

  const fetchDashboard = async () => {
    setDashboardLoading(true);
    setDashboardError(null);
    try {
      const data = await getRetailerDashboard();
      setDashboard(data);
    } catch (err: any) {
      setDashboardError(err.message || 'Failed to load retailer dashboard data.');
    } finally {
      setDashboardLoading(false);
    }
  };

  // Fetch Inventory
  const fetchInventory = async () => {
    setInventoryLoading(true);
    try {
      const data = await getRetailerInventory();
      setInventory(data);
    } catch (err: any) {
      console.error('Failed to load retailer inventory', err);
    } finally {
      setInventoryLoading(false);
    }
  };

  // Fetch Requests
  const fetchRequests = async () => {
    setRequestsLoading(true);
    try {
      const data = await getRetailerRequests();
      setRequests(data);
    } catch (err: any) {
      console.error('Failed to load retailer requests', err);
    } finally {
      setRequestsLoading(false);
    }
  };

  // Fetch Shipments
  const fetchShipments = async () => {
    setShipmentsLoading(true);
    try {
      const data = await getRetailerShipments(
        shipmentStatusFilter !== 'all' ? shipmentStatusFilter : undefined
      );
      setShipments(data);
    } catch (err: any) {
      console.error('Failed to load retailer shipments', err);
    } finally {
      setShipmentsLoading(false);
    }
  };

  // Fetch Products for Request Form
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
      setSubmissionError('Requested quantity must be strictly greater than zero.');
      return;
    }
    if (!selectedSku) {
      setSubmissionError('Please select a valid product SKU.');
      return;
    }

    setSubmittingRequest(true);
    try {
      const result = await submitRetailerRequest({
        sku_id: selectedSku,
        quantity: requestQty,
        preferred_source_location_id: preferredSource,
        required_by_date: requiredByDate || undefined,
        reason: requestReason,
        notes: requestNotes,
      });

      setSubmissionSuccess(
        `Order request #${result.shipment_id} successfully created in proposed status. Awaiting distributor/planner review.`
      );
      setRequestNotes('');
      fetchRequests();
      fetchDashboard();
    } catch (err: any) {
      setSubmissionError(err.message || 'Failed to submit replenishment request.');
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
            <div className="p-2 bg-pink-50 text-pink-700 rounded-lg">
              <ShoppingBag className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight">Retail Shop Portal</h1>
              <p className="text-xs text-slate-500">
                Frontline store interface: Store shelf inventory, stock replenishment requests, and incoming consignment tracking.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3 py-1.5 rounded-lg bg-pink-50 border border-pink-200 text-pink-800 text-xs font-medium flex items-center gap-1.5 shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5 text-pink-600" />
            <span>Store Org: <strong>{dashboard?.retailer_org_id || user?.orgId || 'ORG-RETAIL-METRO'}</strong></span>
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
              ? 'border-pink-600 text-pink-700 bg-pink-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <ShoppingBag className="w-4 h-4" />
          Store Dashboard
        </button>

        <button
          onClick={() => setActiveTab('inventory')}
          className={`px-4 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'inventory'
              ? 'border-pink-600 text-pink-700 bg-pink-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Boxes className="w-4 h-4" />
          My Store Inventory
        </button>

        <button
          onClick={() => setActiveTab('requests')}
          className={`px-4 py-2.5 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all ${
            activeTab === 'requests'
              ? 'border-pink-600 text-pink-700 bg-pink-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Send className="w-4 h-4" />
          Replenishment Requests
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
              ? 'border-pink-600 text-pink-700 bg-pink-50/50 rounded-t-md'
              : 'border-transparent text-slate-600 hover:text-slate-900'
          }`}
        >
          <Truck className="w-4 h-4" />
          Store Deliveries & Shipments
          {dashboard?.in_transit_shipments_count ? (
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-blue-100 text-blue-800 font-bold">
              {dashboard.in_transit_shipments_count}
            </span>
          ) : null}
        </button>
      </div>

      {/* TAB 1: STORE DASHBOARD */}
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
                <span className="text-xs font-medium uppercase tracking-wider">Store On-Hand</span>
                <Boxes className="w-4 h-4 text-pink-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">
                {dashboardLoading ? '...' : (dashboard?.total_on_hand_units.toLocaleString() ?? '0')}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                {dashboard?.total_store_skus ?? 0} Distinct SKUs on shelf
              </div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-medium uppercase tracking-wider">Available For Sale</span>
                <Package className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-2xl font-bold text-slate-900">
                {dashboardLoading ? '...' : (dashboard?.total_available_units.toLocaleString() ?? '0')}
              </div>
              <div className="mt-1 text-[11px] text-emerald-600">
                Unreserved shelf availability
              </div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-medium uppercase tracking-wider">Pending Orders</span>
                <Clock className="w-4 h-4 text-amber-600" />
              </div>
              <div className="text-2xl font-bold text-amber-700">
                {dashboardLoading ? '...' : (dashboard?.pending_requests_count ?? 0)}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                {dashboard?.approved_awaiting_fulfilment_count ?? 0} approved awaiting fulfilment
              </div>
            </div>

            <div className="p-4 bg-white rounded-xl border border-slate-200 shadow-2xs">
              <div className="flex items-center justify-between text-slate-500 mb-2">
                <span className="text-xs font-medium uppercase tracking-wider">Incoming Deliveries</span>
                <Truck className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-2xl font-bold text-blue-700">
                {dashboardLoading ? '...' : (dashboard?.in_transit_shipments_count ?? 0)}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">
                Consignments in transit to store
              </div>
            </div>
          </div>

          {/* Low-Stock Warning Callout */}
          {(dashboard?.low_stock_skus_count ?? 0) > 0 && (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
                <div>
                  <h4 className="text-xs font-bold text-amber-900">
                    {dashboard?.low_stock_skus_count} SKUs Below Safety Stock Threshold
                  </h4>
                  <p className="text-[11px] text-amber-700">
                    Items with less than 25 units available on shelf. Submit a replenishment request to avoid store stockout.
                  </p>
                </div>
              </div>
              <button
                onClick={() => setActiveTab('requests')}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded-lg transition-colors"
              >
                Request Restock
              </button>
            </div>
          )}

          {/* Quick Tables: Incoming Deliveries & Recent Replenishment Requests */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Incoming Deliveries */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Truck className="w-4 h-4 text-pink-600" />
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Incoming Deliveries</h3>
                </div>
                <button
                  onClick={() => setActiveTab('shipments')}
                  className="text-xs text-pink-600 hover:text-pink-800 font-medium"
                >
                  View All &rarr;
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                    <tr>
                      <th className="py-2.5 px-3 font-semibold">Delivery ID</th>
                      <th className="py-2.5 px-3 font-semibold">SKU</th>
                      <th className="py-2.5 px-3 font-semibold">Units</th>
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
                          No deliveries recorded.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Recent Store Requests */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
              <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Send className="w-4 h-4 text-amber-600" />
                  <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Recent Store Requests</h3>
                </div>
                <button
                  onClick={() => setActiveTab('requests')}
                  className="text-xs text-pink-600 hover:text-pink-800 font-medium"
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
                      <th className="py-2.5 px-3 font-semibold">Status</th>
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
                          No store requests found.
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

      {/* TAB 2: MY STORE INVENTORY */}
      {activeTab === 'inventory' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="relative w-full sm:w-80">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search store SKU, product or batch..."
                value={invSearchQuery}
                onChange={(e) => setInvSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-pink-500"
              />
            </div>
            <div className="text-xs text-slate-500">
              Showing <strong>{filteredInventory.length}</strong> store inventory records
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="py-3 px-4 font-semibold">SKU & Product</th>
                    <th className="py-3 px-4 font-semibold">Store Location</th>
                    <th className="py-3 px-4 font-semibold">Batch #</th>
                    <th className="py-3 px-4 font-semibold">Expiry Date</th>
                    <th className="py-3 px-4 font-semibold text-right">On Hand</th>
                    <th className="py-3 px-4 font-semibold text-right">Available on Shelf</th>
                    <th className="py-3 px-4 font-semibold">Stock Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {inventoryLoading ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-pink-500" />
                        Loading store inventory...
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
                          <div className="text-[10px] text-slate-400">Retail Outlet</div>
                        </td>
                        <td className="py-3 px-4 font-mono font-medium text-slate-600">
                          {item.batch_number || 'STORE-BATCH-01'}
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
                          {item.dispatchable_stock < 25 ? (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                              Low Stock
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              In Stock
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-slate-400">
                        No retail store inventory records found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 3: REPLENISHMENT REQUESTS */}
      {activeTab === 'requests' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Submission Form */}
          <div className="lg:col-span-1 bg-white rounded-xl border border-slate-200 p-5 shadow-2xs h-fit space-y-4">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Send className="w-4 h-4 text-pink-600" />
              <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                Request Store Replenishment
              </h3>
            </div>

            <div className="p-3 bg-pink-50/60 border border-pink-200 rounded-lg text-[11px] text-pink-900 flex items-start gap-2">
              <Info className="w-4 h-4 text-pink-600 shrink-0 mt-0.5" />
              <span>
                Submission creates a <strong>proposed shipment</strong>. It does not automatically allocate stock from distributors or dispatch goods until approved.
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
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-pink-500"
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
                  Requested Units <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  value={requestQty}
                  onChange={(e) => setRequestQty(parseInt(e.target.value) || 0)}
                  required
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-pink-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Preferred Source Hub</label>
                <input
                  type="text"
                  value={preferredSource}
                  onChange={(e) => setPreferredSource(e.target.value)}
                  placeholder="e.g. LOC-DIST-WEST"
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-pink-500 font-mono text-[11px]"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Required-By Delivery Date</label>
                <input
                  type="date"
                  value={requiredByDate}
                  onChange={(e) => setRequiredByDate(e.target.value)}
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-pink-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Store Requirement Reason</label>
                <input
                  type="text"
                  value={requestReason}
                  onChange={(e) => setRequestReason(e.target.value)}
                  placeholder="e.g. Weekend traffic surge, stockout prevention..."
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-pink-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Optional Notes</label>
                <textarea
                  rows={2}
                  value={requestNotes}
                  onChange={(e) => setRequestNotes(e.target.value)}
                  placeholder="Dock timing, store manager contact..."
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-pink-500"
                />
              </div>

              <button
                type="submit"
                disabled={submittingRequest}
                className="w-full py-2 px-4 bg-pink-600 hover:bg-pink-700 disabled:bg-slate-300 text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-2 transition-colors shadow-2xs"
              >
                {submittingRequest ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Send className="w-3.5 h-3.5" />
                )}
                <span>Submit Store Order Request</span>
              </button>
            </form>
          </div>

          {/* List of Requests */}
          <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-500" />
                <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Store Order History & Status
                </h3>
              </div>
              <button
                onClick={fetchRequests}
                className="text-xs text-pink-600 hover:text-pink-800 font-medium flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" />
                Refresh
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Order ID</th>
                    <th className="py-2.5 px-3 font-semibold">SKU</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Units</th>
                    <th className="py-2.5 px-3 font-semibold">Status</th>
                    <th className="py-2.5 px-3 font-semibold">Approval Notes</th>
                    <th className="py-2.5 px-3 font-semibold text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {requestsLoading ? (
                    <tr>
                      <td colSpan={6} className="py-8 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-pink-500" />
                        Loading orders...
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
                      <td colSpan={6} className="py-8 text-center text-slate-400">
                        No replenishment requests submitted yet. Use the restock form on the left.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: STORE DELIVERIES & SHIPMENT TRACKING */}
      {activeTab === 'shipments' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-600">Filter Status:</span>
              <select
                value={shipmentStatusFilter}
                onChange={(e) => setShipmentStatusFilter(e.target.value)}
                className="text-xs bg-white border border-slate-200 rounded-lg p-1.5 focus:ring-1 focus:ring-pink-500"
              >
                <option value="all">All Deliveries</option>
                <option value="in_transit">In Transit</option>
                <option value="delivered">Delivered</option>
                <option value="ready_for_dispatch">Ready for Dispatch</option>
                <option value="approved">Approved</option>
                <option value="proposed">Proposed</option>
              </select>
            </div>

            <div className="text-xs text-slate-500">
              Showing <strong>{shipments.length}</strong> store deliveries
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 border-b border-slate-100">
                  <tr>
                    <th className="py-3 px-4 font-semibold">Delivery ID</th>
                    <th className="py-3 px-4 font-semibold">Source Hub &rarr; Store</th>
                    <th className="py-3 px-4 font-semibold">Product SKU</th>
                    <th className="py-3 px-4 font-semibold text-right">Units</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                    <th className="py-3 px-4 font-semibold">Carrier / Vehicle</th>
                    <th className="py-3 px-4 font-semibold">Dispatch / Delivery Date</th>
                    <th className="py-3 px-4 font-semibold text-center">Receipt Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {shipmentsLoading ? (
                    <tr>
                      <td colSpan={8} className="py-8 text-center text-slate-400">
                        <RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2 text-pink-500" />
                        Loading deliveries...
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
                        No deliveries found matching the filter.
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
                  Confirm Store Delivery Receipt & Discrepancies
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
                  <span className="text-slate-500">Delivery ID:</span>
                  <span className="font-mono font-bold text-slate-800">{receiptShipment.shipment_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Product SKU:</span>
                  <span className="font-medium text-slate-800">{receiptShipment.sku_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Shipped Quantity:</span>
                  <span className="font-bold text-slate-900">{receiptShipment.quantity.toLocaleString()} units</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Receiving Store:</span>
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
                  <option value="intact">Intact / Full Store Delivery</option>
                  <option value="shortage">Shortage / Missing Cases</option>
                  <option value="damaged">Damaged Goods / Broken Seals</option>
                  <option value="excess">Excess Quantity Received</option>
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
                  Store Notes & Discrepancy Remarks
                </label>
                <textarea
                  rows={2}
                  value={receiptNotes}
                  onChange={(e) => setReceiptNotes(e.target.value)}
                  placeholder="Notes on shelf readiness, carton damage, driver remarks..."
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
                  <span>Confirm Receipt & Credit Store Stock</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ORDER CANCELLATION MODAL */}
      {showCancelModal && cancelTargetShipment && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full overflow-hidden animate-in fade-in zoom-in duration-150">
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600" />
                <h3 className="text-sm font-bold text-slate-900">Cancel Store Replenishment Order</h3>
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
                Are you sure you want to cancel order{' '}
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
                  placeholder="e.g. Overstock, order placed in error..."
                  className="w-full text-xs bg-white border border-slate-200 rounded-lg p-2 focus:ring-1 focus:ring-red-500"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCancelModal(false)}
                  className="px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Keep Order
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


export default RetailerPortalPage;
