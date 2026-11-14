import React from 'react';

export default function SpacerBlockConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Spacer</h3>

      {/* Height */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Height (px)</label>
        <div className="flex items-center gap-2">
          <input
            type="number"
            value={config.height || 40}
            onChange={(e) => onChange({ ...config, height: parseInt(e.target.value) || 0 })}
            min={0}
            max={500}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
          <span className="text-sm text-gray-500">px</span>
        </div>
      </div>
    </div>
  );
}
