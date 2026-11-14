/**
 * Documentation Service
 * API wrapper for app documentation pages management
 */
import axios from 'axios';
import toast from 'react-hot-toast';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:7001';

/**
 * Get authentication headers
 */
const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// ============================================================================
// OWNER ENDPOINTS - Manage documentation pages
// ============================================================================

/**
 * Create a new documentation page
 * @param {string} appId - Frontend app ID
 * @param {object} pageData - Page data (page_type, page_title, page_slug, content, display_order, is_published)
 * @returns {Promise<object>} Created page
 */
export const createDocumentationPage = async (appId, pageData) => {
  try {
    const response = await axios.post(
      `${API_URL}/api/v1/micro-saas-apps/${appId}/documentation`,
      pageData,
      { headers: getAuthHeaders() }
    );
    toast.success('Documentation page created successfully');
    return response.data;
  } catch (error) {
    const message = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to create documentation page';
    toast.error(message);
    throw error;
  }
};

/**
 * Get all documentation pages for an app (owner view - includes unpublished)
 * @param {string} appId - Frontend app ID
 * @returns {Promise<object>} Pages list response
 */
export const getAppDocumentationPages = async (appId) => {
  try {
    const response = await axios.get(
      `${API_URL}/api/v1/micro-saas-apps/${appId}/documentation`,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching documentation pages:', error);
    throw error;
  }
};

/**
 * Get a specific documentation page by ID (owner view)
 * @param {string} appId - Frontend app ID
 * @param {string} pageId - Page ID
 * @returns {Promise<object>} Page data
 */
export const getDocumentationPageById = async (appId, pageId) => {
  try {
    const response = await axios.get(
      `${API_URL}/api/v1/micro-saas-apps/${appId}/documentation/${pageId}`,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching documentation page:', error);
    throw error;
  }
};

/**
 * Update a documentation page
 * @param {string} appId - Frontend app ID
 * @param {string} pageId - Page ID
 * @param {object} updates - Fields to update
 * @returns {Promise<object>} Updated page
 */
export const updateDocumentationPage = async (appId, pageId, updates) => {
  try {
    const response = await axios.put(
      `${API_URL}/api/v1/micro-saas-apps/${appId}/documentation/${pageId}`,
      updates,
      { headers: getAuthHeaders() }
    );
    toast.success('Documentation page updated successfully');
    return response.data;
  } catch (error) {
    const message = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to update documentation page';
    toast.error(message);
    throw error;
  }
};

/**
 * Delete a documentation page
 * @param {string} appId - Frontend app ID
 * @param {string} pageId - Page ID
 * @returns {Promise<void>}
 */
export const deleteDocumentationPage = async (appId, pageId) => {
  try {
    await axios.delete(
      `${API_URL}/api/v1/micro-saas-apps/${appId}/documentation/${pageId}`,
      { headers: getAuthHeaders() }
    );
    toast.success('Documentation page deleted successfully');
  } catch (error) {
    const message = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to delete documentation page';
    toast.error(message);
    throw error;
  }
};

/**
 * Reorder documentation pages
 * @param {string} appId - Frontend app ID
 * @param {Array<{page_id: string, display_order: number}>} pageOrders - New page orders
 * @returns {Promise<Array>} Reordered pages
 */
export const reorderDocumentationPages = async (appId, pageOrders) => {
  try {
    const response = await axios.patch(
      `${API_URL}/api/v1/micro-saas-apps/${appId}/documentation/reorder`,
      { page_orders: pageOrders },
      { headers: getAuthHeaders() }
    );
    toast.success('Pages reordered successfully');
    return response.data;
  } catch (error) {
    const message = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to reorder pages';
    toast.error(message);
    throw error;
  }
};

// ============================================================================
// PUBLIC ENDPOINTS - View published documentation
// ============================================================================

/**
 * Get published documentation pages for a marketplace app
 * @param {string} appSlug - App public URL slug
 * @returns {Promise<Array>} Published pages (summary only)
 */
export const getMarketplaceDocumentation = async (appSlug) => {
  try {
    const response = await axios.get(
      `${API_URL}/api/v1/marketplace/apps/${appSlug}/documentation`
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching marketplace documentation:', error);
    throw error;
  }
};

/**
 * Get a specific published documentation page by slug
 * @param {string} appSlug - App public URL slug
 * @param {string} pageSlug - Page slug
 * @returns {Promise<object>} Full page data with content
 */
export const getMarketplaceDocumentationPage = async (appSlug, pageSlug) => {
  try {
    const response = await axios.get(
      `${API_URL}/api/v1/marketplace/apps/${appSlug}/documentation/${pageSlug}`
    );
    return response.data;
  } catch (error) {
    console.error('Error fetching marketplace documentation page:', error);
    throw error;
  }
};

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Generate a URL-friendly slug from a title
 * @param {string} title - Page title
 * @returns {string} URL-friendly slug
 */
export const generateSlug = (title) => {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
};

/**
 * Get page type display name
 * @param {string} pageType - Page type enum value
 * @returns {string} Display name
 */
export const getPageTypeLabel = (pageType) => {
  const labels = {
    user_guide: 'User Guide',
    specifications: 'Specifications',
    prerequisites: 'Prerequisites',
    api_docs: 'API Documentation',
    troubleshooting: 'Troubleshooting',
    faq: 'FAQ',
    changelog: 'Changelog',
    custom: 'Custom'
  };
  return labels[pageType] || pageType;
};

/**
 * Get page type icon
 * @param {string} pageType - Page type enum value
 * @returns {string} Icon name for lucide-react
 */
export const getPageTypeIcon = (pageType) => {
  const icons = {
    user_guide: 'BookOpen',
    specifications: 'FileText',
    prerequisites: 'AlertCircle',
    api_docs: 'Code',
    troubleshooting: 'Wrench',
    faq: 'HelpCircle',
    changelog: 'GitBranch',
    custom: 'File'
  };
  return icons[pageType] || 'File';
};

/**
 * Page type options for dropdowns
 */
export const PAGE_TYPE_OPTIONS = [
  { value: 'user_guide', label: 'User Guide', icon: 'BookOpen' },
  { value: 'specifications', label: 'Specifications', icon: 'FileText' },
  { value: 'prerequisites', label: 'Prerequisites', icon: 'AlertCircle' },
  { value: 'api_docs', label: 'API Documentation', icon: 'Code' },
  { value: 'troubleshooting', label: 'Troubleshooting', icon: 'Wrench' },
  { value: 'faq', label: 'FAQ', icon: 'HelpCircle' },
  { value: 'changelog', label: 'Changelog', icon: 'GitBranch' },
  { value: 'custom', label: 'Custom', icon: 'File' }
];

export default {
  createDocumentationPage,
  getAppDocumentationPages,
  getDocumentationPageById,
  updateDocumentationPage,
  deleteDocumentationPage,
  reorderDocumentationPages,
  getMarketplaceDocumentation,
  getMarketplaceDocumentationPage,
  generateSlug,
  getPageTypeLabel,
  getPageTypeIcon,
  PAGE_TYPE_OPTIONS
};
