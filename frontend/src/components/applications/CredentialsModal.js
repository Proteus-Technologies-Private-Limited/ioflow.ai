import React, { useState, useEffect } from 'react';
import { XMarkIcon, KeyIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const CredentialsModal = ({ application, onClose, onConnect }) => {
  const [credentials, setCredentials] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [showSecrets, setShowSecrets] = useState({});
  const [credentialSchema, setCredentialSchema] = useState(null);
  const [testEndpoint, setTestEndpoint] = useState('');
  const [showTestEndpoint, setShowTestEndpoint] = useState(false);

  // Fetch credential schema when modal opens
  useEffect(() => {
    const fetchSchema = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const response = await axios.get(
          `${API_BASE_URL}/api/v1/applications/${application.app_id}/credential-schema`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setCredentialSchema(response.data);
      } catch (error) {
        console.error('Failed to fetch credential schema:', error);
      }
    };

    if (application?.app_id) {
      fetchSchema();
      // Set test endpoint from auth_config if available
      if (application?.auth_config?.test_endpoint) {
        setTestEndpoint(application.auth_config.test_endpoint);
      }
    }
  }, [application]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await onConnect(credentials);
      onClose();
    } catch (error) {
      // Error is handled by parent component
    } finally {
      setIsLoading(false);
    }
  };

  const handleTestCredentials = async () => {
    setIsTesting(true);

    try {
      const token = localStorage.getItem('access_token');
      
      let testPayload = {
        auth_credentials: credentials,
        test_method: 'GET'
      };

      // Add test endpoint if provided
      if (testEndpoint) {
        testPayload.test_endpoint = testEndpoint;
      }

      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/${application.app_id}/test-auth`,
        testPayload,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.data.success) {
        if (response.data.credential_validation_only) {
          showSuccessToast('Credential format is valid!');
        } else {
          showSuccessToast('Authentication test successful!');
        }
      } else {
        // Show detailed error message
        if (response.data.help_text) {
          const errorMessage = `${response.data.error}. ${response.data.help_text}${response.data.help_url ? ` Visit: ${response.data.help_url}` : ''}`;
          showErrorToast(errorMessage);
        } else {
          showErrorToast(response.data.error || 'Authentication test failed');
        }
      }
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to test credentials');
    } finally {
      setIsTesting(false);
    }
  };

  const toggleShowSecret = (field) => {
    setShowSecrets(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const renderCredentialFields = () => {
    const authType = application?.auth_type;
    const webhookConfig = typeof application?.webhook_config === 'string' 
      ? JSON.parse(application.webhook_config) 
      : application?.webhook_config;

    // Check if we need webhook signing secret
    const needsSigningSecret = webhookConfig?.signing_secret_required || webhookConfig?.secret_required;

    return (
      <div className="space-y-6">
        {/* Authentication Credentials */}
        <div>
          {renderAuthFields(authType)}
        </div>

        {/* Webhook Signing Secret */}
        {needsSigningSecret && (
          <div className="border-t pt-4">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Webhook Security</h4>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Signing Secret <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showSecrets.signing_secret ? 'text' : 'password'}
                  value={credentials.signing_secret || ''}
                  onChange={(e) => setCredentials({ ...credentials, signing_secret: e.target.value })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="Enter webhook signing secret"
                  required={needsSigningSecret}
                />
                <button
                  type="button"
                  onClick={() => toggleShowSecret('signing_secret')}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                >
                  {showSecrets.signing_secret ? (
                    <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                  ) : (
                    <EyeIcon className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Used to verify that webhooks are sent by {application?.app_name}
              </p>
            </div>
          </div>
        )}
      </div>
    );
  };

  const renderAuthFields = (authType) => {
    switch (authType) {
      case 'api_key':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showSecrets.api_key ? 'text' : 'password'}
                  value={credentials.api_key || ''}
                  onChange={(e) => setCredentials({ ...credentials, api_key: e.target.value })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="Enter your API key"
                  required
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
              {credentialSchema?.auth_config?.header_name && (
                <p className="mt-1 text-xs text-gray-500">
                  This will be sent in the {credentialSchema.auth_config.header_name} header
                  {credentialSchema.auth_config.header_prefix && ` with prefix "${credentialSchema.auth_config.header_prefix}"`}
                </p>
              )}
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
                value={credentials.username || ''}
                onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="Enter username"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showSecrets.password ? 'text' : 'password'}
                  value={credentials.password || ''}
                  onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="Enter password"
                  required
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
            {/* OAuth2 Help Message */}
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
              <p className="text-sm text-blue-800">
                <strong>Important:</strong> OAuth2 requires application credentials from {application?.app_name}'s developer console, 
                not your personal login credentials.
              </p>
              {application?.app_name === 'Google Sheets' && (
                <a 
                  href="https://console.cloud.google.com/apis/credentials" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="text-sm text-blue-600 hover:text-blue-700 underline mt-1 block"
                >
                  Create Google OAuth2 credentials →
                </a>
              )}
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Client ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={credentials.client_id || ''}
                onChange={(e) => setCredentials({ ...credentials, client_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder={application?.app_name === 'Google Sheets' ? "e.g., 123456789-abc.apps.googleusercontent.com" : "Enter OAuth2 client ID"}
                required
              />
              <p className="text-xs text-gray-500 mt-1">Not your email address</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Client Secret <span className="text-red-500">*</span>
              </label>
              <div className="relative">
                <input
                  type={showSecrets.client_secret ? 'text' : 'password'}
                  value={credentials.client_secret || ''}
                  onChange={(e) => setCredentials({ ...credentials, client_secret: e.target.value })}
                  className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder={application?.app_name === 'Google Sheets' ? "e.g., GOCSPX-..." : "Enter OAuth2 client secret"}
                  required
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
              <p className="text-xs text-gray-500 mt-1">Not your personal password</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Scope (Optional)
              </label>
              <input
                type="text"
                value={credentials.scope || ''}
                onChange={(e) => setCredentials({ ...credentials, scope: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="e.g., read write"
              />
              <p className="mt-1 text-xs text-gray-500">
                OAuth2 scopes (space-separated). Leave empty to use default scope.
              </p>
            </div>
            {credentialSchema?.auth_config?.token_url && (
              <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                <p className="text-xs text-blue-700">
                  Token URL: {credentialSchema.auth_config.token_url}
                </p>
              </div>
            )}
          </div>
        );

      case 'custom':
        return (
          <div className="space-y-4">
            <p className="text-sm text-gray-600 mb-3">
              Enter the required authentication parameters for this application:
            </p>
            
            {credentialSchema?.auth_config?.required_headers?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Required Headers</h4>
                {credentialSchema.auth_config.required_headers.map((header) => (
                  <div key={header} className="mb-3">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {header} <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={credentials.headers?.[header] || ''}
                      onChange={(e) => setCredentials({
                        ...credentials,
                        headers: { ...credentials.headers, [header]: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder={`Enter ${header}`}
                      required
                    />
                  </div>
                ))}
              </div>
            )}

            {credentialSchema?.auth_config?.required_query_params?.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-2">Required Query Parameters</h4>
                {credentialSchema.auth_config.required_query_params.map((param) => (
                  <div key={param} className="mb-3">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {param} <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={credentials.query_params?.[param] || ''}
                      onChange={(e) => setCredentials({
                        ...credentials,
                        query_params: { ...credentials.query_params, [param]: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      placeholder={`Enter ${param}`}
                      required
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      default:
        return (
          <div className="text-sm text-gray-500">
            No authentication required for this application.
          </div>
        );
    }
  };

  const isFormValid = () => {
    const authType = application?.auth_type;
    const webhookConfig = typeof application?.webhook_config === 'string' 
      ? JSON.parse(application.webhook_config) 
      : application?.webhook_config;
    const needsSigningSecret = webhookConfig?.signing_secret_required || webhookConfig?.secret_required;
    
    // First check auth requirements
    let authValid = false;
    switch (authType) {
      case 'api_key':
        authValid = !!credentials.api_key;
        break;
      case 'basic':
        authValid = !!credentials.username && !!credentials.password;
        break;
      case 'oauth2':
        authValid = !!credentials.client_id && !!credentials.client_secret;
        break;
      case 'custom':
        // Check all required fields
        const config = credentialSchema?.auth_config || {};
        const requiredHeaders = config.required_headers || [];
        const requiredParams = config.required_query_params || [];
        
        authValid = true;
        for (const header of requiredHeaders) {
          if (!credentials.headers?.[header]) {
            authValid = false;
            break;
          }
        }
        if (authValid) {
          for (const param of requiredParams) {
            if (!credentials.query_params?.[param]) {
              authValid = false;
              break;
            }
          }
        }
        break;
      default:
        authValid = true;
    }
    
    // Then check webhook requirements
    const webhookValid = !needsSigningSecret || !!credentials.signing_secret;
    
    return authValid && webhookValid;
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-hidden">
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center">
              <KeyIcon className="w-5 h-5 text-gray-400 mr-2" />
              <h3 className="text-lg font-medium text-gray-900">
                Connect to {application?.app_name}
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

          <div className="px-6 py-4 space-y-4 overflow-y-auto max-h-[calc(90vh-200px)]">
            {application?.description && (
              <div className="bg-gray-50 rounded-md p-3">
                <p className="text-sm text-gray-600">{application.description}</p>
              </div>
            )}

            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3">Authentication Credentials</h4>
              {renderCredentialFields()}
            </div>

            {/* Test Endpoint Section */}
            <div className="border-t pt-4">
              <button
                type="button"
                onClick={() => setShowTestEndpoint(!showTestEndpoint)}
                className="text-sm text-indigo-600 hover:text-indigo-500"
              >
                {showTestEndpoint ? 'Hide' : 'Show'} test endpoint (optional)
              </button>
              
              {showTestEndpoint && (
                <div className="mt-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Test Endpoint URL
                  </label>
                  <input
                    type="url"
                    value={testEndpoint}
                    onChange={(e) => setTestEndpoint(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="https://api.example.com/test"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Optional: Provide an endpoint to test the authentication. If not provided, only credential format will be validated.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
            <button
              type="button"
              onClick={handleTestCredentials}
              disabled={!isFormValid() || isTesting}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {isTesting ? 'Testing...' : 'Test Connection'}
            </button>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!isFormValid() || isLoading}
                className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
              >
                {isLoading ? 'Connecting...' : 'Connect'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CredentialsModal;