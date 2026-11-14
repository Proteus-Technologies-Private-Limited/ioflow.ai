import React, { useState, useMemo } from 'react';
import {
  MagnifyingGlassIcon,
  ClockIcon,
  StarIcon,
  XMarkIcon,
  ChevronRightIcon,
  BellAlertIcon,
} from '@heroicons/react/24/outline';
import { StarIcon as StarIconSolid } from '@heroicons/react/24/solid';
import { getIconForCategory } from '../../plugins/IconRegistry';

const ApplicationEventSelector = ({
  applications = [],
  events = [],
  selectedAppId,
  selectedEventId,
  selectedEventName,
  onApplicationSelect,
  onEventSelect,
  loadingEvents = false,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('applications');
  const [favorites, setFavorites] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('appEventFavorites') || '{}');
    } catch { return {}; }
  });
  const [recentlyUsed, setRecentlyUsed] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('appEventRecent') || '{}');
    } catch { return {}; }
  });

  const getAppIcon = (app, cls = "w-5 h-5 text-gray-400 flex-shrink-0") => {
    if (app.icon_url || app.app_icon) {
      const IconComponent = getIconForCategory(app.app_type, app.category);
      return (
        <>
          <img
            src={app.icon_url || app.app_icon}
            alt={app.app_name}
            className="w-5 h-5 object-contain flex-shrink-0"
            onError={(e) => {
              e.target.style.display = 'none';
              const fallback = e.target.nextElementSibling;
              if (fallback) fallback.style.display = 'block';
            }}
          />
          <IconComponent className={cls} style={{ display: 'none' }} />
        </>
      );
    }
    const IconComponent = getIconForCategory(app.app_type, app.category);
    return <IconComponent className={cls} />;
  };

  const trackUsage = (type, id) => {
    const newRecent = { ...recentlyUsed };
    const recentList = newRecent[type] || [];
    const filtered = recentList.filter(item => item.id !== id);
    newRecent[type] = [{ id, timestamp: Date.now() }, ...filtered].slice(0, 10);
    setRecentlyUsed(newRecent);
    localStorage.setItem('appEventRecent', JSON.stringify(newRecent));
  };

  const toggleFavorite = (type, id) => {
    const newFavorites = { ...favorites };
    const favList = newFavorites[type] || [];
    if (favList.includes(id)) {
      newFavorites[type] = favList.filter(fId => fId !== id);
    } else {
      newFavorites[type] = [...favList, id];
    }
    setFavorites(newFavorites);
    localStorage.setItem('appEventFavorites', JSON.stringify(newFavorites));
  };

  const getFrequentlyUsed = (type, items) => {
    const favIds = favorites[type] || [];
    const recentIds = (recentlyUsed[type] || []).map(r => r.id);
    const frequentIds = [...new Set([...favIds, ...recentIds])].slice(0, 5);
    return items.filter(item => {
      const itemId = type === 'applications' ? item.app_id : (item.event_id || item.event_name);
      return frequentIds.includes(itemId);
    });
  };

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
    return events.filter(ev =>
      (ev.display_name || ev.event_name || '').toLowerCase().includes(term) ||
      (ev.description && ev.description.toLowerCase().includes(term))
    );
  }, [events, searchTerm]);

  const selectedApp = applications.find(app => app.app_id === selectedAppId);
  const selectedEvent = events.find(ev =>
    ev.event_id === selectedEventId || ev.event_name === selectedEventName
  );

  const frequentApps = getFrequentlyUsed('applications', applications);
  const frequentEvents = getFrequentlyUsed('events', events);

  const handleApplicationSelect = (appId) => {
    onApplicationSelect(appId);
    trackUsage('applications', appId);
    setActiveTab('events');
    setSearchTerm('');
  };

  const handleEventSelect = (event) => {
    onEventSelect(event);
    trackUsage('events', event.event_id || event.event_name);
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
          onClick={(e) => { e.stopPropagation(); toggleFavorite('applications', app.app_id); }}
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

  const renderEventItem = (ev, isFrequent = false) => {
    const evId = ev.event_id || ev.event_name;
    const isFavorite = (favorites.events || []).includes(evId);
    const isSelected = selectedEventId === ev.event_id || selectedEventName === ev.event_name;
    return (
      <div
        key={evId}
        className={`flex items-center justify-between p-3 hover:bg-gray-50 cursor-pointer rounded-lg transition-colors ${
          isSelected ? 'bg-amber-50 border-amber-200 border' : ''
        }`}
        onClick={() => handleEventSelect(ev)}
      >
        <div className="flex items-center space-x-3 flex-1 min-w-0">
          <BellAlertIcon className="w-5 h-5 text-amber-500 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="font-medium text-gray-900 truncate">{ev.display_name || ev.event_name}</div>
            {ev.description && (
              <div className="text-sm text-gray-500 truncate">{ev.description}</div>
            )}
            <div className="text-xs text-gray-400 mt-1">
              Type: {ev.event_type || 'event'}
            </div>
          </div>
          {isFrequent && <ClockIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />}
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); toggleFavorite('events', evId); }}
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
        className="w-full px-4 py-2 text-left bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
      >
        <div className="flex items-center justify-between">
          <div className="min-w-0 flex-1 flex items-center space-x-3">
            {selectedApp && (
              <div className="flex-shrink-0">
                {getAppIcon(selectedApp)}
              </div>
            )}
            <div className="min-w-0 flex-1">
              {selectedApp && selectedEvent ? (
                <div>
                  <div className="font-medium text-gray-900 truncate">
                    {selectedApp.app_name}
                  </div>
                  <div className="text-sm text-gray-500 truncate">
                    {selectedEvent.display_name || selectedEvent.event_name}
                  </div>
                </div>
              ) : selectedApp ? (
                <div>
                  <div className="font-medium text-gray-900 truncate">
                    {selectedApp.app_name}
                  </div>
                  <div className="text-sm text-gray-500">
                    Select an event...
                  </div>
                </div>
              ) : (
                <span className="text-gray-500">Select application & event...</span>
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
                  Select Application & Event
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
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500"
                />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b">
              <button
                onClick={() => setActiveTab('applications')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'applications'
                    ? 'text-amber-600 border-amber-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700'
                }`}
              >
                Applications
                {selectedAppId && <span className="ml-1 text-green-600">&#10003;</span>}
              </button>
              <button
                onClick={() => setActiveTab('events')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'events'
                    ? 'text-amber-600 border-amber-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700'
                }`}
                disabled={!selectedAppId}
              >
                Events
                {selectedEvent && <span className="ml-1 text-green-600">&#10003;</span>}
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto" style={{ height: 'calc(100% - 180px)' }}>
              {activeTab === 'applications' ? (
                <div className="p-4 space-y-4">
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
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">
                      {searchTerm ? 'Search Results' : 'All Applications'}
                    </h3>
                    <div className="space-y-2">
                      {filteredApplications.length > 0 ? (
                        filteredApplications.map(app => renderApplicationItem(app))
                      ) : (
                        <p className="text-gray-500 text-center py-8">No applications found</p>
                      )}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-4 space-y-4">
                  {!selectedAppId ? (
                    <p className="text-gray-500 text-center py-8">Please select an application first</p>
                  ) : loadingEvents ? (
                    <p className="text-gray-500 text-center py-8">Loading events...</p>
                  ) : (
                    <>
                      {frequentEvents.length > 0 && !searchTerm && (
                        <div>
                          <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center">
                            <ClockIcon className="w-4 h-4 mr-1" />
                            Frequently Used
                          </h3>
                          <div className="space-y-2">
                            {frequentEvents.map(ev => renderEventItem(ev, true))}
                          </div>
                        </div>
                      )}
                      <div>
                        <h3 className="text-sm font-medium text-gray-700 mb-2">
                          {searchTerm ? 'Search Results' : 'All Events'}
                        </h3>
                        <div className="space-y-2">
                          {filteredEvents.length > 0 ? (
                            filteredEvents.map(ev => renderEventItem(ev))
                          ) : (
                            <p className="text-gray-500 text-center py-8">No events found</p>
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

export default ApplicationEventSelector;
