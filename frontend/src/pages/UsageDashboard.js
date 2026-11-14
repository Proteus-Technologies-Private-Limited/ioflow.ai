import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import {
  ChartBarIcon,
  ArrowDownTrayIcon,
  CalendarIcon,
  CurrencyDollarIcon,
  ServerIcon,
  ClockIcon,
  ArrowPathIcon,
  FunnelIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

function UsageDashboard() {
  const navigate = useNavigate();
  const [dateRange, setDateRange] = useState('last_30_days');
  const [selectedApp, setSelectedApp] = useState('all');
  const [viewMode, setViewMode] = useState('overview'); // overview, detailed, applications
  const [refreshing, setRefreshing] = useState(false);

  // Calculate date range
  const getDateRange = () => {
    const end = new Date();
    let start = new Date();

    switch (dateRange) {
      case 'today':
        start.setHours(0, 0, 0, 0);
        break;
      case 'last_7_days':
        start.setDate(start.getDate() - 7);
        break;
      case 'last_30_days':
        start.setDate(start.getDate() - 30);
        break;
      case 'this_month':
        start.setDate(1);
        break;
      case 'last_month':
        start.setMonth(start.getMonth() - 1);
        start.setDate(1);
        end.setDate(0); // Last day of previous month
        break;
      default:
        start.setDate(start.getDate() - 30);
    }

    return {
      start_date: start.toISOString().split('T')[0],
      end_date: end.toISOString().split('T')[0]
    };
  };

  // Fetch usage summary
  const { data: usageSummary, isLoading, refetch } = useQuery({
    queryKey: ['usage-summary', dateRange, selectedApp],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const { start_date, end_date } = getDateRange();
      let url = `${API_BASE_URL}/api/v1/tenant/usage/summary?start_date=${start_date}&end_date=${end_date}`;

      if (selectedApp !== 'all') {
        url += `&app_id=${selectedApp}`;
      }

      const response = await axios.get(url, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    }
  });

  // Fetch application list
  const { data: applications = [] } = useQuery({
    queryKey: ['applications-list'],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    }
  });

  // Fetch application-specific usage
  const { data: appUsageData } = useQuery({
    queryKey: ['app-usage', selectedApp, dateRange],
    queryFn: async () => {
      if (selectedApp === 'all') return null;

      const token = localStorage.getItem('access_token');
      const { start_date, end_date } = getDateRange();
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/tenant/usage/applications/${selectedApp}?start_date=${start_date}&end_date=${end_date}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      return response.data;
    },
    enabled: selectedApp !== 'all'
  });

  const handleRefresh = async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  };

  const handleExport = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const { start_date, end_date } = getDateRange();
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/tenant/usage/export?start_date=${start_date}&end_date=${end_date}&format=csv`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'text/csv'
          },
          responseType: 'blob'
        }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `usage_report_${start_date}_${end_date}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Failed to export usage data:', error);
    }
  };

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount || 0);
  };

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US').format(num || 0);
  };

  // Prepare chart data
  const dailyUsageChartData = {
    labels: usageSummary?.daily_usage?.map(d => d.date) || [],
    datasets: [
      {
        label: 'Executions',
        data: usageSummary?.daily_usage?.map(d => d.executions) || [],
        borderColor: 'rgb(59, 130, 246)',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        fill: true,
        tension: 0.4,
      }
    ]
  };

  const costBreakdownChartData = {
    labels: ['API Calls', 'Data Transfer', 'Token Usage'],
    datasets: [{
      data: [
        usageSummary?.cost_breakdown?.service_cost || 0,
        usageSummary?.cost_breakdown?.data_cost || 0,
        usageSummary?.cost_breakdown?.token_cost || 0,
      ],
      backgroundColor: [
        'rgba(59, 130, 246, 0.8)',
        'rgba(34, 197, 94, 0.8)',
        'rgba(168, 85, 247, 0.8)',
      ],
      borderWidth: 0,
    }]
  };

  const topApplicationsChartData = {
    labels: usageSummary?.by_application?.slice(0, 5).map(a => a.app_name) || [],
    datasets: [{
      label: 'Executions',
      data: usageSummary?.by_application?.slice(0, 5).map(a => a.total_executions) || [],
      backgroundColor: 'rgba(59, 130, 246, 0.8)',
    }]
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Usage Dashboard</h1>
              <p className="mt-1 text-sm text-gray-500">
                Monitor your application usage and costs
              </p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="p-2 text-gray-600 hover:text-gray-900 disabled:opacity-50"
                title="Refresh"
              >
                <ArrowPathIcon className={`h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={handleExport}
                className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                Export
              </button>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-6 bg-white rounded-lg shadow p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date Range</label>
              <select
                value={dateRange}
                onChange={(e) => setDateRange(e.target.value)}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary"
              >
                <option value="today">Today</option>
                <option value="last_7_days">Last 7 Days</option>
                <option value="last_30_days">Last 30 Days</option>
                <option value="this_month">This Month</option>
                <option value="last_month">Last Month</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Application</label>
              <select
                value={selectedApp}
                onChange={(e) => setSelectedApp(e.target.value)}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary"
              >
                <option value="all">All Applications</option>
                {applications.map(app => (
                  <option key={app.app_id} value={app.app_id}>
                    {app.app_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">View Mode</label>
              <select
                value={viewMode}
                onChange={(e) => setViewMode(e.target.value)}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary"
              >
                <option value="overview">Overview</option>
                <option value="detailed">Detailed</option>
                <option value="applications">By Application</option>
              </select>
            </div>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div className="p-2 bg-blue-100 rounded-lg">
                <ServerIcon className="h-6 w-6 text-primary" />
              </div>
            </div>
            <p className="text-sm text-gray-600 mt-4 mb-1">Total Executions</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatNumber(usageSummary?.total_executions)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div className="p-2 bg-green-100 rounded-lg">
                <CurrencyDollarIcon className="h-6 w-6 text-green-600" />
              </div>
            </div>
            <p className="text-sm text-gray-600 mt-4 mb-1">Total Cost</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatCurrency(usageSummary?.total_cost)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div className="p-2 bg-purple-100 rounded-lg">
                <ChartBarIcon className="h-6 w-6 text-purple-600" />
              </div>
            </div>
            <p className="text-sm text-gray-600 mt-4 mb-1">Data Transfer</p>
            <p className="text-2xl font-bold text-gray-900">
              {formatNumber((usageSummary?.total_data_kb || 0) / 1024)} MB
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div className="p-2 bg-yellow-100 rounded-lg">
                <ClockIcon className="h-6 w-6 text-yellow-600" />
              </div>
            </div>
            <p className="text-sm text-gray-600 mt-4 mb-1">Avg Response Time</p>
            <p className="text-2xl font-bold text-gray-900">
              {usageSummary?.avg_response_time || 0} ms
            </p>
          </div>
        </div>

        {/* Charts Section */}
        {viewMode === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            {/* Daily Usage Trend */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Usage Trend</h3>
              <Line data={dailyUsageChartData} options={{
                responsive: true,
                plugins: {
                  legend: { display: false },
                  tooltip: {
                    mode: 'index',
                    intersect: false,
                  }
                },
                scales: {
                  y: {
                    beginAtZero: true,
                    ticks: {
                      precision: 0
                    }
                  }
                }
              }} />
            </div>

            {/* Cost Breakdown */}
            {usageSummary?.total_cost > 0 && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Cost Breakdown</h3>
                <Doughnut data={costBreakdownChartData} options={{
                  responsive: true,
                  plugins: {
                    legend: {
                      position: 'bottom'
                    }
                  }
                }} />
              </div>
            )}
          </div>
        )}

        {/* Application Usage Table */}
        {viewMode === 'applications' && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Application Usage</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Application
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Billing Mode
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Executions
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Data (MB)
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tokens
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Cost
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {usageSummary?.by_application?.map((app) => (
                    <tr
                      key={app.app_id}
                      className="hover:bg-gray-50 cursor-pointer"
                      onClick={() => navigate(`/applications/${app.app_id}`)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {app.app_name}
                            </div>
                            <div className="text-sm text-gray-500">
                              {app.app_id.substring(0, 8)}...
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          app.billing_mode === 'free' ? 'bg-green-100 text-green-800' :
                          app.billing_mode === 'prepaid' ? 'bg-blue-100 text-blue-800' :
                          app.billing_mode === 'postpaid' ? 'bg-purple-100 text-purple-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {app.billing_mode ? app.billing_mode.toUpperCase() : 'PREPAID'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                        {formatNumber(app.total_executions)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                        {((app.total_data_kb || 0) / 1024).toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm text-gray-900">
                        {formatNumber(app.total_tokens)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        {app.billing_mode === 'free' ? (
                          <span className="text-green-600">Free</span>
                        ) : (
                          <span className="text-gray-900">{formatCurrency(app.total_cost)}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Top Applications Bar Chart */}
        {viewMode === 'detailed' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Applications by Usage</h3>
              <Bar data={topApplicationsChartData} options={{
                responsive: true,
                plugins: {
                  legend: { display: false },
                },
                scales: {
                  y: {
                    beginAtZero: true,
                    ticks: {
                      precision: 0
                    }
                  }
                }
              }} />
            </div>

            {/* Service Type Breakdown */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Service Type Breakdown</h3>
              <div className="space-y-4">
                {usageSummary?.by_service_type?.map((service) => (
                  <div key={service.service_type}>
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm font-medium text-gray-700">
                        {service.service_type}
                      </span>
                      <span className="text-sm text-gray-500">
                        {formatNumber(service.count)} calls
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div
                        className="bg-primary h-2 rounded-full"
                        style={{
                          width: `${(service.count / usageSummary.total_executions) * 100}%`
                        }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Free vs Paid Usage Summary */}
        <div className="mt-8 bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Usage Summary</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-primary">
                {usageSummary?.free_executions || 0}
              </div>
              <p className="text-sm text-gray-600 mt-1">Free Executions</p>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">
                {usageSummary?.paid_executions || 0}
              </div>
              <p className="text-sm text-gray-600 mt-1">Paid Executions</p>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-purple-600">
                {formatCurrency(usageSummary?.total_savings || 0)}
              </div>
              <p className="text-sm text-gray-600 mt-1">Saved with Free Apps</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default UsageDashboard;