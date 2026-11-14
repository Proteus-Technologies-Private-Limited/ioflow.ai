import React, { useState, useEffect } from 'react';
import {
  CurrencyDollarIcon,
  CheckCircleIcon,
  XMarkIcon,
  InformationCircleIcon,
  CogIcon
} from '@heroicons/react/24/outline';
import axios from 'axios';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

const PricingConfiguration = ({ application, onClose, onUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [pricing, setPricing] = useState({
    billing_mode: 'prepaid',  // Use lowercase to match backend enum
    is_free: false,
    pricing_model: 'pay_per_use',
    usage_metric_type: 'per_request',  // Required for pay_per_use
    incoming_event_cost: 0.01,
    outgoing_service_cost: 0.02,
    cost_per_kb: 0.001,
    cost_per_token: 0.00001,
    base_subscription_cost: 0,
    billing_cycle: 'monthly',
    currency: 'USD',
    service_pricing_enabled: false
  });

  const [existingPricing, setExistingPricing] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (application && application.app_id) {
      fetchExistingPricing();
    }
  }, [application?.app_id]);

  const fetchExistingPricing = async () => {
    if (!application || !application.app_id) {
      console.error('No application provided to PricingConfiguration');
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/applications/${application.app_id}/pricing`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      if (response.data && response.data.pricing_plans && response.data.pricing_plans.length > 0) {
        const activePricing = response.data.pricing_plans.find(p => p.is_active);
        if (activePricing) {
          setExistingPricing(activePricing);
          setPricing({
            ...activePricing,
            billing_mode: activePricing.billing_mode || 'prepaid',
            is_free: activePricing.is_free || false,
            service_pricing_enabled: activePricing.service_pricing_enabled || false
          });
        }
      }
    } catch (error) {
      console.log('No existing pricing found');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!application || !application.app_id) {
      showErrorToast('Application information is missing');
      return;
    }

    setLoading(true);

    try {
      const token = localStorage.getItem('access_token');

      // Prepare pricing data
      const pricingData = {
        pricing_model: pricing.pricing_model,
        usage_metric_type: pricing.pricing_model === 'pay_per_use' ? (pricing.usage_metric_type || 'per_request') : null,
        billing_cycle: pricing.billing_mode === 'subscription' ? pricing.billing_cycle : null,
        incoming_event_cost: parseFloat(pricing.incoming_event_cost) || 0,
        outgoing_service_cost: parseFloat(pricing.outgoing_service_cost) || 0,
        cost_per_kb: parseFloat(pricing.cost_per_kb) || 0,
        cost_per_token: parseFloat(pricing.cost_per_token) || 0,
        base_subscription_cost: pricing.billing_mode === 'subscription'
          ? parseFloat(pricing.base_subscription_cost) || 0
          : null,
        currency: pricing.currency || 'USD'
      };

      // Add billing mode and is_free as separate fields for the enhanced billing system
      const enhancedPricingData = {
        ...pricingData,
        billing_mode: pricing.billing_mode,
        is_free: pricing.is_free,
        service_pricing_enabled: pricing.service_pricing_enabled
      };

      const endpoint = existingPricing
        ? `${API_BASE_URL}/api/v1/applications/${application.app_id}/pricing/${existingPricing.pricing_id}`
        : `${API_BASE_URL}/api/v1/applications/${application.app_id}/pricing`;

      const method = existingPricing ? 'PUT' : 'POST';

      const response = await axios({
        method,
        url: endpoint,
        data: enhancedPricingData,
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      showSuccessToast('Pricing configuration saved successfully');
      if (onUpdate) onUpdate();
      if (onClose) onClose();
    } catch (error) {
      console.error('Error saving pricing:', error.response?.data);
      // Handle validation errors from FastAPI/Pydantic
      let errorMessage = 'Failed to save pricing configuration';
      if ((error.response?.data?.message || error.response?.data?.detail)) {
        // Check if detail is an array of validation errors
        if (Array.isArray(error.response.data.detail)) {
          errorMessage = error.response.data.detail.map(err => err.msg || err.message).join(', ');
        } else if (typeof error.response.data.detail === 'string') {
          errorMessage = error.response.data.detail;
        } else if (error.response.data.detail.msg) {
          errorMessage = error.response.data.detail.msg;
        }
      }
      showErrorToast(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const calculateSampleCost = () => {
    if (pricing.is_free) return 0;

    const incoming = parseFloat(pricing.incoming_event_cost) || 0;
    const outgoing = parseFloat(pricing.outgoing_service_cost) || 0;
    const perKb = parseFloat(pricing.cost_per_kb) || 0;
    const perToken = parseFloat(pricing.cost_per_token) || 0;

    // Sample: 100 requests with 10KB each and 1000 tokens
    const sampleCost = (100 * incoming) + (100 * outgoing) + (1000 * perKb) + (100000 * perToken);
    return sampleCost.toFixed(2);
  };

  const billingModeOptions = [
    { value: 'free', label: 'Free', description: 'No charges, usage tracked' },
    { value: 'prepaid', label: 'Prepaid', description: 'Requires balance before execution' },
    { value: 'postpaid', label: 'Postpaid', description: 'Invoice at end of period' },
    { value: 'subscription', label: 'Subscription', description: 'Fixed monthly/yearly fee' }
  ];

  // Early return if no application is provided
  if (!application || !application.app_id) {
    return (
      <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
        <div className="bg-white rounded-lg shadow-xl p-6">
          <p className="text-red-600">Error: No application provided for pricing configuration.</p>
          <button
            onClick={onClose}
            className="mt-4 px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <CurrencyDollarIcon className="h-6 w-6 text-green-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">
                Pricing Configuration - {application.app_name || 'Unknown Application'}
              </h2>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 space-y-6">
            {/* Billing Mode Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Billing Mode
              </label>
              <div className="grid grid-cols-2 gap-3">
                {billingModeOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setPricing({
                      ...pricing,
                      billing_mode: option.value,
                      is_free: option.value === 'free'
                    })}
                    className={`relative rounded-lg border p-4 text-left transition-colors ${
                      pricing.billing_mode === option.value
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-900">{option.label}</p>
                        <p className="text-sm text-gray-500 mt-1">{option.description}</p>
                      </div>
                      {pricing.billing_mode === option.value && (
                        <CheckCircleIcon className="h-5 w-5 text-blue-500" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Free Application Notice */}
            {pricing.is_free && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex">
                  <CheckCircleIcon className="h-5 w-5 text-green-400 mr-2" />
                  <div>
                    <h4 className="text-sm font-medium text-green-800">Free Application</h4>
                    <p className="text-sm text-green-700 mt-1">
                      This application will be free to use. Usage will still be tracked for analytics.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Subscription Settings */}
            {pricing.billing_mode === 'subscription' && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Subscription Cost
                  </label>
                  <div className="mt-1 relative rounded-md shadow-sm">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <span className="text-gray-500 sm:text-sm">$</span>
                    </div>
                    <input
                      type="number"
                      step="0.01"
                      value={pricing.base_subscription_cost}
                      onChange={(e) => setPricing({ ...pricing, base_subscription_cost: e.target.value })}
                      className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md"
                      placeholder="0.00"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Billing Cycle
                  </label>
                  <select
                    value={pricing.billing_cycle}
                    onChange={(e) => setPricing({ ...pricing, billing_cycle: e.target.value })}
                    className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="yearly">Yearly</option>
                  </select>
                </div>
              </div>
            )}

            {/* Usage-Based Pricing */}
            {!pricing.is_free && pricing.billing_mode !== 'subscription' && (
              <>
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-3">Usage-Based Costs</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Cost per Incoming Event
                      </label>
                      <div className="mt-1 relative rounded-md shadow-sm">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <span className="text-gray-500 sm:text-sm">$</span>
                        </div>
                        <input
                          type="number"
                          step="0.00001"
                          value={pricing.incoming_event_cost}
                          onChange={(e) => setPricing({ ...pricing, incoming_event_cost: e.target.value })}
                          className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md"
                          placeholder="0.00"
                        />
                      </div>
                      <p className="mt-1 text-xs text-gray-500">Per webhook/API trigger</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Cost per Service Call
                      </label>
                      <div className="mt-1 relative rounded-md shadow-sm">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <span className="text-gray-500 sm:text-sm">$</span>
                        </div>
                        <input
                          type="number"
                          step="0.00001"
                          value={pricing.outgoing_service_cost}
                          onChange={(e) => setPricing({ ...pricing, outgoing_service_cost: e.target.value })}
                          className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md"
                          placeholder="0.00"
                        />
                      </div>
                      <p className="mt-1 text-xs text-gray-500">Per service execution</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Cost per KB Data Transfer
                      </label>
                      <div className="mt-1 relative rounded-md shadow-sm">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <span className="text-gray-500 sm:text-sm">$</span>
                        </div>
                        <input
                          type="number"
                          step="0.00001"
                          value={pricing.cost_per_kb}
                          onChange={(e) => setPricing({ ...pricing, cost_per_kb: e.target.value })}
                          className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md"
                          placeholder="0.00"
                        />
                      </div>
                      <p className="mt-1 text-xs text-gray-500">Per kilobyte transferred</p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Cost per Token (LLM)
                      </label>
                      <div className="mt-1 relative rounded-md shadow-sm">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                          <span className="text-gray-500 sm:text-sm">$</span>
                        </div>
                        <input
                          type="number"
                          step="0.00001"
                          value={pricing.cost_per_token}
                          onChange={(e) => setPricing({ ...pricing, cost_per_token: e.target.value })}
                          className="focus:ring-blue-500 focus:border-blue-500 block w-full pl-7 pr-12 sm:text-sm border-gray-300 rounded-md"
                          placeholder="0.00"
                        />
                      </div>
                      <p className="mt-1 text-xs text-gray-500">Per token for LLM usage</p>
                    </div>
                  </div>
                </div>

                {/* Cost Preview */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <InformationCircleIcon className="h-5 w-5 text-blue-400 mr-2 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="text-sm font-medium text-blue-900">Cost Preview</h4>
                      <p className="text-sm text-blue-700 mt-1">
                        Sample cost for 100 requests (10KB each, 1000 tokens per request):
                        <span className="font-semibold ml-2">${calculateSampleCost()}</span>
                      </p>
                      <div className="mt-2 text-xs text-blue-600">
                        <div>• 100 incoming events: ${(100 * parseFloat(pricing.incoming_event_cost || 0)).toFixed(4)}</div>
                        <div>• 100 service calls: ${(100 * parseFloat(pricing.outgoing_service_cost || 0)).toFixed(4)}</div>
                        <div>• 1MB data transfer: ${(1000 * parseFloat(pricing.cost_per_kb || 0)).toFixed(4)}</div>
                        <div>• 100k tokens: ${(100000 * parseFloat(pricing.cost_per_token || 0)).toFixed(4)}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* Advanced Settings */}
            <div>
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                <CogIcon className="h-4 w-4 mr-1" />
                Advanced Settings
                <span className="ml-2">{showAdvanced ? '▼' : '▶'}</span>
              </button>

              {showAdvanced && (
                <div className="mt-3 space-y-3 pl-5">
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="service-pricing"
                      checked={pricing.service_pricing_enabled}
                      onChange={(e) => setPricing({ ...pricing, service_pricing_enabled: e.target.checked })}
                      className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                    />
                    <label htmlFor="service-pricing" className="ml-2 block text-sm text-gray-700">
                      Enable service-specific pricing overrides
                    </label>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">
                      Currency
                    </label>
                    <select
                      value={pricing.currency}
                      onChange={(e) => setPricing({ ...pricing, currency: e.target.value })}
                      className="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                    >
                      <option value="USD">USD - US Dollar</option>
                      <option value="EUR">EUR - Euro</option>
                      <option value="GBP">GBP - British Pound</option>
                      <option value="INR">INR - Indian Rupee</option>
                    </select>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              {loading ? 'Saving...' : existingPricing ? 'Update Pricing' : 'Create Pricing'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PricingConfiguration;