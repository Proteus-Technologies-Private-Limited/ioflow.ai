import React, { useState, useEffect } from 'react';
import {
  CurrencyDollarIcon,
  UserIcon,
  BoltIcon,
  GiftIcon
} from '@heroicons/react/24/outline';

const BillingConfigTab = ({ app, onSave, isSaving }) => {
  const [billingPreference, setBillingPreference] = useState('free');
  const [pricingConfig, setPricingConfig] = useState({
    per_user_config: {
      monthly_price: 10,
      currency: 'USD',
      trial_period_days: 0,
      minimum_users: 1
    },
    per_execution_config: {
      price_per_execution: 0.01,
      currency: 'USD',
      free_executions_per_month: 100,
      minimum_charge: 0
    }
  });
  const [usageLimits, setUsageLimits] = useState({
    max_executions_per_day: null,
    max_executions_per_month: null,
    max_users: null,
    quota_reset_period: 'monthly'
  });
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    if (app) {
      setBillingPreference(app.billing_preference || 'free');
      if (app.pricing_config) {
        setPricingConfig(app.pricing_config);
      }
      if (app.usage_limits) {
        setUsageLimits(app.usage_limits);
      }
    }
  }, [app]);

  const handleBillingPreferenceChange = (value) => {
    setBillingPreference(value);
    setHasChanges(true);
  };

  const handlePricingConfigChange = (path, value) => {
    setPricingConfig(prev => {
      const newConfig = { ...prev };
      const keys = path.split('.');
      let current = newConfig;
      for (let i = 0; i < keys.length - 1; i++) {
        current = current[keys[i]];
      }
      current[keys[keys.length - 1]] = value;
      return newConfig;
    });
    setHasChanges(true);
  };

  const handleUsageLimitChange = (field, value) => {
    setUsageLimits(prev => ({ ...prev, [field]: value }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    const billingConfig = {
      billing_preference: billingPreference,
      pricing_config: billingPreference !== 'free' ? {
        billing_preference: billingPreference,
        [billingPreference === 'per_user_per_month' ? 'per_user_config' : 'per_execution_config']:
          billingPreference === 'per_user_per_month'
            ? pricingConfig.per_user_config
            : pricingConfig.per_execution_config
      } : null,
      usage_limits: usageLimits
    };

    const success = await onSave(billingConfig);
    if (success) {
      setHasChanges(false);
    }
  };

  const getBillingOptions = () => [
    {
      value: 'free',
      label: 'Free to Use',
      description: 'No charges - your app is completely free',
      icon: GiftIcon,
      color: 'text-green-600'
    },
    {
      value: 'per_user_per_month',
      label: 'Per User / Month',
      description: 'Monthly subscription fee per user',
      icon: UserIcon,
      color: 'text-purple-600'
    },
    {
      value: 'per_execution',
      label: 'Per Execution',
      description: 'Pay per usage/execution',
      icon: BoltIcon,
      color: 'text-blue-600'
    }
  ];

  return (
    <div className="space-y-6">
      {/* Billing Model Selection */}
      <div>
        <h3 className="text-lg font-medium text-gray-900 mb-4">Billing Model</h3>
        <div className="space-y-3">
          {getBillingOptions().map((option) => {
            const Icon = option.icon;
            const isSelected = billingPreference === option.value;
            return (
              <div
                key={option.value}
                onClick={() => handleBillingPreferenceChange(option.value)}
                className={`
                  relative flex cursor-pointer rounded-lg border p-4 focus:outline-none
                  ${isSelected
                    ? 'border-primary bg-primary-10'
                    : 'border-gray-300 bg-white hover:bg-gray-50'
                  }
                `}
              >
                <div className="flex items-start">
                  <Icon className={`h-6 w-6 ${isSelected ? 'text-primary' : option.color}`} />
                  <div className="ml-3 flex-1">
                    <label className="block text-sm font-medium text-gray-900">
                      {option.label}
                    </label>
                    <p className="text-sm text-gray-500">{option.description}</p>
                  </div>
                  {isSelected && (
                    <div className="ml-3">
                      <div className="h-5 w-5 text-primary">
                        <svg viewBox="0 0 20 20" fill="currentColor">
                          <path
                            fillRule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Per User Per Month Configuration */}
      {billingPreference === 'per_user_per_month' && (
        <div className="border-t border-gray-200 pt-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Per User / Month Configuration</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Monthly Price
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="text-gray-500 sm:text-sm">$</span>
                  </div>
                  <input
                    type="number"
                    value={pricingConfig.per_user_config.monthly_price}
                    onChange={(e) => handlePricingConfigChange('per_user_config.monthly_price', parseFloat(e.target.value) || 0)}
                    min="0"
                    step="0.01"
                    className="w-full pl-7 pr-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Trial Period (days)
                </label>
                <input
                  type="number"
                  value={pricingConfig.per_user_config.trial_period_days}
                  onChange={(e) => handlePricingConfigChange('per_user_config.trial_period_days', parseInt(e.target.value) || 0)}
                  min="0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Minimum Users
              </label>
              <input
                type="number"
                value={pricingConfig.per_user_config.minimum_users}
                onChange={(e) => handlePricingConfigChange('per_user_config.minimum_users', parseInt(e.target.value) || 1)}
                min="1"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
              />
            </div>
          </div>
        </div>
      )}

      {/* Per Execution Configuration */}
      {billingPreference === 'per_execution' && (
        <div className="border-t border-gray-200 pt-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Per Execution Configuration</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Price per Execution
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="text-gray-500 sm:text-sm">$</span>
                  </div>
                  <input
                    type="number"
                    value={pricingConfig.per_execution_config.price_per_execution}
                    onChange={(e) => handlePricingConfigChange('per_execution_config.price_per_execution', parseFloat(e.target.value) || 0)}
                    min="0"
                    step="0.001"
                    className="w-full pl-7 pr-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Free Executions / Month
                </label>
                <input
                  type="number"
                  value={pricingConfig.per_execution_config.free_executions_per_month}
                  onChange={(e) => handlePricingConfigChange('per_execution_config.free_executions_per_month', parseInt(e.target.value) || 0)}
                  min="0"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Minimum Monthly Charge (optional)
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <span className="text-gray-500 sm:text-sm">$</span>
                </div>
                <input
                  type="number"
                  value={pricingConfig.per_execution_config.minimum_charge}
                  onChange={(e) => handlePricingConfigChange('per_execution_config.minimum_charge', parseFloat(e.target.value) || 0)}
                  min="0"
                  step="0.01"
                  className="w-full pl-7 pr-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Usage Limits */}
      <div className="border-t border-gray-200 pt-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Usage Limits</h3>
        <p className="text-sm text-gray-500 mb-4">Set execution limits and quotas (leave blank for unlimited)</p>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Executions / Day
              </label>
              <input
                type="number"
                value={usageLimits.max_executions_per_day || ''}
                onChange={(e) => handleUsageLimitChange('max_executions_per_day', e.target.value ? parseInt(e.target.value) : null)}
                min="1"
                placeholder="Unlimited"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Executions / Month
              </label>
              <input
                type="number"
                value={usageLimits.max_executions_per_month || ''}
                onChange={(e) => handleUsageLimitChange('max_executions_per_month', e.target.value ? parseInt(e.target.value) : null)}
                min="1"
                placeholder="Unlimited"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Users
            </label>
            <input
              type="number"
              value={usageLimits.max_users || ''}
              onChange={(e) => handleUsageLimitChange('max_users', e.target.value ? parseInt(e.target.value) : null)}
              min="1"
              placeholder="Unlimited"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-primary focus:border-primary"
            />
          </div>
        </div>
      </div>

      {/* Save Button */}
      {hasChanges && (
        <div className="border-t border-gray-200 pt-6">
          <div className="flex justify-end space-x-3">
            <button
              onClick={() => {
                setBillingPreference(app.billing_preference || 'free');
                if (app.pricing_config) setPricingConfig(app.pricing_config);
                if (app.usage_limits) setUsageLimits(app.usage_limits);
                setHasChanges(false);
              }}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="px-4 py-2 text-sm font-medium text-white bg-gradient-primary rounded-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSaving ? 'Saving...' : 'Save Billing Configuration'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default BillingConfigTab;
