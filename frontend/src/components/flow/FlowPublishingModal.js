import React, { useState, useEffect } from 'react';
import {
  XMarkIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
  ArrowRightIcon,
  CogIcon,
  ShareIcon,
  DocumentTextIcon,
  GlobeAltIcon,
  UserGroupIcon,
  UserIcon,
  BuildingOfficeIcon,
  PlusIcon,
  TrashIcon,
  ShieldCheckIcon,
  CurrencyDollarIcon,
  EyeIcon,
  LockClosedIcon,
  ShoppingBagIcon
} from '@heroicons/react/24/outline';
import { flowPublishingService } from '../../services/flowPublishingService';
import { microSaasService } from '../../services/microSaasService';
import { showErrorToast, showSuccessToast, showInfoToast } from '../../utils/customToast';

const FlowPublishingModal = ({
  isOpen,
  onClose,
  flowId,
  flowName,
  flowDescription,
  publishType, // 'reusable' or 'frontend' - pre-selected type from parent
  onPublishSuccess
}) => {
  const [step, setStep] = useState(1); // 1: Config, 2: Permissions, 3: Preview, 4: Publishing
  const [isLoading, setIsLoading] = useState(false);
  const [publishConfig, setPublishConfig] = useState({
    app_key: '',
    app_name: '',
    description: '',
    category: 'Flow Applications',
    app_scope: 'tenant', // 'global', 'tenant', 'user'
    auto_update: false,
    publish_type: publishType || 'both', // 'reusable', 'frontend', 'both' - use prop if provided
    // Micro SaaS specific fields
    visibility: 'private', // 'public', 'private', 'granted_access'
    billing_preference: 'free', // 'free', 'per_user_per_month', 'per_execution'
    pricing_config: {
      monthly_price: 0,
      price_per_execution: 0,
      trial_period_days: 0,
      free_executions_per_month: 0,
      minimum_users: 1,
      minimum_charge: 0
    },
    usage_limits: {
      max_executions_per_day: null,
      max_executions_per_month: null,
      max_users: null
    },
    frontend_config: {
      access_type: 'public_url',
      rate_limit_per_hour: 100,
      access_config: {
        allowed_users: [],
        allowed_tenants: []
      }
    }
  });
  const [preview, setPreview] = useState(null);
  const [errors, setErrors] = useState({});
  const [newUser, setNewUser] = useState('');
  const [newTenant, setNewTenant] = useState('');

  // Initialize form with flow data
  useEffect(() => {
    if (isOpen && flowName) {
      const defaultAppKey = flowName
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '')
        .slice(0, 50);
      
      setPublishConfig(prev => ({
        ...prev,
        app_key: defaultAppKey,
        app_name: `${flowName} App`,
        description: flowDescription || `Auto-generated application from ${flowName} flow`,
      }));
    }
  }, [isOpen, flowName, flowDescription]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setStep(1);
      setPreview(null);
      setErrors({});
      setNewUser('');
      setNewTenant('');
    }
  }, [isOpen]);

  // Helper functions for permissions management
  const addUser = () => {
    if (!newUser.trim()) return;
    
    const updatedUsers = [...publishConfig.frontend_config.access_config.allowed_users, newUser.trim()];
    setPublishConfig(prev => ({
      ...prev,
      frontend_config: {
        ...prev.frontend_config,
        access_config: {
          ...prev.frontend_config.access_config,
          allowed_users: updatedUsers
        }
      }
    }));
    setNewUser('');
  };

  const removeUser = (index) => {
    const updatedUsers = publishConfig.frontend_config.access_config.allowed_users.filter((_, i) => i !== index);
    setPublishConfig(prev => ({
      ...prev,
      frontend_config: {
        ...prev.frontend_config,
        access_config: {
          ...prev.frontend_config.access_config,
          allowed_users: updatedUsers
        }
      }
    }));
  };

  const addTenant = () => {
    if (!newTenant.trim()) return;
    
    const updatedTenants = [...publishConfig.frontend_config.access_config.allowed_tenants, newTenant.trim()];
    setPublishConfig(prev => ({
      ...prev,
      frontend_config: {
        ...prev.frontend_config,
        access_config: {
          ...prev.frontend_config.access_config,
          allowed_tenants: updatedTenants
        }
      }
    }));
    setNewTenant('');
  };

  const removeTenant = (index) => {
    const updatedTenants = publishConfig.frontend_config.access_config.allowed_tenants.filter((_, i) => i !== index);
    setPublishConfig(prev => ({
      ...prev,
      frontend_config: {
        ...prev.frontend_config,
        access_config: {
          ...prev.frontend_config.access_config,
          allowed_tenants: updatedTenants
        }
      }
    }));
  };

  const getAccessTypeDescription = () => {
    switch (publishConfig.frontend_config.access_type) {
      case 'public_url':
        return 'Anyone with the URL can access this application. No authentication required.';
      case 'organization':
        return 'Only users from your organization can access this application.';
      case 'specific_users':
        return 'Only specific IOFlow users you designate can access this application.';
      case 'tenant_list':
        return 'Users from specific organizations/tenants can access this application.';
      default:
        return '';
    }
  };

  const validateConfig = () => {
    const newErrors = {};

    // Only validate reusable app fields if not frontend-only
    if (publishConfig.publish_type !== 'frontend') {
      if (!publishConfig.app_key.trim()) {
        newErrors.app_key = 'Application key is required';
      } else if (publishConfig.app_key.length < 3) {
        newErrors.app_key = 'Application key must be at least 3 characters';
      } else if (!/^[a-zA-Z0-9_-]+$/.test(publishConfig.app_key)) {
        newErrors.app_key = 'Application key can only contain letters, numbers, hyphens, and underscores';
      }

      if (!publishConfig.app_name.trim()) {
        newErrors.app_name = 'Application name is required';
      } else if (publishConfig.app_name.length < 3) {
        newErrors.app_name = 'Application name must be at least 3 characters';
      }

      if (!publishConfig.description.trim()) {
        newErrors.description = 'Description is required';
      } else if (publishConfig.description.length < 10) {
        newErrors.description = 'Description must be at least 10 characters';
      }
    }

    // Validate frontend config if frontend or both
    if (publishConfig.publish_type === 'frontend' || publishConfig.publish_type === 'both') {
      if (!publishConfig.frontend_config.access_type) {
        newErrors.frontend_access_type = 'Access type is required for frontend application';
      }

      if (!publishConfig.frontend_config.rate_limit_per_hour || publishConfig.frontend_config.rate_limit_per_hour < 1) {
        newErrors.frontend_rate_limit = 'Rate limit must be at least 1 per hour';
      }

      // Validate specific access type requirements
      if (publishConfig.frontend_config.access_type === 'specific_users' &&
          publishConfig.frontend_config.access_config.allowed_users.length === 0) {
        newErrors.frontend_allowed_users = 'At least one user must be specified for specific users access';
      }

      if (publishConfig.frontend_config.access_type === 'tenant_list' &&
          publishConfig.frontend_config.access_config.allowed_tenants.length === 0) {
        newErrors.frontend_allowed_tenants = 'At least one organization must be specified for tenant list access';
      }

      // Validate billing configuration
      if (publishConfig.billing_preference === 'per_user_per_month') {
        if (!publishConfig.pricing_config.monthly_price || publishConfig.pricing_config.monthly_price <= 0) {
          newErrors.pricing_monthly = 'Monthly price must be greater than 0 for subscription billing';
        }
      }

      if (publishConfig.billing_preference === 'per_execution') {
        if (!publishConfig.pricing_config.price_per_execution || publishConfig.pricing_config.price_per_execution <= 0) {
          newErrors.pricing_execution = 'Price per execution must be greater than 0 for usage-based billing';
        }
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (!validateConfig()) return;
    
    // Skip permissions step if not publishing frontend application
    if (step === 1 && publishConfig.publish_type === 'reusable') {
      setStep(3); // Go directly to preview
    } else {
      setStep(step + 1);
    }
  };

  const handlePreview = async () => {
    if (!validateConfig()) return;
    
    setIsLoading(true);
    try {
      const previewData = await flowPublishingService.previewPublishing(
        flowId, 
        publishConfig.app_key
      );
      setPreview(previewData.preview);
      setStep(3);
    } catch (error) {
      showErrorToast(`Preview failed: ${(error.response?.data?.message || error.response?.data?.detail) || error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePublish = async () => {
    setIsLoading(true);
    setStep(4);

    try {
      let result;

      // Check if it's a Micro SaaS app (frontend or both)
      if (publishConfig.publish_type === 'frontend' || publishConfig.publish_type === 'both') {
        // Prepare Micro SaaS app data with proper access_config nesting
        const microSaasData = {
          flow_id: flowId,
          app_key: publishConfig.app_key,
          app_name: publishConfig.app_name,
          description: publishConfig.description,
          category: publishConfig.category,
          visibility: publishConfig.visibility,
          pricing_config: publishConfig.billing_preference !== 'free'
            ? {
                ...publishConfig.pricing_config,
                billing_preference: publishConfig.billing_preference
              }
            : {
                billing_preference: 'free'
              },
          usage_limits: publishConfig.usage_limits,
          access_type: publishConfig.frontend_config.access_type,
          // Nest allowed_users and allowed_tenants inside access_config
          access_config: (publishConfig.frontend_config.access_type === 'specific_users' ||
                         publishConfig.frontend_config.access_type === 'tenant_list')
            ? {
                allowed_users: publishConfig.frontend_config.access_config.allowed_users,
                allowed_tenants: publishConfig.frontend_config.access_config.allowed_tenants
              }
            : null,
          auto_update: publishConfig.auto_update,
          embed_enabled: publishConfig.embed_enabled,
          marketplace_enabled: publishConfig.marketplace_enabled
        };

        result = await microSaasService.createMicroSaasApp(microSaasData);

        // If publishing both types, also create reusable application
        if (publishConfig.publish_type === 'both' && result.success) {
          try {
            await flowPublishingService.publishFlowWithTypes({
              flow_id: flowId,
              app_key: publishConfig.app_key,
              app_name: publishConfig.app_name,
              description: publishConfig.description,
              category: publishConfig.category,
              auto_update: publishConfig.auto_update
            });
          } catch (reusableError) {
            console.warn('Failed to create reusable application:', reusableError);
            // Don't fail the whole operation if reusable creation fails
          }
        }
      } else {
        // Reusable application only
        result = await flowPublishingService.publishFlowWithTypes({
          flow_id: flowId,
          ...publishConfig
        });
      }

      if (result.success || result.frontend_app_id) {
        let successMessage = '';

        if (publishConfig.publish_type === 'reusable') {
          successMessage = 'Reusable application published successfully!';
        } else if (publishConfig.publish_type === 'frontend') {
          successMessage = `Micro SaaS app published successfully! ${result.public_url ? `Public URL: ${result.public_url}` : ''}`;
        } else if (publishConfig.publish_type === 'both') {
          successMessage = 'Micro SaaS app and reusable application published successfully!';
        }

        showSuccessToast(successMessage);

        if (onPublishSuccess) {
          onPublishSuccess(result);
        }

        onClose();
      } else {
        // Show errors
        const errorMessage = result.errors?.length > 0
          ? result.errors.join('; ')
          : result.error || 'Publishing failed';

        setStep(3); // Go back to preview step
        showErrorToast(`Publishing failed: ${errorMessage}`);
      }
    } catch (error) {
      setStep(3); // Go back to preview step
      showErrorToast(`Publishing failed: ${(error.response?.data?.message || error.response?.data?.detail) || error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {publishType === 'reusable' ? (
                <CogIcon className="w-6 h-6" />
              ) : publishType === 'frontend' ? (
                <ShoppingBagIcon className="w-6 h-6" />
              ) : (
                <ShareIcon className="w-6 h-6" />
              )}
              <div>
                <h2 className="text-xl font-semibold">
                  {publishType === 'reusable'
                    ? 'Publish as Reusable Application'
                    : publishType === 'frontend'
                    ? 'Publish as Micro SaaS App'
                    : 'Publish Flow as Application'}
                </h2>
                <p className="text-blue-100 text-sm">
                  {publishType === 'reusable'
                    ? `Convert "${flowName}" into a reusable application for other flows`
                    : publishType === 'frontend'
                    ? `Convert "${flowName}" into a monetizable Micro SaaS application`
                    : `Convert "${flowName}" into a reusable app or Micro SaaS application`}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 transition-colors"
              disabled={isLoading}
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
          
          {/* Progress indicator */}
          <div className="mt-4 flex items-center space-x-2">
            <div className={`flex items-center space-x-2 ${step >= 1 ? 'text-white' : 'text-blue-300'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                step >= 1 ? 'bg-white text-blue-600' : 'bg-blue-500'
              }`}>
                1
              </div>
              <span className="text-sm">Configure</span>
            </div>
            {(publishConfig.publish_type === 'frontend' || publishConfig.publish_type === 'both') && (
              <>
                <ArrowRightIcon className="w-4 h-4 text-blue-300" />
                <div className={`flex items-center space-x-2 ${step >= 2 ? 'text-white' : 'text-blue-300'}`}>
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                    step >= 2 ? 'bg-white text-blue-600' : 'bg-blue-500'
                  }`}>
                    2
                  </div>
                  <span className="text-sm">Permissions</span>
                </div>
              </>
            )}
            <ArrowRightIcon className="w-4 h-4 text-blue-300" />
            <div className={`flex items-center space-x-2 ${step >= 3 ? 'text-white' : 'text-blue-300'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                step >= 3 ? 'bg-white text-blue-600' : 'bg-blue-500'
              }`}>
                {publishConfig.publish_type === 'reusable' ? '2' : '3'}
              </div>
              <span className="text-sm">Preview</span>
            </div>
            <ArrowRightIcon className="w-4 h-4 text-blue-300" />
            <div className={`flex items-center space-x-2 ${step >= 4 ? 'text-white' : 'text-blue-300'}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium ${
                step >= 4 ? 'bg-white text-blue-600' : 'bg-blue-500'
              }`}>
                {publishConfig.publish_type === 'reusable' ? '3' : '4'}
              </div>
              <span className="text-sm">Publish</span>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 max-h-[60vh] overflow-y-auto">
          {step === 1 && (
            <div className="space-y-6">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <InformationCircleIcon className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="font-medium text-blue-900">
                      {publishType === 'reusable'
                        ? 'About Reusable Applications'
                        : publishType === 'frontend'
                        ? 'About Micro SaaS Apps'
                        : 'About Flow Publishing'}
                    </h3>
                    <p className="text-blue-700 text-sm mt-1">
                      {publishType === 'reusable'
                        ? 'Create a reusable application that can be used as a service component by other flows in your organization.'
                        : publishType === 'frontend'
                        ? 'Publish your flow as a Micro SaaS application with marketplace visibility control, billing options, and access management for end users.'
                        : 'Choose how to publish your flow: as a reusable application for other flows, as a Micro SaaS app with visibility and billing control for end users, or both.'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Publishing Type Selection - Only show if publishType not pre-selected */}
              {!publishType && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-3">
                    Publishing Type *
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <label className={`relative rounded-lg border-2 cursor-pointer p-4 transition-colors ${
                      publishConfig.publish_type === 'reusable'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}>
                      <input
                        type="radio"
                        name="publish_type"
                        value="reusable"
                        checked={publishConfig.publish_type === 'reusable'}
                        onChange={(e) => setPublishConfig(prev => ({ ...prev, publish_type: e.target.value }))}
                        className="sr-only"
                      />
                      <div>
                        <CogIcon className="w-6 h-6 text-gray-600 mb-2" />
                        <h4 className="font-medium text-gray-900 mb-1">Reusable Application</h4>
                        <p className="text-sm text-gray-600">
                          For use by other flows as a service component
                        </p>
                      </div>
                    </label>

                    <label className={`relative rounded-lg border-2 cursor-pointer p-4 transition-colors ${
                      publishConfig.publish_type === 'frontend'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}>
                      <input
                        type="radio"
                        name="publish_type"
                        value="frontend"
                        checked={publishConfig.publish_type === 'frontend'}
                        onChange={(e) => setPublishConfig(prev => ({ ...prev, publish_type: e.target.value }))}
                        className="sr-only"
                      />
                      <div>
                        <ShoppingBagIcon className="w-6 h-6 text-gray-600 mb-2" />
                        <h4 className="font-medium text-gray-900 mb-1">Micro SaaS App</h4>
                        <p className="text-sm text-gray-600">
                          Monetizable application with visibility and billing control
                        </p>
                      </div>
                    </label>

                    <label className={`relative rounded-lg border-2 cursor-pointer p-4 transition-colors ${
                      publishConfig.publish_type === 'both'
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}>
                      <input
                        type="radio"
                        name="publish_type"
                        value="both"
                        checked={publishConfig.publish_type === 'both'}
                        onChange={(e) => setPublishConfig(prev => ({ ...prev, publish_type: e.target.value }))}
                        className="sr-only"
                      />
                      <div>
                        <DocumentTextIcon className="w-6 h-6 text-gray-600 mb-2" />
                        <h4 className="font-medium text-gray-900 mb-1">Both</h4>
                        <p className="text-sm text-gray-600">
                          Create both reusable and frontend applications
                        </p>
                      </div>
                    </label>
                  </div>
                </div>
              )}

              {/* Micro SaaS Configuration (only show if frontend or both is selected) */}
              {(publishConfig.publish_type === 'frontend' || publishConfig.publish_type === 'both') && (
                <div className="space-y-4">
                  <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-3 flex items-center">
                      <ShoppingBagIcon className="w-5 h-5 mr-2" />
                      Micro SaaS App Settings
                    </h4>

                    {/* Marketplace Visibility */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-3">
                        Marketplace Visibility *
                      </label>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <label className={`relative rounded-lg border-2 cursor-pointer p-3 transition-colors ${
                          publishConfig.visibility === 'public'
                            ? 'border-green-500 bg-green-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}>
                          <input
                            type="radio"
                            name="visibility"
                            value="public"
                            checked={publishConfig.visibility === 'public'}
                            onChange={(e) => setPublishConfig(prev => ({ ...prev, visibility: e.target.value }))}
                            className="sr-only"
                          />
                          <div className="flex items-start">
                            <GlobeAltIcon className="w-5 h-5 text-green-600 mr-2 flex-shrink-0" />
                            <div>
                              <div className="text-sm font-medium text-gray-900">Public</div>
                              <div className="text-xs text-gray-600 mt-1">
                                Anyone with IOFlow account can see in marketplace
                              </div>
                            </div>
                          </div>
                        </label>

                        <label className={`relative rounded-lg border-2 cursor-pointer p-3 transition-colors ${
                          publishConfig.visibility === 'private'
                            ? 'border-blue-500 bg-blue-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}>
                          <input
                            type="radio"
                            name="visibility"
                            value="private"
                            checked={publishConfig.visibility === 'private'}
                            onChange={(e) => setPublishConfig(prev => ({ ...prev, visibility: e.target.value }))}
                            className="sr-only"
                          />
                          <div className="flex items-start">
                            <LockClosedIcon className="w-5 h-5 text-blue-600 mr-2 flex-shrink-0" />
                            <div>
                              <div className="text-sm font-medium text-gray-900">Private</div>
                              <div className="text-xs text-gray-600 mt-1">
                                Only you can see (useful during testing)
                              </div>
                            </div>
                          </div>
                        </label>

                        <label className={`relative rounded-lg border-2 cursor-pointer p-3 transition-colors ${
                          publishConfig.visibility === 'granted_access'
                            ? 'border-purple-500 bg-purple-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}>
                          <input
                            type="radio"
                            name="visibility"
                            value="granted_access"
                            checked={publishConfig.visibility === 'granted_access'}
                            onChange={(e) => setPublishConfig(prev => ({ ...prev, visibility: e.target.value }))}
                            className="sr-only"
                          />
                          <div className="flex items-start">
                            <EyeIcon className="w-5 h-5 text-purple-600 mr-2 flex-shrink-0" />
                            <div>
                              <div className="text-sm font-medium text-gray-900">Granted Access</div>
                              <div className="text-xs text-gray-600 mt-1">
                                Only users with access can see
                              </div>
                            </div>
                          </div>
                        </label>
                      </div>
                    </div>

                    {/* Billing Preference */}
                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-3">
                        Billing Model
                      </label>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <label className={`relative rounded-lg border-2 cursor-pointer p-3 transition-colors ${
                          publishConfig.billing_preference === 'free'
                            ? 'border-gray-500 bg-gray-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}>
                          <input
                            type="radio"
                            name="billing_preference"
                            value="free"
                            checked={publishConfig.billing_preference === 'free'}
                            onChange={(e) => setPublishConfig(prev => ({ ...prev, billing_preference: e.target.value }))}
                            className="sr-only"
                          />
                          <div className="text-center">
                            <div className="text-sm font-medium text-gray-900">Free to Use</div>
                            <div className="text-xs text-gray-600 mt-1">No charges</div>
                          </div>
                        </label>

                        <label className={`relative rounded-lg border-2 cursor-pointer p-3 transition-colors ${
                          publishConfig.billing_preference === 'per_user_per_month'
                            ? 'border-indigo-500 bg-indigo-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}>
                          <input
                            type="radio"
                            name="billing_preference"
                            value="per_user_per_month"
                            checked={publishConfig.billing_preference === 'per_user_per_month'}
                            onChange={(e) => setPublishConfig(prev => ({ ...prev, billing_preference: e.target.value }))}
                            className="sr-only"
                          />
                          <div className="text-center">
                            <div className="text-sm font-medium text-gray-900">Per User / Month</div>
                            <div className="text-xs text-gray-600 mt-1">Monthly subscription</div>
                          </div>
                        </label>

                        <label className={`relative rounded-lg border-2 cursor-pointer p-3 transition-colors ${
                          publishConfig.billing_preference === 'per_execution'
                            ? 'border-green-500 bg-green-50'
                            : 'border-gray-200 hover:border-gray-300'
                        }`}>
                          <input
                            type="radio"
                            name="billing_preference"
                            value="per_execution"
                            checked={publishConfig.billing_preference === 'per_execution'}
                            onChange={(e) => setPublishConfig(prev => ({ ...prev, billing_preference: e.target.value }))}
                            className="sr-only"
                          />
                          <div className="text-center">
                            <div className="text-sm font-medium text-gray-900">Per Execution</div>
                            <div className="text-xs text-gray-600 mt-1">Pay per usage</div>
                          </div>
                        </label>
                      </div>
                    </div>

                    {/* Pricing Configuration - Per User Per Month */}
                    {publishConfig.billing_preference === 'per_user_per_month' && (
                      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 mb-4">
                        <h5 className="text-sm font-medium text-indigo-900 mb-3">Subscription Pricing</h5>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Monthly Price ($) *
                            </label>
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              value={publishConfig.pricing_config.monthly_price}
                              onChange={(e) => setPublishConfig(prev => ({
                                ...prev,
                                pricing_config: { ...prev.pricing_config, monthly_price: parseFloat(e.target.value) || 0 }
                              }))}
                              className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm ${
                                errors.pricing_monthly ? 'border-red-500' : 'border-gray-300'
                              }`}
                              placeholder="9.99"
                            />
                            {errors.pricing_monthly && (
                              <p className="text-red-500 text-xs mt-1">{errors.pricing_monthly}</p>
                            )}
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Trial Period (days)
                            </label>
                            <input
                              type="number"
                              min="0"
                              value={publishConfig.pricing_config.trial_period_days}
                              onChange={(e) => setPublishConfig(prev => ({
                                ...prev,
                                pricing_config: { ...prev.pricing_config, trial_period_days: parseInt(e.target.value) || 0 }
                              }))}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                              placeholder="14"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Minimum Users
                            </label>
                            <input
                              type="number"
                              min="1"
                              value={publishConfig.pricing_config.minimum_users}
                              onChange={(e) => setPublishConfig(prev => ({
                                ...prev,
                                pricing_config: { ...prev.pricing_config, minimum_users: parseInt(e.target.value) || 1 }
                              }))}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                              placeholder="1"
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Pricing Configuration - Per Execution */}
                    {publishConfig.billing_preference === 'per_execution' && (
                      <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
                        <h5 className="text-sm font-medium text-green-900 mb-3">Usage-Based Pricing</h5>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Price per Execution ($) *
                            </label>
                            <input
                              type="number"
                              step="0.001"
                              min="0"
                              value={publishConfig.pricing_config.price_per_execution}
                              onChange={(e) => setPublishConfig(prev => ({
                                ...prev,
                                pricing_config: { ...prev.pricing_config, price_per_execution: parseFloat(e.target.value) || 0 }
                              }))}
                              className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 text-sm ${
                                errors.pricing_execution ? 'border-red-500' : 'border-gray-300'
                              }`}
                              placeholder="0.01"
                            />
                            {errors.pricing_execution && (
                              <p className="text-red-500 text-xs mt-1">{errors.pricing_execution}</p>
                            )}
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Free Executions/Month
                            </label>
                            <input
                              type="number"
                              min="0"
                              value={publishConfig.pricing_config.free_executions_per_month}
                              onChange={(e) => setPublishConfig(prev => ({
                                ...prev,
                                pricing_config: { ...prev.pricing_config, free_executions_per_month: parseInt(e.target.value) || 0 }
                              }))}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 text-sm"
                              placeholder="100"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">
                              Minimum Charge ($)
                            </label>
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              value={publishConfig.pricing_config.minimum_charge}
                              onChange={(e) => setPublishConfig(prev => ({
                                ...prev,
                                pricing_config: { ...prev.pricing_config, minimum_charge: parseFloat(e.target.value) || 0 }
                              }))}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-green-500 text-sm"
                              placeholder="1.00"
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Usage Limits */}
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                      <h5 className="text-sm font-medium text-yellow-900 mb-3">Usage Limits (Optional)</h5>
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Max Executions/Day
                          </label>
                          <input
                            type="number"
                            min="0"
                            value={publishConfig.usage_limits.max_executions_per_day || ''}
                            onChange={(e) => setPublishConfig(prev => ({
                              ...prev,
                              usage_limits: { ...prev.usage_limits, max_executions_per_day: e.target.value ? parseInt(e.target.value) : null }
                            }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500 text-sm"
                            placeholder="Unlimited"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Max Executions/Month
                          </label>
                          <input
                            type="number"
                            min="0"
                            value={publishConfig.usage_limits.max_executions_per_month || ''}
                            onChange={(e) => setPublishConfig(prev => ({
                              ...prev,
                              usage_limits: { ...prev.usage_limits, max_executions_per_month: e.target.value ? parseInt(e.target.value) : null }
                            }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500 text-sm"
                            placeholder="Unlimited"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">
                            Max Users
                          </label>
                          <input
                            type="number"
                            min="0"
                            value={publishConfig.usage_limits.max_users || ''}
                            onChange={(e) => setPublishConfig(prev => ({
                              ...prev,
                              usage_limits: { ...prev.usage_limits, max_users: e.target.value ? parseInt(e.target.value) : null }
                            }))}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-yellow-500 text-sm"
                            placeholder="Unlimited"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Rate Limit */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Rate Limit (per hour)
                      </label>
                      <input
                        type="number"
                        value={publishConfig.frontend_config.rate_limit_per_hour}
                        onChange={(e) => setPublishConfig(prev => ({
                          ...prev,
                          frontend_config: {
                            ...prev.frontend_config,
                            rate_limit_per_hour: parseInt(e.target.value) || 100
                          }
                        }))}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        min="1"
                        max="10000"
                        placeholder="100"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Maximum number of executions allowed per hour per user
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Reusable Application Configuration (only show if not frontend-only) */}
              {publishConfig.publish_type !== 'frontend' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Application Key *
                  </label>
                  <input
                    type="text"
                    value={publishConfig.app_key}
                    onChange={(e) => setPublishConfig(prev => ({ 
                      ...prev, 
                      app_key: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') 
                    }))}
                    className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.app_key ? 'border-red-500' : 'border-gray-300'
                    }`}
                    placeholder="my_custom_app"
                  />
                  {errors.app_key && (
                    <p className="text-red-500 text-xs mt-1">{errors.app_key}</p>
                  )}
                  <p className="text-gray-500 text-xs mt-1">
                    Unique identifier (lowercase, numbers, underscores only)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Application Name *
                  </label>
                  <input
                    type="text"
                    value={publishConfig.app_name}
                    onChange={(e) => setPublishConfig(prev => ({ 
                      ...prev, 
                      app_name: e.target.value 
                    }))}
                    className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.app_name ? 'border-red-500' : 'border-gray-300'
                    }`}
                    placeholder="My Custom Application"
                  />
                  {errors.app_name && (
                    <p className="text-red-500 text-xs mt-1">{errors.app_name}</p>
                  )}
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Description *
                  </label>
                  <textarea
                    value={publishConfig.description}
                    onChange={(e) => setPublishConfig(prev => ({ 
                      ...prev, 
                      description: e.target.value 
                    }))}
                    rows={3}
                    className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      errors.description ? 'border-red-500' : 'border-gray-300'
                    }`}
                    placeholder="Describe what this application does..."
                  />
                  {errors.description && (
                    <p className="text-red-500 text-xs mt-1">{errors.description}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Category
                  </label>
                  <select
                    value={publishConfig.category}
                    onChange={(e) => setPublishConfig(prev => ({ 
                      ...prev, 
                      category: e.target.value 
                    }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="Flow Applications">Flow Applications</option>
                    <option value="Data Processing">Data Processing</option>
                    <option value="Communication">Communication</option>
                    <option value="Business Logic">Business Logic</option>
                    <option value="Integration">Integration</option>
                    <option value="Utilities">Utilities</option>
                    <option value="Custom">Custom</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Application Scope *
                  </label>
                  <select
                    value={publishConfig.app_scope}
                    onChange={(e) => setPublishConfig(prev => ({ 
                      ...prev, 
                      app_scope: e.target.value 
                    }))}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="global">Global - Available to all tenants</option>
                    <option value="tenant">Tenant - Available only within your tenant</option>
                    <option value="user">User - Private to you only</option>
                  </select>
                  <p className="text-gray-500 text-xs mt-1">
                    Defines who can use this application
                  </p>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="auto_update"
                    checked={publishConfig.auto_update}
                    onChange={(e) => setPublishConfig(prev => ({ 
                      ...prev, 
                      auto_update: e.target.checked 
                    }))}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                  />
                  <label htmlFor="auto_update" className="ml-2 block text-sm text-gray-700">
                    Auto-update when source flow changes
                  </label>
                </div>
              </div>
              )}
            </div>
          )}

          {step === 2 && (publishConfig.publish_type === 'frontend' || publishConfig.publish_type === 'both') && (
            <div className="space-y-6">
              <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <ShieldCheckIcon className="w-5 h-5 text-indigo-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="font-medium text-indigo-900">Access Control & Permissions</h3>
                    <p className="text-indigo-700 text-sm mt-1">
                      Define who can access and execute your frontend application. This ensures proper security and access management.
                    </p>
                  </div>
                </div>
              </div>

              {/* Access Type Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Who can access this application? *
                </label>
                
                <div className="space-y-3">
                  <div className="flex items-center">
                    <input
                      type="radio"
                      id="public_url_modal"
                      name="access_type"
                      value="public_url"
                      checked={publishConfig.frontend_config.access_type === 'public_url'}
                      onChange={(e) => setPublishConfig(prev => ({
                        ...prev,
                        frontend_config: {
                          ...prev.frontend_config,
                          access_type: e.target.value
                        }
                      }))}
                      className="h-4 w-4 text-blue-600"
                    />
                    <label htmlFor="public_url_modal" className="ml-3 flex items-center">
                      <GlobeAltIcon className="w-5 h-5 text-gray-400 mr-2" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">Anyone with URL</div>
                        <div className="text-xs text-gray-500">Public access, no authentication required</div>
                      </div>
                    </label>
                  </div>

                  <div className="flex items-center">
                    <input
                      type="radio"
                      id="organization_modal"
                      name="access_type"
                      value="organization"
                      checked={publishConfig.frontend_config.access_type === 'organization'}
                      onChange={(e) => setPublishConfig(prev => ({
                        ...prev,
                        frontend_config: {
                          ...prev.frontend_config,
                          access_type: e.target.value
                        }
                      }))}
                      className="h-4 w-4 text-blue-600"
                    />
                    <label htmlFor="organization_modal" className="ml-3 flex items-center">
                      <BuildingOfficeIcon className="w-5 h-5 text-gray-400 mr-2" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">My Organization</div>
                        <div className="text-xs text-gray-500">Only users from your organization</div>
                      </div>
                    </label>
                  </div>

                  <div className="flex items-center">
                    <input
                      type="radio"
                      id="specific_users_modal"
                      name="access_type"
                      value="specific_users"
                      checked={publishConfig.frontend_config.access_type === 'specific_users'}
                      onChange={(e) => setPublishConfig(prev => ({
                        ...prev,
                        frontend_config: {
                          ...prev.frontend_config,
                          access_type: e.target.value
                        }
                      }))}
                      className="h-4 w-4 text-blue-600"
                    />
                    <label htmlFor="specific_users_modal" className="ml-3 flex items-center">
                      <UserIcon className="w-5 h-5 text-gray-400 mr-2" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">Specific Users</div>
                        <div className="text-xs text-gray-500">Only designated IOFlow users</div>
                      </div>
                    </label>
                  </div>

                  <div className="flex items-center">
                    <input
                      type="radio"
                      id="tenant_list_modal"
                      name="access_type"
                      value="tenant_list"
                      checked={publishConfig.frontend_config.access_type === 'tenant_list'}
                      onChange={(e) => setPublishConfig(prev => ({
                        ...prev,
                        frontend_config: {
                          ...prev.frontend_config,
                          access_type: e.target.value
                        }
                      }))}
                      className="h-4 w-4 text-blue-600"
                    />
                    <label htmlFor="tenant_list_modal" className="ml-3 flex items-center">
                      <UserGroupIcon className="w-5 h-5 text-gray-400 mr-2" />
                      <div>
                        <div className="text-sm font-medium text-gray-900">Specific Organizations</div>
                        <div className="text-xs text-gray-500">Users from designated organizations</div>
                      </div>
                    </label>
                  </div>
                </div>

                <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
                  <div className="flex">
                    <InformationCircleIcon className="w-5 h-5 text-blue-400 mr-2 flex-shrink-0 mt-0.5" />
                    <p className="text-sm text-blue-800">
                      {getAccessTypeDescription()}
                    </p>
                  </div>
                </div>

                {errors.frontend_access_type && (
                  <p className="text-red-500 text-xs mt-1">{errors.frontend_access_type}</p>
                )}
              </div>

              {/* Specific Users Configuration */}
              {publishConfig.frontend_config.access_type === 'specific_users' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Allowed Users (Email addresses or User IDs) *
                  </label>
                  
                  <div className="flex mb-3">
                    <input
                      type="text"
                      value={newUser}
                      onChange={(e) => setNewUser(e.target.value)}
                      placeholder="user@example.com"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addUser())}
                    />
                    <button
                      type="button"
                      onClick={addUser}
                      className="px-3 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700"
                    >
                      <PlusIcon className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {publishConfig.frontend_config.access_config.allowed_users.map((user, index) => (
                      <div key={index} className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-md">
                        <span className="text-sm text-gray-900">{user}</span>
                        <button
                          type="button"
                          onClick={() => removeUser(index)}
                          className="text-red-600 hover:text-red-800"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>

                  {errors.frontend_allowed_users && (
                    <p className="text-red-500 text-xs mt-1">{errors.frontend_allowed_users}</p>
                  )}
                </div>
              )}

              {/* Tenant List Configuration */}
              {publishConfig.frontend_config.access_type === 'tenant_list' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Allowed Organizations (Tenant IDs or Names) *
                  </label>
                  
                  <div className="flex mb-3">
                    <input
                      type="text"
                      value={newTenant}
                      onChange={(e) => setNewTenant(e.target.value)}
                      placeholder="organization-id"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTenant())}
                    />
                    <button
                      type="button"
                      onClick={addTenant}
                      className="px-3 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700"
                    >
                      <PlusIcon className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="space-y-2 max-h-32 overflow-y-auto">
                    {publishConfig.frontend_config.access_config.allowed_tenants.map((tenant, index) => (
                      <div key={index} className="flex items-center justify-between bg-gray-50 px-3 py-2 rounded-md">
                        <span className="text-sm text-gray-900">{tenant}</span>
                        <button
                          type="button"
                          onClick={() => removeTenant(index)}
                          className="text-red-600 hover:text-red-800"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>

                  {errors.frontend_allowed_tenants && (
                    <p className="text-red-500 text-xs mt-1">{errors.frontend_allowed_tenants}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {step === 3 && preview && (
            <div className="space-y-6">
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-start space-x-3">
                  <CheckCircleIcon className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h3 className="font-medium text-green-900">Preview Generated Successfully</h3>
                    <p className="text-green-700 text-sm mt-1">
                      Review the application that will be created from your flow.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
                    <CogIcon className="w-5 h-5 mr-2" />
                    Application Details
                  </h3>
                  
                  <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                    <div>
                      <span className="text-sm font-medium text-gray-600">Name:</span>
                      <p className="text-sm text-gray-900">{preview.application?.app_name}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-600">Key:</span>
                      <p className="text-sm text-gray-900 font-mono">{preview.application?.app_key}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-600">Type:</span>
                      <p className="text-sm text-gray-900">{preview.application?.app_type}</p>
                    </div>
                    <div>
                      <span className="text-sm font-medium text-gray-600">Category:</span>
                      <p className="text-sm text-gray-900">{preview.application?.category}</p>
                    </div>
                  </div>

                  <h4 className="text-md font-medium text-gray-900 mt-6 mb-3">Flow Analysis</h4>
                  <div className="bg-blue-50 rounded-lg p-4 space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Input Parameters:</span>
                      <span className="text-sm font-medium">{preview.analysis?.input_parameters?.length || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Transformations:</span>
                      <span className="text-sm font-medium">{preview.analysis?.transformations?.length || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Dependencies:</span>
                      <span className="text-sm font-medium">{preview.analysis?.dependencies?.length || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Complexity Score:</span>
                      <span className="text-sm font-medium">{preview.analysis?.complexity_score || 0}</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-medium text-gray-900 mb-4 flex items-center">
                    <DocumentTextIcon className="w-5 h-5 mr-2" />
                    Generated Services
                  </h3>
                  
                  <div className="space-y-3">
                    {preview.services?.map((service, index) => (
                      <div key={index} className="bg-gray-50 rounded-lg p-4">
                        <h4 className="font-medium text-gray-900">{service.service_name}</h4>
                        <p className="text-sm text-gray-600 mt-1">{service.description}</p>
                        <div className="mt-2 text-xs text-gray-500">
                          <span className="inline-block bg-gray-200 rounded px-2 py-1 mr-2">
                            {service.service_type}
                          </span>
                          {service.parameters && (
                            <span className="inline-block bg-blue-100 text-blue-800 rounded px-2 py-1">
                              {service.parameters.length} parameters
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>

                  {preview.parameter_mappings && preview.parameter_mappings.length > 0 && (
                    <>
                      <h4 className="text-md font-medium text-gray-900 mt-6 mb-3">Parameter Mappings</h4>
                      <div className="space-y-2">
                        {preview.parameter_mappings.slice(0, 5).map((mapping, index) => (
                          <div key={index} className="bg-yellow-50 rounded p-3 text-sm">
                            <span className="font-mono text-gray-800">{mapping.flow_variable_path}</span>
                            <span className="text-gray-500 mx-2">→</span>
                            <span className="font-mono text-gray-800">{mapping.service_parameter_name}</span>
                          </div>
                        ))}
                        {preview.parameter_mappings.length > 5 && (
                          <p className="text-xs text-gray-500">
                            ... and {preview.parameter_mappings.length - 5} more mappings
                          </p>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Publishing Flow...</h3>
              <p className="text-gray-600">
                Creating application, generating services, and setting up parameter mappings.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            {step === 1 && "Configure your application settings"}
            {step === 2 && (publishConfig.publish_type === 'frontend' || publishConfig.publish_type === 'both') && "Define access permissions"}
            {step === 3 && "Review the generated application"}
            {step === 4 && "Publishing in progress..."}
          </div>
          
          <div className="flex items-center space-x-3">
            {step === 1 && (
              <>
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
                  disabled={isLoading}
                >
                  Cancel
                </button>
                <button
                  onClick={publishConfig.publish_type === 'reusable' ? handlePreview : handleNext}
                  disabled={isLoading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center"
                >
                  {isLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      {publishConfig.publish_type === 'reusable' ? 'Generating Preview...' : 'Validating...'}
                    </>
                  ) : (
                    <>
                      {publishConfig.publish_type === 'reusable' ? 'Preview' : 'Next: Permissions'}
                      <ArrowRightIcon className="w-4 h-4 ml-2" />
                    </>
                  )}
                </button>
              </>
            )}
            
            {step === 2 && (publishConfig.publish_type === 'frontend' || publishConfig.publish_type === 'both') && (
              <>
                <button
                  onClick={() => setStep(1)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
                  disabled={isLoading}
                >
                  Back
                </button>
                <button
                  onClick={handlePreview}
                  disabled={isLoading}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center"
                >
                  {isLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Generating Preview...
                    </>
                  ) : (
                    <>
                      Next: Preview
                      <ArrowRightIcon className="w-4 h-4 ml-2" />
                    </>
                  )}
                </button>
              </>
            )}

            {step === 3 && (
              <>
                <button
                  onClick={() => setStep(publishConfig.publish_type === 'reusable' ? 1 : 2)}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
                  disabled={isLoading}
                >
                  Back
                </button>
                <button
                  onClick={handlePublish}
                  disabled={isLoading}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 flex items-center"
                >
                  {isLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      Publishing...
                    </>
                  ) : (
                    <>
                      <ShareIcon className="w-4 h-4 mr-2" />
                      Publish Application
                    </>
                  )}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default FlowPublishingModal;