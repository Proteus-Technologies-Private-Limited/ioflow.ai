import React from 'react';
import ImageUploader from '../ImageUploader';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';

export default function ImageGalleryBlockConfig({ config, onChange, appId }) {
  const images = config.images || [];

  const addImage = () => {
    onChange({
      ...config,
      images: [...images, { src: '', alt: '', caption: '' }],
    });
  };

  const removeImage = (index) => {
    const updated = images.filter((_, i) => i !== index);
    onChange({ ...config, images: updated });
  };

  const updateImage = (index, field, value) => {
    const updated = images.map((img, i) =>
      i === index ? { ...img, [field]: value } : img
    );
    onChange({ ...config, images: updated });
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Image Gallery</h3>

      {/* Layout */}
      <div className="grid grid-cols-2 gap-3">
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
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Gap</label>
          <select
            value={config.gap || 'md'}
            onChange={(e) => onChange({ ...config, gap: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          >
            <option value="sm">Small</option>
            <option value="md">Medium</option>
            <option value="lg">Large</option>
          </select>
        </div>
      </div>

      {/* Images List */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Images ({images.length})
        </label>

        <div className="space-y-3">
          {images.map((image, index) => (
            <div key={index} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-medium text-gray-500">Image {index + 1}</span>
                <button
                  type="button"
                  onClick={() => removeImage(index)}
                  className="text-red-500 hover:text-red-700 p-1"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-2">
                <ImageUploader
                  appId={appId}
                  value={image.src || ''}
                  onChange={(url) => updateImage(index, 'src', url)}
                  label="Source"
                />

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Alt Text</label>
                  <input
                    type="text"
                    value={image.alt || ''}
                    onChange={(e) => updateImage(index, 'alt', e.target.value)}
                    placeholder="Image description"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Caption</label>
                  <input
                    type="text"
                    value={image.caption || ''}
                    onChange={(e) => updateImage(index, 'caption', e.target.value)}
                    placeholder="Optional caption"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
                  />
                </div>
              </div>
            </div>
          ))}
        </div>

        <button
          type="button"
          onClick={addImage}
          className="mt-2 flex items-center gap-1 px-3 py-2 text-sm text-primary border border-primary/30 rounded-md hover:bg-primary/5 w-full justify-center"
        >
          <PlusIcon className="w-4 h-4" />
          Add Image
        </button>
      </div>
    </div>
  );
}
