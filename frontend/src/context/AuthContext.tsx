import React, { createContext, useContext, useState, useEffect } from 'react';
import { supabase, DEMO_USERS, mapSupabaseUser, isDemoAllowed } from '../services/auth';
import type { AppUser, UserRole } from '../services/auth';

const GUEST_USER: AppUser = {
  id: '',
  email: '',
  role: 'viewer',
  isDemo: false,
};

interface AuthContextType {
  user: AppUser;
  role: UserRole;
  isAuthenticated: boolean;
  isSupabaseConfigured: boolean;
  loading: boolean;
  switchRole: (newRole: UserRole) => void;
  loginWithSupabase: (email: string, password: string) => Promise<{ error?: string }>;
  signUpWithSupabase: (email: string, password: string, role?: UserRole) => Promise<{ error?: string }>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [role, setRole] = useState<UserRole>(() => {
    return (localStorage.getItem('stockwise_role') as UserRole) || 'planner';
  });
  const [user, setUser] = useState<AppUser>(() => {
    if (isDemoAllowed()) {
      return DEMO_USERS[role] || DEMO_USERS.planner;
    }
    return GUEST_USER;
  });
  const [loading, setLoading] = useState<boolean>(true);
  const isSupabaseConfigured = Boolean(supabase);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    // Check existing Supabase session
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session?.user) {
        const appUser = mapSupabaseUser(session.user);
        setUser(appUser);
        setRole(appUser.role);
        localStorage.setItem('stockwise_role', appUser.role);
      } else if (!isDemoAllowed()) {
        setUser(GUEST_USER);
      }
      setLoading(false);
    });

    // Listen for auth state transitions
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        const appUser = mapSupabaseUser(session.user);
        setUser(appUser);
        setRole(appUser.role);
        localStorage.setItem('stockwise_role', appUser.role);
      } else {
        localStorage.removeItem('stockwise_role');
        if (isDemoAllowed()) {
          const fallbackRole = (localStorage.getItem('stockwise_role') as UserRole) || 'planner';
          setRole(fallbackRole);
          setUser(DEMO_USERS[fallbackRole] || DEMO_USERS.planner);
        } else {
          setRole('viewer');
          setUser(GUEST_USER);
        }
      }
      setLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, []);

  const switchRole = (newRole: UserRole) => {
    if (!isDemoAllowed() || !user.isDemo) {
      console.warn('Role switching is disabled for verified production sessions.');
      return;
    }
    setRole(newRole);
    localStorage.setItem('stockwise_role', newRole);
    setUser(DEMO_USERS[newRole]);
  };

  const loginWithSupabase = async (email: string, password: string) => {
    if (!supabase) return { error: 'Supabase is not configured' };
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) return { error: error.message };
    if (data.user) {
      const appUser = mapSupabaseUser(data.user);
      setUser(appUser);
      setRole(appUser.role);
      localStorage.setItem('stockwise_role', appUser.role);
    }
    return {};
  };

  const signUpWithSupabase = async (email: string, password: string, assignedRole: UserRole = 'planner') => {
    if (!supabase) return { error: 'Supabase is not configured' };
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          role: assignedRole,
          org_id: 'ORG-FMCG-CORP',
        },
      },
    });
    if (error) return { error: error.message };
    if (data.user) {
      const appUser = mapSupabaseUser(data.user);
      setUser(appUser);
      setRole(appUser.role);
    }
    return {};
  };

  const logout = async () => {
    if (supabase) {
      await supabase.auth.signOut();
    }
    localStorage.removeItem('stockwise_role');
    if (isDemoAllowed()) {
      const defaultRole: UserRole = 'planner';
      setRole(defaultRole);
      setUser(DEMO_USERS[defaultRole]);
    } else {
      setRole('viewer');
      setUser(GUEST_USER);
    }
  };

  const isAuthenticated = user.isDemo ? isDemoAllowed() : Boolean(user.id);

  return (
    <AuthContext.Provider
      value={{
        user,
        role,
        isAuthenticated,
        isSupabaseConfigured,
        loading,
        switchRole,
        loginWithSupabase,
        signUpWithSupabase,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
