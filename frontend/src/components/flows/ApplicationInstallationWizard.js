import React, { useState, useEffect } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import {
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const ApplicationInstallationWizard = ({
  open,
  onClose,
  validationData,
  flowName,
  onAllAppsReady
}) => {
  const [expandedApps, setExpandedApps] = useState({});
  const [installationStatus, setInstallationStatus] = useState({});
  const [credentials, setCredentials] = useState({});
  const [configValues, setConfigValues] = useState({});  // For subscription config like {domain}
  const [loading, setLoading] = useState({});

  // Initialize state when validation data changes
  useEffect(() => {
    if (validationData?.missing_applications) {
      const initialStatus = {};
      const initialExpanded = {};

      validationData.missing_applications.forEach(app => {
        initialStatus[app.app_id] = app.status; // 'not_subscribed', 'not_connected', 'ready'
        initialExpanded[app.app_id] = false;

        // Debug log
        console.log('App validation data:', {
          name: app.app_name,
          status: app.status,
          auth_type: app.auth_type,
          required_fields: app.required_fields,
          is_subscribed: app.is_subscribed,
          subscription_id: app.subscription_id
        });
      });

      setInstallationStatus(initialStatus);
      setExpandedApps(initialExpanded);
    }
  }, [validationData]);

  const toggleAppExpansion = (appId) => {
    setExpandedApps(prev => ({
      ...prev,
      [appId]: !prev[appId]
    }));
  };

  const handleCredentialChange = (appId, fieldName, value) => {
    setCredentials(prev => ({
      ...prev,
      [appId]: {
        ...(prev[appId] || {}),
        [fieldName]: value
      }
    }));
  };

  const handleConfigChange = (appId, fieldName, value) => {
    setConfigValues(prev => ({
      ...prev,
      [appId]: {
        ...(prev[appId] || {}),
        [fieldName]: value
      }
    }));
  };

  const handleInstallSeedApplication = async (app) => {
    setLoading(prev => ({ ...prev, [app.app_id]: true }));

    try {
      // Install the seed application
      console.log('Installing seed application:', app.seed_application_key);

      const installResponse = await axios.post('/api/v1/seed-applications/install', {
        application_key: app.seed_application_key,
        force_reinstall: false
      });

      console.log('Seed application installed:', installResponse.data);
      showSuccessToast(`${app.app_name} installed successfully`);

      // Update status to 'not_subscribed' since the app is now in the DB
      setInstallationStatus(prev => ({
        ...prev,
        [app.app_id]: 'not_subscribed'
      }));

      // Update the validation data to reflect the new status
      if (validationData?.missing_applications) {
        const updatedMissingApps = validationData.missing_applications.map(a =>
          a.app_id === app.app_id ? { ...a, status: 'not_subscribed' } : a
        );
        setWizardValidationData({
          ...validationData,
          missing_applications: updatedMissingApps
        });
      }

    } catch (error) {
      console.error('Installation error for', app.app_name, ':', error);
      console.error('Error response:', error.response);

      let errorMsg = `Failed to install ${app.app_name}`;
      if ((error.response?.data?.message || error.response?.data?.detail)) {
        const detail = error.response.data.detail;
        if (typeof detail === 'object' && detail.message) {
          errorMsg = detail.message;
        } else if (typeof detail === 'string') {
          errorMsg = detail;
        } else {
          errorMsg = JSON.stringify(detail);
        }
      } else if (error.message) {
        errorMsg = error.message;
      }

      showErrorToast(errorMsg);
    } finally {
      setLoading(prev => ({ ...prev, [app.app_id]: false }));
    }
  };

  const handleInstallAndConnect = async (app) => {
    setLoading(prev => ({ ...prev, [app.app_id]: true }));

    try {
      let subscriptionId = app.subscription_id;

      // Step 1: Subscribe if not already subscribed
      if (app.status === 'not_subscribed') {
        console.log('Attempting to subscribe to:', app.app_name, 'with app_id:', app.app_id);

        // Validate config fields if required
        const appConfigValues = configValues[app.app_id] || {};
        if (app.config_fields && app.config_fields.length > 0) {
          const missingConfigFields = app.config_fields
            .filter(field => field.required && !appConfigValues[field.name])
            .map(field => field.label);

          if (missingConfigFields.length > 0) {
            showErrorToast(`Please fill in: ${missingConfigFields.join(', ')}`);
            setLoading(prev => ({ ...prev, [app.app_id]: false }));
            return;
          }
        }

        const subscribeResponse = await axios.post('/api/v1/applications/subscriptions/', {
          app_id: app.app_id,
          auth_credentials: null, // Will add credentials in next step
          subscription_config: appConfigValues  // Include config values like {domain}
        });

        subscriptionId = subscribeResponse.data.subscription_id;
        console.log('Subscription successful, subscription_id:', subscriptionId);
        showSuccessToast(`Subscribed to ${app.app_name}`);
      } else if (app.status === 'not_connected' && app.subscription_id) {
        // App is already subscribed, just needs credentials
        subscriptionId = app.subscription_id;
        console.log('Using existing subscription:', subscriptionId);
      }

      // Step 2: Add credentials if required
      if (app.auth_type && app.auth_type !== 'none' && app.required_fields && app.required_fields.length > 0) {
        const appCredentials = credentials[app.app_id] || {};

        // Validate required fields
        const missingFields = app.required_fields
          .filter(field => field.required && !appCredentials[field.name])
          .map(field => field.label);

        if (missingFields.length > 0) {
          showErrorToast(`Please fill in: ${missingFields.join(', ')}`);
          setLoading(prev => ({ ...prev, [app.app_id]: false }));
          return;
        }

        // Update subscription with credentials
        await axios.put(
          `/api/v1/applications/subscriptions/${subscriptionId}`,
          {
            auth_credentials: appCredentials
          }
        );

        showSuccessToast(`Connected to ${app.app_name}`);
      } else if (!subscriptionId) {
        // If we still don't have a subscription ID, something went wrong
        showErrorToast(`Failed to subscribe to ${app.app_name}`);
        setLoading(prev => ({ ...prev, [app.app_id]: false }));
        return;
      } else {
        // App doesn't require credentials, just subscription
        showSuccessToast(`${app.app_name} is ready to use`);
      }

      // Update local status
      setInstallationStatus(prev => ({
        ...prev,
        [app.app_id]: 'ready'
      }));

      // Collapse the card after successful installation
      setExpandedApps(prev => ({
        ...prev,
        [app.app_id]: false
      }));

    } catch (error) {
      console.error('Installation error for', app.app_name, ':', error);
      console.error('Error response:', error.response);

      let errorMsg = `Failed to setup ${app.app_name}`;
      if ((error.response?.data?.message || error.response?.data?.detail)) {
        errorMsg = typeof error.response.data.detail === 'string'
          ? error.response.data.detail
          : JSON.stringify(error.response.data.detail);
      } else if (error.message) {
        errorMsg = error.message;
      }

      showErrorToast(errorMsg);
    } finally {
      setLoading(prev => ({ ...prev, [app.app_id]: false }));
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'ready':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            <CheckCircleIcon className="mr-1 h-4 w-4" />
            Ready
          </span>
        );
      case 'not_connected':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            <ExclamationTriangleIcon className="mr-1 h-4 w-4" />
            Needs Credentials
          </span>
        );
      case 'not_subscribed':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
            <ExclamationTriangleIcon className="mr-1 h-4 w-4" />
            Not Subscribed
          </span>
        );
      case 'seed_available':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            <ExclamationTriangleIcon className="mr-1 h-4 w-4" />
            Available to Install
          </span>
        );
      case 'not_found':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
            <ExclamationTriangleIcon className="mr-1 h-4 w-4" />
            Not Available
          </span>
        );
      default:
        return null;
    }
  };

  const allAppsReady = () => {
    if (!validationData?.missing_applications) return false;
    return validationData.missing_applications.every(
      app => installationStatus[app.app_id] === 'ready'
    );
  };

  const handleProceed = async () => {
    if (!allAppsReady()) {
      showErrorToast('Please install and configure all required applications');
      return;
    }

    // Re-validate before proceeding to ensure apps are actually ready
    try {
      setLoading(prev => ({ ...prev, validating: true }));

      // Wait a moment for backend to process subscriptions
      await new Promise(resolve => setTimeout(resolve, 500));

      onAllAppsReady();
      onClose();
    } catch (error) {
      console.error('Validation error:', error);
      showErrorToast('Failed to validate applications');
    } finally {
      setLoading(prev => ({ ...prev, validating: false }));
    }
  };

  const renderCredentialField = (app, field) => {
    const value = credentials[app.app_id]?.[field.name] || '';

    return (
      <div key={field.name} className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">
          {field.label}
          {field.required && <span className="text-red-500 ml-1">*</span>}
        </label>
        {field.description && (
          <p className="text-xs text-gray-500">{field.description}</p>
        )}
        <input
          type={field.type}
          value={value}
          onChange={(e) => handleCredentialChange(app.app_id, field.name, e.target.value)}
          className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          placeholder={field.placeholder || field.label}
          required={field.required}
        />
      </div>
    );
  };

  const renderConfigField = (app, field) => {
    const value = configValues[app.app_id]?.[field.name] || '';

    return (
      <div key={field.name} className="space-y-1">
        <label className="block text-sm font-medium text-gray-700">
          {field.label}
          {field.required && <span className="text-red-500 ml-1">*</span>}
        </label>
        {field.description && (
          <p className="text-xs text-gray-500">{field.description}</p>
        )}
        <input
          type={field.type}
          value={value}
          onChange={(e) => handleConfigChange(app.app_id, field.name, e.target.value)}
          className="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          placeholder={field.placeholder || field.label}
          required={field.required}
        />
      </div>
    );
  };

  const renderApplicationCard = (app) => {
    const isExpanded = expandedApps[app.app_id];
    const status = installationStatus[app.app_id];
    const isLoading = loading[app.app_id];
    const isReady = status === 'ready';

    return (
      <div
        key={app.app_id}
        className={`border rounded-lg overflow-hidden transition-colors ${
          isReady ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-white'
        }`}
      >
        {/* App Header */}
        <div className="p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3 flex-1">
              {app.icon_url && (
                <img
                  src={app.icon_url}
                  alt={app.app_name}
                  className="h-10 w-10 rounded-md flex-shrink-0"
                  onError={(e) => {
                    e.target.style.display = 'none';
                  }}
                />
              )}
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-gray-900">{app.app_name}</h4>
                {app.description && (
                  <p className="text-xs text-gray-600 mt-1 line-clamp-2">{app.description}</p>
                )}
                <div className="flex items-center gap-2 mt-2">
                  {getStatusBadge(status)}
                  <span className="text-xs text-gray-500">Type: {app.app_type}</span>
                </div>
              </div>
            </div>

            {!isReady && (
              <button
                onClick={() => toggleAppExpansion(app.app_id)}
                className="ml-2 inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                {isExpanded ? (
                  <>
                    <ChevronUpIcon className="h-4 w-4 mr-1" />
                    Close
                  </>
                ) : (
                  <>
                    Setup
                    <ChevronDownIcon className="h-4 w-4 ml-1" />
                  </>
                )}
              </button>
            )}
          </div>

          {/* Show where this app is used */}
          {app.used_in_nodes && app.used_in_nodes.length > 0 && (
            <div className="mt-3 bg-blue-50 border border-blue-200 rounded-md p-3">
              <div className="flex items-start gap-2">
                <InformationCircleIcon className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-blue-900">
                    Used in {app.used_in_nodes.length} step{app.used_in_nodes.length > 1 ? 's' : ''}:
                  </p>
                  <ul className="mt-1 space-y-1">
                    {app.used_in_nodes.slice(0, 3).map((node, idx) => (
                      <li key={idx} className="text-xs text-blue-800">
                        • {node.node_label} ({node.service_name})
                      </li>
                    ))}
                    {app.used_in_nodes.length > 3 && (
                      <li className="text-xs text-blue-700 italic">
                        +{app.used_in_nodes.length - 3} more
                      </li>
                    )}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Expanded Content */}
        {isExpanded && !isReady && (
          <div className="border-t border-gray-200 bg-gray-50 p-4 space-y-4">
            {/* Show different content based on status */}
            {status === 'seed_available' ? (
              <>
                {/* Seed Application Installation */}
                <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                  <p className="text-xs text-blue-900">
                    This application is available as a seed application and needs to be installed first.
                    After installation, you can subscribe and configure credentials.
                  </p>
                </div>

                {/* Documentation Link */}
                {app.documentation_url && (
                  <a
                    href={app.documentation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-xs text-indigo-600 hover:text-indigo-500"
                  >
                    <InformationCircleIcon className="h-4 w-4 mr-1" />
                    View setup documentation
                  </a>
                )}

                {/* Install Seed Application Button */}
                <button
                  onClick={() => handleInstallSeedApplication(app)}
                  disabled={isLoading}
                  className="w-full inline-flex justify-center items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Installing Application...
                    </>
                  ) : (
                    <>
                      Install Application
                      <ArrowRightIcon className="ml-2 h-4 w-4" />
                    </>
                  )}
                </button>
              </>
            ) : (
              <>
                {/* Configuration Fields (like domain, server URL variables) */}
                {app.config_fields && app.config_fields.length > 0 && (
                  <div className="space-y-3">
                    <h5 className="text-sm font-medium text-gray-900">
                      Application Configuration
                    </h5>
                    <p className="text-xs text-gray-600">
                      Configure tenant-specific settings for this application
                    </p>
                    {app.config_fields.map(field => renderConfigField(app, field))}
                  </div>
                )}

                {/* Credential Fields */}
                {app.auth_type && app.auth_type !== 'none' && app.required_fields && app.required_fields.length > 0 && (
                  <div className="space-y-3">
                    <h5 className="text-sm font-medium text-gray-900">
                      {status === 'not_subscribed' ? 'Authentication Credentials' : 'Enter Credentials'}
                    </h5>
                    {app.required_fields.map(field => renderCredentialField(app, field))}
                  </div>
                )}

                {/* Documentation Link */}
                {app.documentation_url && (
                  <a
                    href={app.documentation_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center text-xs text-indigo-600 hover:text-indigo-500"
                  >
                    <InformationCircleIcon className="h-4 w-4 mr-1" />
                    View setup documentation
                  </a>
                )}

                {/* Subscribe/Connect Button */}
                <button
                  onClick={() => handleInstallAndConnect(app)}
                  disabled={isLoading}
                  className="w-full inline-flex justify-center items-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Setting up...
                    </>
                  ) : (
                    <>
                      {status === 'not_subscribed' ? 'Subscribe & Connect' : 'Connect'}
                      <ArrowRightIcon className="ml-2 h-4 w-4" />
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        )}
      </div>
    );
  };

  if (!validationData) return null;

  const missingCount = validationData.missing_applications?.length || 0;
  const readyCount = validationData.missing_applications?.filter(
    app => installationStatus[app.app_id] === 'ready'
  ).length || 0;

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={() => {}}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-[100] overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white shadow-xl transition-all w-full max-w-3xl max-h-[90vh] flex flex-col">
                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-200 flex-shrink-0">
                  <div className="flex items-start justify-between">
                    <div>
                      <Dialog.Title as="h3" className="text-lg font-semibold text-gray-900">
                        Setup Required Applications
                      </Dialog.Title>
                      <p className="mt-1 text-sm text-gray-500">
                        Flow: <span className="font-medium">{flowName}</span>
                      </p>
                      <div className="mt-2 flex items-center gap-2">
                        <div className="text-sm">
                          <span className="font-medium text-gray-900">{readyCount}</span>
                          <span className="text-gray-500"> of </span>
                          <span className="font-medium text-gray-900">{missingCount}</span>
                          <span className="text-gray-500"> applications ready</span>
                        </div>
                        {allAppsReady() && (
                          <CheckCircleIcon className="h-5 w-5 text-green-500" />
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none"
                      onClick={onClose}
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="px-6 py-4 overflow-y-auto flex-1">
                  <div className="space-y-3">
                    {validationData.missing_applications?.map(app => renderApplicationCard(app))}
                  </div>
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between flex-shrink-0">
                  <p className="text-sm text-gray-600">
                    {allAppsReady()
                      ? 'All applications are ready. You can now import the flow.'
                      : 'Please install and configure all required applications to proceed.'
                    }
                  </p>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={onClose}
                      className="inline-flex justify-center rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleProceed}
                      disabled={!allAppsReady()}
                      className="inline-flex items-center justify-center rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-green-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-600 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Complete Import
                      <ArrowRightIcon className="ml-2 h-4 w-4" />
                    </button>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default ApplicationInstallationWizard;
