import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  MagnifyingGlassIcon,
  CheckCircleIcon,
  PlusCircleIcon,
  CubeIcon,
  ArrowPathIcon,
  FunnelIcon,
  LinkIcon,
  ArrowUpCircleIcon,
} from '@heroicons/react/24/outline';
import { showSuccessToast, showErrorToast } from '../../../utils/customToast';
import ConnectionModal from '../../applications/ConnectionModal';
import { useOnboarding } from '../../../contexts/OnboardingContext';

const ApplicationSetupStep = ({ stepData, onComplete }) => {
  const { initialAppFilter, clearInitialAppFilter } = useOnboarding();
  const [applications, setApplications] = useState([]);
  const [filteredApps, setFilteredApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState(initialAppFilter || 'all');
  const [installingApp, setInstallingApp] = useState(null);
  const [updatingApp, setUpdatingApp] = useState(null);
  const [error, setError] = useState(null);
  const [showConnectionModal, setShowConnectionModal] = useState(false);
  const [selectedAppForConnection, setSelectedAppForConnection] = useState(null);

  // Clear the initial filter after it has been applied
  useEffect(() => {
    if (initialAppFilter) {
      setSelectedStatus(initialAppFilter);
      // Clear after a short delay to ensure state is set
      const timer = setTimeout(() => {
        clearInitialAppFilter();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [initialAppFilter, clearInitialAppFilter]);

  const isCompleted = stepData?.completed;
  const subscribedCount = stepData?.details?.subscribed_count || 0;

  // Get app connection status
  const getAppStatus = (app) => {
    if (app.subscription_count > 0) return 'subscribed';
    if (app.status === 'installed') return 'installed';
    if (app.status === 'update_available') return 'update_available';
    return 'not_installed';
  };

  // Fetch applications on mount
  useEffect(() => {
    fetchApplications();
  }, []);

  // Filter applications when search, category, or status changes
  useEffect(() => {
    let filtered = applications;

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (app) =>
          app.name?.toLowerCase().includes(query) ||
          app.description?.toLowerCase().includes(query) ||
          app.category?.toLowerCase().includes(query)
      );
    }

    if (selectedCategory !== 'all') {
      filtered = filtered.filter((app) => app.category === selectedCategory);
    }

    if (selectedStatus !== 'all') {
      filtered = filtered.filter((app) => {
        const status = getAppStatus(app);
        // When filtering by 'installed', also include 'update_available' apps (they're installed too)
        if (selectedStatus === 'installed') {
          return status === 'installed' || status === 'update_available';
        }
        return status === selectedStatus;
      });
    }

    setFilteredApps(filtered);
  }, [applications, searchQuery, selectedCategory, selectedStatus]);

  const fetchApplications = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get('/api/v1/seed-applications/');
      const apps = response.data.applications || [];
      setApplications(apps);
      setFilteredApps(apps);
    } catch (err) {
      console.error('Error fetching applications:', err);
      setError('Failed to load applications');
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async (appKey) => {
    setInstallingApp(appKey);
    try {
      await axios.post('/api/v1/seed-applications/install', {
        application_key: appKey,
      });
      showSuccessToast('Application installed successfully');
      // Refresh applications list
      await fetchApplications();
      // Refresh onboarding status
      if (onComplete) {
        await onComplete();
      }
    } catch (err) {
      console.error('Error installing application:', err);
      console.error('Error response:', err.response?.data);
      console.error('Error response type:', typeof err.response?.data);

      // Extract the most specific error message available
      let errorMessage = 'Failed to install application';
      let responseData = err.response?.data;

      // Handle case where response is a string (might be stringified JSON)
      if (typeof responseData === 'string') {
        try {
          responseData = JSON.parse(responseData);
        } catch {
          // Not JSON, use the string as-is but clean it up
          errorMessage = responseData
            .replace(/\. Use force_reinstall=true to reinstall\.?/gi, '')
            .replace(/Use force_reinstall=true to reinstall\.?/gi, '');
        }
      }

      // Extract message from parsed object
      if (responseData && typeof responseData === 'object') {
        // Handle validation errors with errors array
        if (responseData.errors && Array.isArray(responseData.errors) && responseData.errors.length > 0) {
          // Extract the first validation error message
          const firstError = responseData.errors[0];
          errorMessage = firstError.message || responseData.message || 'Validation failed';
        } else if (responseData.message) {
          errorMessage = responseData.message
            .replace(/\. Use force_reinstall=true to reinstall\.?/gi, '')
            .replace(/Use force_reinstall=true to reinstall\.?/gi, '');
        } else if (responseData.detail) {
          errorMessage = typeof responseData.detail === 'string'
            ? responseData.detail
            : JSON.stringify(responseData.detail);
        } else if (responseData.error) {
          errorMessage = responseData.error;
        }
      }

      // If app is already installed (409 Conflict), refresh list to show correct state
      if (err.response?.status === 409) {
        await fetchApplications();
        showErrorToast(errorMessage || 'Application is already installed');
      } else {
        showErrorToast(errorMessage);
      }
    } finally {
      setInstallingApp(null);
    }
  };

  const handleUpdate = async (appKey) => {
    setUpdatingApp(appKey);
    try {
      const response = await axios.post(`/api/v1/seed-applications/${appKey}/update`);
      const result = response.data;
      showSuccessToast(`Updated to v${result.new_version}`);
      // Refresh applications list
      await fetchApplications();
    } catch (err) {
      console.error('Error updating application:', err);
      let errorMessage = 'Failed to update application';
      if (err.response?.data?.detail) {
        errorMessage = typeof err.response.data.detail === 'string'
          ? err.response.data.detail
          : err.response.data.detail.message || JSON.stringify(err.response.data.detail);
      } else if (err.response?.data?.message) {
        errorMessage = err.response.data.message;
      }
      showErrorToast(errorMessage);
    } finally {
      setUpdatingApp(null);
    }
  };

  const handleConnect = (app) => {
    // Convert seed app data to format expected by ConnectionModal
    const applicationForModal = {
      app_id: app.app_id,
      app_name: app.name,
      description: app.description,
      auth_type: app.auth_type,
      category: app.category,
      icon_url: app.icon_url,
    };
    setSelectedAppForConnection(applicationForModal);
    setShowConnectionModal(true);
  };

  const handleConnectionSuccess = async () => {
    setShowConnectionModal(false);
    setSelectedAppForConnection(null);
    showSuccessToast('Application connected successfully');
    // Refresh applications list
    await fetchApplications();
    // Refresh onboarding status
    if (onComplete) {
      await onComplete();
    }
  };

  // Get unique categories from applications
  const categories = ['all', ...new Set(applications.map((app) => app.category).filter(Boolean))];

  // Status filter options
  const statusOptions = [
    { value: 'all', label: 'All Status' },
    { value: 'not_installed', label: 'Ready to Install' },
    { value: 'installed', label: 'Ready to Connect' },
    { value: 'update_available', label: 'Update Available' },
    { value: 'subscribed', label: 'Connected' },
  ];

  const popularApps = ['slack', 'gmail', 'google_sheets', 'github', 'stripe', 'shopify'];

  return (
    <div className="space-y-6">
      {/* Status banner */}
      {isCompleted ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
          <CheckCircleIcon className="h-6 w-6 text-green-600" />
          <div>
            <h3 className="text-sm font-medium text-green-800">Applications Connected</h3>
            <p className="text-sm text-green-700">
              You have {subscribedCount} application{subscribedCount !== 1 ? 's' : ''} connected.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <CubeIcon className="h-6 w-6 text-purple-600 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-purple-800">Why Connect Applications?</h3>
              <p className="text-sm text-purple-700 mt-1">
                Applications are the building blocks of your flows. Install apps to connect with
                services like Slack, Gmail, Stripe, and 50+ more.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Search and filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search applications..."
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="relative">
          <FunnelIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="pl-10 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 appearance-none bg-white"
          >
            {categories.map((category) => (
              <option key={category} value={category}>
                {category === 'all' ? 'All Categories' : category}
              </option>
            ))}
          </select>
        </div>
        <div className="relative">
          <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="pl-10 pr-8 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 appearance-none bg-white"
          >
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={fetchApplications}
          disabled={loading}
          className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center gap-2"
        >
          <ArrowPathIcon className={`h-5 w-5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <ArrowPathIcon className="h-8 w-8 text-blue-600 animate-spin" />
        </div>
      )}

      {/* Applications grid */}
      {!loading && filteredApps.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 max-h-[300px] overflow-y-auto">
          {filteredApps.map((app) => {
            const status = getAppStatus(app);
            const isInstalling = installingApp === app.key;
            const isPopular = popularApps.includes(app.key);

            return (
              <div
                key={app.key}
                className={`
                  relative border rounded-lg p-4 transition-all
                  ${status === 'subscribed' ? 'border-green-300 bg-green-50' :
                    status === 'update_available' ? 'border-amber-300 bg-amber-50' :
                    'border-gray-200 bg-white hover:shadow-sm'}
                `}
              >
                {/* Popular badge */}
                {isPopular && status !== 'subscribed' && (
                  <span className="absolute -top-2 -right-2 px-2 py-0.5 bg-amber-500 text-white text-xs font-medium rounded-full">
                    Popular
                  </span>
                )}

                {/* App icon */}
                <div className="w-12 h-12 rounded-lg bg-gray-100 flex items-center justify-center mb-3 overflow-hidden">
                  {app.icon_url ? (
                    <img
                      src={app.icon_url}
                      alt={app.name}
                      className="w-10 h-10 object-contain"
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.parentElement.innerHTML = `<span class="text-xl">${app.name?.charAt(0) || '?'}</span>`;
                      }}
                    />
                  ) : (
                    <span className="text-xl font-bold text-gray-400">
                      {app.name?.charAt(0) || '?'}
                    </span>
                  )}
                </div>

                {/* App info */}
                <h4 className="text-sm font-medium text-gray-900 truncate">{app.name}</h4>
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                  {app.description || 'No description available'}
                </p>
                <p className="text-xs text-gray-400 mt-1">{app.category}</p>

                {/* Action button */}
                <div className="mt-3">
                  {status === 'subscribed' ? (
                    <span className="inline-flex items-center gap-1 text-xs text-green-700 font-medium">
                      <CheckCircleIcon className="h-4 w-4" />
                      Connected
                    </span>
                  ) : status === 'installed' ? (
                    <button
                      onClick={() => handleConnect(app)}
                      className="inline-flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-md transition-colors bg-green-100 text-green-700 hover:bg-green-200"
                    >
                      <LinkIcon className="h-4 w-4" />
                      Connect
                    </button>
                  ) : status === 'update_available' ? (
                    <div className="flex flex-col gap-1.5">
                      <span className="text-[10px] text-amber-600">
                        v{app.installed_version} → v{app.version}
                      </span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleUpdate(app.key)}
                          disabled={updatingApp === app.key}
                          className={`inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md transition-colors ${
                            updatingApp === app.key
                              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                              : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                          }`}
                          title="Update to latest version"
                        >
                          {updatingApp === app.key ? (
                            <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          ) : (
                            <ArrowUpCircleIcon className="h-4 w-4" />
                          )}
                          {updatingApp === app.key ? 'Updating...' : 'Update'}
                        </button>
                        <button
                          onClick={() => handleConnect(app)}
                          className="inline-flex items-center gap-1 text-xs font-medium px-2.5 py-1.5 rounded-md transition-colors bg-green-100 text-green-700 hover:bg-green-200"
                        >
                          <LinkIcon className="h-4 w-4" />
                          Connect
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleInstall(app.key)}
                      disabled={isInstalling}
                      className={`
                        inline-flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-md transition-colors
                        ${isInstalling
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                        }
                      `}
                    >
                      {isInstalling ? (
                        <>
                          <ArrowPathIcon className="h-4 w-4 animate-spin" />
                          Installing...
                        </>
                      ) : (
                        <>
                          <PlusCircleIcon className="h-4 w-4" />
                          Install
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {!loading && filteredApps.length === 0 && (
        <div className="text-center py-12">
          <CubeIcon className="h-12 w-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No applications found matching your search.</p>
        </div>
      )}

      {/* Summary */}
      <div className="pt-4 border-t border-gray-200">
        <p className="text-sm text-gray-600">
          <span className="font-medium">{applications.filter((a) => getAppStatus(a) !== 'not_installed').length}</span> of{' '}
          <span className="font-medium">{applications.length}</span> applications installed
        </p>
        <p className="text-xs text-gray-500 mt-1">
          You can install more applications later from the Applications page.
        </p>
      </div>

      {/* Connection Modal */}
      {showConnectionModal && selectedAppForConnection && (
        <ConnectionModal
          application={selectedAppForConnection}
          subscription={null}
          onClose={() => {
            setShowConnectionModal(false);
            setSelectedAppForConnection(null);
          }}
          onSuccess={handleConnectionSuccess}
        />
      )}
    </div>
  );
};

export default ApplicationSetupStep;
