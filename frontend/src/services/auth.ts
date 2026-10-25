import { createClient } from '@supabase/supabase-js';
import type { SupabaseClient, User } from '@supabase/supabase-js';

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || '';

export type UserRole = 'admin' | 'planner' | 'logistics' | 'viewer' | 'distributor' | 'retailer';

export interface AppUser {
  id: string;
  email: string;
  role: UserRole;
  orgId?: string;
  isDemo?: boolean;
}

export const DEMO_USERS: Record<UserRole, AppUser> = {
  admin: {
    id: 'USER-ADMIN-01',
    email: 'admin@stockwise.internal',
    role: 'admin',
    orgId: 'ORG-FMCG-CORP',
    isDemo: true,
  },
  planner: {
    id: 'USER-PLANNER-01',
    email: 'planner@stockwise.internal',
    role: 'planner',
    orgId: 'ORG-FMCG-CORP',
    isDemo: true,
  },
  logistics: {
    id: 'USER-LOGISTICS-01',
    email: 'logistics@stockwise.internal',
    role: 'logistics',
    orgId: 'ORG-LOGISTICS-3PL',
    isDemo: true,
  },
  viewer: {
    id: 'USER-VIEWER-01',
    email: 'viewer@stockwise.internal',
    role: 'viewer',
    orgId: 'ORG-FMCG-CORP',
    isDemo: true,
  },
  distributor: {
    id: 'USER-DISTRIBUTOR-01',
    email: 'distributor@stockwise.internal',
    role: 'distributor',
    orgId: 'ORG-DIST-WEST',
    isDemo: true,
  },
  retailer: {
    id: 'USER-RETAILER-01',
    email: 'retailer@stockwise.internal',
    role: 'retailer',
    orgId: 'ORG-RETAIL-METRO',
    isDemo: true,
  },
};

export function isDemoAllowed(): boolean {
  return import.meta.env.DEV || import.meta.env.VITE_ENABLE_DEMO_AUTH === 'true';
}

// Initialize Supabase client if credentials are configured
export const supabase: SupabaseClient | null =
  SUPABASE_URL && SUPABASE_ANON_KEY
    ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
        },
      })
    : null;

/**
 * Returns the currently active auth token (Supabase JWT or demo bearer token).
 */
export async function getAuthToken(): Promise<string> {
  if (supabase) {
    try {
      const { data } = await supabase.auth.getSession();
      if (data?.session?.access_token) {
        return data.session.access_token;
      }
    } catch {
      // Fall through to stored demo token if permitted
    }
  }

  if (isDemoAllowed()) {
    const storedRole = (localStorage.getItem('stockwise_role') as UserRole) || 'planner';
    return `demo-${storedRole}-token`;
  }

  return '';
}

/**
 * Returns auth headers to include on backend API requests.
 */
export async function getAuthHeaders(customHeaders: Record<string, string> = {}): Promise<Record<string, string>> {
  const token = await getAuthToken();
  const headers: Record<string, string> = { ...customHeaders };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  // Only attach dev persona headers when demo auth is explicitly allowed and active
  if (isDemoAllowed() && token.startsWith('demo-')) {
    const storedRole = (localStorage.getItem('stockwise_role') as UserRole) || 'planner';
    const user = DEMO_USERS[storedRole] || DEMO_USERS.planner;
    headers['X-StockWise-Role'] = storedRole;
    headers['X-User-Id'] = user.id;
  }

  return headers;
}

/**
 * Map Supabase user object to internal AppUser model.
 * Fail-closed: Never grants privileged admin/planner roles based solely on user-editable user_metadata.
 */
export function mapSupabaseUser(user: User): AppUser {
  const email = (user.email || '').toLowerCase().trim();

  // 1. Check verified seed/bootstrap mappings matching server-side configuration
  if (email === 'admin@stockwise.internal') {
    return { id: user.id, email: user.email || '', role: 'admin', orgId: 'ORG-FMCG-CORP', isDemo: false };
  }
  if (email === 'planner@stockwise.internal') {
    return { id: user.id, email: user.email || '', role: 'planner', orgId: 'ORG-FMCG-CORP', isDemo: false };
  }
  if (email === 'logistics@stockwise.internal') {
    return { id: user.id, email: user.email || '', role: 'logistics', orgId: 'ORG-LOGISTICS-3PL', isDemo: false };
  }
  if (email === 'distributor@stockwise.internal') {
    return { id: user.id, email: user.email || '', role: 'distributor', orgId: 'ORG-DIST-WEST', isDemo: false };
  }
  if (email === 'retailer@stockwise.internal') {
    return { id: user.id, email: user.email || '', role: 'retailer', orgId: 'ORG-RETAIL-METRO', isDemo: false };
  }
  if (email === 'viewer@stockwise.internal') {
    return { id: user.id, email: user.email || '', role: 'viewer', orgId: 'ORG-FMCG-CORP', isDemo: false };
  }

  const serverRole = user.app_metadata?.role as UserRole | undefined;
  const userMetadataRole = user.user_metadata?.role as UserRole | undefined;

  let role: UserRole = 'viewer';
  if (serverRole && ['admin', 'planner', 'logistics', 'viewer', 'distributor', 'retailer'].includes(serverRole)) {
    role = serverRole;
  } else if (userMetadataRole === 'viewer') {
    role = 'viewer';
  } else {
    // If client supplied user_metadata has a privileged role without app_metadata, demote to viewer
    role = 'viewer';
  }

  const defaultOrg = role === 'distributor'
    ? 'ORG-DIST-WEST'
    : role === 'retailer'
    ? 'ORG-RETAIL-METRO'
    : role === 'logistics'
    ? 'ORG-LOGISTICS-3PL'
    : 'ORG-FMCG-CORP';

  const orgId = user.app_metadata?.org_id || defaultOrg;
  return {
    id: user.id,
    email: user.email || '',
    role,
    orgId,
    isDemo: false,
  };
}

/**
 * Downloads a protected CSV or file using authenticated fetch and triggers browser download.
 */
export async function downloadAuthenticatedFile(url: string, filename: string): Promise<void> {
  const headers = await getAuthHeaders();
  const res = await fetch(url, { headers });
  if (!res.ok) {
    throw new Error(`Download failed with status ${res.status}: ${res.statusText}`);
  }
  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

/**
 * Installs a global fetch interceptor that automatically attaches Authorization Bearer
 * tokens and role context to all outgoing backend API requests.
 */
let interceptorInstalled = false;
export function setupAuthInterceptor() {
  if (interceptorInstalled || typeof window === 'undefined') return;
  interceptorInstalled = true;

  const originalFetch = window.fetch;
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const urlStr =
      typeof input === 'string'
        ? input
        : input instanceof URL
        ? input.toString()
        : input.url;

    if (urlStr.includes('/api')) {
      try {
        const authHeaders = await getAuthHeaders();
        const headers = new Headers(init?.headers || {});
        for (const [key, value] of Object.entries(authHeaders)) {
          if (!headers.has(key)) {
            headers.set(key, value);
          }
        }
        return originalFetch(input, { ...init, headers });
      } catch (err) {
        console.error('Failed to attach auth headers:', err);
      }
    }
    return originalFetch(input, init);
  };
}

// Auto-initialize interceptor on load
setupAuthInterceptor();

