import React from 'react';

export default function ResultDisplayConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Result Display</h3>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Results"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Layout */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Layout</label>
        <select
          value={config.layout || 'card'}
          onChange={(e) => onChange({ ...config, layout: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        >
          <option value="card">Card</option>
          <option value="full">Full Width</option>
        </select>
      </div>

      {/* Show Timestamp */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={config.showTimestamp !== false}
            onChange={(e) => onChange({ ...config, showTimestamp: e.target.checked })}
            className="rounded border-gray-300 text-primary focus:ring-primary"
          />
          Show Timestamp
        </label>
      </div>

      {/* Empty Message */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Empty Message</label>
        <textarea
          value={config.emptyMessage || ''}
          onChange={(e) => onChange({ ...config, emptyMessage: e.target.value })}
          placeholder="No results to display yet."
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>
    </div>
  );
}
