import React, { useState, useEffect } from 'react';
import { XMarkIcon, Cog6ToothIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const SubscriptionConfigModal = ({ subscription, onClose, onUpdate }) => {
  const [config, setConfig] = useState({
    base_url: '',
    ...(subscription?.subscription_config || {})
  });
  const [isLoading, setIsLoading] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Check if this is an email application
  const isEmailApp = subscription?.application?.app_name === 'SMTP/POP Email Server' || 
                     subscription?.application?.app_key === 'smtp_pop_email_server';

  useEffect(() => {
    if (subscription?.subscription_config) {
      setConfig({
        base_url: '',
        ...subscription.subscription_config
      });
    }
  }, [subscription]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}`,
        {
          subscription_config: config
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      showSuccessToast('Subscription configuration updated successfully!');
      onUpdate(response.data);
      onClose();
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update configuration');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full">
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center">
              <Cog6ToothIcon className="w-5 h-5 text-gray-400 mr-2" />
              <h3 className="text-lg font-medium text-gray-900">
                Subscription Configuration
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
            <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
              <p className="text-sm text-blue-700">
                Configure settings for your subscription to {subscription?.application?.app_name}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Base URL
              </label>
              <input
                type="url"
                value={config.base_url || ''}
                onChange={(e) => setConfig({ ...config, base_url: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                placeholder="https://api.example.com"
              />
              <p className="mt-1 text-xs text-gray-500">
                The base URL will be prepended to all API endpoints. Leave empty if endpoints already include the full URL.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Additional Configuration (JSON)
              </label>
              <textarea
                value={JSON.stringify(config, null, 2)}
                onChange={(e) => {
                  try {
                    setConfig(JSON.parse(e.target.value));
                  } catch (err) {
                    // Invalid JSON, ignore
                  }
                }}
                rows={6}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono text-sm"
                placeholder='{
  "base_url": "https://api.example.com",
  "timeout": 30,
  "retry_count": 3
}'
              />
              <p className="mt-1 text-xs text-gray-500">
                Advanced configuration in JSON format. Be careful when editing.
              </p>
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
              disabled={isLoading}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default SubscriptionConfigModal;