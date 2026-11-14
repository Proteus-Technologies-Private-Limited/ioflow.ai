/**
 * Marketplace Service
 * API client for marketplace browsing, subscriptions, reviews, and approvals
 */

import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:7001';
const MARKETPLACE_API = `${API_BASE_URL}/api/v1/marketplace`;

/**
 * Get authentication headers with JWT token
 */
const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// ============================================================================
// PUBLIC APIs (No authentication required)
// ============================================================================

/**
 * Browse marketplace apps with filters
 * @param {Object} filters - Filter parameters
 * @returns {Promise} Paginated app list
 */
export const browseMarketplaceApps = async (filters = {}) => {
  try {
    const params = new URLSearchParams();

    if (filters.search) params.append('search', filters.search);
    if (filters.category_id) params.append('category_id', filters.category_id);
    if (filters.category_slug) params.append('category_slug', filters.category_slug);
    if (filters.tags && filters.tags.length > 0) {
      filters.tags.forEach(tag => params.append('tags', tag));
    }
    if (filters.min_rating) params.append('min_rating', filters.min_rating);
    if (filters.max_price) params.append('max_price', filters.max_price);
    if (filters.billing_preference) params.append('billing_preference', filters.billing_preference);
    if (filters.sort_by) params.append('sort_by', filters.sort_by);
    if (filters.page) params.append('page', filters.page);
    if (filters.page_size) params.append('page_size', filters.page_size);

    const response = await axios.get(`${MARKETPLACE_API}/apps?${params.toString()}`);
    return response.data;
  } catch (error) {
    console.error('Error browsing marketplace apps:', error);
    throw error;
  }
};

/**
 * Get detailed app information by slug
 * @param {string} slug - App URL slug
 * @returns {Promise} App details with reviews
 */
export const getAppDetails = async (slug) => {
  try {
    const headers = getAuthHeaders(); // Optional auth
    const response = await axios.get(`${MARKETPLACE_API}/apps/${slug}`, { headers });
    return response.data;
  } catch (error) {
    console.error('Error getting app details:', error);
    throw error;
  }
};

/**
 * Get all marketplace categories
 * @param {boolean} activeOnly - Return only active categories
 * @returns {Promise} List of categories
 */
export const getCategories = async (activeOnly = true) => {
  try {
    const response = await axios.get(`${MARKETPLACE_API}/categories`, {
      params: { active_only: activeOnly }
    });
    return response.data;
  } catch (error) {
    console.error('Error getting categories:', error);
    throw error;
  }
};

/**
 * Get all marketplace tags
 * @param {boolean} activeOnly - Return only active tags
 * @returns {Promise} List of tags
 */
export const getTags = async (activeOnly = true) => {
  try {
    const response = await axios.get(`${MARKETPLACE_API}/tags`, {
      params: { active_only: activeOnly }
    });
    return response.data;
  } catch (error) {
    console.error('Error getting tags:', error);
    throw error;
  }
};

/**
 * Get featured marketplace apps
 * @param {number} limit - Number of apps to return
 * @returns {Promise} List of featured apps
 */
export const getFeaturedApps = async (limit = 10) => {
  try {
    console.log('Fetching featured apps from:', `${MARKETPLACE_API}/featured`);
    const response = await axios.get(`${MARKETPLACE_API}/featured`, {
      params: { limit }
    });
    return response.data;
  } catch (error) {
    console.error('Error getting featured apps:', error);
    console.error('Error details:', {
      message: error.message,
      code: error.code,
      url: `${MARKETPLACE_API}/featured`,
      response: error.response,
      request: error.request ? 'Request was made' : 'No request made'
    });
    // Return empty array instead of throwing to prevent page crash
    return [];
  }
};

/**
 * Get trending marketplace apps
 * @param {number} limit - Number of apps to return
 * @returns {Promise} List of trending apps
 */
export const getTrendingApps = async (limit = 10) => {
  try {
    const response = await axios.get(`${MARKETPLACE_API}/trending`, {
      params: { limit }
    });
    return response.data;
  } catch (error) {
    console.error('Error getting trending apps:', error);
    throw error;
  }
};

/**
 * Get reviews for an app
 * @param {string} appId - App ID
 * @param {Object} options - Pagination and sorting options
 * @returns {Promise} List of reviews
 */
export const getAppReviews = async (appId, options = {}) => {
  try {
    const headers = getAuthHeaders(); // Optional auth
    const params = {
      page: options.page || 1,
      page_size: options.page_size || 10,
      sort_by: options.sort_by || 'recent'
    };

    const response = await axios.get(`${MARKETPLACE_API}/apps/${appId}/reviews`, {
      params,
      headers
    });
    return response.data;
  } catch (error) {
    console.error('Error getting app reviews:', error);
    throw error;
  }
};

// ============================================================================
// PROTECTED APIs (Authentication required)
// ============================================================================

/**
 * Get user's marketplace app subscriptions
 * @returns {Promise} List of user subscriptions
 */
export const getMySubscriptions = async () => {
  try {
    const response = await axios.get(`${MARKETPLACE_API}/my-subscriptions`, {
      headers: getAuthHeaders()
    });
    return response.data;
  } catch (error) {
    console.error('Error getting subscriptions:', error);
    throw error;
  }
};

