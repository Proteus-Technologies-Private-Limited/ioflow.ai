import React, { useState, useEffect } from 'react';
import { ChartBarIcon, BoltIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import { microSaasService } from '../../services/microSaasService';
import { showErrorToast } from '../../utils/customToast';

const AnalyticsTab = ({ appId, app }) => {
  const [analytics, setAnalytics] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dateRange, setDateRange] = useState('30'); // days

  useEffect(() => {
    loadAnalytics();
  }, [appId, dateRange]);

  const loadAnalytics = async () => {
    setIsLoading(true);
    try {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - parseInt(dateRange));

      const data = await microSaasService.getAnalytics(appId, {
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString()
      });
      setAnalytics(data);
    } catch (error) {
      console.error('Error loading analytics:', error);
      showErrorToast('Failed to load analytics');
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

  if (!analytics) {
    return (
      <div className="text-center py-12">
        <ChartBarIcon className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-2 text-sm font-medium text-gray-900">No analytics data</h3>
        <p className="mt-1 text-sm text-gray-500">Analytics data will appear here once your app has some activity.</p>
      </div>
    );
  }

  const { execution_metrics, revenue_metrics, subscriber_metrics, executions_by_day } = analytics;

  return (
    <div className="space-y-6">
      {/* Date Range Selector */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">Usage & Analytics</h3>
        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
        >
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
        </select>
      </div>

      {/* Execution Metrics */}
      <div>
        <h4 className="text-sm font-medium text-gray-700 mb-3">Execution Metrics</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <BoltIcon className="h-8 w-8 text-primary" />
              <div className="ml-3">
                <p className="text-2xl font-bold text-gray-900">{execution_metrics.total_executions}</p>
                <p className="text-sm text-gray-500">Total Executions</p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <CheckCircleIcon className="h-8 w-8 text-green-600" />
              <div className="ml-3">
                <p className="text-2xl font-bold text-gray-900">{execution_metrics.successful_executions}</p>
                <p className="text-sm text-gray-500">Successful</p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <XCircleIcon className="h-8 w-8 text-red-600" />
              <div className="ml-3">
                <p className="text-2xl font-bold text-gray-900">{execution_metrics.failed_executions}</p>
                <p className="text-sm text-gray-500">Failed</p>
              </div>
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center">
              <ChartBarIcon className="h-8 w-8 text-blue-600" />
              <div className="ml-3">
                <p className="text-2xl font-bold text-gray-900">{Math.round(execution_metrics.average_execution_time_ms)}ms</p>
                <p className="text-sm text-gray-500">Avg Time</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Revenue Metrics (if paid app) */}
      {revenue_metrics && app.billing_preference !== 'free' && (
        <div className="border-t border-gray-200 pt-6">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Revenue Metrics</h4>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <p className="text-2xl font-bold text-green-900">${revenue_metrics.total_revenue.toFixed(2)}</p>
              <p className="text-sm text-green-700">Total Revenue</p>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-2xl font-bold text-blue-900">${revenue_metrics.revenue_this_month.toFixed(2)}</p>
              <p className="text-sm text-blue-700">This Month</p>
            </div>
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <p className="text-2xl font-bold text-purple-900">${revenue_metrics.revenue_last_month.toFixed(2)}</p>
              <p className="text-sm text-purple-700">Last Month</p>
            </div>
          </div>
        </div>
      )}

      {/* Subscriber Metrics */}
      <div className="border-t border-gray-200 pt-6">
        <h4 className="text-sm font-medium text-gray-700 mb-3">Subscriber Metrics</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <p className="text-2xl font-bold text-gray-900">{subscriber_metrics.total_subscribers}</p>
            <p className="text-sm text-gray-500">Total Subscribers</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <p className="text-2xl font-bold text-green-600">{subscriber_metrics.active_subscribers}</p>
            <p className="text-sm text-gray-500">Active</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <p className="text-2xl font-bold text-blue-600">{subscriber_metrics.new_subscribers_this_month}</p>
            <p className="text-sm text-gray-500">New This Month</p>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <p className="text-2xl font-bold text-red-600">{subscriber_metrics.cancelled_this_month}</p>
            <p className="text-sm text-gray-500">Cancelled</p>
          </div>
        </div>
      </div>

      {/* Executions by Day Chart */}
      {executions_by_day && executions_by_day.length > 0 && (
        <div className="border-t border-gray-200 pt-6">
          <h4 className="text-sm font-medium text-gray-700 mb-3">Executions by Day</h4>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="space-y-2">
              {executions_by_day.slice(-14).map((day, index) => (
                <div key={index} className="flex items-center">
                  <div className="w-24 text-sm text-gray-600">{day.date}</div>
                  <div className="flex-1 mx-4">
                    <div className="bg-gray-200 rounded-full h-4">
                      <div
                        className="bg-primary h-4 rounded-full"
                        style={{
                          width: `${Math.min((day.count / Math.max(...executions_by_day.map(d => d.count))) * 100, 100)}%`
                        }}
                      ></div>
                    </div>
                  </div>
                  <div className="w-16 text-right text-sm font-medium text-gray-900">{day.count}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalyticsTab;
