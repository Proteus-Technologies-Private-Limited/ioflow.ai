import React, { useState, useEffect } from 'react';
import { XMarkIcon, KeyIcon, Cog6ToothIcon, BeakerIcon, CheckCircleIcon, XCircleIcon, EyeIcon, EyeSlashIcon, DocumentDuplicateIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';
import CustomParametersConfig from './CustomParametersConfig';
import OAuth2FlowButton from './OAuth2FlowButton';
import { formatDateTime } from '../../utils/dateFormatter';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const ConnectionSettingsModal = ({ application, subscription, onClose, onUpdate }) => {
  const [settings, setSettings] = useState({
    base_url: subscription?.application?.base_url || '',
    auth_credentials: {},
    test_endpoint: '/health', // Default test endpoint
    custom_params: {} // Custom parameters
  });
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});
  const [getPendingParam, setGetPendingParam] = useState(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [isRegeneratingKey, setIsRegeneratingKey] = useState(false);
  
  // Debug: Log when getPendingParam changes
  React.useEffect(() => {
    console.log('getPendingParam updated:', getPendingParam);
  }, [getPendingParam]);

  useEffect(() => {
    // Initialize with existing values
    if (subscription) {
      console.log('ConnectionSettingsModal - Loading subscription:', subscription);
      console.log('subscription_config:', subscription.subscription_config);
      console.log('subscription.application:', subscription.application);
      console.log('application prop:', application);
      
      // First check if custom params are stored in subscription_config
      const configCustomParams = subscription.subscription_config?.custom_params || {};
      
      // If not in config, extract from auth_credentials
      const extractedCustomParams = {};
      
      // Extract non-auth fields from auth_credentials as custom params
      if (subscription.auth_credentials) {
        // Headers (excluding standard auth headers)
        if (subscription.auth_credentials.headers) {
          const customHeaders = { ...subscription.auth_credentials.headers };
          // Remove standard auth headers
          delete customHeaders.Authorization;
          delete customHeaders.authorization;
          if (Object.keys(customHeaders).length > 0) {
            extractedCustomParams.header = customHeaders;
          }
        }
        
        // Query params
        if (subscription.auth_credentials.query_params) {
          extractedCustomParams.query = subscription.auth_credentials.query_params;
        }
        
        // Body params
        if (subscription.auth_credentials.body_params) {
          extractedCustomParams.body = subscription.auth_credentials.body_params;
        }
      }
      
      // Merge config params with extracted params (config takes precedence)
      const finalCustomParams = { ...extractedCustomParams, ...configCustomParams };
      
      console.log('ConnectionSettingsModal - Loaded custom params:', finalCustomParams);
      
      // Extract base auth credentials (without custom params)
      const baseAuthCredentials = {};
      if (subscription.auth_credentials) {
        // Copy only auth-specific fields
        if (subscription.auth_credentials.api_key) {
          baseAuthCredentials.api_key = subscription.auth_credentials.api_key;
        }
        if (subscription.auth_credentials.username) {
          baseAuthCredentials.username = subscription.auth_credentials.username;
        }
        if (subscription.auth_credentials.password) {
          baseAuthCredentials.password = subscription.auth_credentials.password;
        }
        if (subscription.auth_credentials.client_id) {
          baseAuthCredentials.client_id = subscription.auth_credentials.client_id;
        }
        if (subscription.auth_credentials.client_secret) {
          baseAuthCredentials.client_secret = subscription.auth_credentials.client_secret;
        }
        if (subscription.auth_credentials.access_token) {
          baseAuthCredentials.access_token = subscription.auth_credentials.access_token;
        }
        if (subscription.auth_credentials.token_type) {
          baseAuthCredentials.token_type = subscription.auth_credentials.token_type;
        }
      }
      
      // Debug logging
      console.log('Setting base_url from:', {
        'subscription.application?.base_url': subscription.application?.base_url,
        'application?.base_url': application?.base_url,
        'subscription.subscription_config?.base_url': subscription.subscription_config?.base_url
      });
      
      setSettings({
        base_url: subscription.application?.base_url || application?.base_url || subscription.subscription_config?.base_url || '',
        auth_credentials: baseAuthCredentials,
        test_endpoint: subscription.subscription_config?.test_endpoint || '/health',
        custom_params: finalCustomParams
      });
    }
  }, [subscription, application]);

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);

    try {
      const token = localStorage.getItem('access_token');
      
      // Merge custom parameters for testing
      const testCredentials = { ...settings.auth_credentials };
      
      // Add custom headers if any
      if (settings.custom_params.header) {
        testCredentials.headers = {
          ...(testCredentials.headers || {}),
          ...settings.custom_params.header
        };
      }
      
      // Add custom query params if any
      if (settings.custom_params.query) {
        testCredentials.query_params = {
          ...(testCredentials.query_params || {}),
          ...settings.custom_params.query
        };
      }
      
      // Add custom body params if any
      if (settings.custom_params.body) {
        testCredentials.body_params = {
          ...(testCredentials.body_params || {}),
          ...settings.custom_params.body
        };
      }
      
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/test-connection`,
        {
          base_url: settings.base_url,
          test_endpoint: settings.test_endpoint,
          auth_type: application?.auth_type || 'none',
          auth_credentials: testCredentials,
          auth_config: application?.auth_config || {},
          method: 'GET',
          timeout: 10,
          headers: settings.custom_params.header || {}
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setTestResult({
        success: response.data.success,
        message: response.data.success 
          ? `Connection successful! Status: ${response.data.status_code}`
          : response.data.error || 'Connection failed',
        details: response.data
      });

      if (response.data.success) {
        showSuccessToast('Connection test successful!');
      } else {
        showErrorToast('Connection test failed');
      }
    } catch (error) {
      setTestResult({
        success: false,
        message: (error.response?.data?.message || error.response?.data?.detail) || 'Failed to test connection',
        details: error.response?.data
      });
      showErrorToast('Connection test failed');
    } finally {
      setIsTesting(false);
    }
  };

  const handleSave = async () => {
    console.log('handleSave called');
    
    // Simple check: Look for input fields with values in the custom params section
    const paramKeyInput = document.querySelector('input[placeholder="Parameter name"]');
    const paramValueInput = document.querySelector('input[placeholder="Parameter value"]');
    
    console.log('Param inputs found:', { key: paramKeyInput?.value, value: paramValueInput?.value });
    
    if (paramKeyInput && paramValueInput && paramKeyInput.value && paramValueInput.value) {
      // There's a pending parameter that hasn't been added
      showErrorToast(`Please add the custom parameter "${paramKeyInput.value}" by clicking the + button before saving.`);
      return;
    }
    
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      
      let finalCustomParams = { ...settings.custom_params };
      
      // First, update the application's base_url if it's different
      if (application?.base_url !== settings.base_url && application?.app_id) {
        try {
          await axios.put(
            `${API_BASE_URL}/api/v1/applications/${application.app_id}`,
            { base_url: settings.base_url },
            { headers: { Authorization: `Bearer ${token}` } }
          );
        } catch (appError) {
          // If we can't update the application base_url (e.g., no permission), continue with subscription update
          console.warn('Could not update application base_url:', appError);
        }
      }
      
      // Update subscription with new settings
      // Store custom params in subscription_config to avoid masking issues
      const updateData = {
        auth_credentials: settings.auth_credentials, // Only store actual auth credentials
        subscription_config: {
          ...(subscription?.subscription_config || {}),
          base_url: settings.base_url,
          test_endpoint: settings.test_endpoint,
          custom_params: finalCustomParams // Store custom params with any pending ones
        }
      };

      console.log('Saving connection settings:', updateData);
      console.log('Custom params being saved:', updateData.subscription_config.custom_params);
      
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}`,
        updateData,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      console.log('Response from server:', response.data);
      console.log('Response subscription_config:', response.data.subscription_config);
      
      showSuccessToast('Connection settings updated successfully!');
      
      // Since the backend properly saves subscription_config, we should use the response as-is
      // The backend should have saved our custom_params in subscription_config
      onUpdate(response.data);
      onClose();
    } catch (error) {
      console.error('Save error:', error);
      console.error('Error response:', error.response);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || error.message || 'Failed to update connection settings');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleShowSecret = (field) => {
    setShowSecrets(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const renderCredentialFields = () => {
    const authType = application?.auth_type;

    switch (authType) {
      case 'api_key':
        return (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Key <span className="text-red-500">*</span>
            </label>
            <div className="relative">
              <input
                type={showSecrets.api_key ? 'text' : 'password'}
                value={settings.auth_credentials.api_key || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  auth_credentials: { ...settings.auth_credentials, api_key: e.target.value }
                })}
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="Enter your API key"
              />
              <button
                type="button"
                onClick={() => toggleShowSecret('api_key')}
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                {showSecrets.api_key ? (
                  <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                ) : (
                  <EyeIcon className="h-5 w-5 text-gray-400" />
                )}
              </button>
            </div>
          </div>
        );

      case 'basic':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Username <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={settings.auth_credentials.username || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  auth_credentials: { ...settings.auth_credentials, username: e.target.value }
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="Enter username"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showSecrets.password ? 'text' : 'password'}
                  value={settings.auth_credentials.password || ''}
                  onChange={(e) => setSettings({
                    ...settings,
                    auth_credentials: { ...settings.auth_credentials, password: e.target.value }
                  })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="Enter password"
                />
                <button
                  type="button"
                  onClick={() => toggleShowSecret('password')}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                >
                  {showSecrets.password ? (
                    <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <EyeIcon className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              </div>
            </div>
          </div>
        );

      case 'oauth2':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Client ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={settings.auth_credentials.client_id || ''}
                onChange={(e) => setSettings({
                  ...settings,
                  auth_credentials: { ...settings.auth_credentials, client_id: e.target.value }
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="Enter client ID"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Client Secret <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showSecrets.client_secret ? 'text' : 'password'}
                  value={settings.auth_credentials.client_secret || ''}
                  onChange={(e) => setSettings({
                    ...settings,
                    auth_credentials: { ...settings.auth_credentials, client_secret: e.target.value }
                  })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="Enter client secret"
                />
                <button
                  type="button"
                  onClick={() => toggleShowSecret('client_secret')}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                >
                  {showSecrets.client_secret ? (
                    <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <EyeIcon className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              </div>
            </div>
            
            {/* OAuth2 Flow Button */}
            <OAuth2FlowButton 
              application={application}
              subscription={subscription}
              onSuccess={() => {
                onUpdate();
                showSuccessToast('OAuth2 connection updated successfully');
              }}
            />
          </div>
        );

      case 'none':
        return (
          <div className="text-sm text-gray-500">
            No authentication required for this application.
          </div>
        );

      default:
        return (
          <div className="text-sm text-gray-500">
            Custom authentication type. Please refer to the application documentation.
          </div>
        );
    }
  };

  const handleCopyApiKey = () => {
    if (subscription?.invocation_api_key) {
      navigator.clipboard.writeText(subscription.invocation_api_key);
      showSuccessToast('API key copied to clipboard!');
    }
  };

  const handleRegenerateApiKey = async () => {
    if (!window.confirm('Are you sure you want to regenerate the API key? The old key will stop working immediately.')) {
      return;
    }

    setIsRegeneratingKey(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}/regenerate-api-key`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      showSuccessToast('API key regenerated successfully!');
      
      // Update the subscription with the new API key
      onUpdate({
        ...subscription,
        invocation_api_key: response.data.invocation_api_key,
        api_key_created_at: response.data.api_key_created_at
      });
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to regenerate API key');
    } finally {
      setIsRegeneratingKey(false);
    }
  };

  const isFormValid = () => {
    if (!settings.base_url) return false;
    
    const authType = application?.auth_type;
    switch (authType) {
      case 'api_key':
        return !!settings.auth_credentials.api_key;
      case 'basic':
        return !!settings.auth_credentials.username && !!settings.auth_credentials.password;
      case 'oauth2':
        return !!settings.auth_credentials.client_id && !!settings.auth_credentials.client_secret;
      default:
        return true;
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between sticky top-0 bg-white">
          <div className="flex items-center">
            <Cog6ToothIcon className="w-5 h-5 text-gray-400 mr-2" />
            <h3 className="text-lg font-medium text-gray-900">
              Connection Settings - {application?.app_name}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-6">
          {/* Invocation API Key Section */}
          {subscription?.invocation_api_key && (
            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3">Invocation API Key</h4>
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-start">
                  <KeyIcon className="w-5 h-5 text-yellow-600 mr-2 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="text-sm text-yellow-800 mb-2">
                      Use this API key to authenticate webhook and API calls to IOFlow for this application.
                    </p>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <input
                          type={showApiKey ? 'text' : 'password'}
                          value={subscription.invocation_api_key}
                          readOnly
                          className="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-md font-mono text-sm"
                        />
                        <button
                          type="button"
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="p-2 text-gray-500 hover:text-gray-700"
                          title={showApiKey ? 'Hide API key' : 'Show API key'}
                        >
                          {showApiKey ? (
                            <EyeSlashIcon className="w-5 h-5" />
                          ) : (
                            <EyeIcon className="w-5 h-5" />
                          )}
                        </button>
                        <button
                          type="button"
                          onClick={handleCopyApiKey}
                          className="p-2 text-gray-500 hover:text-gray-700"
                          title="Copy API key"
                        >
                          <DocumentDuplicateIcon className="w-5 h-5" />
                        </button>
                        <button
                          type="button"
                          onClick={handleRegenerateApiKey}
                          disabled={isRegeneratingKey}
                          className="p-2 text-yellow-600 hover:text-yellow-700 disabled:opacity-50"
                          title="Regenerate API key"
                        >
                          <ArrowPathIcon className={`w-5 h-5 ${isRegeneratingKey ? 'animate-spin' : ''}`} />
                        </button>
                      </div>
                      {subscription.api_key_created_at && (
                        <p className="text-xs text-gray-500">
                          Created: {formatDateTime(subscription.api_key_created_at)}
                        </p>
                      )}
                      {subscription.api_key_last_used_at && (
                        <p className="text-xs text-gray-500">
                          Last used: {formatDateTime(subscription.api_key_last_used_at)}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Base URL Section */}
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">API Configuration</h4>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Base URL <span className="text-red-500">*</span>
                </label>
                <input
                  type="url"
                  value={settings.base_url}
                  onChange={(e) => setSettings({ ...settings, base_url: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="https://api.example.com"
                />
                <p className="mt-1 text-xs text-gray-500">
                  The base URL for all API requests to this application
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Test Endpoint
                </label>
                <input
                  type="text"
                  value={settings.test_endpoint}
                  onChange={(e) => setSettings({ ...settings, test_endpoint: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="/health or /api/v1/status"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Endpoint to test the connection (relative to base URL)
                </p>
              </div>
            </div>
          </div>

          {/* Authentication Section */}
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Authentication</h4>
            {renderCredentialFields()}
          </div>

          {/* Test Connection Section */}
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-3">Test Connection</h4>
            <div className="bg-gray-50 rounded-lg p-4">
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={!isFormValid() || isTesting}
                className="w-full px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
              >
                <BeakerIcon className="w-5 h-5 mr-2" />
                {isTesting ? 'Testing Connection...' : 'Test Connection'}
              </button>

              {testResult && (
                <div className={`mt-4 p-4 rounded-md ${testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
                  <div className="flex items-start">
                    {testResult.success ? (
                      <CheckCircleIcon className="w-5 h-5 text-green-600 mr-2 flex-shrink-0 mt-0.5" />
                    ) : (
                      <XCircleIcon className="w-5 h-5 text-red-600 mr-2 flex-shrink-0 mt-0.5" />
                    )}
                    <div className="flex-1">
                      <p className={`text-sm font-medium ${testResult.success ? 'text-green-800' : 'text-red-800'}`}>
                        {testResult.message}
                      </p>
                      {testResult.details && (
                        <details className="mt-2">
                          <summary className="text-xs text-gray-600 cursor-pointer">View details</summary>
                          <pre className="mt-2 text-xs text-gray-600 overflow-x-auto">
                            {JSON.stringify(testResult.details, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Custom Parameters Section */}
          <div>
            <CustomParametersConfig
              parameters={settings.custom_params}
              onChange={(params) => setSettings({ ...settings, custom_params: params })}
              title="Custom API Parameters"
              onGetPendingParam={setGetPendingParam}
            />
            <p className="mt-2 text-xs text-gray-500">
              Configure custom headers, query parameters, or body parameters that will be included in every API request to this application.
            </p>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3 sticky bottom-0 bg-white">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!isFormValid() || isLoading}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {isLoading ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConnectionSettingsModal;