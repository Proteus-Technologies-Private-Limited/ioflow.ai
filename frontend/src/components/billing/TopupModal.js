import React, { useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

function TopupModal({ onClose, onSuccess, currency = 'USD' }) {
  const [amount, setAmount] = useState('');
  const [customAmount, setCustomAmount] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const presetAmounts = [10, 25, 50, 100, 250, 500];

  const handlePresetClick = (value) => {
    setAmount(value.toString());
    setCustomAmount(false);
    setError(null);
  };

  const handleCustomAmountChange = (e) => {
    const value = e.target.value;
    // Allow only numbers and decimal point
    if (/^\d*\.?\d*$/.test(value)) {
      setAmount(value);
      setError(null);
    }
  };

  const handleTopup = async () => {
    const topupAmount = parseFloat(amount);
    
    if (!topupAmount || topupAmount <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    if (topupAmount < 1) {
      setError('Minimum top-up amount is 1.00');
      return;
    }

    if (topupAmount > 10000) {
      setError('Maximum top-up amount is 10,000.00');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/tenant/balance/topup`,
        {
          amount: topupAmount,
          payment_method: 'manual' // For testing, use 'razorpay' for production
        },
        {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('access_token')}`
          }
        }
      );

      if (response.data.success) {
        onSuccess();
      } else {
        setError(response.data.error || 'Failed to process top-up');
      }
    } catch (err) {
      console.error('Error processing top-up:', err);
      setError(err.response?.data?.detail || 'Failed to process top-up');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(value);
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Top Up Balance</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {/* Preset Amounts */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              Select Amount
            </label>
            <div className="grid grid-cols-3 gap-3">
              {presetAmounts.map((value) => (
                <button
                  key={value}
                  onClick={() => handlePresetClick(value)}
                  className={`px-4 py-3 rounded-lg border text-sm font-medium transition ${
                    amount === value.toString() && !customAmount
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  {formatCurrency(value)}
                </button>
              ))}
            </div>
          </div>

          {/* Custom Amount */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Or Enter Custom Amount
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500">
                {currency === 'USD' ? '$' : currency}
              </span>
              <input
                type="text"
                value={amount}
                onChange={handleCustomAmountChange}
                onFocus={() => setCustomAmount(true)}
                placeholder="0.00"
                className="w-full pl-8 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <p className="mt-1 text-xs text-gray-500">
              Min: {formatCurrency(1)} | Max: {formatCurrency(10000)}
            </p>
          </div>

          {/* Summary */}
          {amount && parseFloat(amount) > 0 && (
            <div className="mb-6 p-4 bg-gray-50 rounded-lg">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Top-up Amount:</span>
                <span className="text-lg font-semibold text-gray-900">
                  {formatCurrency(parseFloat(amount))}
                </span>
              </div>
            </div>
          )}

          {/* Payment Note */}
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md">
            <p className="text-xs text-blue-600">
              <strong>Note:</strong> This is a test environment. In production, you'll be redirected to a secure payment gateway.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleTopup}
            disabled={!amount || parseFloat(amount) <= 0 || loading}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Processing...' : `Top Up ${amount ? formatCurrency(parseFloat(amount)) : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
}

export default TopupModal;