import React, { useState, useEffect, useCallback } from 'react';
import {
  XMarkIcon,
  CheckIcon,
  XCircleIcon,
  PencilIcon,
  EyeIcon,
  ClockIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import hitlService from '../../services/hitlService';
import IsolatedField from '../flow/IsolatedParameterInput';

const priorityStyles = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

// Infer variable definition from a value for IsolatedField
const inferVariable = (key, value) => {
  const variable = { name: key, label: key, required: false };

  if (value === null || value === undefined) {
    variable.dataType = 'string';
    variable.defaultValue = '';
  } else if (typeof value === 'boolean') {
    variable.dataType = 'boolean';
    variable.defaultValue = value;
  } else if (typeof value === 'number') {
    variable.dataType = Number.isInteger(value) ? 'integer' : 'number';
    variable.defaultValue = value;
  } else if (Array.isArray(value)) {
    variable.dataType = 'array';
    variable.defaultValue = value;
  } else if (typeof value === 'object') {
    variable.dataType = 'object';
    variable.defaultValue = value;
  } else {
    variable.dataType = 'string';
    variable.defaultValue = String(value);
    // Use textarea for long strings
    if (String(value).length > 100) {
      variable.uiControl = 'textarea';
    }
  }
  return variable;
};

const TaskReviewModal = ({ task, isOpen, onClose, onCompleted, fetchFullTask }) => {
  const [editedData, setEditedData] = useState({});
  const [comment, setComment] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [fullTask, setFullTask] = useState(null);
  const [loadingTask, setLoadingTask] = useState(false);

  // Fetch full task data when opened from ManualTriggerModal (which only has summary)
  useEffect(() => {
    if (isOpen && task?.task_id && fetchFullTask) {
      setLoadingTask(true);
      hitlService.getTask(task.task_id)
        .then(res => {
          setFullTask(res.data);
          if (res.data?.input_data) {
            setEditedData({ ...res.data.input_data });
          }
        })
        .catch(err => {
          setError('Failed to load task details');
          console.error('Failed to fetch HITL task:', err);
        })
        .finally(() => setLoadingTask(false));
    }
  }, [isOpen, task?.task_id, fetchFullTask]);

  const activeTask = fullTask || task;

  useEffect(() => {
    if (!fetchFullTask && activeTask?.input_data) {
      setEditedData({ ...activeTask.input_data });
    } else if (!fetchFullTask) {
      setEditedData({});
    }
    setComment('');
    setError(null);
  }, [activeTask, fetchFullTask]);

  const handleFieldChange = useCallback((name, value) => {
    setEditedData(prev => ({ ...prev, [name]: value }));
  }, []);

  if (!isOpen || !task) return null;

  const displayConfig = activeTask.display_config || { format: 'form' };
  const format = displayConfig.format || 'form';
  const isEditable = activeTask.task_type === 'edit';

  const handleComplete = async (action) => {
    setSubmitting(true);
    setError(null);
    try {
      const responseData = isEditable ? editedData : activeTask.input_data;
      await hitlService.completeTask(activeTask.task_id, {
        response_action: action,
        response_data: responseData,
        comment: comment || null,
      });
      onCompleted && onCompleted(activeTask.task_id, action);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to complete task');
    } finally {
      setSubmitting(false);
    }
  };

  const getTimeRemaining = () => {
    if (!activeTask.timeout_at) return null;
    const timeoutStr = activeTask.timeout_at;
    const timeout = new Date(
      !timeoutStr.endsWith('Z') && !timeoutStr.includes('+') ? timeoutStr + 'Z' : timeoutStr
    );
    const now = new Date();
    const diff = timeout - now;
    if (diff <= 0) return 'Expired';
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    if (hours > 0) return `${hours}h ${minutes}m remaining`;
    return `${minutes}m remaining`;
  };

  const renderReadOnlyData = (data) => {
    if (!data || typeof data !== 'object') {
      return <p className="text-sm text-gray-600">{String(data || 'No data')}</p>;
    }

    if (format === 'json') {
      return (
        <pre className="bg-gray-50 border rounded-md p-4 text-xs overflow-auto max-h-96 font-mono">
          {JSON.stringify(data, null, 2)}
        </pre>
      );
    }

    if (format === 'table') {
      return (
        <div className="overflow-auto max-h-96">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Field</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {Object.entries(data).map(([key, value]) => (
                <tr key={key}>
                  <td className="px-4 py-2 font-medium text-gray-700">{key}</td>
                  <td className="px-4 py-2 text-gray-600">
                    {(value !== null && typeof value === 'object') ? JSON.stringify(value) : String(value ?? '')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // Default: form-style read-only
    return (
      <div className="space-y-3 max-h-96 overflow-auto">
        {Object.entries(data).map(([key, value]) => (
          <div key={key}>
            <label className="block text-sm font-medium text-gray-700 mb-1">{key}</label>
            <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-md text-sm text-gray-700">
              {(value !== null && typeof value === 'object') ? JSON.stringify(value, null, 2) : String(value ?? '')}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderEditableData = (data) => {
    if (!data || typeof data !== 'object' || Object.keys(data).length === 0) {
      return <p className="text-sm text-gray-500">No data to edit</p>;
    }

    const entries = Object.entries(data);

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {entries.map(([key, value]) => {
          const variable = inferVariable(key, value);
          // Use full width for complex types and long text
          const isWide = ['object', 'array'].includes(variable.dataType)
            || variable.uiControl === 'textarea'
            || (typeof value === 'string' && value.length > 80);

          return (
            <div key={key} className={isWide ? 'md:col-span-2' : ''}>
              <IsolatedField
                variable={variable}
                value={editedData[key] !== undefined ? editedData[key] : value}
                onChange={handleFieldChange}
              />
            </div>
          );
        })}
      </div>
    );
  };

  const timeRemaining = getTimeRemaining();

  return (
    <div className="fixed inset-0 z-[110] overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} />

        <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-hidden">
          {/* Header */}
          <div className="bg-blue-50 border-b border-blue-200 px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{activeTask.title}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-gray-500">{activeTask.flow_name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${priorityStyles[activeTask.priority] || priorityStyles.medium}`}>
                    {activeTask.priority}
                  </span>
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">
                    {activeTask.task_type === 'approve_reject' ? 'Approve/Reject' : activeTask.task_type}
                  </span>
                  {timeRemaining && (
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                      <ClockIcon className="w-3 h-3" />
                      {timeRemaining}
                    </span>
                  )}
                </div>
              </div>
              <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="px-6 py-4 overflow-y-auto" style={{ maxHeight: 'calc(90vh - 200px)' }}>
            {loadingTask && (
              <div className="flex items-center justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                <span className="ml-2 text-sm text-gray-500">Loading task details...</span>
              </div>
            )}

            {/* Instructions */}
            {activeTask.description && !loadingTask && (
              <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md flex items-start gap-2">
                <InformationCircleIcon className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-xs font-medium text-amber-700 mb-0.5">Instructions</p>
                  <p className="text-sm text-amber-800">{activeTask.description}</p>
                </div>
              </div>
            )}

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            )}

            {/* Data Section */}
            {!loadingTask && (
              <div className="mb-4">
                <h4 className="text-sm font-medium text-gray-700 mb-3">
                  {isEditable ? 'Edit the data below:' : 'Review the data:'}
                </h4>
                {isEditable
                  ? renderEditableData(activeTask.input_data)
                  : renderReadOnlyData(activeTask.input_data)
                }
              </div>
            )}

            {/* Comment field */}
            {!loadingTask && (
              <div className="mb-4 border-t border-gray-100 pt-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Comment (optional)
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={2}
                  placeholder="Add a comment..."
                  className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
            )}
          </div>

          {/* Footer / Actions */}
          <div className="border-t border-gray-200 px-6 py-4 bg-gray-50 flex items-center justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              disabled={submitting}
            >
              Cancel
            </button>

            {activeTask.task_type === 'review' && (
              <button
                onClick={() => handleComplete('reviewed')}
                disabled={submitting || loadingTask}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                <EyeIcon className="w-4 h-4" />
                {submitting ? 'Submitting...' : 'Mark Reviewed'}
              </button>
            )}

            {activeTask.task_type === 'edit' && (
              <button
                onClick={() => handleComplete('edited')}
                disabled={submitting || loadingTask}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                <PencilIcon className="w-4 h-4" />
                {submitting ? 'Submitting...' : 'Submit Changes'}
              </button>
            )}

            {activeTask.task_type === 'approve_reject' && (
              <>
                <button
                  onClick={() => handleComplete('rejected')}
                  disabled={submitting}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700 disabled:opacity-50 flex items-center gap-2"
                >
                  <XCircleIcon className="w-4 h-4" />
                  {submitting ? 'Submitting...' : 'Reject'}
                </button>
                <button
                  onClick={() => handleComplete('approved')}
                  disabled={submitting}
                  className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
                >
                  <CheckIcon className="w-4 h-4" />
                  {submitting ? 'Submitting...' : 'Approve'}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskReviewModal;
