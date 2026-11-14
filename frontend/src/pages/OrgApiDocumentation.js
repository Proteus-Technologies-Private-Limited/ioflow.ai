import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import {
  DocumentTextIcon,
  MagnifyingGlassIcon,
  BoltIcon,
  ClockIcon,
  ArrowRightIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const STATUS_BADGE_CLASSES = {
  active: 'bg-green-50 text-green-700',
  inactive: 'bg-gray-100 text-gray-600',
  draft: 'bg-yellow-50 text-yellow-700',
  archived: 'bg-gray-100 text-gray-500',
};

function StatusBadge({ status }) {
  const cls = STATUS_BADGE_CLASSES[status] || 'bg-gray-100 text-gray-600';
  return (
    <span className={`inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full ${cls}`}>
      {status}
    </span>
  );
}

function ModeBadge({ isSynchronous }) {
  return isSynchronous ? (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-700">
      <BoltIcon className="h-3 w-3" /> Sync
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-purple-50 text-purple-700">
      <ClockIcon className="h-3 w-3" /> Async
    </span>
  );
}

export default function OrgApiDocumentation() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const { data: flows = [], isLoading, error } = useQuery({
    queryKey: ['org-api-docs-flows'],
    queryFn: async () => {
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/flows/?include_stats=false&include_user_info=false`
      );
      return response.data;
    },
  });

  const filteredFlows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return flows.filter((f) => {
      if (statusFilter !== 'all' && f.status !== statusFilter) return false;
      if (!term) return true;
      return (
        (f.flow_name || '').toLowerCase().includes(term) ||
        (f.description || '').toLowerCase().includes(term) ||
        (f.category || '').toLowerCase().includes(term)
      );
    });
  }, [flows, search, statusFilter]);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-primary/10 rounded-lg">
              <DocumentTextIcon className="h-6 w-6 text-primary" />
            </div>
            <h1 className="text-2xl font-bold text-gray-900">API Documentation</h1>
          </div>
          <p className="text-sm text-gray-500">
            All APIs available in your organization. Every flow in your tenant can be executed via the Flow API;
            click a flow to view its full API reference with authentication, parameters, request/response schema, and code samples.
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 relative">
              <MagnifyingGlassIcon className="h-4 w-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search flows by name, description, or category"
                className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
            >
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="draft">Draft</option>
              <option value="archived">Archived</option>
            </select>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 flex items-start gap-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="text-sm font-semibold text-red-800">Failed to load flows</h3>
              <p className="text-sm text-red-700 mt-1">{error.message}</p>
            </div>
          </div>
        ) : filteredFlows.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <DocumentTextIcon className="h-10 w-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">
              {flows.length === 0
                ? 'No flows have been created yet. Once you create flows, they will appear here with their API documentation.'
                : 'No flows match the current search or filter.'}
            </p>
          </div>
        ) : (
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
              <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">
                {filteredFlows.length} API{filteredFlows.length === 1 ? '' : 's'}
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50">
                    <th className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Name</th>
                    <th className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Category</th>
                    <th className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Mode</th>
                    <th className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-2 text-xs font-semibold text-gray-500 uppercase">Endpoint</th>
                    <th className="px-4 py-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFlows.map((flow) => {
                    const endpoint = flow.is_synchronous
                      ? `/api/v1/flows/${flow.flow_id}/execute-direct-sync`
                      : `/api/v1/flows/${flow.flow_id}/execute-direct`;
                    return (
                      <tr
                        key={flow.flow_id}
                        onClick={() => navigate(`/flows/${flow.flow_id}/api-docs`)}
                        className="border-b border-gray-100 last:border-0 hover:bg-gray-50 cursor-pointer"
                      >
                        <td className="px-4 py-3">
                          <div className="font-medium text-gray-900">{flow.flow_name}</div>
                          {flow.description && (
                            <div className="text-xs text-gray-500 mt-0.5 line-clamp-2 max-w-md">
                              {flow.description}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {flow.category || <span className="text-gray-400">—</span>}
                        </td>
                        <td className="px-4 py-3">
                          <ModeBadge isSynchronous={flow.is_synchronous} />
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={flow.status} />
                        </td>
                        <td className="px-4 py-3">
                          <code className="text-xs font-mono bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded">
                            POST {endpoint}
                          </code>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate(`/flows/${flow.flow_id}/api-docs`);
                            }}
                            className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:text-primary/80"
                          >
                            View Docs
                            <ArrowRightIcon className="h-3.5 w-3.5" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
