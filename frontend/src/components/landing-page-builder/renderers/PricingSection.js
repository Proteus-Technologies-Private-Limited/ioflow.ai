import React from 'react';
import { CheckIcon } from '@heroicons/react/24/outline';

export default function PricingSection({ config, appInfo }) {
  const billingPref = appInfo?.billing_preference || 'free';

  return (
    <div className="py-8">
      {config.title && (
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">{config.title}</h2>
      )}
      <div className="max-w-md mx-auto bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
        <div className="bg-gradient-primary p-6 text-center text-white">
          {config.showBillingPreference !== false && (
            <div className="text-sm opacity-80 mb-1">
              {billingPref === 'free' && 'Free'}
              {billingPref === 'per_execution' && 'Pay Per Use'}
              {billingPref === 'per_user_per_month' && 'Monthly Subscription'}
            </div>
          )}
          {config.customPriceText ? (
            <div className="text-3xl font-bold">{config.customPriceText}</div>
          ) : (
            <div className="text-3xl font-bold">
              {billingPref === 'free' ? 'Free' : 'Contact Us'}
            </div>
          )}
        </div>
        {config.features && config.features.length > 0 && (
          <div className="p-6">
            <ul className="space-y-3">
              {config.features.map((feature, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <CheckIcon className="w-5 h-5 text-green-500 shrink-0 mt-0.5" />
                  <span className="text-sm text-gray-700">{feature}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
