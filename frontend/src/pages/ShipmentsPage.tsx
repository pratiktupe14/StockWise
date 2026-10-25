import React, { useState, useEffect } from 'react';
import {
  Truck,
  CheckCircle2,
  Clock,
  AlertTriangle,
  Plus,
  RefreshCw,
  Search,
  Filter,
  ArrowRight,
  History,
  FileCheck2,
  PackageCheck,
  ClipboardList,
  Building2,
  X,
  FileText,
  BadgeAlert,
  Send,
  Check,
  ShieldCheck,
} from 'lucide-react';
import {
  getShipments,
  proposeShipment,
  approveShipment,
  getStockMovements,
  getProducts,
  getNetworkLocations,
  getNetworkRoutes,
  getInventory,
  getOrganizations,
  prepareShipmentDispatch,
  confirmShipmentDispatch,
  confirmShipmentDelivery,
  assignShipmentCarrier,
  recordCarrierDecision,
  recordShipmentException,
  cancelShipmentExecution,
  getShipmentTraceability,
} from '../services/api';
import type {
  ShipmentItem,
  StockMovementItem,
  ProductItem,
  LocationItem,
  RouteItem,
  InventoryItem,
  OrganizationItem,
  ShipmentTraceabilityItem,
} from '../types/api';

export const ShipmentsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'shipments' | 'propose' | 'approvals' | 'movements'>('shipments');

  // Master & operational data
  const [shipments, setShipments] = useState<ShipmentItem[]>([]);
  const [movements, setMovements] = useState<StockMovementItem[]>([]);
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [routes, setRoutes] = useState<RouteItem[]>([]);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [organizations, setOrganizations] = useState<OrganizationItem[]>([]);

  // Filter & UI states
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Proposal Form State
  const [proposal, setProposal] = useState({
    sku_id: '',
    source_location_id: '',
    destination_location_id: '',
    quantity: 100,
    notes: '',
  });

  // Modal 1: Governance Approval
  const [approvalModalShipment, setApprovalModalShipment] = useState<ShipmentItem | null>(null);
  const [approvalDecision, setApprovalDecision] = useState({
    approved: true,
    authorized_user_id: 'DIST-PLANNER-01',
    notes: '',
  });

  // Modal 2: Dispatch Preparation & Checklist
  const [prepareModalShipment, setPrepareModalShipment] = useState<ShipmentItem | null>(null);
  const [prepChecklist, setPrepChecklist] = useState({
    packaging_inspected: true,
    quantity_reconciled: true,
    dock_assigned: true,
    batch_verified: true,
  });
  const [prepUserId, setPrepUserId] = useState('WH-SUPERVISOR-01');
  const [prepNotes, setPrepNotes] = useState('Palletized at Dock Bay 4. Manifest verified.');

  // Modal 3: Carrier Coordination & Assignment
  const [carrierModalShipment, setCarrierModalShipment] = useState<ShipmentItem | null>(null);
  const [carrierForm, setCarrierForm] = useState({
    carrier_agency_id: '',
    carrier_contact: '',
    planned_pickup_date: '',
    estimated_arrival_date: '',
    consignment_number: '',
    vehicle_number: '',
    driver_contact: '',
    accepted: true,
    authorized_user_id: 'LOG-COORD-01',
    notes: '',
  });

  // Modal 4: Physical Dispatch Confirmation (Gate-Out)
  const [dispatchModalShipment, setDispatchModalShipment] = useState<ShipmentItem | null>(null);
  const [dispatchForm, setDispatchForm] = useState({
    authorized_user_id: 'WH-DISPATCH-MGR',
    consignment_number: '',
    vehicle_number: '',
    driver_contact: '',
    notes: 'Gate pass verified. Truck sealed.',
  });

  // Modal 5: Delivery Confirmation (Gate-In)
  const [deliveryModalShipment, setDeliveryModalShipment] = useState<ShipmentItem | null>(null);
  const [deliveryForm, setDeliveryForm] = useState({
    authorized_user_id: 'RECEIVING-OFFICER-01',
    actual_transport_cost: 0,
    pod_reference: '',
    notes: 'Goods received intact. Seals matched manifest.',
  });

  // Modal 6: Operational Exception & Delays
  const [exceptionModalShipment, setExceptionModalShipment] = useState<ShipmentItem | null>(null);
  const [exceptionForm, setExceptionForm] = useState({
    authorized_user_id: 'LOG-OPS-01',
    exception_reason: 'Monsoon waterlogging on expressway',
    notes: 'Traffic stalled near ghat section. Revised ETA +18 hours.',
  });

  // Drawer / Modal 7: Traceability & Audit Events
  const [traceabilityData, setTraceabilityData] = useState<ShipmentTraceabilityItem | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [shps, movs, prods, locs, rts, inv, orgs] = await Promise.all([
        getShipments(),
        getStockMovements(),
        getProducts(),
        getNetworkLocations(),
        getNetworkRoutes(true),
        getInventory(),
        getOrganizations(),
      ]);
      setShipments(shps);
      setMovements(movs);
      setProducts(prods);
      setLocations(locs);
      setRoutes(rts);
      setInventory(inv);
      setOrganizations(orgs);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch shipment records');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Compute live dispatchable stock at selected source for selected SKU
  const selectedSourceStock = inventory
    .filter((i) => i.sku_id === proposal.sku_id && i.location_id === proposal.source_location_id)
    .reduce((sum, item) => sum + item.dispatchable_stock, 0);

  // Verify if route exists between selected source and destination
  const isPermittedRoute = routes.some(
    (r) =>
      r.is_active !== false &&
      (r.from_location_id === proposal.source_location_id || r.source_location_id === proposal.source_location_id) &&
      (r.to_location_id === proposal.destination_location_id || r.destination_location_id === proposal.destination_location_id)
  );

  const carrierAgencies = organizations.filter(
    (o) => o.org_type === 'logistics_provider' || o.org_type === 'cnf_agency'
  );

  // Handler: Propose Shipment
  const handleProposeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!proposal.sku_id || !proposal.source_location_id || !proposal.destination_location_id) {
      setError('Please select SKU, Source, and Destination facilities.');
      return;
    }
    if (proposal.source_location_id === proposal.destination_location_id) {
      setError('Source and Destination locations must be different.');
      return;
    }
    if (!isPermittedRoute) {
      setError('Forbidden corridor: No permitted route exists between selected facilities.');
      return;
    }
    if (proposal.quantity > selectedSourceStock) {
      setError(`Requested ${proposal.quantity} cases exceeds source uncommitted dispatchable stock (${selectedSourceStock.toFixed(1)}).`);
      return;
    }

    setActionLoading(true);
    setError(null);
    try {
      const newShp = await proposeShipment(proposal);
      setSuccessMsg(`Shipment ${newShp.shipment_id} proposed successfully. Pending governance approval.`);
      setActiveTab('shipments');
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to propose shipment');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Governance Approval
  const handleApprovalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!approvalModalShipment) return;

    setActionLoading(true);
    setError(null);
    try {
      await approveShipment(
        approvalModalShipment.shipment_id,
        approvalDecision.approved,
        approvalDecision.authorized_user_id,
        approvalDecision.notes
      );
      setSuccessMsg(`Shipment ${approvalModalShipment.shipment_id} decision recorded (${approvalDecision.approved ? 'Approved' : 'Rejected'}).`);
      setApprovalModalShipment(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Approval failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Prepare Dispatch
  const handlePrepareSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prepareModalShipment) return;

    const checkedItems = Object.entries(prepChecklist)
      .filter(([, checked]) => checked)
      .map(([key]) => key);

    setActionLoading(true);
    setError(null);
    try {
      await prepareShipmentDispatch(prepareModalShipment.shipment_id, {
        authorized_user_id: prepUserId,
        actor_role: 'warehouse_supervisor',
        checklist_items: checkedItems,
        notes: prepNotes,
      });
      setSuccessMsg(`Shipment ${prepareModalShipment.shipment_id} is Ready for Dispatch. Stock reserved on-hand.`);
      setPrepareModalShipment(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Dispatch preparation failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Carrier Assignment & Decision
  const handleCarrierSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!carrierModalShipment) return;

    setActionLoading(true);
    setError(null);
    try {
      if (carrierForm.carrier_agency_id) {
        await assignShipmentCarrier(carrierModalShipment.shipment_id, {
          carrier_agency_id: carrierForm.carrier_agency_id,
          carrier_contact: carrierForm.carrier_contact || undefined,
          planned_pickup_date: carrierForm.planned_pickup_date ? new Date(carrierForm.planned_pickup_date).toISOString() : undefined,
          estimated_arrival_date: carrierForm.estimated_arrival_date ? new Date(carrierForm.estimated_arrival_date).toISOString() : undefined,
          authorized_user_id: carrierForm.authorized_user_id,
          notes: carrierForm.notes,
        });
      }

      if (carrierForm.consignment_number || carrierForm.vehicle_number || carrierForm.driver_contact) {
        await recordCarrierDecision(carrierModalShipment.shipment_id, {
          accepted: carrierForm.accepted,
          authorized_user_id: carrierForm.authorized_user_id,
          consignment_number: carrierForm.consignment_number || undefined,
          vehicle_number: carrierForm.vehicle_number || undefined,
          driver_contact: carrierForm.driver_contact || undefined,
          notes: carrierForm.notes,
        });
      }

      setSuccessMsg(`Carrier details & consignment updated for ${carrierModalShipment.shipment_id}.`);
      setCarrierModalShipment(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Carrier coordination failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Physical Dispatch (Gate-Out)
  const handleDispatchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dispatchModalShipment) return;

    setActionLoading(true);
    setError(null);
    try {
      await confirmShipmentDispatch(dispatchModalShipment.shipment_id, {
        authorized_user_id: dispatchForm.authorized_user_id,
        consignment_number: dispatchForm.consignment_number || undefined,
        vehicle_number: dispatchForm.vehicle_number || undefined,
        driver_contact: dispatchForm.driver_contact || undefined,
        notes: dispatchForm.notes,
      });
      setSuccessMsg(`Shipment ${dispatchModalShipment.shipment_id} confirmed In Transit. Physical stock consumed from warehouse.`);
      setDispatchModalShipment(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Dispatch confirmation failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Delivery Confirmation (Gate-In)
  const handleDeliverySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deliveryModalShipment) return;

    setActionLoading(true);
    setError(null);
    try {
      await confirmShipmentDelivery(deliveryModalShipment.shipment_id, {
        authorized_user_id: deliveryForm.authorized_user_id,
        actual_transport_cost: Number(deliveryForm.actual_transport_cost) || undefined,
        pod_reference: deliveryForm.pod_reference || undefined,
        notes: deliveryForm.notes,
      });
      setSuccessMsg(`Shipment ${deliveryModalShipment.shipment_id} Delivered. Stock credited at destination facility.`);
      setDeliveryModalShipment(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Delivery confirmation failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Record Exception
  const handleExceptionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!exceptionModalShipment) return;

    setActionLoading(true);
    setError(null);
    try {
      await recordShipmentException(exceptionModalShipment.shipment_id, {
        authorized_user_id: exceptionForm.authorized_user_id,
        exception_reason: exceptionForm.exception_reason,
        notes: exceptionForm.notes,
      });
      setSuccessMsg(`Operational exception recorded for ${exceptionModalShipment.shipment_id}.`);
      setExceptionModalShipment(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Exception logging failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Cancel Shipment
  const handleCancelShipment = async (shp: ShipmentItem) => {
    if (!window.confirm(`Are you sure you want to cancel shipment ${shp.shipment_id}? Any reserved stock will be rolled back.`)) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await cancelShipmentExecution(shp.shipment_id, 'LOG-OPS-ADMIN', 'Cancelled before dispatch by user request');
      setSuccessMsg(`Shipment ${shp.shipment_id} cancelled. Reserved stock rolled back.`);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Cancellation failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Handler: Load Traceability Drawer
  const handleOpenTraceability = async (shipmentId: string) => {
    setError(null);
    try {
      const data = await getShipmentTraceability(shipmentId);
      setTraceabilityData(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load traceability details');
    }
  };

  // Filtered shipments
  const filteredShipments = shipments.filter((shp) => {
    const matchesSearch =
      shp.shipment_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      shp.sku_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (shp.product_name && shp.product_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (shp.source_location_name && shp.source_location_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (shp.destination_location_name && shp.destination_location_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (shp.consignment_number && shp.consignment_number.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (shp.vehicle_number && shp.vehicle_number.toLowerCase().includes(searchTerm.toLowerCase()));

    if (!matchesSearch) return false;

    if (statusFilter === 'all') return true;
    if (statusFilter === 'exceptions') return Boolean(shp.exception_reason);
    return shp.status === statusFilter;
  });

  const pendingApprovals = shipments.filter((s) => s.approval_status === 'pending');
  const readyForDispatchCount = shipments.filter((s) => s.status === 'ready_for_dispatch').length;
  const inTransitCount = shipments.filter((s) => s.status === 'in_transit').length;
  const deliveredCount = shipments.filter((s) => s.status === 'delivered').length;

  return (
    <div className="space-y-6">
      {/* Top Header & Metrics Banner */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-200 pb-5">
        <div>
          <h1 className="text-xl font-bold text-slate-900 flex items-center gap-2">
            <Truck className="w-5 h-5 text-blue-600" />
            Shipment Execution & Logistics Operations
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Phase 4: Warehouse dispatch preparation, 3PL carrier coordination, and auditable delivery confirmation (INR / cases).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-xs text-slate-600 hover:bg-slate-50 transition-colors shadow-2xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-600' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Pipeline Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-amber-500" />
            Pending Approval
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{pendingApprovals.length}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Awaiting planner authorization</div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <PackageCheck className="w-3.5 h-3.5 text-indigo-500" />
            Ready for Dispatch
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{readyForDispatchCount}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Palletized & stock reserved</div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <Truck className="w-3.5 h-3.5 text-blue-600" />
            In Transit
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{inTransitCount}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">On road with waybill/bilty</div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Delivered
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">{deliveredCount}</div>
          <div className="text-[10px] text-slate-400 mt-0.5">Confirmed at destination</div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
          <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
            <BadgeAlert className="w-3.5 h-3.5 text-rose-500" />
            Exceptions / Delays
          </div>
          <div className="text-xl font-bold text-slate-900 mt-1">
            {shipments.filter((s) => s.exception_reason).length}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Weather, dock or truck delays</div>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-slate-200">
        <div className="flex gap-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('shipments')}
            className={`pb-3 relative cursor-pointer ${
              activeTab === 'shipments'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Truck className="w-4 h-4" />
              Shipment Operations ({shipments.length})
            </span>
          </button>
          <button
            onClick={() => setActiveTab('propose')}
            className={`pb-3 relative cursor-pointer ${
              activeTab === 'propose'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Plus className="w-4 h-4" />
              Propose Shipment
            </span>
          </button>
          <button
            onClick={() => setActiveTab('approvals')}
            className={`pb-3 relative cursor-pointer ${
              activeTab === 'approvals'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <FileCheck2 className="w-4 h-4" />
              Pending Governance
              {pendingApprovals.length > 0 && (
                <span className="bg-amber-100 text-amber-800 text-[10px] px-1.5 py-0.2 rounded-full font-bold">
                  {pendingApprovals.length}
                </span>
              )}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('movements')}
            className={`pb-3 relative cursor-pointer ${
              activeTab === 'movements'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <History className="w-4 h-4" />
              Movement Audit Log ({movements.length})
            </span>
          </button>
        </div>
      </div>

      {/* Notifications */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2 shadow-2xs">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <div className="flex-1">
            <p className="font-semibold">Operation Error</p>
            <p>{error}</p>
          </div>
          <button onClick={() => setError(null)} className="text-red-700 font-bold hover:underline">
            ✕
          </button>
        </div>
      )}
      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-start gap-2 shadow-2xs">
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600" />
          <div className="flex-1 flex justify-between items-center">
            <span>{successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} className="text-emerald-700 hover:underline font-medium">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* TAB 1: SHIPMENT OPERATIONS */}
      {activeTab === 'shipments' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-64">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search by ID, SKU, location, vehicle..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-blue-600 shadow-2xs"
                />
              </div>

              {/* Status Pill Filters */}
              <div className="flex items-center gap-1.5 overflow-x-auto py-1">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                {[
                  { id: 'all', label: 'All' },
                  { id: 'proposed', label: 'Proposed' },
                  { id: 'approved', label: 'Approved' },
                  { id: 'ready_for_dispatch', label: 'Ready' },
                  { id: 'in_transit', label: 'In Transit' },
                  { id: 'delivered', label: 'Delivered' },
                  { id: 'exceptions', label: 'Exceptions' },
                  { id: 'cancelled', label: 'Cancelled' },
                ].map((pill) => (
                  <button
                    key={pill.id}
                    onClick={() => setStatusFilter(pill.id)}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer ${
                      statusFilter === pill.id
                        ? 'bg-blue-600 text-white font-semibold'
                        : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {pill.label}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={() => setActiveTab('propose')}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-2xs cursor-pointer whitespace-nowrap"
            >
              <Plus className="w-4 h-4" />
              Propose Shipment
            </button>
          </div>

          {/* Shipments Master Execution Table */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="bg-slate-50/80 border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
                    <th className="px-4 py-3">Shipment ID</th>
                    <th className="px-4 py-3">Product / SKU</th>
                    <th className="px-4 py-3">Qty (Cases)</th>
                    <th className="px-4 py-3">Distribution Corridor</th>
                    <th className="px-4 py-3">Carrier / Vehicle</th>
                    <th className="px-4 py-3">Freight Cost (INR)</th>
                    <th className="px-4 py-3">Lifecycle Stage</th>
                    <th className="px-4 py-3 text-right">Operational Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {filteredShipments.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="text-center py-12 text-slate-500">
                        <Truck className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                        <div className="text-sm font-semibold text-slate-700">
                          {shipments.length === 0 ? 'No shipments created yet' : 'No matching shipments found'}
                        </div>
                        <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
                          {shipments.length === 0
                            ? 'There are currently no shipments in the ledger. Propose a new shipment or execute an optimization run.'
                            : `No shipments match the filter "${statusFilter}" or search term.`}
                        </p>
                        {shipments.length === 0 && (
                          <button
                            onClick={() => setActiveTab('propose')}
                            className="inline-flex items-center gap-1.5 mt-3 text-xs font-semibold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-1.5 rounded-lg transition cursor-pointer"
                          >
                            <Plus className="w-3.5 h-3.5" />
                            Propose First Shipment
                          </button>
                        )}
                      </td>
                    </tr>
                  ) : (
                    filteredShipments.map((shp) => (
                    <tr key={shp.shipment_id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-4 py-3 font-mono font-bold text-slate-900">
                        <div className="flex items-center gap-1.5">
                          <span>{shp.shipment_id}</span>
                          {shp.planning_run_id && (
                            <span className="px-1.5 py-0.2 rounded-xs bg-purple-50 text-purple-700 border border-purple-200 text-[9px] font-bold" title="Optimized Plan Lineage">
                              OPTIMIZED
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-400 font-normal mt-0.5">
                          {new Date(shp.created_at).toLocaleDateString()}
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-800">{shp.product_name || shp.sku_id}</div>
                        <div className="text-[10px] text-slate-400 font-mono">{shp.sku_id}</div>
                      </td>

                      <td className="px-4 py-3 font-mono font-bold text-slate-900">
                        {shp.quantity.toLocaleString()} cases
                      </td>

                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 text-slate-700">
                          <span className="font-medium text-slate-900">{shp.source_location_name || shp.source_location_id}</span>
                          <ArrowRight className="w-3 h-3 text-slate-400 shrink-0" />
                          <span className="font-medium text-slate-900">{shp.destination_location_name || shp.destination_location_id}</span>
                        </div>
                        {shp.lead_time_days && (
                          <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            Lead time: {shp.lead_time_days} days
                          </div>
                        )}
                      </td>

                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-800 flex items-center gap-1">
                          <Building2 className="w-3 h-3 text-slate-400" />
                          {shp.carrier_agency_name || 'Direct Transfer'}
                        </div>
                        {shp.consignment_number ? (
                          <div className="text-[10px] font-mono text-blue-600 mt-0.5">
                            CN: {shp.consignment_number} {shp.vehicle_number && `• ${shp.vehicle_number}`}
                          </div>
                        ) : (
                          <div className="text-[10px] text-slate-400 mt-0.5">No consignment logged</div>
                        )}
                      </td>

                      <td className="px-4 py-3 font-mono text-slate-900">
                        <div className="font-semibold">
                          ₹{shp.actual_transport_cost !== null && shp.actual_transport_cost !== undefined
                            ? shp.actual_transport_cost.toFixed(2)
                            : shp.estimated_transport_cost.toFixed(2)}
                        </div>
                        <div className="text-[9px] text-slate-400">
                          {shp.actual_transport_cost !== null && shp.actual_transport_cost !== undefined ? 'Actual Freight' : 'Estimated Freight'}
                        </div>
                      </td>

                      <td className="px-4 py-3">
                        {/* Status Badge */}
                        <div className="flex flex-col gap-1 items-start">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                              shp.status === 'delivered'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : shp.status === 'in_transit'
                                ? 'bg-blue-50 text-blue-700 border-blue-200'
                                : shp.status === 'ready_for_dispatch'
                                ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                                : shp.status === 'approved'
                                ? 'bg-teal-50 text-teal-700 border-teal-200'
                                : shp.status === 'rejected' || shp.status === 'cancelled'
                                ? 'bg-rose-50 text-rose-700 border-rose-200'
                                : 'bg-amber-50 text-amber-700 border-amber-200'
                            }`}
                          >
                            {shp.status === 'delivered' && <CheckCircle2 className="w-3 h-3 text-emerald-600" />}
                            {shp.status === 'in_transit' && <Truck className="w-3 h-3 text-blue-600" />}
                            {shp.status === 'ready_for_dispatch' && <PackageCheck className="w-3 h-3 text-indigo-600" />}
                            {shp.status === 'approved' && <ShieldCheck className="w-3 h-3 text-teal-600" />}
                            {shp.status.replace(/_/g, ' ').toUpperCase()}
                          </span>

                          {shp.exception_reason && (
                            <span className="inline-flex items-center gap-1 text-[9px] text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded-xs border border-amber-200" title={shp.exception_notes || ''}>
                              <AlertTriangle className="w-2.5 h-2.5 text-amber-600" />
                              Delayed: {shp.exception_reason.slice(0, 24)}...
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Operational Action Buttons */}
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5 flex-wrap">
                          {/* 1. Governance Review for Proposed */}
                          {shp.status === 'proposed' && shp.approval_status === 'pending' && (
                            <button
                              onClick={() => {
                                setApprovalModalShipment(shp);
                              }}
                              className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 hover:bg-blue-100 font-medium text-[11px] cursor-pointer"
                            >
                              Review
                            </button>
                          )}

                          {/* 2. Dispatch Preparation for Approved */}
                          {shp.status === 'approved' && (
                            <button
                              onClick={() => {
                                setPrepareModalShipment(shp);
                              }}
                              className="px-2 py-1 rounded-md bg-indigo-50 text-indigo-700 hover:bg-indigo-100 font-medium text-[11px] flex items-center gap-1 cursor-pointer"
                            >
                              <ClipboardList className="w-3 h-3" />
                              Prepare Dispatch
                            </button>
                          )}

                          {/* 3. Physical Dispatch for Ready For Dispatch */}
                          {shp.status === 'ready_for_dispatch' && (
                            <button
                              onClick={() => {
                                setDispatchModalShipment(shp);
                                setDispatchForm({
                                  ...dispatchForm,
                                  consignment_number: shp.consignment_number || '',
                                  vehicle_number: shp.vehicle_number || '',
                                  driver_contact: shp.driver_contact || '',
                                });
                              }}
                              className="px-2 py-1 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 font-medium text-[11px] flex items-center gap-1 cursor-pointer shadow-2xs"
                            >
                              <Send className="w-3 h-3" />
                              Gate-Out (Dispatch)
                            </button>
                          )}

                          {/* 4. Delivery Confirmation for In Transit */}
                          {shp.status === 'in_transit' && (
                            <button
                              onClick={() => {
                                setDeliveryModalShipment(shp);
                                setDeliveryForm({
                                  ...deliveryForm,
                                  actual_transport_cost: shp.estimated_transport_cost,
                                  pod_reference: shp.pod_reference || '',
                                });
                              }}
                              className="px-2 py-1 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 font-medium text-[11px] flex items-center gap-1 cursor-pointer shadow-2xs"
                            >
                              <Check className="w-3 h-3" />
                              Confirm Delivery
                            </button>
                          )}

                          {/* 5. Carrier Coordination button (if approved or ready) */}
                          {(shp.status === 'approved' || shp.status === 'ready_for_dispatch') && (
                            <button
                              onClick={() => {
                                setCarrierModalShipment(shp);
                                setCarrierForm({
                                  ...carrierForm,
                                  carrier_agency_id: shp.carrier_agency_id || '',
                                  carrier_contact: shp.carrier_contact || '',
                                  consignment_number: shp.consignment_number || '',
                                  vehicle_number: shp.vehicle_number || '',
                                  driver_contact: shp.driver_contact || '',
                                });
                              }}
                              className="px-2 py-1 rounded-md bg-slate-100 text-slate-700 hover:bg-slate-200 font-medium text-[11px] flex items-center gap-1 cursor-pointer"
                              title="Carrier & Waybill Details"
                            >
                              <Truck className="w-3 h-3 text-slate-500" />
                              Carrier
                            </button>
                          )}

                          {/* 6. Exception Logger for In-Transit or Ready */}
                          {(shp.status === 'in_transit' || shp.status === 'ready_for_dispatch') && (
                            <button
                              onClick={() => setExceptionModalShipment(shp)}
                              className="px-1.5 py-1 rounded-md text-amber-700 hover:bg-amber-50 text-[11px] cursor-pointer"
                              title="Log Exception or Delay"
                            >
                              <AlertTriangle className="w-3 h-3" />
                            </button>
                          )}

                          {/* 7. Traceability Drawer Trigger */}
                          <button
                            onClick={() => handleOpenTraceability(shp.shipment_id)}
                            className="px-2 py-1 rounded-md bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200 font-medium text-[11px] flex items-center gap-1 cursor-pointer"
                            title="Traceability and Event Timeline"
                          >
                            <FileText className="w-3 h-3 text-blue-600" />
                            Trace
                          </button>

                          {/* 8. Cancel button (if pre-dispatch) */}
                          {(shp.status === 'proposed' || shp.status === 'approved' || shp.status === 'ready_for_dispatch') && (
                            <button
                              onClick={() => handleCancelShipment(shp)}
                              className="px-1.5 py-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md text-[11px] cursor-pointer"
                              title="Cancel Shipment"
                            >
                              <X className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: PROPOSE SHIPMENT FORM */}
      {activeTab === 'propose' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 max-w-2xl shadow-2xs">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center">
              <Plus className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Propose Stock Allocation Shipment</h3>
              <p className="text-xs text-slate-500">
                Strict FMCG Guardrail: Route must be permitted and source must possess sufficient dispatchable stock.
              </p>
            </div>
          </div>

          <form onSubmit={handleProposeSubmit} className="space-y-4 text-xs">
            <div>
              <label className="block font-semibold text-slate-700 mb-1">Product SKU</label>
              <select
                required
                value={proposal.sku_id}
                onChange={(e) => setProposal({ ...proposal, sku_id: e.target.value })}
                className="w-full p-2.5 border border-slate-200 rounded-lg text-xs focus:outline-blue-600 bg-white"
              >
                <option value="">-- Select Product --</option>
                {products.map((p) => (
                  <option key={p.sku_id} value={p.sku_id}>
                    {p.name} ({p.sku_id}) - Category: {p.category}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Source Facility</label>
                <select
                  required
                  value={proposal.source_location_id}
                  onChange={(e) => setProposal({ ...proposal, source_location_id: e.target.value })}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-xs focus:outline-blue-600 bg-white"
                >
                  <option value="">-- Select Dispatch Source --</option>
                  {locations.map((l) => (
                    <option key={l.location_id} value={l.location_id}>
                      {l.name} ({l.location_type.replace('_', ' ')})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Destination Facility</label>
                <select
                  required
                  value={proposal.destination_location_id}
                  onChange={(e) => setProposal({ ...proposal, destination_location_id: e.target.value })}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-xs focus:outline-blue-600 bg-white"
                >
                  <option value="">-- Select Destination --</option>
                  {locations.map((l) => (
                    <option key={l.location_id} value={l.location_id}>
                      {l.name} ({l.location_type.replace('_', ' ')})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Live Constraints Feedback */}
            {proposal.source_location_id && proposal.destination_location_id && (
              <div
                className={`p-3 rounded-lg border text-xs flex items-start gap-2 ${
                  isPermittedRoute
                    ? 'bg-emerald-50/70 border-emerald-200 text-emerald-800'
                    : 'bg-red-50 border-red-200 text-red-800'
                }`}
              >
                {isPermittedRoute ? (
                  <>
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold">Permitted Transport Corridor</p>
                      <p className="text-[11px] text-emerald-700">
                        Active route exists. Dispatchable stock at source: <strong>{selectedSourceStock.toLocaleString()} cases</strong>.
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold">Forbidden Corridor</p>
                      <p className="text-[11px] text-red-700">
                        No active permitted transport route is registered between these facilities.
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Quantity (Cases)</label>
              <input
                type="number"
                min="1"
                required
                value={proposal.quantity}
                onChange={(e) => setProposal({ ...proposal, quantity: Number(e.target.value) })}
                className="w-full p-2.5 border border-slate-200 rounded-lg text-xs focus:outline-blue-600 font-mono"
              />
            </div>

            <div>
              <label className="block font-semibold text-slate-700 mb-1">Planning Justification Notes</label>
              <textarea
                rows={2}
                placeholder="e.g. Pune depot replenishment for high weekend supermarket sales"
                value={proposal.notes}
                onChange={(e) => setProposal({ ...proposal, notes: e.target.value })}
                className="w-full p-2.5 border border-slate-200 rounded-lg text-xs focus:outline-blue-600"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setActiveTab('shipments')}
                className="px-4 py-2 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading || !isPermittedRoute}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-lg font-semibold shadow-2xs cursor-pointer"
              >
                {actionLoading ? 'Proposing...' : 'Propose Allocation'}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* TAB 3: PENDING APPROVALS */}
      {activeTab === 'approvals' && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
          <div className="p-4 border-b border-slate-200 bg-slate-50/50 flex justify-between items-center">
            <div>
              <h3 className="font-bold text-slate-900 text-sm">Governance Approvals Queue</h3>
              <p className="text-xs text-slate-500">
                Approvals record a formal governance authorization. Physical dispatch requires explicit warehouse recording.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase text-[10px]">
                  <th className="px-4 py-3">Shipment</th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Quantity</th>
                  <th className="px-4 py-3">Route Corridor</th>
                  <th className="px-4 py-3">Estimated Freight</th>
                  <th className="px-4 py-3 text-right">Decision</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {pendingApprovals.map((shp) => (
                  <tr key={shp.shipment_id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">{shp.shipment_id}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{shp.product_name || shp.sku_id}</td>
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">{shp.quantity} cases</td>
                    <td className="px-4 py-3 text-slate-700">
                      {shp.source_location_name} → {shp.destination_location_name}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-800 font-semibold">
                      ₹{shp.estimated_transport_cost.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setApprovalModalShipment(shp)}
                        className="px-3 py-1 bg-blue-600 text-white rounded-md font-semibold text-xs hover:bg-blue-700 cursor-pointer shadow-2xs"
                      >
                        Authorize
                      </button>
                    </td>
                  </tr>
                ))}

                {pendingApprovals.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-slate-400">
                      No pending shipment approvals in the queue.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: STOCK MOVEMENT AUDIT LOG */}
      {activeTab === 'movements' && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
          <div className="p-4 border-b border-slate-200 bg-slate-50/50">
            <h3 className="font-bold text-slate-900 text-sm">Stock Movement & Physical Flow Audit Trail</h3>
            <p className="text-xs text-slate-500">
              Immutable ledger of proposed dispatches, warehouse reservations, actual gate-out pickups, and destination receipts.
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase text-[10px]">
                  <th className="px-4 py-3">Movement ID</th>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Shipment Ref</th>
                  <th className="px-4 py-3">Product</th>
                  <th className="px-4 py-3">Corridor</th>
                  <th className="px-4 py-3">Quantity</th>
                  <th className="px-4 py-3">Movement Type</th>
                  <th className="px-4 py-3">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {movements.map((mov) => (
                  <tr key={mov.movement_id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">{mov.movement_id}</td>
                    <td className="px-4 py-3 text-slate-500 text-[11px]">
                      {new Date(mov.timestamp).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 font-mono text-blue-600 font-medium">
                      {mov.shipment_id || '—'}
                    </td>
                    <td className="px-4 py-3 text-slate-800 font-medium">{mov.product_name || mov.sku_id}</td>
                    <td className="px-4 py-3 text-slate-700">
                      {mov.source_location_name} → {mov.destination_location_name}
                    </td>
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">{mov.quantity} cases</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-sm bg-slate-100 text-slate-700 font-semibold text-[10px] border border-slate-200 uppercase">
                        {mov.movement_type.replace(/_/g, ' ')}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-[11px] max-w-xs truncate" title={mov.notes || ''}>
                      {mov.notes || '—'}
                    </td>
                  </tr>
                ))}
                {movements.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-slate-400">
                      No stock movement audit records yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 1: GOVERNANCE APPROVAL
      ========================================================================= */}
      {approvalModalShipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6">
            <h3 className="font-bold text-base text-slate-900">Governance Review & Decision</h3>
            <p className="text-xs text-slate-500 mt-1">
              Authorizing shipment #{approvalModalShipment.shipment_id}
            </p>

            <div className="my-4 p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-500">SKU:</span>
                <span className="font-semibold text-slate-800">{approvalModalShipment.product_name || approvalModalShipment.sku_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Quantity:</span>
                <span className="font-mono font-bold text-blue-700">{approvalModalShipment.quantity.toLocaleString()} cases</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Corridor:</span>
                <span className="text-slate-800">
                  {approvalModalShipment.source_location_name} → {approvalModalShipment.destination_location_name}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Est. Freight:</span>
                <span className="font-mono font-bold text-slate-800">₹{approvalModalShipment.estimated_transport_cost.toFixed(2)}</span>
              </div>
            </div>

            <form onSubmit={handleApprovalSubmit} className="space-y-3 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Decision</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setApprovalDecision({ ...approvalDecision, approved: true })}
                    className={`py-2 rounded-lg font-bold border transition-colors cursor-pointer ${
                      approvalDecision.approved
                        ? 'bg-emerald-600 text-white border-emerald-600'
                        : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    Approve Allocation
                  </button>
                  <button
                    type="button"
                    onClick={() => setApprovalDecision({ ...approvalDecision, approved: false })}
                    className={`py-2 rounded-lg font-bold border transition-colors cursor-pointer ${
                      !approvalDecision.approved
                        ? 'bg-red-600 text-white border-red-600'
                        : 'border-slate-200 text-slate-700 hover:bg-slate-50'
                    }`}
                  >
                    Reject Proposal
                  </button>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Authorized Planner ID</label>
                <input
                  type="text"
                  required
                  value={approvalDecision.authorized_user_id}
                  onChange={(e) => setApprovalDecision({ ...approvalDecision, authorized_user_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Governance Audit Notes</label>
                <textarea
                  rows={2}
                  placeholder="e.g. Authorized under regional distribution budget..."
                  value={approvalDecision.notes}
                  onChange={(e) => setApprovalDecision({ ...approvalDecision, notes: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setApprovalModalShipment(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold cursor-pointer shadow-2xs"
                >
                  {actionLoading ? 'Recording...' : 'Record Decision'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 2: DISPATCH PREPARATION & CHECKLIST
      ========================================================================= */}
      {prepareModalShipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6">
            <div className="flex items-center gap-2 mb-2">
              <PackageCheck className="w-5 h-5 text-indigo-600" />
              <h3 className="font-bold text-base text-slate-900">Warehouse Dispatch Readiness & Staging</h3>
            </div>
            <p className="text-xs text-slate-500">
              Shipment #{prepareModalShipment.shipment_id} • {prepareModalShipment.product_name} ({prepareModalShipment.quantity} cases)
            </p>

            <div className="my-3 p-3 bg-indigo-50/60 rounded-lg border border-indigo-100 text-xs">
              <p className="font-semibold text-indigo-900">Inventory Safeguard Verification:</p>
              <p className="text-[11px] text-indigo-700 mt-0.5">
                On confirmation, <strong>{prepareModalShipment.quantity} cases</strong> will be reserved from dispatchable inventory at{' '}
                <strong>{prepareModalShipment.source_location_name}</strong>.
              </p>
            </div>

            <form onSubmit={handlePrepareSubmit} className="space-y-4 text-xs mt-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-2">Readiness Checklist</label>
                <div className="space-y-2 bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prepChecklist.packaging_inspected}
                      onChange={(e) => setPrepChecklist({ ...prepChecklist, packaging_inspected: e.target.checked })}
                      className="rounded text-blue-600"
                    />
                    <span className="font-medium text-slate-700">Packaging, corrugate, and shrink-wrap inspected intact</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prepChecklist.quantity_reconciled}
                      onChange={(e) => setPrepChecklist({ ...prepChecklist, quantity_reconciled: e.target.checked })}
                      className="rounded text-blue-600"
                    />
                    <span className="font-medium text-slate-700">Quantity reconciled against warehouse pick list ({prepareModalShipment.quantity} cases)</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prepChecklist.dock_assigned}
                      onChange={(e) => setPrepChecklist({ ...prepChecklist, dock_assigned: e.target.checked })}
                      className="rounded text-blue-600"
                    />
                    <span className="font-medium text-slate-700">Staging bay & loading dock allocated</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={prepChecklist.batch_verified}
                      onChange={(e) => setPrepChecklist({ ...prepChecklist, batch_verified: e.target.checked })}
                      className="rounded text-blue-600"
                    />
                    <span className="font-medium text-slate-700">Batch lot numbers and minimum 70% shelf-life verified</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Authorized Warehouse Supervisor ID</label>
                <input
                  type="text"
                  required
                  value={prepUserId}
                  onChange={(e) => setPrepUserId(e.target.value)}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Staging Bay & Preparation Remarks</label>
                <input
                  type="text"
                  value={prepNotes}
                  onChange={(e) => setPrepNotes(e.target.value)}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setPrepareModalShipment(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-semibold cursor-pointer shadow-2xs"
                >
                  {actionLoading ? 'Staging...' : 'Confirm Dispatch Readiness'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 3: CARRIER & LOGISTICS COORDINATION
      ========================================================================= */}
      {carrierModalShipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6">
            <div className="flex items-center gap-2 mb-2">
              <Truck className="w-5 h-5 text-blue-600" />
              <h3 className="font-bold text-base text-slate-900">Logistics Agency & Carrier Coordination</h3>
            </div>
            <p className="text-xs text-slate-500">
              Shipment #{carrierModalShipment.shipment_id} • Assigned carrier, waybill, and vehicle scheduling.
            </p>

            <form onSubmit={handleCarrierSubmit} className="space-y-3.5 text-xs mt-4">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Carrier Logistics Provider Organization</label>
                <select
                  value={carrierForm.carrier_agency_id}
                  onChange={(e) => setCarrierForm({ ...carrierForm, carrier_agency_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg bg-white focus:outline-blue-600"
                >
                  <option value="">-- Select 3PL / Carrier Agency --</option>
                  {carrierAgencies.map((c) => (
                    <option key={c.org_id} value={c.org_id}>
                      {c.name} ({c.org_id})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Carrier Coordinator Contact</label>
                  <input
                    type="text"
                    placeholder="Name / Mobile (+91...)"
                    value={carrierForm.carrier_contact}
                    onChange={(e) => setCarrierForm({ ...carrierForm, carrier_contact: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Consignment / Bilty / Waybill #</label>
                  <input
                    type="text"
                    placeholder="e.g. VRL-WAYBILL-9901"
                    value={carrierForm.consignment_number}
                    onChange={(e) => setCarrierForm({ ...carrierForm, consignment_number: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Assigned Vehicle Number</label>
                  <input
                    type="text"
                    placeholder="e.g. MH-12-RN-4402"
                    value={carrierForm.vehicle_number}
                    onChange={(e) => setCarrierForm({ ...carrierForm, vehicle_number: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Driver Name & Phone</label>
                  <input
                    type="text"
                    placeholder="e.g. Ramesh (+91 98220...)"
                    value={carrierForm.driver_contact}
                    onChange={(e) => setCarrierForm({ ...carrierForm, driver_contact: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Carrier Acceptance</label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="carrier_accepted"
                      checked={carrierForm.accepted}
                      onChange={() => setCarrierForm({ ...carrierForm, accepted: true })}
                    />
                    <span className="font-semibold text-emerald-700">Accepted by Carrier</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="carrier_accepted"
                      checked={!carrierForm.accepted}
                      onChange={() => setCarrierForm({ ...carrierForm, accepted: false })}
                    />
                    <span className="font-semibold text-rose-700">Rejected by Carrier</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Authorized Coordinator ID</label>
                <input
                  type="text"
                  required
                  value={carrierForm.authorized_user_id}
                  onChange={(e) => setCarrierForm({ ...carrierForm, authorized_user_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCarrierModalShipment(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold cursor-pointer shadow-2xs"
                >
                  {actionLoading ? 'Saving...' : 'Update Carrier Allocation'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 4: PHYSICAL DISPATCH CONFIRMATION (GATE-OUT)
      ========================================================================= */}
      {dispatchModalShipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6">
            <div className="flex items-center gap-2 mb-2">
              <Send className="w-5 h-5 text-emerald-600" />
              <h3 className="font-bold text-base text-slate-900">Physical Dispatch Confirmation (Gate-Out)</h3>
            </div>
            <p className="text-xs text-slate-500">
              Shipment #{dispatchModalShipment.shipment_id} • Recording physical departure from depot.
            </p>

            <div className="my-3 p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-900">
              <p className="font-semibold">Inventory Accounting Trigger:</p>
              <p className="text-[11px] mt-0.5">
                Recording actual dispatch will <strong>deduct {dispatchModalShipment.quantity} cases</strong> from source warehouse on-hand stock and transition shipment to <strong>In Transit</strong>.
              </p>
            </div>

            <form onSubmit={handleDispatchSubmit} className="space-y-3 text-xs mt-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Consignment / Bilty / Waybill Number</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. VRL-BOM-PUN-8841"
                  value={dispatchForm.consignment_number}
                  onChange={(e) => setDispatchForm({ ...dispatchForm, consignment_number: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Vehicle License Plate #</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. MH-12-RN-4402"
                    value={dispatchForm.vehicle_number}
                    onChange={(e) => setDispatchForm({ ...dispatchForm, vehicle_number: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Driver Contact</label>
                  <input
                    type="text"
                    placeholder="Name & Mobile"
                    value={dispatchForm.driver_contact}
                    onChange={(e) => setDispatchForm({ ...dispatchForm, driver_contact: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Authorized Warehouse Dispatch Officer</label>
                <input
                  type="text"
                  required
                  value={dispatchForm.authorized_user_id}
                  onChange={(e) => setDispatchForm({ ...dispatchForm, authorized_user_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Gate Pass / Vehicle Remarks</label>
                <input
                  type="text"
                  value={dispatchForm.notes}
                  onChange={(e) => setDispatchForm({ ...dispatchForm, notes: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setDispatchModalShipment(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold cursor-pointer shadow-2xs"
                >
                  {actionLoading ? 'Recording Dispatch...' : 'Confirm Actual Dispatch'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 5: DELIVERY CONFIRMATION (GATE-IN)
      ========================================================================= */}
      {deliveryModalShipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <h3 className="font-bold text-base text-slate-900">Delivery Confirmation & Inward Receipt</h3>
            </div>
            <p className="text-xs text-slate-500">
              Shipment #{deliveryModalShipment.shipment_id} • Receiving {deliveryModalShipment.quantity} cases at {deliveryModalShipment.destination_location_name}.
            </p>

            <div className="my-3 p-3 bg-emerald-50 rounded-lg border border-emerald-200 text-xs text-emerald-900">
              <p className="font-semibold">Stock Inward Credit:</p>
              <p className="text-[11px] mt-0.5">
                On confirmation, physical stock will be <strong>credited to {deliveryModalShipment.destination_location_name}</strong> on-hand inventory.
              </p>
            </div>

            <form onSubmit={handleDeliverySubmit} className="space-y-3 text-xs mt-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Proof of Delivery (POD) Docket Reference #</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. POD-SIGNED-PUN-4091"
                  value={deliveryForm.pod_reference}
                  onChange={(e) => setDeliveryForm({ ...deliveryForm, pod_reference: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Actual Freight Cost (INR)
                  <span className="text-[10px] font-normal text-slate-400 ml-1">
                    (Estimated: ₹{deliveryModalShipment.estimated_transport_cost.toFixed(2)})
                  </span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={deliveryForm.actual_transport_cost}
                  onChange={(e) => setDeliveryForm({ ...deliveryForm, actual_transport_cost: Number(e.target.value) })}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Authorized Receiving Officer ID</label>
                <input
                  type="text"
                  required
                  value={deliveryForm.authorized_user_id}
                  onChange={(e) => setDeliveryForm({ ...deliveryForm, authorized_user_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Receiving Remarks & Seal Inspection</label>
                <input
                  type="text"
                  value={deliveryForm.notes}
                  onChange={(e) => setDeliveryForm({ ...deliveryForm, notes: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setDeliveryModalShipment(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold cursor-pointer shadow-2xs"
                >
                  {actionLoading ? 'Recording Inward...' : 'Confirm Delivery'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          MODAL 6: LOG OPERATIONAL EXCEPTION
      ========================================================================= */}
      {exceptionModalShipment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6">
            <div className="flex items-center gap-2 mb-2">
              <BadgeAlert className="w-5 h-5 text-rose-600" />
              <h3 className="font-bold text-base text-slate-900">Record Operational Exception / Delay</h3>
            </div>
            <p className="text-xs text-slate-500">
              Shipment #{exceptionModalShipment.shipment_id} • Log transit interruption without breaking lifecycle state.
            </p>

            <form onSubmit={handleExceptionSubmit} className="space-y-3 text-xs mt-4">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Exception Category / Reason</label>
                <select
                  value={exceptionForm.exception_reason}
                  onChange={(e) => setExceptionForm({ ...exceptionForm, exception_reason: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg bg-white focus:outline-blue-600"
                >
                  <option value="Monsoon waterlogging on expressway">Monsoon / Severe Weather Interruption</option>
                  <option value="Highway traffic congestion">Highway Traffic Congestion / Road Block</option>
                  <option value="Transport vehicle mechanical breakdown">Vehicle Mechanical Breakdown</option>
                  <option value="Warehouse loading dock congestion">Loading Dock / Facility Congestion</option>
                  <option value="Driver duty hours restriction">Driver Rest / Duty Hours Regulation</option>
                  <option value="Packaging damage inspection in transit">Transit Packaging Inspection</option>
                </select>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Detailed Incident Narrative</label>
                <textarea
                  rows={3}
                  required
                  placeholder="Provide incident narrative, revised ETA estimate, or corrective action..."
                  value={exceptionForm.notes}
                  onChange={(e) => setExceptionForm({ ...exceptionForm, notes: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Authorized Coordinator ID</label>
                <input
                  type="text"
                  required
                  value={exceptionForm.authorized_user_id}
                  onChange={(e) => setExceptionForm({ ...exceptionForm, authorized_user_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg font-mono focus:outline-blue-600"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setExceptionModalShipment(null)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-semibold cursor-pointer shadow-2xs"
                >
                  {actionLoading ? 'Logging...' : 'Record Exception'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================================
          DRAWER / MODAL 7: FULL PLAN-TO-EXECUTION TRACEABILITY
      ========================================================================= */}
      {traceabilityData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 flex justify-between items-center bg-slate-50/70">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-bold text-base text-slate-900">
                    Shipment Traceability & Lifecycle Audit Trail
                  </h3>
                  <p className="text-xs text-slate-500 font-mono">
                    {traceabilityData.shipment_id} • {traceabilityData.product_name} ({traceabilityData.quantity} cases)
                  </p>
                </div>
              </div>
              <button
                onClick={() => setTraceabilityData(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Scrollable Body */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs">
              {/* Lineage & Optimization Origin Card */}
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-slate-900 text-sm">Phase 3 Planning Lineage & Decision Receipt</span>
                  {traceabilityData.planning_run_id ? (
                    <span className="px-2 py-0.5 rounded-md bg-purple-100 text-purple-800 font-mono text-[10px] font-bold">
                      Run ID: {traceabilityData.planning_run_id}
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 rounded-md bg-slate-200 text-slate-700 text-[10px]">Manual Proposal</span>
                  )}
                </div>

                {traceabilityData.decision_rationale && (
                  <div className="mt-2 p-2.5 bg-white rounded-lg border border-slate-200 text-slate-700">
                    <p className="font-semibold text-slate-900 text-[11px] mb-1">Optimizer Decision Rationale:</p>
                    <p className="italic text-[11px]">{traceabilityData.decision_rationale}</p>
                  </div>
                )}

                {traceabilityData.decision_receipt && (
                  <div className="mt-2 text-[11px] text-slate-600 grid grid-cols-2 gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
                    <div>
                      <span className="text-slate-400">Constraint Evidence:</span>{' '}
                      <span className="font-medium text-slate-800">{traceabilityData.decision_receipt.evidence || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-slate-400">Rejected Alternatives:</span>{' '}
                      <span className="font-medium text-slate-800">
                        {traceabilityData.decision_receipt.rejected_alternatives?.length || 0} corridors
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Cost & Operational Metrics Comparison */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-white border border-slate-200 rounded-xl">
                  <div className="text-slate-400 text-[10px] uppercase font-bold">Est. Freight</div>
                  <div className="text-base font-bold text-slate-900 font-mono mt-0.5">
                    ₹{traceabilityData.estimated_transport_cost.toFixed(2)}
                  </div>
                  <div className="text-[10px] text-slate-400">Based on route tariff</div>
                </div>

                <div className="p-3 bg-white border border-slate-200 rounded-xl">
                  <div className="text-slate-400 text-[10px] uppercase font-bold">Actual Freight</div>
                  <div className="text-base font-bold text-emerald-700 font-mono mt-0.5">
                    {traceabilityData.actual_transport_cost !== null && traceabilityData.actual_transport_cost !== undefined
                      ? `₹${traceabilityData.actual_transport_cost.toFixed(2)}`
                      : 'Pending Delivery'}
                  </div>
                  <div className="text-[10px] text-slate-400">Inward confirmed cost</div>
                </div>

                <div className="p-3 bg-white border border-slate-200 rounded-xl">
                  <div className="text-slate-400 text-[10px] uppercase font-bold">Carrier Reference</div>
                  <div className="text-xs font-bold text-slate-900 truncate mt-0.5 font-mono">
                    {traceabilityData.consignment_number || 'Unassigned'}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate">{traceabilityData.vehicle_number || 'No truck #'}</div>
                </div>

                <div className="p-3 bg-white border border-slate-200 rounded-xl">
                  <div className="text-slate-400 text-[10px] uppercase font-bold">POD Docket</div>
                  <div className="text-xs font-bold text-slate-900 truncate mt-0.5 font-mono">
                    {traceabilityData.pod_reference || 'Pending'}
                  </div>
                  <div className="text-[10px] text-slate-400">Signed delivery proof</div>
                </div>
              </div>

              {/* Immutable ShipmentEvent Timeline */}
              <div>
                <h4 className="font-bold text-slate-900 text-xs mb-3 flex items-center gap-1.5 uppercase tracking-wider">
                  <History className="w-4 h-4 text-blue-600" />
                  Immutable Event History ({traceabilityData.events.length} Events)
                </h4>

                <div className="relative pl-6 border-l-2 border-blue-200 space-y-4">
                  {traceabilityData.events.map((evt) => (
                    <div key={evt.event_id} className="relative">
                      {/* Timeline dot */}
                      <div className="absolute -left-[31px] top-1 w-3.5 h-3.5 rounded-full bg-blue-600 border-2 border-white shadow-xs" />

                      <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                        <div className="flex justify-between items-center text-[11px]">
                          <span className="font-bold text-slate-800">
                            {evt.from_status.toUpperCase()} → {evt.to_status.toUpperCase()}
                          </span>
                          <span className="text-slate-400 font-mono text-[10px]">
                            {new Date(evt.created_at).toLocaleString()}
                          </span>
                        </div>

                        <div className="text-[11px] text-slate-600 mt-1">
                          <span className="text-slate-400">Actor:</span> <strong>{evt.actor_id}</strong>{' '}
                          <span className="text-slate-400">({evt.actor_role || 'operator'})</span>
                        </div>

                        {evt.notes && (
                          <div className="text-[11px] text-slate-700 bg-white p-2 rounded mt-1.5 border border-slate-200">
                            {evt.notes}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}

                  {traceabilityData.events.length === 0 && (
                    <p className="text-slate-400 italic">No events recorded yet.</p>
                  )}
                </div>
              </div>
            </div>

            {/* Drawer Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setTraceabilityData(null)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-semibold rounded-lg text-xs cursor-pointer"
              >
                Close Traceability
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
