import React, { useState, useEffect } from 'react';
import { toast } from 'react-hot-toast';
import axios from 'axios';
import {
  CreditCardIcon,
  BellIcon,
  DocumentTextIcon,
  CurrencyDollarIcon,
  CogIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import { useAuth } from '../../contexts/AuthContext';

const SubscriptionPreferences = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState(null);
  const [spendingStatus, setSpendingStatus] = useState(null);

  // Check if user is tenant admin
  const canEdit = user?.role === 'TENANT_ADMIN' || user?.role === 'INSTANCE_ADMIN';

  useEffect(() => {
    if (!canEdit) {
      setLoading(false);
      return;
    }
    fetchPreferences();
    fetchSpendingStatus();
  }, [canEdit]);

  const fetchPreferences = async () => {
    try {
      const response = await axios.get('/api/v1/subscription-preferences');
      setPreferences(response.data);
    } catch (error) {
      toast.error('Failed to load subscription preferences');
      console.error('Error fetching preferences:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSpendingStatus = async () => {
    try {
      const response = await axios.get('/api/v1/subscription-preferences/spending-status');
      setSpendingStatus(response.data);
    } catch (error) {
      console.error('Error fetching spending status:', error);
    }
  };

  const handleSave = async () => {
    if (!canEdit) {
      toast.error('Only tenant admins can update subscription preferences');
      return;
    }

    setSaving(true);
    try {
      const response = await axios.put('/api/v1/subscription-preferences', preferences);
      setPreferences(response.data);
      toast.success('Subscription preferences updated successfully');
      fetchSpendingStatus(); // Refresh spending status
    } catch (error) {
      toast.error('Failed to update subscription preferences');
      console.error('Error updating preferences:', error);
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setPreferences(prev => ({
      ...prev,
      [field]: value
    }));
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!canEdit) {
    return (
      <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
          </div>
          <div className="ml-3">
            <p className="text-sm text-yellow-700">
              Only tenant administrators can view or modify subscription preferences.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (!preferences) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500">Unable to load subscription preferences</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Spending Status Card */}
      {spendingStatus && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
            <CurrencyDollarIcon className="h-5 w-5 mr-2" />
            Current Spending Status
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-500">Daily Spending</p>
              <div className="flex items-baseline">
                <p className="text-2xl font-semibold text-gray-900">
                  ${spendingStatus.daily_spent?.toFixed(2) || '0.00'}
                </p>
                {spendingStatus.daily_limit && (
                  <span className="ml-2 text-sm text-gray-500">
                    / ${spendingStatus.daily_limit.toFixed(2)}
                  </span>
                )}
              </div>
              {spendingStatus.daily_percentage && (
                <div className="mt-1 w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      spendingStatus.daily_percentage > 80 ? 'bg-red-500' :
                      spendingStatus.daily_percentage > 60 ? 'bg-yellow-500' :
                      'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(spendingStatus.daily_percentage, 100)}%` }}
                  ></div>
                </div>
              )}
            </div>
            <div>
              <p className="text-sm text-gray-500">Monthly Spending</p>
              <div className="flex items-baseline">
                <p className="text-2xl font-semibold text-gray-900">
                  ${spendingStatus.monthly_spent?.toFixed(2) || '0.00'}
                </p>
                {spendingStatus.monthly_limit && (
                  <span className="ml-2 text-sm text-gray-500">
                    / ${spendingStatus.monthly_limit.toFixed(2)}
                  </span>
                )}
              </div>
              {spendingStatus.monthly_percentage && (
                <div className="mt-1 w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${
                      spendingStatus.monthly_percentage > 80 ? 'bg-red-500' :
                      spendingStatus.monthly_percentage > 60 ? 'bg-yellow-500' :
                      'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(spendingStatus.monthly_percentage, 100)}%` }}
                  ></div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Billing Preferences */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <CreditCardIcon className="h-5 w-5 mr-2" />
          Billing Preferences
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Billing Type
            </label>
            <select
              value={preferences.billing_preference || 'prepaid'}
              onChange={(e) => handleChange('billing_preference', e.target.value)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
            >
              <option value="prepaid">Prepaid (Pay in advance)</option>
              <option value="postpaid">Postpaid (Monthly invoice)</option>
              <option value="hybrid">Hybrid (Prepaid with postpaid overages)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Default Payment Method
            </label>
            <select
              value={preferences.default_payment_method || 'razorpay'}
              onChange={(e) => handleChange('default_payment_method', e.target.value)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
            >
              <option value="razorpay">Razorpay</option>
              <option value="credit_card">Credit Card</option>
              <option value="debit_card">Debit Card</option>
              <option value="net_banking">Net Banking</option>
              <option value="upi">UPI</option>
              <option value="bank_transfer">Bank Transfer</option>
            </select>
          </div>

          <div className="space-y-2">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="auto_renewal"
                checked={preferences.auto_renewal_enabled || false}
                onChange={(e) => handleChange('auto_renewal_enabled', e.target.checked)}
                disabled={!canEdit}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:bg-gray-100"
              />
              <label htmlFor="auto_renewal" className="ml-2 block text-sm text-gray-900">
                Enable Auto-Renewal for Subscriptions
              </label>
            </div>

            <div className="flex items-center">
              <input
                type="checkbox"
                id="auto_topup"
                checked={preferences.auto_topup_enabled || false}
                onChange={(e) => handleChange('auto_topup_enabled', e.target.checked)}
                disabled={!canEdit}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:bg-gray-100"
              />
              <label htmlFor="auto_topup" className="ml-2 block text-sm text-gray-900">
                Enable Auto Top-up
              </label>
            </div>
          </div>

          {preferences.auto_topup_enabled && (
            <div className="ml-6 space-y-3 border-l-2 border-gray-200 pl-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Auto Top-up Amount ($)
                </label>
                <input
                  type="number"
                  value={preferences.auto_topup_amount || ''}
                  onChange={(e) => handleChange('auto_topup_amount', parseFloat(e.target.value))}
                  disabled={!canEdit}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
                  placeholder="100.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Trigger When Balance Falls Below ($)
                </label>
                <input
                  type="number"
                  value={preferences.auto_topup_trigger_amount || ''}
                  onChange={(e) => handleChange('auto_topup_trigger_amount', parseFloat(e.target.value))}
                  disabled={!canEdit}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
                  placeholder="20.00"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Spending Limits */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
          Spending Limits
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Daily Limit ($)
            </label>
            <input
              type="number"
              value={preferences.daily_spending_limit || ''}
              onChange={(e) => handleChange('daily_spending_limit', e.target.value ? parseFloat(e.target.value) : null)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
              placeholder="No limit"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Monthly Limit ($)
            </label>
            <input
              type="number"
              value={preferences.monthly_spending_limit || ''}
              onChange={(e) => handleChange('monthly_spending_limit', e.target.value ? parseFloat(e.target.value) : null)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
              placeholder="No limit"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Per Execution Limit ($)
            </label>
            <input
              type="number"
              value={preferences.per_execution_limit || ''}
              onChange={(e) => handleChange('per_execution_limit', e.target.value ? parseFloat(e.target.value) : null)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
              placeholder="No limit"
            />
          </div>
        </div>
      </div>

      {/* Invoice Preferences */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <DocumentTextIcon className="h-5 w-5 mr-2" />
          Invoice Preferences
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Invoice Frequency
            </label>
            <select
              value={preferences.invoice_frequency || 'monthly'}
              onChange={(e) => handleChange('invoice_frequency', e.target.value)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
            >
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Invoice Email (optional)
            </label>
            <input
              type="email"
              value={preferences.invoice_email || ''}
              onChange={(e) => handleChange('invoice_email', e.target.value)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
              placeholder="Leave empty to use account email"
            />
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="detailed_invoice"
              checked={preferences.send_detailed_invoice || false}
              onChange={(e) => handleChange('send_detailed_invoice', e.target.checked)}
              disabled={!canEdit}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:bg-gray-100"
            />
            <label htmlFor="detailed_invoice" className="ml-2 block text-sm text-gray-900">
              Include detailed usage breakdown in invoices
            </label>
          </div>
        </div>
      </div>

      {/* Notification Preferences */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <BellIcon className="h-5 w-5 mr-2" />
          Notification Preferences
        </h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Notification Method
            </label>
            <select
              value={preferences.notification_preference || 'email'}
              onChange={(e) => handleChange('notification_preference', e.target.value)}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
            >
              <option value="email">Email</option>
              <option value="sms">SMS</option>
              <option value="both">Both Email and SMS</option>
              <option value="none">None</option>
            </select>
          </div>
          <div className="space-y-2">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="low_balance_alert"
                checked={preferences.low_balance_alert_enabled || false}
                onChange={(e) => handleChange('low_balance_alert_enabled', e.target.checked)}
                disabled={!canEdit}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:bg-gray-100"
              />
              <label htmlFor="low_balance_alert" className="ml-2 block text-sm text-gray-900">
                Enable low balance alerts
              </label>
            </div>
            <div className="flex items-center">
              <input
                type="checkbox"
                id="usage_alert"
                checked={preferences.usage_alert_enabled || false}
                onChange={(e) => handleChange('usage_alert_enabled', e.target.checked)}
                disabled={!canEdit}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:bg-gray-100"
              />
              <label htmlFor="usage_alert" className="ml-2 block text-sm text-gray-900">
                Enable usage alerts
              </label>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Alert Threshold (%)
            </label>
            <input
              type="number"
              min="1"
              max="100"
              value={preferences.alert_threshold_percentage || 20}
              onChange={(e) => handleChange('alert_threshold_percentage', parseInt(e.target.value))}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
            />
            <p className="mt-1 text-sm text-gray-500">
              Alert when balance or limit reaches this percentage
            </p>
          </div>
        </div>
      </div>

      {/* Cost Optimization */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
          <CogIcon className="h-5 w-5 mr-2" />
          Cost Optimization
        </h3>
        <div className="space-y-4">
          <div className="flex items-center">
            <input
              type="checkbox"
              id="cached_results"
              checked={preferences.prefer_cached_results || false}
              onChange={(e) => handleChange('prefer_cached_results', e.target.checked)}
              disabled={!canEdit}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:bg-gray-100"
            />
            <label htmlFor="cached_results" className="ml-2 block text-sm text-gray-900">
              Prefer cached results when available
            </label>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="cost_optimization"
              checked={preferences.enable_cost_optimization || false}
              onChange={(e) => handleChange('enable_cost_optimization', e.target.checked)}
              disabled={!canEdit}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded disabled:bg-gray-100"
            />
            <label htmlFor="cost_optimization" className="ml-2 block text-sm text-gray-900">
              Enable cost optimization suggestions
            </label>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Maximum Retries on Failure
            </label>
            <input
              type="number"
              min="0"
              max="10"
              value={preferences.max_retry_on_failure || 3}
              onChange={(e) => handleChange('max_retry_on_failure', parseInt(e.target.value))}
              disabled={!canEdit}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:bg-gray-100"
            />
          </div>
        </div>
      </div>

      {/* Save Button */}
      {canEdit && (
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Preferences'}
          </button>
        </div>
      )}

      {!canEdit && (
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
            </div>
            <div className="ml-3">
              <p className="text-sm text-yellow-700">
                Only tenant administrators can modify subscription preferences.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SubscriptionPreferences;