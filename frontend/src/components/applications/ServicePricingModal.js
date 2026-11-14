import React, { useState, useEffect } from 'react';
import { XMarkIcon, CurrencyDollarIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

function ServicePricingModal({ service, applicationPricing, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [pricingData, setPricingData] = useState({
    cost_per_request: 0,
    cost_per_kb: 0,
    cost_per_token: 0,
    is_free: false,
    override_app_pricing: true,
    currency: 'USD'
  });

  // Load existing service pricing if available
  useEffect(() => {
    fetchServicePricing();
  }, [service]);

  const fetchServicePricing = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/applications/services/${service.service_id}/pricing`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      if (response.data) {
        setPricingData({
          ...pricingData,
          ...response.data
        });
      }
    } catch (error) {
      // Service pricing might not exist yet, use defaults
      console.log('No existing service pricing found, using defaults');
    }
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');

      // Validate input
      if (!pricingData.is_free) {
        if (pricingData.cost_per_request < 0) {
          showErrorToast('Cost per request cannot be negative');
          return;
        }
      }

      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/services/${service.service_id}/pricing`,
        pricingData,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      showSuccessToast('Service pricing configured successfully');
      if (onSuccess) onSuccess(response.data);
    } catch (error) {
      showErrorToast('Failed to configure service pricing: ' + ((error.response?.data?.message || error.response?.data?.detail) || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!window.confirm('Are you sure you want to remove service-specific pricing? The service will use application-level pricing.')) {
      return;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem('access_token');

      await axios.delete(
        `${API_BASE_URL}/api/v1/applications/services/${service.service_id}/pricing`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      showSuccessToast('Service pricing removed successfully');
      onClose();
    } catch (error) {
      showErrorToast('Failed to remove service pricing: ' + ((error.response?.data?.message || error.response?.data?.detail) || error.message));
    } finally {
      setLoading(false);
    }
  };

  // Calculate estimated cost
  const calculateEstimatedCost = () => {
    if (pricingData.is_free) return 0;

    let cost = parseFloat(pricingData.cost_per_request) || 0;

    // Add sample data transfer cost (10 KB)
    if (pricingData.cost_per_kb) {
      cost += (parseFloat(pricingData.cost_per_kb) || 0) * 10;
    }

    // Add sample token cost (100 tokens)
    if (pricingData.cost_per_token) {
      cost += (parseFloat(pricingData.cost_per_token) || 0) * 100;
    }

    return cost.toFixed(4);
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <CurrencyDollarIcon className="h-6 w-6 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">
              Service Pricing Configuration
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4">
          {/* Service Info */}
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <h3 className="text-sm font-medium text-gray-700">Service Details</h3>
            <p className="mt-1 text-sm text-gray-900">{service.display_name || service.service_name}</p>
            <p className="text-xs text-gray-500 mt-1">Service ID: {service.service_id}</p>
            {service.description && (
              <p className="text-sm text-gray-600 mt-2">{service.description}</p>
            )}
          </div>

          {/* Application Pricing Info */}
          {applicationPricing && (
            <div className="mb-6 p-4 bg-blue-50 rounded-lg">
              <div className="flex items-start">
                <ExclamationTriangleIcon className="h-5 w-5 text-blue-400 mt-0.5" />
                <div className="ml-3">
                  <h3 className="text-sm font-medium text-blue-800">Current Application Pricing</h3>
                  <div className="mt-2 text-sm text-blue-700">
                    {applicationPricing.is_free ? (
                      <p>This application is configured as FREE</p>
                    ) : (
                      <>
                        <p>• Per Request: ${applicationPricing.outgoing_service_cost || 0}</p>
                        {applicationPricing.cost_per_kb && <p>• Per KB: ${applicationPricing.cost_per_kb}</p>}
                        {applicationPricing.cost_per_token && <p>• Per Token: ${applicationPricing.cost_per_token}</p>}
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Pricing Configuration */}
          <div className="space-y-6">
            {/* Override Toggle */}
            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={pricingData.override_app_pricing}
                  onChange={(e) => setPricingData({ ...pricingData, override_app_pricing: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">
                  Override application-level pricing for this service
                </span>
              </label>
            </div>

            {/* Free Service Toggle */}
            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={pricingData.is_free}
                  onChange={(e) => setPricingData({ ...pricingData, is_free: e.target.checked })}
                  className="rounded border-gray-300 text-green-600 focus:ring-green-500"
                />
                <span className="ml-2 text-sm text-gray-700">
                  This is a free service (no charges)
                </span>
              </label>
            </div>

            {/* Pricing Fields */}
            {!pricingData.is_free && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cost Per Request ($)
                  </label>
                  <input
                    type="number"
                    value={pricingData.cost_per_request}
                    onChange={(e) => setPricingData({ ...pricingData, cost_per_request: parseFloat(e.target.value) || 0 })}
                    step="0.001"
                    min="0"
                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Base cost per API call</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cost Per KB ($)
                  </label>
                  <input
                    type="number"
                    value={pricingData.cost_per_kb}
                    onChange={(e) => setPricingData({ ...pricingData, cost_per_kb: parseFloat(e.target.value) || 0 })}
                    step="0.0001"
                    min="0"
                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">Data transfer cost</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cost Per Token ($)
                  </label>
                  <input
                    type="number"
                    value={pricingData.cost_per_token}
                    onChange={(e) => setPricingData({ ...pricingData, cost_per_token: parseFloat(e.target.value) || 0 })}
                    step="0.00001"
                    min="0"
                    className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500 mt-1">LLM token cost</p>
                </div>
              </div>
            )}

            {/* Cost Preview */}
            {!pricingData.is_free && (
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h4 className="text-sm font-medium text-gray-700">Estimated Cost Per Call</h4>
                <div className="mt-2 text-sm text-gray-600">
                  <p>Sample calculation (1 request + 10KB data + 100 tokens):</p>
                  <p className="text-lg font-semibold text-gray-900 mt-1">
                    ${calculateEstimatedCost()}
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
          <div>
            {pricingData.override_app_pricing && (
              <button
                onClick={handleDelete}
                disabled={loading}
                className="px-4 py-2 text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
              >
                Remove Service Pricing
              </button>
            )}
          </div>
          <div className="flex space-x-3">
            <button
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Save Pricing'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ServicePricingModal;