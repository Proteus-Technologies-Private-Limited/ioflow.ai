import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import {
  CubeIcon,
  BoltIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  ViewColumnsIcon,
  Squares2X2Icon,
  SparklesIcon,
  ShoppingBagIcon,
  ArrowRightIcon,
  PlusIcon,
  CpuChipIcon,
  CurrencyDollarIcon,
  RocketLaunchIcon,
  ArrowPathIcon,
  ExclamationCircleIcon,
  LinkIcon,
  WrenchScrewdriverIcon
} from '@heroicons/react/24/outline';
import { useAuth } from '../contexts/AuthContext';
import { useLayout, LAYOUT_MODES } from '../contexts/LayoutContext';
import { useOnboarding } from '../contexts/OnboardingContext';
import ConnectionModal from '../components/applications/ConnectionModal';

// AI Creation Card Component - defined outside to prevent re-renders
const AICreationCard = ({ icon: Icon, title, description, placeholder, value, onChange, onSubmit, buttonText }) => (
  <div className="bg-white rounded-xl shadow-lg overflow-hidden border border-gray-100 hover:shadow-xl transition-shadow">
    <div className="p-6">
      <div className="flex items-center space-x-3 mb-4">
        <div className="p-3 rounded-lg bg-gradient-primary">
          <Icon className="h-6 w-6 text-white" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          <p className="text-sm text-gray-500">{description}</p>
        </div>
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-primary resize-none text-sm"
        rows={3}
      />
      <button
        onClick={onSubmit}
        disabled={!value.trim()}
        className="mt-4 w-full py-3 px-4 bg-gradient-primary text-white rounded-lg font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
      >
        <SparklesIcon className="h-5 w-5" />
        <span>{buttonText}</span>
      </button>
    </div>
  </div>
);

// Quick Stat Card Component - defined outside to prevent re-renders
const QuickStatCard = ({ icon: Icon, count, label, sublabel, to, addTo, gradientClass, isLoading }) => (
  <div className="group bg-white rounded-xl shadow-md hover:shadow-lg transition-all duration-300 overflow-hidden border border-gray-100 relative">
    <Link to={to} className="block p-5">
      <div className="flex items-start justify-between">
        <div className={`inline-flex p-3 rounded-lg ${gradientClass}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
        {addTo && (
          <Link
            to={addTo}
            onClick={(e) => e.stopPropagation()}
            className="p-2 rounded-lg bg-gray-100 hover:bg-primary hover:text-white text-gray-500 transition-colors"
            title={`Add new ${label.toLowerCase()}`}
          >
            <PlusIcon className="h-4 w-4" />
          </Link>
        )}
      </div>
      <div className="mt-4">
        <p className="text-3xl font-bold text-gray-900">{isLoading ? '-' : count}</p>
        <p className="text-sm font-medium text-gray-600">{label}</p>
        {sublabel && <p className="text-xs text-gray-400 mt-1">{sublabel}</p>}
      </div>
      <div className="mt-3 flex items-center text-sm text-primary font-medium opacity-0 group-hover:opacity-100 transition-opacity">
        <span>View all</span>
        <ArrowRightIcon className="h-4 w-4 ml-1" />
      </div>
    </Link>
  </div>
);

// Compact Setup Progress Card Component
const SetupProgressCard = ({ onboardingStatus, openWizard, loading }) => {
  if (loading || !onboardingStatus?.steps) return null;

  const steps = onboardingStatus.steps;
  const stepConfigs = [
    { key: 'ai', label: 'AI', data: steps.ai_configuration },
    { key: 'balance', label: 'Balance', data: steps.balance_topup },
    { key: 'apps', label: 'Apps', data: steps.application_setup }
  ];

  const completedCount = stepConfigs.filter(s => s.data.completed).length;
  const skippedCount = stepConfigs.filter(s => s.data.skipped).length;
  const allDone = completedCount + skippedCount === 3;

  return (
    <div className={`bg-white rounded-lg shadow-sm border overflow-hidden h-full ${allDone ? 'border-green-200' : 'border-amber-200'}`}>
      {/* Header */}
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RocketLaunchIcon className="h-5 w-5 text-gray-600" />
          <h3 className="text-sm font-semibold text-gray-900">Getting Started</h3>
        </div>
        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
          allDone ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
        }`}>
          {completedCount + skippedCount}/3 Complete
        </span>
      </div>

      {/* Content */}
      <div className="p-4">
        <p className="text-xs text-gray-500 mb-3">Complete these steps to get the most out of IOFlow</p>
        <div className="space-y-2">
          {stepConfigs.map((step) => {
            const done = step.data.completed || step.data.skipped;
            return (
              <div key={step.key} className="flex items-center gap-2">
                {done ? (
                  <CheckCircleIcon className="h-4 w-4 text-green-500 flex-shrink-0" />
                ) : (
                  <div className="h-4 w-4 rounded-full border-2 border-amber-400 flex-shrink-0" />
                )}
                <span className={`text-sm ${done ? 'text-gray-500 line-through' : 'text-gray-700'}`}>
                  {step.key === 'ai' && 'Configure AI Provider'}
                  {step.key === 'balance' && 'Top Up Balance'}
                  {step.key === 'apps' && 'Connect Applications'}
                </span>
              </div>
            );
          })}
        </div>
        <button
          onClick={openWizard}
          className={`mt-4 w-full px-3 py-2 text-sm font-medium rounded-md transition-colors ${
            allDone
              ? 'bg-green-100 text-green-700 hover:bg-green-200'
              : 'bg-amber-100 text-amber-700 hover:bg-amber-200'
          }`}
        >
          {allDone ? 'Review Setup' : 'Continue Setup'}
        </button>
      </div>
    </div>
  );
};

