import React, { useState, useEffect } from 'react';
import {
  Building2,
  MapPin,
  Route as RouteIcon,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Truck,
  ArrowRight,
  Package,
  Users,
  Edit2,
  Trash2,
  Tag,
} from 'lucide-react';
import {
  getOrganizations,
  createOrganization,
  getNetworkLocations,
  createNetworkLocation,
  getNetworkRoutes,
  createNetworkRoute,
  getNetworkEligibility,
  getProducts,
  createProduct,
  updateProduct,
  deleteProduct,
  getProductCategories,
  updateNetworkLocation,
  getAdminUsers,
} from '../services/api';
import type {
  OrganizationItem,
  LocationItem,
  RouteItem,
  NetworkEligibilityResponse,
  ProductItem,
  CategorySummaryItem,
  AdminUserItem,
} from '../types/api';

export const NetworkManagementPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'organizations' | 'locations' | 'routes' | 'eligibility' | 'products' | 'users'>('products');


  // Data states
  const [organizations, setOrganizations] = useState<OrganizationItem[]>([]);
  const [locations, setLocations] = useState<LocationItem[]>([]);
  const [routes, setRoutes] = useState<RouteItem[]>([]);
  const [eligibility, setEligibility] = useState<NetworkEligibilityResponse | null>(null);

  // Products & Categories states
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [categories, setCategories] = useState<CategorySummaryItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [showProductModal, setShowProductModal] = useState<boolean>(false);
  const [editingProduct, setEditingProduct] = useState<ProductItem | null>(null);
  const [productForm, setProductForm] = useState({
    sku_id: '',
    name: '',
    category: 'General',
    unit: 'cases',
    case_pack: 1,
    shelf_life_days: 180 as number | null,
  });

  // Admin Users states
  const [adminUsers, setAdminUsers] = useState<AdminUserItem[]>([]);

  // Facility Edit state
  const [showEditLocModal, setShowEditLocModal] = useState<boolean>(false);
  const [editingLoc, setEditingLoc] = useState<LocationItem | null>(null);
  const [editLocForm, setEditLocForm] = useState({
    name: '',
    location_type: '',
    region: '',
    city: '',
    address: '',
    owner_org_id: '',
    operator_org_id: '',
    storage_capacity_units: 0,
    dispatch_capacity_daily: 0,
    is_active: true,
  });

  // Loading & error states
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Search filter
  const [searchTerm, setSearchTerm] = useState('');

  // Modals / forms
  const [showOrgModal, setShowOrgModal] = useState(false);
  const [newOrg, setNewOrg] = useState({
    org_id: '',
    name: '',
    org_type: 'fmcg_company',
    contact_email: '',
    contact_phone: '',
    is_active: true,
  });

  const [showLocModal, setShowLocModal] = useState(false);
  const [newLoc, setNewLoc] = useState({
    location_id: '',
    name: '',
    location_type: 'company_warehouse',
    region: 'North',
    city: '',
    owner_org_id: '',
    operator_org_id: '',
    storage_capacity_units: 50000,
    dispatch_capacity_daily: 2500,
    is_active: true,
  });

  const [showRouteModal, setShowRouteModal] = useState(false);
  const [newRoute, setNewRoute] = useState({
    from_location_id: '',
    to_location_id: '',
    carrier_agency_id: '',
    lead_time_days: 1.5,
    cost_rate: 8.5,
    capacity_units: 5000,
    pricing_basis: 'per_unit',
    sku_eligibility: 'all',
    is_active: true,
  });

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [orgsData, locsData, routesData, eligData, prodsData, catsData, usersData] = await Promise.all([
        getOrganizations(),
        getNetworkLocations(),
        getNetworkRoutes(),
        getNetworkEligibility(),
        getProducts(),
        getProductCategories(),
        getAdminUsers().catch(() => []),
      ]);
      setOrganizations(orgsData);
      setLocations(locsData);
      setRoutes(routesData);
      setEligibility(eligData);
      setProducts(prodsData);
      setCategories(catsData);
      setAdminUsers(usersData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch network data.');
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAddProduct = () => {
    setEditingProduct(null);
    setProductForm({
      sku_id: '',
      name: '',
      category: 'General',
      unit: 'cases',
      case_pack: 1,
      shelf_life_days: 180,
    });
    setShowProductModal(true);
  };

  const handleOpenEditProduct = (prod: ProductItem) => {
    setEditingProduct(prod);
    setProductForm({
      sku_id: prod.sku_id,
      name: prod.name,
      category: prod.category || 'General',
      unit: prod.unit || 'cases',
      case_pack: prod.case_pack ?? 1,
      shelf_life_days: prod.shelf_life_days ?? null,
    });
    setShowProductModal(true);
  };

  const handleOpenEditLoc = (loc: LocationItem) => {
    setEditingLoc(loc);
    setEditLocForm({
      name: loc.name,
      location_type: loc.location_type,
      region: loc.region,
      city: loc.city || '',
      address: loc.address || '',
      owner_org_id: loc.owner_org_id || '',
      operator_org_id: loc.operator_org_id || '',
      storage_capacity_units: loc.storage_capacity_units ?? 0,
      dispatch_capacity_daily: loc.dispatch_capacity_daily ?? 0,
      is_active: loc.is_active ?? true,
    });
    setShowEditLocModal(true);
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError(null);
    try {
      if (editingProduct) {
        await updateProduct(editingProduct.sku_id, {
          name: productForm.name,
          category: productForm.category,
          unit: productForm.unit,
          case_pack: Number(productForm.case_pack),
          shelf_life_days: productForm.shelf_life_days ? Number(productForm.shelf_life_days) : null,
        });
        setSuccessMsg(`Product '${editingProduct.sku_id}' updated successfully.`);
      } else {
        await createProduct({
          sku_id: productForm.sku_id.trim(),
          name: productForm.name.trim(),
          category: productForm.category.trim() || 'General',
          unit: productForm.unit.trim() || 'cases',
          case_pack: Number(productForm.case_pack) || 1,
          shelf_life_days: productForm.shelf_life_days ? Number(productForm.shelf_life_days) : null,
        });
        setSuccessMsg(`Product '${productForm.sku_id}' created successfully.`);
      }
      setShowProductModal(false);
      setEditingProduct(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save product');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteProduct = async (skuId: string) => {
    if (!window.confirm(`Are you sure you want to delete product SKU '${skuId}'?`)) return;
    setActionLoading(true);
    setError(null);
    try {
      await deleteProduct(skuId);
      setSuccessMsg(`Product '${skuId}' deleted successfully.`);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete product');
    } finally {
      setActionLoading(false);
    }
  };

  const handleUpdateLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingLoc) return;
    setActionLoading(true);
    setError(null);
    try {
      await updateNetworkLocation(editingLoc.location_id, {
        name: editLocForm.name,
        location_type: editLocForm.location_type,
        region: editLocForm.region,
        city: editLocForm.city,
        address: editLocForm.address,
        owner_org_id: editLocForm.owner_org_id || undefined,
        operator_org_id: editLocForm.operator_org_id || undefined,
        storage_capacity_units: Number(editLocForm.storage_capacity_units),
        dispatch_capacity_daily: Number(editLocForm.dispatch_capacity_daily),
        is_active: editLocForm.is_active,
      });
      setSuccessMsg(`Facility '${editingLoc.location_id}' updated successfully.`);
      setShowEditLocModal(false);
      setEditingLoc(null);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update facility');
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);


  const handleCreateOrg = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError(null);
    try {
      await createOrganization(newOrg);
      setSuccessMsg(`Organization '${newOrg.name}' registered successfully.`);
      setShowOrgModal(false);
      setNewOrg({ org_id: '', name: '', org_type: 'fmcg_company', contact_email: '', contact_phone: '', is_active: true });
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create organization');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateLocation = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError(null);
    try {
      await createNetworkLocation({
        ...newLoc,
        owner_org_id: newLoc.owner_org_id || undefined,
        operator_org_id: newLoc.operator_org_id || undefined,
      });
      setSuccessMsg(`Facility '${newLoc.name}' created successfully.`);
      setShowLocModal(false);
      setNewLoc({
        location_id: '',
        name: '',
        location_type: 'company_warehouse',
        region: 'North',
        city: '',
        owner_org_id: '',
        operator_org_id: '',
        storage_capacity_units: 50000,
        dispatch_capacity_daily: 2500,
        is_active: true,
      });
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create facility');
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateRoute = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading(true);
    setError(null);
    try {
      await createNetworkRoute({
        ...newRoute,
        carrier_agency_id: newRoute.carrier_agency_id || undefined,
      });
      setSuccessMsg('Distribution route configured successfully.');
      setShowRouteModal(false);
      fetchData();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to configure route');
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-white rounded-xl border border-slate-200/80 p-5 sm:p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-sm bg-blue-50 text-blue-700 text-xs font-semibold uppercase tracking-wider border border-blue-200">
                Phase 2 FMCG Architecture
              </span>
              <span className="text-xs text-slate-500">• Permitted Multi-Echelon Network</span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 mt-1">Real-World Distribution Network Design</h2>
            <p className="text-xs sm:text-sm text-slate-600 mt-1 max-w-3xl">
              Model Indian FMCG supply chains with company warehouses, C&F depots, 3PL logistics agencies,
              independent distributors, and retail stock points. Strictly governs inventory ownership vs physical storage.
            </p>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="self-start sm:self-center flex items-center gap-2 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh Network
          </button>
        </div>

        {/* Tab Controls */}
        <div className="flex border-b border-slate-200 mt-6 gap-6 text-sm font-semibold overflow-x-auto">
          <button
            onClick={() => setActiveTab('products')}
            className={`pb-3 relative cursor-pointer shrink-0 ${
              activeTab === 'products'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Package className="w-4 h-4" />
              Products & Categories ({products.length})
            </span>
          </button>
          <button
            onClick={() => setActiveTab('locations')}
            className={`pb-3 relative cursor-pointer shrink-0 ${
              activeTab === 'locations'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <MapPin className="w-4 h-4" />
              Facilities & Warehouses ({locations.length})
            </span>
          </button>
          <button
            onClick={() => setActiveTab('organizations')}
            className={`pb-3 relative cursor-pointer shrink-0 ${
              activeTab === 'organizations'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Building2 className="w-4 h-4" />
              Organizations & 3PLs ({organizations.length})
            </span>
          </button>
          <button
            onClick={() => setActiveTab('routes')}
            className={`pb-3 relative cursor-pointer shrink-0 ${
              activeTab === 'routes'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <RouteIcon className="w-4 h-4" />
              Corridors ({routes.length})
            </span>
          </button>
          <button
            onClick={() => setActiveTab('eligibility')}
            className={`pb-3 relative cursor-pointer shrink-0 ${
              activeTab === 'eligibility'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" />
              Corridor Audit
              {eligibility && eligibility.unserviceable_destinations.length > 0 && (
                <span className="bg-amber-100 text-amber-800 text-[10px] px-1.5 py-0.2 rounded-full font-bold">
                  {eligibility.unserviceable_destinations.length}
                </span>
              )}
            </span>
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`pb-3 relative cursor-pointer shrink-0 ${
              activeTab === 'users'
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <span className="flex items-center gap-2">
              <Users className="w-4 h-4" />
              Users & Access ({adminUsers.length})
            </span>
          </button>
        </div>
      </div>


      {/* Notifications */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-semibold">Network Error</p>
            <p>{error}</p>
          </div>
        </div>
      )}
      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800 flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0 text-emerald-600" />
          <div className="flex-1 flex justify-between items-center">
            <span>{successMsg}</span>
            <button onClick={() => setSuccessMsg(null)} className="text-emerald-700 hover:underline font-medium">
              Dismiss
            </button>
          </div>
        </div>
      )}

      {/* TAB: PRODUCTS & CATEGORIES */}
      {activeTab === 'products' && (
        <div className="space-y-5">
          {/* Summary Stat Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-blue-50 text-blue-600">
                  <Package className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total SKUs</div>
                  <div className="text-xl font-bold text-slate-900 mt-0.5">{products.length}</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-purple-50 text-purple-600">
                  <Tag className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Active Categories</div>
                  <div className="text-xl font-bold text-slate-900 mt-0.5">{categories.length}</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-amber-50 text-amber-600">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">Avg Shelf Life</div>
                  <div className="text-xl font-bold text-slate-900 mt-0.5">
                    {products.length > 0
                      ? Math.round(
                          products.reduce((acc, p) => acc + (p.shelf_life_days || 180), 0) / products.length
                        )
                      : 0}{' '}
                    days
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Controls: Search, Category Filter, and Add Button */}
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
              <div className="relative w-full sm:w-64">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search SKU or name..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-blue-600"
                />
              </div>
              <div className="flex items-center gap-1.5 overflow-x-auto py-1 max-w-xl">
                <button
                  onClick={() => setSelectedCategory('all')}
                  className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer shrink-0 ${
                    selectedCategory === 'all'
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                  }`}
                >
                  All ({products.length})
                </button>
                {categories.map((c) => (
                  <button
                    key={c.category}
                    onClick={() => setSelectedCategory(c.category)}
                    className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors cursor-pointer shrink-0 ${
                      selectedCategory === c.category
                        ? 'bg-blue-600 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {c.category} ({c.sku_count ?? c.product_count})
                  </button>
                ))}
              </div>
            </div>
            <button
              onClick={handleOpenAddProduct}
              className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer shrink-0"
            >
              <Plus className="w-4 h-4" />
              Add Product SKU
            </button>
          </div>

          {/* Products Table */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">SKU Code</th>
                  <th className="px-4 py-3">Product Name</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Unit</th>
                  <th className="px-4 py-3">Case Pack</th>
                  <th className="px-4 py-3">Shelf Life</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {products
                  .filter((p) => {
                    const matchesSearch =
                      p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                      p.sku_id.toLowerCase().includes(searchTerm.toLowerCase());
                    const matchesCat = selectedCategory === 'all' || p.category === selectedCategory;
                    return matchesSearch && matchesCat;
                  })
                  .map((p) => (
                    <tr key={p.sku_id} className="hover:bg-slate-50/60">
                      <td className="px-4 py-3 font-mono font-semibold text-slate-900">{p.sku_id}</td>
                      <td className="px-4 py-3 font-medium text-slate-800">{p.name}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200">
                          {p.category}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{p.unit}</td>
                      <td className="px-4 py-3 font-mono text-slate-600">{p.case_pack} units/case</td>
                      <td className="px-4 py-3 text-slate-600">
                        {p.shelf_life_days ? `${p.shelf_life_days} days` : 'No expiry'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleOpenEditProduct(p)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 rounded text-xs font-medium transition-colors cursor-pointer"
                          >
                            <Edit2 className="w-3 h-3" />
                            Edit
                          </button>
                          <button
                            onClick={() => handleDeleteProduct(p.sku_id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-red-50 text-slate-700 hover:text-red-700 rounded text-xs font-medium transition-colors cursor-pointer"
                          >
                            <Trash2 className="w-3 h-3" />
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                {products.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">
                      No products registered yet. Click "Add Product SKU" to register the first SKU.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 1: ORGANIZATIONS */}
      {activeTab === 'organizations' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div className="relative w-72">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search organizations..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-blue-600"
              />
            </div>
            <button
              onClick={() => setShowOrgModal(true)}
              className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Register Organization
            </button>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Org ID</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Contact</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {organizations
                  .filter((o) => o.name.toLowerCase().includes(searchTerm.toLowerCase()) || o.org_id.toLowerCase().includes(searchTerm.toLowerCase()))
                  .map((org) => (
                    <tr key={org.org_id} className="hover:bg-slate-50/60">
                      <td className="px-4 py-3 font-mono font-medium text-slate-800">{org.org_id}</td>
                      <td className="px-4 py-3 font-semibold text-slate-900">{org.name}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`px-2 py-0.5 rounded-full font-medium text-[10px] uppercase tracking-wide border ${
                            org.org_type === 'fmcg_company'
                              ? 'bg-blue-50 text-blue-700 border-blue-200'
                              : org.org_type === 'cnf_agency'
                              ? 'bg-purple-50 text-purple-700 border-purple-200'
                              : org.org_type === 'logistics_provider'
                              ? 'bg-amber-50 text-amber-700 border-amber-200'
                              : org.org_type === 'distributor'
                              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              : 'bg-slate-100 text-slate-700 border-slate-200'
                          }`}
                        >
                          {org.org_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {org.contact_email || '—'} {org.contact_phone ? `(${org.contact_phone})` : ''}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            org.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          {org.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                    </tr>
                  ))}
                {organizations.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-slate-400">
                      No organizations registered. Click "Register Organization" or import via Import Centre.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 2: FACILITIES & LOCATIONS */}
      {activeTab === 'locations' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div className="relative w-72">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search facilities..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-blue-600"
              />
            </div>
            <button
              onClick={() => setShowLocModal(true)}
              className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Add Facility
            </button>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Facility</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Region & City</th>
                  <th className="px-4 py-3">Owning Org</th>
                  <th className="px-4 py-3">Operating Org</th>
                  <th className="px-4 py-3">Storage Cap.</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {locations
                  .filter((l) => l.name.toLowerCase().includes(searchTerm.toLowerCase()) || l.location_id.toLowerCase().includes(searchTerm.toLowerCase()))
                  .map((loc) => {
                    const isSeparateOperator = loc.owner_org_id && loc.operator_org_id && loc.owner_org_id !== loc.operator_org_id;
                    return (
                      <tr key={loc.location_id} className="hover:bg-slate-50/60">
                        <td className="px-4 py-3">
                          <div className="font-semibold text-slate-900">{loc.name}</div>
                          <div className="font-mono text-[11px] text-slate-400">{loc.location_id}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="px-2 py-0.5 rounded-sm bg-slate-100 text-slate-700 text-[10px] font-medium border border-slate-200">
                            {loc.location_type.replace('_', ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-slate-600">
                          {loc.city ? `${loc.city}, ` : ''}{loc.region}
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-medium text-slate-800">{loc.owner_org_name || loc.owner_org_id || '—'}</span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <span className="font-medium text-slate-800">{loc.operator_org_name || loc.operator_org_id || '—'}</span>
                            {isSeparateOperator && (
                              <span className="text-[9px] bg-purple-50 text-purple-700 border border-purple-200 px-1.5 py-0.2 rounded-sm font-semibold">
                                C&F/3PL Managed
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-slate-600 font-mono">
                          {loc.storage_capacity_units ? `${loc.storage_capacity_units.toLocaleString()} units` : '—'}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                              loc.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {loc.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleOpenEditLoc(loc)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-100 hover:bg-blue-50 text-slate-700 hover:text-blue-700 rounded text-xs font-medium transition-colors cursor-pointer"
                          >
                            <Edit2 className="w-3 h-3" />
                            Edit
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                {locations.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center py-8 text-slate-400">
                      No facilities registered.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: PERMITTED ROUTES & RATES */}
      {activeTab === 'routes' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div className="relative w-72">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search corridors..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-blue-600"
              />
            </div>
            <button
              onClick={() => setShowRouteModal(true)}
              className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              Configure Route
            </button>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Source Facility</th>
                  <th className="px-4 py-3">Destination Facility</th>
                  <th className="px-4 py-3">Assigned 3PL / Carrier</th>
                  <th className="px-4 py-3">Lead Time</th>
                  <th className="px-4 py-3">Transport Rate</th>
                  <th className="px-4 py-3">Capacity</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {routes
                  .filter(
                    (r) =>
                      (r.from_location_name || r.from_location_id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
                      (r.to_location_name || r.to_location_id || '').toLowerCase().includes(searchTerm.toLowerCase())
                  )
                  .map((route) => (
                    <tr key={route.id} className="hover:bg-slate-50/60">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{route.from_location_name || route.from_location_id}</div>
                        <div className="font-mono text-[10px] text-slate-400">{route.from_location_id}</div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{route.to_location_name || route.to_location_id}</div>
                        <div className="font-mono text-[10px] text-slate-400">{route.to_location_id}</div>
                      </td>
                      <td className="px-4 py-3">
                        {route.carrier_agency_name ? (
                          <div className="flex items-center gap-1.5 text-blue-700 font-medium">
                            <Truck className="w-3.5 h-3.5" />
                            <span>{route.carrier_agency_name}</span>
                          </div>
                        ) : (
                          <span className="text-slate-400 italic">Self-fleet / Default</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-mono font-medium text-slate-800">
                        {route.lead_time_days} days
                      </td>
                      <td className="px-4 py-3 font-mono font-semibold text-slate-900">
                        ₹{(route.cost_rate ?? route.cost_per_unit ?? 0).toFixed(2)}
                        <span className="text-[10px] text-slate-500 font-normal ml-1">/ {route.pricing_basis || 'unit'}</span>
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-600">
                        {route.capacity_units ? `${route.capacity_units.toLocaleString()} units` : 'Unconstrained'}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            route.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          {route.is_active ? 'Permitted' : 'Inactive'}
                        </span>
                      </td>
                    </tr>
                  ))}
                {routes.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-slate-400">
                      No permitted routes configured. Click "Configure Route" to establish a lane.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: ELIGIBILITY AUDIT */}
      {activeTab === 'eligibility' && eligibility && (
        <div className="space-y-6">
          {/* Summary metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs text-slate-500 uppercase font-semibold">Total Facilities</span>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {eligibility.active_locations} <span className="text-xs text-slate-400">/ {eligibility.total_locations}</span>
              </div>
              <span className="text-[11px] text-emerald-600 font-medium">Active network nodes</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs text-slate-500 uppercase font-semibold">Configured Corridors</span>
              <div className="text-2xl font-bold text-slate-900 mt-1">
                {eligibility.active_routes} <span className="text-xs text-slate-400">/ {eligibility.total_routes}</span>
              </div>
              <span className="text-[11px] text-blue-600 font-medium">Permitted lanes</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs text-slate-500 uppercase font-semibold">Eligible Corridors</span>
              <div className="text-2xl font-bold text-emerald-600 mt-1">
                {eligibility.eligible_corridors.filter((c) => c.is_eligible).length}
              </div>
              <span className="text-[11px] text-slate-500 font-medium">Passes all business rules</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200">
              <span className="text-xs text-slate-500 uppercase font-semibold">Unserviceable Dest.</span>
              <div className={`text-2xl font-bold mt-1 ${eligibility.unserviceable_destinations.length > 0 ? 'text-amber-600' : 'text-slate-900'}`}>
                {eligibility.unserviceable_destinations.length}
              </div>
              <span className="text-[11px] text-amber-700 font-medium">Require route setup</span>
            </div>
          </div>

          {/* Unserviceable alert table if any */}
          {eligibility.unserviceable_destinations.length > 0 && (
            <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-5">
              <div className="flex items-center gap-2 text-amber-800 font-bold text-sm">
                <AlertTriangle className="w-4 h-4 text-amber-600" />
                Unserviceable Destinations Warning
              </div>
              <p className="text-xs text-amber-700 mt-1">
                The following destinations cannot receive shipments because no active, valid transport corridor connects to them:
              </p>
              <div className="mt-3 bg-white rounded-lg border border-amber-200 overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead className="bg-amber-100/50 text-amber-900 font-semibold border-b border-amber-200">
                    <tr>
                      <th className="px-3 py-2">Destination</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Region</th>
                      <th className="px-3 py-2">Deficiency</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-amber-100">
                    {eligibility.unserviceable_destinations.map((u) => (
                      <tr key={u.location_id}>
                        <td className="px-3 py-2 font-semibold text-slate-800">{u.name} ({u.location_id})</td>
                        <td className="px-3 py-2 text-slate-600">{u.location_type.replace('_', ' ')}</td>
                        <td className="px-3 py-2 text-slate-600">{u.region}</td>
                        <td className="px-3 py-2 text-red-600 font-medium">{u.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Detailed Corridors Evaluation */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 font-semibold text-xs text-slate-700 flex justify-between items-center">
              <span>All Evaluated Corridors & Constraints</span>
              <span className="text-[11px] text-slate-500 font-normal">
                PRD Rule: Route eligibility requires active endpoints, positive lead times & defined transport costs.
              </span>
            </div>
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">Lane</th>
                  <th className="px-4 py-3">Carrier</th>
                  <th className="px-4 py-3">Lead Time</th>
                  <th className="px-4 py-3">Cost Rate</th>
                  <th className="px-4 py-3">Eligibility</th>
                  <th className="px-4 py-3">Reason / Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {eligibility.eligible_corridors.map((c) => (
                  <tr key={c.route_id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2 font-medium text-slate-900">
                        <span>{c.from_location_name}</span>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                        <span>{c.to_location_name}</span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-mono">
                        {c.from_location_id} → {c.to_location_id}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {c.carrier_agency_name || 'Internal'}
                    </td>
                    <td className="px-4 py-3 font-mono text-slate-800">{c.lead_time_days} days</td>
                    <td className="px-4 py-3 font-mono text-slate-800">₹{c.cost_rate.toFixed(2)}</td>
                    <td className="px-4 py-3">
                      {c.is_eligible ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          Eligible
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-50 text-red-700 border border-red-200">
                          <XCircle className="w-3 h-3 text-red-600" />
                          Rejected
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {c.rejection_reasons.length > 0 ? (
                        <ul className="list-disc list-inside text-red-600 text-[11px]">
                          {c.rejection_reasons.map((r, i) => (
                            <li key={i}>{r}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-emerald-700 text-[11px]">Fully feasible & operational</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB: USERS & ACCESS */}
      {activeTab === 'users' && (
        <div className="space-y-5">
          {/* Least Privilege & Policy Banner */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200/70 p-4">
            <div className="flex items-start gap-3">
              <ShieldCheck className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" />
              <div>
                <h4 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                  Least-Privilege Role-Based Access Control (RBAC) & Tenant Isolation
                </h4>
                <p className="text-xs text-slate-600 mt-1">
                  Server-side authorization verifies user identities and their bound organizations directly from the database session.
                  Distributor and retailer organizations are cryptographically isolated and cannot access cross-organization records.
                </p>
                <div className="grid grid-cols-2 sm:grid-cols-6 gap-2 mt-3">
                  <div className="bg-white/80 p-2 rounded-lg border border-blue-100 text-[11px]">
                    <div className="font-bold text-slate-800">admin</div>
                    <div className="text-slate-500">Company Admin Portal</div>
                  </div>
                  <div className="bg-white/80 p-2 rounded-lg border border-blue-100 text-[11px]">
                    <div className="font-bold text-slate-800">planner</div>
                    <div className="text-slate-500">Distribution Intelligence</div>
                  </div>
                  <div className="bg-white/80 p-2 rounded-lg border border-blue-100 text-[11px]">
                    <div className="font-bold text-slate-800">logistics</div>
                    <div className="text-slate-500">Warehouse & Logistics</div>
                  </div>
                  <div className="bg-white/80 p-2 rounded-lg border border-blue-100 text-[11px]">
                    <div className="font-bold text-slate-800">distributor</div>
                    <div className="text-slate-500">Distributor Portal</div>
                  </div>
                  <div className="bg-white/80 p-2 rounded-lg border border-blue-100 text-[11px]">
                    <div className="font-bold text-slate-800">retailer</div>
                    <div className="text-slate-500">Retailer Portal</div>
                  </div>
                  <div className="bg-white/80 p-2 rounded-lg border border-blue-100 text-[11px]">
                    <div className="font-bold text-slate-800">viewer</div>
                    <div className="text-slate-500">Auditor Read-Only</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Search bar */}
          <div className="flex justify-between items-center">
            <div className="relative w-72">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search users or email..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-blue-600"
              />
            </div>
            <div className="text-xs text-slate-500">
              Authorized Users: <span className="font-semibold text-slate-800">{adminUsers.length}</span>
            </div>
          </div>

          {/* Users Table */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase font-semibold">
                <tr>
                  <th className="px-4 py-3">User ID</th>
                  <th className="px-4 py-3">Email Address</th>
                  <th className="px-4 py-3">System Role</th>
                  <th className="px-4 py-3">Tenant Organization</th>
                  <th className="px-4 py-3">Account Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {adminUsers
                  .filter((u) => {
                    const orgIdentifier = u.tenant_org_id || u.org_id || '';
                    const orgLabel = u.tenant_org_name || u.org_name || '';
                    return (
                      u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                      u.user_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
                      (u.role && u.role.toLowerCase().includes(searchTerm.toLowerCase())) ||
                      orgIdentifier.toLowerCase().includes(searchTerm.toLowerCase()) ||
                      orgLabel.toLowerCase().includes(searchTerm.toLowerCase())
                    );
                  })
                  .map((u) => {
                    const orgIdentifier = u.tenant_org_id || u.org_id;
                    const orgLabel = u.tenant_org_name || u.org_name;
                    return (
                      <tr key={u.user_id} className="hover:bg-slate-50/60">
                        <td className="px-4 py-3 font-mono font-medium text-slate-700">{u.user_id}</td>
                        <td className="px-4 py-3 font-semibold text-slate-900">{u.email}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide border ${
                              u.role === 'admin'
                                ? 'bg-red-50 text-red-700 border-red-200'
                                : u.role === 'planner'
                                ? 'bg-blue-50 text-blue-700 border-blue-200'
                                : u.role === 'logistics'
                                ? 'bg-amber-50 text-amber-700 border-amber-200'
                                : u.role === 'distributor'
                                ? 'bg-purple-50 text-purple-700 border-purple-200'
                                : u.role === 'retailer'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : 'bg-slate-100 text-slate-700 border-slate-200'
                            }`}
                          >
                            {u.role}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {orgLabel ? (
                            <div>
                              <span className="font-medium text-slate-800">{orgLabel}</span>
                              <span className="text-[10px] text-slate-400 font-mono ml-1">({orgIdentifier})</span>
                            </div>
                          ) : orgIdentifier ? (
                            <span className="font-mono text-slate-700">{orgIdentifier}</span>
                          ) : (
                            <span className="text-slate-400 italic">Company Internal (Network-wide)</span>
                          )}
                        </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            u.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                          }`}
                        >
                          {u.is_active ? 'Active' : 'Suspended'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {adminUsers.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center py-8 text-slate-400">
                      No user accounts found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* REGISTER ORG MODAL */}
      {showOrgModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6">
            <h3 className="font-bold text-base text-slate-900">Register Organization</h3>
            <p className="text-xs text-slate-500 mt-1">
              Distinguish FMCG brands, C&F operators, 3PL providers, and distributors.
            </p>
            <form onSubmit={handleCreateOrg} className="space-y-3 mt-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Organization ID</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. ORG-ITC-01"
                  value={newOrg.org_id}
                  onChange={(e) => setNewOrg({ ...newOrg, org_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Organization Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. ITC Consumer Products"
                  value={newOrg.name}
                  onChange={(e) => setNewOrg({ ...newOrg, name: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Organization Type</label>
                <select
                  value={newOrg.org_type}
                  onChange={(e) => setNewOrg({ ...newOrg, org_type: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                >
                  <option value="fmcg_company">FMCG Company (Brand Owner)</option>
                  <option value="cnf_agency">C&F Agency (Carrying & Forwarding)</option>
                  <option value="logistics_provider">3PL Logistics Provider (Transporter)</option>
                  <option value="distributor">Independent Distributor (Stockist)</option>
                  <option value="retailer">Retail Enterprise</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Contact Email</label>
                  <input
                    type="email"
                    value={newOrg.contact_email}
                    onChange={(e) => setNewOrg({ ...newOrg, contact_email: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Contact Phone</label>
                  <input
                    type="text"
                    value={newOrg.contact_phone}
                    onChange={(e) => setNewOrg({ ...newOrg, contact_phone: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowOrgModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold cursor-pointer"
                >
                  {actionLoading ? 'Saving...' : 'Save Organization'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD FACILITY MODAL */}
      {showLocModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="font-bold text-base text-slate-900">Add Distribution Facility</h3>
            <p className="text-xs text-slate-500 mt-1">
              Supports Plants, Warehouses, C&F Depots, 3PL Facilities, and Distributors.
            </p>
            <form onSubmit={handleCreateLocation} className="space-y-3 mt-4 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Location ID</label>
                  <input
                    type="text"
                    required
                    placeholder="LOC-WH-DELHI"
                    value={newLoc.location_id}
                    onChange={(e) => setNewLoc({ ...newLoc, location_id: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Facility Name</label>
                  <input
                    type="text"
                    required
                    placeholder="Delhi Central Depot"
                    value={newLoc.name}
                    onChange={(e) => setNewLoc({ ...newLoc, name: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Location Type</label>
                  <select
                    value={newLoc.location_type}
                    onChange={(e) => setNewLoc({ ...newLoc, location_type: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="manufacturing_plant">Manufacturing Plant</option>
                    <option value="company_warehouse">Company Warehouse</option>
                    <option value="central_warehouse">Central Warehouse</option>
                    <option value="regional_warehouse">Regional Warehouse</option>
                    <option value="cnf_facility">C&F Facility (Depot)</option>
                    <option value="3pl_facility">3PL Facility</option>
                    <option value="distributor_warehouse">Distributor Warehouse</option>
                    <option value="retail_destination">Retail Destination</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Region</label>
                  <input
                    type="text"
                    required
                    placeholder="North / West / South"
                    value={newLoc.region}
                    onChange={(e) => setNewLoc({ ...newLoc, region: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">City</label>
                <input
                  type="text"
                  placeholder="e.g. New Delhi"
                  value={newLoc.city}
                  onChange={(e) => setNewLoc({ ...newLoc, city: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Owning Organization</label>
                  <select
                    value={newLoc.owner_org_id}
                    onChange={(e) => setNewLoc({ ...newLoc, owner_org_id: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="">-- Select Owner --</option>
                    {organizations.map((o) => (
                      <option key={o.org_id} value={o.org_id}>
                        {o.name} ({o.org_id})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Operating Organization</label>
                  <select
                    value={newLoc.operator_org_id}
                    onChange={(e) => setNewLoc({ ...newLoc, operator_org_id: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="">-- Same as Owner --</option>
                    {organizations.map((o) => (
                      <option key={o.org_id} value={o.org_id}>
                        {o.name} ({o.org_id})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Storage Capacity (Units)</label>
                  <input
                    type="number"
                    value={newLoc.storage_capacity_units}
                    onChange={(e) => setNewLoc({ ...newLoc, storage_capacity_units: Number(e.target.value) })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Daily Dispatch Cap.</label>
                  <input
                    type="number"
                    value={newLoc.dispatch_capacity_daily}
                    onChange={(e) => setNewLoc({ ...newLoc, dispatch_capacity_daily: Number(e.target.value) })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowLocModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold cursor-pointer"
                >
                  {actionLoading ? 'Saving...' : 'Save Facility'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CONFIGURE ROUTE MODAL */}
      {showRouteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="font-bold text-base text-slate-900">Configure Permitted Route</h3>
            <p className="text-xs text-slate-500 mt-1">
              Establish an eligible lane between two facilities with assigned 3PL carrier and cost rate.
            </p>
            <form onSubmit={handleCreateRoute} className="space-y-3 mt-4 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Source Facility</label>
                  <select
                    required
                    value={newRoute.from_location_id}
                    onChange={(e) => setNewRoute({ ...newRoute, from_location_id: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="">-- Select Source --</option>
                    {locations.map((l) => (
                      <option key={l.location_id} value={l.location_id}>
                        {l.name} ({l.location_id})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Destination Facility</label>
                  <select
                    required
                    value={newRoute.to_location_id}
                    onChange={(e) => setNewRoute({ ...newRoute, to_location_id: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="">-- Select Destination --</option>
                    {locations.map((l) => (
                      <option key={l.location_id} value={l.location_id}>
                        {l.name} ({l.location_id})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Assigned 3PL Carrier Agency</label>
                <select
                  value={newRoute.carrier_agency_id}
                  onChange={(e) => setNewRoute({ ...newRoute, carrier_agency_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                >
                  <option value="">-- Self Fleet / Direct Transfer --</option>
                  {organizations
                    .filter((o) => o.org_type === 'logistics_provider' || o.org_type === 'cnf_agency')
                    .map((o) => (
                      <option key={o.org_id} value={o.org_id}>
                        {o.name} ({o.org_type.replace('_', ' ')})
                      </option>
                    ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Lead Time (Days)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    required
                    value={newRoute.lead_time_days}
                    onChange={(e) => setNewRoute({ ...newRoute, lead_time_days: Number(e.target.value) })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Cost Rate (₹)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    required
                    value={newRoute.cost_rate}
                    onChange={(e) => setNewRoute({ ...newRoute, cost_rate: Number(e.target.value) })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowRouteModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold cursor-pointer"
                >
                  {actionLoading ? 'Saving...' : 'Save Route'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ADD / EDIT PRODUCT MODAL */}
      {showProductModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-md w-full p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="font-bold text-base text-slate-900">
              {editingProduct ? `Edit Product SKU: ${editingProduct.sku_id}` : 'Add New Product SKU'}
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              {editingProduct
                ? 'Update SKU specifications, category, packaging, and shelf-life policy.'
                : 'Register a finished goods item into the central FMCG product catalog.'}
            </p>
            <form onSubmit={handleSaveProduct} className="space-y-3 mt-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">SKU Code / ID</label>
                <input
                  type="text"
                  required
                  disabled={!!editingProduct}
                  placeholder="e.g. SKU-SNK-001"
                  value={productForm.sku_id}
                  onChange={(e) => setProductForm({ ...productForm, sku_id: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono disabled:bg-slate-100 disabled:text-slate-500"
                />
              </div>
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Product Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Masala Chips 50g"
                  value={productForm.name}
                  onChange={(e) => setProductForm({ ...productForm, name: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Category</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Snacks, Beverages"
                    value={productForm.category}
                    onChange={(e) => setProductForm({ ...productForm, category: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Unit of Measure</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. cases, units"
                    value={productForm.unit}
                    onChange={(e) => setProductForm({ ...productForm, unit: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Units per Case</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={productForm.case_pack}
                    onChange={(e) => setProductForm({ ...productForm, case_pack: Number(e.target.value) })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Shelf Life (Days)</label>
                  <input
                    type="number"
                    min="1"
                    placeholder="e.g. 180"
                    value={productForm.shelf_life_days ?? ''}
                    onChange={(e) =>
                      setProductForm({
                        ...productForm,
                        shelf_life_days: e.target.value ? Number(e.target.value) : null,
                      })
                    }
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowProductModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold cursor-pointer"
                >
                  {actionLoading ? 'Saving...' : editingProduct ? 'Save Changes' : 'Create Product'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT FACILITY MODAL */}
      {showEditLocModal && editingLoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
          <div className="bg-white rounded-xl shadow-xl border border-slate-200 max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
            <h3 className="font-bold text-base text-slate-900">
              Edit Facility: {editingLoc.location_id}
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Update facility capacities, operator organization, and operational status.
            </p>
            <form onSubmit={handleUpdateLocation} className="space-y-3 mt-4 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Location ID</label>
                  <input
                    type="text"
                    disabled
                    value={editingLoc.location_id}
                    className="w-full p-2 border border-slate-200 rounded-lg bg-slate-100 text-slate-500 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Facility Name</label>
                  <input
                    type="text"
                    required
                    value={editLocForm.name}
                    onChange={(e) => setEditLocForm({ ...editLocForm, name: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Location Type</label>
                  <select
                    value={editLocForm.location_type}
                    onChange={(e) => setEditLocForm({ ...editLocForm, location_type: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="manufacturing_plant">Manufacturing Plant</option>
                    <option value="company_warehouse">Company Warehouse</option>
                    <option value="central_warehouse">Central Warehouse</option>
                    <option value="regional_warehouse">Regional Warehouse</option>
                    <option value="cnf_facility">C&F Facility (Depot)</option>
                    <option value="3pl_facility">3PL Facility</option>
                    <option value="distributor_warehouse">Distributor Warehouse</option>
                    <option value="retail_destination">Retail Destination</option>
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Region</label>
                  <input
                    type="text"
                    required
                    value={editLocForm.region}
                    onChange={(e) => setEditLocForm({ ...editLocForm, region: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">City</label>
                  <input
                    type="text"
                    value={editLocForm.city}
                    onChange={(e) => setEditLocForm({ ...editLocForm, city: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Address</label>
                  <input
                    type="text"
                    value={editLocForm.address}
                    onChange={(e) => setEditLocForm({ ...editLocForm, address: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Owning Organization</label>
                  <select
                    value={editLocForm.owner_org_id}
                    onChange={(e) => setEditLocForm({ ...editLocForm, owner_org_id: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="">-- Select Owner --</option>
                    {organizations.map((o) => (
                      <option key={o.org_id} value={o.org_id}>
                        {o.name} ({o.org_id})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Operating Organization</label>
                  <select
                    value={editLocForm.operator_org_id}
                    onChange={(e) => setEditLocForm({ ...editLocForm, operator_org_id: e.target.value })}
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600"
                  >
                    <option value="">-- Same as Owner --</option>
                    {organizations.map((o) => (
                      <option key={o.org_id} value={o.org_id}>
                        {o.name} ({o.org_id})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Storage Capacity (Units)</label>
                  <input
                    type="number"
                    min="0"
                    value={editLocForm.storage_capacity_units}
                    onChange={(e) =>
                      setEditLocForm({ ...editLocForm, storage_capacity_units: Number(e.target.value) })
                    }
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Daily Dispatch Cap.</label>
                  <input
                    type="number"
                    min="0"
                    value={editLocForm.dispatch_capacity_daily}
                    onChange={(e) =>
                      setEditLocForm({ ...editLocForm, dispatch_capacity_daily: Number(e.target.value) })
                    }
                    className="w-full p-2 border border-slate-200 rounded-lg focus:outline-blue-600 font-mono"
                  />
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="loc_is_active"
                  checked={editLocForm.is_active}
                  onChange={(e) => setEditLocForm({ ...editLocForm, is_active: e.target.checked })}
                  className="rounded text-blue-600"
                />
                <label htmlFor="loc_is_active" className="font-semibold text-slate-700 cursor-pointer">
                  Facility is Operational & Active
                </label>
              </div>
              <div className="flex justify-end gap-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowEditLocModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={actionLoading}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold cursor-pointer"
                >
                  {actionLoading ? 'Saving...' : 'Update Facility'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
