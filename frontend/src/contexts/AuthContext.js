import React, { createContext, useState, useContext, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { showErrorToast, showSuccessToast, showWarningToast } from '../utils/customToast';
import { API_BASE_URL } from '../config';

// Configure axios defaults
axios.defaults.baseURL = API_BASE_URL;

const AuthContext = createContext({});

export const useAuth = () => useContext(AuthContext);

// Token refresh settings
const TOKEN_LIFETIME = 60 * 60 * 1000; // 1 hour in milliseconds
const REFRESH_BUFFER = 10 * 60 * 1000; // Refresh 10 minutes before expiry
const ACTIVITY_CHECK_INTERVAL = 30 * 1000; // Check activity every 30 seconds

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [tokenExpiry, setTokenExpiry] = useState(() => {
    const stored = localStorage.getItem('token_expiry');
    return stored ? parseInt(stored) : null;
  });
  const lastActivityRef = useRef(Date.now());
  const refreshIntervalRef = useRef(null);
  const axiosInterceptorRef = useRef(null);
  const isRefreshingRef = useRef(false);
  const refreshSubscribersRef = useRef([]);

  // Update last activity timestamp on user interaction
  useEffect(() => {
    const updateActivity = () => {
      lastActivityRef.current = Date.now();
    };

    // Track user activity
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach(event => window.addEventListener(event, updateActivity));

    return () => {
      events.forEach(event => window.removeEventListener(event, updateActivity));
    };
  }, []);

  // Define logout first since it's used by other functions
  const logout = useCallback(async (skipPreferenceFetch = false) => {
    // Clear intervals
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
    }

    // Check user's cache retention preference
    let retainCache = false;
    // Only try to fetch UI preferences if we still have a valid token and not skipping
    if (token && !skipPreferenceFetch) {
      try {
        const response = await axios.get('/api/v1/ui-preferences');
        retainCache = response.data?.retain_cache_on_logout || false;
      } catch (error) {
        // If we can't fetch preferences, default to clearing cache
        console.log('Could not fetch UI preferences, defaulting to clear cache');
      }
    }

    // Clear auth data
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_expiry');
    delete axios.defaults.headers.common['Authorization'];

    // Clear other cached data unless user wants to retain it
    if (!retainCache) {
      // Clear application service favorites and recent items
      localStorage.removeItem('appServiceFavorites');
      localStorage.removeItem('appServiceRecent');
      // Clear properties panel mode preference
      localStorage.removeItem('propertiesPanelMode');
      // Clear any other user-specific cached data
      const keysToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        // Keep only non-user-specific items
        if (key && !['theme', 'app_url', 'api_base_url'].includes(key)) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(key => localStorage.removeItem(key));
    }

    // Reset state
    setToken(null);
    setTokenExpiry(null);
    setUser(null);

    showSuccessToast('Logged out successfully');
  }, [token]);

  // Define refreshToken before it's used
  const refreshToken = useCallback(async () => {
    try {
      console.log('Refreshing token...');
      const response = await axios.post('/api/v1/auth/refresh');
      
      const { access_token, user_id, tenant_id, tenant_name, username, role } = response.data;
      
      // Update token and storage
      localStorage.setItem('access_token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      setToken(access_token);
      
      // Update token expiry
      const expiry = Date.now() + TOKEN_LIFETIME;
      setTokenExpiry(expiry);
      localStorage.setItem('token_expiry', expiry.toString());
      
      // Update user data if needed
      if (user_id && tenant_id) {
        setUser({
          user_id,
          email: user?.email || response.data.email,
          username,
          role,
          tenant: {
            tenant_id,
            tenant_name,
          },
        });
      }
      
      console.log('Token refreshed successfully');
      return access_token;
    } catch (error) {
      console.error('Token refresh failed:', error);
      throw error;
    }
  }, [user]);

  // Setup axios interceptor for 401 responses
  useEffect(() => {
    // Remove existing interceptor if any
    if (axiosInterceptorRef.current !== null) {
      axios.interceptors.response.eject(axiosInterceptorRef.current);
    }

    // Add new interceptor
    axiosInterceptorRef.current = axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        // If we get a 401, the token is expired or invalid
        if (error.response?.status === 401) {
          // Skip if this is already a retry or certain endpoints
          if (originalRequest._retry ||
              originalRequest.url?.includes('/auth/login') ||
              originalRequest.url?.includes('/auth/logout') ||
              originalRequest.url?.includes('/auth/refresh') ||
              // Check if we're on the login page
              window.location.pathname === '/login' ||
              window.location.pathname === '/register' ||
              window.location.pathname === '/activate' ||
              !token) {

            // If this is a ui-preferences call after session expiry, don't keep retrying
            if (originalRequest.url?.includes('/ui-preferences') && !token) {
              return Promise.reject(error);
            }

            return Promise.reject(error);
          }
          
          // Mark as retried to prevent loops
          originalRequest._retry = true;
          
          // If we're already refreshing, wait for it
          if (isRefreshingRef.current) {
            return new Promise((resolve, reject) => {
              refreshSubscribersRef.current.push((token) => {
                if (token) {
                  originalRequest.headers['Authorization'] = `Bearer ${token}`;
                  resolve(axios(originalRequest));
                } else {
                  reject(error);
                }
              });
            });
          }
          
          // Try to refresh the token
          isRefreshingRef.current = true;
          
          try {
            const newToken = await refreshToken();
            
            // Notify all waiting requests
            refreshSubscribersRef.current.forEach(callback => callback(newToken));
            refreshSubscribersRef.current = [];
            
            // Retry the original request with new token
            originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
            return axios(originalRequest);
            
          } catch (refreshError) {
            // Refresh failed, logout
            refreshSubscribersRef.current.forEach(callback => callback(null));
            refreshSubscribersRef.current = [];

            // Only show error and logout if we're not already on login page
            if (window.location.pathname !== '/login' &&
                window.location.pathname !== '/register' &&
                window.location.pathname !== '/activate') {
              // Pass true to skip preference fetch when logging out due to expired session
              logout(true);
              showErrorToast('Session expired - please log in again');
              // Redirect to login page
              window.location.href = '/login';
            }

            return Promise.reject(error);
          } finally {
            isRefreshingRef.current = false;
          }
        }
        
        return Promise.reject(error);
      }
    );

    return () => {
      if (axiosInterceptorRef.current !== null) {
        axios.interceptors.response.eject(axiosInterceptorRef.current);
      }
    };
  }, [token, logout, refreshToken]);

  // Setup token expiry check interval
  useEffect(() => {
    // Clear existing interval
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }

    if (token && tokenExpiry) {
      // Setup new interval to check token expiry and refresh if needed
      refreshIntervalRef.current = setInterval(async () => {
        const now = Date.now();
        const timeUntilExpiry = tokenExpiry - now;
        const timeSinceLastActivity = now - lastActivityRef.current;
        
        // If user has been inactive for more than token lifetime, logout
        if (timeSinceLastActivity > TOKEN_LIFETIME) {
          logout(true);
          showWarningToast('Session expired due to inactivity');
          window.location.href = '/login';
          return;
        }

        // If token is expired, logout
        if (timeUntilExpiry < 0) {
          logout(true);
          showErrorToast('Session expired - please log in again');
          window.location.href = '/login';
          return;
        }
        
        // If token will expire soon and user is active, refresh it
        if (timeUntilExpiry < REFRESH_BUFFER && timeSinceLastActivity < ACTIVITY_CHECK_INTERVAL * 2) {
          try {
            console.log('Token expiring soon, refreshing...');
            await refreshToken();
            showSuccessToast('Session extended');
          } catch (error) {
            console.error('Failed to refresh token:', error);
            // If refresh fails, we'll try again on next interval
            // Don't logout immediately as user might still have some time
          }
        }
      }, ACTIVITY_CHECK_INTERVAL);

      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
        }
      };
    }
  }, [token, tokenExpiry, logout, refreshToken]);

  const fetchUser = useCallback(async () => {
    try {
      const response = await axios.get('/api/v1/auth/me');
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      if (error.response?.status === 401) {
        logout(true);
        window.location.href = '/login';
      }
    } finally {
      setLoading(false);
    }
  }, [logout]);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      // Check if we already have token expiry, otherwise set it
      if (!tokenExpiry) {
        const expiry = Date.now() + TOKEN_LIFETIME;
        setTokenExpiry(expiry);
        localStorage.setItem('token_expiry', expiry.toString());
      }
      fetchUser();
    } else {
      setLoading(false);
    }
  }, [token, tokenExpiry, fetchUser]);

  const login = async (email, password) => {
    try {
      console.log('Attempting login with email:', email);
      console.log('API Base URL:', API_BASE_URL);
      console.log('Login endpoint:', `${API_BASE_URL}/api/v1/auth/login`);
      
      const formData = new FormData();
      formData.append('username', email); // OAuth2PasswordRequestForm expects 'username'
      formData.append('password', password);
      
      const response = await axios.post('/api/v1/auth/login', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      console.log('Login response:', response.data);
      
      const { access_token, user_id, tenant_id, tenant_name, username, role } = response.data;
      
      if (!access_token) {
        throw new Error('No access token received from server');
      }
      
      localStorage.setItem('access_token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      setToken(access_token);
      
      // Set token expiry
      const expiry = Date.now() + TOKEN_LIFETIME;
      setTokenExpiry(expiry);
      localStorage.setItem('token_expiry', expiry.toString());
      
      setUser({
        user_id,
        email,
        username,
        role,
        tenant: {
          tenant_id,
          tenant_name,
        },
      });

      return response.data;
    } catch (error) {
      console.error('Login error:', error);
      console.error('Error response:', error.response);
      
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 
                          error.response?.data?.message || 
                          error.message || 
                          'Login failed. Please check your credentials.';
      
      showErrorToast(errorMessage);
      throw error;
    }
  };

  const register = async (userData) => {
    try {
      const response = await axios.post('/api/v1/auth/register', userData);
      
      // Handle different response statuses
      if (response.data.status === 'activated') {
        showSuccessToast(response.data.message);
      } else if (response.data.status === 'unactivated') {
        showWarningToast(response.data.message);
      } else {
        showSuccessToast(response.data.message);
      }
      
      return response.data;
    } catch (error) {
      console.error('Registration error:', error);
      console.error('Error response:', error.response);
      
      // Extract the most specific error message available
      let errorMessage = 'Registration failed';
      
      if (error.response?.data) {
        const data = error.response.data;
        // Check for different error message formats
        errorMessage = data.detail || 
                      data.message || 
                      data.error ||
                      (typeof data === 'string' ? data : errorMessage);
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      showErrorToast(errorMessage);
      throw error;
    }
  };

  const activate = async (email, activationCode) => {
    try {
      const response = await axios.post('/api/v1/auth/activate', {
        email,
        activation_code: activationCode,
      });
      const message = response?.data?.message || 'Account activated successfully! You can now login.';
      showSuccessToast(message);
      return response.data;
    } catch (error) {
      console.error('Activation error:', error);
      
      // Extract the most specific error message available
      let errorMessage = 'Activation failed';
      
      if (error.response?.data) {
        const data = error.response.data;
        errorMessage = data.detail || 
                      data.message || 
                      data.error ||
                      (typeof data === 'string' ? data : errorMessage);
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      showErrorToast(errorMessage);
      throw error;
    }
  };

  // Method to directly set auth data (used by Google OAuth callback)
  const setAuthData = useCallback((authData) => {
    const { token: accessToken, userId, tenantId, tenantName, username, userRole } = authData;
    
    // Set token
    localStorage.setItem('access_token', accessToken);
    axios.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`;
    setToken(accessToken);
    
    // Set token expiry
    const expiry = Date.now() + TOKEN_LIFETIME;
    setTokenExpiry(expiry);
    localStorage.setItem('token_expiry', expiry.toString());
    
    // Set user data
    setUser({
      user_id: userId,
      username,
      role: userRole,
      tenant: {
        tenant_id: tenantId,
        tenant_name: tenantName,
      },
    });
  }, []);

  const value = {
    user,
    loading,
    login,
    register,
    logout,
    activate,
    setAuthData,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};