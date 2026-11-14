import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import {
  UserIcon,
  PencilIcon,
  TrashIcon,
  ShieldCheckIcon,
  UserGroupIcon,
  DocumentTextIcon,
  EyeIcon,
  KeyIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  EnvelopeIcon,
  ClockIcon,
  ArrowPathIcon,
  ClipboardDocumentIcon,
  UserPlusIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  ChevronDownIcon,
  ChevronUpIcon
} from '@heroicons/react/24/outline';
import { useAuth } from '../../contexts/AuthContext';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';
import { formatDateTime } from '../../utils/dateFormatter';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const ROLE_LABELS = {
  INSTANCE_ADMIN: 'Instance Admin',
  TENANT_ADMIN: 'Tenant Admin',
  FLOW_DESIGNER: 'Flow Designer',
  FLOW_EXECUTOR: 'Flow Executor',
  EXECUTION_MONITOR: 'Execution Monitor',
  APPLICATION_PROVIDER: 'Application Provider'
};

const ROLE_COLORS = {
  INSTANCE_ADMIN: 'bg-red-100 text-red-800',
  TENANT_ADMIN: 'bg-orange-100 text-orange-800',
  FLOW_DESIGNER: 'bg-blue-100 text-blue-800',
  FLOW_EXECUTOR: 'bg-teal-100 text-teal-800',
  EXECUTION_MONITOR: 'bg-green-100 text-green-800',
  APPLICATION_PROVIDER: 'bg-purple-100 text-purple-800'
};

const ROLE_ICONS = {
  INSTANCE_ADMIN: ShieldCheckIcon,
  TENANT_ADMIN: UserGroupIcon,
  FLOW_DESIGNER: DocumentTextIcon,
  FLOW_EXECUTOR: DocumentTextIcon,
  EXECUTION_MONITOR: EyeIcon,
  APPLICATION_PROVIDER: KeyIcon
};

const INVITATION_STATUS_COLORS = {
  pending: 'bg-yellow-100 text-yellow-800',
  accepted: 'bg-green-100 text-green-800',
  expired: 'bg-gray-100 text-gray-800',
  cancelled: 'bg-red-100 text-red-800'
};

const ROLE_PERMISSIONS = {
  INSTANCE_ADMIN: {
    description: 'Full system administrator with unrestricted access',
    permissions: [
      'Full system access',
      'Manage all tenants',
      'Manage all users and roles',
      'Access all data across tenants',
      'Configure system settings',
      'Load seed applications',
      'View system metrics'
    ]
  },
  TENANT_ADMIN: {
    description: 'Administrator for a specific tenant',
    permissions: [
      'Manage users within tenant',
      'View all tenant data',
      'Configure tenant settings',
      'Cannot assign Instance Admin role',
      'Limited to own tenant only',
      'Manage tenant applications'
    ]
  },
  FLOW_DESIGNER: {
    description: 'Create and manage automation flows',
    permissions: [
      'Create and edit flows',
      'Execute flows',
      'View flow execution history',
      'Access application services',
      'Limited to own tenant'
    ]
  },
  FLOW_EXECUTOR: {
    description: 'Execute existing flows and view execution logs only',
    permissions: [
      'Execute existing flows',
      'View flow execution history',
      'View execution logs',
      'Cannot create, edit, or delete flows',
      'Cannot import flows',
      'Limited to own tenant'
    ]
  },
  EXECUTION_MONITOR: {
    description: 'Monitor flow executions and logs',
    permissions: [
      'View flow executions',
      'View execution logs',
      'Monitor flow status',
      'Read-only access',
      'Cannot modify flows'
    ]
  },
  APPLICATION_PROVIDER: {
    description: 'Manage applications and integrations',
    permissions: [
      'Create applications',
      'Configure services',
      'Manage webhooks',
      'Set up OAuth connections',
      'Define application events'
    ]
  }
};

