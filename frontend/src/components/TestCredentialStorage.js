import React, { useState } from 'react';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const TestCredentialStorage = ({ subscription, application, onClose }) => {
  const [apiKey, setApiKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [response, setResponse] = useState(null);

  const testUpdate = async () => {
    setIsLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      
      console.log('Updating subscription with:', {
        subscription_id: subscription.subscription_id,
        auth_credentials: { api_key: apiKey }
      });

      const updateResponse = await axios.put(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}`,
        {
          auth_credentials: { api_key: apiKey }
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      console.log('Update response:', updateResponse.data);

      // Now test the credentials
      const testResponse = await axios.post(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}/test-auth`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      console.log('Test response:', testResponse.data);
      setResponse(testResponse.data);

      if (testResponse.data.success) {
        showSuccessToast('Credentials saved and validated successfully!');
      } else {
        showErrorToast('Credentials saved but validation failed: ' + testResponse.data.error);
      }
    } catch (error) {
      console.error('Error:', error);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update credentials');
      setResponse(error.response?.data);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          Test Credential Storage
        </h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Key
            </label>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
            />
          </div>

          <button
            onClick={testUpdate}
            disabled={!apiKey || isLoading}
            className="w-full px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
          >
            {isLoading ? 'Testing...' : 'Update and Test'}
          </button>

          {response && (
            <div className="mt-4 p-4 bg-gray-50 rounded-md">
              <h4 className="text-sm font-medium text-gray-900 mb-2">Response:</h4>
              <pre className="text-xs overflow-auto">
                {JSON.stringify(response, null, 2)}
              </pre>
            </div>
          )}

          <button
            onClick={onClose}
            className="w-full px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TestCredentialStorage;