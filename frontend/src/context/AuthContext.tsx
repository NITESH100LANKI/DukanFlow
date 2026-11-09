import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiClient from '../api/client';
import {
  CurrentUser,
  verifyOtp,
  deskLogin,
  logoutApi,
  refreshToken,
  getMe,
} from '../api/auth';

interface AuthContextType {
  user: CurrentUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  loginWithOtp: (mobile: string, otp: string) => Promise<void>;
  loginWithPassword: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Module-level token holder for Axios interceptors
let inMemoryToken: string | null = null;

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Setup Axios interceptors
  useEffect(() => {
    const reqInterceptor = apiClient.interceptors.request.use((config) => {
      if (inMemoryToken && config.headers) {
        config.headers.Authorization = `Bearer ${inMemoryToken}`;
      }
      return config;
    });

    const resInterceptor = apiClient.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;
        if (
          error.response?.status === 401 &&
          !originalRequest._retry &&
          !originalRequest.url?.includes('/auth/login') &&
          !originalRequest.url?.includes('/auth/verify-otp') &&
          !originalRequest.url?.includes('/auth/refresh')
        ) {
          originalRequest._retry = true;
          try {
            const data = await refreshToken();
            inMemoryToken = data.access_token;
            originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
            return apiClient(originalRequest);
          } catch (refreshErr) {
            inMemoryToken = null;
            setUser(null);
            return Promise.reject(refreshErr);
          }
        }
        return Promise.reject(error);
      }
    );

    // Silent login attempt on page reload using HttpOnly refresh cookie
    const initAuth = async () => {
      try {
        const data = await refreshToken();
        inMemoryToken = data.access_token;
        const profile = await getMe();
        setUser(profile);
      } catch {
        inMemoryToken = null;
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();

    return () => {
      apiClient.interceptors.request.eject(reqInterceptor);
      apiClient.interceptors.response.eject(resInterceptor);
    };
  }, []);

  const loginWithOtp = async (mobile: string, otp: string) => {
    setIsLoading(true);
    try {
      const data = await verifyOtp(mobile, otp);
      inMemoryToken = data.access_token;
      if (data.retailer) {
        setUser({
          id: data.retailer.id,
          role: 'retailer',
          name: data.retailer.name,
          identifier: data.retailer.mobile,
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loginWithPassword = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const data = await deskLogin(email, password);
      inMemoryToken = data.access_token;
      if (data.user) {
        setUser({
          id: data.user.id,
          role: 'order_desk',
          name: data.user.full_name,
          identifier: data.user.email,
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await logoutApi();
    } catch {
      // Ignore API logout errors and clear client state
    } finally {
      inMemoryToken = null;
      setUser(null);
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        loginWithOtp,
        loginWithPassword,
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

