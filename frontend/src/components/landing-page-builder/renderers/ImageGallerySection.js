import React, { useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';

export default function ImageGallerySection({ config }) {
  const [lightboxImage, setLightboxImage] = useState(null);
  const images = config.images || [];
  const columns = config.columns || 3;

  const gapClass = {
    sm: 'gap-2',
    md: 'gap-4',
    lg: 'gap-6',
  }[config.gap || 'md'];

  if (images.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 bg-gray-100 rounded-lg border-2 border-dashed border-gray-300">
        <p className="text-gray-400 text-sm">No images in gallery</p>
      </div>
    );
  }

  return (
    <div className="py-4">
      <div
        className={`grid ${gapClass}`}
        style={{ gridTemplateColumns: `repeat(${Math.min(columns, 4)}, minmax(0, 1fr))` }}
      >
        {images.map((img, idx) => (
          <div
            key={idx}
            className="relative group cursor-pointer overflow-hidden rounded-lg"
            onClick={() => setLightboxImage(img)}
          >
            <img
              src={img.src}
              alt={img.alt || ''}
              className="w-full h-48 object-cover transition-transform duration-200 group-hover:scale-105"
              loading="lazy"
            />
            {img.caption && (
              <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-xs p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                {img.caption}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Lightbox */}
      {lightboxImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80"
          onClick={() => setLightboxImage(null)}
        >
          <button
            className="absolute top-4 right-4 text-white hover:text-gray-300"
            onClick={() => setLightboxImage(null)}
          >
            <XMarkIcon className="w-8 h-8" />
          </button>
          <img
            src={lightboxImage.src}
            alt={lightboxImage.alt || ''}
            className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg"
          />
        </div>
      )}
    </div>
  );
}
