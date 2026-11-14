import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../utils/customToast';
import { ArrowLeftIcon, CloudArrowUpIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import { getFullErrorMessage } from '../utils/errorHandler';
import { useAuth } from '../contexts/AuthContext';

const ApplicationForm = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.role === 'INSTANCE_ADMIN';
  const [formData, setFormData] = useState({
    app_name: '',
    app_scope: 'tenant',
    app_type: 'api',
    description: '',
    icon_url: '',
    category: '',
    base_url: '',
    auth_type: 'none',
    auth_config: {},
    webhook_config: {},
    status: 'active',
    version: '1.0.0'
  });

  const createApplicationMutation = useMutation({
    mutationFn: (data) => axios.post('/api/v1/applications/', data),
    onSuccess: () => {
      showSuccessToast('Application created successfully!');
      navigate('/applications');
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to create application');
      showErrorToast(errorMessage);
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    createApplicationMutation.mutate(formData);
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleAuthConfigChange = (key, value) => {
    setFormData(prev => ({
      ...prev,
      auth_config: {
        ...prev.auth_config,
        [key]: value
      }
    }));
  };

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6">
        <button
          onClick={() => navigate('/applications')}
          className="flex items-center text-gray-600 hover:text-gray-900"
        >
          <ArrowLeftIcon className="w-4 h-4 mr-2" />
          Back to Applications
        </button>
      </div>

      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-2xl font-bold mb-6">Create New Application</h2>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Application Name *
              </label>
              <input
                type="text"
                name="app_name"
                value={formData.app_name}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="e.g., My Custom App"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Application Scope *
              </label>
              <select
                name="app_scope"
                value={formData.app_scope}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
              >
                <option value="tenant">Tenant</option>
                <option value="user">User</option>
                <option value="global" disabled={!isAdmin}>
                  Global{isAdmin ? ' (visible to all tenants)' : ' (Admin only)'}
                </option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Application Type *
              </label>
              <select
                name="app_type"
                value={formData.app_type}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
              >
                <option value="api">API</option>
                <option value="database">Database</option>
                <option value="email">Email</option>
                <option value="file_system">File System</option>
                <option value="memory">Memory</option>
                <option value="flow">Flow</option>
                <option value="ai_agent">AI Agent</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Category
              </label>
              <input
                type="text"
                name="category"
                value={formData.category}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="e.g., Communication, Productivity"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Version
              </label>
              <input
                type="text"
                name="version"
                value={formData.version}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="1.0.0"
              />
            </div>

            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="Describe your application..."
              />
            </div>

            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Base URL
              </label>
              <input
                type="url"
                name="base_url"
                value={formData.base_url}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="https://api.example.com"
              />
              <p className="mt-1 text-xs text-gray-500">
                The base URL for the application's API (optional)
              </p>
            </div>

            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Icon URL
              </label>
              <input
                type="url"
                name="icon_url"
                value={formData.icon_url}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                placeholder="https://example.com/icon.png"
              />
            </div>

            <div className="col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Authentication Type *
              </label>
              <select
                name="auth_type"
                value={formData.auth_type}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
              >
                <option value="none">None</option>
                <option value="api_key">API Key</option>
                <option value="oauth2">OAuth2</option>
                <option value="basic">Basic Auth</option>
                <option value="token_exchange">Token Exchange</option>
                <option value="custom">Custom</option>
              </select>
            </div>

            {formData.auth_type === 'api_key' && (
              <div className="col-span-2 space-y-4 p-4 bg-gray-50 rounded-md">
                <h3 className="font-medium text-gray-700">API Key Configuration</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Header Name
                    </label>
                    <input
                      type="text"
                      value={formData.auth_config.header_name || 'Authorization'}
                      onChange={(e) => handleAuthConfigChange('header_name', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                      placeholder="e.g., Authorization"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Header Prefix
                    </label>
                    <input
                      type="text"
                      value={formData.auth_config.header_prefix || ''}
                      onChange={(e) => handleAuthConfigChange('header_prefix', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                      placeholder="e.g., Bearer (leave empty for no prefix)"
                    />
                    <p className="mt-1 text-xs text-gray-500">Leave empty if API key should be sent without a prefix</p>
                  </div>
                </div>
              </div>
            )}

            {formData.auth_type === 'oauth2' && (
              <div className="col-span-2 space-y-4 p-4 bg-gray-50 rounded-md">
                <h3 className="font-medium text-gray-700">OAuth2 Configuration</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Token URL *
                    </label>
                    <input
                      type="url"
                      value={formData.auth_config.token_url || ''}
                      onChange={(e) => handleAuthConfigChange('token_url', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                      placeholder="https://example.com/oauth/token"
                      required={formData.auth_type === 'oauth2'}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Authorization URL
                    </label>
                    <input
                      type="url"
                      value={formData.auth_config.authorization_url || ''}
                      onChange={(e) => handleAuthConfigChange('authorization_url', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                      placeholder="https://example.com/oauth/authorize"
                    />
                  </div>
                </div>
              </div>
            )}

            {formData.auth_type === 'token_exchange' && (
              <div className="col-span-2 space-y-4 p-4 bg-gray-50 rounded-md">
                <h3 className="font-medium text-gray-700">Token Exchange Configuration</h3>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Login URL *
                      </label>
                      <input
                        type="url"
                        value={formData.auth_config.login_url || ''}
                        onChange={(e) => handleAuthConfigChange('login_url', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                        placeholder="https://api.example.com/auth/login"
                        required={formData.auth_type === 'token_exchange'}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Refresh URL
                      </label>
                      <input
                        type="url"
                        value={formData.auth_config.refresh_url || ''}
                        onChange={(e) => handleAuthConfigChange('refresh_url', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                        placeholder="https://api.example.com/auth/refresh"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Token Field Path *
                      </label>
                      <input
                        type="text"
                        value={formData.auth_config.token_field || ''}
                        onChange={(e) => handleAuthConfigChange('token_field', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                        placeholder="data.token"
                        required={formData.auth_type === 'token_exchange'}
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Path to token in response (e.g., data.token)
                      </p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Expiry Field Path
                      </label>
                      <input
                        type="text"
                        value={formData.auth_config.expiry_field || ''}
                        onChange={(e) => handleAuthConfigChange('expiry_field', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                        placeholder="data.expiry"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Path to expiry in response (optional)
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Login Method
                      </label>
                      <select
                        value={formData.auth_config.login_method || 'POST'}
                        onChange={(e) => handleAuthConfigChange('login_method', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                      >
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Token Duration (mins)
                      </label>
                      <input
                        type="number"
                        value={formData.auth_config.token_duration_mins || 60}
                        onChange={(e) => handleAuthConfigChange('token_duration_mins', parseInt(e.target.value))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                        placeholder="60"
                      />
                    </div>
                  </div>
                  <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                    <p className="text-sm text-blue-800">
                      <InformationCircleIcon className="h-4 w-4 inline mr-1" />
                      Token Exchange authentication allows users to exchange username/password for JWT tokens.
                      The system will automatically refresh tokens before they expire.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {formData.category === 'Database' && (
              <div className="col-span-2 space-y-4 p-4 bg-gray-50 rounded-md">
                <h3 className="font-medium text-gray-700">Database Configuration</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Database Type *
                    </label>
                    <select
                      value={formData.auth_config.database_type || 'postgresql'}
                      onChange={(e) => handleAuthConfigChange('database_type', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                    >
                      <option value="postgresql">PostgreSQL</option>
                      <option value="mysql">MySQL</option>
                      <option value="oracle">Oracle</option>
                      <option value="sqlserver">SQL Server</option>
                      <option value="sqlite">SQLite</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Connection Pool Size
                    </label>
                    <input
                      type="number"
                      value={formData.auth_config.connection_pool_size || 10}
                      onChange={(e) => handleAuthConfigChange('connection_pool_size', parseInt(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                      min="1"
                      max="50"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Connection Timeout (seconds)
                    </label>
                    <input
                      type="number"
                      value={formData.auth_config.connection_timeout || 30}
                      onChange={(e) => handleAuthConfigChange('connection_timeout', parseInt(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                      min="5"
                      max="300"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      SSL Mode
                    </label>
                    <select
                      value={formData.auth_config.ssl_mode || ''}
                      onChange={(e) => handleAuthConfigChange('ssl_mode', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                    >
                      <option value="">None</option>
                      <option value="require">Require</option>
                      <option value="prefer">Prefer</option>
                      <option value="disable">Disable</option>
                    </select>
                  </div>
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                  <p className="text-sm text-blue-800">
                    <InformationCircleIcon className="h-4 w-4 inline mr-1" />
                    Database connection URL format: {formData.auth_config.database_type || 'postgresql'}://user:password@host:port/database
                  </p>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-end space-x-4 pt-6 border-t">
            <button
              type="button"
              onClick={() => navigate('/applications')}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={createApplicationMutation.isPending}
              className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg disabled:opacity-50 flex items-center"
            >
              <CloudArrowUpIcon className="w-4 h-4 mr-2" />
              {createApplicationMutation.isPending ? 'Creating...' : 'Create Application'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ApplicationForm;