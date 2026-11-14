import React, { useState, useEffect, useCallback } from 'react';
import {
  InboxIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  HandRaisedIcon,
} from '@heroicons/react/24/outline';
import hitlService from '../services/hitlService';
import TaskReviewModal from '../components/flows/TaskReviewModal';

const statusConfig = {
  pending: { label: 'Pending', color: 'bg-yellow-100 text-yellow-800', icon: ClockIcon },
  completed: { label: 'Completed', color: 'bg-green-100 text-green-800', icon: CheckCircleIcon },
  expired: { label: 'Expired', color: 'bg-red-100 text-red-800', icon: XCircleIcon },
  escalated: { label: 'Escalated', color: 'bg-orange-100 text-orange-800', icon: ExclamationTriangleIcon },
  cancelled: { label: 'Cancelled', color: 'bg-gray-100 text-gray-800', icon: XCircleIcon },
};

const priorityConfig = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

const taskTypeLabels = {
  review: 'Review',
  edit: 'Edit',
  approve_reject: 'Approve/Reject',
};

const TaskInbox = () => {
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTask, setSelectedTask] = useState(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit, offset };
      if (statusFilter) params.status = statusFilter;

      const [tasksRes, statsRes] = await Promise.all([
        hitlService.getTasks(params),
        hitlService.getTaskStats(),
      ]);

      setTasks(tasksRes.data?.tasks || []);
      setTotal(tasksRes.data?.total || 0);
      setStats(statsRes.data || {});
    } catch (error) {
      console.error('Failed to load tasks:', error);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, offset]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  const handleTaskClick = (task) => {
    setSelectedTask(task);
    setShowReviewModal(true);
  };

  const handleTaskCompleted = () => {
    setShowReviewModal(false);
    setSelectedTask(null);
    fetchTasks();
  };

  const filteredTasks = searchQuery
    ? tasks.filter(t =>
        t.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (t.flow_name && t.flow_name.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : tasks;

  // Parse UTC timestamps from backend (which omit the Z suffix)
  const parseUTC = (dateStr) => {
    if (!dateStr) return null;
    // If no timezone info, treat as UTC by appending Z
    if (!dateStr.endsWith('Z') && !dateStr.includes('+') && !dateStr.includes('T00:00:00.000')) {
      return new Date(dateStr + 'Z');
    }
    return new Date(dateStr);
  };

  const getTimeAgo = (dateStr) => {
    const date = parseUTC(dateStr);
    if (!date) return '';
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  const getTimeRemaining = (timeoutAt) => {
    if (!timeoutAt) return null;
    const timeout = parseUTC(timeoutAt);
    const now = new Date();
    const diff = timeout - now;
    if (diff <= 0) return 'Expired';
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    if (hours > 0) return `${hours}h ${minutes}m left`;
    return `${minutes}m left`;
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <InboxIcon className="w-7 h-7 text-purple-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Task Inbox</h1>
            <p className="text-sm text-gray-500">Human-in-the-loop tasks requiring your attention</p>
          </div>
        </div>
        <button
          onClick={fetchTasks}
          className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
        >
          <ArrowPathIcon className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-yellow-600">{stats.pending || 0}</div>
          <div className="text-sm text-gray-500">Pending</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-red-600">{stats.urgent || 0}</div>
          <div className="text-sm text-gray-500">Urgent</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-green-600">{stats.completed || 0}</div>
          <div className="text-sm text-gray-500">Completed</div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-2xl font-bold text-orange-600">{stats.escalated || 0}</div>
          <div className="text-sm text-gray-500">Escalated</div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex items-center gap-2">
          <FunnelIcon className="w-4 h-4 text-gray-500" />
          <div className="flex gap-1">
            {[
              { value: 'pending', label: 'Pending' },
              { value: 'completed', label: 'Completed' },
              { value: 'expired', label: 'Expired' },
              { value: '', label: 'All' },
            ].map(f => (
              <button
                key={f.value}
                onClick={() => { setStatusFilter(f.value); setOffset(0); }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md ${
                  statusFilter === f.value
                    ? 'bg-purple-100 text-purple-700 border border-purple-300'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 max-w-xs">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tasks..."
              className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-purple-500 focus:border-purple-500"
            />
          </div>
        </div>
      </div>

      {/* Task List */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <ArrowPathIcon className="w-6 h-6 animate-spin text-purple-600" />
          <span className="ml-2 text-gray-500">Loading tasks...</span>
        </div>
      ) : filteredTasks.length === 0 ? (
        <div className="text-center py-12">
          <HandRaisedIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-500">No tasks found</p>
          <p className="text-sm text-gray-400 mt-1">
            {statusFilter === 'pending' ? 'No pending tasks - you\'re all caught up!' : 'Try adjusting your filters'}
          </p>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-200">
          {filteredTasks.map(task => {
            const statusInfo = statusConfig[task.status] || statusConfig.pending;
            const StatusIcon = statusInfo.icon;
            const timeRemaining = task.status === 'pending' ? getTimeRemaining(task.timeout_at) : null;

            return (
              <div
                key={task.task_id}
                onClick={() => task.status === 'pending' && handleTaskClick(task)}
                className={`px-5 py-4 flex items-center justify-between ${
                  task.status === 'pending' ? 'hover:bg-purple-50 cursor-pointer' : ''
                } transition-colors`}
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <StatusIcon className={`w-5 h-5 flex-shrink-0 ${
                    task.status === 'pending' ? 'text-yellow-500' :
                    task.status === 'completed' ? 'text-green-500' : 'text-gray-400'
                  }`} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900 truncate">{task.title}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${priorityConfig[task.priority] || priorityConfig.medium}`}>
                        {task.priority}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-purple-100 text-purple-700">
                        {taskTypeLabels[task.task_type] || task.task_type}
                      </span>
                    </div>
                    {task.description && (
                      <p className="text-xs text-gray-600 mt-0.5 line-clamp-1">{task.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-xs text-gray-500">{task.flow_name || 'Unknown flow'}</span>
                      <span className="text-xs text-gray-400">{getTimeAgo(task.created_at)}</span>
                      {timeRemaining && (
                        <span className={`text-xs flex items-center gap-1 ${
                          timeRemaining === 'Expired' ? 'text-red-500' : 'text-gray-400'
                        }`}>
                          <ClockIcon className="w-3 h-3" />
                          {timeRemaining}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusInfo.color}`}>
                    {statusInfo.label}
                  </span>
                  {task.completed_by_name && (
                    <span className="text-xs text-gray-400">by {task.completed_by_name}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between mt-4">
          <span className="text-sm text-gray-500">
            Showing {offset + 1}-{Math.min(offset + limit, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-50 hover:bg-gray-50"
            >
              Previous
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:opacity-50 hover:bg-gray-50"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Review Modal */}
      <TaskReviewModal
        task={selectedTask}
        isOpen={showReviewModal}
        onClose={() => { setShowReviewModal(false); setSelectedTask(null); }}
        onCompleted={handleTaskCompleted}
      />
    </div>
  );
};

export default TaskInbox;
