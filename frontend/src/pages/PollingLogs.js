import React, { useState, useEffect, Fragment } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Dialog, Transition, Switch } from '@headlessui/react';
import {
  ArrowPathIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  ClockIcon,
  XMarkIcon,
  EyeIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { format } from 'date-fns';
import { showErrorToast, showSuccessToast } from '../utils/customToast';

const PollingLogs = () => {
  const [showErrorsOnly, setShowErrorsOnly] = useState(false);
  const [selectedLog, setSelectedLog] = useState(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [expandedRows, setExpandedRows] = useState({});
  const navigate = useNavigate();

  // Fetch polling logs
  const { data: logs = [], isLoading, error, refetch } = useQuery({
    queryKey: ['pollingLogs', showErrorsOnly],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (showErrorsOnly) params.append('show_errors_only', 'true');
      
      const response = await axios.get(`/api/v1/polling/logs?${params}`);
      return response.data;
    },
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  });

  const handleClearErrors = async (pollingStateId) => {
    try {
      await axios.post(`/api/v1/polling/logs/${pollingStateId}/clear-errors`);
      showSuccessToast('Errors cleared successfully');
      refetch();
    } catch (err) {
      showErrorToast(err.response?.data?.detail || 'Failed to clear errors');
    }
  };

  const handleResetState = async (pollingStateId) => {
    if (!window.confirm('Are you sure you want to reset this polling state? This will clear all processed items.')) {
      return;
    }
    
    try {
      await axios.delete(`/api/v1/polling/state/${pollingStateId}`);
      showSuccessToast('Polling state reset successfully');
      refetch();
    } catch (err) {
      showErrorToast(err.response?.data?.detail || 'Failed to reset state');
    }
  };

  const toggleRowExpanded = (logId) => {
    setExpandedRows(prev => ({
      ...prev,
      [logId]: !prev[logId]
    }));
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Never';
    try {
      return format(new Date(dateString), 'PPpp');
    } catch {
      return dateString;
    }
  };

  const getStatusBadge = (log) => {
    if (log.consecutive_errors > 0) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
          <ExclamationCircleIcon className="w-4 h-4 mr-1" />
          {log.consecutive_errors} Errors
        </span>
      );
    } else if (!log.is_active) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
          <ExclamationTriangleIcon className="w-4 h-4 mr-1" />
          Inactive
        </span>
      );
    } else if (log.last_successful_poll) {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
          <CheckCircleIcon className="w-4 h-4 mr-1" />
          Active
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          <ClockIcon className="w-4 h-4 mr-1" />
          Pending
        </span>
      );
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <ArrowPathIcon className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div>
      <div className="sm:flex sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Polling Logs</h1>
          <p className="mt-1 text-sm text-gray-600">
            Monitor polling operations and troubleshoot errors
          </p>
        </div>
        <div className="mt-4 sm:mt-0 flex items-center space-x-4">
          <Switch.Group>
            <div className="flex items-center">
              <Switch
                checked={showErrorsOnly}
                onChange={setShowErrorsOnly}
                className={`${
                  showErrorsOnly ? 'bg-primary' : 'bg-gray-200'
                } relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2`}
              >
                <span
                  className={`${
                    showErrorsOnly ? 'translate-x-6' : 'translate-x-1'
                  } inline-block h-4 w-4 transform rounded-full bg-white transition-transform`}
                />
              </Switch>
              <Switch.Label className="ml-3 text-sm font-medium text-gray-700">
                Show errors only
              </Switch.Label>
            </div>
          </Switch.Group>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
          >
            <ArrowPathIcon className="h-4 w-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4 mb-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <ExclamationCircleIcon className="h-5 w-5 text-red-400" />
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error loading logs</h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{(error.response?.data?.message || error.response?.data?.detail) || error.message}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {logs.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <ClockIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No polling logs</h3>
          <p className="mt-1 text-sm text-gray-500">
            {showErrorsOnly ? 'No polling errors found' : 'No polling operations have been configured'}
          </p>
        </div>
      ) : (
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul className="divide-y divide-gray-200">
            {logs.map((log) => (
              <li key={log.polling_state_id}>
                <div className="px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <button
                        onClick={() => toggleRowExpanded(log.polling_state_id)}
                        className="mr-3 text-gray-400 hover:text-gray-600"
                      >
                        {expandedRows[log.polling_state_id] ? (
                          <ChevronUpIcon className="h-5 w-5" />
                        ) : (
                          <ChevronDownIcon className="h-5 w-5" />
                        )}
                      </button>
                      <div>
                        <div className="flex items-center">
                          <p className="text-sm font-medium text-primary truncate">
                            <button
                              onClick={() => navigate(`/flows/${log.flow_id}/edit`)}
                              className="hover:underline"
                            >
                              {log.flow_name}
                            </button>
                          </p>
                          <span className="ml-3">{getStatusBadge(log)}</span>
                        </div>
                        <div className="mt-1 flex items-center text-sm text-gray-500">
                          <span>{log.app_name}</span>
                          <span className="mx-2">•</span>
                          <span>{log.event_name}</span>
                          <span className="mx-2">•</span>
                          <span>{log.items_processed_count} items processed</span>
                        </div>
                        {log.last_poll_timestamp && (
                          <p className="mt-1 text-xs text-gray-500">
                            Last poll: {formatDate(log.last_poll_timestamp)}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => {
                          setSelectedLog(log);
                          setDetailModalOpen(true);
                        }}
                        className="text-gray-400 hover:text-gray-500"
                        title="View Details"
                      >
                        <EyeIcon className="h-5 w-5" />
                      </button>
                      {log.consecutive_errors > 0 && (
                        <button
                          onClick={() => handleClearErrors(log.polling_state_id)}
                          className="text-yellow-600 hover:text-yellow-700"
                          title="Clear Errors"
                        >
                          <XMarkIcon className="h-5 w-5" />
                        </button>
                      )}
                      <button
                        onClick={() => handleResetState(log.polling_state_id)}
                        className="text-red-600 hover:text-red-700"
                        title="Reset State"
                      >
                        <TrashIcon className="h-5 w-5" />
                      </button>
                    </div>
                  </div>

                  {/* Expanded content */}
                  {expandedRows[log.polling_state_id] && (
                    <div className="mt-4 space-y-4">
                      {log.last_error && (
                        <div className="bg-red-50 rounded-lg p-4">
                          <div className="flex">
                            <div className="flex-shrink-0">
                              <ExclamationCircleIcon className="h-5 w-5 text-red-400" />
                            </div>
                            <div className="ml-3 flex-1">
                              <h3 className="text-sm font-medium text-red-800">
                                Last Error ({log.consecutive_errors} consecutive)
                              </h3>
                              <p className="mt-1 text-xs text-red-600">
                                {formatDate(log.last_error_timestamp)}
                              </p>
                              <div className="mt-2 text-sm text-red-700">
                                <pre className="whitespace-pre-wrap font-mono text-xs overflow-x-auto">
                                  {log.last_error}
                                </pre>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {log.last_poll_state && (
                        <div className="bg-gray-50 rounded-lg p-4">
                          <h3 className="text-sm font-medium text-gray-900 mb-2">Polling State</h3>
                          <pre className="text-xs font-mono text-gray-700 overflow-x-auto">
                            {JSON.stringify(log.last_poll_state, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Detail Modal */}
      <Transition.Root show={detailModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-10" onClose={setDetailModalOpen}>
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
                <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-3xl sm:p-6">
                  <div>
                    <div className="mt-3 text-center sm:mt-0 sm:text-left">
                      <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900">
                        Polling State Details
                        {selectedLog && (
                          <span className="ml-3">{getStatusBadge(selectedLog)}</span>
                        )}
                      </Dialog.Title>
                      {selectedLog && (
                        <div className="mt-4 space-y-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <dt className="text-sm font-medium text-gray-500">Flow</dt>
                              <dd className="mt-1 text-sm text-gray-900">{selectedLog.flow_name}</dd>
                            </div>
                            <div>
                              <dt className="text-sm font-medium text-gray-500">Application</dt>
                              <dd className="mt-1 text-sm text-gray-900">{selectedLog.app_name}</dd>
                            </div>
                            <div>
                              <dt className="text-sm font-medium text-gray-500">Event</dt>
                              <dd className="mt-1 text-sm text-gray-900">{selectedLog.event_name}</dd>
                            </div>
                            <div>
                              <dt className="text-sm font-medium text-gray-500">Items Processed</dt>
                              <dd className="mt-1 text-sm text-gray-900">{selectedLog.items_processed_count}</dd>
                            </div>
                            <div>
                              <dt className="text-sm font-medium text-gray-500">Last Poll</dt>
                              <dd className="mt-1 text-sm text-gray-900">{formatDate(selectedLog.last_poll_timestamp)}</dd>
                            </div>
                            <div>
                              <dt className="text-sm font-medium text-gray-500">Last Success</dt>
                              <dd className="mt-1 text-sm text-gray-900">{formatDate(selectedLog.last_successful_poll)}</dd>
                            </div>
                          </div>

                          {selectedLog.last_error && (
                            <div className="bg-red-50 rounded-lg p-4">
                              <div className="flex">
                                <div className="flex-shrink-0">
                                  <ExclamationCircleIcon className="h-5 w-5 text-red-400" />
                                </div>
                                <div className="ml-3 flex-1">
                                  <h3 className="text-sm font-medium text-red-800">
                                    Last Error ({selectedLog.consecutive_errors} consecutive)
                                  </h3>
                                  <p className="mt-1 text-xs text-red-600">
                                    {formatDate(selectedLog.last_error_timestamp)}
                                  </p>
                                  <div className="mt-2 text-sm text-red-700">
                                    <pre className="whitespace-pre-wrap font-mono text-xs overflow-x-auto">
                                      {selectedLog.last_error}
                                    </pre>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )}

                          {selectedLog.last_poll_state && (
                            <div>
                              <h4 className="text-sm font-medium text-gray-900 mb-2">Polling State</h4>
                              <div className="bg-gray-50 rounded-lg p-4">
                                <pre className="text-xs font-mono text-gray-700 overflow-x-auto">
                                  {JSON.stringify(selectedLog.last_poll_state, null, 2)}
                                </pre>
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="mt-5 sm:mt-6 sm:grid sm:grid-flow-row-dense sm:grid-cols-3 sm:gap-3">
                    {selectedLog?.consecutive_errors > 0 && (
                      <button
                        type="button"
                        className="inline-flex w-full justify-center rounded-md bg-yellow-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-600 sm:col-start-1"
                        onClick={() => {
                          handleClearErrors(selectedLog.polling_state_id);
                          setDetailModalOpen(false);
                        }}
                      >
                        Clear Errors
                      </button>
                    )}
                    <button
                      type="button"
                      className="inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600 sm:col-start-2"
                      onClick={() => {
                        handleResetState(selectedLog.polling_state_id);
                        setDetailModalOpen(false);
                      }}
                    >
                      Reset State
                    </button>
                    <button
                      type="button"
                      className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:col-start-3 sm:mt-0"
                      onClick={() => setDetailModalOpen(false)}
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
    </div>
  );
};

export default PollingLogs;