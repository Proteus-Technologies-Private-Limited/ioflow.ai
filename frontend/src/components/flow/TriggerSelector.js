import React, { useState, useEffect, useMemo } from 'react';
import ReactDOM from 'react-dom';
import {
  MagnifyingGlassIcon,
  ClockIcon,
  StarIcon,
  XMarkIcon,
  ChevronRightIcon,
  BoltIcon,
  CubeIcon,
  CalendarIcon,
  GlobeAltIcon,
  CursorArrowRaysIcon,
  CommandLineIcon,
  FolderIcon,
  ChatBubbleLeftRightIcon,
  SignalIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';

const TriggerSelector = ({
  applications = [],
  events = [],
  selectedTriggerType,
  selectedAppId,
  selectedEventId,
  onTriggerTypeSelect,
  onApplicationSelect,
  onEventSelect,
  loadingEvents = false,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('trigger-type'); // 'trigger-type', 'application', 'event'
  const [favorites, setFavorites] = useState({ triggers: [], applications: [], events: [] });
  const [recentlyUsed, setRecentlyUsed] = useState({ triggers: [], applications: [], events: [] });
  // Trigger types
  const triggerTypes = [
    { 
      id: 'manual', 
      name: 'Manual', 
      description: 'Trigger the flow manually with custom inputs',
      icon: <CursorArrowRaysIcon className="w-5 h-5" />
    },
    { 
      id: 'event', 
      name: 'Application Event', 
      description: 'Trigger when an event occurs in an application',
      icon: <BoltIcon className="w-5 h-5" />
    },
    { 
      id: 'webhook', 
      name: 'Webhook', 
      description: 'Trigger when a webhook is received',
      icon: <GlobeAltIcon className="w-5 h-5" />
    },
    { 
      id: 'schedule', 
      name: 'Schedule', 
      description: 'Trigger on a recurring schedule',
      icon: <CalendarIcon className="w-5 h-5" />
    },
    {
      id: 'file_change',
      name: 'File Change',
      description: 'Trigger when files are created, modified, or deleted',
      icon: <FolderIcon className="w-5 h-5" />
    },
    {
      id: 'mqtt',
      name: 'MQTT',
      description: 'Trigger when a message is published to an MQTT topic',
      icon: <SignalIcon className="w-5 h-5" />
    },
    {
      id: 'api_call',
      name: 'API Call',
      description: 'Trigger via API endpoint',
      icon: <CommandLineIcon className="w-5 h-5" />
    },
    {
      id: 'chat_input',
      name: 'Chat Input',
      description: 'Chat-based trigger for conversational flows with AI agents',
      icon: <ChatBubbleLeftRightIcon className="w-5 h-5" />
    },
  ];

  // Load favorites and recently used from localStorage
  useEffect(() => {
    const savedFavorites = localStorage.getItem('triggerSelectorFavorites');
    const savedRecent = localStorage.getItem('triggerSelectorRecent');

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
    localStorage.setItem('triggerSelectorRecent', JSON.stringify(newRecent));
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
    localStorage.setItem('triggerSelectorFavorites', JSON.stringify(newFavorites));
  };

  // Get frequently used items
  const getFrequentlyUsed = (type, items) => {
    const favIds = favorites[type] || [];
    const recentIds = (recentlyUsed[type] || []).map(r => r.id);
    
    // Combine favorites and recent (favorites first)
    const frequentIds = [...new Set([...favIds, ...recentIds])].slice(0, 5);
    
    if (type === 'triggers') {
      return items.filter(item => frequentIds.includes(item.id));
    } else if (type === 'applications') {
      return items.filter(item => frequentIds.includes(item.app_id));
    } else {
      return items.filter(item => frequentIds.includes(item.event_id));
    }
  };

  // Filter items based on search
  const filteredTriggerTypes = useMemo(() => {
    if (!searchTerm) return triggerTypes;
    const term = searchTerm.toLowerCase();
    return triggerTypes.filter(trigger => 
      trigger.name.toLowerCase().includes(term) ||
      trigger.description.toLowerCase().includes(term)
    );
  }, [searchTerm]);

  const filteredApplications = useMemo(() => {
    if (!searchTerm) return applications;
    const term = searchTerm.toLowerCase();
    return applications.filter(app => 
      app.app_name.toLowerCase().includes(term) ||
      (app.description && app.description.toLowerCase().includes(term))
    );
  }, [applications, searchTerm]);

  const filteredEvents = useMemo(() => {
    if (!searchTerm) return events;
    const term = searchTerm.toLowerCase();
    return events.filter(event => 
      event.event_name.toLowerCase().includes(term) ||
      (event.description && event.description.toLowerCase().includes(term))
    );
  }, [events, searchTerm]);

  // Get selected items
  const selectedTrigger = triggerTypes.find(t => t.id === selectedTriggerType);
  const selectedApp = applications.find(app => app.app_id === selectedAppId);
  const selectedEvent = events.find(event => event.event_id === selectedEventId);

  const frequentTriggers = getFrequentlyUsed('triggers', triggerTypes);
  const frequentApps = getFrequentlyUsed('applications', applications);
  const frequentEvents = getFrequentlyUsed('events', events);

  const handleTriggerTypeSelect = (triggerId) => {
    onTriggerTypeSelect(triggerId);
    trackUsage('triggers', triggerId);
    if (triggerId === 'event' || triggerId === 'application_event') {
      setActiveTab('application');
    } else {
      setIsOpen(false);
    }
    setSearchTerm('');
  };

  const handleApplicationSelect = (appId) => {
    onApplicationSelect(appId);
    trackUsage('applications', appId);
    setActiveTab('event');
    setSearchTerm('');
  };

  const handleEventSelect = (eventId) => {
    onEventSelect(eventId);
    trackUsage('events', eventId);
    setIsOpen(false);
    setSearchTerm('');
  };

  const renderTriggerItem = (trigger, isFrequent = false) => {
    const isFavorite = (favorites.triggers || []).includes(trigger.id);
    
    return (
      <div
        key={trigger.id}
        className={`flex items-center justify-between p-3 hover:bg-gray-50 cursor-pointer rounded-lg transition-colors ${
          selectedTriggerType === trigger.id ? 'bg-blue-50 border-blue-200 border' : ''
        }`}
        onClick={() => handleTriggerTypeSelect(trigger.id)}
      >
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          <div className="text-gray-400 flex-shrink-0">{trigger.icon}</div>
          <div className="min-w-0 flex-1">
            <div className="font-medium text-gray-900">{trigger.name}</div>
            <div className="text-sm text-gray-500">{trigger.description}</div>
          </div>
          {isFrequent && <ClockIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleFavorite('triggers', trigger.id);
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
          <CubeIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
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

  const renderEventItem = (event, isFrequent = false) => {
    const isFavorite = (favorites.events || []).includes(event.event_id);
    
    // Extract parameter mappings if available - handle both webhook and API events
    let parameterMappings = {};
    let hasParameterMappings = false;
    
    if (event.event_type === 'webhook') {
      // For webhook events, use extraction_configuration.path_mappings
      const extractionConfig = event.extraction_configuration || {};
      parameterMappings = extractionConfig.path_mappings || {};
    } else if (event.event_type === 'api_call') {
      // For API events, use output_schema.properties or parameter_extraction.mappings
      const outputSchema = event.output_schema || {};
      if (outputSchema.parameter_extraction && outputSchema.parameter_extraction.mappings) {
        parameterMappings = outputSchema.parameter_extraction.mappings;
      } else if (outputSchema.properties) {
        // Convert properties to parameter mappings for display
        parameterMappings = {};
        Object.entries(outputSchema.properties).forEach(([key, value]) => {
          if (value.mapping && value.mapping !== 'N/A') {
            parameterMappings[key] = value.mapping;
          } else {
            // For API events, show the property name itself as the mapping
            parameterMappings[key] = `$.${key}`;
          }
        });
      }
    }
    
    hasParameterMappings = Object.keys(parameterMappings).length > 0;
    
    return (
      <div
        key={event.event_id}
        className={`p-3 hover:bg-gray-50 cursor-pointer rounded-lg transition-colors ${
          selectedEventId === event.event_id ? 'bg-blue-50 border-blue-200 border' : ''
        }`}
        onClick={() => handleEventSelect(event.event_id)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3 flex-1 min-w-0">
            <BoltIcon className="w-5 h-5 text-gray-400 flex-shrink-0" />
            <div className="min-w-0 flex-1">
              <div className="font-medium text-gray-900 truncate">{event.event_name}</div>
              {event.description && (
                <div className="text-sm text-gray-500 truncate">{event.description}</div>
              )}
              {hasParameterMappings && (
                <div className="text-xs text-blue-600 mt-1">
                  📋 {Object.keys(parameterMappings).length} parameter mappings available
                </div>
              )}
            </div>
            {isFrequent && <ClockIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />}
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleFavorite('events', event.event_id);
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
        
        {/* Show parameter mappings when selected */}
        {selectedEventId === event.event_id && hasParameterMappings && (
          <div className="mt-3 pt-3 border-t border-blue-200">
            <div className="text-xs font-medium text-blue-700 mb-2">
              Available Parameters:
            </div>
            <div className="grid grid-cols-1 gap-1">
              {Object.entries(parameterMappings).slice(0, 6).map(([param, jsonPath]) => (
                <div key={param} className="flex justify-between text-xs">
                  <span className="font-medium text-gray-700 truncate">{param}:</span>
                  <span className="text-gray-500 truncate ml-2" title={jsonPath}>
                    {jsonPath}
                  </span>
                </div>
              ))}
              {Object.keys(parameterMappings).length > 6 && (
                <div className="text-xs text-blue-600 text-center mt-1">
                  +{Object.keys(parameterMappings).length - 6} more parameters
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  // Get display text for button
  const getButtonText = () => {
    if ((selectedTriggerType === 'event' || selectedTriggerType === 'application_event') && selectedApp && selectedEvent) {
      return (
        <div>
          <div className="font-medium text-gray-900 truncate">
            {selectedApp.app_name}: {selectedEvent.event_name}
          </div>
          <div className="text-sm text-gray-500">
            Application Event Trigger
          </div>
        </div>
      );
    } else if (selectedTrigger) {
      return (
        <div>
          <div className="font-medium text-gray-900">
            {selectedTrigger.name} Trigger
          </div>
          {(selectedTriggerType === 'event' || selectedTriggerType === 'application_event') && (
            <div className="text-sm text-gray-500">
              {selectedApp ? 'Select an event...' : 'Select an application...'}
            </div>
          )}
        </div>
      );
    }
    return <span className="text-gray-500">Select trigger type...</span>;
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
          <div className="min-w-0 flex-1">
            {getButtonText()}
          </div>
          <ChevronRightIcon className="w-5 h-5 text-gray-400 ml-2 flex-shrink-0" />
        </div>
      </button>

      {/* Selection Panel */}
      {isOpen && ReactDOM.createPortal(
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-gray-500 bg-opacity-75 z-[10000]"
            onClick={() => setIsOpen(false)}
          />

          {/* Panel */}
          <div
            className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-xl z-[10000]">
            {/* Header */}
            <div className="px-6 py-4 border-b">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">
                  Select Trigger
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
                onClick={() => setActiveTab('trigger-type')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'trigger-type'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700'
                }`}
              >
                Trigger Type
                {selectedTriggerType && <span className="ml-1 text-green-600">✓</span>}
              </button>
              {(selectedTriggerType === 'event' || selectedTriggerType === 'application_event') && (
                <>
                  <button
                    onClick={() => setActiveTab('application')}
                    className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'application'
                        ? 'text-blue-600 border-blue-600'
                        : 'text-gray-500 border-transparent hover:text-gray-700'
                    }`}
                  >
                    Application
                    {selectedAppId && <span className="ml-1 text-green-600">✓</span>}
                  </button>
                  <button
                    onClick={() => setActiveTab('event')}
                    className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                      activeTab === 'event'
                        ? 'text-blue-600 border-blue-600'
                        : 'text-gray-500 border-transparent hover:text-gray-700'
                    }`}
                    disabled={!selectedAppId}
                  >
                    Event
                    {selectedEventId && <span className="ml-1 text-green-600">✓</span>}
                  </button>
                </>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto" style={{ height: 'calc(100% - 180px)' }}>
              {activeTab === 'trigger-type' ? (
                <div className="p-4 space-y-4">
                  {/* Frequently Used Triggers */}
                  {frequentTriggers.length > 0 && !searchTerm && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                        <ClockIcon className="w-4 h-4 mr-1" />
                        Frequently Used
                      </h3>
                      <div className="space-y-2">
                        {frequentTriggers.map(trigger => renderTriggerItem(trigger, true))}
                      </div>
                    </div>
                  )}

                  {/* All Trigger Types */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">
                      {searchTerm ? 'Search Results' : 'All Trigger Types'}
                    </h3>
                    <div className="space-y-2">
                      {filteredTriggerTypes.length > 0 ? (
                        filteredTriggerTypes.map(trigger => renderTriggerItem(trigger))
                      ) : (
                        <p className="text-gray-500 text-center py-8">
                          No trigger types found
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ) : activeTab === 'application' ? (
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
                  ) : loadingEvents ? (
                    <p className="text-gray-500 text-center py-8">
                      Loading events...
                    </p>
                  ) : (
                    <>
                      {/* Frequently Used Events */}
                      {frequentEvents.length > 0 && !searchTerm && (
                        <div>
                          <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                            <ClockIcon className="w-4 h-4 mr-1" />
                            Frequently Used
                          </h3>
                          <div className="space-y-2">
                            {frequentEvents.map(event => renderEventItem(event, true))}
                          </div>
                        </div>
                      )}

                      {/* All Events */}
                      <div>
                        <h3 className="text-sm font-medium text-gray-700 mb-2">
                          {searchTerm ? 'Search Results' : 'All Events'}
                        </h3>
                        <div className="space-y-2">
                          {filteredEvents.length > 0 ? (
                            filteredEvents.map(event => renderEventItem(event))
                          ) : (
                            <p className="text-gray-500 text-center py-8">
                              No events found
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
        </>,
        document.body
      )}
    </div>
  );
};

export default TriggerSelector;