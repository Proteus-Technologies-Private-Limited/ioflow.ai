import React from 'react';

/**
 * ThemeEditor - Modal/panel for editing theme settings
 */
export default function ThemeEditor({ theme, onChange, onClose }) {
  const update = (field, value) => {
    onChange({ ...theme, [field]: value });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold text-gray-900">Theme Settings</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Primary Color</label>
            <div className="flex gap-2 items-center">
              <input
                type="color"
                value={theme.primaryColor || '#0891b2'}
                onChange={(e) => update('primaryColor', e.target.value)}
                className="w-10 h-10 rounded border border-gray-300 cursor-pointer"
              />
              <input
                type="text"
                value={theme.primaryColor || '#0891b2'}
                onChange={(e) => update('primaryColor', e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Background Color</label>
            <div className="flex gap-2 items-center">
              <input
                type="color"
                value={theme.backgroundColor || '#f9fafb'}
                onChange={(e) => update('backgroundColor', e.target.value)}
                className="w-10 h-10 rounded border border-gray-300 cursor-pointer"
              />
              <input
                type="text"
                value={theme.backgroundColor || '#f9fafb'}
                onChange={(e) => update('backgroundColor', e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Font Family</label>
            <select
              value={theme.fontFamily || 'Inter, system-ui, sans-serif'}
              onChange={(e) => update('fontFamily', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="Inter, system-ui, sans-serif">Inter (Default)</option>
              <option value="Georgia, serif">Georgia (Serif)</option>
              <option value="'Courier New', monospace">Courier New (Mono)</option>
              <option value="system-ui, sans-serif">System UI</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Border Radius</label>
            <select
              value={theme.borderRadius || '8px'}
              onChange={(e) => update('borderRadius', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="0px">None (0px)</option>
              <option value="4px">Small (4px)</option>
              <option value="8px">Medium (8px)</option>
              <option value="12px">Large (12px)</option>
              <option value="16px">Extra Large (16px)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max Width</label>
            <select
              value={theme.maxWidth || '1200px'}
              onChange={(e) => update('maxWidth', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="800px">Narrow (800px)</option>
              <option value="1024px">Medium (1024px)</option>
              <option value="1200px">Wide (1200px)</option>
              <option value="1400px">Extra Wide (1400px)</option>
              <option value="100%">Full Width</option>
            </select>
          </div>
        </div>

        <div className="px-6 py-4 border-t flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gradient-primary text-white text-sm font-medium rounded-lg hover:shadow-lg transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
