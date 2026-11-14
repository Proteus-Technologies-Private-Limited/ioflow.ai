import React from 'react';
import ImageUploader from '../ImageUploader';

export default function ImageBlockConfig({ config, onChange, appId }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Image Block</h3>

      {/* Image Source */}
      <div>
        <ImageUploader
          appId={appId}
          value={config.src || ''}
          onChange={(url) => onChange({ ...config, src: url })}
          label="Image"
        />
      </div>

      {/* Alt Text */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Alt Text</label>
        <input
          type="text"
          value={config.alt || ''}
          onChange={(e) => onChange({ ...config, alt: e.target.value })}
          placeholder="Describe the image"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Dimensions */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Width</label>
          <input
            type="text"
            value={config.width || ''}
            onChange={(e) => onChange({ ...config, width: e.target.value })}
            placeholder="e.g. 100%, 400px"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Max Width</label>
          <input
            type="text"
            value={config.maxWidth || ''}
            onChange={(e) => onChange({ ...config, maxWidth: e.target.value })}
            placeholder="e.g. 600px"
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
        </div>
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

      {/* Border Radius */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Border Radius</label>
        <input
          type="text"
          value={config.borderRadius || ''}
          onChange={(e) => onChange({ ...config, borderRadius: e.target.value })}
          placeholder="e.g. 8px, 50%"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Caption */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Caption</label>
        <textarea
          value={config.caption || ''}
          onChange={(e) => onChange({ ...config, caption: e.target.value })}
          placeholder="Optional image caption"
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>
    </div>
  );
}
