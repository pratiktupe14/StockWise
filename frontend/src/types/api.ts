export interface DatabaseHealth {
  connected: boolean;
  status: 'connected' | 'disconnected';
  message: string;
  dialect: string;
  latency_ms: number | null;
}

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  app_name: string;
  tagline: string;
  version: string;
  environment: string;
  timestamp: string;
  api: string;
  database: DatabaseHealth;
}

export interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  lastChecked: Date | null;
}
