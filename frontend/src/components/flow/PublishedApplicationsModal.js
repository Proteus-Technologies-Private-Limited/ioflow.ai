import React, { useState, useEffect } from 'react';
import { 
  XMarkIcon, 
  MagnifyingGlassIcon,
  ArrowPathIcon,
  TrashIcon,
  EyeIcon,
  CogIcon,
  ShareIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  GlobeAltIcon,
  CodeBracketIcon,
  PlusIcon
} from '@heroicons/react/24/outline';
import { flowPublishingService } from '../../services/flowPublishingService';
import { showErrorToast, showSuccessToast, showInfoToast } from '../../utils/customToast';
import FrontendAppConfig from './FrontendAppConfig';
import EmbedCodeViewer from './EmbedCodeViewer';

const PublishedApplicationsModal = ({ isOpen, onClose }) => {
  // Tab state
  const [activeTab, setActiveTab] = useState('published'); // 'published' or 'frontend'
  
  // Published apps state
  const [publishedApps, setPublishedApps] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedApp, setSelectedApp] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [statusFilter, setStatusFilter] = useState('all');
  
  // Frontend apps state
  const [frontendApps, setFrontendApps] = useState([]);
  const [selectedFrontendApp, setSelectedFrontendApp] = useState(null);
  const [showFrontendDetails, setShowFrontendDetails] = useState(false);
  const [showCreateFrontendApp, setShowCreateFrontendApp] = useState(false);
  const [showEmbedCode, setShowEmbedCode] = useState(false);

  const fetchPublishedApps = async () => {
    if (!isOpen || activeTab !== 'published') return;
    
    setIsLoading(true);
    try {
      const data = await flowPublishingService.getPublishedApplications({
        search: searchTerm,
        status: statusFilter === 'all' ? undefined : statusFilter,
        sort_by: sortBy,
        sort_order: sortOrder
      });
      setPublishedApps(data.applications || []);
    } catch (error) {
      showErrorToast(`Failed to fetch published applications: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFrontendApps = async () => {
    if (!isOpen || activeTab !== 'frontend') return;
    
    setIsLoading(true);
    try {
      // This will need to be implemented to fetch all frontend apps for the user
      // For now, we'll fetch frontend apps for each published app
      const allFrontendApps = [];
      for (const publishedApp of publishedApps) {
        try {
          const response = await fetch(`/api/v1/frontend-applications/published-app/${publishedApp.published_app_id}`);
          if (response.ok) {
            const frontendAppsData = await response.json();
            allFrontendApps.push(...frontendAppsData);
          }
        } catch (error) {
          console.error(`Error fetching frontend apps for ${publishedApp.app_key}:`, error);
        }
      }
      setFrontendApps(allFrontendApps);
    } catch (error) {
      showErrorToast(`Failed to fetch frontend applications: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'published') {
      fetchPublishedApps();
    } else if (activeTab === 'frontend') {
      fetchFrontendApps();
    }
  }, [isOpen, activeTab, searchTerm, sortBy, sortOrder, statusFilter]);

  // Tab change handler
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchTerm('');
    setStatusFilter('all');
  };

  const handleViewDetails = async (app) => {
    try {
      const details = await flowPublishingService.getPublishedApplication(app.published_app_id);
      setSelectedApp(details);
      setShowDetails(true);
    } catch (error) {
      showErrorToast(`Failed to fetch application details: ${error.message}`);
    }
  };

  const handleUpdate = async (appId) => {
    try {
      await flowPublishingService.updatePublishedApplication(appId);
      showSuccessToast('Application updated successfully');
      fetchPublishedApps();
    } catch (error) {
      showErrorToast(`Update failed: ${(error.response?.data?.message || error.response?.data?.detail) || error.message}`);
    }
  };

  const handleUnpublish = async (appId, appName) => {
    if (!window.confirm(`Are you sure you want to unpublish "${appName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      await flowPublishingService.unpublishApplication(appId);
      showSuccessToast('Application unpublished successfully');
      fetchPublishedApps();
    } catch (error) {
      showErrorToast(`Unpublish failed: ${(error.response?.data?.message || error.response?.data?.detail) || error.message}`);
    }
  };

  const handleDeleteFrontendApp = async (frontendAppId, appName) => {
    if (!window.confirm(`Are you sure you want to delete "${appName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await fetch(`/api/v1/frontend-applications/${frontendAppId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
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

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'inactive': return 'bg-yellow-100 text-yellow-800';
      case 'deprecated': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
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

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-purple-600 to-blue-600 px-6 py-4 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <ShareIcon className="w-6 h-6" />
              <div>
                <h2 className="text-xl font-semibold">Flow Applications</h2>
                <p className="text-purple-100 text-sm">Manage your reusable and public applications</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 transition-colors"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="bg-white border-b">
          <div className="px-6">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => handleTabChange('published')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'published'
                    ? 'border-purple-500 text-purple-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <div className="flex items-center">
                  <CogIcon className="w-4 h-4 mr-2" />
                  Reusable Applications
                </div>
              </button>
              <button
                onClick={() => handleTabChange('frontend')}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'frontend'
                    ? 'border-purple-500 text-purple-600'
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
        </div>

        {/* Filters and Search */}
        <div className="bg-gray-50 border-b px-6 py-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-64">
              <div className="relative">
                <MagnifyingGlassIcon className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search applications..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
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
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="created_at-desc">Newest First</option>
              <option value="created_at-asc">Oldest First</option>
              <option value="app_name-asc">Name A-Z</option>
              <option value="app_name-desc">Name Z-A</option>
              <option value="usage_count-desc">Most Used</option>
              <option value="usage_count-asc">Least Used</option>
            </select>

            <button
              onClick={activeTab === 'published' ? fetchPublishedApps : fetchFrontendApps}
              disabled={isLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center"
            >
              <ArrowPathIcon className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            
            {activeTab === 'frontend' && (
              <button
                onClick={() => {
                  // For creating a new frontend app, we need to select from published apps
                  // For now, we'll show a simple approach - if there's only one published app, use it
                  // Otherwise, we'll need a selection mechanism
                  if (publishedApps.length === 1) {
                    setSelectedApp(publishedApps[0]);
                    setShowCreateFrontendApp(true);
                  } else {
                    showInfoToast('Please switch to the Reusable Applications tab to select which published app to make into a frontend app');
                  }
                }}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center"
              >
                <PlusIcon className="w-4 h-4 mr-2" />
                Create Frontend App
              </button>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {activeTab === 'published' ? (
            // Published Applications Tab
            isLoading ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600">Loading published applications...</p>
              </div>
            ) : publishedApps.length === 0 ? (
              <div className="text-center py-8">
                <ShareIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Published Applications</h3>
                <p className="text-gray-600">
                  {searchTerm ? 'No applications match your search criteria.' : 'You haven\'t published any flows as applications yet.'}
                </p>
              </div>
            ) : (
            <div className="space-y-4">
              {publishedApps.map((app) => (
                <div key={app.published_app_id} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h3 className="text-lg font-medium text-gray-900">{app.app_name}</h3>
                        <span className={`px-2 py-1 text-xs rounded-full font-medium ${getStatusColor(app.status)}`}>
                          {app.status}
                        </span>
                        {app.auto_update && (
                          <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full font-medium">
                            Auto-update
                          </span>
                        )}
                      </div>
                      
                      <p className="text-gray-600 text-sm mb-3">{app.description}</p>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-gray-500">Key:</span>
                          <p className="font-mono text-gray-900">{app.app_key}</p>
                        </div>
                        <div>
                          <span className="text-gray-500">Flow:</span>
                          <p className="text-gray-900">{app.flow_name}</p>
                        </div>
                        <div>
                          <span className="text-gray-500">Version:</span>
                          <p className="text-gray-900">{app.published_version}</p>
                        </div>
                        <div>
                          <span className="text-gray-500">Usage:</span>
                          <p className="text-gray-900">{app.usage_count || 0} times</p>
                        </div>
                      </div>
                      
                      <div className="flex items-center text-xs text-gray-500 mt-3">
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
                    
                    <div className="flex items-center space-x-2 ml-4">
                      <button
                        onClick={() => handleViewDetails(app)}
                        className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                        title="View Details"
                      >
                        <EyeIcon className="w-4 h-4" />
                      </button>
                      
                      {app.status === 'active' && (
                        <button
                          onClick={() => handleUpdate(app.published_app_id)}
                          className="p-2 text-gray-600 hover:text-green-600 hover:bg-green-50 rounded-md transition-colors"
                          title="Update from Flow"
                        >
                          <ArrowPathIcon className="w-4 h-4" />
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
                        <GlobeAltIcon className="w-4 h-4" />
                      </button>
                      
                      <button
                        onClick={() => handleUnpublish(app.published_app_id, app.app_name)}
                        className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                        title="Unpublish"
                      >
                        <TrashIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            )
          ) : (
            // Frontend Applications Tab
            isLoading ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <p className="text-gray-600">Loading frontend applications...</p>
              </div>
            ) : frontendApps.length === 0 ? (
              <div className="text-center py-8">
                <GlobeAltIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Frontend Applications</h3>
                <p className="text-gray-600">
                  {searchTerm ? 'No applications match your search criteria.' : 'Create frontend applications to make your flows publicly accessible.'}
                </p>
                <button
                  onClick={() => setShowCreateFrontendApp(true)}
                  className="mt-4 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 inline-flex items-center"
                >
                  <PlusIcon className="w-4 h-4 mr-2" />
                  Create Your First Frontend App
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {frontendApps.map((app) => (
                  <div key={app.frontend_app_id} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3 mb-2">
                          <h3 className="text-lg font-medium text-gray-900">{app.frontend_app_name}</h3>
                          <span className={`px-2 py-1 text-xs rounded-full font-medium ${app.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                            {app.is_active ? 'Active' : 'Inactive'}
                          </span>
                          <span className="px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded-full font-medium">
                            {app.access_type.replace('_', ' ')}
                          </span>
                        </div>
                        
                        <p className="text-gray-600 text-sm mb-3">{app.description}</p>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                          <div>
                            <span className="text-gray-500">URL Slug:</span>
                            <p className="font-mono text-gray-900">{app.public_url_slug}</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Access Type:</span>
                            <p className="text-gray-900">{app.access_type.replace('_', ' ')}</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Usage Count:</span>
                            <p className="text-gray-900">{app.usage_count || 0} times</p>
                          </div>
                          <div>
                            <span className="text-gray-500">Rate Limit:</span>
                            <p className="text-gray-900">{app.rate_limit_per_hour}/hour</p>
                          </div>
                        </div>
                        
                        <div className="mt-3 flex items-center text-xs text-gray-500">
                          <ClockIcon className="w-4 h-4 mr-1" />
                          Created {formatDate(app.created_at)}
                          <span className="mx-2">•</span>
                          <a 
                            href={app.public_url} 
                            target="_blank" 
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800"
                          >
                            {app.public_url}
                          </a>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-2 ml-4">
                        <button
                          onClick={() => {
                            setSelectedFrontendApp(app);
                            setShowEmbedCode(true);
                          }}
                          className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                          title="Generate Embed Code"
                        >
                          <CodeBracketIcon className="w-4 h-4" />
                        </button>
                        
                        <button
                          onClick={() => {
                            setSelectedFrontendApp(app);
                            setShowFrontendDetails(true);
                          }}
                          className="p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-md transition-colors"
                          title="View Details"
                        >
                          <EyeIcon className="w-4 h-4" />
                        </button>
                        
                        <button
                          onClick={() => handleDeleteFrontendApp(app.frontend_app_id, app.frontend_app_name)}
                          className="p-2 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
                          title="Delete Frontend App"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            {activeTab === 'published' 
              ? `${publishedApps.length} application${publishedApps.length !== 1 ? 's' : ''} found`
              : `${frontendApps.length} frontend application${frontendApps.length !== 1 ? 's' : ''} found`
            }
          </div>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
          >
            Close
          </button>
        </div>
      </div>

      {/* Details Modal */}
      {showDetails && selectedApp && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[120]">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
            <div className="bg-gray-800 px-6 py-4 text-white">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Application Details</h3>
                <button
                  onClick={() => setShowDetails(false)}
                  className="text-white hover:text-gray-200"
                >
                  <XMarkIcon className="w-5 h-5" />
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
                        <span>{selectedApp.published_version}</span>
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
    </div>
  );
};

export default PublishedApplicationsModal;