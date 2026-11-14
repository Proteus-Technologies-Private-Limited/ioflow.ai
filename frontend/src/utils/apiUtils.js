/**
 * API utility functions for managing API URLs and endpoints
 */

// Get the base API URL from environment or use the current origin
const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

/**
 * Get the full API URL for a given endpoint
 * @param {string} endpoint - The API endpoint (e.g., '/api/v1/tenant/balance')
 * @returns {string} The full API URL
 */
export const getApiUrl = (endpoint) => {
  // Remove leading slash if present to avoid double slashes
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint.slice(1) : endpoint;
  return `${API_BASE_URL}/${cleanEndpoint}`;
};

/**
 * Get the base API URL
 * @returns {string} The base API URL
 */
export const getBaseUrl = () => {
  return API_BASE_URL;
};

export default {
  getApiUrl,
  getBaseUrl,
  API_BASE_URL
};