// Application Connection Card Component
const ApplicationConnectionCard = ({ seedApps, isLoading, onConnectApp, onRefresh, onOpenAppSetup }) => {
  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 h-full">
        <div className="animate-pulse flex items-center gap-4">
          <div className="h-10 w-10 bg-gray-200 rounded-lg" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-gray-200 rounded w-1/3" />
            <div className="h-3 bg-gray-200 rounded w-1/2" />
          </div>
        </div>
      </div>
    );
  }

  const apps = seedApps || [];
  const totalApps = apps.length;
  const connectedApps = apps.filter(app => app.subscription_count > 0).length;
  // Apps that are installed (or have updates) but not connected
  const readyToConnect = apps.filter(app => (app.status === 'installed' || app.status === 'update_available') && app.subscription_count === 0).length;
  const notInstalled = apps.filter(app => app.status === 'not_installed').length;

  // Get apps ready to connect for quick action (includes update_available since they can still be connected)
  const appsReadyToConnect = apps.filter(app => (app.status === 'installed' || app.status === 'update_available') && app.subscription_count === 0);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden h-full">
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <LinkIcon className="h-5 w-5 text-gray-600" />
          <h3 className="text-sm font-semibold text-gray-900">Application Connections</h3>
        </div>
        <button
          onClick={onRefresh}
          className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
          title="Refresh"
        >
          <ArrowPathIcon className="h-4 w-4" />
        </button>
      </div>

      <div className="p-4">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <button
            onClick={() => onOpenAppSetup('not_installed')}
            className="text-center p-2 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors cursor-pointer"
            title="Click to view apps available to install"
          >
            <p className="text-lg font-bold text-blue-600">{notInstalled}</p>
            <p className="text-xs text-blue-700">Available to Install</p>
          </button>
          <button
            onClick={() => onOpenAppSetup('installed')}
            className="text-center p-2 bg-amber-50 rounded-lg hover:bg-amber-100 transition-colors cursor-pointer"
            title="Click to view apps ready to connect"
          >
            <p className="text-lg font-bold text-amber-600">{readyToConnect}</p>
            <p className="text-xs text-amber-700">Ready to Connect</p>
          </button>
          <button
            onClick={() => onOpenAppSetup('subscribed')}
            className="text-center p-2 bg-green-50 rounded-lg hover:bg-green-100 transition-colors cursor-pointer"
            title="Click to view connected apps"
          >
            <p className="text-lg font-bold text-green-600">{connectedApps}</p>
            <p className="text-xs text-green-700">Connected</p>
          </button>
        </div>

        {/* Quick Connect Section */}
        {readyToConnect > 0 && (
          <div className="border-t border-gray-100 pt-3">
            <p className="text-xs text-gray-500 mb-2">Quick Connect:</p>
            <div className="flex flex-wrap gap-2">
              {appsReadyToConnect.slice(0, 4).map((app) => (
                <button
                  key={app.key}
                  onClick={() => onConnectApp(app)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 text-xs font-medium rounded-md transition-colors border border-amber-200"
                  title={`Connect to ${app.name}`}
                >
                  {app.icon_url ? (
                    <img
                      src={app.icon_url}
                      alt=""
                      className="h-4 w-4 rounded object-cover"
                      onError={(e) => {
                        // Replace broken image with a fallback initial
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'flex';
                      }}
                    />
                  ) : null}
                  <span
                    className="h-4 w-4 rounded bg-amber-200 text-amber-700 text-[10px] font-bold items-center justify-center flex-shrink-0"
                    style={{ display: app.icon_url ? 'none' : 'flex' }}
                  >
                    {app.name?.charAt(0)?.toUpperCase() || 'A'}
                  </span>
                  {app.name}
                </button>
              ))}
              {readyToConnect > 4 && (
                <Link
                  to="/applications"
                  className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 text-xs font-medium rounded-md transition-colors"
                >
                  +{readyToConnect - 4} more
                </Link>
              )}
            </div>
          </div>
        )}

        {/* All connected message */}
        {readyToConnect === 0 && connectedApps > 0 && (
          <div className="border-t border-gray-100 pt-3">
            <div className="flex items-center gap-2 text-green-600">
              <CheckCircleIcon className="h-4 w-4" />
              <p className="text-xs">All installed apps are connected</p>
            </div>
          </div>
        )}

        {/* No apps installed */}
        {readyToConnect === 0 && connectedApps === 0 && (
          <div className="border-t border-gray-100 pt-3">
            <Link
              to="/applications"
              className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700"
            >
              <WrenchScrewdriverIcon className="h-4 w-4" />
              Install and connect applications
              <ArrowRightIcon className="h-3 w-3" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

const Dashboard = () => {
  const { user } = useAuth();
  const isRestrictedRole = user?.role === 'FLOW_EXECUTOR' || user?.role === 'EXECUTION_MONITOR';
  const canCreateWithAI = !isRestrictedRole;
  const { layoutMode, toggleLayoutMode, isAssistantLayout, setIsAssistantPanelOpen, setIsFloatingAssistantOpen, setPendingAssistantMessage } = useLayout();
  const { onboardingStatus, isAdmin, isSetupIncomplete, openWizard, openWizardWithAppFilter, showWizard, loading: onboardingLoading } = useOnboarding();

  // State for connection modal
  const [showConnectionModal, setShowConnectionModal] = useState(false);
  const [selectedApp, setSelectedApp] = useState(null);

  // State for AI-powered creation inputs
  const [flowDescription, setFlowDescription] = useState('');
  const [connectorDescription, setConnectorDescription] = useState('');

  // Fetch statistics
  const { data: stats, isLoading } = useQuery({
    queryKey: ['executionStats'],
    queryFn: async () => {
      try {
        const response = await axios.get('/api/v1/executions/stats/summary?days=7');
        return response.data;
      } catch (error) {
        console.error('Failed to fetch execution stats:', error);
        return { total_executions: 0, status_breakdown: { completed: 0, failed: 0, running: 0 }, most_active_flows: [] };
      }
    },
    enabled: !!user,
    retry: false
  });

  const { data: applications } = useQuery({
    queryKey: ['applicationCount'],
    queryFn: async () => {
      try {
        const response = await axios.get('/api/v1/applications/');
        return response.data;
      } catch (error) {
        console.error('Failed to fetch applications:', error);
        return [];
      }
    },
    enabled: !!user,
    retry: false
  });

  const { data: flows } = useQuery({
    queryKey: ['flowCount'],
    queryFn: async () => {
      try {
        const response = await axios.get('/api/v1/flows/');
        return response.data;
      } catch (error) {
        console.error('Failed to fetch flows:', error);
        return [];
      }
    },
    enabled: !!user,
    retry: false
  });

  // Fetch Micro SaaS apps count
  const { data: microSaasData } = useQuery({
    queryKey: ['microSaasCount'],
    queryFn: async () => {
      try {
        const response = await axios.get('/api/v1/micro-saas-apps');
        return response.data;
      } catch (error) {
        console.error('Failed to fetch micro saas apps:', error);
        return { total: 0, apps: [] };
      }
    },
    enabled: !!user,
    retry: false
  });

  // Fetch seed applications for connection card
  const { data: seedAppsData, isLoading: seedAppsLoading, refetch: refetchSeedApps } = useQuery({
    queryKey: ['seedApplications'],
    queryFn: async () => {
      try {
        const response = await axios.get('/api/v1/seed-applications/');
        return response.data.applications || [];
      } catch (error) {
        console.error('Failed to fetch seed applications:', error);
        return [];
      }
    },
    enabled: !!user && isAdmin,
    retry: false
  });

  // Track previous wizard state to detect when it closes
  const prevShowWizardRef = useRef(showWizard);

  // Refetch seed apps when wizard closes (user may have installed/connected apps)
  useEffect(() => {
    if (prevShowWizardRef.current === true && showWizard === false) {
      // Wizard just closed, refetch data
      refetchSeedApps();
    }
    prevShowWizardRef.current = showWizard;
  }, [showWizard, refetchSeedApps]);

  // Handle connecting to an app
  const handleConnectApp = (app) => {
    const applicationForModal = {
      app_id: app.app_id,
      app_name: app.name,
      description: app.description,
      auth_type: app.auth_type,
      category: app.category,
      icon_url: app.icon_url,
    };
    setSelectedApp(applicationForModal);
    setShowConnectionModal(true);
  };

  // Handle successful connection
  const handleConnectionSuccess = () => {
    setShowConnectionModal(false);
    setSelectedApp(null);
    refetchSeedApps();
  };

  // Handle opening application setup wizard with specific filter
  const handleOpenAppSetup = (filterValue) => {
    openWizardWithAppFilter(filterValue);
  };

  // AI-powered creation handlers
  const handleCreateFlowWithAI = () => {
    if (!flowDescription.trim()) return;

    // Set the pending message with agent ID (panel will select agent and send message)
    setPendingAssistantMessage({
      message: `Create a flow that: ${flowDescription}`,
      agentId: 'flow_designer'
    });
    setFlowDescription(''); // Clear input

    // Open assistant panel
    if (isAssistantLayout) {
      setIsAssistantPanelOpen(true);
    } else {
      setIsFloatingAssistantOpen(true);
    }
  };

  const handleCreateConnectorWithAI = () => {
    if (!connectorDescription.trim()) return;

    // Set the pending message with agent ID (panel will select agent and send message)
    setPendingAssistantMessage({
      message: `Create an application connector for: ${connectorDescription}`,
      agentId: 'seed_application_designer' // fallback handled in panel
    });
    setConnectorDescription('');

    // Open assistant panel
    if (isAssistantLayout) {
      setIsAssistantPanelOpen(true);
    } else {
      setIsFloatingAssistantOpen(true);
    }
  };

  const statusCards = [
    {
      name: 'Total Executions',
      value: stats?.total_executions || 0,
      icon: PlayIcon,
      color: 'bg-gradient-primary',
    },
    {
      name: 'Successful',
      value: stats?.status_breakdown?.completed || 0,
      icon: CheckCircleIcon,
      color: 'bg-secondary',
    },
    {
      name: 'Failed',
      value: stats?.status_breakdown?.failed || 0,
      icon: XCircleIcon,
      color: 'bg-red-500',
    },
    {
      name: 'Running',
      value: stats?.status_breakdown?.running || 0,
      icon: ClockIcon,
      color: 'bg-primary',
    },
  ];

  return (
    <div className={`py-6 ${isAssistantLayout ? 'px-3 sm:px-4 lg:px-6' : 'px-4 sm:px-6 lg:px-8'}`}>
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">
              Welcome back, {user?.username}!
            </h1>
            <p className="mt-1 text-sm text-gray-600">
              Here's what's happening with your integrations today.
            </p>
          </div>

          {/* Layout Toggle Button */}
          {!isRestrictedRole && (
            <button
              onClick={toggleLayoutMode}
              className="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
              title={`Switch to ${isAssistantLayout ? 'Classic' : 'Assistant Panel'} Layout`}
            >
              {isAssistantLayout ? (
                <>
                  <Squares2X2Icon className="h-4 w-4 mr-2" />
                  Classic Layout
                </>
              ) : (
                <>
                  <ViewColumnsIcon className="h-4 w-4 mr-2" />
                  Assistant Layout
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Admin Cards - Setup Progress and Application Connections */}
      {isAdmin && (
        <section className="mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <SetupProgressCard
              onboardingStatus={onboardingStatus}
              openWizard={openWizard}
              loading={onboardingLoading}
            />
            <ApplicationConnectionCard
              seedApps={seedAppsData}
              isLoading={seedAppsLoading}
              onConnectApp={handleConnectApp}
              onRefresh={refetchSeedApps}
              onOpenAppSetup={handleOpenAppSetup}
            />
          </div>
        </section>
      )}

      {/* AI-Powered Creation Section */}
      {canCreateWithAI && (
        <section className="mb-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Create with AI</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <AICreationCard
              icon={BoltIcon}
              title="Design a Flow"
              description="Describe your automation workflow in plain English"
              placeholder="e.g., When a new order is placed in Shopify, send a Slack notification and create a task in Asana"
              value={flowDescription}
              onChange={setFlowDescription}
              onSubmit={handleCreateFlowWithAI}
              buttonText="Create Flow with AI"
            />
            <AICreationCard
              icon={CubeIcon}
              title="Build a Connector"
              description="Connect to any API or service"
              placeholder="e.g., Connect to Stripe API to process payments and manage subscriptions"
              value={connectorDescription}
              onChange={setConnectorDescription}
              onSubmit={handleCreateConnectorWithAI}
              buttonText="Create Connector with AI"
            />
          </div>
        </section>
      )}

      {/* Quick Stats Section */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Workspace</h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <QuickStatCard
            icon={BoltIcon}
            count={flows?.length || 0}
            label="Total Flows"
            sublabel="Click to manage"
            to="/flows"
            addTo={isRestrictedRole ? undefined : "/flows/new"}
            gradientClass="bg-gradient-to-br from-cyan-500 to-teal-500"
            isLoading={isLoading}
          />
          {!isRestrictedRole && (
            <QuickStatCard
              icon={ShoppingBagIcon}
              count={microSaasData?.total || 0}
              label="Micro SaaS Apps"
              sublabel="Your published apps"
              to="/micro-saas"
              gradientClass="bg-gradient-to-br from-purple-500 to-indigo-500"
              isLoading={isLoading}
            />
          )}
          {!isRestrictedRole && (
            <QuickStatCard
              icon={CubeIcon}
              count={applications?.length || 0}
              label="Applications"
              sublabel="Connected services"
              to="/applications"
              addTo="/applications/new"
              gradientClass="bg-gradient-to-br from-orange-500 to-red-500"
              isLoading={isLoading}
            />
          )}
          <QuickStatCard
            icon={PlayIcon}
            count={stats?.total_executions || 0}
            label="Executions"
            sublabel="Last 7 days"
            to="/executions"
            gradientClass="bg-gradient-to-br from-green-500 to-emerald-500"
            isLoading={isLoading}
          />
        </div>
      </section>

      {/* Statistics */}
      <div className="mb-8">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Last 7 Days</h2>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {statusCards.map((card) => (
            <div key={card.name} className="bg-white overflow-hidden shadow rounded-lg">
              <div className="p-5">
                <div className="flex items-center">
                  <div className={`flex-shrink-0 ${card.color} rounded-md p-3`}>
                    <card.icon className="h-6 w-6 text-white" aria-hidden="true" />
                  </div>
                  <div className="ml-5 w-0 flex-1">
                    <dl>
                      <dt className="text-sm font-medium text-gray-500 truncate">{card.name}</dt>
                      <dd className="text-2xl font-semibold text-gray-900">
                        {isLoading ? '-' : card.value}
                      </dd>
                    </dl>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Your Resources</h3>
          <dl className="space-y-4">
            {!isRestrictedRole && (
              <div className="flex justify-between">
                <dt className="text-sm font-medium text-gray-500">Active Applications</dt>
                <dd className="text-sm font-semibold text-gray-900">
                  {applications?.length || 0}
                </dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-sm font-medium text-gray-500">Total Flows</dt>
              <dd className="text-sm font-semibold text-gray-900">
                {flows?.length || 0}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-sm font-medium text-gray-500">Active Flows</dt>
              <dd className="text-sm font-semibold text-gray-900">
                {flows?.filter(f => f.status === 'active').length || 0}
              </dd>
            </div>
          </dl>
        </div>

        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Most Active Flows</h3>
          {stats?.most_active_flows?.length > 0 ? (
            <ul className="space-y-3">
              {stats.most_active_flows.map((flow) => (
                <li key={flow.flow_id} className="flex items-center justify-between group">
                  <Link
                    to={`/flows/${flow.flow_id}/edit`}
                    className="text-sm text-gray-600 truncate pr-2 hover:text-primary"
                  >
                    {flow.flow_name}
                  </Link>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-semibold text-gray-900">
                      {flow.execution_count} runs
                    </span>
                    <Link
                      to={`/flows/${flow.flow_id}/edit`}
                      className="p-1.5 rounded-md bg-gray-100 hover:bg-green-500 hover:text-white text-gray-500 transition-colors opacity-0 group-hover:opacity-100"
                      title="Open flow"
                    >
                      <PlayIcon className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-500">No flow executions yet</p>
          )}
        </div>
      </div>

      {/* Connection Modal */}
      {showConnectionModal && selectedApp && (
        <ConnectionModal
          application={selectedApp}
          subscription={null}
          onClose={() => {
            setShowConnectionModal(false);
            setSelectedApp(null);
          }}
          onSuccess={handleConnectionSuccess}
        />
      )}
    </div>
  );
};

export default Dashboard;