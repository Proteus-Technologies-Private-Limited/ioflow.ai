import React, { useState, useRef } from 'react';
import { PhotoIcon, ArrowUpTrayIcon, LinkIcon, XMarkIcon } from '@heroicons/react/24/outline';

/**
 * ImageUploader - Combined upload + URL image picker
 *
 * Props:
 *   appId     - Frontend app ID for upload endpoint
 *   value     - Current image URL
 *   onChange  - (url) => void
 *   label     - Optional label
 */
export default function ImageUploader({ appId, value, onChange, label }) {
  const [mode, setMode] = useState(value ? 'url' : 'upload');
  const [urlInput, setUrlInput] = useState(value || '');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const resp = await fetch(`/api/v1/micro-saas-apps/${appId}/landing-images/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
        body: formData,
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const data = await resp.json();
      onChange(data.public_url);
      setUrlInput(data.public_url);
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleUrlSubmit = () => {
    if (urlInput.trim()) {
      onChange(urlInput.trim());
    }
  };

  const handleClear = () => {
    onChange('');
    setUrlInput('');
  };

  return (
    <div>
      {label && <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>}

      {/* Preview */}
      {value && (
        <div className="mb-2 relative inline-block">
          <img
            src={value}
            alt="Preview"
            className="w-32 h-20 object-cover rounded border border-gray-200"
          />
          <button
            onClick={handleClear}
            className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full p-0.5 hover:bg-red-600"
          >
            <XMarkIcon className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Mode toggle */}
      <div className="flex gap-1 mb-2">
        <button
          type="button"
          onClick={() => setMode('upload')}
          className={`flex items-center gap-1 px-3 py-1 text-xs rounded ${
            mode === 'upload' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          <ArrowUpTrayIcon className="w-3 h-3" />
          Upload
        </button>
        <button
          type="button"
          onClick={() => setMode('url')}
          className={`flex items-center gap-1 px-3 py-1 text-xs rounded ${
            mode === 'url' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          <LinkIcon className="w-3 h-3" />
          URL
        </button>
      </div>

      {mode === 'upload' ? (
        <div>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/gif,image/svg+xml,image/webp"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-primary hover:text-primary transition-colors w-full justify-center"
          >
            {uploading ? (
              <span className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
            ) : (
              <PhotoIcon className="w-5 h-5" />
            )}
            {uploading ? 'Uploading...' : 'Choose Image'}
          </button>
        </div>
      ) : (
        <div className="flex gap-2">
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            onBlur={handleUrlSubmit}
            onKeyDown={(e) => e.key === 'Enter' && handleUrlSubmit()}
            placeholder="https://example.com/image.png"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
          />
        </div>
      )}

      {error && <p className="mt-1 text-xs text-red-500">{error}</p>}
    </div>
  );
}
