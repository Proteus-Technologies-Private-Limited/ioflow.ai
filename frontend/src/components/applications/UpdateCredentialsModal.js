import React, { useState, useEffect } from 'react';
import { XMarkIcon, KeyIcon, EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const UpdateCredentialsModal = ({ application, subscription, onClose, onUpdate }) => {
  const [credentials, setCredentials] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [showSecrets, setShowSecrets] = useState({});

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}`,
        {
          auth_credentials: credentials
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      showSuccessToast('Credentials updated successfully!');
      onUpdate(response.data);
      onClose();
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update credentials');
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
              <p className="mt-1 text-xs text-gray-500">
                Your API key will be sent as: Authorization: Bearer YOUR_KEY
              </p>
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

      case 'token_exchange':
        return (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email <span className="text-red-500">*</span>
              </label>
              <input
                type="email"
                value={credentials.username || ''}
                onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="Enter your email address"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Handle Type <span className="text-red-500">*</span>
              </label>
              <select
                value={credentials.handle_type || 'email'}
                onChange={(e) => setCredentials({ ...credentials, handle_type: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                required
              >
                <option value="email">Email</option>
                <option value="mobile">Mobile</option>
              </select>
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
    
    switch (authType) {
      case 'api_key':
        return !!credentials.api_key;
      case 'basic':
        return !!credentials.username && !!credentials.password;
      case 'token_exchange':
        return !!credentials.username && !!credentials.password && !!credentials.handle_type;
      default:
        return true;
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full">
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center">
              <KeyIcon className="w-5 h-5 text-gray-400 mr-2" />
              <h3 className="text-lg font-medium text-gray-900">
                Update Credentials for {application?.app_name}
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

          <div className="px-6 py-4 space-y-4">
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
              <p className="text-sm text-yellow-800">
                Your subscription is missing credentials. Please provide them to enable authentication.
              </p>
            </div>

            <div>
              <h4 className="text-sm font-medium text-gray-900 mb-3">Authentication Credentials</h4>
              {renderCredentialFields()}
            </div>
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
              disabled={!isFormValid() || isLoading}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {isLoading ? 'Updating...' : 'Update Credentials'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UpdateCredentialsModal;