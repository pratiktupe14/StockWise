import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Boxes, Search, Filter, UploadCloud } from 'lucide-react';
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
import type { InventoryRecord } from '../types/inventory';

export const InventoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLocation, setSelectedLocation] = useState('all');

  // Honest state: zero rows until Phase 2 dataset import
  const inventoryData: InventoryRecord[] = [];

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">Inventory Visibility</h1>
            <Badge variant="neutral" size="sm">Schema Ready</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Multi-location stock balances with mathematically isolated dispatchable quantities.
          </p>
        </div>

        <Button
          variant="primary"
          leftIcon={<UploadCloud className="w-4 h-4" />}
          onClick={() => navigate('/imports')}
        >
          Import Inventory
        </Button>
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
            In-transit units are excluded until confirmed ETA.
          </span>
        </div>
      </Alert>

      {/* Controls: Search & Location filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="relative w-full sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search by SKU or product name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E5E7EB] bg-white text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
            />
          </div>

          <div className="flex items-center gap-2 w-full sm:w-auto">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={selectedLocation}
              onChange={(e) => setSelectedLocation(e.target.value)}
              className="text-xs px-3 py-1.5 rounded-lg border border-[#E5E7EB] bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-600 cursor-pointer"
            >
              <option value="all">All Locations (Source & Destination)</option>
              <option value="central">Central Warehouses</option>
              <option value="regional">Regional DCs</option>
              <option value="distributor">Distributor Nodes</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Structured Table Layout with Column Definitions */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>SKU Identifier</TableHead>
            <TableHead>Product Description</TableHead>
            <TableHead>Location</TableHead>
            <TableHead className="text-right">On-Hand</TableHead>
            <TableHead className="text-right">Reserved</TableHead>
            <TableHead className="text-right">Blocked</TableHead>
            <TableHead className="text-right bg-blue-50/50 text-blue-900 font-bold">
              Dispatchable Stock
            </TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {inventoryData.length > 0 ? (
            inventoryData.map((item) => (
              <TableRow key={`${item.location}-${item.sku}`}>
                <TableCell className="font-mono font-medium">{item.sku}</TableCell>
                <TableCell>{item.productName}</TableCell>
                <TableCell>{item.location}</TableCell>
                <TableCell className="text-right font-mono">{item.onHand.toLocaleString()}</TableCell>
                <TableCell className="text-right font-mono text-amber-600">{item.reserved.toLocaleString()}</TableCell>
                <TableCell className="text-right font-mono text-rose-600">{item.blocked.toLocaleString()}</TableCell>
                <TableCell className="text-right font-mono font-bold text-blue-700 bg-blue-50/30">
                  {item.dispatchable.toLocaleString()}
                </TableCell>
                <TableCell>
                  <Badge variant={item.dispatchable > 0 ? 'success' : 'critical'}>
                    {item.dispatchable > 0 ? 'Available' : 'Depleted'}
                  </Badge>
                </TableCell>
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={8} className="p-0">
                <EmptyState
                  icon={Boxes}
                  title="No inventory records available"
                  description="The inventory database is currently empty. Ingest an inventory snapshot via the Import Centre to calculate on-hand, reserved, and dispatchable balances."
                  actionLabel="Go to Import Centre"
                  onAction={() => navigate('/imports')}
                  className="border-0 rounded-none py-12"
                />
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
};
