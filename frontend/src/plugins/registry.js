/**
 * Frontend Plugin Registry
 *
 * Fetches UI schemas from the backend plugin schema API and caches them.
 * Provides lookup methods for service type, auth type, and node type schemas.
 */
import React, { createContext, useContext, useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from '../config';

class FrontendPluginRegistry {
  constructor() {
    this._schemas = {};
    this._loaded = false;
    this._loading = false;
    this._loadPromise = null;
  }

  /**
   * Load all schemas from the backend. Safe to call multiple times
   * (returns cached promise if already loading).
   */
  async loadSchemas() {
    if (this._loaded) return this._schemas;
    if (this._loading) return this._loadPromise;

    this._loading = true;
    this._loadPromise = this._fetchSchemas();

    try {
      this._schemas = await this._loadPromise;
      this._loaded = true;
    } catch (err) {
      console.warn('Failed to load plugin schemas:', err);
      this._schemas = {};
    } finally {
      this._loading = false;
    }

    return this._schemas;
  }

  async _fetchSchemas() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/plugins/ui-schemas`);
      return response.data?.schemas || {};
    } catch (err) {
      console.warn('Plugin schema fetch failed:', err);
      return {};
    }
  }

  /** Get schema for a specific auth type (e.g., 'oauth2'). */
  getAuthTypeSchema(authType) {
    return this._schemas?.auth_type?.[authType] || null;
  }

  /** Get schema for a specific service type (e.g., 'api_call'). */
  getServiceTypeSchema(serviceType) {
    return this._schemas?.service_type?.[serviceType] || null;
  }

  /** Get schema for a specific node type (e.g., 'transform'). */
  getNodeTypeSchema(nodeType) {
    return this._schemas?.node_type?.[nodeType] || null;
  }

  /** Check if schemas have been loaded. */
  get isLoaded() {
    return this._loaded;
  }
}

// Singleton instance
export const pluginRegistry = new FrontendPluginRegistry();

// React Context
const PluginRegistryContext = createContext(null);

/**
 * Provider component — wraps the app and loads schemas at mount time.
 */
export function PluginRegistryProvider({ children }) {
  const [registry] = useState(() => pluginRegistry);
  const [loaded, setLoaded] = useState(pluginRegistry.isLoaded);

  useEffect(() => {
    if (!loaded) {
      registry.loadSchemas().then(() => setLoaded(true));
    }
  }, [registry, loaded]);

  return (
    <PluginRegistryContext.Provider value={registry}>
      {children}
    </PluginRegistryContext.Provider>
  );
}

/**
 * Hook to access the plugin registry from any component.
 */
export function usePluginRegistry() {
  const ctx = useContext(PluginRegistryContext);
  if (!ctx) {
    // Return singleton if used outside provider (graceful degradation)
    return pluginRegistry;
  }
  return ctx;
}

export default pluginRegistry;
