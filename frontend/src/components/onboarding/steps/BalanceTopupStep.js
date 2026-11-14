import React, { useState } from 'react';
import axios from 'axios';
import {
  CurrencyDollarIcon,
  CheckCircleIcon,
  BoltIcon,
  CloudArrowUpIcon,
  CreditCardIcon,
} from '@heroicons/react/24/outline';
import { showSuccessToast, showErrorToast } from '../../../utils/customToast';

const BalanceTopupStep = ({ stepData, onComplete }) => {
  const [amount, setAmount] = useState('');
  const [customAmount, setCustomAmount] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const isCompleted = stepData?.completed;
  const currentBalance = stepData?.details?.current_balance || 0;

  const presetAmounts = [10, 25, 50, 100];

  const handlePresetClick = (value) => {
    setAmount(value.toString());
    setCustomAmount(false);
    setError(null);
  };

  const handleCustomAmountChange = (e) => {
    const value = e.target.value;
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
      setError('Minimum top-up amount is $1.00');
      return;
    }

    if (topupAmount > 10000) {
      setError('Maximum top-up amount is $10,000.00');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await axios.post('/api/v1/tenant/balance/topup', {
        amount: topupAmount,
        payment_method: 'manual',
      });

      if (response.data.success) {
        showSuccessToast(`Successfully added $${topupAmount.toFixed(2)} to your balance`);
        setAmount('');
        // Refresh onboarding status to update completion
        if (onComplete) {
          await onComplete();
        }
      } else {
        setError(response.data.error || 'Failed to process top-up');
      }
    } catch (err) {
      console.error('Error processing top-up:', err);
      setError(err.response?.data?.detail || 'Failed to process top-up');
      showErrorToast('Failed to process top-up');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(value);
  };

  const reasons = [
    {
      icon: BoltIcon,
      title: 'Flow Execution',
      description: 'Running flows consumes credits based on complexity',
    },
    {
      icon: CloudArrowUpIcon,
      title: 'API Calls',
      description: 'External service calls are metered per request',
    },
    {
      icon: CreditCardIcon,
      title: 'Pay As You Go',
      description: 'Only pay for what you use, no monthly minimums',
    },
  ];

  return (
    <div className="space-y-6">
      {/* Status banner */}
      {isCompleted ? (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
          <CheckCircleIcon className="h-6 w-6 text-green-600" />
          <div>
            <h3 className="text-sm font-medium text-green-800">Balance Added</h3>
            <p className="text-sm text-green-700">
              Current balance: {formatCurrency(currentBalance)}
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <CurrencyDollarIcon className="h-6 w-6 text-amber-600 mt-0.5" />
            <div>
              <h3 className="text-sm font-medium text-amber-800">Why Add Balance?</h3>
              <p className="text-sm text-amber-700 mt-1">
                IOFlow uses a pay-as-you-go model. Add balance to run flows and make API calls.
                Start small - you can always add more later.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Reasons */}
      <div>
        <h3 className="text-sm font-medium text-gray-900 mb-3">What Balance Is Used For</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {reasons.map((reason, index) => (
            <div
              key={index}
              className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
            >
              <reason.icon className="h-8 w-8 text-amber-600 mb-2" />
              <h4 className="text-sm font-medium text-gray-900">{reason.title}</h4>
              <p className="text-xs text-gray-600 mt-1">{reason.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Top-up section */}
      {!isCompleted && (
        <div className="pt-4 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-900 mb-3">Add Balance</h3>

          {/* Preset amounts */}
          <div className="grid grid-cols-4 gap-3 mb-4">
            {presetAmounts.map((preset) => (
              <button
                key={preset}
                onClick={() => handlePresetClick(preset)}
                className={`
                  py-3 px-4 rounded-lg border text-sm font-medium transition-colors
                  ${amount === preset.toString() && !customAmount
                    ? 'border-blue-600 bg-blue-50 text-blue-700'
                    : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                  }
                `}
              >
                ${preset}
              </button>
            ))}
          </div>

          {/* Custom amount */}
          <div className="mb-4">
            <label className="block text-sm text-gray-600 mb-1">Or enter custom amount</label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">$</span>
              <input
                type="text"
                value={customAmount ? amount : ''}
                onChange={(e) => {
                  setCustomAmount(true);
                  handleCustomAmountChange(e);
                }}
                onFocus={() => setCustomAmount(true)}
                placeholder="0.00"
                className="w-full pl-8 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Submit button */}
          <button
            onClick={handleTopup}
            disabled={loading || !amount}
            className={`
              w-full py-3 px-4 rounded-lg text-sm font-medium transition-colors
              ${loading || !amount
                ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
              }
            `}
          >
            {loading ? 'Processing...' : `Add ${amount ? formatCurrency(parseFloat(amount) || 0) : '$0.00'} to Balance`}
          </button>

          <p className="text-xs text-gray-500 mt-2 text-center">
            For testing purposes. In production, this would connect to a payment provider.
          </p>
        </div>
      )}

      {/* Current balance display */}
      {isCompleted && (
        <div className="pt-4 border-t border-gray-200">
          <div className="bg-gray-50 rounded-lg p-4 text-center">
            <p className="text-sm text-gray-600">Current Balance</p>
            <p className="text-2xl font-bold text-gray-900">{formatCurrency(currentBalance)}</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default BalanceTopupStep;
