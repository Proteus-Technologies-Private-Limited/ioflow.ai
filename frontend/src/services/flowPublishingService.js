import axios from 'axios';

const API_BASE_URL = '/api/v1/flow-publishing';

/**
 * Service for managing flow publishing system
 */
export const flowPublishingService = {
  /**
   * Preview what will be created when publishing a flow
   * @param {string} flowId - The ID of the flow to preview
   * @param {string} appKey - The desired application key
   * @returns {Promise} Preview of the generated application
   */
  async previewPublishing(flowId, appKey) {
    const response = await axios.get(`${API_BASE_URL}/preview`, {
      params: { flow_id: flowId, app_key: appKey }
    });
    return response.data;
  },

  /**
   * Publish a flow as an application
   * @param {Object} publishData - Publishing configuration
   * @param {string} publishData.flow_id - The ID of the flow to publish
   * @param {string} publishData.app_key - The desired application key
   * @param {string} publishData.app_name - The application name
   * @param {string} publishData.description - Application description
   * @param {string} publishData.category - Application category
   * @param {boolean} publishData.auto_update - Auto-update when source flow changes
   * @returns {Promise} Publishing result
   */
  async publishFlow(publishData) {
    const response = await axios.post(`${API_BASE_URL}/publish`, publishData);
    return response.data;
  },

  /**
   * Get list of published applications
   * @param {Object} params - Query parameters
   * @param {string} params.search - Search query
   * @param {string} params.status - Filter by status (active, inactive, deprecated)
   * @param {string} params.sort_by - Field to sort by
   * @param {string} params.sort_order - Sort order (asc/desc)
   * @returns {Promise} List of published applications
   */
  async getPublishedApplications(params = {}) {
    const response = await axios.get(`${API_BASE_URL}/applications`, { params });
    return response.data;
  },

  /**
   * Get details of a specific published application
   * @param {string} publishedAppId - The ID of the published application
   * @returns {Promise} Application details
   */
  async getPublishedApplication(publishedAppId) {
    const response = await axios.get(`${API_BASE_URL}/applications/${publishedAppId}`);
    return response.data;
  },

  /**
   * Update a published application
   * @param {string} publishedAppId - The ID of the published application
   * @param {Object} updateData - Update configuration
   * @param {boolean} updateData.force_update - Force update even if there are breaking changes
   * @returns {Promise} Update result
   */
  async updatePublishedApplication(publishedAppId, updateData = {}) {
    const response = await axios.put(`${API_BASE_URL}/applications/${publishedAppId}/update`, updateData);
    return response.data;
  },

  /**
   * Unpublish an application
   * @param {string} publishedAppId - The ID of the published application
   * @returns {Promise} Unpublish result
   */
  async unpublishApplication(publishedAppId) {
    const response = await axios.delete(`${API_BASE_URL}/applications/${publishedAppId}`);
    return response.data;
  },

  /**
   * Get version history of a published application
   * @param {string} publishedAppId - The ID of the published application
   * @returns {Promise} Version history
   */
  async getVersionHistory(publishedAppId) {
    const response = await axios.get(`${API_BASE_URL}/applications/${publishedAppId}/versions`);
    return response.data;
  },

  /**
   * Get dependencies of a published application
   * @param {string} publishedAppId - The ID of the published application
   * @returns {Promise} Dependencies list
   */
  async getDependencies(publishedAppId) {
    const response = await axios.get(`${API_BASE_URL}/applications/${publishedAppId}/dependencies`);
    return response.data;
  },

  /**
   * Get parameter mappings of a published application
   * @param {string} publishedAppId - The ID of the published application
   * @returns {Promise} Parameter mappings
   */
  async getParameterMappings(publishedAppId) {
    const response = await axios.get(`${API_BASE_URL}/applications/${publishedAppId}/parameters`);
    return response.data;
  },

  /**
   * Get publishing statistics
   * @returns {Promise} Statistics about published applications
   */
  async getStatistics() {
    const response = await axios.get(`${API_BASE_URL}/statistics`);
    return response.data;
  },

  /**
   * Publish flow directly as frontend application (without creating reusable app)
   * @param {Object} publishData - Publishing configuration
   * @returns {Promise} Publishing result
   */
  async publishFrontendDirect(publishData) {
    const response = await axios.post('/api/v1/direct-frontend-publishing/publish-frontend-direct', publishData);
    return response.data;
  },

  /**
   * Create frontend application from a published app
   * @param {Object} frontendData - Frontend app configuration
   * @returns {Promise} Frontend app creation result
   */
  async createFrontendFromPublishedApp(frontendData) {
    const response = await axios.post('/api/v1/frontend-applications/from-published-app', frontendData);
    return response.data;
  },

  /**
   * Publish flow as Micro SaaS app
   * @param {Object} microSaasData - Micro SaaS app configuration
   * @returns {Promise} Publishing result
   */
  async publishMicroSaasApp(microSaasData) {
    // Set the publish_as_micro_saas flag
    const publishData = {
      ...microSaasData,
      publish_as_micro_saas: true
    };

    const response = await axios.post(`${API_BASE_URL}/publish`, publishData);
    return response.data;
  },

  /**
   * Publish flow with multiple types (reusable, frontend, or both)
   * @param {Object} publishData - Publishing configuration with publish_type
   * @returns {Promise} Publishing result
   */
  async publishFlowWithTypes(publishData) {
    const { publish_type, frontend_config, ...reusableConfig } = publishData;

    const results = {
      success: true,
      publish_type,
      reusable_app: null,
      frontend_app: null,
      errors: []
    };

    try {
      // Step 1: Create reusable application if needed
      if (publish_type === 'reusable' || publish_type === 'both') {
        try {
          const reusableResult = await this.publishFlow(reusableConfig);
          results.reusable_app = reusableResult;
        } catch (error) {
          results.errors.push(`Reusable app creation failed: ${error.message}`);
          if (publish_type === 'reusable') {
            results.success = false;
            return results;
          }
        }
      }

      // Step 2: Create frontend application
      if (publish_type === 'frontend' || publish_type === 'both') {
        try {
          if (publish_type === 'frontend') {
            // Direct frontend publishing (no reusable app)
            const frontendResult = await this.publishFrontendDirect({
              flow_id: publishData.flow_id,
              frontend_app_name: `${reusableConfig.app_name || 'Flow'} - Public`,
              description: `Public interface for ${reusableConfig.app_name || 'flow'}`,
              access_type: frontend_config.access_type || 'public_url',
              access_config: frontend_config.access_config || {},
              rate_limit_per_hour: frontend_config.rate_limit_per_hour || 100
            });
            results.frontend_app = frontendResult;
          } else if (publish_type === 'both' && results.reusable_app?.published_app_id) {
            // Create frontend app from the published reusable app
            const frontendResult = await this.createFrontendFromPublishedApp({
              published_app_id: results.reusable_app.published_app_id,
              frontend_app_name: `${reusableConfig.app_name || 'Flow'} - Public`,
              description: `Public interface for ${reusableConfig.app_name || 'flow'}`,
              access_type: frontend_config.access_type || 'public_url',
              access_config: frontend_config.access_config || {},
              rate_limit_per_hour: frontend_config.rate_limit_per_hour || 100,
              embed_enabled: true
            });
            results.frontend_app = frontendResult;
          }
        } catch (error) {
          results.errors.push(`Frontend app creation failed: ${error.message}`);
          if (publish_type === 'frontend') {
            results.success = false;
          }
        }
      }

      return results;

    } catch (error) {
      return {
        success: false,
        publish_type,
        error: error.message,
        errors: [error.message]
      };
    }
  }
};

export default flowPublishingService;