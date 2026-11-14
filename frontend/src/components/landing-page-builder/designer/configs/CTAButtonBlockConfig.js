import React from 'react';

export default function CTAButtonBlockConfig({ config, onChange }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">CTA Button</h3>

      {/* Text */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Button Text</label>
        <input
          type="text"
          value={config.text || ''}
          onChange={(e) => onChange({ ...config, text: e.target.value })}
          placeholder="Get Started"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Alignment */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Alignment</label>
        <select
          value={config.alignment || 'center'}
          onChange={(e) => onChange({ ...config, alignment: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        >
          <option value="left">Left</option>
          <option value="center">Center</option>
          <option value="right">Right</option>
        </select>
      </div>

      {/* Style */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Style</label>
        <select
          value={config.style || 'primary'}
          onChange={(e) => onChange({ ...config, style: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        >
          <option value="primary">Primary</option>
          <option value="secondary">Secondary</option>
          <option value="accent">Accent</option>
        </select>
      </div>

      {/* Actions */}
      <div className="border-t pt-3">
        <p className="text-xs font-medium text-gray-500 mb-2">Button Action</p>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Scroll To (block ID)</label>
          <input
            type="text"
            value={config.scrollTo || ''}
            onChange={(e) => onChange({ ...config, scrollTo: e.target.value })}
            placeholder="e.g. trigger_form"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
        </div>

        <div className="mt-3">
          <label className="block text-sm font-medium text-gray-700 mb-1">External URL</label>
          <input
            type="url"
            value={config.externalUrl || ''}
            onChange={(e) => onChange({ ...config, externalUrl: e.target.value })}
            placeholder="https://example.com"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
          <p className="mt-1 text-xs text-gray-500">
            If both Scroll To and External URL are set, Scroll To takes priority.
          </p>
        </div>
      </div>
    </div>
  );
}
