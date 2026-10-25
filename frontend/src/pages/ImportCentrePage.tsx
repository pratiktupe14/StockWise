import React, { useState, useEffect, useRef } from 'react';
import {
  UploadCloud,
  FileSpreadsheet,
  Boxes,
  TrendingUp,
  MapPin,
  Route,
  FileCheck2,
  AlertCircle,
  CheckCircle2,
  Download,
  RefreshCw,
  AlertTriangle,
  FileText,
  XCircle,
  Building2,
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Alert } from '../components/ui/Alert';
import { Button } from '../components/ui/Button';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '../components/ui/Table';
import { EmptyState } from '../components/ui/EmptyState';
import {
  uploadDataset,
  previewDataset,
  getImportErrorsCSVUrl,
  getImportRuns,
  getImportRunErrors,
  getTemplateDownloadUrl,
  ApiError,
} from '../services/api';
import { downloadAuthenticatedFile } from '../services/auth';
import type {
  DatasetType,
  ImportRunSummary,
  ImportRowError,
} from '../types/api';

interface DatasetMeta {
  id: DatasetType;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  requiredFields: string[];
  purpose: string;
}

const DATASETS: DatasetMeta[] = [
  {
    id: 'products',
    title: 'Products / SKUs',
    icon: Boxes,
    requiredFields: ['sku_id', 'name', 'unit', 'case_pack', 'category (opt)', 'shelf_life_days (opt)'],
    purpose: 'Master product identifiers, standard case packaging, and perishable shelf-life days.',
  },
  {
    id: 'locations',
    title: 'Network Locations',
    icon: MapPin,
    requiredFields: ['location_id', 'name', 'location_type', 'region', 'city (opt)', 'address (opt)'],
    purpose: 'Classifies plant sources, regional distribution centers (RDC), and retail destination hubs.',
  },
  {
    id: 'inventory',
    title: 'Inventory Snapshots',
    icon: FileSpreadsheet,
    requiredFields: ['snapshot_id', 'as_of_date', 'location_id', 'sku_id', 'on_hand', 'reserved', 'blocked'],
    purpose: 'Warehouse stock balances. Dispatchable stock is calculated as max(0, OH - Reserved - Blocked).',
  },
  {
    id: 'sales',
    title: 'Sales History',
    icon: TrendingUp,
    requiredFields: ['sales_date', 'location_id', 'sku_id', 'units_sold'],
    purpose: 'Historical daily SKU-location demand observations used for baseline consumption analysis.',
  },
  {
    id: 'routes',
    title: 'Permitted Routes & Rates',
    icon: Route,
    requiredFields: ['from_location_id', 'to_location_id', 'lead_time_days', 'cost_rate', 'carrier_agency_id (opt)', 'capacity_units (opt)'],
    purpose: 'Approved transit corridors, carrier freight costs per unit, and transport lead times.',
  },
  {
    id: 'organizations',
    title: 'Organizations & Partners',
    icon: Building2,
    requiredFields: ['org_id', 'name', 'org_type', 'contact_email (opt)', 'contact_phone (opt)'],
    purpose: 'Registers FMCG brand owners, C&F agencies, 3PL logistics carriers, and independent distributors.',
  },
];

