import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftIcon } from '@heroicons/react/24/outline';
import SubscriptionPreferences from '../components/settings/SubscriptionPreferences';

const SubscriptionPage = () => {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="py-6 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-6">
            <Link
              to="/settings"
              className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              Back to Settings
            </Link>
          </div>
          
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Subscription & Billing</h1>
            <p className="mt-2 text-lg text-gray-600">
              Manage your organization's subscription preferences, billing settings, and spending limits
            </p>
          </div>

          {/* Subscription Preferences Component */}
          <SubscriptionPreferences />
        </div>
      </div>
    </div>
  );
};

export default SubscriptionPage;