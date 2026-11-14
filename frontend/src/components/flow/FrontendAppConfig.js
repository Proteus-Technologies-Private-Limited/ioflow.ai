import React, { useState, useEffect } from 'react';
import { 
  XMarkIcon, 
  GlobeAltIcon,
  UserGroupIcon,
  UserIcon,
  BuildingOfficeIcon,
  InformationCircleIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const FrontendAppConfig = ({ 
  isOpen, 
  onClose, 
  publishedApp, 
  onSuccess 
}) => {
  const [formData, setFormData] = useState({
    frontend_app_name: '',
    description: '',
    access_type: 'public_url',
    public_url_slug: '',
    rate_limit_per_hour: 100,
    access_config: {
      allowed_users: [],
      allowed_tenants: []
    }
  });

  const [isLoading, setIsLoading] = useState(false);
  const [newUser, setNewUser] = useState('');
  const [newTenant, setNewTenant] = useState('');

  useEffect(() => {
    if (publishedApp && isOpen) {
      setFormData({
        frontend_app_name: `${publishedApp.flow_name} - Public`,
        description: `Public interface for ${publishedApp.flow_name}`,
        access_type: 'public_url',
        public_url_slug: '',
        rate_limit_per_hour: 100,
        access_config: {
          allowed_users: [],
          allowed_tenants: []
        }
      });
    }
  }, [publishedApp, isOpen]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleAccessConfigChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      access_config: {
        ...prev.access_config,
        [field]: value
      }
    }));
  };

  const addUser = () => {
    if (!newUser.trim()) return;
    
    const updatedUsers = [...formData.access_config.allowed_users, newUser.trim()];
    handleAccessConfigChange('allowed_users', updatedUsers);
    setNewUser('');
  };

  const removeUser = (index) => {
    const updatedUsers = formData.access_config.allowed_users.filter((_, i) => i !== index);
    handleAccessConfigChange('allowed_users', updatedUsers);
  };

  const addTenant = () => {
    if (!newTenant.trim()) return;
    
    const updatedTenants = [...formData.access_config.allowed_tenants, newTenant.trim()];
    handleAccessConfigChange('allowed_tenants', updatedTenants);
    setNewTenant('');
  };

  const removeTenant = (index) => {
    const updatedTenants = formData.access_config.allowed_tenants.filter((_, i) => i !== index);
    handleAccessConfigChange('allowed_tenants', updatedTenants);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const payload = {
        published_app_id: publishedApp.published_app_id,
        frontend_app_name: formData.frontend_app_name,
        description: formData.description,
        access_type: formData.access_type,
        access_config: formData.access_config,
        public_url_slug: formData.public_url_slug || undefined,
        rate_limit_per_hour: formData.rate_limit_per_hour
      };

      const response = await fetch('/api/v1/frontend-applications/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create frontend application');
      }

      const result = await response.json();
      showSuccessToast(result.message);
      onSuccess?.(result);
      onClose();
    } catch (error) {
      showErrorToast(`Failed to create frontend application: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const getAccessTypeDescription = () => {
    switch (formData.access_type) {
      case 'public_url':
        return 'Anyone with the URL can access this application. No authentication required.';
      case 'organization':
        return 'Only users from your organization can access this application.';
      case 'specific_users':
        return 'Only specific IOFlow users you designate can access this application.';
      case 'tenant_list':
        return 'Users from specific organizations/tenants can access this application.';
      default:
        return '';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-green-600 to-blue-600 px-6 py-4 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <GlobeAltIcon className="w-6 h-6" />
              <div>
                <h2 className="text-xl font-semibold">Create Frontend Application</h2>
                <p className="text-green-100 text-sm">Make your flow publicly accessible</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 transition-colors"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[70vh] overflow-y-auto">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Basic Information */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Basic Information</h3>
              
              <div className="grid grid-cols-1 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Application Name
                  </label>
                  <input
                    type="text"
                    value={formData.frontend_app_name}
                    onChange={(e) => handleInputChange('frontend_app_name', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Description
                  </label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => handleInputChange('description', e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Custom URL Slug (optional)
                  </label>
                  <div className="flex">
                    <span className="inline-flex items-center px-3 border border-r-0 border-gray-300 bg-gray-50 text-gray-500 text-sm">
                      /public-app/
                    </span>
                    <input
                      type="text"
                      value={formData.public_url_slug}
                      onChange={(e) => handleInputChange('public_url_slug', e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-r-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      placeholder="my-app"
                    />
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    Leave empty to auto-generate from application name
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Rate Limit (requests per hour)
                  </label>
                  <input
                    type="number"
                    value={formData.rate_limit_per_hour}
                    onChange={(e) => handleInputChange('rate_limit_per_hour', parseInt(e.target.value) || 100)}
                    min="1"
                    max="10000"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            </div>

            {/* Access Control */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Access Control</h3>
              
              <div className="space-y-4">
                {/* Access Type Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Who can access this application?
                  </label>
                  
                  <div className="space-y-3">
                    <div className="flex items-center">
                      <input
                        type="radio"
                        id="public_url"
                        name="access_type"
                        value="public_url"
                        checked={formData.access_type === 'public_url'}
                        onChange={(e) => handleInputChange('access_type', e.target.value)}
                        className="h-4 w-4 text-blue-600"
                      />
                      <label htmlFor="public_url" className="ml-3 flex items-center">
                        <GlobeAltIcon className="w-5 h-5 text-gray-400 mr-2" />
                        <div>
                          <div className="text-sm font-medium text-gray-900">Anyone with URL</div>
                          <div className="text-xs text-gray-500">Public access, no authentication required</div>
                        </div>
                      </label>
                    </div>

                    <div className="flex items-center">
                      <input
                        type="radio"
                        id="organization"
                        name="access_type"
                        value="organization"
                        checked={formData.access_type === 'organization'}
                        onChange={(e) => handleInputChange('access_type', e.target.value)}
                        className="h-4 w-4 text-blue-600"
                      />
                      <label htmlFor="organization" className="ml-3 flex items-center">
                        <BuildingOfficeIcon className="w-5 h-5 text-gray-400 mr-2" />
                        <div>
                          <div className="text-sm font-medium text-gray-900">My Organization</div>
                          <div className="text-xs text-gray-500">Only users from your organization</div>
                        </div>
                      </label>
                    </div>

                    <div className="flex items-center">
                      <input
                        type="radio"
                        id="specific_users"
                        name="access_type"
                        value="specific_users"
                        checked={formData.access_type === 'specific_users'}
                        onChange={(e) => handleInputChange('access_type', e.target.value)}
                        className="h-4 w-4 text-blue-600"
                      />
                      <label htmlFor="specific_users" className="ml-3 flex items-center">
                        <UserIcon className="w-5 h-5 text-gray-400 mr-2" />
                        <div>
                          <div className="text-sm font-medium text-gray-900">Specific Users</div>
                          <div className="text-xs text-gray-500">Only designated IOFlow users</div>
                        </div>
                      </label>
                    </div>

                    <div className="flex items-center">
                      <input
                        type="radio"
                        id="tenant_list"
                        name="access_type"
                        value="tenant_list"
                        checked={formData.access_type === 'tenant_list'}
                        onChange={(e) => handleInputChange('access_type', e.target.value)}
                        className="h-4 w-4 text-blue-600"
                      />
                      <label htmlFor="tenant_list" className="ml-3 flex items-center">
                        <UserGroupIcon className="w-5 h-5 text-gray-400 mr-2" />
                        <div>
                          <div className="text-sm font-medium text-gray-900">Specific Organizations</div>
                          <div className="text-xs text-gray-500">Users from designated organizations</div>
                        </div>
                      </label>
                    </div>
                  </div>

                  <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
                    <div className="flex">
                      <InformationCircleIcon className="w-5 h-5 text-blue-400 mr-2 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-blue-800">
                        {getAccessTypeDescription()}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Specific Users Configuration */}
                {formData.access_type === 'specific_users' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Allowed Users (Email addresses or User IDs)
                    </label>
                    
                    <div className="flex mb-3">
                      <input
                        type="text"
                        value={newUser}
                        onChange={(e) => setNewUser(e.target.value)}
                        placeholder="user@example.com"
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addUser())}
                      />
                      <button
                        type="button"
                        onClick={addUser}
                        className="px-3 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700"
                      >
                        <PlusIcon className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="space-y-2">
                      {formData.access_config.allowed_users.map((user, index) => (
                        <div key={index} className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-md">
                          <span className="text-sm text-gray-900">{user}</span>
                          <button
                            type="button"
                            onClick={() => removeUser(index)}
                            className="text-red-600 hover:text-red-800"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Tenant List Configuration */}
                {formData.access_type === 'tenant_list' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Allowed Organizations (Tenant IDs or Names)
                    </label>
                    
                    <div className="flex mb-3">
                      <input
                        type="text"
                        value={newTenant}
                        onChange={(e) => setNewTenant(e.target.value)}
                        placeholder="organization-id"
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTenant())}
                      />
                      <button
                        type="button"
                        onClick={addTenant}
                        className="px-3 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700"
                      >
                        <PlusIcon className="w-4 h-4" />
                      </button>
                    </div>

                    <div className="space-y-2">
                      {formData.access_config.allowed_tenants.map((tenant, index) => (
                        <div key={index} className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-md">
                          <span className="text-sm text-gray-900">{tenant}</span>
                          <button
                            type="button"
                            onClick={() => removeTenant(index)}
                            className="text-red-600 hover:text-red-800"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Source Flow: {publishedApp?.flow_name}
          </div>
          <div className="flex space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              onClick={handleSubmit}
              disabled={isLoading}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 flex items-center"
            >
              {isLoading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Creating...
                </>
              ) : (
                <>
                  <GlobeAltIcon className="w-4 h-4 mr-2" />
                  Create Frontend App
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FrontendAppConfig;