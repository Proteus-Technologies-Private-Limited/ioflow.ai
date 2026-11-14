import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Tab } from '@headlessui/react';
import {
  UserIcon,
  KeyIcon,
  BuildingOfficeIcon,
  ShieldCheckIcon,
  SparklesIcon,
  CreditCardIcon,
} from '@heroicons/react/24/outline';
import APIKeys from '../components/settings/APIKeys';
import AISettings from '../components/settings/AISettings';
import GoogleOAuthSettings from '../components/admin/GoogleOAuthSettings';
import SMTPConfiguration from '../components/admin/SMTPConfiguration';
import ChangePassword from '../components/auth/ChangePassword';
import SubscriptionPreferences from '../components/settings/SubscriptionPreferences';
import CachePreferences from '../components/settings/CachePreferences';
import LayoutPreferences from '../components/settings/LayoutPreferences';
import OrganizationSettings from '../components/settings/OrganizationSettings';
import { useAuth } from '../contexts/AuthContext';
import { useLayout } from '../contexts/LayoutContext';

function classNames(...classes) {
  return classes.filter(Boolean).join(' ');
}

const Settings = () => {
  const [searchParams] = useSearchParams();
  const [selectedIndex, setSelectedIndex] = useState(0);
  const { user } = useAuth();
  const { isAssistantLayout } = useLayout();

  // Check if user is instance admin
  const isInstanceAdmin = user?.role === 'INSTANCE_ADMIN';
  const isRestrictedRole = user?.role === 'FLOW_EXECUTOR' || user?.role === 'EXECUTION_MONITOR';

  const profilePanel = (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-medium text-gray-900">Profile Settings</h2>
        <p className="mt-2 text-sm text-gray-600">
          Manage your personal account settings and preferences.
        </p>
      </div>

      <div className="border-b pb-6">
        <LayoutPreferences />
      </div>

      <div className="border-b pb-6">
        <CachePreferences />
      </div>

      <div>
        <ChangePassword />
      </div>
    </div>
  );

  const securityPanel = (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-medium text-gray-900">Security Settings</h2>
        <p className="mt-2 text-sm text-gray-600">
          Manage authentication and security settings for your organization.
        </p>
      </div>

      {isInstanceAdmin && (
        <>
          <div className="mt-6">
            <GoogleOAuthSettings />
          </div>

          <div className="mt-8 border-t pt-8">
            <SMTPConfiguration />
          </div>
        </>
      )}

      {!isInstanceAdmin && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
          <p className="text-sm text-yellow-800">
            Advanced security settings are available to instance administrators only.
          </p>
        </div>
      )}
    </div>
  );

  const allTabs = [
    { name: 'Profile', icon: UserIcon, panel: profilePanel },
    { name: 'API Keys', icon: KeyIcon, panel: <APIKeys />, restricted: true },
    { name: 'AI Settings', icon: SparklesIcon, panel: <AISettings />, restricted: true },
    { name: 'Subscription', icon: CreditCardIcon, panel: <SubscriptionPreferences />, restricted: true },
    { name: 'Organization', icon: BuildingOfficeIcon, panel: <OrganizationSettings />, restricted: true },
    { name: 'Security', icon: ShieldCheckIcon, panel: securityPanel, restricted: true },
  ];

  const tabs = allTabs.filter((tab) => !(isRestrictedRole && tab.restricted));

  // Handle URL parameter for tab selection (e.g., /settings?tab=2 for AI Settings)
  useEffect(() => {
    const tabParam = searchParams.get('tab');
    if (tabParam !== null) {
      const tabIndex = parseInt(tabParam, 10);
      if (!isNaN(tabIndex) && tabIndex >= 0 && tabIndex < tabs.length) {
        setSelectedIndex(tabIndex);
      }
    }
  }, [searchParams, tabs.length]);

  return (
    <div className={`py-6 ${isAssistantLayout ? 'px-3 sm:px-4 lg:px-6' : 'px-4 sm:px-6 lg:px-8'}`}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
        <p className="mt-2 text-gray-600">Manage your account settings and preferences</p>

        <div className="mt-6">
          <Tab.Group selectedIndex={selectedIndex} onChange={setSelectedIndex}>
            <Tab.List className="flex space-x-1 rounded-xl bg-gray-100 p-1">
              {tabs.map((tab) => (
                <Tab
                  key={tab.name}
                  className={({ selected }) =>
                    classNames(
                      'w-full rounded-lg py-2.5 text-sm font-medium leading-5',
                      'ring-white ring-opacity-60 ring-offset-2 ring-offset-blue-400 focus:outline-none focus:ring-2',
                      selected
                        ? 'bg-white text-blue-700 shadow'
                        : 'text-gray-600 hover:bg-white/[0.12] hover:text-gray-800'
                    )
                  }
                >
                  <div className="flex items-center justify-center space-x-2">
                    <tab.icon className="h-5 w-5" />
                    <span>{tab.name}</span>
                  </div>
                </Tab>
              ))}
            </Tab.List>
            <Tab.Panels className="mt-6">
              {tabs.map((tab) => (
                <Tab.Panel key={tab.name} className="rounded-xl bg-white p-6 shadow">
                  {tab.panel}
                </Tab.Panel>
              ))}
            </Tab.Panels>
          </Tab.Group>
        </div>
      </div>
    </div>
  );
};

export default Settings;