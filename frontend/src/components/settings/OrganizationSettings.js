import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';
import { useAuth } from '../../contexts/AuthContext';
import {
  BuildingOfficeIcon,
  GlobeAltIcon,
  IdentificationIcon,
  MapPinIcon,
  KeyIcon
} from '@heroicons/react/24/outline';

const OrganizationSettings = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tenantData, setTenantData] = useState({
    tenant_id: '',
    tenant_name: '',
    email_domain: '',
    web_site: '',
    gst_no: '',
    address: '',
    status: ''
  });
  const [isEditing, setIsEditing] = useState(false);
  const [originalData, setOriginalData] = useState({});

  // Check if user is tenant admin or instance admin
  const isTenantAdmin = user?.role === 'TENANT_ADMIN' || user?.role === 'INSTANCE_ADMIN';

  useEffect(() => {
    fetchTenantData();
  }, []);

  const fetchTenantData = async () => {
    if (!user?.tenant?.tenant_id) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`/api/v1/tenants/${user.tenant.tenant_id}`);
      const data = {
        tenant_id: response.data.tenant_id || '',
        tenant_name: response.data.tenant_name || '',
        email_domain: response.data.email_domain || '',
        web_site: response.data.web_site || '',
        gst_no: response.data.gst_no || '',
        address: response.data.address || '',
        status: response.data.status || ''
      };
      setTenantData(data);
      setOriginalData(data);
    } catch (error) {
      console.error('Failed to fetch tenant data:', error);
      showErrorToast('Failed to load organization settings');
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setTenantData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updateData = {
        tenant_name: tenantData.tenant_name,
        email_domain: tenantData.email_domain,
        web_site: tenantData.web_site,
        gst_no: tenantData.gst_no,
        address: tenantData.address
      };

      await axios.put(`/api/v1/tenants/${user.tenant.tenant_id}`, updateData);
      showSuccessToast('Organization settings updated successfully');
      setOriginalData(tenantData);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to update tenant data:', error);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update organization settings');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setTenantData(originalData);
    setIsEditing(false);
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-4 bg-gray-200 rounded w-1/4"></div>
        <div className="h-4 bg-gray-200 rounded w-3/4"></div>
        <div className="h-32 bg-gray-200 rounded"></div>
      </div>
    );
  }

  if (!user?.tenant?.tenant_id) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <p className="text-sm text-yellow-800">
          No tenant information available. Please contact your administrator.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900">Organization Settings</h2>
          <p className="mt-1 text-sm text-gray-600">
            View and manage your organization information
          </p>
        </div>
        {isTenantAdmin && !isEditing && (
          <button
            onClick={() => setIsEditing(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            Edit
          </button>
        )}
      </div>

      {!isTenantAdmin && (
        <div className="bg-primary-10 border border-primary/30 rounded-md p-4">
          <p className="text-sm text-primary-dark">
            Only Tenant Administrators and Instance Administrators can edit organization settings.
          </p>
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-200">
        {/* Tenant ID - Read Only */}
        <div className="p-4 flex items-start">
          <KeyIcon className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="ml-3 flex-1">
            <label className="block text-sm font-medium text-gray-700">
              Tenant ID
            </label>
            <div className="mt-1">
              <input
                type="text"
                value={tenantData.tenant_id}
                readOnly
                className="block w-full px-3 py-2 bg-gray-50 border border-gray-300 rounded-md shadow-sm text-sm text-gray-700 cursor-not-allowed"
              />
            </div>
            <p className="mt-1 text-xs text-gray-500">
              Your unique organization identifier (read-only)
            </p>
          </div>
        </div>

        {/* Organization Name */}
        <div className="p-4 flex items-start">
          <BuildingOfficeIcon className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="ml-3 flex-1">
            <label className="block text-sm font-medium text-gray-700">
              Organization Name
            </label>
            <div className="mt-1">
              <input
                type="text"
                value={tenantData.tenant_name}
                onChange={(e) => handleInputChange('tenant_name', e.target.value)}
                readOnly={!isEditing}
                className={`block w-full px-3 py-2 border rounded-md shadow-sm text-sm ${
                  isEditing
                    ? 'border-gray-300 focus:ring-primary focus:border-primary'
                    : 'bg-gray-50 border-gray-300 text-gray-700 cursor-not-allowed'
                }`}
              />
            </div>
          </div>
        </div>

        {/* Email Domain */}
        <div className="p-4 flex items-start">
          <GlobeAltIcon className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="ml-3 flex-1">
            <label className="block text-sm font-medium text-gray-700">
              Email Domain
            </label>
            <div className="mt-1">
              <input
                type="text"
                value={tenantData.email_domain}
                onChange={(e) => handleInputChange('email_domain', e.target.value)}
                readOnly={!isEditing}
                className={`block w-full px-3 py-2 border rounded-md shadow-sm text-sm ${
                  isEditing
                    ? 'border-gray-300 focus:ring-primary focus:border-primary'
                    : 'bg-gray-50 border-gray-300 text-gray-700 cursor-not-allowed'
                }`}
              />
            </div>
          </div>
        </div>

        {/* Website */}
        <div className="p-4 flex items-start">
          <GlobeAltIcon className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="ml-3 flex-1">
            <label className="block text-sm font-medium text-gray-700">
              Website
            </label>
            <div className="mt-1">
              <input
                type="url"
                value={tenantData.web_site}
                onChange={(e) => handleInputChange('web_site', e.target.value)}
                readOnly={!isEditing}
                placeholder="https://example.com"
                className={`block w-full px-3 py-2 border rounded-md shadow-sm text-sm ${
                  isEditing
                    ? 'border-gray-300 focus:ring-primary focus:border-primary'
                    : 'bg-gray-50 border-gray-300 text-gray-700 cursor-not-allowed'
                }`}
              />
            </div>
          </div>
        </div>

        {/* GST Number */}
        <div className="p-4 flex items-start">
          <IdentificationIcon className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="ml-3 flex-1">
            <label className="block text-sm font-medium text-gray-700">
              GST Number
            </label>
            <div className="mt-1">
              <input
                type="text"
                value={tenantData.gst_no}
                onChange={(e) => handleInputChange('gst_no', e.target.value)}
                readOnly={!isEditing}
                placeholder="Enter GST number"
                className={`block w-full px-3 py-2 border rounded-md shadow-sm text-sm ${
                  isEditing
                    ? 'border-gray-300 focus:ring-primary focus:border-primary'
                    : 'bg-gray-50 border-gray-300 text-gray-700 cursor-not-allowed'
                }`}
              />
            </div>
          </div>
        </div>

        {/* Address */}
        <div className="p-4 flex items-start">
          <MapPinIcon className="h-5 w-5 text-gray-400 mt-0.5" />
          <div className="ml-3 flex-1">
            <label className="block text-sm font-medium text-gray-700">
              Address
            </label>
            <div className="mt-1">
              <textarea
                value={tenantData.address}
                onChange={(e) => handleInputChange('address', e.target.value)}
                readOnly={!isEditing}
                rows={3}
                placeholder="Enter organization address"
                className={`block w-full px-3 py-2 border rounded-md shadow-sm text-sm ${
                  isEditing
                    ? 'border-gray-300 focus:ring-primary focus:border-primary'
                    : 'bg-gray-50 border-gray-300 text-gray-700 cursor-not-allowed'
                }`}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Action buttons when editing */}
      {isEditing && (
        <div className="flex justify-end space-x-3 pt-4">
          <button
            onClick={handleCancel}
            disabled={saving}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      )}
    </div>
  );
};

export default OrganizationSettings;
