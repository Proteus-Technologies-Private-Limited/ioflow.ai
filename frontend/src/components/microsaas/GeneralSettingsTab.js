import React, { useState, useEffect } from 'react';
import {
  GlobeAltIcon,
  LockClosedIcon,
  ShieldCheckIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline';

const GeneralSettingsTab = ({ app, onSave, onSaveVisibility, isSaving }) => {
  const [formData, setFormData] = useState({
    frontend_app_name: '',
    description: '',
    visibility: 'private',
    is_active: true,
    access_type: 'public_url',
    rate_limit_per_hour: 100,
    embed_enabled: true,
    marketplace_enabled: false
  });

  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (app) {
      setFormData({
        frontend_app_name: app.frontend_app_name || '',
        description: app.description || '',
        visibility: app.visibility || 'private',
        is_active: app.is_active ?? true,
        access_type: app.access_type || 'public_url',
        rate_limit_per_hour: app.rate_limit_per_hour || 100,
        embed_enabled: app.embed_enabled ?? true,
        marketplace_enabled: app.marketplace_enabled ?? false
      });
    }
  }, [app]);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    const success = await onSave(formData);
    if (success) {
      setHasChanges(false);
    }
  };

  const handleVisibilityChange = async (newVisibility) => {
    const success = await onSaveVisibility(newVisibility);
    if (success) {
      setFormData(prev => ({ ...prev, visibility: newVisibility }));
    }
  };

  const getVisibilityOptions = () => [
    {
      value: 'public',
      label: 'Public',
      description: 'Anyone with an IOFlow account can see this app in the marketplace',
      icon: GlobeAltIcon,
      color: 'text-green-600'
    },
    {
      value: 'private',
      label: 'Private',
      description: 'Only you can see this app (useful during testing)',
      icon: LockClosedIcon,
      color: 'text-yellow-600'
    },
    {
      value: 'granted_access',
      label: 'Granted Access Only',
      description: 'Only users with granted access can see this app',
      icon: ShieldCheckIcon,
      color: 'text-blue-600'
    }
  ];

  const getAccessTypeOptions = () => [
    {
      value: 'public_url',
      label: 'Public URL',
      description: 'Anyone with the URL can access'
    },
    {
      value: 'organization',
      label: 'Organization',
      description: 'Only users from your organization'
    },
    {
      value: 'specific_users',
      label: 'Specific Users',
      description: 'Only designated users'
    },
    {
      value: 'tenant_list',
      label: 'Tenant List',
      description: 'Specific organizations only'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Basic Information */}
      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-4">Basic Information</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              App Name
            </label>
            <input
              type="text"
              value={formData.frontend_app_name}
              onChange={(e) => handleChange('frontend_app_name', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
              placeholder="My Awesome App"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
              placeholder="Describe what your app does..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Public URL
            </label>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={app?.public_url || ''}
                readOnly
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md bg-gray-50 text-gray-600"
              />
              <button
                onClick={() => navigator.clipboard.writeText(app?.public_url || '')}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Copy
              </button>
              <a
                href={app?.public_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-4 py-2 text-sm font-medium text-white bg-gradient-primary rounded-md hover:shadow-lg"
              >
                Open
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Marketplace Settings */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Marketplace Settings</h3>

        {/* Marketplace Enabled Toggle */}
        <div className="flex items-center justify-between mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="flex-1">
            <div className="flex items-center">
              <GlobeAltIcon className="h-5 w-5 text-primary mr-2" />
              <span className="text-sm font-medium text-gray-900">
                Enable in Marketplace
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              Make this app available in the IOFlow marketplace for others to discover and use
            </p>
            {app?.marketplace_status && (
              <div className="mt-2">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  app.marketplace_status === 'approved' || app.marketplace_status === 'auto_approved'
                    ? 'bg-green-100 text-green-800'
                    : app.marketplace_status === 'pending'
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  Status: {app.marketplace_status.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                </span>
              </div>
            )}
          </div>
          <button
            onClick={() => handleChange('marketplace_enabled', !formData.marketplace_enabled)}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2
              ${formData.marketplace_enabled ? 'bg-primary' : 'bg-gray-200'}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                transition duration-200 ease-in-out
                ${formData.marketplace_enabled ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>

        {/* Marketplace Visibility */}
        <div className={`transition-opacity duration-200 ${formData.marketplace_enabled ? 'opacity-100' : 'opacity-50'}`}>
          <p className="text-sm text-gray-500 mb-4">
            Control who can see your app in the IOFlow marketplace
          </p>
          <div className="space-y-3">
            {getVisibilityOptions().map((option) => {
            const Icon = option.icon;
            const isSelected = formData.visibility === option.value;
            return (
              <div
                key={option.value}
                onClick={() => handleVisibilityChange(option.value)}
                className={`
                  relative flex cursor-pointer rounded-lg border p-4 focus:outline-none
                  ${isSelected
                    ? 'border-primary bg-primary-10'
                    : 'border-gray-300 bg-white hover:bg-gray-50'
                  }
                `}
              >
                <div className="flex items-start">
                  <Icon className={`h-6 w-6 ${isSelected ? 'text-primary' : option.color}`} />
                  <div className="ml-3 flex-1">
                    <label className="block text-sm font-medium text-gray-900">
                      {option.label}
                    </label>
                    <p className="text-sm text-gray-500">{option.description}</p>
                  </div>
                  {isSelected && (
                    <div className="ml-3">
                      <div className="h-5 w-5 text-primary">
                        <svg viewBox="0 0 20 20" fill="currentColor">
                          <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        </div>
      </div>

      {/* Access Control */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Access Control</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Access Type
            </label>
            <select
              value={formData.access_type}
              onChange={(e) => handleChange('access_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            >
              {getAccessTypeOptions().map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label} - {option.description}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Rate Limit (per hour)
            </label>
            <input
              type="number"
              value={formData.rate_limit_per_hour}
              onChange={(e) => handleChange('rate_limit_per_hour', parseInt(e.target.value) || 0)}
              min="1"
              max="10000"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            />
            <p className="mt-1 text-sm text-gray-500">
              Maximum number of executions allowed per hour per IP address
            </p>
          </div>
        </div>
      </div>

      {/* App Status */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">App Status</h3>
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center">
              {formData.is_active ? (
                <EyeIcon className="h-5 w-5 text-green-600 mr-2" />
              ) : (
                <EyeSlashIcon className="h-5 w-5 text-gray-400 mr-2" />
              )}
              <span className="text-sm font-medium text-gray-900">
                {formData.is_active ? 'App is Active' : 'App is Inactive'}
              </span>
            </div>
            <p className="mt-1 text-sm text-gray-500">
              {formData.is_active
                ? 'Your app is publicly accessible via its URL'
                : 'Your app is currently disabled and not accessible'
              }
            </p>
          </div>
          <button
            onClick={() => handleChange('is_active', !formData.is_active)}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2
              ${formData.is_active ? 'bg-primary' : 'bg-gray-200'}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                transition duration-200 ease-in-out
                ${formData.is_active ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>
      </div>

      {/* Embed Settings */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Embed Settings</h3>
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <span className="text-sm font-medium text-gray-900">Enable Embed Functionality</span>
            <p className="mt-1 text-sm text-gray-500">
              Allow this app to be embedded in external websites
            </p>
          </div>
          <button
            onClick={() => handleChange('embed_enabled', !formData.embed_enabled)}
            className={`
              relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent
              transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2
              ${formData.embed_enabled ? 'bg-primary' : 'bg-gray-200'}
            `}
          >
            <span
              className={`
                pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0
                transition duration-200 ease-in-out
                ${formData.embed_enabled ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>
      </div>

      {/* Save Button */}
      {hasChanges && (
        <div className="border-t border-gray-200 pt-6">
          <div className="flex justify-end space-x-3">
            <button
              onClick={() => {
                setFormData({
                  frontend_app_name: app.frontend_app_name || '',
                  description: app.description || '',
                  visibility: app.visibility || 'private',
                  is_active: app.is_active ?? true,
                  access_type: app.access_type || 'public_url',
                  rate_limit_per_hour: app.rate_limit_per_hour || 100,
                  embed_enabled: app.embed_enabled ?? true,
                  marketplace_enabled: app.marketplace_enabled ?? false
                });
                setHasChanges(false);
              }}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 text-sm font-medium text-white bg-gradient-primary rounded-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default GeneralSettingsTab;
