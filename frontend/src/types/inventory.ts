export interface InventoryRecord {
  sku: string;
  productName: string;
  category?: string;
  location: string;
  onHand: number;
  reserved: number;
  blocked: number;
  dispatchable: number;
  unit: string;
  lastUpdated?: string;
}

export interface InventoryFilterOptions {
  searchQuery: string;
  locationFilter: string;
  categoryFilter: string;
  stockStatus: 'all' | 'dispatchable' | 'zero-stock' | 'reserved';
}
