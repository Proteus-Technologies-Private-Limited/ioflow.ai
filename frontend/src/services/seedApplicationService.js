import axios from 'axios';

const API_BASE_URL = '/api/v1/seed-applications';

/**
 * Service for managing seed applications
 */
export const seedApplicationService = {
  /**
   * Get list of all available seed applications
   * @param {Object} params - Query parameters
   * @param {string} params.search - Search query
   * @param {string} params.sort_by - Field to sort by
   * @param {string} params.sort_order - Sort order (asc/desc)
   * @returns {Promise} List of seed applications with their status
   */
  async getApplications(params = {}) {
    const response = await axios.get(`${API_BASE_URL}/`, { params });
    return response.data;
  },

  /**
   * Get details of a specific seed application
   * @param {string} applicationKey - The key of the application
   * @returns {Promise} Application details
   */
  async getApplication(applicationKey) {
    const response = await axios.get(`${API_BASE_URL}/${applicationKey}`);
    return response.data;
  },

  /**
   * Get installation warning for an application
   * @param {string} applicationKey - The key of the application
   * @returns {Promise} Warning information or null
   */
  async getInstallationWarning(applicationKey) {
    const response = await axios.get(`${API_BASE_URL}/${applicationKey}/installation-warning`);
    return response.data;
  },

  /**
   * Install or reinstall a seed application
   * @param {string} applicationKey - The key of the application to install
   * @param {boolean} forceReinstall - Whether to force reinstall if already installed
   * @returns {Promise} Installation result
   */
  async installApplication(applicationKey, forceReinstall = false) {
    const response = await axios.post(`${API_BASE_URL}/install`, {
      application_key: applicationKey,
      force_reinstall: forceReinstall
    });
    return response.data;
  },

  /**
   * Refresh the seed applications cache
   * @returns {Promise} Refresh result
   */
  async refreshCache() {
    const response = await axios.post(`${API_BASE_URL}/refresh-cache`);
    return response.data;
  },

  /**
   * Delete a seed application
   * @param {string} applicationKey - The key of the application to delete
   * @returns {Promise} Deletion result
   */
  async deleteApplication(applicationKey) {
    const response = await axios.delete(`${API_BASE_URL}/${applicationKey}`);
    return response.data;
  },

  /**
   * Update an installed application to the latest seed version
   * @param {string} applicationKey - The key of the application to update
   * @returns {Promise} Update result
   */
  async updateApplication(applicationKey) {
    const response = await axios.post(`${API_BASE_URL}/${applicationKey}/update`);
    return response.data;
  },

  /**
   * Uninstall an installed seed application
   * @param {string} applicationKey - The key of the application to uninstall
   * @param {boolean} force - Whether to force uninstall (delete subscriptions)
   * @returns {Promise} Uninstallation result
   */
  async uninstallApplication(applicationKey, force = false) {
    const response = await axios.post(`${API_BASE_URL}/${applicationKey}/uninstall`, null, {
      params: { force }
    });
    return response.data;
  },

  /**
   * Get the raw JSON of a seed application
   * @param {string} applicationKey - The key of the application
   * @returns {Promise} Raw JSON data
   */
  async getApplicationJson(applicationKey) {
    const response = await axios.get(`${API_BASE_URL}/${applicationKey}/json`);
    return response.data;
  },

  /**
   * Update the raw JSON of a seed application
   * @param {string} applicationKey - The key of the application
   * @param {object} jsonData - The updated JSON data
   * @returns {Promise} Update result
   */
  async updateApplicationJson(applicationKey, jsonData) {
    const response = await axios.put(`${API_BASE_URL}/${applicationKey}/json`, jsonData);
    return response.data;
  },

  /**
   * Verify an installed application against its seed JSON
   * @param {string} applicationKey - The key of the application
   * @returns {Promise} Verification result with parameter comparison
   */
  async verifyApplication(applicationKey) {
    const response = await axios.get(`${API_BASE_URL}/${applicationKey}/verify`);
    return response.data;
  },

  /**
   * Validate a seed application schema
   * @param {string} applicationKey - The key of the application
   * @returns {Promise} Validation result with errors and warnings
   */
  async validateApplication(applicationKey) {
    const response = await axios.get(`${API_BASE_URL}/${applicationKey}/validate`);
    return response.data;
  }
};

export default seedApplicationService;