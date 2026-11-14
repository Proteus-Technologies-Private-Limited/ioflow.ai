import React, { useState, useEffect } from 'react';
import {
  CreditCardIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  CurrencyDollarIcon,
  BanknotesIcon,
  ChartBarIcon,
  CogIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import TopupModal from '../components/billing/TopupModal';
import TransactionHistory from '../components/billing/TransactionHistory';
import BalanceSettings from '../components/billing/BalanceSettings';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

function Billing() {
  const navigate = useNavigate();
  const [balance, setBalance] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showTopupModal, setShowTopupModal] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const fetchBalance = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/tenant/balance`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      setBalance(response.data);
      setError(null);
    } catch (err) {
      console.error('Error fetching balance:', err);
      setError('Failed to load balance information');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchBalance();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchBalance();
  };

  const handleTopupSuccess = () => {
    setShowTopupModal(false);
    fetchBalance();
  };

  const formatCurrency = (amount, currency = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  const getBalanceStatus = () => {
    if (!balance) return 'unknown';
    const { available_balance, low_balance_threshold, critical_balance_threshold } = balance;
    
    if (critical_balance_threshold && available_balance <= critical_balance_threshold) {
      return 'critical';
    }
    if (low_balance_threshold && available_balance <= low_balance_threshold) {
      return 'low';
    }
    return 'healthy';
  };

  const balanceStatus = getBalanceStatus();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <p className="text-gray-600">{error}</p>
          <button
            onClick={fetchBalance}
            className="mt-4 px-4 py-2 bg-gradient-primary text-white rounded hover:shadow-lg"
          >
            Retry
          </button>
        </div>
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
              <h1 className="text-3xl font-bold text-gray-900">Billing & Balance</h1>
              <p className="mt-1 text-sm text-gray-500">
                Manage your prepaid balance and monitor usage
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
                onClick={() => setShowSettings(!showSettings)}
                className="p-2 text-gray-600 hover:text-gray-900"
                title="Settings"
              >
                <CogIcon className="h-5 w-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Balance Alert */}
        {balanceStatus === 'critical' && (
          <div className="mb-6 bg-red-50 border-l-4 border-red-400 p-4">
            <div className="flex">
              <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
              <div className="ml-3">
                <p className="text-sm text-red-700">
                  <span className="font-medium">Critical Balance Alert!</span> Your balance is critically low. 
                  Please top up to avoid service interruption.
                </p>
              </div>
            </div>
          </div>
        )}
        
        {balanceStatus === 'low' && (
          <div className="mb-6 bg-yellow-50 border-l-4 border-yellow-400 p-4">
            <div className="flex">
              <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
              <div className="ml-3">
                <p className="text-sm text-yellow-700">
                  <span className="font-medium">Low Balance Warning</span> - Consider topping up soon.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Balance Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          {/* Current Balance Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2 bg-blue-100 rounded-lg">
                <BanknotesIcon className="h-6 w-6 text-primary" />
              </div>
              <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                balanceStatus === 'healthy' ? 'bg-green-100 text-green-800' :
                balanceStatus === 'low' ? 'bg-yellow-100 text-yellow-800' :
                'bg-red-100 text-red-800'
              }`}>
                {balanceStatus.toUpperCase()}
              </span>
            </div>
            <p className="text-sm text-gray-600 mb-1">Available Balance</p>
            <p className="text-2xl font-bold text-gray-900">
              {balance && formatCurrency(balance.available_balance, balance.currency)}
            </p>
            <div className="mt-4">
              <button
                onClick={() => setShowTopupModal(true)}
                className="w-full px-4 py-2 bg-gradient-primary text-white rounded-lg hover:shadow-lg transition"
              >
                Top Up Balance
              </button>
            </div>
          </div>

          {/* Monthly Spending Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2 bg-purple-100 rounded-lg">
                <ChartBarIcon className="h-6 w-6 text-purple-600" />
              </div>
              <ArrowTrendingUpIcon className="h-5 w-5 text-gray-400" />
            </div>
            <p className="text-sm text-gray-600 mb-1">Monthly Spending</p>
            <p className="text-2xl font-bold text-gray-900">
              {balance && formatCurrency(balance.monthly_spending, balance.currency)}
            </p>
            {balance?.monthly_spending_limit && (
              <div className="mt-2">
                <div className="flex justify-between text-xs text-gray-500 mb-1">
                  <span>Limit</span>
                  <span>{formatCurrency(balance.monthly_spending_limit, balance.currency)}</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-purple-600 h-2 rounded-full"
                    style={{
                      width: `${Math.min(100, (balance.monthly_spending / balance.monthly_spending_limit) * 100)}%`
                    }}
                  ></div>
                </div>
              </div>
            )}
          </div>

          {/* Total Statistics Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2 bg-green-100 rounded-lg">
                <CurrencyDollarIcon className="h-6 w-6 text-green-600" />
              </div>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-600">Total Topped Up</p>
                <p className="text-lg font-semibold text-gray-900">
                  {balance && formatCurrency(balance.total_topped_up, balance.currency)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-600">Total Spent</p>
                <p className="text-lg font-semibold text-gray-900">
                  {balance && formatCurrency(balance.total_spent, balance.currency)}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Settings Section */}
        {showSettings && (
          <div className="mb-8">
            <BalanceSettings 
              balance={balance}
              onUpdate={fetchBalance}
            />
          </div>
        )}

        {/* Transaction History */}
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recent Transactions</h2>
          </div>
          <TransactionHistory 
            transactions={balance?.recent_transactions || []}
            currency={balance?.currency || 'USD'}
          />
        </div>

        {/* Auto Top-up Status */}
        {balance?.auto_topup_enabled && (
          <div className="mt-6 bg-blue-50 border-l-4 border-blue-400 p-4">
            <div className="flex">
              <CheckCircleIcon className="h-5 w-5 text-blue-400" />
              <div className="ml-3">
                <p className="text-sm text-blue-700">
                  <span className="font-medium">Auto Top-up Enabled</span> - 
                  {formatCurrency(balance.auto_topup_amount, balance.currency)} will be added when balance 
                  falls below {formatCurrency(balance.auto_topup_trigger_amount || balance.low_balance_threshold, balance.currency)}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Top-up Modal */}
      {showTopupModal && (
        <TopupModal
          onClose={() => setShowTopupModal(false)}
          onSuccess={handleTopupSuccess}
          currency={balance?.currency || 'USD'}
        />
      )}
    </div>
  );
}

export default Billing;