function UserManagement() {
  const { user: currentUser } = useAuth();
  const queryClient = useQueryClient();
  const [selectedTenant, setSelectedTenant] = useState('');
  const [selectedRole, setSelectedRole] = useState('');
  const [activeFilter, setActiveFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [editingUser, setEditingUser] = useState(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [userToDelete, setUserToDelete] = useState(null);
  const [activeTab, setActiveTab] = useState('users');

  // Invitation states
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('FLOW_DESIGNER');
  const [inviteMessage, setInviteMessage] = useState('');
  const [invitationStatusFilter, setInvitationStatusFilter] = useState('pending');

  // Workflow role states
  const [showWfRoleModal, setShowWfRoleModal] = useState(false);
  const [editingWfRole, setEditingWfRole] = useState(null);
  const [wfRoleName, setWfRoleName] = useState('');
  const [wfRoleDescription, setWfRoleDescription] = useState('');
  const [showDeleteWfRoleConfirm, setShowDeleteWfRoleConfirm] = useState(false);
  const [wfRoleToDelete, setWfRoleToDelete] = useState(null);
  const [expandedWfRoleId, setExpandedWfRoleId] = useState(null);
  const [showUserAssignModal, setShowUserAssignModal] = useState(false);
  const [assignToRoleId, setAssignToRoleId] = useState(null);
  const [userAssignSearch, setUserAssignSearch] = useState('');
  const [selectedUserIds, setSelectedUserIds] = useState([]);

  // User workflow roles modal (from Users tab)
  const [showUserWfRolesModal, setShowUserWfRolesModal] = useState(false);
  const [userWfRolesTarget, setUserWfRolesTarget] = useState(null); // user object
  const [userWfRolesSearch, setUserWfRolesSearch] = useState('');

  // Check permissions
  const canManageUsers = currentUser?.role === 'INSTANCE_ADMIN' || currentUser?.role === 'TENANT_ADMIN';

  // Fetch users
  const { data: users = [], isLoading: loadingUsers, error: usersError } = useQuery({
    queryKey: ['users', selectedTenant, selectedRole, activeFilter, searchQuery],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams();
      if (selectedTenant) params.append('tenant_id', selectedTenant);
      if (selectedRole) params.append('role', selectedRole);
      if (activeFilter) params.append('is_active', activeFilter);
      if (searchQuery) params.append('search', searchQuery);

      const response = await axios.get(`${API_BASE_URL}/api/v1/users/?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: canManageUsers
  });

  // Fetch invitations
  const { data: invitations = [], isLoading: loadingInvitations } = useQuery({
    queryKey: ['invitations', invitationStatusFilter],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams();
      if (invitationStatusFilter) params.append('status_filter', invitationStatusFilter);

      const response = await axios.get(`${API_BASE_URL}/api/v1/invitations/?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: canManageUsers && activeTab === 'invitations'
  });

  // Fetch tenants for filter (only for instance admin)
  const { data: tenants = [] } = useQuery({
    queryKey: ['tenants'],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/tenants/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: currentUser?.role === 'INSTANCE_ADMIN'
  });

  // Update user mutation
  const updateUserMutation = useMutation({
    mutationFn: async ({ userId, updates }) => {
      const token = localStorage.getItem('access_token');
      const response = await axios.put(`${API_BASE_URL}/api/v1/users/${userId}`, updates, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['users']);
      setShowEditModal(false);
      setEditingUser(null);
      showSuccessToast('User updated successfully');
    },
    onError: (error) => {
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to update user';
      showErrorToast(errorMessage);
    }
  });

  // Delete user mutation
  const deleteUserMutation = useMutation({
    mutationFn: async (userId) => {
      const token = localStorage.getItem('access_token');
      await axios.delete(`${API_BASE_URL}/api/v1/users/${userId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['users']);
      setShowDeleteConfirm(false);
      setUserToDelete(null);
      showSuccessToast('User deleted successfully');
    },
    onError: (error) => {
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to delete user';
      showErrorToast(errorMessage);
    }
  });

  // Create invitation mutation
  const createInvitationMutation = useMutation({
    mutationFn: async (invitationData) => {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(`${API_BASE_URL}/api/v1/invitations/`, invitationData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['invitations']);
      setShowInviteModal(false);
      setInviteEmail('');
      setInviteRole('FLOW_DESIGNER');
      setInviteMessage('');
      showSuccessToast(`Invitation sent to ${data.email}`);
    },
    onError: (error) => {
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to send invitation';
      showErrorToast(errorMessage);
    }
  });

  // Resend invitation mutation
  const resendInvitationMutation = useMutation({
    mutationFn: async (invitationId) => {
      const token = localStorage.getItem('access_token');
      await axios.post(`${API_BASE_URL}/api/v1/invitations/${invitationId}/resend`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
    },
    onSuccess: () => {
      showSuccessToast('Invitation resent successfully');
    },
    onError: (error) => {
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to resend invitation';
      showErrorToast(errorMessage);
    }
  });

  // Cancel invitation mutation
  const cancelInvitationMutation = useMutation({
    mutationFn: async (invitationId) => {
      const token = localStorage.getItem('access_token');
      await axios.delete(`${API_BASE_URL}/api/v1/invitations/${invitationId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['invitations']);
      showSuccessToast('Invitation cancelled');
    },
    onError: (error) => {
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 'Failed to cancel invitation';
      showErrorToast(errorMessage);
    }
  });

  // ============================================================================
  // Workflow Role Queries & Mutations
  // ============================================================================

  // Fetch workflow roles
  const { data: workflowRoles = [], isLoading: loadingWfRoles } = useQuery({
    queryKey: ['workflowRoles'],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/hitl/roles`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: canManageUsers && activeTab === 'workflowRoles'
  });

  // Fetch users for a specific workflow role
  const { data: wfRoleUsers = [], isLoading: loadingWfRoleUsers } = useQuery({
    queryKey: ['workflowRoleUsers', expandedWfRoleId],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/hitl/roles/${expandedWfRoleId}/users`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: !!expandedWfRoleId
  });

  // Fetch all tenant users for assignment modal
  const { data: allTenantUsers = [] } = useQuery({
    queryKey: ['tenantUsersForAssign'],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/users/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: showUserAssignModal
  });

  // Fetch all workflow roles (for Users tab badges + manage modal)
  const { data: allWfRoles = [] } = useQuery({
    queryKey: ['allWorkflowRoles'],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/hitl/roles`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: canManageUsers
  });

  // Fetch workflow roles for a specific user (when modal is open)
  const { data: userWfRoles = [], isLoading: loadingUserWfRoles } = useQuery({
    queryKey: ['userWorkflowRoles', userWfRolesTarget?.user_id],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/hitl/users/${userWfRolesTarget.user_id}/roles`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    enabled: !!userWfRolesTarget?.user_id
  });

  // Create workflow role mutation
  const createWfRoleMutation = useMutation({
    mutationFn: async (roleData) => {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(`${API_BASE_URL}/api/v1/hitl/roles`, roleData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['workflowRoles']);
      setShowWfRoleModal(false);
      setWfRoleName('');
      setWfRoleDescription('');
      setEditingWfRole(null);
      showSuccessToast('Workflow role created successfully');
    },
    onError: (error) => {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to create workflow role');
    }
  });

  // Update workflow role mutation
  const updateWfRoleMutation = useMutation({
    mutationFn: async ({ roleId, roleData }) => {
      const token = localStorage.getItem('access_token');
      const response = await axios.put(`${API_BASE_URL}/api/v1/hitl/roles/${roleId}`, roleData, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['workflowRoles']);
      setShowWfRoleModal(false);
      setWfRoleName('');
      setWfRoleDescription('');
      setEditingWfRole(null);
      showSuccessToast('Workflow role updated successfully');
    },
    onError: (error) => {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update workflow role');
    }
  });

  // Delete workflow role mutation
  const deleteWfRoleMutation = useMutation({
    mutationFn: async (roleId) => {
      const token = localStorage.getItem('access_token');
      await axios.delete(`${API_BASE_URL}/api/v1/hitl/roles/${roleId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['workflowRoles']);
      setShowDeleteWfRoleConfirm(false);
      setWfRoleToDelete(null);
      if (expandedWfRoleId === wfRoleToDelete?.role_id) setExpandedWfRoleId(null);
      showSuccessToast('Workflow role deleted successfully');
    },
    onError: (error) => {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to delete workflow role');
    }
  });

  // Assign users to workflow role mutation
  const assignUsersToWfRoleMutation = useMutation({
    mutationFn: async ({ roleId, userIds }) => {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(`${API_BASE_URL}/api/v1/hitl/roles/${roleId}/users`, { user_ids: userIds }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries(['workflowRoleUsers', assignToRoleId]);
      queryClient.invalidateQueries(['workflowRoles']);
      setShowUserAssignModal(false);
      setSelectedUserIds([]);
      setUserAssignSearch('');
      showSuccessToast(data.message || 'Users assigned successfully');
    },
    onError: (error) => {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to assign users');
    }
  });

  // Remove user from workflow role mutation
  const removeUserFromWfRoleMutation = useMutation({
    mutationFn: async ({ roleId, userId }) => {
      const token = localStorage.getItem('access_token');
      await axios.delete(`${API_BASE_URL}/api/v1/hitl/roles/${roleId}/users/${userId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['workflowRoleUsers', expandedWfRoleId]);
      queryClient.invalidateQueries(['workflowRoles']);
      showSuccessToast('User removed from role');
    },
    onError: (error) => {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to remove user');
    }
  });

  // Workflow role handlers
  const handleCreateWfRole = () => {
    setEditingWfRole(null);
    setWfRoleName('');
    setWfRoleDescription('');
    setShowWfRoleModal(true);
  };

  const handleEditWfRole = (role) => {
    setEditingWfRole(role);
    setWfRoleName(role.role_name);
    setWfRoleDescription(role.role_description || '');
    setShowWfRoleModal(true);
  };

  const handleSaveWfRole = () => {
    if (!wfRoleName.trim()) {
      showErrorToast('Role name is required');
      return;
    }
    if (editingWfRole) {
      updateWfRoleMutation.mutate({
        roleId: editingWfRole.role_id,
        roleData: { role_name: wfRoleName, role_description: wfRoleDescription }
      });
    } else {
      createWfRoleMutation.mutate({ role_name: wfRoleName, role_description: wfRoleDescription });
    }
  };

  const handleDeleteWfRole = (role) => {
    setWfRoleToDelete(role);
    setShowDeleteWfRoleConfirm(true);
  };

  const confirmDeleteWfRole = () => {
    if (wfRoleToDelete) {
      deleteWfRoleMutation.mutate(wfRoleToDelete.role_id);
    }
  };

  const handleOpenUserAssign = (roleId) => {
    setAssignToRoleId(roleId);
    setSelectedUserIds([]);
    setUserAssignSearch('');
    setShowUserAssignModal(true);
  };

  const handleAssignUsers = () => {
    if (selectedUserIds.length === 0) {
      showErrorToast('Select at least one user');
      return;
    }
    assignUsersToWfRoleMutation.mutate({ roleId: assignToRoleId, userIds: selectedUserIds });
  };

  const toggleUserSelection = (userId) => {
    setSelectedUserIds(prev =>
      prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId]
    );
  };

  const filteredAssignUsers = allTenantUsers.filter(u => {
    if (!userAssignSearch) return true;
    const search = userAssignSearch.toLowerCase();
    return u.user_name.toLowerCase().includes(search) || u.email.toLowerCase().includes(search);
  }).filter(u => {
    // Exclude users already assigned to this role
    return !wfRoleUsers.some(ru => ru.user_id === u.user_id);
  });

  // --- User workflow roles (from Users tab) ---
  const handleManageUserWfRoles = (user) => {
    setUserWfRolesTarget(user);
    setUserWfRolesSearch('');
    setShowUserWfRolesModal(true);
  };

  const handleAddWfRoleToUser = (roleId) => {
    if (!userWfRolesTarget) return;
    const token = localStorage.getItem('access_token');
    axios.post(`${API_BASE_URL}/api/v1/hitl/roles/${roleId}/users`, { user_ids: [userWfRolesTarget.user_id] }, {
      headers: { Authorization: `Bearer ${token}` }
    }).then(() => {
      queryClient.invalidateQueries(['userWorkflowRoles', userWfRolesTarget.user_id]);
      queryClient.invalidateQueries(['allWorkflowRoles']);
      queryClient.invalidateQueries(['workflowRoles']);
      showSuccessToast('Workflow role assigned');
    }).catch(err => {
      showErrorToast(err.response?.data?.detail || 'Failed to assign role');
    });
  };

  const handleRemoveWfRoleFromUser = (roleId) => {
    if (!userWfRolesTarget) return;
    const token = localStorage.getItem('access_token');
    axios.delete(`${API_BASE_URL}/api/v1/hitl/roles/${roleId}/users/${userWfRolesTarget.user_id}`, {
      headers: { Authorization: `Bearer ${token}` }
    }).then(() => {
      queryClient.invalidateQueries(['userWorkflowRoles', userWfRolesTarget.user_id]);
      queryClient.invalidateQueries(['allWorkflowRoles']);
      queryClient.invalidateQueries(['workflowRoles']);
      showSuccessToast('Workflow role removed');
    }).catch(err => {
      showErrorToast(err.response?.data?.detail || 'Failed to remove role');
    });
  };

  const userWfRolesAssigned = new Set(userWfRoles.map(r => r.role_id));
  const filteredAvailableWfRoles = allWfRoles.filter(r => {
    if (userWfRolesAssigned.has(r.role_id)) return false;
    if (!userWfRolesSearch) return true;
    return r.role_name.toLowerCase().includes(userWfRolesSearch.toLowerCase());
  });

  const handleEdit = (user) => {
    setEditingUser({ ...user });
    setShowEditModal(true);
  };

  const handleSaveEdit = () => {
    if (!editingUser) return;

    const updates = {
      user_name: editingUser.user_name,
      email: editingUser.email,
      role: editingUser.role,
      is_active: editingUser.is_active
    };

    updateUserMutation.mutate({
      userId: editingUser.user_id,
      updates
    });
  };

  const handleDelete = (user) => {
    setUserToDelete(user);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    if (userToDelete) {
      deleteUserMutation.mutate(userToDelete.user_id);
    }
  };

  const handleActivationToggle = (user) => {
    updateUserMutation.mutate({
      userId: user.user_id,
      updates: { is_active: !user.is_active }
    });
  };

  const handleSendInvitation = () => {
    if (!inviteEmail) {
      showErrorToast('Please enter an email address');
      return;
    }
    createInvitationMutation.mutate({
      email: inviteEmail,
      role: inviteRole,
      message: inviteMessage || undefined
    });
  };

  const copyInvitationLink = (link) => {
    navigator.clipboard.writeText(link);
    showSuccessToast('Invitation link copied to clipboard');
  };

  const formatExpiryDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = date - now;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays < 0) return 'Expired';
    if (diffDays === 0) return 'Expires today';
    if (diffDays === 1) return 'Expires tomorrow';
    return `Expires in ${diffDays} days`;
  };

  if (!canManageUsers) {
    return (
      <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
          </div>
          <div className="ml-3">
            <p className="text-sm text-yellow-700">
              You need to be an Instance Admin or Tenant Admin to manage users.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (usersError) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Error loading users: {usersError.message}</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">
            {currentUser?.role === 'INSTANCE_ADMIN' ? 'User Management' : 'Team Members'}
          </h1>
          <button
            onClick={() => setShowInviteModal(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            <UserPlusIcon className="h-5 w-5 mr-2" />
            Invite User
          </button>
        </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('users')}
            className={`${
              activeTab === 'users'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm`}
          >
            Users
          </button>
          <button
            onClick={() => setActiveTab('invitations')}
            className={`${
              activeTab === 'invitations'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <EnvelopeIcon className="h-4 w-4 mr-1" />
            Invitations
          </button>
          <button
            onClick={() => setActiveTab('workflowRoles')}
            className={`${
              activeTab === 'workflowRoles'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <UserGroupIcon className="h-4 w-4 mr-1" />
            Workflow Roles
          </button>
          <button
            onClick={() => setActiveTab('permissions')}
            className={`${
              activeTab === 'permissions'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-2 px-1 border-b-2 font-medium text-sm`}
          >
            Role Permissions
          </button>
        </nav>
      </div>

      {activeTab === 'users' && (
        <div className="space-y-4">
          {/* Search and Filters */}
          <div className="flex flex-wrap gap-4">
            {/* Search Input */}
            <div className="relative flex-grow max-w-md">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by name or email..."
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-primary focus:border-primary sm:text-sm"
              />
            </div>

            {currentUser?.role === 'INSTANCE_ADMIN' && (
              <select
                value={selectedTenant}
                onChange={(e) => setSelectedTenant(e.target.value)}
                className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
              >
                <option value="">All Tenants</option>
                {tenants.map(tenant => (
                  <option key={tenant.tenant_id} value={tenant.tenant_id}>
                    {tenant.tenant_name}
                  </option>
                ))}
              </select>
            )}

            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
            >
              <option value="">All Roles</option>
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>

            <select
              value={activeFilter}
              onChange={(e) => setActiveFilter(e.target.value)}
              className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
            >
              <option value="">All Status</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </div>

          {/* Users Table */}
          {loadingUsers ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
          ) : (
            <div className="bg-white shadow sm:rounded-md overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      User
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Role
                    </th>
                    {currentUser?.role === 'INSTANCE_ADMIN' && (
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                        Tenant
                      </th>
                    )}
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Workflow Roles
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Last Login
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.map((user) => {
                    const RoleIcon = ROLE_ICONS[user.role] || UserIcon;
                    const canEdit = user.user_id !== currentUser.userId || currentUser.role === 'INSTANCE_ADMIN';
                    const canDelete = user.user_id !== currentUser.userId && user.role !== 'INSTANCE_ADMIN';
                    const canToggleActivation = user.role !== 'INSTANCE_ADMIN';

                    return (
                      <tr key={user.user_id}>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <div>
                            <div className="text-sm font-medium text-gray-900">{user.user_name}</div>
                            <div className="text-sm text-gray-500 truncate max-w-[200px]">{user.email}</div>
                          </div>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[user.role] || 'bg-gray-100 text-gray-800'}`}>
                            <RoleIcon className="w-3 h-3 mr-1 flex-shrink-0" />
                            <span className="truncate">{ROLE_LABELS[user.role] || user.role}</span>
                          </span>
                        </td>
                        {currentUser?.role === 'INSTANCE_ADMIN' && (
                          <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                            {user.tenant_name || 'N/A'}
                          </td>
                        )}
                        <td className="px-4 py-4">
                          <button
                            onClick={() => handleManageUserWfRoles(user)}
                            className="inline-flex items-center gap-1 text-xs text-gray-600 hover:text-primary transition-colors group"
                            title="Manage workflow roles"
                          >
                            {(() => {
                              const userRoles = allWfRoles.filter(r =>
                                r.user_count > 0
                              );
                              // We don't have per-user role data in the list query, so show a manage link
                              return (
                                <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md border border-gray-200 group-hover:border-primary group-hover:bg-primary-10 text-xs">
                                  <UserGroupIcon className="w-3.5 h-3.5" />
                                  Manage
                                </span>
                              );
                            })()}
                          </button>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {user.is_active ? (
                              <>
                                <CheckCircleIcon className="w-3 h-3 mr-1" />
                                Active
                              </>
                            ) : (
                              <>
                                <XCircleIcon className="w-3 h-3 mr-1" />
                                Inactive
                              </>
                            )}
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {user.last_login_at ? formatDateTime(user.last_login_at) : 'Never'}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <div className="flex justify-end space-x-1">
                            {canToggleActivation && (
                              <button
                                onClick={() => handleActivationToggle(user)}
                                className={`inline-flex items-center p-1 border border-transparent rounded-full ${
                                  user.is_active
                                    ? 'text-red-600 hover:bg-red-100'
                                    : 'text-green-600 hover:bg-green-100'
                                }`}
                                title={user.is_active ? 'Deactivate' : 'Activate'}
                              >
                                {user.is_active ? (
                                  <XCircleIcon className="h-5 w-5" />
                                ) : (
                                  <CheckCircleIcon className="h-5 w-5" />
                                )}
                              </button>
                            )}
                            {canEdit && (
                              <button
                                onClick={() => handleEdit(user)}
                                className="inline-flex items-center p-1 border border-transparent rounded-full text-primary hover:bg-primary-10"
                              >
                                <PencilIcon className="h-5 w-5" />
                              </button>
                            )}
                            {canDelete && (
                              <button
                                onClick={() => handleDelete(user)}
                                className="inline-flex items-center p-1 border border-transparent rounded-full text-red-600 hover:bg-red-100"
                              >
                                <TrashIcon className="h-5 w-5" />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'invitations' && (
        <div className="space-y-4">
          {/* Invitation Status Filter */}
          <div className="flex space-x-4">
            <select
              value={invitationStatusFilter}
              onChange={(e) => setInvitationStatusFilter(e.target.value)}
              className="block w-48 rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
            >
              <option value="">All Invitations</option>
              <option value="pending">Pending</option>
              <option value="accepted">Accepted</option>
              <option value="expired">Expired</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {/* Invitations Table */}
          {loadingInvitations ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
          ) : invitations.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-lg shadow">
              <EnvelopeIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No invitations</h3>
              <p className="mt-1 text-sm text-gray-500">
                {invitationStatusFilter ? `No ${invitationStatusFilter} invitations found.` : 'Get started by inviting a new user.'}
              </p>
              <div className="mt-6">
                <button
                  onClick={() => setShowInviteModal(true)}
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg"
                >
                  <UserPlusIcon className="h-5 w-5 mr-2" />
                  Invite User
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-white shadow sm:rounded-md overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Email
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Role
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Invited By
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Expiry
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {invitations.map((invitation) => {
                    const RoleIcon = ROLE_ICONS[invitation.role] || UserIcon;
                    const isPending = invitation.status === 'pending';

                    return (
                      <tr key={invitation.invitation_id}>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <div className="text-sm font-medium text-gray-900 truncate max-w-[200px]">{invitation.email}</div>
                          {invitation.message && (
                            <div className="text-xs text-gray-500 truncate max-w-[200px]" title={invitation.message}>
                              "{invitation.message}"
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[invitation.role] || 'bg-gray-100 text-gray-800'}`}>
                            <RoleIcon className="w-3 h-3 mr-1 flex-shrink-0" />
                            <span className="truncate">{ROLE_LABELS[invitation.role] || invitation.role}</span>
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${INVITATION_STATUS_COLORS[invitation.status]}`}>
                            {invitation.status === 'pending' && <ClockIcon className="w-3 h-3 mr-1" />}
                            {invitation.status === 'accepted' && <CheckCircleIcon className="w-3 h-3 mr-1" />}
                            {invitation.status === 'expired' && <XCircleIcon className="w-3 h-3 mr-1" />}
                            {invitation.status === 'cancelled' && <XCircleIcon className="w-3 h-3 mr-1" />}
                            {invitation.status.charAt(0).toUpperCase() + invitation.status.slice(1)}
                          </span>
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {invitation.inviter_name || 'Unknown'}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-500">
                          {isPending ? (
                            <span className="flex items-center">
                              <ClockIcon className="w-4 h-4 mr-1 flex-shrink-0" />
                              <span className="truncate">{formatExpiryDate(invitation.expires_at)}</span>
                            </span>
                          ) : invitation.accepted_at ? (
                            <span className="truncate">Accepted {formatDateTime(invitation.accepted_at)}</span>
                          ) : (
                            <span className="truncate">{formatDateTime(invitation.expires_at)}</span>
                          )}
                        </td>
                        <td className="px-4 py-4 whitespace-nowrap text-right text-sm font-medium">
                          <div className="flex justify-end space-x-1">
                            {isPending && invitation.invitation_link && (
                              <>
                                <button
                                  onClick={() => copyInvitationLink(invitation.invitation_link)}
                                  className="inline-flex items-center p-1 border border-transparent rounded-full text-gray-600 hover:bg-gray-100"
                                  title="Copy invitation link"
                                >
                                  <ClipboardDocumentIcon className="h-5 w-5" />
                                </button>
                                <button
                                  onClick={() => resendInvitationMutation.mutate(invitation.invitation_id)}
                                  disabled={resendInvitationMutation.isLoading}
                                  className="inline-flex items-center p-1 border border-transparent rounded-full text-primary hover:bg-primary-10"
                                  title="Resend invitation"
                                >
                                  <ArrowPathIcon className="h-5 w-5" />
                                </button>
                                <button
                                  onClick={() => cancelInvitationMutation.mutate(invitation.invitation_id)}
                                  disabled={cancelInvitationMutation.isLoading}
                                  className="inline-flex items-center p-1 border border-transparent rounded-full text-red-600 hover:bg-red-100"
                                  title="Cancel invitation"
                                >
                                  <XCircleIcon className="h-5 w-5" />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'workflowRoles' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-500">
              Workflow roles control who receives tasks in flow executions. Users can be assigned to multiple workflow roles.
            </p>
            <button
              onClick={handleCreateWfRole}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              <PlusIcon className="h-5 w-5 mr-2" />
              Add Workflow Role
            </button>
          </div>

          {loadingWfRoles ? (
            <div className="flex justify-center items-center h-64">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
          ) : workflowRoles.length === 0 ? (
            <div className="text-center py-12 bg-white rounded-lg shadow">
              <UserGroupIcon className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">No workflow roles</h3>
              <p className="mt-1 text-sm text-gray-500">Create workflow roles to assign tasks to groups of users in your flows.</p>
              <div className="mt-6">
                <button
                  onClick={handleCreateWfRole}
                  className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg"
                >
                  <PlusIcon className="h-5 w-5 mr-2" />
                  Add Workflow Role
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-white shadow sm:rounded-md">
              <ul className="divide-y divide-gray-200">
                {workflowRoles.map((role) => {
                  const isExpanded = expandedWfRoleId === role.role_id;
                  return (
                    <li key={role.role_id}>
                      <div className={`px-4 py-4 ${isExpanded ? 'bg-gray-50' : ''}`}>
                        <div
                          className="flex items-center justify-between cursor-pointer"
                          onClick={() => setExpandedWfRoleId(isExpanded ? null : role.role_id)}
                        >
                          <div className="flex items-center min-w-0 flex-1">
                            <div className={`mr-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
                              <ChevronDownIcon className="h-5 w-5 text-gray-400" />
                            </div>
                            <div className="flex items-center justify-center h-8 w-8 rounded-full bg-blue-100 mr-3 flex-shrink-0">
                              <UserGroupIcon className="h-4 w-4 text-blue-600" />
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center">
                                <span className="text-sm font-medium text-gray-900">{role.role_name}</span>
                                <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                  {role.user_count} user{role.user_count !== 1 ? 's' : ''}
                                </span>
                              </div>
                              {role.role_description && (
                                <p className="mt-1 text-sm text-gray-500 truncate">{role.role_description}</p>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center space-x-1 ml-4" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => handleEditWfRole(role)}
                              className="inline-flex items-center p-1.5 border border-transparent rounded-md text-primary hover:bg-primary-10"
                              title="Edit role"
                            >
                              <PencilIcon className="h-4 w-4" />
                            </button>
                            <button
                              onClick={() => handleDeleteWfRole(role)}
                              className="inline-flex items-center p-1.5 border border-transparent rounded-md text-red-600 hover:bg-red-100"
                              title="Delete role"
                            >
                              <TrashIcon className="h-4 w-4" />
                            </button>
                          </div>
                        </div>

                        {/* Expanded: show assigned users */}
                        {isExpanded && (
                          <div className="mt-4 ml-8 border-t pt-4">
                            <div className="flex justify-between items-center mb-3">
                              <h4 className="text-sm font-medium text-gray-700">Assigned Users</h4>
                              <button
                                onClick={() => handleOpenUserAssign(role.role_id)}
                                className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
                              >
                                <UserPlusIcon className="h-4 w-4 mr-1" />
                                Add Users
                              </button>
                            </div>
                            {loadingWfRoleUsers ? (
                              <div className="flex justify-center py-4">
                                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                              </div>
                            ) : wfRoleUsers.length === 0 ? (
                              <p className="text-sm text-gray-500 py-2">No users assigned to this role.</p>
                            ) : (
                              <div className="space-y-2">
                                {wfRoleUsers.map((u) => (
                                  <div key={u.user_id} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-md">
                                    <div>
                                      <span className="text-sm font-medium text-gray-900">{u.user_name}</span>
                                      <span className="ml-2 text-sm text-gray-500">{u.email}</span>
                                    </div>
                                    <button
                                      onClick={() => removeUserFromWfRoleMutation.mutate({ roleId: role.role_id, userId: u.user_id })}
                                      className="inline-flex items-center p-1 text-red-500 hover:bg-red-100 rounded-full"
                                      title="Remove from role"
                                    >
                                      <XCircleIcon className="h-4 w-4" />
                                    </button>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}

      {activeTab === 'permissions' && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(ROLE_PERMISSIONS).map(([role, info]) => {
            const RoleIcon = ROLE_ICONS[role] || UserIcon;
            return (
              <div key={role} className="bg-white overflow-hidden shadow rounded-lg">
                <div className="px-4 py-5 sm:p-6">
                  <div className="flex items-center mb-4">
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${ROLE_COLORS[role]}`}>
                      <RoleIcon className="w-4 h-4 mr-2" />
                      {ROLE_LABELS[role]}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 mb-4">{info.description}</p>
                  <ul className="space-y-2">
                    {info.permissions.map((permission, index) => (
                      <li key={index} className="flex items-start">
                        <CheckCircleIcon className="flex-shrink-0 h-4 w-4 text-green-500 mt-0.5" />
                        <span className="ml-2 text-sm text-gray-700">{permission}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            );
          })}
        </div>
      )}
      </div>

      {/* Invite User Modal */}
      {showInviteModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" onClick={() => setShowInviteModal(false)}>
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-primary-10 sm:mx-0 sm:h-10 sm:w-10">
                    <UserPlusIcon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="ml-4 text-lg leading-6 font-medium text-gray-900">
                    Invite User
                  </h3>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Email Address</label>
                    <input
                      type="email"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                      placeholder="user@example.com"
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Role</label>
                    <select
                      value={inviteRole}
                      onChange={(e) => setInviteRole(e.target.value)}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    >
                      {Object.entries(ROLE_LABELS).map(([value, label]) => (
                        <option
                          key={value}
                          value={value}
                          disabled={currentUser.role === 'TENANT_ADMIN' && value === 'INSTANCE_ADMIN'}
                        >
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Personal Message <span className="text-gray-400">(optional)</span>
                    </label>
                    <textarea
                      value={inviteMessage}
                      onChange={(e) => setInviteMessage(e.target.value)}
                      rows={3}
                      placeholder="Add a personal note to the invitation..."
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    />
                  </div>
                  <div className="bg-blue-50 rounded-md p-3">
                    <p className="text-sm text-blue-700">
                      The user will receive an email with a link to accept the invitation and create their account. The invitation will expire in 7 days.
                    </p>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  onClick={handleSendInvitation}
                  disabled={createInvitationMutation.isLoading || !inviteEmail}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-gradient-primary text-base font-medium text-white hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createInvitationMutation.isLoading ? 'Sending...' : 'Send Invitation'}
                </button>
                <button
                  onClick={() => setShowInviteModal(false)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {showEditModal && editingUser && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" onClick={() => setShowEditModal(false)}>
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
                  Edit User
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Name</label>
                    <input
                      type="text"
                      value={editingUser.user_name}
                      onChange={(e) => setEditingUser({ ...editingUser, user_name: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Email</label>
                    <input
                      type="email"
                      value={editingUser.email}
                      onChange={(e) => setEditingUser({ ...editingUser, email: e.target.value })}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Role</label>
                    <select
                      value={editingUser.role}
                      onChange={(e) => setEditingUser({ ...editingUser, role: e.target.value })}
                      disabled={editingUser.user_id === currentUser.userId && currentUser.role !== 'INSTANCE_ADMIN'}
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    >
                      {Object.entries(ROLE_LABELS).map(([value, label]) => (
                        <option
                          key={value}
                          value={value}
                          disabled={currentUser.role === 'TENANT_ADMIN' && value === 'INSTANCE_ADMIN'}
                        >
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={editingUser.is_active}
                      onChange={(e) => setEditingUser({ ...editingUser, is_active: e.target.checked })}
                      disabled={editingUser.role === 'INSTANCE_ADMIN'}
                      className="h-4 w-4 text-primary focus:ring-primary border-gray-300 rounded"
                    />
                    <label className="ml-2 block text-sm text-gray-900">
                      Active
                    </label>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  onClick={handleSaveEdit}
                  disabled={updateUserMutation.isLoading}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-gradient-primary text-base font-medium text-white hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:ml-3 sm:w-auto sm:text-sm"
                >
                  {updateUserMutation.isLoading ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => setShowEditModal(false)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && userToDelete && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" onClick={() => setShowDeleteConfirm(false)}>
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                    <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
                  </div>
                  <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                    <h3 className="text-lg leading-6 font-medium text-gray-900">
                      Delete User
                    </h3>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        Are you sure you want to delete user "{userToDelete.user_name}"? This action cannot be undone.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  onClick={confirmDelete}
                  disabled={deleteUserMutation.isLoading}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  {deleteUserMutation.isLoading ? 'Deleting...' : 'Delete'}
                </button>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add/Edit Workflow Role Modal */}
      {showWfRoleModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" onClick={() => setShowWfRoleModal(false)}>
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-primary-10 sm:mx-0 sm:h-10 sm:w-10">
                    <UserGroupIcon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="ml-4 text-lg leading-6 font-medium text-gray-900">
                    {editingWfRole ? 'Edit Workflow Role' : 'Add Workflow Role'}
                  </h3>
                </div>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Role Name</label>
                    <input
                      type="text"
                      value={wfRoleName}
                      onChange={(e) => setWfRoleName(e.target.value)}
                      placeholder="e.g. Approvers, Reviewers"
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Description <span className="text-gray-400">(optional)</span>
                    </label>
                    <textarea
                      value={wfRoleDescription}
                      onChange={(e) => setWfRoleDescription(e.target.value)}
                      rows={3}
                      placeholder="Describe what this workflow role is for..."
                      className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                    />
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  onClick={handleSaveWfRole}
                  disabled={createWfRoleMutation.isLoading || updateWfRoleMutation.isLoading || !wfRoleName.trim()}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-gradient-primary text-base font-medium text-white hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {(createWfRoleMutation.isLoading || updateWfRoleMutation.isLoading) ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={() => setShowWfRoleModal(false)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Delete Workflow Role Confirmation Modal */}
      {showDeleteWfRoleConfirm && wfRoleToDelete && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" onClick={() => setShowDeleteWfRoleConfirm(false)}>
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                    <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
                  </div>
                  <div className="mt-3 text-center sm:mt-0 sm:ml-4 sm:text-left">
                    <h3 className="text-lg leading-6 font-medium text-gray-900">Delete Workflow Role</h3>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        Are you sure you want to delete the workflow role "{wfRoleToDelete.role_name}"?
                        {wfRoleToDelete.user_count > 0 && (
                          <span className="block mt-1 text-red-600">
                            This role has {wfRoleToDelete.user_count} assigned user(s). They will be unassigned.
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  onClick={confirmDeleteWfRole}
                  disabled={deleteWfRoleMutation.isLoading}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-red-600 text-base font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  {deleteWfRoleMutation.isLoading ? 'Deleting...' : 'Delete'}
                </button>
                <button
                  onClick={() => setShowDeleteWfRoleConfirm(false)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Assign Users to Workflow Role Modal */}
      {showUserAssignModal && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" onClick={() => setShowUserAssignModal(false)}>
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-primary-10 sm:mx-0 sm:h-10 sm:w-10">
                    <UserPlusIcon className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="ml-4 text-lg leading-6 font-medium text-gray-900">Add Users to Role</h3>
                </div>
                <div className="space-y-4">
                  <div className="relative">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
                    </div>
                    <input
                      type="text"
                      value={userAssignSearch}
                      onChange={(e) => setUserAssignSearch(e.target.value)}
                      placeholder="Search by name or email..."
                      className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary sm:text-sm"
                    />
                  </div>
                  {selectedUserIds.length > 0 && (
                    <p className="text-sm text-primary font-medium">{selectedUserIds.length} user(s) selected</p>
                  )}
                  <div className="max-h-64 overflow-y-auto border rounded-md divide-y divide-gray-200">
                    {filteredAssignUsers.length === 0 ? (
                      <p className="p-4 text-sm text-gray-500 text-center">No users available to assign</p>
                    ) : (
                      filteredAssignUsers.map((u) => (
                        <label
                          key={u.user_id}
                          className="flex items-center px-4 py-3 hover:bg-gray-50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedUserIds.includes(u.user_id)}
                            onChange={() => toggleUserSelection(u.user_id)}
                            className="h-4 w-4 text-primary focus:ring-primary border-gray-300 rounded"
                          />
                          <div className="ml-3">
                            <span className="text-sm font-medium text-gray-900">{u.user_name}</span>
                            <span className="ml-2 text-sm text-gray-500">{u.email}</span>
                          </div>
                        </label>
                      ))
                    )}
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  onClick={handleAssignUsers}
                  disabled={assignUsersToWfRoleMutation.isLoading || selectedUserIds.length === 0}
                  className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-gradient-primary text-base font-medium text-white hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {assignUsersToWfRoleMutation.isLoading ? 'Assigning...' : `Assign ${selectedUserIds.length} User(s)`}
                </button>
                <button
                  onClick={() => setShowUserAssignModal(false)}
                  className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Manage Workflow Roles for a User Modal */}
      {showUserWfRolesModal && userWfRolesTarget && (
        <div className="fixed z-10 inset-0 overflow-y-auto">
          <div className="flex items-end justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
            <div className="fixed inset-0 transition-opacity" onClick={() => { setShowUserWfRolesModal(false); setUserWfRolesTarget(null); }}>
              <div className="absolute inset-0 bg-gray-500 opacity-75"></div>
            </div>
            <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
              <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex-shrink-0 flex items-center justify-center h-12 w-12 rounded-full bg-primary-10 sm:mx-0 sm:h-10 sm:w-10">
                    <UserGroupIcon className="h-6 w-6 text-primary" />
                  </div>
                  <div className="ml-4">
                    <h3 className="text-lg leading-6 font-medium text-gray-900">Workflow Roles</h3>
                    <p className="text-sm text-gray-500">{userWfRolesTarget.user_name} ({userWfRolesTarget.email})</p>
                  </div>
                </div>

                {/* Currently assigned roles */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-2">Assigned Roles</label>
                  {loadingUserWfRoles ? (
                    <div className="flex justify-center py-4">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                    </div>
                  ) : userWfRoles.length === 0 ? (
                    <p className="text-sm text-gray-400 py-2">No workflow roles assigned</p>
                  ) : (
                    <div className="space-y-2">
                      {userWfRoles.map((role) => (
                        <div key={role.role_id} className="flex items-center justify-between py-2 px-3 bg-blue-50 border border-blue-200 rounded-md">
                          <div className="flex items-center">
                            <UserGroupIcon className="w-4 h-4 text-blue-600 mr-2" />
                            <span className="text-sm font-medium text-blue-900">{role.role_name}</span>
                            {role.role_description && (
                              <span className="ml-2 text-xs text-blue-600 truncate max-w-[200px]">{role.role_description}</span>
                            )}
                          </div>
                          <button
                            onClick={() => handleRemoveWfRoleFromUser(role.role_id)}
                            className="inline-flex items-center p-1 text-red-500 hover:bg-red-100 rounded-full"
                            title="Remove role"
                          >
                            <XCircleIcon className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Add roles */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Add Role</label>
                  {allWfRoles.length === 0 ? (
                    <p className="text-sm text-gray-400">No workflow roles available. Create roles in the Workflow Roles tab.</p>
                  ) : filteredAvailableWfRoles.length === 0 && !userWfRolesSearch ? (
                    <p className="text-sm text-gray-400">All roles are already assigned</p>
                  ) : (
                    <>
                      {allWfRoles.length > 3 && (
                        <div className="relative mb-2">
                          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <MagnifyingGlassIcon className="h-4 w-4 text-gray-400" />
                          </div>
                          <input
                            type="text"
                            value={userWfRolesSearch}
                            onChange={(e) => setUserWfRolesSearch(e.target.value)}
                            placeholder="Search roles..."
                            className="block w-full pl-9 pr-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-1 focus:ring-primary focus:border-primary"
                          />
                        </div>
                      )}
                      <div className="max-h-40 overflow-y-auto space-y-1">
                        {filteredAvailableWfRoles.map((role) => (
                          <button
                            key={role.role_id}
                            onClick={() => handleAddWfRoleToUser(role.role_id)}
                            className="w-full flex items-center justify-between py-2 px-3 rounded-md border border-gray-200 hover:border-primary hover:bg-primary-10 transition-colors text-left"
                          >
                            <div className="flex items-center">
                              <PlusIcon className="w-4 h-4 text-gray-400 mr-2" />
                              <span className="text-sm text-gray-700">{role.role_name}</span>
                            </div>
                            <span className="text-xs text-gray-400">{role.user_count} user{role.user_count !== 1 ? 's' : ''}</span>
                          </button>
                        ))}
                        {filteredAvailableWfRoles.length === 0 && userWfRolesSearch && (
                          <p className="text-sm text-gray-400 text-center py-2">No matching roles</p>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
                <button
                  onClick={() => { setShowUserWfRolesModal(false); setUserWfRolesTarget(null); }}
                  className="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary sm:w-auto sm:text-sm"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default UserManagement;
