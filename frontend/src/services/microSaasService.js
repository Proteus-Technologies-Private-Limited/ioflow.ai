import axios from 'axios';

const API_BASE_URL = '/api/v1/micro-saas-apps';

/**
 * Service for managing Micro SaaS applications
 */
export const microSaasService = {
  /**
   * Create a new Micro SaaS application from a flow
   * @param {Object} appData - Micro SaaS app configuration
   * @param {string} appData.flow_id - The ID of the flow to publish
   * @param {string} appData.app_key - The desired application key
   * @param {string} appData.app_name - The application name
   * @param {string} appData.description - Application description
   * @param {string} appData.category - Application category
   * @param {string} appData.icon_url - Icon URL
   * @param {string} appData.visibility - Marketplace visibility (public, private, granted_access)
   * @param {string} appData.billing_preference - Billing model (per_user_per_month, per_execution, free)
   * @param {Object} appData.pricing_config - Pricing configuration
   * @param {Object} appData.usage_limits - Usage limits and quotas
   * @param {string} appData.access_type - Access control type
   * @param {Object} appData.access_config - Access configuration
   * @param {string} appData.public_url_slug - Custom URL slug
   * @param {boolean} appData.auto_update - Auto-update when source flow changes
   * @param {boolean} appData.embed_enabled - Enable embed functionality
   * @param {Object} appData.custom_styling - Custom CSS/styling
   * @returns {Promise} Creation result with app details and URLs
   */
  async createMicroSaasApp(appData) {
    const response = await axios.post(`${API_BASE_URL}/create`, appData);
    return response.data;
  },

  /**
   * Get list of Micro SaaS apps for the current user
   * @param {Object} params - Query parameters
   * @param {boolean} params.include_inactive - Include inactive apps
   * @param {string} params.visibility - Filter by visibility (public, private, granted_access)
   * @returns {Promise} List of Micro SaaS apps
   */
  async getMicroSaasApps(params = {}) {
    const response = await axios.get(`${API_BASE_URL}`, { params });
    return response.data;
  },

  /**
   * Get details of a specific Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @returns {Promise} App details with full configuration
   */
  async getMicroSaasApp(frontendAppId) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}`);
    return response.data;
  },

  /**
   * Update all settings for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Object} updates - Settings to update
   * @returns {Promise} Updated app details
   */
  async updateAppSettings(frontendAppId, updates) {
    const response = await axios.put(`${API_BASE_URL}/${frontendAppId}/settings`, updates);
    return response.data;
  },

  /**
   * Update visibility setting for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {string} visibility - New visibility (public, private, granted_access)
   * @returns {Promise} Updated app details
   */
  async updateVisibility(frontendAppId, visibility) {
    const response = await axios.put(`${API_BASE_URL}/${frontendAppId}/visibility`, { visibility });
    return response.data;
  },

  /**
   * Update billing configuration for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Object} billingConfig - Billing configuration
   * @param {string} billingConfig.billing_preference - Billing model
   * @param {Object} billingConfig.pricing_config - Pricing details
   * @param {Object} billingConfig.usage_limits - Usage limits
   * @returns {Promise} Updated app details
   */
  async updateBillingConfig(frontendAppId, billingConfig) {
    const response = await axios.put(`${API_BASE_URL}/${frontendAppId}/billing`, billingConfig);
    return response.data;
  },

  /**
   * Update usage limits for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Object} usageLimits - Usage limits configuration
   * @returns {Promise} Updated app details
   */
  async updateUsageLimits(frontendAppId, usageLimits) {
    const response = await axios.put(`${API_BASE_URL}/${frontendAppId}/usage-limits`, { usage_limits: usageLimits });
    return response.data;
  },

  /**
   * Get comprehensive analytics for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Object} params - Query parameters
   * @param {string} params.start_date - Start date (ISO format)
   * @param {string} params.end_date - End date (ISO format)
   * @returns {Promise} Analytics data with execution metrics, revenue, and usage patterns
   */
  async getAnalytics(frontendAppId, params = {}) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}/analytics`, { params });
    return response.data;
  },

  /**
   * Get list of subscribers for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Object} params - Query parameters
   * @param {string} params.status_filter - Filter by status (active, paused, expired, cancelled)
   * @returns {Promise} List of subscribers with payment and usage info
   */
  async getSubscribers(frontendAppId, params = {}) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}/subscribers`, { params });
    return response.data;
  },

  /**
   * Get billing history for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Object} params - Query parameters
   * @param {string} params.start_date - Start date (ISO format)
   * @param {string} params.end_date - End date (ISO format)
   * @returns {Promise} Billing history with transactions and execution costs
   */
  async getBillingHistory(frontendAppId, params = {}) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}/billing-history`, { params });
    return response.data;
  },

  /**
   * Grant access to specific users
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Array<string>} userEmails - List of user emails to grant access
   * @returns {Promise} Access management result
   */
  async grantAccess(frontendAppId, userEmails) {
    const response = await axios.post(`${API_BASE_URL}/${frontendAppId}/grant-access`, { user_emails: userEmails });
    return response.data;
  },

  /**
   * Revoke access from specific subscribers
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Array<string>} subscriberIds - List of subscriber IDs to revoke access
   * @returns {Promise} Access management result
   */
  async revokeAccess(frontendAppId, subscriberIds) {
    const response = await axios.post(`${API_BASE_URL}/${frontendAppId}/revoke-access`, { subscriber_ids: subscriberIds });
    return response.data;
  },

  /**
   * Top up prepaid balance for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {Object} topUpData - Top up configuration
   * @param {number} topUpData.amount - Amount to add
   * @param {string} topUpData.currency - Currency code
   * @param {string} topUpData.payment_method - Payment method identifier
   * @param {string} topUpData.payment_gateway - Payment gateway to use
   * @returns {Promise} Top up result with new balance
   */
  async topUpBalance(frontendAppId, topUpData) {
    const response = await axios.post(`${API_BASE_URL}/${frontendAppId}/top-up`, topUpData);
    return response.data;
  },

  /**
   * Delete a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @returns {Promise} Deletion result
   */
  async deleteMicroSaasApp(frontendAppId) {
    const response = await axios.delete(`${API_BASE_URL}/${frontendAppId}`);
    return response.data;
  },

  // ============================================================
  // Related Flows (Prerequisites and Follow-ups)
  // ============================================================

  /**
   * Get all related flows (prerequisites and follow-ups) for a Micro SaaS app
   * @param {string} frontendAppId - The ID of the Micro SaaS app
   * @param {boolean} includeInactive - Include inactive relationships
   * @returns {Promise} Object with prerequisites and followups arrays
   */
  async getRelatedFlows(frontendAppId, includeInactive = false) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}/related-flows`, {
      params: { include_inactive: includeInactive }
    });
    return response.data;
  },

  /**
   * Add a new related flow (prerequisite or follow-up)
   * @param {string} frontendAppId - The ID of the main Micro SaaS app
   * @param {Object} config - Related flow configuration
   * @param {string} config.related_frontend_app_id - ID of the related app
   * @param {string} config.relationship_type - 'prerequisite' or 'followup'
   * @param {boolean} config.is_mandatory - For prerequisites: whether it must be completed
   * @param {number} config.execution_order - Order within relationship type
   * @param {string} config.display_name - Optional custom display name
   * @param {string} config.documentation - Help text shown to users
   * @param {Object} config.parameter_mappings - Manual parameter mapping config
   * @param {boolean} config.auto_map_enabled - Whether to auto-map parameters
   * @returns {Promise} Created relationship
   */
  async addRelatedFlow(frontendAppId, config) {
    const response = await axios.post(`${API_BASE_URL}/${frontendAppId}/related-flows`, config);
    return response.data;
  },

  /**
   * Update an existing related flow relationship
   * @param {string} frontendAppId - The ID of the main Micro SaaS app
   * @param {string} relationshipId - The ID of the relationship to update
   * @param {Object} updates - Fields to update
   * @returns {Promise} Updated relationship
   */
  async updateRelatedFlow(frontendAppId, relationshipId, updates) {
    const response = await axios.put(
      `${API_BASE_URL}/${frontendAppId}/related-flows/${relationshipId}`,
      updates
    );
    return response.data;
  },

  /**
   * Remove a related flow relationship
   * @param {string} frontendAppId - The ID of the main Micro SaaS app
   * @param {string} relationshipId - The ID of the relationship to remove
   * @returns {Promise} Removal result
   */
  async removeRelatedFlow(frontendAppId, relationshipId) {
    const response = await axios.delete(
      `${API_BASE_URL}/${frontendAppId}/related-flows/${relationshipId}`
    );
    return response.data;
  },

  /**
   * Reorder related flows within a relationship type
   * @param {string} frontendAppId - The ID of the main Micro SaaS app
   * @param {string} relationshipType - 'prerequisite' or 'followup'
   * @param {Array<string>} orderedIds - List of relationship IDs in desired order
   * @returns {Promise} Reorder result
   */
  async reorderRelatedFlows(frontendAppId, relationshipType, orderedIds) {
    const response = await axios.put(`${API_BASE_URL}/${frontendAppId}/related-flows/reorder`, {
      relationship_type: relationshipType,
      ordered_ids: orderedIds
    });
    return response.data;
  },

  /**
   * Get apps available for linking as prerequisites or follow-ups
   * @param {string} frontendAppId - The ID of the main Micro SaaS app
   * @param {Object} params - Query parameters
   * @param {string} params.relationship_type - Filter by relationship type
   * @param {string} params.search - Search term
   * @returns {Promise} List of available apps
   */
  async getAvailableAppsForLinking(frontendAppId, params = {}) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}/available-apps`, { params });
    return response.data;
  },

  /**
   * Preview auto-mapping for follow-up flows
   * @param {string} frontendAppId - The ID of the main Micro SaaS app
   * @param {Object} sourceOutputs - Output values from main flow execution
   * @returns {Promise} Auto-mapping previews for each follow-up
   */
  async previewAutoMapping(frontendAppId, sourceOutputs) {
    const response = await axios.post(
      `${API_BASE_URL}/${frontendAppId}/preview-mapping`,
      sourceOutputs
    );
    return response.data;
  },

  /**
   * Helper: Format visibility for display
   * @param {string} visibility - Visibility value
   * @returns {string} Display-friendly visibility text
   */
  formatVisibility(visibility) {
    const visibilityMap = {
      'public': 'Public',
      'private': 'Private',
      'granted_access': 'Granted Access Only'
    };
    return visibilityMap[visibility] || visibility;
  },

  /**
   * Helper: Format billing preference for display
   * @param {string} billingPreference - Billing preference value
   * @returns {string} Display-friendly billing text
   */
  formatBillingPreference(billingPreference) {
    const billingMap = {
      'per_user_per_month': 'Per User / Month',
      'per_execution': 'Per Execution',
      'free': 'Free to Use'
    };
    return billingMap[billingPreference] || billingPreference;
  },

  /**
   * Helper: Get badge color for visibility
   * @param {string} visibility - Visibility value
   * @returns {string} CSS class or color for badge
   */
  getVisibilityBadgeColor(visibility) {
    const colorMap = {
      'public': 'success',
      'private': 'warning',
      'granted_access': 'info'
    };
    return colorMap[visibility] || 'secondary';
  },

  /**
   * Helper: Get badge color for billing preference
   * @param {string} billingPreference - Billing preference value
   * @returns {string} CSS class or color for badge
   */
  getBillingBadgeColor(billingPreference) {
    const colorMap = {
      'per_user_per_month': 'primary',
      'per_execution': 'info',
      'free': 'success'
    };
    return colorMap[billingPreference] || 'secondary';
  },

  /**
   * Helper: Calculate estimated cost for executions
   * @param {Object} pricingConfig - Pricing configuration
   * @param {number} executions - Number of executions
   * @returns {number} Estimated cost
   */
  calculateExecutionCost(pricingConfig, executions) {
    if (!pricingConfig || !pricingConfig.per_execution_config) {
      return 0;
    }

    const config = pricingConfig.per_execution_config;
    const pricePerExec = config.price_per_execution || 0;
    const freeExecutions = config.free_executions_per_month || 0;

    // Calculate billable executions
    const billableExecutions = Math.max(0, executions - freeExecutions);

    // Apply bulk discounts if configured
    let finalPrice = pricePerExec;
    if (config.bulk_discounts && config.bulk_discounts.length > 0) {
      const sortedDiscounts = [...config.bulk_discounts].sort((a, b) =>
        b.execution_threshold - a.execution_threshold
      );

      for (const discount of sortedDiscounts) {
        if (billableExecutions >= discount.execution_threshold) {
          finalPrice = pricePerExec * (1 - discount.discount_percent / 100);
          break;
        }
      }
    }

    const totalCost = billableExecutions * finalPrice;

    // Apply minimum charge if configured
    const minimumCharge = config.minimum_charge || 0;
    return Math.max(totalCost, minimumCharge);
  },

  // ============================================================
  // Landing Page Designer
  // ============================================================

  async getPageDefinition(frontendAppId) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}/page-definition`);
    return response.data;
  },

  async updatePageDefinition(frontendAppId, pageDefinition) {
    const response = await axios.put(`${API_BASE_URL}/${frontendAppId}/page-definition`, {
      page_definition: pageDefinition,
    });
    return response.data;
  },

  async deletePageDefinition(frontendAppId) {
    const response = await axios.delete(`${API_BASE_URL}/${frontendAppId}/page-definition`);
    return response.data;
  },

  async uploadLandingImage(frontendAppId, file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await axios.post(
      `${API_BASE_URL}/${frontendAppId}/landing-images/upload`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return response.data;
  },

  async getLandingImages(frontendAppId) {
    const response = await axios.get(`${API_BASE_URL}/${frontendAppId}/landing-images`);
    return response.data;
  },

  async deleteLandingImage(frontendAppId, imageId) {
    const response = await axios.delete(`${API_BASE_URL}/${frontendAppId}/landing-images/${imageId}`);
    return response.data;
  },
};

// ============================================================
// Public API helpers (no auth required)
// ============================================================

/**
 * Fetch related flows info for public execution page
 * @param {string} publicUrlSlug - Public URL slug of the app
 * @returns {Promise} Related flows info with prerequisites and followups
 */
export const fetchPublicRelatedFlows = async (publicUrlSlug) => {
  const response = await fetch(`/api/v1/public-apps/${publicUrlSlug}/related-flows`);
  if (!response.ok) {
    throw new Error('Failed to fetch related flows');
  }
  return response.json();
};

export default microSaasService;
