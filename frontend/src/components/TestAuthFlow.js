import React, { useState } from 'react';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const TestAuthFlow = ({ subscription, onClose }) => {
  const [apiKey, setApiKey] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [flowResult, setFlowResult] = useState(null);

  const handleTestFlow = async () => {
    setIsLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      
      // Step 1: Update credentials
      const updateResponse = await axios.put(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}`,
        {
          auth_credentials: { api_key: apiKey }
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      console.log('Updated subscription:', updateResponse.data);
      
      // Step 2: Test authentication
      const testResponse = await axios.post(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}/test-auth`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
      
      console.log('Test auth response:', testResponse.data);
      
      if (testResponse.data.success) {
        showSuccessToast('Authentication test successful!');
        
        // Step 3: Get debug info
        const debugResponse = await axios.get(
          `${API_BASE_URL}/api/v1/debug/subscription/${subscription.subscription_id}/auth-info`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        
        setFlowResult({
          updateResult: updateResponse.data,
          testResult: testResponse.data,
          debugInfo: debugResponse.data
        });
      } else {
        showErrorToast('Authentication test failed: ' + testResponse.data.error);
        setFlowResult({
          updateResult: updateResponse.data,
          testResult: testResponse.data,
          error: testResponse.data.error
        });
      }
    } catch (error) {
      console.error('Error in auth flow:', error);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to test authentication');
      setFlowResult({
        error: (error.response?.data?.message || error.response?.data?.detail) || error.message
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">
            Test Complete Authentication Flow
          </h3>
        </div>
        
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-160px)]">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                type="text"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter your API key (e.g., mysecrettoken123)"
                className="w-full px-3 py-2 border border-gray-300 rounded-md"
              />
            </div>

            <button
              onClick={handleTestFlow}
              disabled={!apiKey || isLoading}
              className="w-full px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {isLoading ? 'Testing...' : 'Test Authentication Flow'}
            </button>

            {flowResult && (
              <div className="space-y-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="text-sm font-medium text-gray-900 mb-2">Flow Results:</h4>
                  
                  {flowResult.testResult && (
                    <div className="mb-4">
                      <h5 className="text-sm font-medium text-gray-700">Test Result:</h5>
                      <pre className="text-xs bg-white p-2 rounded border overflow-auto">
                        {JSON.stringify(flowResult.testResult, null, 2)}
                      </pre>
                    </div>
                  )}
                  
                  {flowResult.debugInfo && (
                    <div className="mb-4">
                      <h5 className="text-sm font-medium text-gray-700">Debug Info:</h5>
                      <pre className="text-xs bg-white p-2 rounded border overflow-auto">
                        {JSON.stringify(flowResult.debugInfo, null, 2)}
                      </pre>
                    </div>
                  )}
                  
                  {flowResult.error && (
                    <div className="mb-4 bg-red-50 p-2 rounded">
                      <h5 className="text-sm font-medium text-red-700">Error:</h5>
                      <p className="text-sm text-red-600">{flowResult.error}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-200">
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

export default TestAuthFlow;