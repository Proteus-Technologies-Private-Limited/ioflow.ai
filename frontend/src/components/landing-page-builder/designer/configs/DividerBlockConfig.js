import React from 'react';

export default function DividerBlockConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Divider</h3>

      {/* Color */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
        <input
          type="color"
          value={config.color || '#e5e7eb'}
          onChange={(e) => onChange({ ...config, color: e.target.value })}
          className="w-full h-9 border border-gray-300 rounded-md cursor-pointer"
        />
      </div>

      {/* Margin */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Margin</label>
        <select
          value={config.margin || 'md'}
          onChange={(e) => onChange({ ...config, margin: e.target.value })}
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
