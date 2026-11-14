import React, { useState, useEffect, useCallback } from 'react';
import {
  InboxStackIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  PaperAirplaneIcon,
  PencilIcon,
  EyeIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import axios from 'axios';
import IsolatedField from '../../../components/flow/IsolatedParameterInput';

const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'completed', label: 'Completed' },
  { value: 'expired', label: 'Expired' },
  { value: 'all', label: 'All' },
];

const PRIORITY_COLORS = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  low: 'bg-gray-100 text-gray-600 border-gray-200',
};

const ACTION_TYPES = {
  APPROVE_REJECT: ['approved', 'rejected'],
  REVIEW: ['reviewed'],
  EDIT: ['edited'],
};

export default function TaskInboxSection({ config, appInfo, previewMode }) {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState((config.defaultStatus || 'pending').toLowerCase());
  const [expandedTask, setExpandedTask] = useState(null);
  const [submitting, setSubmitting] = useState(null);

  const pageSize = config.pageSize || 10;
  const flowId = appInfo?.flow_id;

  const authToken = localStorage.getItem('access_token') || localStorage.getItem('token');
  const hasAuthToken = !!authToken;
  const getAuthHeaders = () => authToken ? { Authorization: `Bearer ${authToken}` } : {};

  const fetchTasks = useCallback(async () => {
    if (previewMode || !hasAuthToken) return;
    setLoading(true);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (statusFilter !== 'all') params.status = statusFilter;

      const resp = await axios.get('/api/v1/hitl/tasks', { params, headers: getAuthHeaders() });
      const data = resp.data;
      // Filter tasks for this flow
      let items = data.tasks || [];
      if (flowId) {
        items = items.filter((t) => t.flow_id === flowId);
      }
      setTasks(items);
      setTotal(data.total || items.length);
    } catch {
      setTasks([]);
    } finally {
      setLoading(false);
    }
  }, [flowId, statusFilter, page, pageSize, previewMode, hasAuthToken]);

  const fetchStats = useCallback(async () => {
    if (previewMode || !config.showStats || !hasAuthToken) return;
    try {
      const resp = await axios.get('/api/v1/hitl/tasks/stats', { headers: getAuthHeaders() });
      setStats(resp.data);
    } catch {
      // Ignore
    }
  }, [previewMode, config.showStats, hasAuthToken]);

  useEffect(() => {
    fetchTasks();
    fetchStats();
  }, [fetchTasks, fetchStats]);

  // Auto-refresh
  useEffect(() => {
    if (!config.autoRefresh || previewMode) return;
    const interval = setInterval(() => {
      fetchTasks();
      fetchStats();
    }, (config.autoRefreshInterval || 15) * 1000);
    return () => clearInterval(interval);
  }, [config.autoRefresh, config.autoRefreshInterval, fetchTasks, fetchStats, previewMode]);

  const handleCompleteTask = async (taskId, responseAction, responseData, comment) => {
    setSubmitting(taskId);
    try {
      await axios.post(`/api/v1/hitl/tasks/${taskId}/complete`, {
        response_action: responseAction,
        response_data: responseData || {},
        comment: comment || '',
      }, { headers: getAuthHeaders() });
      fetchTasks();
      fetchStats();
      setExpandedTask(null);
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to complete task');
    } finally {
      setSubmitting(null);
    }
  };

  if (previewMode) {
    return (
      <div className="py-6">
        {config.title && <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>}
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center">
          <InboxStackIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Task inbox will appear here for authenticated users</p>
        </div>
      </div>
    );
  }

  return (
    <div className="py-6">
      {config.title && <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>}

      {/* Stats */}
      {config.showStats && stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <StatCard label="Pending" value={stats.pending} color="text-yellow-600" bg="bg-yellow-50" />
          <StatCard label="Urgent" value={stats.urgent} color="text-red-600" bg="bg-red-50" />
          <StatCard label="Completed" value={stats.completed} color="text-green-600" bg="bg-green-50" />
          <StatCard label="Expired" value={stats.expired} color="text-gray-600" bg="bg-gray-50" />
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
          className="px-3 py-1.5 border border-gray-300 rounded-md text-sm"
        >
          {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <button
          onClick={() => { fetchTasks(); fetchStats(); }}
          className="px-3 py-1.5 text-sm text-primary border border-primary/30 rounded-md hover:bg-primary/5"
        >
          <ArrowPathIcon className={`w-4 h-4 inline mr-1 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Task List */}
      {loading && tasks.length === 0 ? (
        <div className="flex items-center justify-center py-12">
          <ArrowPathIcon className="w-6 h-6 text-primary animate-spin" />
        </div>
      ) : tasks.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <InboxStackIcon className="w-10 h-10 text-gray-300 mx-auto mb-2" />
          <p className="text-gray-400 text-sm">No tasks found</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <TaskCard
              key={task.task_id}
              task={task}
              isExpanded={expandedTask === task.task_id}
              onToggle={() => setExpandedTask(expandedTask === task.task_id ? null : task.task_id)}
              onComplete={handleCompleteTask}
              submitting={submitting === task.task_id}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-gray-500">
            {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0} className="px-3 py-1 text-xs border rounded disabled:opacity-30">Prev</button>
            <button onClick={() => setPage(page + 1)} disabled={(page + 1) * pageSize >= total} className="px-3 py-1 text-xs border rounded disabled:opacity-30">Next</button>
          </div>
        </div>
      )}
    </div>
  );
}


function StatCard({ label, value, color, bg }) {
  return (
    <div className={`${bg} rounded-lg border p-3 text-center`}>
      <div className={`text-2xl font-bold ${color}`}>{value || 0}</div>
      <div className="text-xs text-gray-500">{label}</div>
    </div>
  );
}


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
    if (String(value).length > 100) {
      variable.uiControl = 'textarea';
    }
  }
  return variable;
};

function TaskCard({ task, isExpanded, onToggle, onComplete, submitting }) {
  const [comment, setComment] = useState('');
  const [editData, setEditData] = useState({});

  const isPending = task.status?.toLowerCase() === 'pending';
  const taskType = (task.task_type || 'approve_reject').toLowerCase();
  const isEditable = taskType === 'edit';
  const isTimedOut = task.timeout_at && new Date(task.timeout_at) < new Date();

  // Initialize edit data from input_data
  useEffect(() => {
    if (isExpanded && task.input_data) {
      setEditData({ ...task.input_data });
    }
  }, [isExpanded, task.input_data]);

  const handleFieldChange = useCallback((name, value) => {
    setEditData((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleAction = (action) => {
    const responseData = isEditable ? editData : (task.input_data || {});
    onComplete(task.task_id, action, responseData, comment);
  };

  const taskTypeLabel = taskType === 'approve_reject' ? 'Approve/Reject'
    : taskType === 'edit' ? 'Edit' : taskType === 'review' ? 'Review' : taskType;

  return (
    <div className={`bg-white rounded-lg border overflow-hidden ${
      isPending ? 'border-yellow-200' : 'border-gray-200'
    }`}>
      {/* Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-50"
      >
        {isPending ? (
          <ClockIcon className="w-5 h-5 text-yellow-500 shrink-0" />
        ) : task.status?.toLowerCase() === 'completed' ? (
          <CheckCircleIcon className="w-5 h-5 text-green-500 shrink-0" />
        ) : (
          <XCircleIcon className="w-5 h-5 text-gray-400 shrink-0" />
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-900 truncate">{task.title}</span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${PRIORITY_COLORS[task.priority?.toLowerCase()] || PRIORITY_COLORS.medium}`}>
              {task.priority}
            </span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 uppercase font-medium">
              {taskTypeLabel}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-0.5">
            {new Date(task.created_at).toLocaleString()}
            {isTimedOut && isPending && (
              <span className="ml-2 text-red-500 font-medium">Timed out</span>
            )}
          </div>
        </div>

        {isExpanded ? <ChevronUpIcon className="w-4 h-4 text-gray-400" /> : <ChevronDownIcon className="w-4 h-4 text-gray-400" />}
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t border-gray-100 px-4 py-4">
          {/* Description / Instructions */}
          {task.description && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-md flex items-start gap-2">
              <InformationCircleIcon className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-xs font-medium text-amber-700 mb-0.5">Instructions</p>
                <p className="text-sm text-amber-800">{task.description}</p>
              </div>
            </div>
          )}

          {/* Input Data */}
          {task.input_data && Object.keys(task.input_data).length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                {isEditable ? 'Edit the data below:' : 'Review the data:'}
              </h4>
              {isEditable && isPending ? (
                /* Editable form using IsolatedField */
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {Object.entries(task.input_data).map(([key, value]) => {
                    const variable = inferVariable(key, value);
                    const isWide = ['object', 'array'].includes(variable.dataType)
                      || variable.uiControl === 'textarea'
                      || (typeof value === 'string' && value.length > 80);
                    return (
                      <div key={key} className={isWide ? 'md:col-span-2' : ''}>
                        <IsolatedField
                          variable={variable}
                          value={editData[key] !== undefined ? editData[key] : value}
                          onChange={handleFieldChange}
                        />
                      </div>
                    );
                  })}
                </div>
              ) : (
                /* Read-only form-style display */
                <div className="space-y-3 max-h-96 overflow-auto">
                  {Object.entries(task.input_data).map(([key, value]) => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-gray-700 mb-1">{key}</label>
                      <div className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-md text-sm text-gray-700">
                        {(value !== null && typeof value === 'object')
                          ? JSON.stringify(value, null, 2)
                          : String(value ?? '')}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Display Config - custom fields from the HITL node */}
          {task.display_config?.fields && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Details</h4>
              <div className="grid grid-cols-2 gap-2">
                {task.display_config.fields.map((field) => (
                  <div key={field.key} className="bg-gray-50 rounded p-2">
                    <div className="text-[10px] text-gray-500 uppercase">{field.label || field.key}</div>
                    <div className="text-sm text-gray-800">
                      {task.input_data?.[field.key] != null ? String(task.input_data[field.key]) : '-'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Response (if completed) */}
          {task.response_data && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Response</h4>
              <div className="bg-green-50 rounded border border-green-200 p-3">
                <div className="text-xs text-green-700 mb-1 font-medium">Action: {task.response_action}</div>
                <div className="space-y-2">
                  {Object.entries(task.response_data).map(([key, value]) => (
                    <div key={key}>
                      <span className="text-xs font-medium text-green-700">{key}: </span>
                      <span className="text-xs text-green-800">
                        {(value !== null && typeof value === 'object') ? JSON.stringify(value) : String(value ?? '')}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons (only for pending tasks) */}
          {isPending && (
            <div className="border-t border-gray-100 pt-4">
              {/* Comment */}
              <div className="mb-3">
                <label className="block text-xs font-medium text-gray-600 mb-1">Comment (optional)</label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  rows={2}
                  placeholder="Add a comment..."
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div className="flex gap-2">
                {taskType === 'approve_reject' && (
                  <>
                    <button
                      onClick={() => handleAction('rejected')}
                      disabled={submitting}
                      className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                    >
                      <XCircleIcon className="w-4 h-4" />
                      Reject
                    </button>
                    <button
                      onClick={() => handleAction('approved')}
                      disabled={submitting}
                      className="flex items-center gap-1.5 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
                    >
                      <CheckCircleIcon className="w-4 h-4" />
                      Approve
                    </button>
                  </>
                )}
                {taskType === 'review' && (
                  <button
                    onClick={() => handleAction('reviewed')}
                    disabled={submitting}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    <EyeIcon className="w-4 h-4" />
                    Mark Reviewed
                  </button>
                )}
                {taskType === 'edit' && (
                  <button
                    onClick={() => handleAction('edited')}
                    disabled={submitting}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    <PencilIcon className="w-4 h-4" />
                    Submit Changes
                  </button>
                )}
                {submitting && <ArrowPathIcon className="w-5 h-5 text-primary animate-spin self-center" />}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
