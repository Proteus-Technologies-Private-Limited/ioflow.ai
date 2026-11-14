import React from 'react';
import ImageUploader from '../ImageUploader';

export default function HeroBlockConfig({ config, onChange, appId }) {
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Hero Block</h3>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Hero title"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Subtitle */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Subtitle</label>
        <input
          type="text"
          value={config.subtitle || ''}
          onChange={(e) => onChange({ ...config, subtitle: e.target.value })}
          placeholder="Hero subtitle"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Colors */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Background Color</label>
          <input
            type="color"
            value={config.backgroundColor || '#ffffff'}
            onChange={(e) => onChange({ ...config, backgroundColor: e.target.value })}
            className="w-full h-9 border border-gray-300 rounded-md cursor-pointer"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Text Color</label>
          <input
            type="color"
            value={config.textColor || '#000000'}
            onChange={(e) => onChange({ ...config, textColor: e.target.value })}
            className="w-full h-9 border border-gray-300 rounded-md cursor-pointer"
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
          <option value="xl">Extra Large</option>
        </select>
      </div>

      {/* Background Image */}
      <div>
        <ImageUploader
          appId={appId}
          value={config.backgroundImage || ''}
          onChange={(url) => onChange({ ...config, backgroundImage: url })}
          label="Background Image"
        />
      </div>

      {/* CTA Section */}
      <div className="border-t pt-3">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2">
          <input
            type="checkbox"
            checked={config.showCTA || false}
            onChange={(e) => onChange({ ...config, showCTA: e.target.checked })}
            className="rounded border-gray-300 text-primary focus:ring-primary"
          />
          Show CTA Button
        </label>

        {config.showCTA && (
          <div className="space-y-3 pl-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">CTA Text</label>
              <input
                type="text"
                value={config.ctaText || ''}
                onChange={(e) => onChange({ ...config, ctaText: e.target.value })}
                placeholder="Get Started"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Scroll To (block ID)</label>
              <input
                type="text"
                value={config.ctaScrollTo || ''}
                onChange={(e) => onChange({ ...config, ctaScrollTo: e.target.value })}
                placeholder="trigger_form"
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