/**
 * Check subscription requirements for an app
 * @param {string} appId - App ID
 * @returns {Promise} Required applications and their status
 */
export const checkSubscriptionRequirements = async (appId) => {
  try {
    const response = await axios.get(
      `${MARKETPLACE_API}/apps/${appId}/subscription-requirements`,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error checking subscription requirements:', error);
    throw error;
  }
};

/**
 * Create a review for an app
 * @param {Object} reviewData - Review data (app_id, rating, title, review_text)
 * @returns {Promise} Created review
 */
export const createReview = async (reviewData) => {
  try {
    const response = await axios.post(
      `${MARKETPLACE_API}/reviews`,
      reviewData,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error creating review:', error);
    throw error;
  }
};

/**
 * Update an existing review
 * @param {string} reviewId - Review ID
 * @param {Object} reviewData - Updated review data
 * @returns {Promise} Updated review
 */
export const updateReview = async (reviewId, reviewData) => {
  try {
    const response = await axios.put(
      `${MARKETPLACE_API}/reviews/${reviewId}`,
      reviewData,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error updating review:', error);
    throw error;
  }
};

/**
 * Mark/unmark a review as helpful
 * @param {string} reviewId - Review ID
 * @returns {Promise} Success response
 */
export const markReviewHelpful = async (reviewId) => {
  try {
    const response = await axios.post(
      `${MARKETPLACE_API}/reviews/${reviewId}/helpful`,
      {},
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error marking review helpful:', error);
    throw error;
  }
};

/**
 * Submit app for marketplace approval
 * @param {string} appId - App ID
 * @returns {Promise} Approval status
 */
export const submitForApproval = async (appId) => {
  try {
    const response = await axios.post(
      `${MARKETPLACE_API}/apps/${appId}/submit-for-approval`,
      {},
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error submitting for approval:', error);
    throw error;
  }
};

// ============================================================================
// ADMIN APIs (Admin access required)
// ============================================================================

/**
 * Get pending approval requests (admin only)
 * @returns {Promise} List of pending approvals
 */
export const getPendingApprovals = async () => {
  try {
    const response = await axios.get(`${MARKETPLACE_API}/admin/pending-approvals`, {
      headers: getAuthHeaders()
    });
    return response.data;
  } catch (error) {
    console.error('Error getting pending approvals:', error);
    throw error;
  }
};

/**
 * Approve or reject a marketplace app (admin only)
 * @param {string} appId - App ID
 * @param {Object} reviewData - Review data (status, review_notes, rejection_reason)
 * @returns {Promise} Approval result
 */
export const reviewMarketplaceApp = async (appId, reviewData) => {
  try {
    const response = await axios.post(
      `${MARKETPLACE_API}/admin/apps/${appId}/approve`,
      reviewData,
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error reviewing app:', error);
    throw error;
  }
};

/**
 * Update trending scores (admin only, background job)
 * @returns {Promise} Success response
 */
export const updateTrendingScores = async () => {
  try {
    const response = await axios.post(
      `${MARKETPLACE_API}/admin/update-trending-scores`,
      {},
      { headers: getAuthHeaders() }
    );
    return response.data;
  } catch (error) {
    console.error('Error updating trending scores:', error);
    throw error;
  }
};

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Format price from pricing config
 * @param {Object} pricingConfig - Pricing configuration
 * @param {string} billingPreference - Billing preference
 * @returns {string} Formatted price string
 */
export const formatPrice = (pricingConfig, billingPreference) => {
  if (billingPreference === 'free') {
    return 'Free';
  }

  if (!pricingConfig) {
    return 'Contact for pricing';
  }

  if (billingPreference === 'per_user_per_month' && pricingConfig.per_user_per_month) {
    return `$${pricingConfig.per_user_per_month}/user/month`;
  }

  if (billingPreference === 'per_execution' && pricingConfig.per_execution) {
    return `$${pricingConfig.per_execution}/execution`;
  }

  return 'Contact for pricing';
};

/**
 * Get rating stars display
 * @param {number} rating - Average rating (0-5)
 * @returns {Object} Stars configuration
 */
export const getRatingStars = (rating) => {
  const fullStars = Math.floor(rating);
  const hasHalfStar = rating % 1 >= 0.5;
  const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

  return {
    full: fullStars,
    half: hasHalfStar ? 1 : 0,
    empty: emptyStars,
    rating: rating.toFixed(1)
  };
};

/**
 * Check if user is subscribed to an app
 * @param {string} appId - App ID
 * @param {Array} subscriptions - User's subscriptions
 * @returns {boolean} Is subscribed
 */
export const isSubscribed = (appId, subscriptions) => {
  if (!subscriptions || !Array.isArray(subscriptions)) {
    return false;
  }
  return subscriptions.some(sub => sub.app_id === appId && sub.status === 'active');
};

export default {
  browseMarketplaceApps,
  getAppDetails,
  getCategories,
  getTags,
  getFeaturedApps,
  getTrendingApps,
  getAppReviews,
  getMySubscriptions,
  checkSubscriptionRequirements,
  createReview,
  updateReview,
  markReviewHelpful,
  submitForApproval,
  getPendingApprovals,
  reviewMarketplaceApp,
  updateTrendingScores,
  formatPrice,
  getRatingStars,
  isSubscribed
};
