import React, { useState, useEffect, useCallback } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  PauseCircleIcon,
  FunnelIcon,
} from '@heroicons/react/24/outline';
import axios from 'axios';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'RUNNING', label: 'Running' },
  { value: 'PAUSED', label: 'Paused' },
  { value: 'CANCELLED', label: 'Cancelled' },
];

const TIMEFRAME_OPTIONS = [
  { value: '1h', label: 'Last Hour' },
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
  { value: 'all', label: 'All Time' },
];

const SCOPE_OPTIONS = [
  { value: 'user', label: 'My Executions' },
  { value: 'all', label: 'All Users' },
];

const statusIcon = (status) => {
  switch (status?.toUpperCase()) {
    case 'COMPLETED': return <CheckCircleIcon className="w-4 h-4 text-green-600" />;
    case 'FAILED': return <XCircleIcon className="w-4 h-4 text-red-600" />;
    case 'RUNNING': return <ArrowPathIcon className="w-4 h-4 text-blue-600 animate-spin" />;
    case 'PAUSED': return <PauseCircleIcon className="w-4 h-4 text-yellow-600" />;
    default: return <ClockIcon className="w-4 h-4 text-gray-400" />;
  }
};

const statusBadge = (status) => {
  const colors = {
    COMPLETED: 'bg-green-100 text-green-700',
    FAILED: 'bg-red-100 text-red-700',
    RUNNING: 'bg-blue-100 text-blue-700',
    PAUSED: 'bg-yellow-100 text-yellow-700',
    CANCELLED: 'bg-gray-100 text-gray-600',
  };
  return colors[status?.toUpperCase()] || 'bg-gray-100 text-gray-600';
};

export default function ExecutionsListSection({ config, appInfo, previewMode }) {
  const [executions, setExecutions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);

  const [statusFilter, setStatusFilter] = useState(config.defaultStatus || 'all');
  const [timeframe, setTimeframe] = useState(config.defaultTimeframe || '7d');
  const [scope, setScope] = useState(config.defaultScope || 'user');

  const pageSize = config.pageSize || 10;
  const slug = appInfo?.public_url_slug;

  const fetchExecutions = useCallback(async () => {
    if (previewMode || !slug) return;
    setLoading(true);
    try {
      const params = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (statusFilter !== 'all') params.status_filter = statusFilter;

      const resp = await axios.get(`/api/v1/public-apps/${slug}/executions`, { params });
      const data = resp.data;
      let items = Array.isArray(data) ? data : (data.executions || []);
      // Filter by timeframe client-side
      if (timeframe !== 'all') {
        const now = Date.now();
        const ms = { '1h': 3600000, '24h': 86400000, '7d': 604800000, '30d': 2592000000 }[timeframe] || 604800000;
        items = items.filter((e) => new Date(e.started_at).getTime() > now - ms);
      }
      setExecutions(items);
      setTotal(data.total || items.length);
    } catch {
      setExecutions([]);
    } finally {
      setLoading(false);
    }
  }, [slug, statusFilter, timeframe, scope, page, pageSize, previewMode]);

  useEffect(() => {
    fetchExecutions();
  }, [fetchExecutions]);

  // Auto-refresh
  useEffect(() => {
    if (!config.autoRefresh || previewMode) return;
    const interval = setInterval(fetchExecutions, (config.autoRefreshInterval || 30) * 1000);
    return () => clearInterval(interval);
  }, [config.autoRefresh, config.autoRefreshInterval, fetchExecutions, previewMode]);

  if (previewMode) {
    return (
      <div className="py-6">
        {config.title && <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>}
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center">
          <FunnelIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Execution history will appear here for authenticated users</p>
        </div>
      </div>
    );
  }

  return (
    <div className="py-6">
      {config.title && <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>}

      {/* Filters */}
      {config.showFilters !== false && (
        <div className="flex flex-wrap gap-3 mb-4">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(0); }}
            className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50"
          >
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select
            value={timeframe}
            onChange={(e) => { setTimeframe(e.target.value); setPage(0); }}
            className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50"
          >
            {TIMEFRAME_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select
            value={scope}
            onChange={(e) => { setScope(e.target.value); setPage(0); }}
            className="px-3 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50"
          >
            {SCOPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button
            onClick={fetchExecutions}
            className="px-3 py-1.5 text-sm text-primary border border-primary/30 rounded-md hover:bg-primary/5"
          >
            <ArrowPathIcon className={`w-4 h-4 inline mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading && executions.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <ArrowPathIcon className="w-6 h-6 text-primary animate-spin" />
          </div>
        ) : executions.length === 0 ? (
          <div className="text-center py-12 text-gray-400 text-sm">No executions found</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600">Started</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600">Duration</th>
                <th className="text-left px-4 py-2.5 font-medium text-gray-600">Trigger</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {executions.map((exec) => {
                const duration = exec.completed_at && exec.started_at
                  ? ((new Date(exec.completed_at) - new Date(exec.started_at)) / 1000).toFixed(1) + 's'
                  : exec.status === 'RUNNING' ? 'Running...' : '-';
                return (
                  <tr key={exec.execution_id} className="hover:bg-gray-50">
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${statusBadge(exec.status)}`}>
                        {statusIcon(exec.status)}
                        {exec.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">
                      {new Date(exec.started_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-gray-600">{duration}</td>
                    <td className="px-4 py-2.5 text-gray-500 text-xs">{exec.trigger_type}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {total > pageSize && (
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-gray-500">
            Showing {page * pageSize + 1}-{Math.min((page + 1) * pageSize, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-3 py-1 text-xs border rounded disabled:opacity-30"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={(page + 1) * pageSize >= total}
              className="px-3 py-1 text-xs border rounded disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
