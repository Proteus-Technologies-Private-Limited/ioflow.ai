import React from 'react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

export default function TaskInboxConfig({ config, onChange, manualVariables }) {
  // Check if flow has HITL nodes (passed via manualVariables context or detected)
  // The block is always configurable but shows a warning if no HITL node is detected

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Task Inbox</h3>

      <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <ExclamationTriangleIcon className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
        <p className="text-xs text-blue-700">
          This block displays Human-in-the-Loop tasks for the current user.
          It requires a Human Review node in your flow and authenticated users to function.
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Task Inbox"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Default Status Filter</label>
        <select
          value={config.defaultStatus || 'PENDING'}
          onChange={(e) => onChange({ ...config, defaultStatus: e.target.value })}
          className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm"
        >
          <option value="pending">Pending</option>
          <option value="completed">Completed</option>
          <option value="expired">Expired</option>
          <option value="all">All</option>
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Page Size</label>
        <select
          value={config.pageSize || 10}
          onChange={(e) => onChange({ ...config, pageSize: parseInt(e.target.value) })}
          className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm"
        >
          <option value={5}>5</option>
          <option value={10}>10</option>
          <option value={25}>25</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={config.showStats !== false}
            onChange={(e) => onChange({ ...config, showStats: e.target.checked })}
            className="rounded text-primary focus:ring-primary"
          />
          <span className="text-sm text-gray-700">Show task statistics</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={config.autoRefresh !== false}
            onChange={(e) => onChange({ ...config, autoRefresh: e.target.checked })}
            className="rounded text-primary focus:ring-primary"
          />
          <span className="text-sm text-gray-700">Auto-refresh</span>
        </label>
        {config.autoRefresh !== false && (
          <div className="ml-6">
            <label className="block text-xs text-gray-600 mb-1">Interval (seconds)</label>
            <input
              type="number"
              value={config.autoRefreshInterval || 15}
              onChange={(e) => onChange({ ...config, autoRefreshInterval: parseInt(e.target.value) || 15 })}
              min={5}
              max={120}
              className="w-24 px-2 py-1 border border-gray-300 rounded text-sm"
            />
          </div>
        )}
      </div>
    </div>
  );
}
