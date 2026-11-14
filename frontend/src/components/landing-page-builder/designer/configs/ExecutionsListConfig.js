import React from 'react';

export default function ExecutionsListConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Executions List</h3>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Execution History"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Default Timeframe</label>
          <select
            value={config.defaultTimeframe || '7d'}
            onChange={(e) => onChange({ ...config, defaultTimeframe: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm"
          >
            <option value="1h">Last Hour</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="all">All Time</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Default Status</label>
          <select
            value={config.defaultStatus || 'all'}
            onChange={(e) => onChange({ ...config, defaultStatus: e.target.value })}
            className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm"
          >
            <option value="all">All</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="RUNNING">Running</option>
            <option value="PAUSED">Paused</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 mb-1">Default Scope</label>
        <select
          value={config.defaultScope || 'user'}
          onChange={(e) => onChange({ ...config, defaultScope: e.target.value })}
          className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm"
        >
          <option value="user">My Executions Only</option>
          <option value="all">All Users (Enterprise)</option>
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
          <option value={50}>50</option>
        </select>
      </div>

      <div className="space-y-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={config.showFilters !== false}
            onChange={(e) => onChange({ ...config, showFilters: e.target.checked })}
            className="rounded text-primary focus:ring-primary"
          />
          <span className="text-sm text-gray-700">Show filter controls</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={config.autoRefresh || false}
            onChange={(e) => onChange({ ...config, autoRefresh: e.target.checked })}
            className="rounded text-primary focus:ring-primary"
          />
          <span className="text-sm text-gray-700">Auto-refresh</span>
        </label>
        {config.autoRefresh && (
          <div className="ml-6">
            <label className="block text-xs text-gray-600 mb-1">Interval (seconds)</label>
            <input
              type="number"
              value={config.autoRefreshInterval || 30}
              onChange={(e) => onChange({ ...config, autoRefreshInterval: parseInt(e.target.value) || 30 })}
              min={5}
              max={300}
              className="w-24 px-2 py-1 border border-gray-300 rounded text-sm"
            />
          </div>
        )}
      </div>
    </div>
  );
}
