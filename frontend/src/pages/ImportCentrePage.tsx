import React from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  Boxes,
  TrendingUp,
  MapPin,
  Route,
  FileCheck2,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { EmptyState } from '../components/ui/EmptyState';

export const ImportCentrePage: React.FC = () => {
  const supportedDatasets = [
    {
      id: 'products',
      title: 'Products / SKUs',
      icon: Boxes,
      requiredFields: ['sku_id', 'description', 'unit', 'case_pack', 'optional shelf_life'],
      purpose: 'Defines master product identifiers, standard case quantities, and perishable handling.',
    },
    {
      id: 'inventory',
      title: 'Current Inventory',
      icon: FileSpreadsheet,
      requiredFields: ['location_id', 'sku_id', 'on_hand', 'reserved', 'blocked', 'as_of_date'],
      purpose: 'Raw warehouse positions. Dispatchable stock is calculated as max(0, OH - Reserved - Blocked).',
    },
    {
      id: 'sales',
      title: 'Sales History',
      icon: TrendingUp,
      requiredFields: ['sku_id', 'destination_id', 'sales_date', 'quantity'],
      purpose: 'Historical daily consumption used by moving-average and seasonal-naive demand forecasts.',
    },
    {
      id: 'locations',
      title: 'Network Locations',
      icon: MapPin,
      requiredFields: ['location_id', 'name', 'location_type', 'region'],
      purpose: 'Classifies source warehouses, distributor DCs, and retail destination points.',
    },
    {
      id: 'routes',
      title: 'Permitted Transport Routes',
      icon: Route,
      requiredFields: ['from_id', 'to_id', 'lead_time_days', 'cost_rate', 'optional capacity'],
      purpose: 'Approved transit lanes, carrier cost rates, transit windows, and throughput ceilings.',
    },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">Import Centre</h1>
            <Badge variant="neutral" size="sm">Schema Specification</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Supported dataset categories, required fields, and validation pipeline contracts.
          </p>
        </div>
      </div>

      {/* Honest Scope Clarification Alert */}
      <Alert
        variant="info"
        title="Phase 1 Foundation Notice"
      >
        File parsing, schema validation, and CSV/Excel uploads are part of <strong>Phase 2 (Milestone M1)</strong>.
        In Phase 1, the dataset schemas and ingestion contracts below are formally defined and ready for the backend import pipeline.
      </Alert>

      {/* Supported Datasets Grid */}
      <div>
        <h2 className="text-base font-semibold text-[#172033] mb-4">Supported Dataset Categories</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {supportedDatasets.map((ds) => {
            const Icon = ds.icon;
            return (
              <Card key={ds.id} className="flex flex-col justify-between">
                <CardHeader>
                  <div className="flex items-center justify-between mb-2">
                    <div className="w-8 h-8 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
                      <Icon className="w-4 h-4" />
                    </div>
                    <Badge variant="neutral" size="sm">Phase 2 Ingestion</Badge>
                  </div>
                  <CardTitle>{ds.title}</CardTitle>
                  <CardDescription>{ds.purpose}</CardDescription>
                </CardHeader>
                <CardContent className="pt-2">
                  <div className="p-2.5 rounded-lg bg-slate-50 border border-slate-100 mb-3">
                    <div className="text-[11px] font-semibold text-slate-700 mb-1">Expected Fields:</div>
                    <div className="flex flex-wrap gap-1">
                      {ds.requiredFields.map((field) => (
                        <code key={field} className="text-[10px] bg-white px-1.5 py-0.5 rounded border border-slate-200 text-slate-700 font-mono">
                          {field}
                        </code>
                      ))}
                    </div>
                  </div>

                  <button
                    disabled
                    className="w-full py-2 px-3 rounded-lg border border-dashed border-slate-300 text-xs text-slate-400 bg-slate-50 flex items-center justify-center gap-1.5 cursor-not-allowed select-none"
                  >
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>Upload disabled in Phase 1</span>
                  </button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Validation Pipeline Architecture Card */}
      <Card>
        <CardHeader>
          <CardTitle>Data Integrity & Validation Rules (PRD P0-01)</CardTitle>
          <CardDescription>
            Rules enforced on every import row before creating an immutable snapshot.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="font-semibold text-slate-800 mb-1">Schema Compliance</div>
              <p className="text-slate-600 text-[11px]">Identifies missing headers, unexpected delimiters, or corrupted file encodings.</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="font-semibold text-slate-800 mb-1">Identifier Integrity</div>
              <p className="text-slate-600 text-[11px]">Rejects unmapped SKUs or unknown warehouse/retailer location references.</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="font-semibold text-slate-800 mb-1">Non-Negative Quantities</div>
              <p className="text-slate-600 text-[11px]">Flags negative quantities and unit discrepancies; no silent coercion of bad values.</p>
            </div>
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-100">
              <div className="font-semibold text-slate-800 mb-1">Row-Level Quarantining</div>
              <p className="text-slate-600 text-[11px]">Accepts valid records; generates detailed diagnostic log for rejected rows.</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Empty State */}
      <EmptyState
        icon={FileCheck2}
        title="No import batches on record"
        description="The dataset repository is currently unpopulated. When file upload is enabled in Phase 2, validated snapshots and error reports will appear here."
      />
    </div>
  );
};
