import React, { useState, useEffect } from 'react';
import { CogIcon, CheckIcon, XMarkIcon } from '@heroicons/react/24/outline';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

function BalanceSettings({ balance, onUpdate }) {
  const [settings, setSettings] = useState({
    low_balance_threshold: '',
    critical_balance_threshold: '',
    auto_topup_enabled: false,
    auto_topup_amount: '',
    auto_topup_trigger_amount: '',
    daily_spending_limit: '',
    monthly_spending_limit: ''
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (balance) {
      setSettings({
        low_balance_threshold: balance.low_balance_threshold || '',
        critical_balance_threshold: balance.critical_balance_threshold || '',
        auto_topup_enabled: balance.auto_topup_enabled || false,
        auto_topup_amount: balance.auto_topup_amount || '',
        auto_topup_trigger_amount: balance.auto_topup_trigger_amount || '',
        daily_spending_limit: balance.daily_spending_limit || '',
        monthly_spending_limit: balance.monthly_spending_limit || ''
      });
    }
  }, [balance]);

  const handleChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
    setError(null);
    setSuccess(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);

    // Prepare data - only send non-empty values
    const updateData = {};
    
    if (settings.low_balance_threshold !== '') {
      updateData.low_balance_threshold = parseFloat(settings.low_balance_threshold);
    }
    if (settings.critical_balance_threshold !== '') {
      updateData.critical_balance_threshold = parseFloat(settings.critical_balance_threshold);
    }
    updateData.auto_topup_enabled = settings.auto_topup_enabled;
    if (settings.auto_topup_amount !== '') {
      updateData.auto_topup_amount = parseFloat(settings.auto_topup_amount);
    }
    if (settings.auto_topup_trigger_amount !== '') {
      updateData.auto_topup_trigger_amount = parseFloat(settings.auto_topup_trigger_amount);
    }
    if (settings.daily_spending_limit !== '') {
      updateData.daily_spending_limit = parseFloat(settings.daily_spending_limit);
    }
    if (settings.monthly_spending_limit !== '') {
      updateData.monthly_spending_limit = parseFloat(settings.monthly_spending_limit);
    }

    try {
      await axios.put(
        `${API_BASE_URL}/api/v1/tenant/balance/settings`,
        updateData,
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }
      );
      setSuccess(true);
      onUpdate();
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      console.error('Error updating settings:', err);
      setError(err.response?.data?.detail || 'Failed to update settings');
    } finally {
      setSaving(false);
    }
  };

  const formatCurrency = (value) => {
    if (!value) return '';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: balance?.currency || 'USD'
    }).format(value);
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center">
          <CogIcon className="h-5 w-5 text-gray-500 mr-2" />
          <h3 className="text-lg font-semibold text-gray-900">Balance Settings</h3>
        </div>
      </div>

      <div className="px-6 py-4">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-sm text-red-600">{error}</p>
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md flex items-center">
            <CheckIcon className="h-5 w-5 text-green-600 mr-2" />
            <p className="text-sm text-green-600">Settings updated successfully!</p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Alert Thresholds */}
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-4">Alert Thresholds</h4>
            
            <div className="mb-4">
              <label className="block text-sm text-gray-700 mb-1">
                Low Balance Alert
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                  $
                </span>
                <input
                  type="number"
                  value={settings.low_balance_threshold}
                  onChange={(e) => handleChange('low_balance_threshold', e.target.value)}
                  placeholder="10.00"
                  className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Get notified when balance falls below this amount
              </p>
            </div>

            <div className="mb-4">
              <label className="block text-sm text-gray-700 mb-1">
                Critical Balance Alert
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                  $
                </span>
                <input
                  type="number"
                  value={settings.critical_balance_threshold}
                  onChange={(e) => handleChange('critical_balance_threshold', e.target.value)}
                  placeholder="5.00"
                  className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Urgent alert when balance is critically low
              </p>
            </div>
          </div>

          {/* Auto Top-up */}
          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-4">Auto Top-up</h4>
            
            <div className="mb-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.auto_topup_enabled}
                  onChange={(e) => handleChange('auto_topup_enabled', e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Enable Auto Top-up</span>
              </label>
            </div>

            {settings.auto_topup_enabled && (
              <>
                <div className="mb-4">
                  <label className="block text-sm text-gray-700 mb-1">
                    Top-up Amount
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                      $
                    </span>
                    <input
                      type="number"
                      value={settings.auto_topup_amount}
                      onChange={(e) => handleChange('auto_topup_amount', e.target.value)}
                      placeholder="50.00"
                      className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Amount to add when triggered
                  </p>
                </div>

                <div className="mb-4">
                  <label className="block text-sm text-gray-700 mb-1">
                    Trigger When Balance Below
                  </label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                      $
                    </span>
                    <input
                      type="number"
                      value={settings.auto_topup_trigger_amount}
                      onChange={(e) => handleChange('auto_topup_trigger_amount', e.target.value)}
                      placeholder="10.00"
                      className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                  <p className="mt-1 text-xs text-gray-500">
                    Auto top-up triggers at this balance
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Spending Limits */}
          <div className="md:col-span-2">
            <h4 className="text-sm font-medium text-gray-900 mb-4">Spending Limits</h4>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-700 mb-1">
                  Daily Spending Limit
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                    $
                  </span>
                  <input
                    type="number"
                    value={settings.daily_spending_limit}
                    onChange={(e) => handleChange('daily_spending_limit', e.target.value)}
                    placeholder="No limit"
                    className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Maximum daily spending allowed
                </p>
              </div>

              <div>
                <label className="block text-sm text-gray-700 mb-1">
                  Monthly Spending Limit
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                    $
                  </span>
                  <input
                    type="number"
                    value={settings.monthly_spending_limit}
                    onChange={(e) => handleChange('monthly_spending_limit', e.target.value)}
                    placeholder="No limit"
                    className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Maximum monthly spending allowed
                </p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default BalanceSettings;