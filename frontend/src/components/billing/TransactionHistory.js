import React from 'react';
import {
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowPathIcon,
  CurrencyDollarIcon
} from '@heroicons/react/24/outline';
import { formatDateTime, getTimezoneDisplay } from '../../utils/dateFormatter';

function TransactionHistory({ transactions, currency }) {
  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  const getTransactionIcon = (type) => {
    switch (type) {
      case 'topup':
        return <ArrowDownIcon className="h-5 w-5 text-green-600" />;
      case 'debit':
        return <ArrowUpIcon className="h-5 w-5 text-red-600" />;
      case 'refund':
        return <ArrowPathIcon className="h-5 w-5 text-blue-600" />;
      default:
        return <CurrencyDollarIcon className="h-5 w-5 text-gray-600" />;
    }
  };

  const getTransactionColor = (type) => {
    switch (type) {
      case 'topup':
        return 'text-green-600';
      case 'debit':
        return 'text-red-600';
      case 'refund':
        return 'text-blue-600';
      default:
        return 'text-gray-600';
    }
  };

  const getTransactionSign = (type) => {
    switch (type) {
      case 'topup':
      case 'refund':
      case 'bonus':
        return '+';
      case 'debit':
      case 'adjustment':
        return '-';
      default:
        return '';
    }
  };

  if (!transactions || transactions.length === 0) {
    return (
      <div className="px-6 py-12 text-center">
        <CurrencyDollarIcon className="h-12 w-12 text-gray-300 mx-auto mb-4" />
        <p className="text-gray-500">No transactions yet</p>
        <p className="text-sm text-gray-400 mt-1">
          Your transaction history will appear here
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Type
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Description
            </th>
            <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Date & Time ({getTimezoneDisplay()})
            </th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Amount
            </th>
            <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
              Balance After
            </th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {transactions.map((transaction) => (
            <tr key={transaction.transaction_id} className="hover:bg-gray-50">
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="flex items-center">
                  <div className="p-2 bg-gray-100 rounded-lg">
                    {getTransactionIcon(transaction.type)}
                  </div>
                  <span className="ml-3 text-sm font-medium text-gray-900 capitalize">
                    {transaction.type}
                  </span>
                </div>
              </td>
              <td className="px-6 py-4">
                <p className="text-sm text-gray-900 line-clamp-2">
                  {transaction.description || 'No description'}
                </p>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <p className="text-sm text-gray-500">
                  {formatDateTime(transaction.created_at, {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    second: undefined
                  })}
                </p>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <span className={`text-sm font-medium ${getTransactionColor(transaction.type)}`}>
                  {getTransactionSign(transaction.type)}{formatCurrency(Math.abs(transaction.amount))}
                </span>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <span className="text-sm font-medium text-gray-900">
                  {formatCurrency(transaction.balance_after)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default TransactionHistory;