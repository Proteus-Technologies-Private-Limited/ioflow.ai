import React from 'react';

export default function ImageSection({ config }) {
  if (!config.src) {
    return (
      <div className="flex items-center justify-center py-12 bg-gray-100 rounded-lg border-2 border-dashed border-gray-300">
        <p className="text-gray-400 text-sm">No image configured</p>
      </div>
    );
  }

  const alignClass = {
    left: 'flex justify-start',
    center: 'flex justify-center',
    right: 'flex justify-end',
  }[config.alignment || 'center'];

  return (
    <div className={`py-4 ${alignClass}`}>
      <figure style={{ maxWidth: config.maxWidth || '100%', width: config.width || '100%' }}>
        <img
          src={config.src}
          alt={config.alt || ''}
          className="w-full h-auto"
          style={{ borderRadius: config.borderRadius || '8px' }}
          loading="lazy"
        />
        {config.caption && (
          <figcaption className="mt-2 text-center text-sm text-gray-500">
            {config.caption}
          </figcaption>
        )}
      </figure>
    </div>
  );
}
