import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { API_BASE_URL } from '../../config';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';

const GoogleOAuthSettings = () => {
  const [loading, setLoading] = useState(false);
  const [configLoading, setConfigLoading] = useState(true);
  const [config, setConfig] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const { register, handleSubmit, setValue, formState: { errors } } = useForm();

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchRedirectUri = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/status`);
      if (response.ok) {
        const data = await response.json();
        if (data.redirect_uri) {
          setConfig(prev => ({ ...prev, redirect_uri: data.redirect_uri }));
        }
      }
    } catch (error) {
      console.error('Failed to fetch redirect URI:', error);
    }
  };

  const fetchConfig = async () => {
    setConfigLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/config`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
        if (data.is_configured) {
          setValue('client_id', data.client_id);
          setValue('project_id', data.project_id);
          setShowForm(false);
        } else {
          // If not configured, show the form by default
          setShowForm(true);
        }
      } else {
        console.error('Failed to fetch config, status:', response.status);
        // Set default config if fetch fails - redirect_uri will come from backend
        setConfig({ is_configured: false, redirect_uri: '' });
        setShowForm(true);
        // Try to get the redirect URI from the status endpoint which doesn't require auth
        fetchRedirectUri();
      }
    } catch (error) {
      console.error('Failed to fetch Google OAuth config:', error);
      // Set default config if fetch fails - redirect_uri will come from backend
      setConfig({ is_configured: false, redirect_uri: '' });
      setShowForm(true);
      // Try to get the redirect URI from the status endpoint which doesn't require auth
      fetchRedirectUri();
    } finally {
      setConfigLoading(false);
    }
  };

  const onSubmit = async (data) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          client_id: data.client_id,
          client_secret: data.client_secret,
          project_id: data.project_id
        })
      });

      if (response.ok) {
        const result = await response.json();
        showSuccessToast('Google OAuth configuration saved successfully!');
        fetchConfig();
        setShowForm(false);
      } else {
        const error = await response.json();
        showErrorToast(error.detail || 'Failed to save configuration');
      }
    } catch (error) {
      showErrorToast('Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to delete the Google OAuth configuration?')) {
      return;
    }

    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/config`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        showSuccessToast('Google OAuth configuration deleted successfully!');
        setConfig({ ...config, is_configured: false, client_id: '', project_id: null });
        setShowForm(false);
      } else {
        showErrorToast('Failed to delete configuration');
      }
    } catch (error) {
      showErrorToast('Failed to delete configuration');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-lg font-medium text-gray-900">Google OAuth Configuration</h2>
        {config && !showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700"
          >
            {config.is_configured ? 'Edit Configuration' : 'Configure OAuth'}
          </button>
        )}
      </div>

      {configLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : config && (
        <>
          {config.is_configured && !showForm ? (
            <div className="space-y-4">
              <div className="bg-green-50 border border-green-200 rounded-md p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-green-800">
                      Google OAuth is configured
                    </h3>
                    <div className="mt-2 text-sm text-green-700">
                      <p>Users can now sign in and sign up using their Google accounts.</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Client ID</label>
                  <p className="mt-1 text-sm text-gray-900 font-mono bg-gray-50 p-2 rounded">
                    {config.client_id}
                  </p>
                </div>
                {config.project_id && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Project ID</label>
                    <p className="mt-1 text-sm text-gray-900 font-mono bg-gray-50 p-2 rounded">
                      {config.project_id}
                    </p>
                  </div>
                )}
                <div>
                  <label className="block text-sm font-medium text-gray-700">Redirect URI</label>
                  <p className="mt-1 text-sm text-gray-900 font-mono bg-gray-50 p-2 rounded">
                    {config.redirect_uri}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">
                    Add this redirect URI to your Google OAuth 2.0 client configuration
                  </p>
                </div>
              </div>

              <div className="mt-6 flex gap-3">
                <button
                  onClick={() => setShowForm(true)}
                  className="px-4 py-2 text-sm font-medium text-primary-600 bg-white border border-primary-600 rounded-md hover:bg-primary-50"
                >
                  Update Configuration
                </button>
                <button
                  onClick={handleDelete}
                  className="px-4 py-2 text-sm font-medium text-red-600 bg-white border border-red-600 rounded-md hover:bg-red-50"
                >
                  Delete Configuration
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              {!config.is_configured && (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mb-4">
                  <p className="text-sm text-blue-800">
                    To enable Google OAuth, you need to create OAuth 2.0 credentials in the Google Cloud Console.
                  </p>
                  <ol className="mt-2 text-sm text-blue-700 list-decimal list-inside space-y-1">
                    <li>Go to the <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="underline">Google Cloud Console</a></li>
                    <li>Create a new OAuth 2.0 Client ID</li>
                    <li>Add the redirect URI shown below</li>
                    <li>Copy the Client ID and Client Secret</li>
                  </ol>
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Redirect URI (Add this to Google OAuth)
                </label>
                <p className="mt-1 text-sm text-gray-900 font-mono bg-gray-50 p-2 rounded">
                  {config?.redirect_uri || 'Loading...'}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Client ID <span className="text-red-500">*</span>
                </label>
                <input
                  {...register('client_id', { required: 'Client ID is required' })}
                  type="text"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                  placeholder="Your Google OAuth Client ID"
                />
                {errors.client_id && (
                  <p className="mt-1 text-xs text-red-600">{errors.client_id.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Client Secret <span className="text-red-500">*</span>
                </label>
                <input
                  {...register('client_secret', { required: 'Client Secret is required' })}
                  type="password"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                  placeholder="Your Google OAuth Client Secret"
                />
                {errors.client_secret && (
                  <p className="mt-1 text-xs text-red-600">{errors.client_secret.message}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Project ID (Optional)
                </label>
                <input
                  {...register('project_id')}
                  type="text"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                  placeholder="Your Google Cloud Project ID"
                />
              </div>

              <div className="flex gap-3">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 text-sm font-medium text-white bg-primary-600 rounded-md hover:bg-primary-700 disabled:opacity-50"
                >
                  {loading ? 'Saving...' : 'Save Configuration'}
                </button>
                {(config.is_configured || showForm) && (
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          )}
        </>
      )}
    </div>
  );
};

export default GoogleOAuthSettings;