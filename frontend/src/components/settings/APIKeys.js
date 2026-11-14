import React, { useState, useEffect, Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import {
  KeyIcon,
  PlusIcon,
  TrashIcon,
  EyeIcon,
  EyeSlashIcon,
  ClipboardDocumentIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { format } from 'date-fns';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';

const APIKeys = () => {
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [selectedKey, setSelectedKey] = useState(null);
  const [createdKey, setCreatedKey] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    scopes: ['read'],
    expires_in_days: '',
  });

  useEffect(() => {
    fetchAPIKeys();
  }, []);

  const fetchAPIKeys = async () => {
    try {
      const response = await fetch('/api/v1/api-keys/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setApiKeys(data.api_keys || []);
      } else {
        showErrorToast('Failed to fetch API keys');
      }
    } catch (error) {
      console.error('Error fetching API keys:', error);
      showErrorToast('Failed to fetch API keys');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKey = async () => {
    try {
      const payload = {
        ...formData,
        expires_in_days: formData.expires_in_days ? parseInt(formData.expires_in_days) : null,
      };

      const response = await fetch('/api/v1/api-keys/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        const data = await response.json();
        setCreatedKey(data.api_key);
        setShowKeyModal(true);
        setCreateModalOpen(false);
        setFormData({ name: '', description: '', scopes: ['read'], expires_in_days: '' });
        fetchAPIKeys();
        showSuccessToast('API key created successfully');
      } else {
        const error = await response.json();
        showErrorToast(error.message || 'Failed to create API key');
      }
    } catch (error) {
      console.error('Error creating API key:', error);
      showErrorToast('Failed to create API key');
    }
  };

  const handleDeleteKey = async () => {
    if (!selectedKey) return;

    try {
      const response = await fetch(`/api/v1/api-keys/${selectedKey.id}/`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (response.ok) {
        setDeleteModalOpen(false);
        setSelectedKey(null);
        fetchAPIKeys();
        showSuccessToast('API key deleted successfully');
      } else {
        showErrorToast('Failed to delete API key');
      }
    } catch (error) {
      console.error('Error deleting API key:', error);
      showErrorToast('Failed to delete API key');
    }
  };

  const handleDeactivateKey = async (key) => {
    try {
      const response = await fetch(`/api/v1/api-keys/${key.id}/deactivate/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      });

      if (response.ok) {
        fetchAPIKeys();
        showSuccessToast('API key deactivated successfully');
      } else {
        showErrorToast('Failed to deactivate API key');
      }
    } catch (error) {
      console.error('Error deactivating API key:', error);
      showErrorToast('Failed to deactivate API key');
    }
  };

  const copyToClipboard = (text, customMessage) => {
    navigator.clipboard.writeText(text);
    if (!customMessage) {
      showSuccessToast('Copied to clipboard');
    }
  };

  const formatDate = (dateString) => {
    return format(new Date(dateString), 'MMM dd, yyyy HH:mm');
  };

  if (loading) {
    return <div className="text-center py-4">Loading...</div>;
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-medium text-gray-900">API Keys</h2>
          <p className="mt-1 text-sm text-gray-600">
            API keys allow you to access IOFlow programmatically. Keep your API keys secure and do not share them publicly.
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <button
            type="button"
            onClick={() => setCreateModalOpen(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            <PlusIcon className="-ml-1 mr-2 h-5 w-5" />
            Create API Key
          </button>
        </div>
      </div>

      <div className="mt-6">
        {apiKeys.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <KeyIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">No API keys</h3>
            <p className="mt-1 text-sm text-gray-500">Get started by creating a new API key.</p>
            <div className="mt-6">
              <button
                type="button"
                onClick={() => setCreateModalOpen(true)}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gradient-primary hover:shadow-lg"
              >
                <PlusIcon className="-ml-1 mr-2 h-5 w-5" />
                Create API Key
              </button>
            </div>
          </div>
        ) : (
          <div className="overflow-hidden shadow ring-1 ring-black ring-opacity-5 md:rounded-lg">
            <table className="min-w-full divide-y divide-gray-300">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Name
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Key Preview
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Last Used
                  </th>
                  <th className="relative px-6 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {apiKeys.map((key) => (
                  <tr key={key.id}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{key.name}</div>
                        {key.description && (
                          <div className="text-sm text-gray-500">{key.description}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <code className="text-sm text-gray-900">{key.key_prefix}...</code>
                        <button
                          onClick={() => {
                            copyToClipboard(key.key_prefix, true);
                            showSuccessToast('Key prefix copied to clipboard (full key only available when created)');
                          }}
                          className="ml-2 text-gray-400 hover:text-gray-600"
                          title="Copy key prefix (full key only shown once when created)"
                        >
                          <ClipboardDocumentIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`inline-flex px-2 text-xs font-semibold leading-5 rounded-full ${
                          key.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {key.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(key.created_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {key.last_used_at ? formatDate(key.last_used_at) : 'Never'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex items-center justify-end space-x-2">
                        {key.is_active && (
                          <button
                            onClick={() => handleDeactivateKey(key)}
                            className="text-gray-400 hover:text-gray-600"
                            title="Deactivate"
                          >
                            <EyeSlashIcon className="h-5 w-5" />
                          </button>
                        )}
                        <button
                          onClick={() => {
                            setSelectedKey(key);
                            setDeleteModalOpen(true);
                          }}
                          className="text-red-400 hover:text-red-600"
                          title="Delete"
                        >
                          <TrashIcon className="h-5 w-5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create API Key Modal */}
      <Transition.Root show={createModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-10" onClose={setCreateModalOpen}>
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
                <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
                  <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                    <div className="sm:flex sm:items-start">
                      <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-primary-10 sm:mx-0 sm:h-10 sm:w-10">
                        <KeyIcon className="h-6 w-6 text-primary" />
                      </div>
                      <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                        <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                          Create API Key
                        </Dialog.Title>
                        <div className="mt-4 space-y-4">
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Name</label>
                            <input
                              type="text"
                              value={formData.name}
                              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                              placeholder="My API Key"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Description</label>
                            <textarea
                              value={formData.description}
                              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                              rows={2}
                              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                              placeholder="Optional description"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Scopes</label>
                            <div className="mt-2 space-y-2">
                              {['read', 'write', 'delete'].map((scope) => (
                                <label key={scope} className="flex items-center">
                                  <input
                                    type="checkbox"
                                    value={scope}
                                    checked={formData.scopes.includes(scope)}
                                    onChange={(e) => {
                                      if (e.target.checked) {
                                        setFormData({ ...formData, scopes: [...formData.scopes, scope] });
                                      } else {
                                        setFormData({ ...formData, scopes: formData.scopes.filter(s => s !== scope) });
                                      }
                                    }}
                                    className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                                  />
                                  <span className="ml-2 text-sm text-gray-700 capitalize">{scope}</span>
                                </label>
                              ))}
                            </div>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700">Expiration (days)</label>
                            <input
                              type="number"
                              value={formData.expires_in_days}
                              onChange={(e) => setFormData({ ...formData, expires_in_days: e.target.value })}
                              min="1"
                              max="365"
                              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm"
                              placeholder="Leave empty for no expiration"
                            />
                            <p className="mt-1 text-xs text-gray-500">Maximum 365 days</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md bg-gradient-primary px-3 py-2 text-sm font-semibold text-white shadow-sm hover:shadow-lg sm:ml-3 sm:w-auto"
                      onClick={handleCreateKey}
                      disabled={!formData.name}
                    >
                      Create
                    </button>
                    <button
                      type="button"
                      className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                      onClick={() => setCreateModalOpen(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>

      {/* Show Created Key Modal */}
      <Transition.Root show={showKeyModal} as={Fragment}>
        <Dialog as="div" className="relative z-10" onClose={setShowKeyModal}>
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
                <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl">
                  <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                    <div className="sm:flex sm:items-start">
                      <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-green-100 sm:mx-0 sm:h-10 sm:w-10">
                        <KeyIcon className="h-6 w-6 text-green-600" />
                      </div>
                      <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                        <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                          API Key Created Successfully
                        </Dialog.Title>
                        <div className="mt-4">
                          <div className="rounded-md bg-yellow-50 p-4">
                            <div className="flex">
                              <div className="flex-shrink-0">
                                <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
                              </div>
                              <div className="ml-3">
                                <p className="text-sm text-yellow-800">
                                  This is the only time you'll see this API key. Make sure to copy it now!
                                </p>
                              </div>
                            </div>
                          </div>
                          <div className="mt-4">
                            <div className="flex items-center justify-between rounded-lg bg-gray-50 p-3">
                              <code className="text-sm text-gray-900 break-all">{createdKey}</code>
                              <button
                                onClick={() => copyToClipboard(createdKey)}
                                className="ml-2 flex-shrink-0 text-primary hover:text-primary-dark"
                              >
                                <ClipboardDocumentIcon className="h-5 w-5" />
                              </button>
                            </div>
                          </div>
                          <div className="mt-4">
                            <p className="text-sm text-gray-600">
                              Use this API key in your requests by including it in the Authorization header:
                            </p>
                            <div className="mt-2 rounded-lg bg-gray-900 p-3">
                              <code className="text-sm text-green-400">
                                Authorization: Bearer {createdKey}
                              </code>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md bg-gradient-primary px-3 py-2 text-sm font-semibold text-white shadow-sm hover:shadow-lg sm:ml-3 sm:w-auto"
                      onClick={() => setShowKeyModal(false)}
                    >
                      Done
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>

      {/* Delete Confirmation Modal */}
      <Transition.Root show={deleteModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-10" onClose={setDeleteModalOpen}>
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
                <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
                  <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                    <div className="sm:flex sm:items-start">
                      <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                        <ExclamationTriangleIcon className="h-6 w-6 text-red-600" />
                      </div>
                      <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left">
                        <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                          Delete API Key
                        </Dialog.Title>
                        <div className="mt-2">
                          <p className="text-sm text-gray-500">
                            Are you sure you want to delete the API key "{selectedKey?.name}"? This action cannot be undone.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 sm:ml-3 sm:w-auto"
                      onClick={handleDeleteKey}
                    >
                      Delete
                    </button>
                    <button
                      type="button"
                      className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                      onClick={() => setDeleteModalOpen(false)}
                    >
                      Cancel
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>
    </div>
  );
};

export default APIKeys;