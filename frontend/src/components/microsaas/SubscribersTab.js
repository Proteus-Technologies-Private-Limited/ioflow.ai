import React, { useState, useEffect } from 'react';
import { UserGroupIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import { microSaasService } from '../../services/microSaasService';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const SubscribersTab = ({ appId, app }) => {
  const [subscribers, setSubscribers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');

  useEffect(() => {
    loadSubscribers();
  }, [appId, statusFilter]);

  const loadSubscribers = async () => {
    setIsLoading(true);
    try {
      const params = {};
      if (statusFilter) params.status_filter = statusFilter;

      const data = await microSaasService.getSubscribers(appId, params);
      setSubscribers(data.subscribers || []);
    } catch (error) {
      console.error('Error loading subscribers:', error);
      showErrorToast('Failed to load subscribers');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header with Filter */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">Subscribers</h3>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="paused">Paused</option>
          <option value="expired">Expired</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>

      {/* Subscribers List or Empty State */}
      {subscribers.length === 0 ? (
        <div className="text-center py-12">
          <UserGroupIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No subscribers yet</h3>
          <p className="mt-1 text-sm text-gray-500">
            Subscribers will appear here once users start using your app.
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Subscriber
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Executions
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Total Paid
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Since
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {subscribers.map((subscriber) => (
                <tr key={subscriber.subscriber_id}>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{subscriber.subscriber_name}</div>
                    <div className="text-sm text-gray-500">{subscriber.subscriber_email}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      subscriber.subscription_status === 'active' ? 'bg-green-100 text-green-800' :
                      subscriber.subscription_status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                      subscriber.subscription_status === 'expired' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {subscriber.subscription_status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {subscriber.execution_count}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${subscriber.total_paid.toFixed(2)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(subscriber.subscribed_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default SubscribersTab;
