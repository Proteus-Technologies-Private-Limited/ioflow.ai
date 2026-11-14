import React, { useState, useEffect, useMemo } from 'react';
import {
  MagnifyingGlassIcon,
  ClockIcon,
  StarIcon,
  XMarkIcon,
  ChevronRightIcon,
  CubeIcon,
  CommandLineIcon,
  CircleStackIcon,
  EnvelopeIcon,
  GlobeAltIcon,
  ChatBubbleLeftRightIcon,
  CloudIcon,
  CpuChipIcon,
  DocumentIcon,
  CogIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import { getIconForCategory } from '../../plugins/IconRegistry';

const ApplicationServiceSelector = ({
  applications = [],
  services = [],
  selectedAppId,
  selectedServiceId,
  onApplicationSelect,
  onServiceSelect,
  loadingServices = false,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('applications'); // 'applications' or 'services'
  const [favorites, setFavorites] = useState({ applications: [], services: [] });
  const [recentlyUsed, setRecentlyUsed] = useState({ applications: [], services: [] });

  // Get icon based on app type or category
  const getAppIcon = (app, className = "w-5 h-5 text-gray-400 flex-shrink-0") => {
    // Show custom icon if available, with fallback to category icon
    if (app.icon_url || app.app_icon) {
      const IconComponent = getIconComponent(app);
      return (
        <>
          <img 
            src={app.icon_url || app.app_icon} 
            alt={app.app_name} 
            className="w-5 h-5 object-contain flex-shrink-0"
            onError={(e) => {
              // Hide the broken image and show fallback icon
              e.target.style.display = 'none';
              const fallback = e.target.nextElementSibling;
              if (fallback) fallback.style.display = 'block';
            }}
          />
          <IconComponent className={className} style={{ display: 'none' }} />
        </>
      );
    }
    
    // No icon URL, show category-based icon
    const IconComponent = getIconComponent(app);
    return <IconComponent className={className} />;
  };

  const getIconComponent = (app) => {
    return getIconForCategory(app.app_type, app.category);
  };

  // Load favorites and recently used from localStorage
  useEffect(() => {
    const savedFavorites = localStorage.getItem('appServiceFavorites');
    const savedRecent = localStorage.getItem('appServiceRecent');
    
    if (savedFavorites) {
      setFavorites(JSON.parse(savedFavorites));
    }
    if (savedRecent) {
      setRecentlyUsed(JSON.parse(savedRecent));
    }
  }, []);

  // Track usage
  const trackUsage = (type, id) => {
    const newRecent = { ...recentlyUsed };
    const recentList = newRecent[type] || [];
    
    // Remove if already exists and add to front
    const filtered = recentList.filter(item => item.id !== id);
    const timestamp = Date.now();
    newRecent[type] = [{ id, timestamp }, ...filtered].slice(0, 10); // Keep last 10
    
    setRecentlyUsed(newRecent);
    localStorage.setItem('appServiceRecent', JSON.stringify(newRecent));
  };

  // Toggle favorite
  const toggleFavorite = (type, id) => {
    const newFavorites = { ...favorites };
    const favList = newFavorites[type] || [];
    
    if (favList.includes(id)) {
      newFavorites[type] = favList.filter(fId => fId !== id);
    } else {
      newFavorites[type] = [...favList, id];
    }
    
    setFavorites(newFavorites);
    localStorage.setItem('appServiceFavorites', JSON.stringify(newFavorites));
  };

  // Get frequently used items (combination of favorites and recent)
  const getFrequentlyUsed = (type, items) => {
    const favIds = favorites[type] || [];
    const recentIds = (recentlyUsed[type] || []).map(r => r.id);
    
    // Combine favorites and recent (favorites first)
    const frequentIds = [...new Set([...favIds, ...recentIds])].slice(0, 5);
    
    return items.filter(item => {
      const itemId = type === 'applications' ? item.app_id : item.service_id;
      return frequentIds.includes(itemId);
    });
  };

  // Filter items based on search
  const filteredApplications = useMemo(() => {
    if (!searchTerm) return applications;
    const term = searchTerm.toLowerCase();
    return applications.filter(app => 
      app.app_name.toLowerCase().includes(term) ||
      (app.description && app.description.toLowerCase().includes(term))
    );
  }, [applications, searchTerm]);

  const filteredServices = useMemo(() => {
    if (!searchTerm) return services;
    const term = searchTerm.toLowerCase();
    return services.filter(service => 
      service.display_name.toLowerCase().includes(term) ||
      (service.description && service.description.toLowerCase().includes(term))
    );
  }, [services, searchTerm]);

  // Get selected application and service names
  const selectedApp = applications.find(app => app.app_id === selectedAppId);
  const selectedService = services.find(service => service.service_id === selectedServiceId);

  const frequentApps = getFrequentlyUsed('applications', applications);
  const frequentServices = getFrequentlyUsed('services', services);

  const handleApplicationSelect = (appId) => {
    onApplicationSelect(appId);
    trackUsage('applications', appId);
    setActiveTab('services');
    setSearchTerm('');
  };

  const handleServiceSelect = (serviceId) => {
    onServiceSelect(serviceId);
    trackUsage('services', serviceId);
    setIsOpen(false);
    setSearchTerm('');
  };

  const renderApplicationItem = (app, isFrequent = false) => {
    const isFavorite = (favorites.applications || []).includes(app.app_id);
    
    return (
      <div
        key={app.app_id}
        className={`flex items-center justify-between p-3 hover:bg-gray-50 cursor-pointer rounded-lg transition-colors ${
          selectedAppId === app.app_id ? 'bg-blue-50 border-blue-200 border' : ''
        }`}
        onClick={() => handleApplicationSelect(app.app_id)}
      >
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          {getAppIcon(app)}
          <div className="min-w-0 flex-1">
            <div className="font-medium text-gray-900 truncate">{app.app_name}</div>
            {app.description && (
              <div className="text-sm text-gray-500 truncate">{app.description}</div>
            )}
          </div>
          {isFrequent && <ClockIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleFavorite('applications', app.app_id);
          }}
          className="ml-2 p-1 hover:bg-gray-100 rounded flex-shrink-0"
        >
          {isFavorite ? (
            <StarIconSolid className="w-4 h-4 text-yellow-500" />
          ) : (
            <StarIcon className="w-4 h-4 text-gray-400" />
          )}
        </button>
      </div>
    );
  };

  const renderServiceItem = (service, isFrequent = false) => {
    const isFavorite = (favorites.services || []).includes(service.service_id);
    
    return (
      <div
        key={service.service_id}
        className={`flex items-center justify-between p-3 hover:bg-gray-50 cursor-pointer rounded-lg transition-colors ${
          selectedServiceId === service.service_id ? 'bg-blue-50 border-blue-200 border' : ''
        }`}
        onClick={() => handleServiceSelect(service.service_id)}
      >
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          <CommandLineIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-medium text-gray-900 truncate">{service.display_name}</div>
            {service.description && (
              <div className="text-sm text-gray-500 truncate">{service.description}</div>
            )}
            <div className="text-xs text-gray-400 mt-1">
              Type: {service.service_type}
            </div>
          </div>
          {isFrequent && <ClockIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleFavorite('services', service.service_id);
          }}
          className="ml-2 p-1 hover:bg-gray-100 rounded flex-shrink-0"
        >
          {isFavorite ? (
            <StarIconSolid className="w-4 h-4 text-yellow-500" />
          ) : (
            <StarIcon className="w-4 h-4 text-gray-400" />
          )}
        </button>
      </div>
    );
  };

  return (
    <div className={`relative ${className}`}>
      {/* Main Button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="w-full px-4 py-2 text-left bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        <div className="flex items-center justify-between">
          <div className="min-w-0 flex-1 flex items-center space-x-3">
            {selectedApp && (
              <div className="flex-shrink-0">
                {getAppIcon(selectedApp)}
              </div>
            )}
            <div className="min-w-0 flex-1">
              {selectedApp && selectedService ? (
                <div>
                  <div className="font-medium text-gray-900 truncate">
                    {selectedApp.app_name}
                  </div>
                  <div className="text-sm text-gray-500 truncate">
                    {selectedService.display_name}
                  </div>
                </div>
              ) : selectedApp ? (
                <div>
                  <div className="font-medium text-gray-900 truncate">
                    {selectedApp.app_name}
                  </div>
                  <div className="text-sm text-gray-500">
                    Select a service...
                  </div>
                </div>
              ) : (
                <span className="text-gray-500">Select application & service...</span>
              )}
            </div>
          </div>
          <ChevronRightIcon className="w-5 h-5 text-gray-400 ml-2 flex-shrink-0" />
        </div>
      </button>

      {/* Selection Panel */}
      {isOpen && (
        <div className="fixed inset-0 z-[100] overflow-hidden">
          <div className="absolute inset-0 bg-gray-500 bg-opacity-75" onClick={() => setIsOpen(false)} />
          
          <div className="absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-xl">
            {/* Header */}
            <div className="px-6 py-4 border-b">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Select Application & Service
                </h2>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 hover:bg-gray-100 rounded"
                >
                  <XMarkIcon className="w-5 h-5 text-gray-500" />
                </button>
              </div>
              
              {/* Search */}
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b">
              <button
                onClick={() => setActiveTab('applications')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'applications'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700'
                }`}
              >
                Applications
                {selectedAppId && <span className="ml-1 text-green-600">✓</span>}
              </button>
              <button
                onClick={() => setActiveTab('services')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'services'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700'
                }`}
                disabled={!selectedAppId}
              >
                Services
                {selectedServiceId && <span className="ml-1 text-green-600">✓</span>}
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto" style={{ height: 'calc(100% - 180px)' }}>
              {activeTab === 'applications' ? (
                <div className="p-4 space-y-4">
                  {/* Frequently Used Applications */}
                  {frequentApps.length > 0 && !searchTerm && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                        <ClockIcon className="w-4 h-4 mr-1" />
                        Frequently Used
                      </h3>
                      <div className="space-y-2">
                        {frequentApps.map(app => renderApplicationItem(app, true))}
                      </div>
                    </div>
                  )}

                  {/* All Applications */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">
                      {searchTerm ? 'Search Results' : 'All Applications'}
                    </h3>
                    <div className="space-y-2">
                      {filteredApplications.length > 0 ? (
                        filteredApplications.map(app => renderApplicationItem(app))
                      ) : (
                        <p className="text-gray-500 text-center py-8">
                          No applications found
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 space-y-4">
                  {!selectedAppId ? (
                    <p className="text-gray-500 text-center py-8">
                      Please select an application first
                    </p>
                  ) : loadingServices ? (
                    <p className="text-gray-500 text-center py-8">
                      Loading services...
                    </p>
                  ) : (
                    <>
                      {/* Frequently Used Services */}
                      {frequentServices.length > 0 && !searchTerm && (
                        <div>
                          <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                            <ClockIcon className="w-4 h-4 mr-1" />
                            Frequently Used
                          </h3>
                          <div className="space-y-2">
                            {frequentServices.map(service => renderServiceItem(service, true))}
                          </div>
                        </div>
                      )}

                      {/* All Services */}
                      <div>
                        <h3 className="text-sm font-medium text-gray-700 mb-2">
                          {searchTerm ? 'Search Results' : 'All Services'}
                        </h3>
                        <div className="space-y-2">
                          {filteredServices.length > 0 ? (
                            filteredServices.map(service => renderServiceItem(service))
                          ) : (
                            <p className="text-gray-500 text-center py-8">
                              No services found
                            </p>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ApplicationServiceSelector;