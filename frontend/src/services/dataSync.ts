import { useEffect, useRef, useState, useCallback } from 'react';
import type { DatasetType, ImportRunSummary } from '../types/api';

export interface DatasetSyncRecord {
  datasetType: DatasetType;
  lastImportedAt: string;
  runId: string;
  filename: string;
  validRows: number;
  insertedRows: number;
  updatedRows: number;
}

const STORAGE_KEY = 'stockwise_dataset_sync';
const SYNC_EVENT_NAME = 'stockwise:dataset-sync';

/**
 * Retrieves the persisted map of dataset sync metadata.
 */
export function getAllDatasetSyncRecords(): Record<string, DatasetSyncRecord> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

/**
 * Retrieves the latest import metadata for a specific dataset type or the overall newest.
 */
export function getLatestDatasetSyncInfo(datasetType?: DatasetType): DatasetSyncRecord | null {
  const records = getAllDatasetSyncRecords();
  if (datasetType) {
    return records[datasetType] || null;
  }
  const allRecords = Object.values(records);
  if (allRecords.length === 0) return null;
  return allRecords.reduce((latest, current) => {
    return new Date(current.lastImportedAt) > new Date(latest.lastImportedAt) ? current : latest;
  }, allRecords[0]);
}

/**
 * Broadcasts a dataset update to all open pages and stores the sync metadata.
 */
export function broadcastDatasetImport(summary: ImportRunSummary): void {
  const record: DatasetSyncRecord = {
    datasetType: summary.dataset_type,
    lastImportedAt: summary.created_at || new Date().toISOString(),
    runId: summary.run_id,
    filename: summary.filename,
    validRows: summary.valid_rows,
    insertedRows: summary.inserted_rows ?? summary.valid_rows,
    updatedRows: summary.updated_rows ?? 0,
  };

  try {
    const records = getAllDatasetSyncRecords();
    records[summary.dataset_type] = record;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records));
  } catch {
    // Ignore localStorage quota errors
  }

  // Dispatch cross-component DOM event
  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(SYNC_EVENT_NAME, {
        detail: {
          datasetType: summary.dataset_type,
          record,
          timestamp: Date.now(),
        },
      })
    );
  }
}

/**
 * React hook that subscribes a page to updates for specific dataset categories.
 * Automatically triggers `onRefresh` when:
 * 1. A new import completes in the Import Centre while the page is mounted.
 * 2. Navigating to the page after a newer import has occurred.
 * Prevents duplicate refetch loops via timestamp debouncing.
 */
export function useDatasetSync(
  relevantDatasets: DatasetType[],
  onRefresh: () => Promise<void> | void
) {
  const [lastSyncRecord, setLastSyncRecord] = useState<DatasetSyncRecord | null>(() => {
    const all = getAllDatasetSyncRecords();
    for (const d of relevantDatasets) {
      if (all[d]) return all[d];
    }
    return null;
  });

  const lastProcessedTimeRef = useRef<number>(Date.now());
  const onRefreshRef = useRef(onRefresh);
  onRefreshRef.current = onRefresh;

  // Check staleness on mount/navigation
  useEffect(() => {
    const all = getAllDatasetSyncRecords();
    let hasNewer = false;
    let newestRecord: DatasetSyncRecord | null = null;

    for (const d of relevantDatasets) {
      const rec = all[d];
      if (rec) {
        const importTime = new Date(rec.lastImportedAt).getTime();
        if (importTime > lastProcessedTimeRef.current) {
          hasNewer = true;
          if (!newestRecord || importTime > new Date(newestRecord.lastImportedAt).getTime()) {
            newestRecord = rec;
          }
        }
      }
    }

    if (hasNewer && newestRecord) {
      setLastSyncRecord(newestRecord);
      lastProcessedTimeRef.current = Date.now();
      void onRefreshRef.current();
    }
  }, [relevantDatasets]);

  // Subscribe to live broadcast events
  useEffect(() => {
    const handleEvent = (event: Event) => {
      const customEvent = event as CustomEvent<{
        datasetType: DatasetType;
        record: DatasetSyncRecord;
        timestamp: number;
      }>;
      const { datasetType, record } = customEvent.detail;

      if (relevantDatasets.includes(datasetType) || datasetType === ('all' as any)) {
        setLastSyncRecord(record);
        lastProcessedTimeRef.current = Date.now();
        void onRefreshRef.current();
      }
    };

    window.addEventListener(SYNC_EVENT_NAME, handleEvent);
    return () => {
      window.removeEventListener(SYNC_EVENT_NAME, handleEvent);
    };
  }, [relevantDatasets]);

  const triggerManualSync = useCallback(async () => {
    lastProcessedTimeRef.current = Date.now();
    await onRefreshRef.current();
  }, []);

  const formattedSyncTime = lastSyncRecord
    ? new Date(lastSyncRecord.lastImportedAt).toLocaleTimeString()
    : null;

  return {
    lastSyncRecord,
    lastSyncedAt: lastSyncRecord?.lastImportedAt || null,
    dataset: lastSyncRecord?.datasetType || null,
    formattedSyncTime,
    triggerManualSync,
  };
}
