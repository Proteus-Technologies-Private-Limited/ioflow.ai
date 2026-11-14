import React from 'react';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';

export default function PricingBlockConfig({ config, onChange }) {
  const features = config.features || [];

  const addFeature = () => {
    onChange({ ...config, features: [...features, ''] });
  };

  const removeFeature = (index) => {
    const updated = features.filter((_, i) => i !== index);
    onChange({ ...config, features: updated });
  };

  const updateFeature = (index, value) => {
    const updated = features.map((f, i) => (i === index ? value : f));
    onChange({ ...config, features: updated });
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Pricing Block</h3>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Pricing"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Show Billing Preference */}
      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={config.showBillingPreference || false}
            onChange={(e) => onChange({ ...config, showBillingPreference: e.target.checked })}
            className="rounded border-gray-300 text-primary focus:ring-primary"
          />
          Show Billing Preference Toggle
        </label>
      </div>

      {/* Custom Price Text */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Custom Price Text</label>
        <input
          type="text"
          value={config.customPriceText || ''}
          onChange={(e) => onChange({ ...config, customPriceText: e.target.value })}
          placeholder="e.g. Starting at $9/mo"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Features List */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Features ({features.length})
        </label>

        <div className="space-y-2">
          {features.map((feature, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="text"
                value={feature}
                onChange={(e) => updateFeature(index, e.target.value)}
                placeholder="Feature description"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
              />
              <button
                type="button"
                onClick={() => removeFeature(index)}
                className="text-red-500 hover:text-red-700 p-1 shrink-0"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
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
