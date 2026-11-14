import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  EyeIcon,
  CurrencyDollarIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  TrashIcon,
  GlobeAltIcon,
  LockClosedIcon,
  ShieldCheckIcon,
  CheckCircleIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';
import { microSaasService } from '../services/microSaasService';
import { showErrorToast, showSuccessToast, showInfoToast } from '../utils/customToast';

const MicroSaasAppsPage = () => {
  const navigate = useNavigate();
  const [apps, setApps] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [visibilityFilter, setVisibilityFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [includeInactive, setIncludeInactive] = useState(false);

  useEffect(() => {
    loadApps();
  }, [visibilityFilter, includeInactive]);

  const loadApps = async () => {
    setIsLoading(true);
    try {
      const params = {};
      if (visibilityFilter) params.visibility = visibilityFilter;
      if (includeInactive) params.include_inactive = true;

      const response = await microSaasService.getMicroSaasApps(params);
      setApps(response.apps || []);
    } catch (error) {
      console.error('Error loading Micro SaaS apps:', error);
      showErrorToast('Failed to load Micro SaaS apps');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (appId, appName) => {
    if (!window.confirm(`Are you sure you want to delete "${appName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await microSaasService.deleteMicroSaasApp(appId);
      showSuccessToast(`App "${appName}" deleted successfully`);
      loadApps();
    } catch (error) {
      console.error('Error deleting app:', error);
      showErrorToast('Failed to delete app');
    }
  };

  const filteredApps = apps.filter(app =>
    app.frontend_app_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    app.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getVisibilityIcon = (visibility) => {
    switch (visibility) {
      case 'public':
        return <GlobeAltIcon className="h-5 w-5 text-green-500" />;
      case 'private':
        return <LockClosedIcon className="h-5 w-5 text-yellow-500" />;
      case 'granted_access':
        return <ShieldCheckIcon className="h-5 w-5 text-primary" />;
      default:
        return <LockClosedIcon className="h-5 w-5 text-gray-500" />;
    }
  };

  const getVisibilityBadge = (visibility) => {
    const colors = {
      'public': 'bg-green-100 text-green-800',
      'private': 'bg-yellow-100 text-yellow-800',
      'granted_access': 'bg-blue-100 text-blue-800'
    };

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[visibility] || 'bg-gray-100 text-gray-800'}`}>
        {microSaasService.formatVisibility(visibility)}
      </span>
    );
  };

  const getBillingBadge = (billingPreference) => {
    const colors = {
      'per_user_per_month': 'bg-purple-100 text-purple-800',
      'per_execution': 'bg-blue-100 text-blue-800',
      'free': 'bg-green-100 text-green-800'
    };

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colors[billingPreference] || 'bg-gray-100 text-gray-800'}`}>
        {microSaasService.formatBillingPreference(billingPreference)}
      </span>
    );
  };

  return (
    <div className="container mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Micro SaaS Apps</h1>
            <p className="mt-1 text-sm text-gray-500">
              Manage your monetizable flow applications
            </p>
          </div>
          <button
            onClick={() => navigate('/flows')}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            Create New App
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search apps..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
              />
            </div>
          </div>

          {/* Filter Toggle */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            <FunnelIcon className="h-5 w-5 mr-2" />
            Filters
          </button>
        </div>

        {/* Filter Options */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Visibility Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Visibility
                </label>
                <select
                  value={visibilityFilter}
                  onChange={(e) => setVisibilityFilter(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                >
                  <option value="">All</option>
                  <option value="public">Public</option>
                  <option value="private">Private</option>
                  <option value="granted_access">Granted Access</option>
                </select>
              </div>

              {/* Status Filter */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Status
                </label>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    checked={includeInactive}
                    onChange={(e) => setIncludeInactive(e.target.checked)}
                    className="h-4 w-4 text-primary focus:ring-primary border-gray-300 rounded"
                  />
                  <label className="ml-2 text-sm text-gray-700">
                    Include inactive apps
                  </label>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Apps List */}
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      ) : filteredApps.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <GlobeAltIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No Micro SaaS apps</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating your first Micro SaaS app.
          </p>
          <div className="mt-6">
            <button
              onClick={() => navigate('/flows')}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              Create Micro SaaS App
            </button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredApps.map((app) => (
            <div
              key={app.frontend_app_id}
              className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow duration-200"
            >
              {/* Card Header */}
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0 pr-4">
                    <h3 className="text-lg font-semibold text-gray-900 break-words line-clamp-2">
                      {app.frontend_app_name}
                    </h3>
                    <p className="mt-1 text-sm text-gray-500 break-words line-clamp-2">
                      {app.description || 'No description'}
                    </p>
                  </div>
                  <div className="flex-shrink-0">
                    {app.is_active ? (
                      <CheckCircleIcon className="h-6 w-6 text-green-500" />
                    ) : (
                      <XCircleIcon className="h-6 w-6 text-gray-400" />
                    )}
                  </div>
                </div>

                {/* Creator and Tenant Info */}
                <div className="mt-3 space-y-1">
                  {app.creator_username && (
                    <p className="text-xs text-gray-600">
                      <span className="font-medium">Created by:</span> {app.creator_username}
                    </p>
                  )}
                  {app.tenant_name && (
                    <p className="text-xs text-gray-600">
                      <span className="font-medium">Tenant:</span> {app.tenant_name}
                    </p>
                  )}
                </div>

                {/* Badges */}
                <div className="mt-4 flex flex-wrap gap-2">
                  {getVisibilityBadge(app.visibility)}
                  {getBillingBadge(app.billing_preference)}
                </div>

                {/* Stats */}
                <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500">Executions</p>
                    <p className="mt-1 font-semibold text-gray-900">{app.usage_count || 0}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Rate Limit</p>
                    <p className="mt-1 font-semibold text-gray-900">{app.rate_limit_per_hour}/hr</p>
                  </div>
                </div>

                {/* Public URL */}
                <div className="mt-4">
                  <a
                    href={app.public_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-primary hover:text-primary-dark break-all block"
                    title={app.public_url}
                  >
                    {app.public_url}
                  </a>
                </div>
              </div>

              {/* Card Actions */}
              <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
                <div className="flex space-x-2">
                  <button
                    onClick={() => navigate(`/micro-saas/${app.frontend_app_id}`)}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                    title="Settings"
                  >
                    <Cog6ToothIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => navigate(`/micro-saas/${app.frontend_app_id}/analytics`)}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                    title="Analytics"
                  >
                    <ChartBarIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => window.open(app.public_url, '_blank')}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                    title="View App"
                  >
                    <EyeIcon className="h-4 w-4" />
                  </button>
                </div>
                <button
                  onClick={() => handleDelete(app.frontend_app_id, app.frontend_app_name)}
                  className="inline-flex items-center px-3 py-1.5 border border-red-300 rounded-md text-sm font-medium text-red-700 bg-white hover:bg-red-50"
                  title="Delete"
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary Stats */}
      {!isLoading && filteredApps.length > 0 && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-700 mb-4">Summary</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-2xl font-bold text-gray-900">{filteredApps.length}</p>
              <p className="text-sm text-gray-500">Total Apps</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-green-600">
                {filteredApps.filter(a => a.is_active).length}
              </p>
              <p className="text-sm text-gray-500">Active</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-primary">
                {filteredApps.reduce((sum, app) => sum + (app.usage_count || 0), 0)}
              </p>
              <p className="text-sm text-gray-500">Total Executions</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-purple-600">
                {filteredApps.filter(a => a.billing_preference !== 'free').length}
              </p>
              <p className="text-sm text-gray-500">Paid Apps</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MicroSaasAppsPage;
