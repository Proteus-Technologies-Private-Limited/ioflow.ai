import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useFilters } from '../contexts/FilterContext';
import axios from 'axios';
import '../styles/FilterIndicators.css';
import { 
  PlusIcon, 
  MagnifyingGlassIcon,
  CogIcon,
  BoltIcon,
  LinkIcon,
  ChevronRightIcon,
  Cog6ToothIcon,
  ExclamationTriangleIcon,
  CircleStackIcon,
  ChevronUpDownIcon,
  XMarkIcon,
  EllipsisVerticalIcon,
  TrashIcon,
  DocumentDuplicateIcon
} from '@heroicons/react/24/outline';
import { useDebounce } from '../hooks/useDebounce';
import { useAuth } from '../contexts/AuthContext';
import ConnectionModal from '../components/applications/ConnectionModal';
import AuthDebugModal from '../components/applications/AuthDebugModal';
import InstanceManagementModal from '../components/applications/InstanceManagementModal';
import TestAuthFlow from '../components/TestAuthFlow';
import { showErrorToast, showSuccessToast, showWarningToast, showInfoToast } from '../utils/customToast';
import { getFullErrorMessage } from '../utils/errorHandler';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

function Applications() {
  const { user } = useAuth();
  const canManageApps = user?.role !== 'EXECUTION_MONITOR' && user?.role !== 'FLOW_EXECUTOR';
  const [applications, setApplications] = useState([]);
  const [subscriptions, setSubscriptions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { getPageFilters, updatePageFilters, clearPageFilters } = useFilters();
  
  // Get saved filters or use defaults
  const savedFilters = getPageFilters('applications', {
    filter: 'all',
    searchTerm: '',
    selectedCategory: 'all'
  });
  
  const [filter, setFilter] = useState(savedFilters.filter);
  const [searchTerm, setSearchTerm] = useState(savedFilters.searchTerm);
  const [selectedCategory, setSelectedCategory] = useState(savedFilters.selectedCategory);
  const [showConnectionModal, setShowConnectionModal] = useState(false);
  const [showAuthDebugModal, setShowAuthDebugModal] = useState(false);
  const [showTestAuthFlow, setShowTestAuthFlow] = useState(false);
  const [showInstanceModal, setShowInstanceModal] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);
  const [selectedSubscription, setSelectedSubscription] = useState(null);
  const [sortBy, setSortBy] = useState('updated_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [applicationInstances, setApplicationInstances] = useState({}); // Store instances for each app
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [openDropdownId, setOpenDropdownId] = useState(null); // For managing dropdown menus

  // Debounce search term to avoid too many API calls
  const debouncedSearchTerm = useDebounce(searchTerm, 500);
  
  // Save filters whenever they change
  useEffect(() => {
    updatePageFilters('applications', {
      filter,
      searchTerm,
      selectedCategory
    });
  }, [filter, searchTerm, selectedCategory, updatePageFilters]);

  useEffect(() => {
    fetchApplications();
    fetchSubscriptions();
    
    // Check for OAuth callback parameters
    const urlParams = new URLSearchParams(window.location.search);
    const authResult = urlParams.get('auth');
    const appName = urlParams.get('app');
    
    if (authResult === 'success') {
      // OAuth was successful, close any open modals
      setShowConnectionModal(false);
      showSuccessToast(`Successfully connected to ${appName || 'the application'}!`);
      // Clean up URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
      // Refresh subscriptions to show the new connection
      fetchSubscriptions();
    } else if (authResult === 'error') {
      // OAuth failed
      setShowConnectionModal(false);
      const error = urlParams.get('error');
      showErrorToast(`Failed to connect: ${error || 'Authorization failed'}`);
      // Clean up URL parameters
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  useEffect(() => {
    // Refetch applications when debounced search or sort changes
    fetchApplications();
  }, [debouncedSearchTerm, sortBy, sortOrder]);

  useEffect(() => {
    // Close dropdown when clicking outside
    const handleClickOutside = (event) => {
      if (openDropdownId && !event.target.closest('.dropdown-menu')) {
        setOpenDropdownId(null);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [openDropdownId]);

  const fetchApplications = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const params = {
        search: debouncedSearchTerm,
        sort_by: sortBy,
        sort_order: sortOrder
      };
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/`, {
        headers: { Authorization: `Bearer ${token}` },
        params
      });
      setApplications(response.data);
      setLoading(false);
    } catch (err) {
      const errorMessage = getFullErrorMessage(err, 'Failed to load applications');
      setError(errorMessage);
      setLoading(false);
    }
  };

  const fetchSubscriptions = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/subscriptions/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      console.log('Applications - Fetched subscriptions from backend:', response.data);
      // Check if subscriptions have the application relationship
      if (response.data.length > 0) {
        console.log('First subscription has application?', !!response.data[0].application);
        console.log('First subscription structure:', response.data[0]);
      }
      const subMap = {};
      response.data.forEach(sub => {
        subMap[sub.app_id] = sub;
      });
      setSubscriptions(subMap);
    } catch (err) {
      const errorMessage = getFullErrorMessage(err, 'Failed to load subscriptions');
      console.error(errorMessage);
      // Don't show toast here as it's called on mount and could be annoying
    }
  };

  const handleSubscribe = async (app) => {
    console.log('handleSubscribe called for app:', app.app_name, app.app_id);
    console.log('App auth_type:', app.auth_type);
    console.log('App auth_config:', app.auth_config);
    
    try {
      const token = localStorage.getItem('access_token');
      
      // Check if this OAuth app has default credentials
      if (app.auth_type === 'oauth2') {
        console.log('Checking for default OAuth credentials...');
        const checkResponse = await axios.get(
          `${API_BASE_URL}/api/v1/applications/${app.app_id}/has-default-oauth`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        
        console.log('Default OAuth check response:', checkResponse.data);
        
        if (checkResponse.data.has_default_oauth) {
          console.log('App has default OAuth credentials, starting OAuth flow directly...');
          
          // For OAuth apps with default credentials, start OAuth flow immediately without creating subscription
          showInfoToast('Redirecting to authorize access...');
          
          // Clear any existing URL parameters to avoid confusion
          window.history.replaceState({}, document.title, window.location.pathname);
          
          // Start OAuth flow immediately
          const currentUrl = window.location.href.split('?')[0];
          console.log('Starting OAuth flow for app:', app.app_id);
          console.log('Current URL:', currentUrl);
          
          try {
            const authResponse = await axios.get(
              `${API_BASE_URL}/api/v1/oauth2/authorize`,
              {
                params: {
                  app_id: app.app_id,
                  redirect_uri: currentUrl
                },
                headers: { Authorization: `Bearer ${token}` }
              }
            );
            
            console.log('OAuth authorize response:', authResponse.data);
            const { authorization_url, use_popup } = authResponse.data;
            
            if (!authorization_url) {
              throw new Error('No authorization URL received');
            }
            
            // Set a flag to prevent showing success messages until we return from OAuth
            sessionStorage.setItem('oauth_flow_in_progress', 'true');
            
            // Open OAuth window
            console.log('Opening OAuth in popup:', authorization_url);
            console.log('Use popup:', use_popup);
            
            if (use_popup) {
              // Open in popup window
              const width = 600;
              const height = 700;
              const left = (window.screen.width - width) / 2;
              const top = (window.screen.height - height) / 2;
              
              const popup = window.open(
                authorization_url,
                'oauth2_popup',
                `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
              );
              
              if (!popup || popup.closed || typeof popup.closed === 'undefined') {
                // Popup was blocked, fall back to redirect
                console.warn('Popup blocked, falling back to redirect');
                showWarningToast('Popup was blocked. Redirecting to authorization page...');
                setTimeout(() => {
                  window.location.href = authorization_url;
                }, 1500);
                return;
              }
              
              // Listen for messages from the popup
              const messageHandler = (event) => {
                // Verify the message is from our domain
                if (event.origin !== window.location.origin) return;
                
                if (event.data.type === 'oauth-success') {
                  window.removeEventListener('message', messageHandler);
                  showSuccessToast(`Successfully connected to ${event.data.app || app.app_name}`);
                  fetchSubscriptions();
                } else if (event.data.type === 'oauth-error') {
                  window.removeEventListener('message', messageHandler);
                  showErrorToast('OAuth2 authorization failed. Please try again from the settings.');
                  // Refresh to show the subscription with "Auth Required" status
                  fetchSubscriptions();
                }
              };
              
              window.addEventListener('message', messageHandler);
              
              // Also check for popup close
              const checkPopup = setInterval(() => {
                if (popup.closed) {
                  clearInterval(checkPopup);
                  window.removeEventListener('message', messageHandler);
                  // Refresh subscriptions to check if auth was successful
                  fetchSubscriptions();
                }
              }, 1000);
            } else {
              // Redirect to OAuth provider
              window.location.href = authorization_url;
            }
            
          } catch (authError) {
            console.error('OAuth authorization error:', authError);
            console.error('Error response:', authError.response);
            showErrorToast('Failed to start OAuth: ' + (authError.response?.data?.detail || authError.message));
            // Still refresh subscriptions to show the created subscription
            await fetchSubscriptions();
          }
          
          return; // Exit early
        } else {
          console.log('App does not have default OAuth credentials, showing modal...');
        }
      }
      
      // For non-OAuth or OAuth without defaults, show modal
      console.log('Showing connection modal for app:', app.app_name);
      setSelectedApp(app);
      // Check if app already has a subscription - pass it to modal for update instead of create
      const existingSubscription = subscriptions[app.app_id];
      setSelectedSubscription(existingSubscription || null);
      setShowConnectionModal(true);
      
    } catch (error) {
      console.error('Error in handleSubscribe:', error);
      console.error('Error response:', error.response);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to connect');
    }
  };

  const fetchApplicationInstances = async (appId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/applications/${appId}/instances`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      const instances = response.data || [];
      
      // Store instances by the provided app ID
      setApplicationInstances(prev => ({
        ...prev,
        [appId]: instances
      }));
      
      // Also update by seed_key if available for consistency
      const seedApp = instances.find(inst => inst.is_seed_app) || instances[0];
      if (seedApp?.seed_key) {
        setApplicationInstances(prev => ({
          ...prev,
          [seedApp.seed_key]: instances
        }));
      }
      
      return instances;
    } catch (error) {
      console.error('Error fetching instances:', error);
      return [];
    }
  };

  const handleManageSubscriptions = (app) => {
    // Get subscription for this app
    const subscription = subscriptions[app.app_id];
    if (subscription) {
      setSelectedApp(app);
      setSelectedSubscription(subscription);
      setShowConnectionModal(true);
    } else {
      // No subscription yet, create one
      handleSubscribe(app);
    }
  };

  const handleCreateInstance = async (app) => {
    // For single instance apps, we need to fetch or create the instances array
    if (!app._instances || app._instances.length === 0) {
      // Single instance - create instances array with just this app
      app._instances = [app];
      app._instanceCount = 1;
    }
    
    // Set the app and open the instance modal
    setSelectedApp(app);
    setApplicationInstances(prev => ({
      ...prev,
      [app.app_id]: app._instances
    }));
    setShowInstanceModal(true);
  };

  const handleMultiInstanceClick = async (app) => {
    // Set the selected app
    setSelectedApp(app);
    
    // If we already have instances from grouping, use those
    if (app._instances && app._instances.length > 0) {
      setApplicationInstances(prev => ({
        ...prev,
        [app.app_id]: app._instances
      }));
    } else if (!applicationInstances[app.app_id]) {
      // Otherwise fetch instances
      await fetchApplicationInstances(app.app_id);
    }
    
    // Open the instance management modal
    setShowInstanceModal(true);
  };

  const handleInstanceConnect = (instance, subscription) => {
    setSelectedApp(instance);
    setSelectedSubscription(subscription);
    setShowInstanceModal(false);
    setShowConnectionModal(true);
  };

  const handleInstanceDisconnect = async (subscriptionId) => {
    await handleUnsubscribe(subscriptionId);
    // Refresh instances
    if (selectedApp) {
      await fetchApplicationInstances(selectedApp.app_id);
    }
  };

  const refreshInstances = async () => {
    // Refresh the main applications list first
    await fetchApplications();
    await fetchSubscriptions();
    
    if (selectedApp) {
      // Determine the correct app ID to fetch instances for
      // Always use the seed app ID for fetching instances
      let seedAppId = selectedApp.app_id;
      
      if (!selectedApp.is_seed_app && selectedApp.parent_seed_app_id) {
        seedAppId = selectedApp.parent_seed_app_id;
      }
      
      // Fetch the latest instances for the seed app
      const instances = await fetchApplicationInstances(seedAppId);
      
      // Update the applicationInstances state immediately for the modal
      // This ensures the modal gets the fresh data right away
      setApplicationInstances(prev => {
        const newState = { ...prev };
        
        // Update all possible keys that might reference these instances
        newState[seedAppId] = instances;
        
        // Also update for each instance's app_id
        instances.forEach(inst => {
          newState[inst.app_id] = instances;
        });
        
        // If we have a seed_key, update that too
        const seedInstance = instances.find(inst => inst.is_seed_app) || instances[0];
        if (seedInstance?.seed_key) {
          newState[seedInstance.seed_key] = instances;
        }
        
        return newState;
      });
      
      // Update the selected app's instances
      setSelectedApp(prev => {
        // Find the updated version of the selected app from the instances
        const updatedSelectedApp = instances.find(inst => inst.app_id === prev.app_id) || prev;
        
        return {
          ...updatedSelectedApp,
          _instances: instances,
          _instanceCount: instances.length
        };
      });
      
      // Find and update the app in the main applications list
      setApplications(prevApps => 
        prevApps.map(app => {
          // Check if this app is related to our instances
          const isRelated = instances.some(inst => 
            inst.app_id === app.app_id || 
            (inst.seed_key && inst.seed_key === app.seed_key)
          );
          
          if (isRelated) {
            return {
              ...app,
              _instances: instances,
              _instanceCount: instances.length,
              total_instances: instances.filter(inst => !inst.is_seed_app).length + 1
            };
          }
          return app;
        })
      );
    }
  };

  const handleConnectionSuccess = async (needsOAuth = false, newSubscription = null) => {
    setShowConnectionModal(false);
    await fetchSubscriptions();
    
    // If OAuth is needed, open the connection settings modal with the new subscription
    if (needsOAuth && newSubscription && selectedApp) {
      setTimeout(() => {
        setSelectedSubscription(newSubscription);
        setShowConnectionModal(true);
      }, 500);
    } else {
      setSelectedApp(null);
      setSelectedSubscription(null);
    }
  };

  const handleUnsubscribe = async (subscriptionId) => {
    if (!window.confirm('Are you sure you want to unsubscribe?')) return;
    
    try {
      const token = localStorage.getItem('access_token');
      await axios.delete(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${subscriptionId}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      fetchSubscriptions();
      showSuccessToast('Successfully unsubscribed!');
    } catch (err) {
      const errorMessage = getFullErrorMessage(err, 'Failed to unsubscribe from application');
      showErrorToast(errorMessage);
    }
  };

  const handleDeleteApplication = async (appId) => {
    if (!window.confirm('Are you sure you want to delete this application? This action cannot be undone.')) return;
    
    try {
      const token = localStorage.getItem('access_token');
      await axios.delete(
        `${API_BASE_URL}/api/v1/applications/${appId}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      showSuccessToast('Application deleted successfully');
      fetchApplications();
    } catch (err) {
      const errorMessage = getFullErrorMessage(err, 'Failed to delete application');
      showErrorToast(errorMessage);
    }
  };

  const handleDuplicateApplication = async (appId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/${appId}/duplicate`,
        {},
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      showSuccessToast(`Application duplicated successfully as "${response.data.app_name}"`);
      fetchApplications();
    } catch (err) {
      const errorMessage = getFullErrorMessage(err, 'Failed to duplicate application');
      showErrorToast(errorMessage);
    }
  };

  // Group applications by seed_key to combine instances
  const groupedApplications = applications.reduce((groups, app) => {
    // Determine the grouping key
    let groupKey;
    if (app.seed_key) {
      // Use seed_key for seed applications
      groupKey = app.seed_key;
    } else if (app.parent_seed_app_id) {
      // For instances without seed_key, group by parent
      groupKey = `parent_${app.parent_seed_app_id}`;
    } else {
      // Standalone app without seed or parent
      groupKey = `standalone_${app.app_id}`;
    }
    
    if (!groups[groupKey]) {
      groups[groupKey] = {
        primary: null,
        instances: []
      };
    }
    
    // Determine which app should be primary (shown on top)
    if (app.is_seed_app || (!groups[groupKey].primary || app.instance_number === 1)) {
      groups[groupKey].primary = app;
    }
    
    // Add to instances list
    groups[groupKey].instances.push(app);
    
    return groups;
  }, {});

  // Convert grouped applications to array, using primary app with instance info
  const consolidatedApplications = Object.values(groupedApplications).map(group => {
    const primaryApp = { ...group.primary };
    
    // Add instance information
    primaryApp._instanceCount = group.instances.length;
    primaryApp._instances = group.instances;
    
    // Update total_instances to reflect actual count
    if (primaryApp._instanceCount > 1) {
      primaryApp.total_instances = primaryApp._instanceCount - 1;
    }
    
    return primaryApp;
  });

  const filteredApplications = consolidatedApplications.filter(app => {
    // Check if any instance is subscribed
    const hasSubscription = app._instances 
      ? app._instances.some(inst => subscriptions[inst.app_id])
      : subscriptions[app.app_id];
    
    const matchesFilter = filter === 'all' || 
      (filter === 'subscribed' && hasSubscription) ||
      (filter === 'available' && !hasSubscription);
    
    const matchesCategory = selectedCategory === 'all' || app.category === selectedCategory;
    
    return matchesFilter && matchesCategory;
  });

  const categories = ['all', ...new Set(applications.map(app => app.category).filter(Boolean))];

  const getAppIcon = (app) => {
    if (app.icon_url) {
      return <img src={app.icon_url} alt={app.app_name} className="w-12 h-12 object-contain" />;
    }
    
    // Default icons based on category
    const iconClass = "w-12 h-12 text-gray-400";
    switch (app.category) {
      case 'Communication':
        return <BoltIcon className={iconClass} />;
      case 'Productivity':
        return <CogIcon className={iconClass} />;
      case 'Database':
        return <CircleStackIcon className={iconClass} />;
      default:
        return <LinkIcon className={iconClass} />;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">{error}</p>
      </div>
    );
  }

  return (
    <div className="py-6">
      <div className="w-full px-4 sm:px-6 lg:px-8">
        <div className="sm:flex sm:items-center">
          <div className="sm:flex-auto">
            <h1 className="text-2xl font-semibold text-gray-900">Applications</h1>
            <p className="mt-2 text-sm text-gray-700">
              Connect and manage integrations with external applications
            </p>
          </div>
          {canManageApps && (
            <div className="mt-4 sm:mt-0 sm:ml-16 sm:flex-none">
              <Link
                to="/applications/new"
                className="inline-flex items-center justify-center rounded-md border border-transparent bg-gradient-primary px-4 py-2 text-sm font-medium text-white shadow-sm hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 sm:w-auto transition-all"
              >
                <PlusIcon className="-ml-1 mr-2 h-5 w-5" aria-hidden="true" />
                New Application
              </Link>
            </div>
          )}
        </div>

        {/* Filters and Sort */}
        <div className="mt-6 space-y-4">
          {/* Search and Filter Row */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="search" className="sr-only">
                Search
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
                </div>
                <input
                  type="text"
                  name="search"
                  id="search"
                  className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-primary focus:border-primary sm:text-sm"
                  placeholder="Search by ID, name, category, or description..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            <div>
              <select
                className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm rounded-md"
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
              >
                {categories.map(cat => (
                  <option key={cat} value={cat}>
                    {cat === 'all' ? 'All Categories' : cat}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <select
                className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm rounded-md"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="all">All Applications</option>
                <option value="subscribed">Subscribed</option>
                <option value="available">Available</option>
              </select>
            </div>
          </div>

          {/* Clear Filters and Sort Controls */}
          <div className="flex justify-between items-center">
            {/* Clear Filters Button */}
            {(searchTerm !== '' || filter !== 'all' || selectedCategory !== 'all') && (
              <div className="relative">
                <button
                  onClick={() => {
                    setSearchTerm('');
                    setFilter('all');
                    setSelectedCategory('all');
                    clearPageFilters('applications');
                  }}
                  className="clear-filter-glow inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
                >
                  <XMarkIcon className="h-4 w-4 mr-1.5" />
                  Clear Filters
                  <span className="filter-count-badge">
                    {[
                      searchTerm !== '',
                      filter !== 'all',
                      selectedCategory !== 'all'
                    ].filter(Boolean).length}
                  </span>
                </button>
              </div>
            )}
            
            {/* Sort Controls */}
            <div className="flex gap-2 ml-auto">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="block rounded-md border-gray-300 py-2 pl-3 pr-10 text-base focus:border-primary focus:outline-none focus:ring-primary sm:text-sm"
            >
              <option value="updated_at">Last Modified</option>
              <option value="app_name">Name</option>
              <option value="category">Category</option>
              <option value="created_at">Created Date</option>
            </select>
            
            <button
              type="button"
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="inline-flex items-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              title={sortOrder === 'asc' ? 'Sort descending' : 'Sort ascending'}
            >
              <ChevronUpDownIcon className="h-5 w-5 mr-1" />
              {sortOrder === 'asc' ? 'Asc' : 'Desc'}
            </button>
            </div>
          </div>
        </div>

        {/* Applications Grid */}
        <div className="mt-8 grid gap-6" style={{
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))'
        }}>
          {filteredApplications.map((app) => {
            // Get subscription for the primary instance
            const subscription = subscriptions[app.app_id];
            const isSubscribed = !!subscription;
            
            // Check if this app has multiple instances or can have instances
            const hasMultipleInstances = app._instanceCount > 1;
            const canHaveInstances = app.seed_key || app.is_seed_app;
            const instanceCount = app._instanceCount || 1;
            
            return (
              <div key={app.seed_key || app.app_id} className="relative">
                {/* Show overlapping cards effect for multiple instances */}
                {hasMultipleInstances && (
                  <>
                    {/* Background cards to show stacking effect */}
                    {instanceCount >= 3 && (
                      <div className="absolute inset-0 translate-x-4 translate-y-4 bg-white rounded-lg border border-gray-200 opacity-40" />
                    )}
                    {instanceCount >= 2 && (
                      <div className="absolute inset-0 translate-x-2 translate-y-2 bg-white rounded-lg border border-gray-200 opacity-60" />
                    )}
                  </>
                )}

                {/* Main card */}
                <div
                  className={`relative bg-white border border-gray-200 rounded-lg shadow-sm transition-all ${
                    (hasMultipleInstances || canHaveInstances)
                      ? 'cursor-pointer hover:shadow-lg hover:-translate-y-0.5'
                      : 'hover:shadow-md'
                  }`}
                  onClick={() => {
                    // If it has multiple instances or can have instances, open instance modal
                    if (hasMultipleInstances) {
                      handleMultiInstanceClick(app);
                    } else if (canHaveInstances) {
                      handleCreateInstance(app);
                    }
                  }}
                >
                <div className="p-6">
                  {/* Header Section */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-3 min-w-0 flex-1">
                      {getAppIcon(app)}
                      <div className="min-w-0 flex-1">
                        <h3 className="text-base font-medium text-gray-900 truncate" title={app.app_name}>
                          {app.app_name}
                        </h3>
                        <p className="text-xs text-gray-500">{app.category}</p>
                      </div>
                    </div>

                    {/* 3-dot menu for non-seed applications */}
                    {!app.is_seed_app && app.app_scope !== 'global' && (
                      <div className="relative dropdown-menu ml-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenDropdownId(openDropdownId === app.app_id ? null : app.app_id);
                          }}
                          className="p-1 rounded-md hover:bg-gray-100 transition-colors"
                          title="More options"
                        >
                          <EllipsisVerticalIcon className="h-4 w-4 text-gray-500" />
                        </button>

                        {openDropdownId === app.app_id && (
                          <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg ring-1 ring-black ring-opacity-5 z-10">
                            <div className="py-1" role="menu">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenDropdownId(null);
                                  handleDuplicateApplication(app.app_id);
                                }}
                                className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 text-left"
                                role="menuitem"
                              >
                                <DocumentDuplicateIcon className="h-4 w-4 mr-2 text-gray-500" />
                                Duplicate
                              </button>

                              {!isSubscribed && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setOpenDropdownId(null);
                                    handleDeleteApplication(app.app_id);
                                  }}
                                  className="flex items-center w-full px-4 py-2 text-sm text-red-700 hover:bg-red-50 text-left"
                                  role="menuitem"
                                >
                                  <TrashIcon className="h-4 w-4 mr-2 text-red-500" />
                                  Delete
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Description */}
                  <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                    {app.description}
                  </p>

                  {/* Tags Section */}
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      app.app_type === 'global'
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-green-100 text-green-800'
                    }`}>
                      {app.app_type}
                    </span>

                    {/* Billing Mode Indicator */}
                    {app.billing_mode && (
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        app.billing_mode === 'free'
                          ? 'bg-green-100 text-green-800'
                          : app.billing_mode === 'prepaid'
                          ? 'bg-yellow-100 text-yellow-800'
                          : app.billing_mode === 'postpaid'
                          ? 'bg-purple-100 text-purple-800'
                          : app.billing_mode === 'subscription'
                          ? 'bg-primary-10 text-primary'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {app.billing_mode === 'free' ? '✓ Free' : (app.billing_mode ? app.billing_mode.charAt(0).toUpperCase() + app.billing_mode.slice(1) : 'Pay-per-use')}
                      </span>
                    )}
                    {hasMultipleInstances && (
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800"
                        title="Click card to manage instances"
                      >
                        {instanceCount} instances
                      </span>
                    )}
                    {!hasMultipleInstances && canHaveInstances && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCreateInstance(app);
                        }}
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 hover:bg-purple-200 transition-colors"
                        title="Create additional instance"
                      >
                        <PlusIcon className="mr-1 h-3 w-3" />
                        Add Instance
                      </button>
                    )}
                  </div>

                  {/* Auth Info and Status */}
                  <div className="text-xs text-gray-500 mb-3">
                    Auth: {app.auth_type} • v{app.version}
                  </div>

                  {/* Connection Status Section */}
                  <div className="flex items-center justify-between mb-3">
                    {isSubscribed ? (
                      <>
                        <div className="flex items-center space-x-1.5">
                          {(() => {
                            const authCreds = subscription.auth_credentials || {};

                            if (!authCreds.has_credentials) {
                              return (
                                <>
                                  <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500" />
                                  <span className="text-xs text-yellow-600">Setup Required</span>
                                </>
                              );
                            }

                            if (app.auth_type === 'oauth2') {
                              if (authCreds.access_token === false || !authCreds.access_token) {
                                return (
                                  <>
                                    <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500" />
                                    <span className="text-xs text-yellow-600">Auth Required</span>
                                  </>
                                );
                              }
                              return <span className="text-xs text-green-600">Connected</span>;
                            }

                            return <span className="text-xs text-green-600">Connected</span>;
                          })()}
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedApp(app);
                              setSelectedSubscription(subscription);
                              setShowConnectionModal(true);
                            }}
                            className="text-gray-600 hover:text-gray-800"
                            title="Connection settings"
                          >
                            <Cog6ToothIcon className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleUnsubscribe(subscription.subscription_id);
                            }}
                            className="text-xs text-red-600 hover:text-red-800"
                          >
                            Disconnect
                          </button>
                        </div>
                      </>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSubscribe(app);
                        }}
                        className="w-full inline-flex justify-center items-center px-3 py-1.5 border border-transparent text-xs font-medium rounded-md text-primary bg-primary-10 hover:bg-primary-20 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
                      >
                        Connect
                      </button>
                    )}
                  </div>

                  {/* View Details Link */}
                  <div className="pt-3 border-t border-gray-200">
                    <Link
                      to={`/applications/${app.app_id}`}
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center text-sm text-primary hover:text-secondary"
                    >
                      View Details
                      <ChevronRightIcon className="ml-1 h-4 w-4" />
                    </Link>
                  </div>
                </div>
              </div>
              </div>
            );
          })}
        </div>

        {filteredApplications.length === 0 && (
          <div className="text-center py-12">
            <LinkIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No applications found</h3>
            <p className="mt-1 text-sm text-gray-500">
              Try adjusting your search or filter criteria
            </p>
          </div>
        )}
      </div>
      
      {/* Connection Modal - Unified for all connection operations */}
      {showConnectionModal && selectedApp && (
        <ConnectionModal
          application={selectedApp}
          subscription={selectedSubscription}
          onClose={() => {
            setShowConnectionModal(false);
            setSelectedApp(null);
            setSelectedSubscription(null);
          }}
          onSuccess={handleConnectionSuccess}
        />
      )}

      {/* Instance Management Modal */}
      {showInstanceModal && selectedApp && (
        <InstanceManagementModal
          isOpen={showInstanceModal}
          onClose={() => {
            setShowInstanceModal(false);
          }}
          application={selectedApp}
          instances={(() => {
            // Get instances using multiple fallback methods to ensure we always have the latest data
            const seedAppId = selectedApp.is_seed_app ? selectedApp.app_id : selectedApp.parent_seed_app_id;
            return applicationInstances[seedAppId] || 
                   applicationInstances[selectedApp.app_id] || 
                   selectedApp._instances || 
                   [];
          })()}
          subscriptions={subscriptions}
          onConnect={handleInstanceConnect}
          onDisconnect={handleInstanceDisconnect}
          onRefresh={refreshInstances}
        />
      )}

      {/* Auth Debug Modal */}
      {showAuthDebugModal && selectedApp && selectedSubscription && (
        <AuthDebugModal
          application={selectedApp}
          subscription={selectedSubscription}
          onClose={() => {
            setShowAuthDebugModal(false);
            setSelectedApp(null);
            setSelectedSubscription(null);
          }}
        />
      )}

      {/* Test Auth Flow Modal */}
      {showTestAuthFlow && selectedSubscription && (
        <TestAuthFlow
          subscription={selectedSubscription}
          onClose={() => {
            setShowTestAuthFlow(false);
            setSelectedSubscription(null);
          }}
        />
      )}
    </div>
  );
}

export default Applications;