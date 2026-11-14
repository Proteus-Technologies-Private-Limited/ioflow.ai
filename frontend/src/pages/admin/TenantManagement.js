import React, { useState, useEffect } from 'react';
import {
  PlusIcon,
  PencilIcon,
  TrashIcon,
  BuildingOfficeIcon,
  CheckCircleIcon,
  XCircleIcon,
  UserGroupIcon
} from '@heroicons/react/24/outline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';
import { useAuth } from '../../contexts/AuthContext';
import { formatDateTime } from '../../utils/dateFormatter';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const TenantManagement = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedTenant, setSelectedTenant] = useState(null);
  const [showUsersModal, setShowUsersModal] = useState(false);
  
  // Check if user is instance admin
  const isInstanceAdmin = user?.role === 'INSTANCE_ADMIN';

  // Fetch tenants
  const { data: tenants = [], isLoading, error, refetch } = useQuery({
    queryKey: ['tenants'],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      console.log('Fetching tenants list...');
      try {
        const response = await axios.get(`${API_BASE_URL}/api/v1/tenants/`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        console.log('Tenants fetched:', response.data);
        return response.data;
      } catch (error) {
        console.error('Error fetching tenants:', error);
        throw error;
      }
    },
    enabled: isInstanceAdmin
  });

  // Create tenant mutation
  const createTenantMutation = useMutation({
    mutationFn: async (tenantData) => {
      const token = localStorage.getItem('access_token');
      console.log('Creating tenant with data:', tenantData);
      console.log('Using token:', token ? 'Token present' : 'No token');
      console.log('API URL:', `${API_BASE_URL}/api/v1/tenants/`);
      
      try {
        const response = await axios.post(`${API_BASE_URL}/api/v1/tenants/`, tenantData, {
          headers: { Authorization: `Bearer ${token}` }
        });
        return response.data;
      } catch (error) {
        console.error('Request failed:', error);
        throw error;
      }
    },
    onSuccess: () => {
      showSuccessToast('Tenant created successfully');
      queryClient.invalidateQueries(['tenants']);
      setShowAddModal(false);
      // Force refetch
      queryClient.refetchQueries(['tenants']);
    },
    onError: (error) => {
      console.error('Tenant creation error:', error);
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 
                          error.response?.data?.message || 
                          error.message || 
                          'Failed to create tenant';
      showErrorToast(errorMessage);
    }
  });

  // Update tenant mutation
  const updateTenantMutation = useMutation({
    mutationFn: async ({ tenantId, data }) => {
      const token = localStorage.getItem('access_token');
      const response = await axios.put(`${API_BASE_URL}/api/v1/tenants/${tenantId}`, data, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    onSuccess: () => {
      showSuccessToast('Tenant updated successfully');
      queryClient.invalidateQueries(['tenants']);
      setShowEditModal(false);
    },
    onError: (error) => {
      console.error('Tenant update error:', error);
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 
                          error.response?.data?.message || 
                          error.message || 
                          'Failed to update tenant';
      showErrorToast(errorMessage);
    }
  });

  // Delete tenant mutation
  const deleteTenantMutation = useMutation({
    mutationFn: async (tenantId) => {
      const token = localStorage.getItem('access_token');
      await axios.delete(`${API_BASE_URL}/api/v1/tenants/${tenantId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
    },
    onSuccess: () => {
      showSuccessToast('Tenant deleted successfully');
      queryClient.invalidateQueries(['tenants']);
    },
    onError: (error) => {
      console.error('Tenant delete error:', error);
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 
                          error.response?.data?.message || 
                          error.message || 
                          'Failed to delete tenant';
      showErrorToast(errorMessage);
    }
  });

  if (!isInstanceAdmin) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">You don't have permission to access this page.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading tenants: {error.message}</p>
        <button
          onClick={() => refetch()}
          className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Tenant Management</h1>
        <div className="flex space-x-2">
          <button
            onClick={() => refetch()}
            className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            Refresh
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            <PlusIcon className="h-5 w-5 mr-2" />
            Create Tenant
          </button>
        </div>
      </div>

      {/* Tenants Table */}
      <div className="bg-white shadow overflow-hidden sm:rounded-md">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Tenant Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Tenant ID
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Email Domain
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Users
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Created
              </th>
              <th className="relative px-6 py-3">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tenants.map((tenant) => (
              <tr key={tenant.tenant_id}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <BuildingOfficeIcon className="h-5 w-5 text-gray-400 mr-3" />
                    <div>
                      <div className="text-sm font-medium text-gray-900">{tenant.tenant_name}</div>
                      {tenant.web_site && (
                        <div className="text-sm text-gray-500">{tenant.web_site}</div>
                      )}
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <code className="text-xs bg-gray-100 px-2 py-1 rounded">{tenant.tenant_id}</code>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {tenant.email_domain || '-'}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <button
                    onClick={() => {
                      setSelectedTenant(tenant);
                      setShowUsersModal(true);
                    }}
                    className="inline-flex items-center text-sm text-primary hover:text-primary-dark"
                  >
                    <UserGroupIcon className="h-4 w-4 mr-1" />
                    {tenant.user_count || 0}
                  </button>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    tenant.status === 'active' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {tenant.status === 'active' ? (
                      <CheckCircleIcon className="h-3 w-3 mr-1" />
                    ) : (
                      <XCircleIcon className="h-3 w-3 mr-1" />
                    )}
                    {tenant.status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                  {new Date(tenant.created_at).toLocaleDateString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                  <button
                    onClick={() => {
                      setSelectedTenant(tenant);
                      setShowEditModal(true);
                    }}
                    className="text-primary hover:text-primary-dark mr-4"
                  >
                    <PencilIcon className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => {
                      if (tenant.user_count === 0) {
                        if (window.confirm(`Are you sure you want to delete "${tenant.tenant_name}"?`)) {
                          deleteTenantMutation.mutate(tenant.tenant_id);
                        }
                      } else {
                        showErrorToast(`Cannot delete tenant with ${tenant.user_count} active users`);
                      }
                    }}
                    className="text-red-600 hover:text-red-900"
                    disabled={tenant.user_count > 0}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Tenant Modal */}
      {showAddModal && (
        <TenantFormModal
          onClose={() => setShowAddModal(false)}
          onSubmit={(data) => createTenantMutation.mutate(data)}
          isLoading={createTenantMutation.isLoading}
        />
      )}

      {/* Edit Tenant Modal */}
      {showEditModal && selectedTenant && (
        <TenantFormModal
          tenant={selectedTenant}
          onClose={() => {
            setShowEditModal(false);
            setSelectedTenant(null);
          }}
          onSubmit={(data) => updateTenantMutation.mutate({ 
            tenantId: selectedTenant.tenant_id, 
            data 
          })}
          isLoading={updateTenantMutation.isLoading}
        />
      )}

      {/* Users Modal */}
      {showUsersModal && selectedTenant && (
        <TenantUsersModal
          tenant={selectedTenant}
          onClose={() => {
            setShowUsersModal(false);
            setSelectedTenant(null);
          }}
        />
      )}
      </div>
    </div>
  );
};

// Tenant Form Modal Component
const TenantFormModal = ({ tenant, onClose, onSubmit, isLoading }) => {
  const [formData, setFormData] = useState({
    tenant_name: tenant?.tenant_name || '',
    email_domain: tenant?.email_domain || '',
    web_site: tenant?.web_site || '',
    gst_no: tenant?.gst_no || '',
    status: tenant?.status || 'active'
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.tenant_name?.trim()) {
      showErrorToast('Tenant name is required');
      return;
    }
    
    if (!formData.email_domain?.trim()) {
      showErrorToast('Email domain is required');
      return;
    }
    
    onSubmit(formData);
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[100]">
      <div className="bg-white rounded-lg max-w-md w-full p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">
          {tenant ? 'Edit Tenant' : 'Create New Tenant'}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Tenant Name</label>
            <input
              type="text"
              value={formData.tenant_name}
              onChange={(e) => setFormData({ ...formData, tenant_name: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Email Domain</label>
            <input
              type="text"
              value={formData.email_domain}
              onChange={(e) => setFormData({ ...formData, email_domain: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
              placeholder="example.com"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Website (optional)</label>
            <input
              type="url"
              value={formData.web_site}
              onChange={(e) => setFormData({ ...formData, web_site: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
              placeholder="https://example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">GST Number (optional)</label>
            <input
              type="text"
              value={formData.gst_no}
              onChange={(e) => setFormData({ ...formData, gst_no: e.target.value })}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
            />
          </div>
          {tenant && (
            <div>
              <label className="block text-sm font-medium text-gray-700">Status</label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          )}
          <div className="flex justify-end space-x-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              disabled={isLoading}
            >
              {isLoading ? 'Saving...' : (tenant ? 'Update' : 'Create')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Tenant Users Modal Component
const TenantUsersModal = ({ tenant, onClose }) => {
  const { data: users = [], isLoading } = useQuery({
    queryKey: ['tenant-users', tenant.tenant_id],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/tenants/${tenant.tenant_id}/users`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    }
  });

  const toggleUserStatusMutation = useMutation({
    mutationFn: async ({ userId, isActive }) => {
      const token = localStorage.getItem('access_token');
      await axios.put(
        `${API_BASE_URL}/api/v1/tenants/${tenant.tenant_id}/users/${userId}/activate`,
        { is_active: isActive },
        { headers: { Authorization: `Bearer ${token}` } }
      );
    },
    onSuccess: () => {
      showSuccessToast('User status updated');
      queryClient.invalidateQueries(['tenant-users', tenant.tenant_id]);
    },
    onError: (error) => {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update user status');
    }
  });

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[100]">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[80vh] overflow-hidden">
        <div className="p-6 border-b">
          <h3 className="text-lg font-medium text-gray-900">
            Users in {tenant.tenant_name}
          </h3>
        </div>
        <div className="overflow-y-auto max-h-[60vh]">
          {isLoading ? (
            <div className="flex justify-center p-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : users.length === 0 ? (
            <p className="text-center text-gray-500 p-8">No users in this tenant</p>
          ) : (
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    User
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Role
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Last Login
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user.user_id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{user.user_name}</div>
                        <div className="text-sm text-gray-500">{user.email}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800">
                        {user.role}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        user.is_active 
                          ? 'bg-green-100 text-green-800' 
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {user.last_login_at
                        ? formatDateTime(user.last_login_at)
                        : 'Never'
                      }
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <button
                        onClick={() => toggleUserStatusMutation.mutate({
                          userId: user.user_id,
                          isActive: !user.is_active
                        })}
                        className={`text-sm ${
                          user.is_active 
                            ? 'text-red-600 hover:text-red-900' 
                            : 'text-green-600 hover:text-green-900'
                        }`}
                        disabled={user.role === 'INSTANCE_ADMIN'}
                      >
                        {user.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="p-4 border-t">
          <button
            onClick={onClose}
            className="w-full sm:w-auto px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TenantManagement;