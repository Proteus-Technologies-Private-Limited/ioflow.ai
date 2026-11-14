import React, { useState, Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import {
  XMarkIcon,
  PlusIcon,
  LinkIcon,
  TrashIcon,
  CogIcon,
  ServerIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClockIcon,
  PencilIcon,
  CheckIcon
} from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const InstanceManagementModal = ({ 
  isOpen, 
  onClose, 
  application,
  instances = [],
  subscriptions = {},
  onConnect,
  onDisconnect,
  onRefresh
}) => {
  const [creatingInstance, setCreatingInstance] = useState(false);
  const [instanceName, setInstanceName] = useState('');
  const [deletingInstance, setDeletingInstance] = useState(null);
  const [editingInstance, setEditingInstance] = useState(null);
  const [editName, setEditName] = useState('');

  const createNewInstance = async () => {
    if (!instanceName.trim()) {
      showErrorToast('Please enter an instance name');
      return;
    }

    setCreatingInstance(true);
    try {
      const token = localStorage.getItem('access_token');
      
      // Find the seed app ID - it's the one with is_seed_app=true
      let seedAppId;
      
      if (instances && instances.length > 0) {
        const seedApp = instances.find(inst => inst.is_seed_app);
        if (seedApp) {
          seedAppId = seedApp.app_id;
        } else {
          // If no seed app marked, use the one with instance_number = 1
          const firstInstance = instances.find(inst => inst.instance_number === 1) || instances[0];
          seedAppId = firstInstance.parent_seed_app_id || firstInstance.app_id;
        }
      } else if (application) {
        // Use the application prop if no instances
        seedAppId = application.is_seed_app ? application.app_id : (application.parent_seed_app_id || application.app_id);
      }
      
      if (!seedAppId) {
        throw new Error('Could not determine seed application ID');
      }
      
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/${seedAppId}/create-instance`,
        { instance_name: instanceName },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      showSuccessToast(`Created instance: ${instanceName}`);
      setInstanceName('');
      
      // Refresh the instances list - this will update both the modal and main UI
      if (onRefresh) {
        await onRefresh();
      }
      
      // The new instance should now be visible in the modal
    } catch (error) {
      console.error('Error creating instance:', error);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || error.message || 'Failed to create instance');
    } finally {
      setCreatingInstance(false);
    }
  };

  const deleteInstance = async (instance) => {
    if (!window.confirm(`Are you sure you want to delete "${instance.instance_name || instance.app_name}"?`)) {
      return;
    }

    setDeletingInstance(instance.app_id);
    try {
      const token = localStorage.getItem('access_token');
      
      // Find the seed app ID - same logic as create
      let seedAppId;
      
      if (instances && instances.length > 0) {
        const seedApp = instances.find(inst => inst.is_seed_app);
        if (seedApp) {
          seedAppId = seedApp.app_id;
        } else {
          // If no seed app marked, use parent_seed_app_id from the instance being deleted
          seedAppId = instance.parent_seed_app_id;
          
          if (!seedAppId) {
            // Fallback: find the instance with lowest instance_number
            const firstInstance = instances.find(inst => inst.instance_number === 1) || instances[0];
            seedAppId = firstInstance.parent_seed_app_id || firstInstance.app_id;
          }
        }
      }
      
      if (!seedAppId) {
        throw new Error('Could not determine seed application ID');
      }
      
      await axios.delete(
        `${API_BASE_URL}/api/v1/applications/${seedAppId}/instances/${instance.app_id}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      showSuccessToast(`Deleted instance: ${instance.instance_name || instance.app_name}`);
      
      // Refresh the instances list
      if (onRefresh) {
        await onRefresh();
      }
    } catch (error) {
      console.error('Error deleting instance:', error);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || error.message || 'Failed to delete instance');
    } finally {
      setDeletingInstance(null);
    }
  };

  const startEditingInstance = (instance) => {
    setEditingInstance(instance.app_id);
    setEditName(instance.instance_name || instance.app_name);
  };

  const cancelEditing = () => {
    setEditingInstance(null);
    setEditName('');
  };

  const saveInstanceName = async (instance) => {
    if (!editName.trim()) {
      showErrorToast('Instance name cannot be empty');
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      
      // Find the seed app ID - consistent with create and delete
      let seedAppId;
      
      if (instances && instances.length > 0) {
        const seedApp = instances.find(inst => inst.is_seed_app);
        if (seedApp) {
          seedAppId = seedApp.app_id;
        } else {
          // Use parent_seed_app_id from the instance being edited
          seedAppId = instance.parent_seed_app_id;
          
          if (!seedAppId) {
            // Fallback: find the instance with lowest instance_number
            const firstInstance = instances.find(inst => inst.instance_number === 1) || instances[0];
            seedAppId = firstInstance.parent_seed_app_id || firstInstance.app_id;
          }
        }
      }
      
      if (!seedAppId) {
        throw new Error('Could not determine seed application ID');
      }
      
      const response = await axios.patch(
        `${API_BASE_URL}/api/v1/applications/${seedAppId}/instances/${instance.app_id}`,
        { instance_name: editName },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      showSuccessToast(`Renamed to: ${editName}`);
      setEditingInstance(null);
      setEditName('');
      
      // Refresh the instances list
      if (onRefresh) {
        await onRefresh();
      }
    } catch (error) {
      console.error('Error updating instance name:', error);
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || error.message || 'Failed to update instance name');
    }
  };

  const getStatusBadge = (instance) => {
    const subscription = subscriptions[instance.app_id];
    
    if (!subscription) {
      return (
        <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
          <ClockIcon className="mr-1 h-3 w-3" />
          Not Connected
        </span>
      );
    }
    
    const authCreds = subscription.auth_credentials || {};
    
    if (!authCreds.has_credentials) {
      return (
        <span className="inline-flex items-center rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-600">
          <ExclamationCircleIcon className="mr-1 h-3 w-3" />
          Setup Required
        </span>
      );
    }
    
    if (instance.auth_type === 'oauth2' && !authCreds.access_token) {
      return (
        <span className="inline-flex items-center rounded-full bg-yellow-100 px-2 py-0.5 text-xs font-medium text-yellow-600">
          <ExclamationCircleIcon className="mr-1 h-3 w-3" />
          Auth Required
        </span>
      );
    }
    
    return (
      <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-600">
        <CheckCircleIcon className="mr-1 h-3 w-3" />
        Connected
      </span>
    );
  };

  // Sort instances by instance_number
  const sortedInstances = [...instances].sort((a, b) => 
    (a.instance_number || 1) - (b.instance_number || 1)
  );

  return (
    <Transition.Root show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-[100] overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-4xl sm:p-6">
                <div className="absolute right-0 top-0 pr-4 pt-4">
                  <button
                    type="button"
                    className="rounded-md bg-white text-gray-400 hover:text-gray-500"
                    onClick={onClose}
                  >
                    <span className="sr-only">Close</span>
                    <XMarkIcon className="h-6 w-6" />
                  </button>
                </div>

                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-indigo-100 sm:mx-0 sm:h-10 sm:w-10">
                    <ServerIcon className="h-6 w-6 text-indigo-600" />
                  </div>
                  <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left flex-1">
                    <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900">
                      Manage Application Instances
                    </Dialog.Title>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        {application?.app_name} - {sortedInstances.length} instance{sortedInstances.length !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-6">
                  {/* Create new instance section */}
                  <div className="mb-6 p-4 bg-gray-50 rounded-lg">
                    <h4 className="text-sm font-medium text-gray-900 mb-3">Create New Instance</h4>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={instanceName}
                        onChange={(e) => setInstanceName(e.target.value)}
                        placeholder="Enter instance name (e.g., Production, Staging)"
                        className="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                        onKeyPress={(e) => {
                          if (e.key === 'Enter' && !creatingInstance) {
                            createNewInstance();
                          }
                        }}
                      />
                      <button
                        onClick={createNewInstance}
                        disabled={creatingInstance || !instanceName.trim()}
                        className="inline-flex items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <PlusIcon className="mr-2 h-4 w-4" />
                        {creatingInstance ? 'Creating...' : 'Create Instance'}
                      </button>
                    </div>
                  </div>

                  {/* Instances list */}
                  <div className="space-y-3">
                    {sortedInstances.map((instance) => {
                      const subscription = subscriptions[instance.app_id];
                      const isConnected = !!subscription;
                      
                      return (
                        <div
                          key={instance.app_id}
                          className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                        >
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-3">
                                {editingInstance === instance.app_id ? (
                                  <div className="flex items-center gap-2">
                                    <input
                                      type="text"
                                      value={editName}
                                      onChange={(e) => setEditName(e.target.value)}
                                      className="px-2 py-1 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                      onKeyPress={(e) => {
                                        if (e.key === 'Enter') {
                                          saveInstanceName(instance);
                                        } else if (e.key === 'Escape') {
                                          cancelEditing();
                                        }
                                      }}
                                      autoFocus
                                    />
                                    <button
                                      onClick={() => saveInstanceName(instance)}
                                      className="p-1 text-green-600 hover:text-green-700"
                                      title="Save"
                                    >
                                      <CheckIcon className="h-4 w-4" />
                                    </button>
                                    <button
                                      onClick={cancelEditing}
                                      className="p-1 text-gray-600 hover:text-gray-700"
                                      title="Cancel"
                                    >
                                      <XMarkIcon className="h-4 w-4" />
                                    </button>
                                  </div>
                                ) : (
                                  <div className="flex items-center gap-2">
                                    <h4 className="text-sm font-medium text-gray-900">
                                      {instance.instance_name || instance.app_name}
                                    </h4>
                                    {!instance.is_seed_app && (
                                      <button
                                        onClick={() => startEditingInstance(instance)}
                                        className="p-1 text-gray-400 hover:text-gray-600"
                                        title="Edit name"
                                      >
                                        <PencilIcon className="h-3 w-3" />
                                      </button>
                                    )}
                                  </div>
                                )}
                                <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                                  Instance #{instance.instance_number || 1}
                                </span>
                                {instance.is_seed_app && (
                                  <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-600">
                                    Primary
                                  </span>
                                )}
                                {getStatusBadge(instance)}
                              </div>
                              {instance.base_url && (
                                <p className="mt-1 text-xs text-gray-500">
                                  URL: {instance.base_url}
                                </p>
                              )}
                              {instance.description && (
                                <p className="mt-1 text-xs text-gray-500">
                                  {instance.description}
                                </p>
                              )}
                            </div>
                            
                            <div className="flex items-center gap-2">
                              {isConnected ? (
                                <>
                                  <button
                                    onClick={() => onConnect(instance, subscription)}
                                    className="inline-flex items-center rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                                  >
                                    <CogIcon className="mr-1 h-3 w-3" />
                                    Settings
                                  </button>
                                  <button
                                    onClick={() => onDisconnect(subscription.subscription_id)}
                                    className="inline-flex items-center rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-red-600 shadow-sm ring-1 ring-inset ring-red-300 hover:bg-red-50"
                                  >
                                    Disconnect
                                  </button>
                                </>
                              ) : (
                                <button
                                  onClick={() => onConnect(instance, null)}
                                  className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
                                >
                                  <LinkIcon className="mr-1 h-3 w-3" />
                                  Connect
                                </button>
                              )}
                              
                              {!instance.is_seed_app && instance.instance_number > 1 && !isConnected && (
                                <button
                                  onClick={() => deleteInstance(instance)}
                                  disabled={deletingInstance === instance.app_id}
                                  className="inline-flex items-center rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-red-600 shadow-sm ring-1 ring-inset ring-red-300 hover:bg-red-50 disabled:opacity-50"
                                  title="Delete this instance"
                                >
                                  <TrashIcon className="mr-1 h-3 w-3" />
                                  {deletingInstance === instance.app_id ? 'Deleting...' : 'Delete'}
                                </button>
                              )}
                              
                              {!instance.is_seed_app && instance.instance_number > 1 && isConnected && (
                                <span className="text-xs text-gray-400 italic" title="Disconnect first to delete">
                                  Disconnect to delete
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    
                    {sortedInstances.length === 0 && (
                      <div className="text-center py-6 text-gray-500">
                        No instances found. Create your first instance to get started.
                      </div>
                    )}
                  </div>
                </div>

                <div className="mt-6 sm:flex sm:flex-row-reverse">
                  <button
                    type="button"
                    className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                    onClick={onClose}
                  >
                    Close
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default InstanceManagementModal;