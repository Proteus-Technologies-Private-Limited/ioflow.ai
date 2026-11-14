import React, { useState, useEffect } from 'react';
import { XMarkIcon, KeyIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';
import { usePluginRegistry } from '../../plugins/registry';
import SchemaRenderer from '../../plugins/SchemaRenderer';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const AuthConfigModal = ({ application, onClose, onUpdate }) => {
  const [authType, setAuthType] = useState(application?.auth_type || 'none');
  const [authConfig, setAuthConfig] = useState(application?.auth_config || {});
  const [isLoading, setIsLoading] = useState(false);
  const [credentialSchema, setCredentialSchema] = useState(null);
  const [isTestingCredentials, setIsTestingCredentials] = useState(false);
  const pluginRegistry = usePluginRegistry();

  // Fetch credential schema when auth type changes
  useEffect(() => {
    const fetchSchema = async () => {
      if (authType === 'none') {
        setCredentialSchema(null);
        return;
      }

      try {
        const token = localStorage.getItem('access_token');
        const response = await axios.get(
          `${API_BASE_URL}/api/v1/applications/auth-types/${authType}/config-schema`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setCredentialSchema(response.data);
      } catch (error) {
        console.error('Failed to fetch auth schema:', error);
      }
    };

    fetchSchema();
  }, [authType]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/applications/${application.app_id}/auth-config`,
        {
          auth_type: authType,
          auth_config: authConfig
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      showSuccessToast('Authentication configuration updated successfully');
      onUpdate(response.data);
      onClose();
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update authentication configuration');
    } finally {
      setIsLoading(false);
    }
  };
  
  const testDefaultOAuthCredentials = async () => {
    setIsTestingCredentials(true);
    
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/${application.app_id}/test-default-oauth`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      if (response.data.success) {
        showSuccessToast(response.data.message || 'OAuth credentials are valid!');
      } else {
        showErrorToast(response.data.error || 'OAuth credentials test failed');
      }
    } catch (error) {
      const errorMsg = (error.response?.data?.message || error.response?.data?.detail) || error.response?.data?.error || 'Failed to test credentials';
      showErrorToast(errorMsg);
    } finally {
      setIsTestingCredentials(false);
    }
  };

  const renderAuthConfigFields = () => {
    switch (authType) {
      case 'api_key':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Header Name
              </label>
              <input
                type="text"
                value={authConfig.header_name || 'Authorization'}
                onChange={(e) => setAuthConfig({ ...authConfig, header_name: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Authorization"
              />
              <p className="mt-1 text-xs text-gray-500">The header name where the API key will be sent</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Header Prefix
              </label>
              <input
                type="text"
                value={authConfig.header_prefix || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, header_prefix: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Bearer (leave empty for no prefix)"
              />
              <p className="mt-1 text-xs text-gray-500">Prefix to add before the API key (e.g., Bearer, Token). Leave empty to send API key without prefix.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Key Location
              </label>
              <select
                value={authConfig.key_location || 'header'}
                onChange={(e) => setAuthConfig({ ...authConfig, key_location: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="header">Header</option>
                <option value="query">Query Parameter</option>
                <option value="body">Body Parameter</option>
              </select>
            </div>
            {authConfig.key_location !== 'header' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Parameter Name
                </label>
                <input
                  type="text"
                  value={authConfig.key_param_name || 'api_key'}
                  onChange={(e) => setAuthConfig({ ...authConfig, key_param_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="api_key"
                />
              </div>
            )}
          </div>
        );

      case 'basic':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Realm (Optional)
              </label>
              <input
                type="text"
                value={authConfig.realm || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, realm: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Protected Area"
              />
              <p className="mt-1 text-xs text-gray-500">Authentication realm for Basic Auth</p>
            </div>
          </div>
        );

      case 'oauth2':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Token URL <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={authConfig.token_url || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, token_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="https://api.example.com/oauth/token"
                required
              />
              <p className="mt-1 text-xs text-gray-500">OAuth2 token endpoint URL</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Authorization URL <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={authConfig.authorization_url || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, authorization_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="https://api.example.com/oauth/authorize"
                required
              />
              <p className="mt-1 text-xs text-gray-500">OAuth2 authorization endpoint URL</p>
            </div>
            
            {/* Scopes Configuration */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                OAuth2 Scopes
              </label>
              <div className="space-y-2">
                {(authConfig.scopes || []).map((scope, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={scope}
                      onChange={(e) => {
                        const newScopes = [...(authConfig.scopes || [])];
                        newScopes[index] = e.target.value;
                        setAuthConfig({ ...authConfig, scopes: newScopes });
                      }}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      placeholder="Enter scope"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const newScopes = [...(authConfig.scopes || [])];
                        newScopes.splice(index, 1);
                        setAuthConfig({ ...authConfig, scopes: newScopes });
                      }}
                      className="text-red-600 hover:text-red-800"
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    setAuthConfig({ 
                      ...authConfig, 
                      scopes: [...(authConfig.scopes || []), ''] 
                    });
                  }}
                  className="text-sm text-primary hover:text-primary-dark"
                >
                  + Add Scope
                </button>
              </div>
              <p className="mt-1 text-xs text-gray-500">OAuth2 scopes required by the application</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Grant Type
                </label>
                <select
                  value={authConfig.grant_type || 'authorization_code'}
                  onChange={(e) => setAuthConfig({ ...authConfig, grant_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="authorization_code">Authorization Code</option>
                  <option value="client_credentials">Client Credentials</option>
                  <option value="refresh_token">Refresh Token</option>
                  <option value="password">Resource Owner Password</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Auth Method
                </label>
                <select
                  value={authConfig.auth_method || 'post'}
                  onChange={(e) => setAuthConfig({ ...authConfig, auth_method: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="post">POST Body</option>
                  <option value="basic">Basic Auth Header</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">How to send client credentials</p>
              </div>
            </div>

            {/* Authorization Parameters */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Authorization Parameters</h4>
              <p className="text-xs text-gray-500 mb-3">
                Additional parameters to include in the authorization URL (e.g., access_type, prompt)
              </p>
              <div className="space-y-2">
                {Object.entries(authConfig.authorization_params || {}).map(([key, value]) => (
                  <div key={key} className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={key}
                      onChange={(e) => {
                        const newParams = { ...(authConfig.authorization_params || {}) };
                        delete newParams[key];
                        newParams[e.target.value] = value;
                        setAuthConfig({ ...authConfig, authorization_params: newParams });
                      }}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      placeholder="Parameter name"
                    />
                    <input
                      type="text"
                      value={value}
                      onChange={(e) => {
                        setAuthConfig({ 
                          ...authConfig, 
                          authorization_params: {
                            ...(authConfig.authorization_params || {}),
                            [key]: e.target.value
                          }
                        });
                      }}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      placeholder="Parameter value"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const newParams = { ...(authConfig.authorization_params || {}) };
                        delete newParams[key];
                        setAuthConfig({ ...authConfig, authorization_params: newParams });
                      }}
                      className="text-red-600 hover:text-red-800"
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    setAuthConfig({ 
                      ...authConfig, 
                      authorization_params: {
                        ...(authConfig.authorization_params || {}),
                        '': ''
                      }
                    });
                  }}
                  className="text-sm text-primary hover:text-primary-dark"
                >
                  + Add Parameter
                </button>
              </div>
            </div>

            {/* Token Parameters */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Token Parameters</h4>
              <p className="text-xs text-gray-500 mb-3">
                Additional parameters to include in token requests
              </p>
              <div className="space-y-2">
                {Object.entries(authConfig.token_params || {}).map(([key, value]) => (
                  <div key={key} className="flex items-center space-x-2">
                    <input
                      type="text"
                      value={key}
                      onChange={(e) => {
                        const newParams = { ...(authConfig.token_params || {}) };
                        delete newParams[key];
                        newParams[e.target.value] = value;
                        setAuthConfig({ ...authConfig, token_params: newParams });
                      }}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      placeholder="Parameter name"
                    />
                    <input
                      type="text"
                      value={value}
                      onChange={(e) => {
                        setAuthConfig({ 
                          ...authConfig, 
                          token_params: {
                            ...(authConfig.token_params || {}),
                            [key]: e.target.value
                          }
                        });
                      }}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      placeholder="Parameter value"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const newParams = { ...(authConfig.token_params || {}) };
                        delete newParams[key];
                        setAuthConfig({ ...authConfig, token_params: newParams });
                      }}
                      className="text-red-600 hover:text-red-800"
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    setAuthConfig({ 
                      ...authConfig, 
                      token_params: {
                        ...(authConfig.token_params || {}),
                        '': ''
                      }
                    });
                  }}
                  className="text-sm text-primary hover:text-primary-dark"
                >
                  + Add Parameter
                </button>
              </div>
            </div>
            
            {/* Default OAuth Credentials Section */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Default OAuth Credentials (Global)</h4>
              <p className="text-xs text-gray-500 mb-3">
                Configure default OAuth credentials that will be used for all tenant subscriptions unless they provide their own.
              </p>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Default Client ID
                </label>
                <input
                  type="text"
                  value={authConfig.default_credentials?.client_id || ''}
                  onChange={(e) => setAuthConfig({ 
                    ...authConfig, 
                    default_credentials: {
                      ...authConfig.default_credentials,
                      client_id: e.target.value
                    }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Your OAuth App Client ID"
                />
              </div>
              <div className="mt-3">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Default Client Secret
                </label>
                <input
                  type="password"
                  value={authConfig.default_credentials?.client_secret || ''}
                  onChange={(e) => setAuthConfig({ 
                    ...authConfig, 
                    default_credentials: {
                      ...authConfig.default_credentials,
                      client_secret: e.target.value
                    }
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Your OAuth App Client Secret"
                />
              </div>
              {authConfig.default_credentials?.client_id && authConfig.default_credentials?.client_secret && (
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={testDefaultOAuthCredentials}
                    disabled={isTestingCredentials}
                    className="inline-flex items-center px-3 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
                  >
                    {isTestingCredentials ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-gray-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Testing...
                      </>
                    ) : (
                      'Test OAuth Credentials'
                    )}
                  </button>
                  <p className="mt-1 text-xs text-gray-500">
                    Test if the default credentials can acquire an access token
                  </p>
                </div>
              )}
            </div>
          </div>
        );

      case 'token_exchange':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Login URL <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={authConfig.login_url || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, login_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="https://api.example.com/auth/login"
                required
              />
              <p className="mt-1 text-xs text-gray-500">Endpoint to exchange credentials for tokens</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Refresh URL
              </label>
              <input
                type="text"
                value={authConfig.refresh_url || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, refresh_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="https://api.example.com/auth/refresh"
              />
              <p className="mt-1 text-xs text-gray-500">Endpoint to refresh tokens (optional)</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Token Field Path <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={authConfig.token_field || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, token_field: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="data.token"
                required
              />
              <p className="mt-1 text-xs text-gray-500">Path to token in response (e.g., data.token)</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Expiry Field Path
              </label>
              <input
                type="text"
                value={authConfig.expiry_field || ''}
                onChange={(e) => setAuthConfig({ ...authConfig, expiry_field: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="data.expiry"
              />
              <p className="mt-1 text-xs text-gray-500">Path to token expiry in response</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Login Method
                </label>
                <select
                  value={authConfig.login_method || 'POST'}
                  onChange={(e) => setAuthConfig({ ...authConfig, login_method: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Refresh Method
                </label>
                <select
                  value={authConfig.refresh_method || 'PUT'}
                  onChange={(e) => setAuthConfig({ ...authConfig, refresh_method: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="POST">POST</option>
                  <option value="PUT">PUT</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Token Duration (minutes)
              </label>
              <input
                type="number"
                value={authConfig.token_duration_mins || 60}
                onChange={(e) => setAuthConfig({ ...authConfig, token_duration_mins: parseInt(e.target.value) })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="60"
              />
              <p className="mt-1 text-xs text-gray-500">Token validity duration in minutes</p>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
              <p className="text-sm text-blue-800">
                <svg className="w-4 h-4 inline mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                Token Exchange authentication exchanges username/password for JWT tokens
              </p>
            </div>
          </div>
        );

      case 'custom':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Required Headers (comma-separated)
              </label>
              <input
                type="text"
                value={(authConfig.required_headers || []).join(', ')}
                onChange={(e) => setAuthConfig({ 
                  ...authConfig, 
                  required_headers: e.target.value.split(',').map(h => h.trim()).filter(h => h) 
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="X-API-Key, X-API-Secret"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Required Query Parameters (comma-separated)
              </label>
              <input
                type="text"
                value={(authConfig.required_query_params || []).join(', ')}
                onChange={(e) => setAuthConfig({ 
                  ...authConfig, 
                  required_query_params: e.target.value.split(',').map(p => p.trim()).filter(p => p) 
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="apikey, token"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Required Body Parameters (comma-separated)
              </label>
              <input
                type="text"
                value={(authConfig.required_body_params || []).join(', ')}
                onChange={(e) => setAuthConfig({ 
                  ...authConfig, 
                  required_body_params: e.target.value.split(',').map(p => p.trim()).filter(p => p) 
                })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="client_id, client_secret"
              />
            </div>
          </div>
        );

      default: {
        // Try schema-driven rendering for plugin-registered auth types
        const pluginSchema = pluginRegistry?.getAuthTypeSchema?.(authType);
        if (pluginSchema) {
          return (
            <SchemaRenderer
              schema={pluginSchema}
              value={authConfig}
              onChange={setAuthConfig}
            />
          );
        }
        return (
          <div className="text-sm text-gray-500">
            No authentication configuration required.
          </div>
        );
      }
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[9999]">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center">
              <KeyIcon className="w-5 h-5 text-gray-400 mr-2" />
              <h3 className="text-lg font-medium text-gray-900">
                Authentication Configuration
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

          <div className="px-6 py-4 space-y-6 overflow-y-auto max-h-[calc(90vh-200px)]">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Authentication Type
              </label>
              <select
                value={authType}
                onChange={(e) => setAuthType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="none">None</option>
                <option value="api_key">API Key</option>
                <option value="basic">Basic Authentication</option>
                <option value="oauth2">OAuth2</option>
                <option value="token_exchange">Token Exchange</option>
                <option value="custom">Custom</option>
              </select>
              {credentialSchema?.description && (
                <p className="mt-1 text-xs text-gray-500">{credentialSchema.description}</p>
              )}
            </div>

            {authType !== 'none' && (
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-900 mb-3">Configuration</h4>
                {renderAuthConfigFields()}
              </div>
            )}

            {credentialSchema && authType !== 'none' && (
              <div className="border-t pt-4">
                <h4 className="text-sm font-medium text-gray-900 mb-2">Required Credentials</h4>
                <p className="text-xs text-gray-500 mb-3">
                  Users will need to provide these credentials when connecting to this application:
                </p>
                <div className="bg-gray-50 rounded-md p-3">
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                    {JSON.stringify(credentialSchema.credential_schema?.properties || {}, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || (authType === 'oauth2' && !authConfig.token_url)}
              className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AuthConfigModal;