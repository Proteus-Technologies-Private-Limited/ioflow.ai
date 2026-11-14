import React, { useState, useRef, useEffect } from 'react';
import { BellIcon, ClockIcon, HandRaisedIcon } from '@heroicons/react/24/outline';
import { useNavigate } from 'react-router-dom';
import useHITLNotifications from '../../hooks/useHITLNotifications';

const priorityStyles = {
  low: 'border-l-green-400',
  medium: 'border-l-yellow-400',
  high: 'border-l-orange-400',
  critical: 'border-l-red-400',
};

const HITLNotificationBell = () => {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();
  const { pendingCount, urgentCount, latestTasks, refresh } = useHITLNotifications();

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getTimeAgo = (dateStr) => {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'now';
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h`;
    return `${Math.floor(hours / 24)}d`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => {
          setShowDropdown(!showDropdown);
          if (!showDropdown) refresh();
        }}
        className="relative p-2 text-gray-500 hover:text-gray-700 rounded-md hover:bg-gray-100 transition-colors"
        title="Pending Tasks"
      >
        <BellIcon className="w-5 h-5" />
        {pendingCount > 0 && (
          <span className={`absolute -top-0.5 -right-0.5 inline-flex items-center justify-center w-4 h-4 text-[10px] font-bold text-white rounded-full ${
            urgentCount > 0 ? 'bg-red-500' : 'bg-purple-500'
          }`}>
            {pendingCount > 9 ? '9+' : pendingCount}
          </span>
        )}
      </button>

      {showDropdown && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border border-gray-200 z-50">
          <div className="px-4 py-3 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900">Pending Tasks</h3>
              <span className="text-xs text-gray-500">{pendingCount} task{pendingCount !== 1 ? 's' : ''}</span>
            </div>
          </div>

          <div className="max-h-64 overflow-y-auto">
            {latestTasks.length === 0 ? (
              <div className="px-4 py-6 text-center">
                <HandRaisedIcon className="w-8 h-8 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">No pending tasks</p>
              </div>
            ) : (
              latestTasks.map(task => (
                <div
                  key={task.task_id}
                  onClick={() => {
                    setShowDropdown(false);
                    navigate('/tasks');
                  }}
                  className={`px-4 py-3 hover:bg-purple-50 cursor-pointer border-l-2 ${priorityStyles[task.priority] || priorityStyles.medium}`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-800 truncate flex-1">{task.title}</span>
                    <span className="text-[10px] text-gray-400 ml-2 flex-shrink-0">
                      {getTimeAgo(task.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-xs text-gray-500 truncate">{task.flow_name || ''}</span>
                    {task.timeout_at && (
                      <span className="text-[10px] text-gray-400 flex items-center gap-0.5 flex-shrink-0">
                        <ClockIcon className="w-3 h-3" />
                        timeout
                      </span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="px-4 py-2 border-t border-gray-200">
            <button
              onClick={() => {
                setShowDropdown(false);
                navigate('/tasks');
              }}
              className="w-full text-center text-sm text-purple-600 hover:text-purple-800 font-medium py-1"
            >
              View All Tasks
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default HITLNotificationBell;
