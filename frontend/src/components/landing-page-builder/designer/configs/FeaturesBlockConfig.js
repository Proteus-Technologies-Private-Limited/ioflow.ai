import React from 'react';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';

const AVAILABLE_ICONS = [
  { value: 'bolt', label: 'Bolt' },
  { value: 'shield-check', label: 'Shield Check' },
  { value: 'globe-alt', label: 'Globe' },
  { value: 'clock', label: 'Clock' },
  { value: 'cpu-chip', label: 'CPU Chip' },
  { value: 'lock-closed', label: 'Lock' },
  { value: 'chart-bar', label: 'Chart Bar' },
  { value: 'cog', label: 'Cog' },
  { value: 'star', label: 'Star' },
  { value: 'heart', label: 'Heart' },
  { value: 'rocket-launch', label: 'Rocket' },
  { value: 'check-badge', label: 'Check Badge' },
];

export default function FeaturesBlockConfig({ config, onChange }) {
  const items = config.items || [];

  const addFeature = () => {
    onChange({
      ...config,
      items: [...items, { icon: 'bolt', title: '', description: '' }],
    });
  };

  const removeFeature = (index) => {
    const updated = items.filter((_, i) => i !== index);
    onChange({ ...config, items: updated });
  };

  const updateFeature = (index, field, value) => {
    const updated = items.map((f, i) =>
      i === index ? { ...f, [field]: value } : f
    );
    onChange({ ...config, items: updated });
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Features Block</h3>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Features"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Columns */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Columns</label>
        <select
          value={config.columns || 3}
          onChange={(e) => onChange({ ...config, columns: parseInt(e.target.value) })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        >
          <option value={1}>1</option>
          <option value={2}>2</option>
          <option value={3}>3</option>
          <option value={4}>4</option>
        </select>
      </div>

      {/* Features List */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Features ({items.length})
        </label>

        <div className="space-y-3">
          {items.map((feature, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-medium text-gray-500">Feature {index + 1}</span>
                <button
                  type="button"
                  onClick={() => removeFeature(index)}
                  className="text-red-500 hover:text-red-700 p-1"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-2">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Icon</label>
                  <select
                    value={feature.icon || 'bolt'}
                    onChange={(e) => updateFeature(index, 'icon', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  >
                    {AVAILABLE_ICONS.map((icon) => (
                      <option key={icon.value} value={icon.value}>
                        {icon.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Title</label>
                  <input
                    type="text"
                    value={feature.title || ''}
                    onChange={(e) => updateFeature(index, 'title', e.target.value)}
                    placeholder="Feature title"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Description</label>
                  <textarea
                    value={feature.description || ''}
                    onChange={(e) => updateFeature(index, 'description', e.target.value)}
                    placeholder="Feature description"
                    rows={2}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={addFeature}
          className="mt-2 flex items-center gap-1 px-3 py-2 text-sm text-primary border border-primary/30 rounded-md hover:bg-primary/5 w-full justify-center"
        >
          <PlusIcon className="w-4 h-4" />
          Add Feature
        </button>
      </div>
    </div>
  );
}
