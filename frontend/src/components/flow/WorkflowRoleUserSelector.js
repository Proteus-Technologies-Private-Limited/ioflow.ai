import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import {
  MagnifyingGlassIcon,
  XMarkIcon,
  ChevronRightIcon,
  UserGroupIcon,
  UserIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const WorkflowRoleUserSelector = ({
  assignmentConfig = { type: 'user', users: [], roles: [] },
  onAssignmentChange,
  className = '',
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState(assignmentConfig.type === 'role' ? 'roles' : 'users');
  const [roles, setRoles] = useState([]);
  const [users, setUsers] = useState([]);
  const [loadingRoles, setLoadingRoles] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Local selection state (committed on Done)
  const [selectedUsers, setSelectedUsers] = useState(assignmentConfig.users || []);
  const [selectedRoles, setSelectedRoles] = useState(assignmentConfig.roles || []);

  useEffect(() => {
    if (isOpen) {
      loadData();
      setSelectedUsers(assignmentConfig.users || []);
      setSelectedRoles(assignmentConfig.roles || []);
      setActiveTab(assignmentConfig.type === 'role' ? 'roles' : 'users');
      setSearchTerm('');
    }
  }, [isOpen]);

  const loadData = async () => {
    const token = localStorage.getItem('token') || localStorage.getItem('access_token');
    const headers = { Authorization: `Bearer ${token}` };

    setLoadingRoles(true);
    setLoadingUsers(true);

    try {
      const [rolesRes, usersRes] = await Promise.all([
        axios.get(`${API_BASE_URL}/api/v1/hitl/roles`, { headers }),
        axios.get(`${API_BASE_URL}/api/v1/users/`, { headers }),
      ]);
      setRoles(rolesRes.data || []);
      setUsers(usersRes.data || []);
    } catch (error) {
      console.error('Failed to load roles/users:', error);
    } finally {
      setLoadingRoles(false);
      setLoadingUsers(false);
    }
  };

  const filteredRoles = useMemo(() => {
    if (!searchTerm) return roles;
    const term = searchTerm.toLowerCase();
    return roles.filter(r =>
      r.role_name.toLowerCase().includes(term) ||
      (r.role_description || '').toLowerCase().includes(term)
    );
  }, [roles, searchTerm]);

  const filteredUsers = useMemo(() => {
    if (!searchTerm) return users;
    const term = searchTerm.toLowerCase();
    return users.filter(u =>
      u.user_name.toLowerCase().includes(term) ||
      u.email.toLowerCase().includes(term)
    );
  }, [users, searchTerm]);

  const toggleUser = (userId) => {
    setSelectedUsers(prev =>
      prev.includes(userId) ? prev.filter(id => id !== userId) : [...prev, userId]
    );
    // When selecting users, clear roles (mutually exclusive)
    setSelectedRoles([]);
  };

  const toggleRole = (roleId) => {
    setSelectedRoles(prev =>
      prev.includes(roleId) ? prev.filter(id => id !== roleId) : [...prev, roleId]
    );
    // When selecting roles, clear users (mutually exclusive)
    setSelectedUsers([]);
  };

  const handleDone = () => {
    const hasRoles = selectedRoles.length > 0;
    const hasUsers = selectedUsers.length > 0;

    onAssignmentChange({
      type: hasRoles ? 'role' : 'user',
      users: hasRoles ? [] : selectedUsers,
      roles: hasUsers ? [] : selectedRoles,
    });
    setIsOpen(false);
  };

  const handleTabSwitch = (tab) => {
    setActiveTab(tab);
    setSearchTerm('');
  };

  // Summary text for the trigger button
  const getSummaryText = () => {
    if (assignmentConfig.type === 'role' && assignmentConfig.roles?.length > 0) {
      const count = assignmentConfig.roles.length;
      return `${count} workflow role${count !== 1 ? 's' : ''} selected`;
    }
    if (assignmentConfig.type === 'user' && assignmentConfig.users?.length > 0) {
      const count = assignmentConfig.users.length;
      return `${count} user${count !== 1 ? 's' : ''} selected`;
    }
    return 'Select assignment...';
  };

  const hasSelection = assignmentConfig.users?.length > 0 || assignmentConfig.roles?.length > 0;

  return (
    <div className={className}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={`w-full flex items-center justify-between px-3 py-2.5 border rounded-lg text-left transition-colors ${
          hasSelection
            ? 'border-primary bg-primary-10 hover:bg-blue-100'
            : 'border-gray-300 bg-white hover:bg-gray-50'
        }`}
      >
        <div className="flex items-center min-w-0">
          {assignmentConfig.type === 'role' && assignmentConfig.roles?.length > 0 ? (
            <UserGroupIcon className="w-5 h-5 text-primary mr-2 flex-shrink-0" />
          ) : assignmentConfig.users?.length > 0 ? (
            <UserIcon className="w-5 h-5 text-primary mr-2 flex-shrink-0" />
          ) : (
            <UserIcon className="w-5 h-5 text-gray-400 mr-2 flex-shrink-0" />
          )}
          <span className={`text-sm truncate ${hasSelection ? 'text-gray-900 font-medium' : 'text-gray-500'}`}>
            {getSummaryText()}
          </span>
        </div>
        <ChevronRightIcon className="w-5 h-5 text-gray-400 ml-2 flex-shrink-0" />
      </button>

      {/* Selection Panel */}
      {isOpen && (
        <div className="fixed inset-0 z-[100] overflow-hidden">
          <div className="absolute inset-0 bg-gray-500 bg-opacity-75" onClick={() => setIsOpen(false)} />

          <div className="absolute right-0 top-0 h-full w-full max-w-md bg-white shadow-xl flex flex-col">
            {/* Header */}
            <div className="px-6 py-4 border-b flex-shrink-0">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-gray-900">Select Assignment</h2>
                <button onClick={() => setIsOpen(false)} className="p-1 hover:bg-gray-100 rounded">
                  <XMarkIcon className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              {/* Search */}
              <div className="relative">
                <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder={activeTab === 'roles' ? 'Search workflow roles...' : 'Search users...'}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b flex-shrink-0">
              <button
                onClick={() => handleTabSwitch('roles')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'roles'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700'
                }`}
              >
                By Role
                {selectedRoles.length > 0 && (
                  <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-blue-600 rounded-full">
                    {selectedRoles.length}
                  </span>
                )}
              </button>
              <button
                onClick={() => handleTabSwitch('users')}
                className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'users'
                    ? 'text-blue-600 border-blue-600'
                    : 'text-gray-500 border-transparent hover:text-gray-700'
                }`}
              >
                By User
                {selectedUsers.length > 0 && (
                  <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-blue-600 rounded-full">
                    {selectedUsers.length}
                  </span>
                )}
              </button>
            </div>

            {/* Info banner */}
            {((activeTab === 'users' && selectedRoles.length > 0) ||
              (activeTab === 'roles' && selectedUsers.length > 0)) && (
              <div className="px-4 py-2 bg-yellow-50 border-b border-yellow-100 text-xs text-yellow-700 flex-shrink-0">
                Selecting here will clear the other tab's selection. Assignment is either by role or by user.
              </div>
            )}

            {/* Content */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === 'roles' ? (
                <div className="p-4 space-y-2">
                  {loadingRoles ? (
                    <div className="flex justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    </div>
                  ) : filteredRoles.length === 0 ? (
                    <div className="text-center py-12">
                      <UserGroupIcon className="mx-auto h-10 w-10 text-gray-300" />
                      <p className="mt-2 text-sm text-gray-500">
                        {searchTerm ? 'No roles match your search' : 'No workflow roles defined. Create roles in User Management.'}
                      </p>
                    </div>
                  ) : (
                    filteredRoles.map((role) => {
                      const isSelected = selectedRoles.includes(role.role_id);
                      return (
                        <button
                          key={role.role_id}
                          onClick={() => toggleRole(role.role_id)}
                          className={`w-full flex items-center px-4 py-3 rounded-lg border transition-colors text-left ${
                            isSelected
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-200 hover:bg-gray-50'
                          }`}
                        >
                          <div className={`w-5 h-5 rounded border flex items-center justify-center mr-3 flex-shrink-0 ${
                            isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-300'
                          }`}>
                            {isSelected && <CheckIcon className="w-3.5 h-3.5 text-white" />}
                          </div>
                          <UserGroupIcon className="w-5 h-5 text-gray-400 mr-3 flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-gray-900">{role.role_name}</div>
                            {role.role_description && (
                              <div className="text-xs text-gray-500 truncate">{role.role_description}</div>
                            )}
                          </div>
                          <span className="ml-2 text-xs text-gray-400 flex-shrink-0">
                            {role.user_count} user{role.user_count !== 1 ? 's' : ''}
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>
              ) : (
                <div className="p-4 space-y-2">
                  {loadingUsers ? (
                    <div className="flex justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    </div>
                  ) : filteredUsers.length === 0 ? (
                    <div className="text-center py-12">
                      <UserIcon className="mx-auto h-10 w-10 text-gray-300" />
                      <p className="mt-2 text-sm text-gray-500">
                        {searchTerm ? 'No users match your search' : 'No users found'}
                      </p>
                    </div>
                  ) : (
                    filteredUsers.map((user) => {
                      const isSelected = selectedUsers.includes(user.user_id);
                      return (
                        <button
                          key={user.user_id}
                          onClick={() => toggleUser(user.user_id)}
                          className={`w-full flex items-center px-4 py-3 rounded-lg border transition-colors text-left ${
                            isSelected
                              ? 'border-blue-500 bg-blue-50'
                              : 'border-gray-200 hover:bg-gray-50'
                          }`}
                        >
                          <div className={`w-5 h-5 rounded border flex items-center justify-center mr-3 flex-shrink-0 ${
                            isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-300'
                          }`}>
                            {isSelected && <CheckIcon className="w-3.5 h-3.5 text-white" />}
                          </div>
                          <UserIcon className="w-5 h-5 text-gray-400 mr-3 flex-shrink-0" />
                          <div className="min-w-0 flex-1">
                            <div className="text-sm font-medium text-gray-900">{user.user_name}</div>
                            <div className="text-xs text-gray-500 truncate">{user.email}</div>
                          </div>
                        </button>
                      );
                    })
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t bg-gray-50 flex items-center justify-between flex-shrink-0">
              <span className="text-sm text-gray-500">
                {selectedRoles.length > 0
                  ? `${selectedRoles.length} role${selectedRoles.length !== 1 ? 's' : ''} selected`
                  : selectedUsers.length > 0
                  ? `${selectedUsers.length} user${selectedUsers.length !== 1 ? 's' : ''} selected`
                  : 'No selection'}
              </span>
              <div className="flex space-x-3">
                <button
                  onClick={() => setIsOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDone}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700"
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
};

export default WorkflowRoleUserSelector;
