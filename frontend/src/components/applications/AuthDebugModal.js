import React, { useState, useEffect } from 'react';
import { XMarkIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const AuthDebugModal = ({ subscription, application, onClose }) => {
  const [authInfo, setAuthInfo] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchAuthInfo();
  }, []);

  const fetchAuthInfo = async () => {
    try {
      const token = localStorage.getItem('access_token');
      
      // Get subscription details
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/applications/subscriptions/`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      const sub = response.data.find(s => s.subscription_id === subscription.subscription_id);
      setAuthInfo(sub);
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to fetch auth info:', error);
      setIsLoading(false);
    }
  };

  const testAuthentication = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}/test-auth`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.data.success) {
        showSuccessToast('Authentication test successful!');
      } else {
        showErrorToast(response.data.error || 'Authentication test failed');
      }
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to test authentication');
    }
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
        <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center">
            <ShieldCheckIcon className="w-5 h-5 text-gray-400 mr-2" />
            <h3 className="text-lg font-medium text-gray-900">
              Authentication Debug Info
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

        <div className="px-6 py-4 space-y-4 overflow-y-auto max-h-[calc(90vh-160px)]">
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Application Settings</h4>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-600">Auth Type:</dt>
              <dd className="font-mono">{application.auth_type}</dd>
              
              <dt className="text-gray-600">Auth Config:</dt>
              <dd className="font-mono text-xs col-span-2 mt-1">
                <pre className="bg-white p-2 rounded border overflow-x-auto">
                  {JSON.stringify(application.auth_config, null, 2)}
                </pre>
              </dd>
            </dl>
          </div>

          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="text-sm font-medium text-gray-900 mb-2">Subscription Settings</h4>
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-gray-600">Has Credentials:</dt>
              <dd className="font-mono">{authInfo?.auth_credentials ? 'Yes' : 'No'}</dd>
              
              <dt className="text-gray-600">Subscription Config:</dt>
              <dd className="font-mono text-xs col-span-2 mt-1">
                <pre className="bg-white p-2 rounded border overflow-x-auto">
                  {JSON.stringify(authInfo?.subscription_config || {}, null, 2)}
                </pre>
              </dd>
              
              {authInfo?.auth_credentials && (
                <>
                  <dt className="text-gray-600">Credential Keys:</dt>
                  <dd className="font-mono text-xs col-span-2 mt-1">
                    {Object.keys(authInfo.auth_credentials).join(', ')}
                  </dd>
                </>
              )}
            </dl>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
            <h4 className="text-sm font-medium text-blue-900 mb-2">Expected Authentication Format</h4>
            {application.auth_type === 'api_key' && (
              <div className="text-sm text-blue-700">
                <p>Header: {application.auth_config?.header_name || 'Authorization'}</p>
                <p>Format: {application.auth_config?.header_prefix ? 
                  `${application.auth_config.header_prefix} YOUR_API_KEY` : 
                  'YOUR_API_KEY'}</p>
              </div>
            )}
            {application.auth_type === 'basic' && (
              <div className="text-sm text-blue-700">
                <p>Header: Authorization</p>
                <p>Format: Basic base64(username:password)</p>
              </div>
            )}
            {application.auth_type === 'oauth2' && (
              <div className="text-sm text-blue-700">
                <p>Header: Authorization</p>
                <p>Format: Bearer YOUR_ACCESS_TOKEN</p>
                <p>Token URL: {application.auth_config?.token_url}</p>
              </div>
            )}
          </div>

          {!authInfo?.auth_credentials && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
              <p className="text-sm text-yellow-800">
                No authentication credentials found. Please disconnect and reconnect the application to provide credentials.
              </p>
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
          <button
            onClick={testAuthentication}
            disabled={!authInfo?.auth_credentials}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            Test Authentication
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default AuthDebugModal;