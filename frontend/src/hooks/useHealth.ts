import { useState, useEffect, useCallback } from 'react';
import type { HealthResponse } from '../types/api';
import { getSystemHealth, ApiError } from '../services/api';

export interface UseHealthReturn {
  data: HealthResponse | null;
  loading: boolean;
  error: string | null;
  lastChecked: Date | null;
  refetch: () => Promise<void>;
}

export function useHealth(pollIntervalMs: number = 30000): UseHealthReturn {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getSystemHealth();
      setData(response);
      setError(null);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Unable to connect to backend service');
      }
    } finally {
      setLoading(false);
      setLastChecked(new Date());
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    getSystemHealth()
      .then((res) => {
        if (isMounted) {
          setData(res);
          setError(null);
          setLoading(false);
          setLastChecked(new Date());
        }
      })
      .catch((err: unknown) => {
        if (isMounted) {
          const msg = err instanceof Error ? err.message : 'Unable to connect to backend service';
          setError(msg);
          setLoading(false);
          setLastChecked(new Date());
        }
      });

    if (pollIntervalMs > 0) {
      const interval = setInterval(fetchStatus, pollIntervalMs);
      return () => {
        isMounted = false;
        clearInterval(interval);
      };
    }
    return () => {
      isMounted = false;
    };
  }, [fetchStatus, pollIntervalMs]);

  return {
    data,
    loading,
    error,
    lastChecked,
    refetch: fetchStatus,
  };
}
