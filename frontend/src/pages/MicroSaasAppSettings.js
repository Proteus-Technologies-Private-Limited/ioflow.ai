import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Cog6ToothIcon,
  CurrencyDollarIcon,
  ChartBarIcon,
  UserGroupIcon,
  DocumentTextIcon,
  ArrowLeftIcon,
  CheckIcon,
  XMarkIcon,
  ArrowsRightLeftIcon
} from '@heroicons/react/24/outline';
import { BookOpen } from 'lucide-react';
import { microSaasService } from '../services/microSaasService';
import { showErrorToast, showSuccessToast } from '../utils/customToast';

// Import tab components
import GeneralSettingsTab from '../components/microsaas/GeneralSettingsTab';
import BillingConfigTab from '../components/microsaas/BillingConfigTab';
import AnalyticsTab from '../components/microsaas/AnalyticsTab';
import SubscribersTab from '../components/microsaas/SubscribersTab';
import BillingHistoryTab from '../components/microsaas/BillingHistoryTab';
import DocumentationTab from '../components/microsaas/DocumentationTab';
import RelatedFlowsTab from '../components/microsaas/RelatedFlowsTab';
import LandingPageDesignerTab from '../components/landing-page-builder/designer/LandingPageDesignerTab';
import { PaintBrushIcon } from '@heroicons/react/24/outline';

const TABS = [
  { id: 'general', name: 'General Settings', icon: Cog6ToothIcon },
  { id: 'billing', name: 'Billing Configuration', icon: CurrencyDollarIcon },
  { id: 'documentation', name: 'Documentation', icon: BookOpen },
  { id: 'landing-page', name: 'Landing Page', icon: PaintBrushIcon },
  { id: 'related-flows', name: 'Related Flows', icon: ArrowsRightLeftIcon },
  { id: 'analytics', name: 'Usage & Analytics', icon: ChartBarIcon },
  { id: 'subscribers', name: 'Subscribers', icon: UserGroupIcon },
  { id: 'billing-history', name: 'Billing History', icon: DocumentTextIcon }
];

const MicroSaasAppSettings = () => {
  const { appId } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('general');
  const [app, setApp] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    loadApp();
  }, [appId]);

  const loadApp = async () => {
    setIsLoading(true);
    try {
      const appData = await microSaasService.getMicroSaasApp(appId);
      setApp(appData);
    } catch (error) {
      console.error('Error loading app:', error);
      showErrorToast('Failed to load app details');
      navigate('/micro-saas');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveSettings = async (updates) => {
    setIsSaving(true);
    try {
      const updatedApp = await microSaasService.updateAppSettings(appId, updates);
      setApp(updatedApp);
      showSuccessToast('Settings saved successfully');
      return true;
    } catch (error) {
      console.error('Error saving settings:', error);
      showErrorToast('Failed to save settings');
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveVisibility = async (visibility) => {
    setIsSaving(true);
    try {
      const updatedApp = await microSaasService.updateVisibility(appId, visibility);
      setApp(updatedApp);
      showSuccessToast('Visibility updated successfully');
      return true;
    } catch (error) {
      console.error('Error updating visibility:', error);
      showErrorToast('Failed to update visibility');
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveBilling = async (billingConfig) => {
    setIsSaving(true);
    try {
      const updatedApp = await microSaasService.updateBillingConfig(appId, billingConfig);
      setApp(updatedApp);
      showSuccessToast('Billing configuration saved successfully');
      return true;
    } catch (error) {
      console.error('Error saving billing config:', error);
      showErrorToast('Failed to save billing configuration');
      return false;
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-6">
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        </div>
      </div>
    );
  }

  if (!app) {
    return (
      <div className="container mx-auto px-4 py-6">
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <h3 className="text-lg font-medium text-gray-900">App not found</h3>
          <p className="mt-1 text-sm text-gray-500">The requested Micro SaaS app could not be found.</p>
          <div className="mt-6">
            <button
              onClick={() => navigate('/micro-saas')}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg"
            >
              Back to Apps
            </button>
          </div>
        </div>
      </div>
    );
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'general':
        return (
          <GeneralSettingsTab
            app={app}
            onSave={handleSaveSettings}
            onSaveVisibility={handleSaveVisibility}
            isSaving={isSaving}
          />
        );
      case 'billing':
        return (
          <BillingConfigTab
            app={app}
            onSave={handleSaveBilling}
            isSaving={isSaving}
          />
        );
      case 'documentation':
        return (
          <DocumentationTab
            appId={appId}
            appName={app.frontend_app_name}
          />
        );
      case 'landing-page':
        return <LandingPageDesignerTab app={app} />;
      case 'related-flows':
        return (
          <RelatedFlowsTab
            app={app}
            onRefresh={loadApp}
          />
        );
      case 'analytics':
        return <AnalyticsTab appId={appId} app={app} />;
      case 'subscribers':
        return <SubscribersTab appId={appId} app={app} />;
      case 'billing-history':
        return <BillingHistoryTab appId={appId} app={app} />;
      default:
        return <div>Select a tab</div>;
    }
  };

  return (
    <div className="container mx-auto px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate('/micro-saas')}
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
        >
          <ArrowLeftIcon className="h-4 w-4 mr-1" />
          Back to Apps
        </button>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{app.frontend_app_name}</h1>
            <p className="mt-1 text-sm text-gray-500">{app.description}</p>
            <div className="mt-2 flex items-center space-x-4">
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                app.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
              }`}>
                {app.is_active ? (
                  <>
                    <CheckIcon className="h-3 w-3 mr-1" />
                    Active
                  </>
                ) : (
                  <>
                    <XMarkIcon className="h-3 w-3 mr-1" />
                    Inactive
                  </>
                )}
              </span>
              <a
                href={app.public_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:text-primary-dark"
              >
                {app.public_url}
              </a>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        {/* Tab Headers */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6" aria-label="Tabs">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    group inline-flex items-center py-4 px-1 border-b-2 font-medium text-sm
                    ${isActive
                      ? 'border-primary text-primary'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }
                  `}
                >
                  <Icon
                    className={`
                      -ml-0.5 mr-2 h-5 w-5
                      ${isActive ? 'text-primary' : 'text-gray-400 group-hover:text-gray-500'}
                    `}
                  />
                  {tab.name}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
};

export default MicroSaasAppSettings;