export const ImportCentrePage: React.FC = () => {
  const [selectedDataset, setSelectedDataset] = useState<DatasetType>('products');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Active or most recent import run result
  const [latestRun, setLatestRun] = useState<ImportRunSummary | null>(null);
  const [selectedRunErrors, setSelectedRunErrors] = useState<ImportRowError[]>([]);
  const [inspectingRunId, setInspectingRunId] = useState<string | null>(null);

  // Import run history
  const [history, setHistory] = useState<ImportRunSummary[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeDatasetMeta = DATASETS.find((d) => d.id === selectedDataset) || DATASETS[0];

  const fetchHistory = async () => {
    setLoadingHistory(true);
    try {
      const data = await getImportRuns();
      setHistory(data.runs);
    } catch {
      // Ignore background refresh errors
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      const ext = file.name.split('.').pop()?.toLowerCase();
      if (ext !== 'csv' && ext !== 'xlsx') {
        setUploadError('Only CSV (.csv) and Excel (.xlsx) files are supported.');
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setUploadError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const summary = await uploadDataset(selectedDataset, selectedFile);
      setLatestRun(summary);
      setSelectedRunErrors(summary.errors || []);

      // Reset file input
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';

      // Refresh history list
      fetchHistory();
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setUploadError(err.message);
      } else if (err instanceof Error) {
        setUploadError(err.message);
      } else {
        setUploadError('File upload and validation failed');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const [previewSummary, setPreviewSummary] = useState<ImportRunSummary | null>(null);
  const [isPreviewing, setIsPreviewing] = useState<boolean>(false);

  const handlePreview = async () => {
    if (!selectedFile) return;
    setIsPreviewing(true);
    setUploadError(null);
    try {
      const summary = await previewDataset(selectedDataset, selectedFile);
      setPreviewSummary(summary);
      setSelectedRunErrors(summary.errors || []);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setUploadError(err.message);
      } else if (err instanceof Error) {
        setUploadError(err.message);
      } else {
        setUploadError('Dataset preview validation failed');
      }
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleInspectRun = async (run: ImportRunSummary) => {
    setLatestRun(run);
    setInspectingRunId(run.run_id);
    try {
      const errors = await getImportRunErrors(run.run_id);
      setSelectedRunErrors(errors);
    } catch {
      setSelectedRunErrors(run.errors || []);
    } finally {
      setInspectingRunId(null);
    }
  };

  const handleDownloadErrorReport = () => {
    if (!latestRun || selectedRunErrors.length === 0) return;

    if (latestRun.run_id && !latestRun.run_id.startsWith('preview-')) {
      downloadAuthenticatedFile(
        getImportErrorsCSVUrl(latestRun.run_id),
        `validation_errors_${latestRun.dataset_type}_${latestRun.run_id.slice(0, 8)}.csv`
      );
      return;
    }

    const headers = ['Row', 'Field', 'Rejected Value', 'Error Reason', 'Error Code'];
    const rows = selectedRunErrors.map((err) => [
      err.row_index,
      err.field_name || '',
      `"${(err.rejected_value || '').replace(/"/g, '""')}"`,
      `"${(err.error_reason || '').replace(/"/g, '""')}"`,
      err.error_code || '',
    ]);

    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `validation_errors_${latestRun.dataset_type}_${latestRun.run_id.slice(0, 8)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-8 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#E5E7EB]">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold text-[#172033] tracking-tight">Import Centre</h1>
            <Badge variant="success" size="sm">Phase 2 Active</Badge>
          </div>
          <p className="text-sm text-[#667085]">
            Ingest, validate, quarantine, and persist FMCG supply chain datasets with row-level integrity checks.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchHistory}
            isLoading={loadingHistory}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
          >
            Refresh History
          </Button>
        </div>
      </div>

      {/* Dataset Selection Tabs */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#172033] uppercase tracking-wider">Select Dataset Category</h2>
          <span className="text-xs text-[#667085]">Strict foreign key order: Products & Locations must be imported first</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {DATASETS.map((ds) => {
            const Icon = ds.icon;
            const isSelected = selectedDataset === ds.id;
            return (
              <button
                key={ds.id}
                onClick={() => {
                  setSelectedDataset(ds.id);
                  setSelectedFile(null);
                  setUploadError(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
                className={`p-3.5 rounded-xl border text-left transition-all flex flex-col justify-between ${
                  isSelected
                    ? 'border-blue-600 bg-blue-50/60 shadow-sm ring-1 ring-blue-600'
                    : 'border-[#E5E7EB] bg-white hover:border-slate-300 hover:bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div
                    className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                      isSelected ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  {isSelected && (
                    <span className="w-2 h-2 rounded-full bg-blue-600"></span>
                  )}
                </div>
                <div>
                  <div className={`text-xs font-semibold ${isSelected ? 'text-blue-900' : 'text-slate-800'}`}>
                    {ds.title}
                  </div>
                  <div className="text-[11px] text-[#667085] mt-0.5 line-clamp-1">{ds.id}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active Dataset Ingestion Card */}
      <Card className="border-slate-200">
        <CardHeader className="border-b border-slate-100 pb-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <CardTitle className="text-base font-semibold text-slate-900">
                  Import {activeDatasetMeta.title}
                </CardTitle>
                <Badge variant="neutral" size="sm">.csv or .xlsx</Badge>
              </div>
              <CardDescription className="text-xs">
                {activeDatasetMeta.purpose}
              </CardDescription>
            </div>

            {/* Template Download Links */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 font-medium">Templates:</span>
              <a
                href={getTemplateDownloadUrl(selectedDataset, 'csv')}
                download
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 hover:text-blue-600 transition-colors"
                title="Download CSV sample format"
              >
                <Download className="w-3.5 h-3.5" />
                CSV
              </a>
              <a
                href={getTemplateDownloadUrl(selectedDataset, 'xlsx')}
                download
                className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 hover:text-blue-600 transition-colors"
                title="Download Excel sample format"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                Excel (.xlsx)
              </a>
            </div>
          </div>
        </CardHeader>

        <CardContent className="pt-6 space-y-6">
          {/* Required Fields Pill List */}
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 flex flex-col sm:flex-row sm:items-center gap-2 text-xs">
            <span className="font-semibold text-slate-700 shrink-0">Required & Canonical Columns:</span>
            <div className="flex flex-wrap gap-1.5">
              {activeDatasetMeta.requiredFields.map((col) => {
                const isOpt = col.includes('(opt)');
                return (
                  <code
                    key={col}
                    className={`px-2 py-0.5 rounded font-mono text-[11px] ${
                      isOpt
                        ? 'bg-slate-100 text-slate-500 border border-slate-200'
                        : 'bg-blue-50 text-blue-700 border border-blue-200 font-semibold'
                    }`}
                  >
                    {col}
                  </code>
                );
              })}
            </div>
          </div>

          {/* File Upload Area */}
          <div className="flex flex-col sm:flex-row items-center gap-4">
            <div className="flex-1 w-full">
              <label
                htmlFor="dataset-file-input"
                className={`flex flex-col items-center justify-center border-2 border-dashed rounded-xl p-6 cursor-pointer transition-colors ${
                  selectedFile
                    ? 'border-blue-400 bg-blue-50/30'
                    : 'border-slate-300 hover:border-blue-400 bg-white'
                }`}
              >
                <UploadCloud className={`w-8 h-8 mb-2 ${selectedFile ? 'text-blue-600' : 'text-slate-400'}`} />
                <span className="text-xs font-medium text-slate-700">
                  {selectedFile ? (
                    <span className="text-blue-700 font-semibold">{selectedFile.name}</span>
                  ) : (
                    'Click to select or drag and drop CSV / Excel file'
                  )}
                </span>
                <span className="text-[11px] text-slate-400 mt-1">
                  {selectedFile
                    ? `${(selectedFile.size / 1024).toFixed(1)} KB`
                    : 'Max file size 10MB • Enforces strict row validation'}
                </span>
                <input
                  id="dataset-file-input"
                  ref={fileInputRef}
                  type="file"
                  accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </label>
            </div>

            <div className="flex flex-col gap-2 w-full sm:w-auto shrink-0">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  onClick={handlePreview}
                  disabled={!selectedFile || isPreviewing || isUploading}
                  isLoading={isPreviewing}
                  leftIcon={<FileCheck2 className="w-4 h-4 text-blue-600" />}
                  className="w-full sm:w-auto text-xs"
                >
                  {isPreviewing ? 'Validating Preview...' : 'Preview Validation'}
                </Button>
                <Button
                  variant="primary"
                  onClick={handleUpload}
                  disabled={!selectedFile || isUploading || isPreviewing}
                  isLoading={isUploading}
                  leftIcon={<UploadCloud className="w-4 h-4" />}
                  className="w-full sm:w-auto text-xs"
                >
                  {isUploading ? 'Committing...' : 'Commit Import'}
                </Button>
              </div>
              {selectedFile && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedFile(null);
                    setPreviewSummary(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                  }}
                  className="text-slate-500 hover:text-slate-700 text-xs"
                >
                  Clear Selection
                </Button>
              )}
            </div>
          </div>

          {/* Pre-Commit Preview Summary Banner */}
          {previewSummary && (
            <div className="p-4 bg-blue-50/80 border border-blue-200 rounded-lg text-xs space-y-2">
              <div className="flex items-center justify-between font-semibold text-blue-900">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-blue-600" />
                  Pre-Commit Preview Mode (Master Database Unchanged)
                </span>
                <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                  previewSummary.status === 'preview_valid'
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-amber-100 text-amber-800'
                }`}>
                  {previewSummary.status}
                </span>
              </div>
              <p className="text-blue-800">
                Total Rows: <strong>{previewSummary.total_rows}</strong> • Valid Rows: <strong className="text-emerald-700">{previewSummary.valid_rows}</strong> • Rejected Rows: <strong className="text-rose-700">{previewSummary.rejected_rows}</strong>.
                {previewSummary.rejected_rows === 0
                  ? ' All rows satisfy foreign key references, types, and constraints.'
                  : ' Review errors below. Master records have not been committed.'}
              </p>
            </div>
          )}

          {/* Upload Error Banner */}
          {uploadError && (
            <Alert variant="error" title="Import Error">
              {uploadError}
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Validation Summary & Diagnostics Section */}
      {latestRun && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">
              Validation & Persistence Results
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Run ID:</span>
              <code className="text-xs bg-slate-100 px-2 py-0.5 rounded font-mono text-slate-700">
                {latestRun.run_id.slice(0, 12)}...
              </code>
            </div>
          </div>

          {/* Metrics summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="p-4 bg-white border-slate-200">
              <div className="text-xs text-slate-500 font-medium">Dataset / File</div>
              <div className="text-sm font-semibold text-slate-900 mt-1 capitalize">
                {latestRun.dataset_type}
              </div>
              <div className="text-[11px] text-slate-500 truncate mt-0.5" title={latestRun.filename}>
                {latestRun.filename} ({latestRun.file_format.toUpperCase()})
              </div>
            </Card>

            <Card className="p-4 bg-white border-slate-200">
              <div className="text-xs text-slate-500 font-medium">Execution Status</div>
              <div className="mt-1.5 flex items-center gap-1.5">
                {latestRun.status === 'completed' && (
                  <Badge variant="success" size="md">
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1 inline" /> Completed
                  </Badge>
                )}
                {latestRun.status === 'partial' && (
                  <Badge variant="warning" size="md">
                    <AlertTriangle className="w-3.5 h-3.5 mr-1 inline" /> Partial (Quarantined)
                  </Badge>
                )}
                {latestRun.status === 'failed' && (
                  <Badge variant="critical" size="md">
                    <XCircle className="w-3.5 h-3.5 mr-1 inline" /> Failed
                  </Badge>
                )}
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                {new Date(latestRun.created_at).toLocaleTimeString()}
              </div>
            </Card>

            <Card className="p-4 bg-white border-slate-200">
              <div className="text-xs text-slate-500 font-medium">Valid & Persisted Rows</div>
              <div className="text-2xl font-bold text-emerald-600 mt-1">
                {latestRun.valid_rows}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                out of {latestRun.total_rows} total rows
              </div>
            </Card>

            <Card className="p-4 bg-white border-slate-200">
              <div className="text-xs text-slate-500 font-medium">Rejected (Quarantined)</div>
              <div className={`text-2xl font-bold mt-1 ${latestRun.rejected_rows > 0 ? 'text-amber-600' : 'text-slate-400'}`}>
                {latestRun.rejected_rows}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {latestRun.rejected_rows > 0 ? 'Not written to operational tables' : 'Zero validation violations'}
              </div>
            </Card>
          </div>

          {/* Missing Column Alert Banner */}
          {selectedRunErrors.some((e) => e.error_code === 'MISSING_COLUMN') && (
            <Alert variant="error" title="Missing Required Header Column">
              The uploaded file header is missing one or more required columns. For {activeDatasetMeta.title}, required columns are:{' '}
              <strong>{activeDatasetMeta.requiredFields.filter(f => !f.includes('(opt)')).join(', ')}</strong>.
              Please verify your column headers or download the official template from the top-right buttons.
            </Alert>
          )}

          {/* Row-Level Errors Table */}
          {selectedRunErrors.length > 0 ? (
            <Card className="border-amber-200 bg-amber-50/20">
              <CardHeader className="border-b border-amber-100/60 pb-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 text-amber-600" />
                    <CardTitle className="text-sm font-semibold text-slate-900">
                      Row-Level Validation Diagnostics ({selectedRunErrors.length} issues)
                    </CardTitle>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadErrorReport}
                    leftIcon={<Download className="w-3.5 h-3.5 text-slate-600" />}
                  >
                    Download Error Report (.csv)
                  </Button>
                </div>
                <CardDescription className="text-xs text-slate-600 mt-1">
                  Rejected rows are quarantined and not persisted into production tables. Fix these rows and re-upload.
                </CardDescription>
              </CardHeader>

              <CardContent className="p-0">
                <div className="max-h-80 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-20">Row #</TableHead>
                        <TableHead className="w-36">Field</TableHead>
                        <TableHead className="w-44">Rejected Value</TableHead>
                        <TableHead>Error Reason</TableHead>
                        <TableHead className="w-32">Error Code</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {selectedRunErrors.map((err, idx) => (
                        <TableRow key={idx} className="hover:bg-amber-50/40">
                          <TableCell className="font-mono text-xs font-semibold text-slate-700">
                            Line {err.row_index}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-slate-800">
                            {err.field_name || '—'}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-red-700 bg-red-50/50 rounded">
                            {err.rejected_value !== null && err.rejected_value !== undefined ? (
                              <span className="truncate block max-w-[150px]" title={err.rejected_value}>
                                {err.rejected_value}
                              </span>
                            ) : (
                              <span className="text-slate-400 italic">null/empty</span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs text-slate-700">
                            {err.error_reason}
                          </TableCell>
                          <TableCell>
                            <Badge variant="neutral" size="sm" className="font-mono text-[10px]">
                              {err.error_code || 'INVALID'}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          ) : (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-100 flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
              <div className="text-xs text-emerald-900">
                <strong className="font-semibold">All rows passed validation.</strong> {latestRun.valid_rows} records successfully persisted to the operational database with zero quarantine rejections.
              </div>
            </div>
          )}
        </div>
      )}

      {/* Historical Import Runs */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Import Run History</h2>
            <p className="text-xs text-slate-500">
              Audit log of persisted dataset versions and snapshot identifiers.
            </p>
          </div>
          <span className="text-xs text-slate-500 font-medium">
            {history.length} runs recorded
          </span>
        </div>

        {history.length === 0 ? (
          <EmptyState
            icon={FileCheck2}
            title="No import batches on record"
            description="The dataset repository is currently unpopulated. Select a dataset category and upload a CSV or Excel file above to begin."
          />
        ) : (
          <Card className="border-slate-200">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Dataset</TableHead>
                  <TableHead>File Name</TableHead>
                  <TableHead>Format</TableHead>
                  <TableHead>Total Rows</TableHead>
                  <TableHead>Valid / Rejected</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Imported At</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((run) => (
                  <TableRow key={run.run_id}>
                    <TableCell className="font-medium text-slate-900 capitalize flex items-center gap-1.5">
                      <FileText className="w-3.5 h-3.5 text-blue-600" />
                      {run.dataset_type}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-700 truncate max-w-[180px]" title={run.filename}>
                      {run.filename}
                    </TableCell>
                    <TableCell>
                      <Badge variant="neutral" size="sm" className="uppercase font-mono text-[10px]">
                        {run.file_format}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-700">
                      {run.total_rows}
                    </TableCell>
                    <TableCell className="text-xs">
                      <span className="text-emerald-700 font-semibold">{run.valid_rows}</span>
                      <span className="text-slate-400"> / </span>
                      <span className={run.rejected_rows > 0 ? 'text-amber-600 font-semibold' : 'text-slate-400'}>
                        {run.rejected_rows}
                      </span>
                    </TableCell>
                    <TableCell>
                      {run.status === 'completed' && <Badge variant="success" size="sm">Completed</Badge>}
                      {run.status === 'partial' && <Badge variant="warning" size="sm">Partial</Badge>}
                      {run.status === 'failed' && <Badge variant="critical" size="sm">Failed</Badge>}
                    </TableCell>
                    <TableCell className="text-xs text-slate-500">
                      {new Date(run.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleInspectRun(run)}
                        isLoading={inspectingRunId === run.run_id}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        Inspect
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
        )}
      </div>
    </div>
  );
};
