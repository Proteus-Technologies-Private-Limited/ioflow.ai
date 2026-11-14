/**
 * Marketplace Approval Admin Page
 * Instance admin page to manage marketplace app approvals
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle,
  XCircle,
  Clock,
  Filter,
  ArrowUpDown,
  Eye,
  AlertCircle,
  Search,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { useAuth } from '../../contexts/AuthContext';

const MarketplaceApprovalAdmin = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: 20,
    total: 0,
    total_pages: 0
  });

  // Filters
  const [filters, setFilters] = useState({
    status: '',
    tenant_id: '',
    visibility: ''
  });

  // Sorting
  const [sorting, setSorting] = useState({
    sort_by: 'created_at',
    sort_order: 'desc'
  });

  // Action states
  const [actionLoading, setActionLoading] = useState({});
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');
  const [reviewAction, setReviewAction] = useState('approve');

  useEffect(() => {
    // Check if user is instance admin
    if (user && user.role !== 'INSTANCE_ADMIN') {
      toast.error('Access denied. Instance admin only.');
      navigate('/dashboard');
      return;
    }
    loadApps();
  }, [pagination.page, filters, sorting]);

  const loadApps = async () => {
    try {
      setLoading(true);
      const params = {
        page: pagination.page,
        page_size: pagination.page_size,
        ...filters,
        ...sorting
      };

      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === '') delete params[key];
      });

      console.log('Fetching apps with params:', params);
      const response = await axios.get('/api/v1/marketplace/admin/apps', { params });
      console.log('Response:', response.data);
      setApps(response.data.apps);
      setPagination(prev => ({
        ...prev,
        total: response.data.total,
        total_pages: response.data.total_pages
      }));
    } catch (error) {
      console.error('Error loading apps:', error);
      console.error('Error response:', error.response?.data);
      console.error('Error status:', error.response?.status);
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || error.message || 'Failed to load apps';
      toast.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (app) => {
    setSelectedApp(app);
    setReviewAction('approve');
    setReviewNotes('');
    setShowReviewModal(true);
  };

  const handleReject = async (app) => {
    setSelectedApp(app);
    setReviewAction('reject');
    setRejectionReason('');
    setReviewNotes('');
    setShowReviewModal(true);
  };

  const submitReview = async () => {
    if (!selectedApp) return;

    try {
      setActionLoading({ [selectedApp.frontend_app_id]: true });

      const payload = {
        status: reviewAction === 'approve' ? 'approved' : 'rejected',
        review_notes: reviewNotes,
        rejection_reason: reviewAction === 'reject' ? rejectionReason : undefined
      };

      await axios.post(
        `/api/v1/marketplace/admin/apps/${selectedApp.frontend_app_id}/approve`,
        payload
      );

      toast.success(
        reviewAction === 'approve'
          ? `${selectedApp.frontend_app_name} approved successfully`
          : `${selectedApp.frontend_app_name} rejected`
      );

      setShowReviewModal(false);
      setSelectedApp(null);
      setReviewNotes('');
      setRejectionReason('');
      loadApps();
    } catch (error) {
      console.error('Error reviewing app:', error);
      toast.error(
        (error.response?.data?.message || error.response?.data?.detail) || 'Failed to review app'
      );
    } finally {
      setActionLoading({});
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      approved: { color: 'bg-green-100 text-green-800', icon: CheckCircle, label: 'Approved' },
      auto_approved: { color: 'bg-green-100 text-green-800', icon: CheckCircle, label: 'Auto Approved' },
      pending: { color: 'bg-yellow-100 text-yellow-800', icon: Clock, label: 'Pending' },
      rejected: { color: 'bg-red-100 text-red-800', icon: XCircle, label: 'Rejected' },
      draft: { color: 'bg-gray-100 text-gray-800', icon: AlertCircle, label: 'Draft' }
    };

    const config = statusConfig[status] || statusConfig.draft;
    const Icon = config.icon;

    return (
      <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
        <Icon className="w-3 h-3" />
        {config.label}
      </span>
    );
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const handleSort = (field) => {
    setSorting(prev => ({
      sort_by: field,
      sort_order: prev.sort_by === field && prev.sort_order === 'asc' ? 'desc' : 'asc'
    }));
  };

  return (
    <div className="container mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Marketplace App Approvals</h1>
        <p className="mt-1 text-sm text-gray-600">
          Manage and review marketplace app submissions
        </p>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Filter className="w-5 h-5 text-gray-600" />
          <h2 className="text-lg font-semibold text-gray-900">Filters</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Status
            </label>
            <select
              value={filters.status}
              onChange={(e) => {
                setFilters(prev => ({ ...prev, status: e.target.value }));
                setPagination(prev => ({ ...prev, page: 1 }));
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            >
              <option value="">All Status</option>
              <option value="pending">Pending</option>
              <option value="approved">Approved</option>
              <option value="auto_approved">Auto Approved</option>
              <option value="rejected">Rejected</option>
              <option value="draft">Draft</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Visibility
            </label>
            <select
              value={filters.visibility}
              onChange={(e) => {
                setFilters(prev => ({ ...prev, visibility: e.target.value }));
                setPagination(prev => ({ ...prev, page: 1 }));
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            >
              <option value="">All Visibility</option>
              <option value="public">Public</option>
              <option value="private">Private</option>
              <option value="granted_access">Granted Access</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Sort By
            </label>
            <select
              value={sorting.sort_by}
              onChange={(e) => setSorting(prev => ({ ...prev, sort_by: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            >
              <option value="created_at">Date Created</option>
              <option value="frontend_app_name">App Name</option>
              <option value="marketplace_status">Status</option>
              <option value="tenant_id">Tenant</option>
            </select>
          </div>
        </div>

        {/* Results info */}
        <div className="mt-4 pt-4 border-t border-gray-200 flex items-center justify-between">
          <p className="text-sm text-gray-600">
            Showing {apps.length} of {pagination.total} apps
          </p>
          <button
            onClick={() => {
              setFilters({ status: '', tenant_id: '', visibility: '' });
              setSorting({ sort_by: 'created_at', sort_order: 'desc' });
              setPagination(prev => ({ ...prev, page: 1 }));
            }}
            className="text-sm text-primary hover:text-primary-dark font-medium"
          >
            Reset Filters
          </button>
        </div>
      </div>

      {/* Apps Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          </div>
        ) : apps.length === 0 ? (
          <div className="text-center py-12">
            <AlertCircle className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600">No apps found</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('frontend_app_name')}>
                      <div className="flex items-center gap-2">
                        App Name
                        <ArrowUpDown className="w-4 h-4" />
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Creator
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('marketplace_status')}>
                      <div className="flex items-center gap-2">
                        Status
                        <ArrowUpDown className="w-4 h-4" />
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Visibility
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                        onClick={() => handleSort('created_at')}>
                      <div className="flex items-center gap-2">
                        Created
                        <ArrowUpDown className="w-4 h-4" />
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Stats
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {apps.map((app) => (
                    <tr key={app.frontend_app_id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {app.frontend_app_name}
                            </div>
                            <div className="text-sm text-gray-500 max-w-xs truncate">
                              {app.description}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">{app.creator_name || 'N/A'}</div>
                        <div className="text-sm text-gray-500">{app.creator_email}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(app.marketplace_status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm capitalize text-gray-900">
                          {app.visibility}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">
                          {formatDate(app.created_at)}
                        </div>
                        {app.approved_at && (
                          <div className="text-sm text-gray-500">
                            Approved: {formatDate(app.approved_at)}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <div>⭐ {app.avg_rating.toFixed(1)} ({app.total_reviews})</div>
                        <div>👥 {app.total_subscribers} subscribers</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => window.open(`/marketplace/app/${app.public_url_slug}`, '_blank')}
                            className="text-gray-600 hover:text-gray-900"
                            title="View App"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                          {app.marketplace_status === 'pending' && (
                            <>
                              <button
                                onClick={() => handleApprove(app)}
                                disabled={actionLoading[app.frontend_app_id]}
                                className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => handleReject(app)}
                                disabled={actionLoading[app.frontend_app_id]}
                                className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                              >
                                Reject
                              </button>
                            </>
                          )}
                          {(app.marketplace_status === 'approved' || app.marketplace_status === 'auto_approved') && (
                            <button
                              onClick={() => handleReject(app)}
                              disabled={actionLoading[app.frontend_app_id]}
                              className="px-3 py-1 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                            >
                              Revoke
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="bg-white px-4 py-3 border-t border-gray-200 sm:px-6">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-700">
                  Page <span className="font-medium">{pagination.page}</span> of{' '}
                  <span className="font-medium">{pagination.total_pages}</span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
                    disabled={pagination.page === 1}
                    className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                  >
                    <ChevronLeft className="w-4 h-4" />
                    Previous
                  </button>
                  <button
                    onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                    disabled={pagination.page === pagination.total_pages}
                    className="px-3 py-1 border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                  >
                    Next
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Review Modal */}
      {showReviewModal && selectedApp && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="fixed inset-0 bg-black bg-opacity-50" onClick={() => setShowReviewModal(false)} />

          <div className="flex min-h-full items-center justify-center p-4">
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                {reviewAction === 'approve' ? 'Approve App' : 'Reject App'}
              </h3>

              <div className="mb-4">
                <p className="text-sm text-gray-600 mb-2">
                  <strong>App:</strong> {selectedApp.frontend_app_name}
                </p>
                <p className="text-sm text-gray-600">
                  <strong>Creator:</strong> {selectedApp.creator_name} ({selectedApp.creator_email})
                </p>
              </div>

              {reviewAction === 'reject' && (
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Rejection Reason *
                  </label>
                  <textarea
                    value={rejectionReason}
                    onChange={(e) => setRejectionReason(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                    placeholder="Please provide a reason for rejection..."
                  />
                </div>
              )}

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Review Notes (optional)
                </label>
                <textarea
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                  placeholder="Add any additional notes..."
                />
              </div>

              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowReviewModal(false)}
                  className="px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={submitReview}
                  disabled={reviewAction === 'reject' && !rejectionReason}
                  className={`px-4 py-2 text-white rounded-md ${
                    reviewAction === 'approve'
                      ? 'bg-green-600 hover:bg-green-700'
                      : 'bg-red-600 hover:bg-red-700'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {reviewAction === 'approve' ? 'Approve' : 'Reject'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MarketplaceApprovalAdmin;
