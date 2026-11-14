import React, { useState, useEffect } from 'react';
import { DocumentTextIcon, CurrencyDollarIcon, ArrowUpIcon, ArrowDownIcon } from '@heroicons/react/24/outline';
import { microSaasService } from '../../services/microSaasService';
import { showErrorToast } from '../../utils/customToast';

const BillingHistoryTab = ({ appId, app }) => {
  const [billingHistory, setBillingHistory] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dateRange, setDateRange] = useState('30');

  useEffect(() => {
    loadBillingHistory();
  }, [appId, dateRange]);

  const loadBillingHistory = async () => {
    setIsLoading(true);
    try {
      const endDate = new Date();
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - parseInt(dateRange));

      const data = await microSaasService.getBillingHistory(appId, {
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString()
      });
      setBillingHistory(data);
    } catch (error) {
      console.error('Error loading billing history:', error);
      showErrorToast('Failed to load billing history');
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

  if (!billingHistory) {
    return (
      <div className="text-center py-12">
        <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
        <h3 className="mt-2 text-sm font-medium text-gray-900">No billing history</h3>
        <p className="mt-1 text-sm text-gray-500">Billing transactions will appear here.</p>
      </div>
    );
  }

  const getTransactionIcon = (type) => {
    switch (type) {
      case 'top_up':
      case 'subscription_payment':
        return <ArrowUpIcon className="h-5 w-5 text-green-600" />;
      case 'execution_charge':
        return <ArrowDownIcon className="h-5 w-5 text-red-600" />;
      default:
        return <CurrencyDollarIcon className="h-5 w-5 text-gray-600" />;
    }
  };

  const getTransactionColor = (type) => {
    switch (type) {
      case 'top_up':
      case 'subscription_payment':
        return 'text-green-600';
      case 'execution_charge':
        return 'text-red-600';
      default:
        return 'text-gray-600';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header with Filter */}
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium text-gray-900">Billing History</h3>
        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
        >
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
          <option value="365">Last year</option>
        </select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-sm text-gray-500">Total Transactions</p>
          <p className="text-2xl font-bold text-gray-900">{billingHistory.total_transactions}</p>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-sm text-green-700">Total Revenue</p>
          <p className="text-2xl font-bold text-green-900">
            ${billingHistory.total_revenue.toFixed(2)}
          </p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-sm text-red-700">Total Costs</p>
          <p className="text-2xl font-bold text-red-900">
            ${billingHistory.total_costs.toFixed(2)}
          </p>
        </div>
        <div className="bg-primary-10 border border-primary/30 rounded-lg p-4">
          <p className="text-sm text-primary-dark">Net Revenue</p>
          <p className="text-2xl font-bold text-primary">
            ${billingHistory.net_revenue.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Prepaid Balance (if applicable) */}
      {billingHistory.prepaid_balance !== null && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-blue-700">Prepaid Balance</p>
              <p className="text-2xl font-bold text-blue-900">
                ${billingHistory.prepaid_balance.toFixed(2)}
              </p>
            </div>
            <button
              className="px-4 py-2 text-sm font-medium text-white bg-gradient-primary rounded-md hover:shadow-lg"
              onClick={() => {
                // TODO: Implement top-up modal
                alert('Top-up functionality coming soon!');
              }}
            >
              Top Up
            </button>
          </div>
        </div>
      )}

      {/* Transactions List */}
      {billingHistory.transactions && billingHistory.transactions.length > 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
            <h4 className="text-sm font-medium text-gray-700">Recent Transactions</h4>
          </div>
          <div className="divide-y divide-gray-200">
            {billingHistory.transactions.map((transaction) => (
              <div key={transaction.transaction_id} className="px-6 py-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    {getTransactionIcon(transaction.transaction_type)}
                    <div>
                      <p className="text-sm font-medium text-gray-900">
                        {transaction.description || transaction.transaction_type}
                      </p>
                      <p className="text-xs text-gray-500">
                        {new Date(transaction.created_at).toLocaleString()}
                      </p>
                      {transaction.subscriber_name && (
                        <p className="text-xs text-gray-500">
                          {transaction.subscriber_name}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className={`text-sm font-semibold ${getTransactionColor(transaction.transaction_type)}`}>
                      {transaction.transaction_type.includes('charge') || transaction.transaction_type.includes('cost') ? '-' : '+'}
                      ${transaction.amount.toFixed(2)}
                    </p>
                    <p className="text-xs text-gray-500">
                      {transaction.currency}
                    </p>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                      transaction.status === 'completed' ? 'bg-green-100 text-green-800' :
                      transaction.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                      transaction.status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {transaction.status}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-center py-12 bg-white border border-gray-200 rounded-lg">
          <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No transactions</h3>
          <p className="mt-1 text-sm text-gray-500">
            Transactions will appear here once there is billing activity.
          </p>
        </div>
      )}

      {/* Execution Costs Breakdown */}
      {billingHistory.execution_costs && billingHistory.execution_costs.length > 0 && (
        <div className="border-t border-gray-200 pt-6">
          <h4 className="text-sm font-medium text-gray-700 mb-4">Execution Costs by Day</h4>
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="space-y-2">
              {billingHistory.execution_costs.slice(-14).map((day, index) => (
                <div key={index} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{day.date}</span>
                  <div className="flex items-center space-x-4">
                    <span className="text-sm text-gray-500">{day.executions} executions</span>
                    <span className="text-sm font-medium text-gray-900">${day.cost.toFixed(2)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BillingHistoryTab;
