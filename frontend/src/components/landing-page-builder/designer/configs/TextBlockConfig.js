import React from 'react';

export default function TextBlockConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Text Block</h3>

      {/* HTML Content */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Content</label>
        <textarea
          value={config.content || ''}
          onChange={(e) => onChange({ ...config, content: e.target.value })}
          placeholder="<h2>Your heading</h2><p>Your paragraph text here...</p>"
          rows={8}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary font-mono"
        />
        <p className="mt-1 text-xs text-gray-500">Supports HTML tags for formatting.</p>
      </div>

      {/* Padding */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Padding</label>
        <select
          value={config.padding || 'md'}
          onChange={(e) => onChange({ ...config, padding: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        >
          <option value="sm">Small</option>
          <option value="md">Medium</option>
          <option value="lg">Large</option>
        </select>
      </div>
    </div>
  );
}
