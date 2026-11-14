import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  ShareIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  TrashIcon,
  EyeIcon,
  CogIcon,
  PlusIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowTopRightOnSquareIcon,
  ChartBarIcon,
  GlobeAltIcon,
  CodeBracketIcon,
  BookOpenIcon
} from '@heroicons/react/24/outline';
import { flowPublishingService } from '../services/flowPublishingService';
import { showErrorToast, showSuccessToast, showInfoToast } from '../utils/customToast';
import FrontendAppConfig from '../components/flow/FrontendAppConfig';
import EmbedCodeViewer from '../components/flow/EmbedCodeViewer';
import DocumentationManager from '../components/microsaas/DocumentationManager';
import DocumentationTab from '../components/microsaas/DocumentationTab';

const PublishedApplications = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  // Tab state
  const [activeTab, setActiveTab] = useState('published'); // 'published' or 'frontend'
  
  // Published apps state
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [selectedApp, setSelectedApp] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  
  // Frontend apps state
  const [frontendApps, setFrontendApps] = useState([]);
  const [selectedFrontendApp, setSelectedFrontendApp] = useState(null);
  const [showCreateFrontendApp, setShowCreateFrontendApp] = useState(false);
  const [showEmbedCode, setShowEmbedCode] = useState(false);
  const [showDocumentation, setShowDocumentation] = useState(false);
  const [expandedAppId, setExpandedAppId] = useState(null);
  const [appSubTab, setAppSubTab] = useState('overview'); // 'overview', 'documentation', 'embed'

  // Fetch published applications
  const { data: appsData, isLoading, error } = useQuery({
    queryKey: ['publishedApplications', searchTerm, statusFilter, sortBy, sortOrder],
    queryFn: () => flowPublishingService.getPublishedApplications({
      search: searchTerm,
      status: statusFilter === 'all' ? undefined : statusFilter,
      sort_by: sortBy,
      sort_order: sortOrder
    }),
    refetchOnWindowFocus: false,
  });

  // Fetch statistics
  const { data: stats } = useQuery({
    queryKey: ['publishingStats'],
    queryFn: () => flowPublishingService.getStatistics(),
    refetchOnWindowFocus: false,
  });

  const publishedApps = appsData || [];

  // Fetch frontend applications (both from published apps and direct frontend apps)
  const fetchFrontendApps = async () => {
    if (activeTab !== 'frontend') return;
    
    try {
      const allFrontendApps = [];
      
      // Get frontend apps created from published apps
      for (const publishedApp of publishedApps) {
        try {
          const response = await fetch(`/api/v1/frontend-applications/published-app/${publishedApp.published_app_id}`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            }
          });
          if (response.ok) {
            const frontendAppsData = await response.json();
            allFrontendApps.push(...frontendAppsData.map(app => ({
              ...app,
              published_app: publishedApp,
              type: 'from_published'
            })));
          }
        } catch (error) {
          console.error(`Error fetching frontend apps for ${publishedApp.app_key}:`, error);
        }
      }
      
      // Also fetch direct frontend applications (frontend-only)
      try {
        const directResponse = await fetch('/api/v1/frontend-applications/direct', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        });
        if (directResponse.ok) {
          const directApps = await directResponse.json();
          allFrontendApps.push(...directApps.map(app => ({
            ...app,
            type: 'direct_frontend'
          })));
        }
      } catch (error) {
        // Direct frontend endpoint might not exist yet, that's OK
        console.log('Direct frontend apps endpoint not available yet');
      }
      
      setFrontendApps(allFrontendApps);
    } catch (error) {
      showErrorToast(`Failed to fetch frontend applications: ${error.message}`);
    }
  };

  // Fetch frontend apps when tab changes or published apps change
  useEffect(() => {
    if (activeTab === 'frontend' && publishedApps.length > 0) {
      fetchFrontendApps();
    }
  }, [activeTab, publishedApps]);

  // Delete frontend app function
  const handleDeleteFrontendApp = async (frontendAppId, appName) => {
    if (!window.confirm(`Are you sure you want to delete "${appName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/frontend-applications/${frontendAppId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        }
      });

      if (!response.ok) {
        throw new Error('Failed to delete frontend application');
      }

      showSuccessToast('Frontend application deleted successfully');
      fetchFrontendApps();
    } catch (error) {
      showErrorToast(`Delete failed: ${error.message}`);
    }
  };

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (appId) => flowPublishingService.updatePublishedApplication(appId),
    onSuccess: () => {
      showSuccessToast('Application updated successfully');
      queryClient.invalidateQueries({ queryKey: ['publishedApplications'] });
    },
    onError: (error) => {
      showErrorToast(`Update failed: ${(error.response?.data?.message || error.response?.data?.detail) || error.message}`);
    }
  });

  // Unpublish mutation
  const unpublishMutation = useMutation({
    mutationFn: (appId) => flowPublishingService.unpublishApplication(appId),
    onSuccess: () => {
      showSuccessToast('Application unpublished successfully');
      queryClient.invalidateQueries({ queryKey: ['publishedApplications'] });
      queryClient.invalidateQueries({ queryKey: ['publishingStats'] });
    },
    onError: (error) => {
      showErrorToast(`Unpublish failed: ${(error.response?.data?.message || error.response?.data?.detail) || error.message}`);
    }
  });

  const handleViewDetails = async (app) => {
    try {
      const details = await flowPublishingService.getPublishedApplication(app.published_app_id);
      setSelectedApp(details);
      setShowDetails(true);
    } catch (error) {
      showErrorToast(`Failed to fetch application details: ${error.message}`);
    }
  };

  const handleUpdate = (appId) => {
    updateMutation.mutate(appId);
  };

  const handleUnpublish = (appId, appName) => {
    if (!window.confirm(`Are you sure you want to unpublish "${appName}"? This action cannot be undone.`)) {
      return;
    }
    unpublishMutation.mutate(appId);
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'inactive': return 'bg-yellow-100 text-yellow-800';
      case 'deprecated': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'active': return <CheckCircleIcon className="w-4 h-4" />;
      case 'inactive': return <ClockIcon className="w-4 h-4" />;
      case 'deprecated': return <ExclamationTriangleIcon className="w-4 h-4" />;
      default: return <ClockIcon className="w-4 h-4" />;
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="text-center">
            <ExclamationTriangleIcon className="mx-auto h-12 w-12 text-red-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">Error loading published applications</h3>
            <p className="mt-1 text-sm text-gray-500">{error.message}</p>
            <div className="mt-6">
              <button
                onClick={() => queryClient.invalidateQueries({ queryKey: ['publishedApplications'] })}
                className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg"
              >
                <ArrowPathIcon className="w-4 h-4 mr-2" />
                Retry
              </button>
            </div>
          </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 flex items-center">
                <ShareIcon className="w-8 h-8 mr-3 text-primary" />
                Flow Applications
              </h1>
              <p className="mt-2 text-gray-600">
                Manage your reusable and public applications
              </p>
            </div>
            
            <div className="flex items-center space-x-3">
              <button
                onClick={() => navigate('/flows')}
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                <PlusIcon className="w-4 h-4 mr-2" />
                Create Flow
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="mt-6 border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('published')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'published'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center">
                  <CogIcon className="w-4 h-4 mr-2" />
                  Reusable Applications
                </div>
              </button>
              <button
                onClick={() => setActiveTab('frontend')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'frontend'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center">
                  <GlobeAltIcon className="w-4 h-4 mr-2" />
                  Frontend Applications
                </div>
              </button>
            </nav>
          </div>

          {/* Statistics */}
          {stats && (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white p-4 rounded-lg shadow border">
                <div className="flex items-center">
                  <ShareIcon className="w-8 h-8 text-primary" />
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-600">Total Published</p>
                    <p className="text-2xl font-bold text-gray-900">{stats.total_published_applications || 0}</p>
                  </div>
                </div>
              </div>
              
              <div className="bg-white p-4 rounded-lg shadow border">
                <div className="flex items-center">
                  <CheckCircleIcon className="w-8 h-8 text-green-600" />
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-600">Active</p>
                    <p className="text-2xl font-bold text-gray-900">{stats.active_published_applications || 0}</p>
                  </div>
                </div>
              </div>
              
              <div className="bg-white p-4 rounded-lg shadow border">
                <div className="flex items-center">
                  <ChartBarIcon className="w-8 h-8 text-purple-600" />
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-600">My Apps</p>
                    <p className="text-2xl font-bold text-gray-900">{stats.user_published_applications || 0}</p>
                  </div>
                </div>
              </div>
              
              <div className="bg-white p-4 rounded-lg shadow border">
                <div className="flex items-center">
                  <ClockIcon className="w-8 h-8 text-yellow-600" />
                  <div className="ml-3">
                    <p className="text-sm font-medium text-gray-600">This Month</p>
                    <p className="text-2xl font-bold text-gray-900">{stats.monthly_usage || 0}</p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="bg-white p-6 rounded-lg shadow mb-6">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-64">
              <div className="relative">
                <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search applications..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
            </div>
            
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="deprecated">Deprecated</option>
            </select>

            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={(e) => {
                const [field, order] = e.target.value.split('-');
                setSortBy(field);
                setSortOrder(order);
              }}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
            >
              <option value="created_at-desc">Newest First</option>
              <option value="created_at-asc">Oldest First</option>
              <option value="app_name-asc">Name A-Z</option>
              <option value="app_name-desc">Name Z-A</option>
              <option value="usage_count-desc">Most Used</option>
              <option value="usage_count-asc">Least Used</option>
            </select>

            <button
              onClick={() => queryClient.invalidateQueries({ queryKey: ['publishedApplications'] })}
              disabled={isLoading}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 flex items-center"
            >
              <ArrowPathIcon className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>

        {/* Applications List */}
        {activeTab === 'published' ? (
          // Published Applications Tab
          isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
              <p className="text-gray-600">Loading published applications...</p>
            </div>
          ) : publishedApps.length === 0 ? (
          <div className="text-center py-12 bg-white rounded-lg shadow">
            <ShareIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Published Applications</h3>
            <p className="text-gray-600 mb-6">
              {searchTerm ? 'No applications match your search criteria.' : 'You haven\'t published any flows as applications yet.'}
            </p>
            {!searchTerm && (
              <button
                onClick={() => navigate('/flows')}
                className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                <PlusIcon className="w-4 h-4 mr-2" />
                Create Your First Flow
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {publishedApps.map((app) => (
              <div key={app.published_app_id} className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-3">
                      <h3 className="text-xl font-semibold text-gray-900">{app.app_name}</h3>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(app.status)}`}>
                        {getStatusIcon(app.status)}
                        <span className="ml-1">{app.status}</span>
                      </span>
                      {app.auto_update && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                          <ArrowPathIcon className="w-3 h-3 mr-1" />
                          Auto-update
                        </span>
                      )}
                    </div>
                    
                    <p className="text-gray-600 mb-4">{app.description}</p>
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-gray-500 block">Application Key</span>
                        <p className="font-mono text-gray-900">{app.app_key}</p>
                      </div>
                      <div>
                        <span className="text-gray-500 block">Source Flow</span>
                        <p className="text-gray-900">{app.flow_name}</p>
                      </div>
                      <div>
                        <span className="text-gray-500 block">Version</span>
                        <p className="text-gray-900">{app.version}</p>
                      </div>
                      <div>
                        <span className="text-gray-500 block">Usage Count</span>
                        <p className="text-gray-900">{app.usage_count || 0} times</p>
                      </div>
                    </div>
                    
                    <div className="flex items-center text-xs text-gray-500 mt-4">
                      <ClockIcon className="w-4 h-4 mr-1" />
                      Created {formatDate(app.created_at)}
                      {app.last_sync_at && (
                        <>
                          <span className="mx-2">•</span>
                          Last synced {formatDate(app.last_sync_at)}
                        </>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2 ml-6">
                    <button
                      onClick={() => handleViewDetails(app)}
                      className="p-2 text-gray-600 hover:text-primary hover:bg-primary-10 rounded-md transition-colors"
                      title="View Details"
                    >
                      <EyeIcon className="w-5 h-5" />
                    </button>
                    
                    {app.status === 'active' && (
                      <button
                        onClick={() => handleUpdate(app.published_app_id)}
                        disabled={updateMutation.isPending}
                        className="p-2 text-gray-600 hover:text-green-600 hover:bg-green-50 rounded-md transition-colors disabled:opacity-50"
                        title="Update from Flow"
                      >
                        <ArrowPathIcon className={`w-5 h-5 ${updateMutation.isPending ? 'animate-spin' : ''}`} />
                      </button>
                    )}
                    
                    <button
                      onClick={() => {
                        setSelectedApp(app);
                        setShowCreateFrontendApp(true);
                      }}
                      className="p-2 text-gray-600 hover:text-green-600 hover:bg-green-50 rounded-md transition-colors"
                      title="Create Frontend App"
                    >
                      <GlobeAltIcon className="w-5 h-5" />
                    </button>
                    
                    <button
                      onClick={() => navigate(`/flows`)}
                      className="p-2 text-gray-600 hover:text-purple-600 hover:bg-purple-50 rounded-md transition-colors"
                      title="Go to Flows"
                    >
                      <ArrowTopRightOnSquareIcon className="w-5 h-5" />
                    </button>
                    
                    <button
                      onClick={() => handleUnpublish(app.published_app_id, app.app_name)}
                      disabled={unpublishMutation.isPending}
                      className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
                      title="Unpublish"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
          )
        ) : (
          // Frontend Applications Tab
          <div className="space-y-4">
            {frontendApps.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg shadow">
                <GlobeAltIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Frontend Applications</h3>
                <p className="text-gray-600 mb-6">
                  Create frontend applications to make your flows publicly accessible.
                </p>
                <button
                  onClick={() => setActiveTab('published')}
                  className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                >
                  <PlusIcon className="w-4 h-4 mr-2" />
                  Go to Published Apps to Create Frontend App
                </button>
              </div>
            ) : (
              frontendApps.map((app) => {
                const isExpanded = expandedAppId === app.frontend_app_id;

                return (
                <div key={app.frontend_app_id} className="bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow">
                  {/* Main Card */}
                  <div className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-3">
                          <h3 className="text-xl font-semibold text-gray-900">{app.frontend_app_name}</h3>
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            app.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {app.is_active ? 'Active' : 'Inactive'}
                          </span>
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                            {app.access_type?.replace('_', ' ')}
                          </span>
                        </div>

                        <p className="text-gray-600 mb-4">{app.description}</p>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-gray-500 font-medium">URL Slug:</span>
                            <p className="font-mono text-gray-900">{app.public_url_slug}</p>
                          </div>
                          <div>
                            <span className="text-gray-500 font-medium">Access Type:</span>
                            <p className="text-gray-900 capitalize">{app.access_type?.replace('_', ' ')}</p>
                          </div>
                          <div>
                            <span className="text-gray-500 font-medium">Usage Count:</span>
                            <p className="text-gray-900">{app.usage_count || 0} times</p>
                          </div>
                          <div>
                            <span className="text-gray-500 font-medium">Rate Limit:</span>
                            <p className="text-gray-900">{app.rate_limit_per_hour}/hour</p>
                          </div>
                        </div>

                        <div className="mt-4 flex items-center text-sm text-gray-500">
                          <ClockIcon className="w-4 h-4 mr-1" />
                          Created {new Date(app.created_at).toLocaleDateString()}
                          <span className="mx-2">•</span>
                          <a
                            href={app.public_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:text-primary-dark flex items-center"
                          >
                            {app.public_url}
                            <ArrowTopRightOnSquareIcon className="w-3 h-3 ml-1" />
                          </a>
                        </div>
                      </div>

                      <div className="flex items-center space-x-2 ml-4">
                        <button
                          onClick={() => {
                            if (isExpanded && appSubTab === 'documentation') {
                              setExpandedAppId(null);
                            } else {
                              setExpandedAppId(app.frontend_app_id);
                              setAppSubTab('documentation');
                            }
                          }}
                          className={`p-2 rounded-md transition-colors ${
                            isExpanded && appSubTab === 'documentation'
                              ? 'text-purple-600 bg-purple-50'
                              : 'text-gray-600 hover:text-purple-600 hover:bg-purple-50'
                          }`}
                          title="Manage Documentation"
                        >
                          <BookOpenIcon className="w-5 h-5" />
                        </button>

                        <button
                          onClick={() => {
                            if (isExpanded && appSubTab === 'embed') {
                              setExpandedAppId(null);
                            } else {
                              setExpandedAppId(app.frontend_app_id);
                              setAppSubTab('embed');
                              setSelectedFrontendApp(app);
                            }
                          }}
                          className={`p-2 rounded-md transition-colors ${
                            isExpanded && appSubTab === 'embed'
                              ? 'text-primary bg-primary-10'
                              : 'text-gray-600 hover:text-primary hover:bg-primary-10'
                          }`}
                          title="Generate Embed Code"
                        >
                          <CodeBracketIcon className="w-5 h-5" />
                        </button>

                        <button
                          onClick={() => handleDeleteFrontendApp(app.frontend_app_id, app.frontend_app_name)}
                          className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                          title="Delete Frontend App"
                        >
                          <TrashIcon className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Section with Tabs */}
                  {isExpanded && (
                    <div className="border-t border-gray-200">
                      {/* Tab Navigation */}
                      <div className="flex space-x-1 px-6 pt-4 border-b">
                        <button
                          onClick={() => setAppSubTab('overview')}
                          className={`px-4 py-2 text-sm font-medium rounded-t-lg ${
                            appSubTab === 'overview'
                              ? 'bg-white text-primary border-b-2 border-primary'
                              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                          }`}
                        >
                          Overview
                        </button>
                        <button
                          onClick={() => setAppSubTab('documentation')}
                          className={`px-4 py-2 text-sm font-medium rounded-t-lg flex items-center gap-2 ${
                            appSubTab === 'documentation'
                              ? 'bg-white text-primary border-b-2 border-primary'
                              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                          }`}
                        >
                          <BookOpenIcon className="w-4 h-4" />
                          Documentation
                        </button>
                        <button
                          onClick={() => {
                            setAppSubTab('embed');
                            setSelectedFrontendApp(app);
                          }}
                          className={`px-4 py-2 text-sm font-medium rounded-t-lg flex items-center gap-2 ${
                            appSubTab === 'embed'
                              ? 'bg-white text-primary border-b-2 border-primary'
                              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                          }`}
                        >
                          <CodeBracketIcon className="w-4 h-4" />
                          Embed Code
                        </button>
                      </div>

                      {/* Tab Content */}
                      <div className="p-6 bg-gray-50">
                        {appSubTab === 'overview' && (
                          <div className="bg-white rounded-lg p-6">
                            <h4 className="text-lg font-semibold mb-4">Application Overview</h4>
                            <div className="space-y-3 text-sm">
                              <div>
                                <span className="font-medium text-gray-700">Description:</span>
                                <p className="text-gray-600 mt-1">{app.description}</p>
                              </div>
                              <div>
                                <span className="font-medium text-gray-700">Public URL:</span>
                                <a
                                  href={app.public_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary hover:text-primary-dark block mt-1"
                                >
                                  {app.public_url}
                                </a>
                              </div>
                              <div>
                                <span className="font-medium text-gray-700">Status:</span>
                                <p className="text-gray-600 mt-1">{app.is_active ? 'Active' : 'Inactive'}</p>
                              </div>
                            </div>
                          </div>
                        )}

                        {appSubTab === 'documentation' && (
                          <DocumentationTab
                            appId={app.frontend_app_id}
                            appName={app.frontend_app_name}
                          />
                        )}

                        {appSubTab === 'embed' && selectedFrontendApp && (
                          <div className="bg-white rounded-lg p-6">
                            <h4 className="text-lg font-semibold mb-4">Embed Code</h4>
                            <EmbedCodeViewer frontendApp={selectedFrontendApp} />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
                );
              })
            )}
          </div>
        )}

        {/* Details Modal */}
        {showDetails && selectedApp && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
            <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
              <div className="bg-gray-800 px-6 py-4 text-white">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold">Application Details</h3>
                  <button
                    onClick={() => setShowDetails(false)}
                    className="text-white hover:text-gray-200"
                  >
                    ✕
                  </button>
                </div>
              </div>
              
              <div className="p-6 max-h-[70vh] overflow-y-auto">
                <div className="space-y-6">
                  <div>
                    <h4 className="text-lg font-medium text-gray-900 mb-3">{selectedApp.app_name}</h4>
                    <p className="text-gray-600">{selectedApp.description}</p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <h5 className="font-medium text-gray-900 mb-2">Application Info</h5>
                      <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600">Key:</span>
                          <span className="font-mono">{selectedApp.app_key}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Status:</span>
                          <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(selectedApp.status)}`}>
                            {selectedApp.status}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Version:</span>
                          <span>{selectedApp.version}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Usage Count:</span>
                          <span>{selectedApp.usage_count || 0}</span>
                        </div>
                      </div>
                    </div>

                    <div>
                      <h5 className="font-medium text-gray-900 mb-2">Flow Analysis</h5>
                      <div className="bg-blue-50 rounded-lg p-4 space-y-2 text-sm">
                        {selectedApp.flow_analysis && (
                          <>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Input Parameters:</span>
                              <span>{selectedApp.flow_analysis.input_parameters?.length || 0}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Transformations:</span>
                              <span>{selectedApp.flow_analysis.transformations?.length || 0}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Dependencies:</span>
                              <span>{selectedApp.flow_analysis.dependencies?.length || 0}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Complexity:</span>
                              <span>{selectedApp.flow_analysis.complexity_score || 0}</span>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {selectedApp.services && selectedApp.services.length > 0 && (
                    <div>
                      <h5 className="font-medium text-gray-900 mb-3">Generated Services</h5>
                      <div className="space-y-3">
                        {selectedApp.services.map((service, index) => (
                          <div key={index} className="border border-gray-200 rounded-lg p-4">
                            <h6 className="font-medium text-gray-900">{service.service_name}</h6>
                            <p className="text-sm text-gray-600 mt-1">{service.description}</p>
                            <div className="mt-2 flex items-center space-x-2 text-xs">
                              <span className="bg-gray-100 px-2 py-1 rounded">{service.service_type}</span>
                              <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">
                                {service.parameters?.length || 0} parameters
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Frontend App Creation Modal */}
        <FrontendAppConfig
          isOpen={showCreateFrontendApp}
          onClose={() => setShowCreateFrontendApp(false)}
          publishedApp={selectedApp}
          onSuccess={() => {
            setShowCreateFrontendApp(false);
            fetchFrontendApps();
          }}
        />

        {/* Embed Code Viewer Modal */}
        <EmbedCodeViewer
          isOpen={showEmbedCode}
          onClose={() => setShowEmbedCode(false)}
          frontendApp={selectedFrontendApp}
        />

        {/* Documentation Manager Modal */}
        {showDocumentation && selectedFrontendApp && (
          <DocumentationManager
            appId={selectedFrontendApp.frontend_app_id}
            appName={selectedFrontendApp.frontend_app_name}
            onClose={() => {
              setShowDocumentation(false);
              setSelectedFrontendApp(null);
            }}
          />
        )}
    </div>
  );
};

export default PublishedApplications;