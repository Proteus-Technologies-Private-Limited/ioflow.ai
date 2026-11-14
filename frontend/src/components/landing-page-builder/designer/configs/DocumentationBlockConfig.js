import React from 'react';

export default function DocumentationBlockConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Documentation Block</h3>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Documentation"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Layout */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Layout</label>
        <select
          value={config.layout || 'tabs'}
          onChange={(e) => onChange({ ...config, layout: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        >
          <option value="tabs">Tabs</option>
          <option value="accordion">Accordion</option>
        </select>
      </div>

      {/* Show All Pages */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={config.showAllPages !== false}
            onChange={(e) => onChange({ ...config, showAllPages: e.target.checked })}
            className="rounded border-gray-300 text-primary focus:ring-primary"
          />
          Show All Pages
        </label>
        <p className="mt-1 text-xs text-gray-500">
          When unchecked, specific page selection will be available in a future update.
        </p>
      </div>
    </div>
  );
}
