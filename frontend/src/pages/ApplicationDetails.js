import React, { useState, useEffect, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../utils/customToast';
import { getFullErrorMessage } from '../utils/errorHandler';
import { useAuth } from '../contexts/AuthContext';
import ParameterForm from '../components/flow/ParameterForm';
import {
  ArrowLeftIcon,
  PlusIcon,
  PencilIcon,
  TrashIcon,
  BoltIcon,
  CalendarIcon,
  LinkIcon,
  KeyIcon,
  CloudArrowUpIcon,
  DocumentDuplicateIcon,
  ExclamationTriangleIcon,
  CodeBracketIcon,
  CheckCircleIcon,
  XCircleIcon,
  CogIcon,
  InformationCircleIcon,
  CurrencyDollarIcon,
} from '@heroicons/react/24/outline';
import SchemaBuilder from '../components/parameters/SchemaBuilder';
import { buildNestedSchema, generateSampleFromSchema } from '../utils/schemaUtils';
import CodeBlock from '../components/CodeBlock';
import ServiceTypeConfig from '../components/applications/ServiceTypeConfig';
import AuthConfigModal from '../components/applications/AuthConfigModal';
import WebhookConfigModal from '../components/applications/WebhookConfigModal';
import ServiceDetailModal from '../components/applications/ServiceDetailModal';
import PricingConfiguration from '../components/applications/PricingConfiguration';

const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;

// Helper function to get display name for service types
const getServiceTypeDisplay = (type) => {
  const typeMap = {
    'api_call': 'API Call',
    'graphql': 'GraphQL',
    'webhook': 'Webhook',
    'email_send': 'Email Send',
    'smtp_send': 'SMTP Send',
    'pop3_receive': 'POP3 Receive',
    'imap_receive': 'IMAP Receive',
    'llm_api_call': 'LLM API Call',
    'mcp_call': 'MCP Call',
    'database_query': 'Database Query',
    'action': 'Action',
    'search': 'Search',
    'create': 'Create',
    'update': 'Update',
    'delete': 'Delete',
    'custom': 'Custom'
  };
  return typeMap[type] || type;
};

function ApplicationDetails() {
  const { appId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  const [activeTab, setActiveTab] = useState('overview');
  const [showEventModal, setShowEventModal] = useState(false);
  const [showAuthConfigModal, setShowAuthConfigModal] = useState(false);
  const [showWebhookConfigModal, setShowWebhookConfigModal] = useState(false);
  const [showPricingModal, setShowPricingModal] = useState(false);
  
  // Get user from auth context
  const { user } = useAuth();
  const isAdmin = user?.role === 'INSTANCE_ADMIN';
  
  // Refresh function for development
  const refreshApplicationData = () => {
    queryClient.invalidateQueries(['application', appId]);
    queryClient.invalidateQueries(['application-events', appId]);
    queryClient.invalidateQueries(['application-services', appId]);
    showSuccessToast('Data refreshed');
  };
  const [showServiceModal, setShowServiceModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState(null);
  const [editingService, setEditingService] = useState(null);
  const [scopeDraft, setScopeDraft] = useState(null); // { app_scope, tenant_id_owner } when editing scope
  const [showSampleCodeModal, setShowSampleCodeModal] = useState(false);
  const [selectedEventForCode, setSelectedEventForCode] = useState(null);
  const [showServiceDetailModal, setShowServiceDetailModal] = useState(false);
  const [selectedServiceForDetail, setSelectedServiceForDetail] = useState(null);

  // Fetch application details
  const { data: application, isLoading } = useQuery({
    queryKey: ['application', appId],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/${appId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
  });

  // Fetch events
  const { data: events = [], isError: eventsError, error: eventsErrorDetails } = useQuery({
    queryKey: ['application-events', appId],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/${appId}/events`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to load events');
      showErrorToast(errorMessage);
      console.error('Failed to fetch events:', error);
    },
  });

  // Fetch services
  const { data: services = [], isError: servicesError, error: servicesErrorDetails } = useQuery({
    queryKey: ['application-services', appId],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/${appId}/services`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      // Debug headers_template for GSTIN service
      const gstin = response.data.find(s => s.service_name === 'GSTIN Verification');
      if (gstin) {
        console.log('GSTIN Service headers_template:', gstin.headers_template);
        console.log('Full GSTIN service:', gstin);
      }
      return response.data;
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to load services');
      showErrorToast(errorMessage);
      console.error('Failed to fetch services:', error);
    },
  });

  // Fetch subscription for API key
  const { data: subscription } = useQuery({
    queryKey: ['application-subscription', appId],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/subscriptions/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      // Find subscription for this app
      const foundSubscription = response.data.find(sub => sub.app_id === appId);
      // Return null instead of undefined if not found
      return foundSubscription || null;
    },
  });

  // Fetch tenants (admin only) - used as owner options when scoping an app to a tenant
  const { data: tenants = [] } = useQuery({
    queryKey: ['tenants'],
    enabled: isAdmin,
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/tenants/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      return response.data;
    },
  });

  // Update application scope/owner mutation (admin only)
  const scopeMutation = useMutation({
    mutationFn: async ({ app_scope, tenant_id_owner }) => {
      const token = localStorage.getItem('access_token');
      const payload = { app_scope };
      // Only send an owner when scoping to a tenant; backend clears it for global.
      if (app_scope === 'tenant') {
        payload.tenant_id_owner = tenant_id_owner;
      }
      return axios.put(
        `${API_BASE_URL}/api/v1/applications/${appId}`,
        payload,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['application', appId]);
      showSuccessToast('Application scope updated successfully');
      setScopeDraft(null);
    },
    onError: (error) => {
      showErrorToast(getFullErrorMessage(error, 'Failed to update application scope'));
    },
  });

  // Create/Update event mutation
  const eventMutation = useMutation({
    mutationFn: async (eventData) => {
      const token = localStorage.getItem('access_token');
      if (editingEvent) {
        return axios.put(
          `${API_BASE_URL}/api/v1/applications/${appId}/events/${editingEvent.event_id}`,
          eventData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else {
        return axios.post(
          `${API_BASE_URL}/api/v1/applications/${appId}/events`,
          eventData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['application-events', appId]);
      showSuccessToast(editingEvent ? 'Event updated successfully' : 'Event created successfully');
      setShowEventModal(false);
      setEditingEvent(null);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to save event');
      showErrorToast(errorMessage);
    },
  });

  // Create/Update service mutation
  const serviceMutation = useMutation({
    mutationFn: async (serviceData) => {
      const token = localStorage.getItem('access_token');
      if (editingService) {
        return axios.put(
          `${API_BASE_URL}/api/v1/applications/${appId}/services/${editingService.service_id}`,
          serviceData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else {
        return axios.post(
          `${API_BASE_URL}/api/v1/applications/${appId}/services`,
          serviceData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['application-services', appId]);
      showSuccessToast(editingService ? 'Service updated successfully' : 'Service created successfully');
      setShowServiceModal(false);
      setEditingService(null);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to save service');
      showErrorToast(errorMessage);
    },
  });

  // Delete event mutation
  const deleteEventMutation = useMutation({
    mutationFn: async (eventId) => {
      const token = localStorage.getItem('access_token');
      return axios.delete(
        `${API_BASE_URL}/api/v1/applications/${appId}/events/${eventId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['application-events', appId]);
      showSuccessToast('Event deleted successfully');
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to delete event');
      showErrorToast(errorMessage);
    },
  });

  // Delete service mutation
  const deleteServiceMutation = useMutation({
    mutationFn: async (serviceId) => {
      const token = localStorage.getItem('access_token');
      return axios.delete(
        `${API_BASE_URL}/api/v1/applications/${appId}/services/${serviceId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['application-services', appId]);
      showSuccessToast('Service deleted successfully');
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to delete service');
      showErrorToast(errorMessage);
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (!application) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Application not found</p>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', name: 'Overview', count: null },
    { id: 'events', name: 'Incoming Events', count: events.length },
    { id: 'services', name: 'Outgoing Services', count: services.length },
    { id: 'advanced', name: 'Advanced', count: null },
    { id: 'settings', name: 'Settings', count: null },
  ];

  return (
    <div className="py-6">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8">
          <Link
            to="/applications"
            className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
          >
            <ArrowLeftIcon className="w-4 h-4 mr-1" />
            Back to Applications
          </Link>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-16 h-16 rounded-lg bg-gray-100 flex items-center justify-center">
                {application.icon_url ? (
                  <img src={application.icon_url} alt={application.app_name} className="w-12 h-12" />
                ) : (
                  <BoltIcon className="w-8 h-8 text-gray-400" />
                )}
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">{application.app_name}</h1>
                <p className="text-sm text-gray-500">{application.category} · v{application.version}</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
                application.app_scope === 'global'
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-green-100 text-green-800'
              }`}>
                {application.app_scope || application.app_type}
              </span>
              <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
                application.is_active 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-gray-100 text-gray-800'
              }`}>
                {application.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200 mb-8">
          <nav className="-mb-px flex space-x-8">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.name}
                {tab.count !== null && (
                  <span className="ml-2 bg-gray-100 text-gray-900 py-0.5 px-2.5 rounded-full text-xs">
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Application Details</h3>
              <dl className="space-y-3">
                <div>
                  <dt className="text-sm font-medium text-gray-500">Description</dt>
                  <dd className="mt-1 text-sm text-gray-900">{application.description || 'No description'}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Base URL</dt>
                  <dd className="mt-1 text-sm text-gray-900 font-mono">{application.base_url || 'N/A'}</dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Authentication Type</dt>
                  <dd className="mt-1 flex items-center justify-between">
                    <span className="text-sm text-gray-900">{application.auth_type}</span>
                    <button
                      onClick={() => setShowAuthConfigModal(true)}
                      className="inline-flex items-center px-2 py-1 text-xs font-medium text-primary bg-primary-10 rounded-md hover:bg-primary-20"
                    >
                      <KeyIcon className="w-3 h-3 mr-1" />
                      Configure
                    </button>
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Pricing & Billing</dt>
                  <dd className="mt-1 flex items-center justify-between">
                    <span className="text-sm text-gray-900">Pay-per-use</span>
                    <button
                      onClick={() => setShowPricingModal(true)}
                      className="inline-flex items-center px-2 py-1 text-xs font-medium text-primary bg-primary-10 rounded-md hover:bg-primary-20"
                    >
                      <CurrencyDollarIcon className="w-3 h-3 mr-1" />
                      Configure
                    </button>
                  </dd>
                </div>
                <div>
                  <dt className="text-sm font-medium text-gray-500">Created By</dt>
                  <dd className="mt-1 text-sm text-gray-900">{application.created_by || 'System'}</dd>
                </div>
              </dl>
            </div>

            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Statistics</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-gray-900">{events.length}</div>
                  <div className="text-sm text-gray-500">Incoming Events</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-gray-900">{services.length}</div>
                  <div className="text-sm text-gray-500">Outgoing Services</div>
                </div>
              </div>
            </div>

            {/* Subscription Configuration */}
            {subscription && (
              <div className="bg-white shadow rounded-lg p-6 lg:col-span-2">
                <div className="flex justify-between items-center mb-4">
                  <h3 className="text-lg font-medium text-gray-900">Connection Configuration</h3>
                  <button
                    onClick={() => setShowAuthConfigModal(true)}
                    className="inline-flex items-center px-3 py-1 text-xs font-medium text-primary bg-primary-10 rounded-md hover:bg-primary-20"
                  >
                    <CogIcon className="w-3 h-3 mr-1" />
                    Edit Settings
                  </button>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Connection Status */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Connection Status</h4>
                    <dl className="space-y-2">
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Status</dt>
                        <dd className="mt-1">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            subscription.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                          }`}>
                            {subscription.status}
                          </span>
                        </dd>
                      </div>
                      {subscription.api_key_created_at && (
                        <div>
                          <dt className="text-xs font-medium text-gray-500">API Key Created</dt>
                          <dd className="mt-1 text-xs text-gray-900">
                            {new Date(subscription.api_key_created_at).toLocaleDateString()}
                          </dd>
                        </div>
                      )}
                    </dl>
                  </div>

                  {/* Custom Parameters */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Custom API Parameters</h4>
                    {(() => {
                      const subConfig = subscription.subscription_config || {};
                      const customParams = subConfig.custom_params || {};
                      const hasCustomParams = Object.keys(customParams).some(type => 
                        customParams[type] && Object.keys(customParams[type]).length > 0
                      );

                      if (!hasCustomParams) {
                        return <p className="text-xs text-gray-500">No custom parameters configured</p>;
                      }

                      return (
                        <div className="space-y-3">
                          {/* Headers */}
                          {customParams.header && Object.keys(customParams.header).length > 0 && (
                            <div>
                              <h5 className="text-xs font-medium text-gray-600 mb-1">Headers</h5>
                              <div className="bg-gray-50 rounded p-2 space-y-1">
                                {Object.entries(customParams.header).map(([key, value]) => (
                                  <div key={key} className="flex justify-between text-xs">
                                    <span className="font-mono text-gray-700">{key}:</span>
                                    <span className="font-mono text-gray-900">{value}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Query Parameters */}
                          {customParams.query && Object.keys(customParams.query).length > 0 && (
                            <div>
                              <h5 className="text-xs font-medium text-gray-600 mb-1">Query Parameters</h5>
                              <div className="bg-gray-50 rounded p-2 space-y-1">
                                {Object.entries(customParams.query).map(([key, value]) => (
                                  <div key={key} className="flex justify-between text-xs">
                                    <span className="font-mono text-gray-700">{key}:</span>
                                    <span className="font-mono text-gray-900">{value}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Body Parameters */}
                          {customParams.body && Object.keys(customParams.body).length > 0 && (
                            <div>
                              <h5 className="text-xs font-medium text-gray-600 mb-1">Body Parameters</h5>
                              <div className="bg-gray-50 rounded p-2 space-y-1">
                                {Object.entries(customParams.body).map(([key, value]) => (
                                  <div key={key} className="flex justify-between text-xs">
                                    <span className="font-mono text-gray-700">{key}:</span>
                                    <span className="font-mono text-gray-900">{value}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                </div>

                {/* Additional Auth Fields */}
                {application.auth_config?.additional_fields && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Additional Authentication Fields</h4>
                    <p className="text-xs text-gray-600 mb-2">These fields are automatically extracted from authentication responses:</p>
                    <div className="bg-gray-50 rounded p-3">
                      {Object.entries(application.auth_config.additional_fields).map(([fieldName, fieldPath]) => (
                        <div key={fieldName} className="flex justify-between text-xs mb-1">
                          <span className="font-medium text-gray-700">{fieldName}:</span>
                          <span className="font-mono text-gray-600">{fieldPath}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Webhook Configuration Details */}
            {application.webhook_config && (() => {
              // Parse webhook_config if it's a JSON string
              const webhookConfig = typeof application.webhook_config === 'string' 
                ? JSON.parse(application.webhook_config) 
                : application.webhook_config;
              
              return (
                <div className="bg-white shadow rounded-lg p-6 lg:col-span-2">
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Webhook Configuration</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Verification Method</h4>
                      <dl className="space-y-2">
                        <div>
                          <dt className="text-xs font-medium text-gray-500">Method</dt>
                          <dd className="mt-1 text-xs text-gray-900 font-mono">
                            {webhookConfig.verification_method || 'none'}
                          </dd>
                        </div>
                        {webhookConfig.signature_header && (
                          <div>
                            <dt className="text-xs font-medium text-gray-500">Signature Header</dt>
                            <dd className="mt-1 text-xs text-gray-900 font-mono">{webhookConfig.signature_header}</dd>
                          </div>
                        )}
                        {webhookConfig.signature_algorithm && (
                          <div>
                            <dt className="text-xs font-medium text-gray-500">Algorithm</dt>
                            <dd className="mt-1 text-xs text-gray-900 font-mono">{webhookConfig.signature_algorithm}</dd>
                          </div>
                        )}
                      </dl>
                    </div>
                    
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Security Settings</h4>
                      <dl className="space-y-2">
                        {webhookConfig.timestamp_header && (
                          <div>
                            <dt className="text-xs font-medium text-gray-500">Timestamp Header</dt>
                            <dd className="mt-1 text-xs text-gray-900 font-mono">{webhookConfig.timestamp_header}</dd>
                          </div>
                        )}
                        {webhookConfig.timestamp_tolerance && (
                          <div>
                            <dt className="text-xs font-medium text-gray-500">Timestamp Tolerance</dt>
                            <dd className="mt-1 text-xs text-gray-900">{webhookConfig.timestamp_tolerance} seconds</dd>
                          </div>
                        )}
                        <div>
                          <dt className="text-xs font-medium text-gray-500">Signing Secret Required</dt>
                          <dd className="mt-1 text-xs text-gray-900">{webhookConfig.signing_secret_required ? 'Yes' : 'No'}</dd>
                        </div>
                        <div>
                          <dt className="text-xs font-medium text-gray-500">URL Verification Enabled</dt>
                          <dd className="mt-1 text-xs text-gray-900">{webhookConfig.url_verification_enabled ? 'Yes' : 'No'}</dd>
                        </div>
                      </dl>
                    </div>
                  </div>
                  
                  {webhookConfig.events && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Supported Events</h4>
                      <div className="flex flex-wrap gap-2">
                        {webhookConfig.events.map((event, index) => (
                          <span key={index} className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-800">
                            {event}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}

            {/* OAuth2 Configuration Details */}
            {application.auth_type === 'oauth2' && application.auth_config && (
              <div className="bg-white shadow rounded-lg p-6 lg:col-span-2">
                <h3 className="text-lg font-medium text-gray-900 mb-4">OAuth2 Configuration</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Endpoints</h4>
                    <dl className="space-y-2">
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Authorization URL</dt>
                        <dd className="mt-1 text-xs text-gray-900 font-mono break-all">{application.auth_config.authorization_url || application.auth_config.auth_url || 'Not configured'}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Token URL</dt>
                        <dd className="mt-1 text-xs text-gray-900 font-mono break-all">{application.auth_config.token_url || 'Not configured'}</dd>
                      </div>
                    </dl>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Authorization Parameters</h4>
                    <dl className="space-y-2">
                      {application.auth_config.authorization_params ? (
                        <>
                          <div>
                            <dt className="text-xs font-medium text-gray-500">Access Type</dt>
                            <dd className="mt-1 text-xs text-gray-900">
                              {application.auth_config.authorization_params.access_type || 'Not set'}
                              {application.auth_config.authorization_params.access_type === 'offline' && (
                                <span className="ml-2 text-green-600">(✓ Refresh token enabled)</span>
                              )}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs font-medium text-gray-500">Prompt</dt>
                            <dd className="mt-1 text-xs text-gray-900">
                              {application.auth_config.authorization_params.prompt || 'Not set'}
                              {application.auth_config.authorization_params.prompt === 'consent' && (
                                <span className="ml-2 text-green-600">(✓ Forces consent screen)</span>
                              )}
                            </dd>
                          </div>
                          {Object.entries(application.auth_config.authorization_params).map(([key, value]) => {
                            if (key !== 'access_type' && key !== 'prompt') {
                              return (
                                <div key={key}>
                                  <dt className="text-xs font-medium text-gray-500">{key}</dt>
                                  <dd className="mt-1 text-xs text-gray-900">{String(value)}</dd>
                                </div>
                              );
                            }
                            return null;
                          })}
                        </>
                      ) : (
                        <dd className="text-xs text-gray-500">No authorization parameters configured</dd>
                      )}
                    </dl>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Scopes</h4>
                    <div className="mt-1">
                      {application.auth_config.scopes && application.auth_config.scopes.length > 0 ? (
                        <ul className="space-y-1">
                          {application.auth_config.scopes.map((scope, index) => (
                            <li key={index} className="text-xs text-gray-900 font-mono">{scope}</li>
                          ))}
                        </ul>
                      ) : (
                        <span className="text-xs text-gray-500">No default scopes configured</span>
                      )}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Settings</h4>
                    <dl className="space-y-2">
                      <div>
                        <dt className="text-xs font-medium text-gray-500">PKCE Required</dt>
                        <dd className="mt-1 text-xs text-gray-900">{application.auth_config.pkce_required ? 'Yes' : 'No'}</dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Grant Types</dt>
                        <dd className="mt-1 text-xs text-gray-900">
                          {application.auth_config.grant_types ? application.auth_config.grant_types.join(', ') : 'Not specified'}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Default OAuth Credentials</dt>
                        <dd className="mt-1 text-xs">
                          {application.auth_config.default_credentials?.client_id && application.auth_config.default_credentials?.client_secret ? (
                            <span className="text-green-600 font-medium">✓ Configured</span>
                          ) : (
                            <span className="text-gray-500">Not configured</span>
                          )}
                        </dd>
                      </div>
                    </dl>
                  </div>
                </div>
                
                {application.app_name === 'Google Sheets' && !application.auth_config.authorization_params?.access_type && (
                  <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
                    <p className="text-sm text-yellow-800">
                      <strong>Warning:</strong> OAuth2 configuration may not include refresh token parameters. 
                      Users might need to reconnect frequently.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'events' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-medium text-gray-900">Incoming Events</h3>
              <button
                onClick={() => {
                  setEditingEvent(null);
                  setShowEventModal(true);
                }}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              >
                <PlusIcon className="w-4 h-4 mr-2" />
                Add Event
              </button>
            </div>

            {eventsError && (
              <div className="mb-4 bg-red-50 border-l-4 border-red-400 p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-red-700">
                      Failed to load events: {getFullErrorMessage(eventsErrorDetails, 'Unknown error')}
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="bg-white shadow overflow-hidden sm:rounded-md">
              <ul className="divide-y divide-gray-200">
                {events.map((event) => (
                  <li key={event.event_id} className="px-6 py-4 hover:bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h4 className="text-sm font-medium text-gray-900">{event.display_name}</h4>
                        <p className="text-sm text-gray-500">{event.event_name}</p>
                        {event.description && (
                          <p className="text-xs text-gray-400 mt-1">{event.description}</p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => {
                            setSelectedEventForCode(event);
                            setShowSampleCodeModal(true);
                          }}
                          className="text-green-600 hover:text-green-900"
                          title="Generate Sample Code"
                        >
                          <CodeBracketIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingEvent(event);
                            setShowEventModal(true);
                          }}
                          className="text-primary hover:text-primary-dark"
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm('Are you sure you want to delete this event?')) {
                              deleteEventMutation.mutate(event.event_id);
                            }
                          }}
                          className="text-red-600 hover:text-red-900"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
                {events.length === 0 && (
                  <li className="px-6 py-12 text-center text-gray-500">
                    No events defined. Click "Add Event" to create one.
                  </li>
                )}
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'services' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-medium text-gray-900">Outgoing Services</h3>
              <button
                onClick={() => {
                  setEditingService(null);
                  setShowServiceModal(true);
                }}
                className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              >
                <PlusIcon className="w-4 h-4 mr-2" />
                Add Service
              </button>
            </div>

            {servicesError && (
              <div className="mb-4 bg-red-50 border-l-4 border-red-400 p-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
                  </div>
                  <div className="ml-3">
                    <p className="text-sm text-red-700">
                      Failed to load services: {getFullErrorMessage(servicesErrorDetails, 'Unknown error')}
                    </p>
                  </div>
                </div>
              </div>
            )}

            <div className="bg-white shadow overflow-hidden sm:rounded-md">
              <ul className="divide-y divide-gray-200">
                {services.map((service) => (
                  <li key={service.service_id} className="px-6 py-4 hover:bg-gray-50">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <h4 className="text-sm font-medium text-gray-900">{service.display_name}</h4>
                        <p className="text-sm text-gray-500">{service.service_name}</p>
                        {service.description && (
                          <p className="text-xs text-gray-400 mt-1">{service.description}</p>
                        )}
                        <div className="flex items-center space-x-3 mt-2 text-xs text-gray-500">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                            {getServiceTypeDisplay(service.service_type)}
                          </span>
                          {service.service_config?.request_config?.parameter_method && (
                            <span>Method: {service.service_config.request_config.parameter_method}</span>
                          )}
                          {service.service_config?.request_config?.method && (
                            <span>HTTP: {service.service_config.request_config.method}</span>
                          )}
                        </div>
                        {service.endpoint_template && (
                          <div className="mt-2 text-xs text-gray-500 font-mono bg-gray-50 p-2 rounded">
                            {service.endpoint_template}
                          </div>
                        )}
                        {(() => {
                          // Try to get parameters from various sources
                          const directParams = service.parameters || service.service_config?.parameters;
                          
                          // Parse input schema if it's a string
                          const inputSchema = service.input_schema ? (
                            typeof service.input_schema === 'string' 
                              ? JSON.parse(service.input_schema) 
                              : service.input_schema
                          ) : null;
                          
                          const allowsAdditional = inputSchema?.additionalProperties;
                          
                          if (directParams?.length > 0) {
                            return (
                              <div className="mt-2 text-xs text-gray-500">
                                <span className="font-medium">Parameters:</span>{' '}
                                {directParams.map(p => p.param_name || p.name).join(', ')}
                                {allowsAdditional && (
                                  <span className="italic">
                                    , + additional properties
                                  </span>
                                )}
                              </div>
                            );
                          }
                          
                          // Fallback to input_schema if no direct parameters
                          if (inputSchema?.properties) {
                            const schemaProps = Object.keys(inputSchema.properties);
                            
                            if (schemaProps.length > 0 || allowsAdditional) {
                              return (
                                <div className="mt-2 text-xs text-gray-500">
                                  <span className="font-medium">Parameters:</span>{' '}
                                  {schemaProps.join(', ')}
                                  {allowsAdditional && (
                                    <span className="italic">
                                      {schemaProps.length > 0 ? ', ' : ''}
                                      + additional properties
                                    </span>
                                  )}
                                </div>
                              );
                            }
                          }
                          
                          return null;
                        })()}
                      </div>
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => {
                            setSelectedServiceForDetail(service);
                            setShowServiceDetailModal(true);
                          }}
                          className="text-green-600 hover:text-green-900"
                          title="View Details"
                        >
                          <InformationCircleIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            setEditingService(service);
                            setShowServiceModal(true);
                          }}
                          className="text-primary hover:text-primary-dark"
                          title="Edit Service"
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => {
                            if (window.confirm('Are you sure you want to delete this service?')) {
                              deleteServiceMutation.mutate(service.service_id);
                            }
                          }}
                          className="text-red-600 hover:text-red-900"
                          title="Delete Service"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </li>
                ))}
                {services.length === 0 && (
                  <li className="px-6 py-12 text-center text-gray-500">
                    No services defined. Click "Add Service" to create one.
                  </li>
                )}
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="space-y-6">
            {/* General Settings */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">General Information</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">Application Type</label>
                  <p className="mt-1 text-sm text-gray-900">{application.app_type}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Version</label>
                  <p className="mt-1 text-sm text-gray-900">{application.version}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Status</label>
                  <p className="mt-1 text-sm text-gray-900">{application.is_active ? 'Active' : 'Inactive'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Category</label>
                  <p className="mt-1 text-sm text-gray-900">{application.category}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Created By</label>
                  <p className="mt-1 text-sm text-gray-900">{application.created_by || 'System'}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Base URL</label>
                  <p className="mt-1 text-sm text-gray-900 font-mono text-xs">{application.base_url || 'N/A'}</p>
                </div>
              </div>
            </div>

            {/* Scope & Visibility (Admin Only) */}
            {isAdmin && (
              <div className="bg-white shadow rounded-lg p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">Scope & Visibility</h3>
                    <p className="mt-1 text-sm text-gray-500">
                      Controls which tenants can see this application. Global apps are visible to all
                      tenants; tenant-scoped apps are visible only to their owning tenant.
                    </p>
                  </div>
                  {!scopeDraft && (
                    <button
                      onClick={() => setScopeDraft({
                        app_scope: application.app_scope || 'tenant',
                        tenant_id_owner: application.tenant_id_owner || '',
                      })}
                      className="inline-flex items-center px-3 py-1 text-xs font-medium text-primary bg-primary-10 rounded-md hover:bg-primary-20 whitespace-nowrap"
                    >
                      <PencilIcon className="w-3 h-3 mr-1" />
                      Change Scope
                    </button>
                  )}
                </div>

                {!scopeDraft ? (
                  <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Current Scope</dt>
                      <dd className="mt-1">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          application.app_scope === 'global'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {application.app_scope || 'tenant'}
                        </span>
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm font-medium text-gray-500">Owning Tenant</dt>
                      <dd className="mt-1 text-sm text-gray-900">
                        {application.app_scope === 'global'
                          ? 'All tenants (shared)'
                          : (tenants.find(t => t.tenant_id === application.tenant_id_owner)?.tenant_name
                              || application.tenant_id_owner
                              || 'Not assigned')}
                      </dd>
                    </div>
                  </dl>
                ) : (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Scope</label>
                        <select
                          value={scopeDraft.app_scope}
                          onChange={(e) => setScopeDraft({ ...scopeDraft, app_scope: e.target.value })}
                          className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary text-sm"
                        >
                          <option value="global">Global (visible to all tenants)</option>
                          <option value="tenant">Tenant (single owning tenant)</option>
                          <option value="user">User</option>
                        </select>
                      </div>
                      {scopeDraft.app_scope === 'tenant' && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Owning Tenant</label>
                          <select
                            value={scopeDraft.tenant_id_owner}
                            onChange={(e) => setScopeDraft({ ...scopeDraft, tenant_id_owner: e.target.value })}
                            className="w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary text-sm"
                          >
                            <option value="">Select a tenant…</option>
                            {tenants.map(t => (
                              <option key={t.tenant_id} value={t.tenant_id}>{t.tenant_name}</option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>
                    {scopeDraft.app_scope === 'global' && (
                      <div className="bg-blue-50 border border-blue-200 rounded-md p-3 text-sm text-blue-800">
                        Promoting to global makes this application visible to all tenants and marks it as a shared seed application.
                      </div>
                    )}
                    <div className="flex items-center space-x-3">
                      <button
                        onClick={() => scopeMutation.mutate(scopeDraft)}
                        disabled={scopeMutation.isPending || (scopeDraft.app_scope === 'tenant' && !scopeDraft.tenant_id_owner)}
                        className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {scopeMutation.isPending ? 'Saving…' : 'Save Scope'}
                      </button>
                      <button
                        onClick={() => setScopeDraft(null)}
                        disabled={scopeMutation.isPending}
                        className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-md text-gray-700 bg-gray-100 hover:bg-gray-200"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Incoming Configuration */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center">
                  <CloudArrowUpIcon className="w-5 h-5 text-gray-400 mr-2" />
                  <h3 className="text-lg font-medium text-gray-900">Incoming Configuration</h3>
                  <span className="ml-2 text-sm text-gray-500">(Events & Webhooks)</span>
                </div>
              </div>
              
              <div className="p-6 space-y-6">
                {/* Webhook Configuration */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-gray-900">Webhook Security</h4>
                    {isAdmin && (
                      <button
                        onClick={() => setShowWebhookConfigModal(true)}
                        className="inline-flex items-center px-2 py-1 text-xs font-medium text-primary bg-primary-10 rounded-md hover:bg-primary-20"
                      >
                        <PencilIcon className="w-3 h-3 mr-1" />
                        Edit
                      </button>
                    )}
                  </div>
                  
                  {application.webhook_config ? (
                    <div className="bg-gray-50 rounded-lg p-4">
                      {(() => {
                        const webhookConfig = typeof application.webhook_config === 'string' 
                          ? JSON.parse(application.webhook_config) 
                          : application.webhook_config;
                        
                        return (
                          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2">
                            <div>
                              <dt className="text-xs font-medium text-gray-500">Verification Method</dt>
                              <dd className="mt-1 text-sm text-gray-900">{webhookConfig.verification_method || 'none'}</dd>
                            </div>
                            {webhookConfig.signature_header && (
                              <div>
                                <dt className="text-xs font-medium text-gray-500">Signature Header</dt>
                                <dd className="mt-1 text-sm text-gray-900 font-mono">{webhookConfig.signature_header}</dd>
                              </div>
                            )}
                            {webhookConfig.signature_algorithm && (
                              <div>
                                <dt className="text-xs font-medium text-gray-500">Algorithm</dt>
                                <dd className="mt-1 text-sm text-gray-900">{webhookConfig.signature_algorithm}</dd>
                              </div>
                            )}
                            {webhookConfig.timestamp_tolerance && (
                              <div>
                                <dt className="text-xs font-medium text-gray-500">Timestamp Tolerance</dt>
                                <dd className="mt-1 text-sm text-gray-900">{webhookConfig.timestamp_tolerance}s</dd>
                              </div>
                            )}
                            <div>
                              <dt className="text-xs font-medium text-gray-500">Signing Secret Required</dt>
                              <dd className="mt-1 text-sm text-gray-900">{webhookConfig.signing_secret_required ? 'Yes' : 'No'}</dd>
                            </div>
                            <div>
                              <dt className="text-xs font-medium text-gray-500">URL Verification</dt>
                              <dd className="mt-1 text-sm text-gray-900">{webhookConfig.url_verification_enabled ? 'Enabled' : 'Disabled'}</dd>
                            </div>
                          </dl>
                        );
                      })()}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-500">No webhook configuration defined</p>
                  )}
                </div>

                {/* Event Triggers */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-gray-900">Event Triggers</h4>
                    <Link
                      to={`/applications/${appId}?tab=events`}
                      className="text-xs text-primary hover:text-secondary"
                    >
                      View all events →
                    </Link>
                  </div>
                  <p className="text-sm text-gray-500">
                    {events.length} event{events.length !== 1 ? 's' : ''} configured
                  </p>
                </div>
              </div>
            </div>

            {/* Outgoing Configuration */}
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center">
                  <LinkIcon className="w-5 h-5 text-gray-400 mr-2" />
                  <h3 className="text-lg font-medium text-gray-900">Outgoing Configuration</h3>
                  <span className="ml-2 text-sm text-gray-500">(Authentication & Services)</span>
                </div>
              </div>
              
              <div className="p-6 space-y-6">
                {/* Authentication Configuration */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-gray-900">Authentication</h4>
                    {isAdmin && (
                      <button
                        onClick={() => setShowAuthConfigModal(true)}
                        className="inline-flex items-center px-2 py-1 text-xs font-medium text-primary bg-primary-10 rounded-md hover:bg-primary-20"
                      >
                        <PencilIcon className="w-3 h-3 mr-1" />
                        Edit
                      </button>
                    )}
                  </div>
                  
                  <div className="bg-gray-50 rounded-lg p-4">
                    <dl className="space-y-2">
                      <div>
                        <dt className="text-xs font-medium text-gray-500">Type</dt>
                        <dd className="mt-1 text-sm text-gray-900">{application.auth_type || 'None'}</dd>
                      </div>
                      
                      {application.auth_type === 'oauth2' && application.auth_config && (
                        <>
                          <div>
                            <dt className="text-xs font-medium text-gray-500">OAuth URLs</dt>
                            <dd className="mt-1 text-xs text-gray-900 space-y-1">
                              <div>Authorization: {(application.auth_config.authorization_url || application.auth_config.auth_url) ? '✓' : '✗'}</div>
                              <div>Token: {application.auth_config.token_url ? '✓' : '✗'}</div>
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs font-medium text-gray-500">Features</dt>
                            <dd className="mt-1 text-xs text-gray-900 space-y-1">
                              <div>Refresh Token: {application.auth_config.authorization_params?.access_type === 'offline' ? '✓' : '✗'}</div>
                              <div>PKCE: {application.auth_config.pkce_required ? '✓' : '✗'}</div>
                              <div>Default Credentials: {application.auth_config.default_credentials?.client_id ? '✓' : '✗'}</div>
                            </dd>
                          </div>
                        </>
                      )}
                      
                      {application.auth_type === 'api_key' && application.auth_config && (
                        <div>
                          <dt className="text-xs font-medium text-gray-500">Configuration</dt>
                          <dd className="mt-1 text-xs text-gray-900">
                            Header: {application.auth_config.header_name || 'Authorization'} {application.auth_config.header_prefix || ''}
                          </dd>
                        </div>
                      )}
                    </dl>
                  </div>
                </div>

                {/* Services */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-gray-900">Services</h4>
                    <Link
                      to={`/applications/${appId}?tab=services`}
                      className="text-xs text-primary hover:text-secondary"
                    >
                      View all services →
                    </Link>
                  </div>
                  <p className="text-sm text-gray-500">
                    {services.length} service{services.length !== 1 ? 's' : ''} configured
                  </p>
                </div>
              </div>
            </div>

            {/* Raw Configuration (Admin Only) */}
            {isAdmin && (
              <div className="bg-white shadow rounded-lg">
                <div className="px-6 py-4 border-b border-gray-200">
                  <div className="flex items-center">
                    <CogIcon className="w-5 h-5 text-gray-400 mr-2" />
                    <h3 className="text-lg font-medium text-gray-900">Raw Configuration</h3>
                    <span className="ml-2 text-sm text-gray-500">(Admin Only)</span>
                  </div>
                </div>
                
                <div className="p-6 space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Full Authentication Config</h4>
                    <div className="bg-gray-50 rounded-md p-4 max-h-64 overflow-y-auto">
                      <pre className="text-xs text-gray-800 whitespace-pre-wrap font-mono">
{JSON.stringify(application.auth_config || {}, null, 2)}
                      </pre>
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Full Webhook Config</h4>
                    <div className="bg-gray-50 rounded-md p-4 max-h-64 overflow-y-auto">
                      <pre className="text-xs text-gray-800 whitespace-pre-wrap font-mono">
{JSON.stringify(typeof application.webhook_config === 'string' ? JSON.parse(application.webhook_config) : application.webhook_config || {}, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'advanced' && (
          <div className="space-y-6">
            {/* Advanced Configuration Notice */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex">
                <InformationCircleIcon className="h-5 w-5 text-blue-400 mr-2" />
                <div className="text-sm text-blue-800">
                  <p className="font-medium">Advanced Configuration</p>
                  <p className="mt-1">These settings are for advanced use cases and special configurations. Modify with caution.</p>
                </div>
              </div>
            </div>

            {/* Rate Limiting Configuration */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Rate Limiting</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">Global Rate Limit</label>
                  <p className="mt-1 text-sm text-gray-900">{application.rate_limit_config?.global_limit || 'Not configured'} req/min</p>
                  <p className="text-xs text-gray-500 mt-1">Maximum requests per minute across all users</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Per-User Rate Limit</label>
                  <p className="mt-1 text-sm text-gray-900">{application.rate_limit_config?.per_user_limit || 'Not configured'} req/min</p>
                  <p className="text-xs text-gray-500 mt-1">Maximum requests per minute per user</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Burst Limit</label>
                  <p className="mt-1 text-sm text-gray-900">{application.rate_limit_config?.burst_limit || 'Not configured'}</p>
                  <p className="text-xs text-gray-500 mt-1">Maximum burst requests allowed</p>
                </div>
              </div>
            </div>

            {/* Custom Headers Configuration */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Custom Headers</h3>
              <div className="space-y-3">
                <p className="text-sm text-gray-500">Global headers applied to all API requests for this application.</p>
                {application.custom_headers && Object.keys(application.custom_headers).length > 0 ? (
                  <div className="bg-gray-50 rounded-md p-4">
                    <dl className="space-y-2">
                      {Object.entries(application.custom_headers).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <dt className="text-sm font-mono text-gray-700">{key}:</dt>
                          <dd className="text-sm font-mono text-gray-900">{value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">No custom headers configured</p>
                )}
              </div>
            </div>

            {/* Retry Configuration */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Retry Configuration</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">Max Retries</label>
                  <p className="mt-1 text-sm text-gray-900">{application.retry_config?.max_retries || 3}</p>
                  <p className="text-xs text-gray-500 mt-1">Maximum number of retry attempts</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Retry Delay</label>
                  <p className="mt-1 text-sm text-gray-900">{application.retry_config?.retry_delay || 1000}ms</p>
                  <p className="text-xs text-gray-500 mt-1">Initial delay between retries</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Backoff Multiplier</label>
                  <p className="mt-1 text-sm text-gray-900">{application.retry_config?.backoff_multiplier || 2}x</p>
                  <p className="text-xs text-gray-500 mt-1">Exponential backoff multiplier</p>
                </div>
              </div>
            </div>

            {/* Timeout Configuration */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Timeout Settings</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">Connection Timeout</label>
                  <p className="mt-1 text-sm text-gray-900">{application.timeout_config?.connection_timeout || 30} seconds</p>
                  <p className="text-xs text-gray-500 mt-1">Maximum time to establish connection</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Read Timeout</label>
                  <p className="mt-1 text-sm text-gray-900">{application.timeout_config?.read_timeout || 60} seconds</p>
                  <p className="text-xs text-gray-500 mt-1">Maximum time to wait for response</p>
                </div>
              </div>
            </div>

            {/* API Versioning */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">API Versioning</h3>
              <div className="space-y-3">
                <div>
                  <label className="text-sm font-medium text-gray-700">API Version</label>
                  <p className="mt-1 text-sm text-gray-900">{application.api_version || 'Not specified'}</p>
                  <p className="text-xs text-gray-500 mt-1">Version of the external API being used</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Version Header</label>
                  <p className="mt-1 text-sm text-gray-900 font-mono">{application.version_header || 'Not configured'}</p>
                  <p className="text-xs text-gray-500 mt-1">Header name for API version specification</p>
                </div>
              </div>
            </div>

            {/* Feature Flags */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Feature Flags</h3>
              <div className="space-y-3">
                {application.feature_flags && Object.keys(application.feature_flags).length > 0 ? (
                  <div className="space-y-2">
                    {Object.entries(application.feature_flags).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between py-2 border-b border-gray-100">
                        <span className="text-sm font-medium text-gray-700">{key}</span>
                        <span className={`text-sm font-medium ${value ? 'text-green-600' : 'text-gray-400'}`}>
                          {value ? 'Enabled' : 'Disabled'}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">No feature flags configured</p>
                )}
              </div>
            </div>

            {/* Metadata */}
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Metadata</h3>
              <div className="space-y-3">
                <p className="text-sm text-gray-500">Additional metadata and custom attributes for this application.</p>
                {application.metadata && Object.keys(application.metadata).length > 0 ? (
                  <div className="bg-gray-50 rounded-md p-4 max-h-64 overflow-y-auto">
                    <pre className="text-xs text-gray-800 whitespace-pre-wrap font-mono">
{JSON.stringify(application.metadata, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">No metadata configured</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Event Modal */}
      {showEventModal && (
        <EventModal
          event={editingEvent}
          appId={appId}
          services={services}
          onSave={(eventData) => eventMutation.mutate(eventData)}
          onClose={() => {
            setShowEventModal(false);
            setEditingEvent(null);
          }}
          isLoading={eventMutation.isPending}
        />
      )}

      {/* Service Modal */}
      {showServiceModal && (
        <ServiceModal
          service={editingService}
          appId={appId}
          onSave={(serviceData) => serviceMutation.mutate(serviceData)}
          onClose={() => {
            setShowServiceModal(false);
            setEditingService(null);
          }}
          isLoading={serviceMutation.isPending}
        />
      )}

      {/* Sample Code Modal */}
      {showSampleCodeModal && selectedEventForCode && (
        <SampleCodeModal
          event={selectedEventForCode}
          application={application}
          subscription={subscription}
          onClose={() => {
            setShowSampleCodeModal(false);
            setSelectedEventForCode(null);
          }}
        />
      )}

      {/* Auth Config Modal */}
      {showAuthConfigModal && application && (
        <AuthConfigModal
          application={application}
          onClose={() => setShowAuthConfigModal(false)}
          onUpdate={(updatedApp) => {
            queryClient.invalidateQueries(['application', appId]);
            showSuccessToast('Authentication configuration updated');
          }}
        />
      )}

      {/* Webhook Config Modal */}
      {showWebhookConfigModal && application && (
        <WebhookConfigModal
          application={application}
          onClose={() => setShowWebhookConfigModal(false)}
          onUpdate={(updatedApp) => {
            queryClient.invalidateQueries(['application', appId]);
            showSuccessToast('Webhook configuration updated');
          }}
        />
      )}

      {/* Service Detail Modal */}
      {showServiceDetailModal && selectedServiceForDetail && (
        <ServiceDetailModal
          service={selectedServiceForDetail}
          application={application}
          onClose={() => {
            setShowServiceDetailModal(false);
            setSelectedServiceForDetail(null);
          }}
          onServiceUpdated={(updatedService) => {
            // Update the service in the services list
            setServices(prevServices =>
              prevServices.map(s =>
                s.service_id === updatedService.service_id ? updatedService : s
              )
            );
            setSelectedServiceForDetail(updatedService);
          }}
        />
      )}

      {/* Pricing Configuration Modal */}
      {showPricingModal && application && (
        <PricingConfiguration
          application={application}
          onClose={() => setShowPricingModal(false)}
          onUpdate={() => {
            setShowPricingModal(false);
            queryClient.invalidateQueries(['application', appId]);
            showSuccessToast('Pricing configuration updated successfully');
          }}
        />
      )}
    </div>
  );
}

// Event Modal Component
function EventModal({ event, appId, services = [], onSave, onClose, isLoading }) {
  const [formData, setFormData] = useState({
    event_name: event?.event_name || '',
    display_name: event?.display_name || '',
    description: event?.description || '',
    event_type: event?.event_type || 'webhook',
    event_configuration: event?.event_configuration || {},
    output_schema: event?.output_schema || null,
    api_endpoint: event?.api_endpoint || '',
    sync_mode: event?.sync_mode || 'asynchronous',
  });

  const [schemaData, setSchemaData] = useState(null);
  const [checkingEndpoint, setCheckingEndpoint] = useState(false);
  const [endpointAvailable, setEndpointAvailable] = useState(null);

  const handleSchemaChange = useCallback((data) => {
    setSchemaData(data);
  }, []);

  // Helper function to add parameter extraction to schema
  const addParameterExtractionToSchema = (schema, fields) => {
    const mappings = {};
    const updatedProperties = { ...schema.properties };
    
    // Extract JSONPath expressions from field descriptions
    fields.forEach(field => {
      const fieldName = field.field_name || field.param_name;
      const description = field.description || '';
      
      if (fieldName && description.includes('extracted from $')) {
        try {
          // Extract the JSONPath from description like "extracted from $.text.body"
          const pathMatch = description.match(/extracted from \$\.?(.+?)(\s|$)/);
          if (pathMatch && pathMatch[1]) {
            const jsonPath = pathMatch[1].trim();
            mappings[fieldName] = jsonPath;
            
            // Add mapping info to the property
            if (updatedProperties[fieldName]) {
              updatedProperties[fieldName].mapping = jsonPath;
            }
          }
        } catch (e) {
          console.warn(`Failed to extract JSONPath from field ${fieldName}:`, e);
        }
      }
    });
    
    // Create unified schema with parameter extraction
    const unifiedSchema = {
      ...schema,
      properties: updatedProperties
    };
    
    // Add parameter_extraction section if we found mappings
    if (Object.keys(mappings).length > 0) {
      unifiedSchema.parameter_extraction = {
        method: 'json_path',
        mappings: mappings
      };
    }
    
    return unifiedSchema;
  };

  // Check endpoint availability when API endpoint changes
  useEffect(() => {
    if (formData.event_type === 'api_call' && formData.api_endpoint) {
      const timeoutId = setTimeout(async () => {
        setCheckingEndpoint(true);
        try {
          const token = localStorage.getItem('access_token');
          const params = { endpoint: formData.api_endpoint };
          // If editing, pass the current event ID to exclude it from the check
          if (event && event.event_id) {
            params.exclude_event_id = event.event_id;
          }
          const response = await axios.get(
            `${API_BASE_URL}/api/v1/applications/events/check-endpoint-availability`,
            {
              params,
              headers: { Authorization: `Bearer ${token}` }
            }
          );
          setEndpointAvailable(response.data.available);
        } catch (error) {
          console.error('Error checking endpoint availability:', error);
          setEndpointAvailable(null);
        } finally {
          setCheckingEndpoint(false);
        }
      }, 500); // Debounce for 500ms

      return () => clearTimeout(timeoutId);
    } else {
      setEndpointAvailable(null);
    }
  }, [formData.api_endpoint, formData.event_type, event]);

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Build the unified output schema for ALL event types
    let outputSchema = formData.output_schema;
    
    if (schemaData && schemaData.fields && Array.isArray(schemaData.fields)) {
      // Only build nested schema if we have valid fields
      const validFields = schemaData.fields.filter(f => f && (f.field_name || f.param_name));
      if (validFields.length > 0) {
        outputSchema = buildNestedSchema(schemaData.fields);
        
        // Add parameter extraction for webhook events
        if (formData.event_type === 'webhook') {
          outputSchema = addParameterExtractionToSchema(outputSchema, schemaData.fields);
        }
        
        console.log('Built unified schema from fields:', outputSchema);
        console.log('Schema fields used:', schemaData.fields);
      } else {
        // If no valid fields, use the schema property or create empty schema
        outputSchema = schemaData.schema || { type: 'object', properties: {} };
      }
    } else if (schemaData && schemaData.schema) {
      // Use the generated schema directly
      outputSchema = schemaData.schema;
      
      // Add parameter extraction for webhook events if not already present
      if (formData.event_type === 'webhook' && !outputSchema.parameter_extraction) {
        outputSchema = addParameterExtractionToSchema(outputSchema, []);
      }
    }
    
    // Ensure we always have a valid output_schema for ALL event types
    if (!outputSchema) {
      outputSchema = { 
        type: 'object', 
        properties: {},
        required: []
      };
    }
    
    // Generate a sample payload based on the schema
    let samplePayload = {};
    
    if (outputSchema && outputSchema.properties) {
      // Use the schema utility function for consistent sample generation
      samplePayload = generateSampleFromSchema(outputSchema) || {};
      console.log('EventModal - Generated sample payload:', samplePayload);
      console.log('EventModal - From schema:', outputSchema);
    } else if (outputSchema && outputSchema.type === 'object') {
      // Fallback for schemas without properties defined
      samplePayload = {};
    }
    
    const submitData = {
      event_name: formData.event_name,
      display_name: formData.display_name,
      description: formData.description,
      event_type: formData.event_type,
      event_configuration: formData.event_configuration,
      output_schema: outputSchema,
      sample_payload: samplePayload,
      api_endpoint: formData.event_type === 'api_call' ? formData.api_endpoint : null,
      sync_mode: formData.sync_mode,
    };
    
    onSave(submitData);
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9999]">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto z-[9999]">
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">
              {event ? 'Edit Event' : 'Add Event'}
            </h3>
          </div>

          <div className="px-6 py-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Event Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.event_name}
                  onChange={(e) => setFormData({ ...formData, event_name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_') })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="new_order"
                  pattern="[a-z0-9_]+"
                  title="Only lowercase letters, numbers, and underscores allowed"
                  required
                />
                <p className="mt-1 text-xs text-gray-500">Internal identifier (lowercase, no spaces)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Display Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="New Order"
                  required
                />
                <p className="mt-1 text-xs text-gray-500">User-friendly name shown in the UI</p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Triggered when a new order is created"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Event Type
                </label>
                <select
                  value={formData.event_type}
                  onChange={(e) => setFormData({ ...formData, event_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="webhook">Webhook</option>
                  <option value="schedule">Schedule</option>
                  <option value="polling">Polling</option>
                  <option value="api_call">API Call</option>
                  <option value="manual">Manual</option>
                  <option value="email">Email</option>
                  <option value="form">Form</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">
                  {formData.event_type === 'webhook' ? 'Triggered by external webhooks' :
                   formData.event_type === 'schedule' ? 'Runs on a scheduled basis' :
                   formData.event_type === 'polling' ? 'Polls external API for changes' :
                   formData.event_type === 'api_call' ? 'Triggered via IOFlow API' :
                   formData.event_type === 'manual' ? 'Manually triggered by users' :
                   formData.event_type === 'email' ? 'Triggered by incoming emails' :
                   'Triggered by form submissions'}
                </p>
              </div>

              {formData.event_type === 'polling' && (
                <div className="col-span-2 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Service to Poll <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={formData.event_configuration?.polling_service || ''}
                      onChange={(e) => setFormData({ 
                        ...formData, 
                        event_configuration: { 
                          ...formData.event_configuration, 
                          polling_service: e.target.value 
                        }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      required
                    >
                      <option value="">Select a service...</option>
                      {services.filter(s => {
                        // Filter services suitable for polling (GET methods, list operations)
                        const method = s.request_config?.method || s.service_config?.request_config?.method;
                        const name = s.service_name.toLowerCase();
                        return method === 'GET' || name.includes('list') || name.includes('get') || name.includes('fetch');
                      }).map((service) => (
                        <option key={service.service_id} value={service.service_name}>
                          {service.service_name} {service.description ? `- ${service.description.substring(0, 50)}` : ''}
                        </option>
                      ))}
                    </select>
                    <p className="mt-1 text-xs text-gray-500">
                      Select which service to call periodically to check for changes
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Polling Interval (seconds)
                      </label>
                      <input
                        type="number"
                        value={formData.event_configuration?.interval_seconds || formData.event_configuration?.polling_interval || 300}
                        onChange={(e) => setFormData({ 
                          ...formData, 
                          event_configuration: { 
                            ...formData.event_configuration, 
                            interval_seconds: parseInt(e.target.value),
                            polling_interval: undefined // Remove old field name
                          }
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                        min="60"
                        max="3600"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        How often to check (60-3600 seconds)
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Change Detection Method
                      </label>
                      <select
                        value={formData.event_configuration?.change_detection?.method || 'new_items'}
                        onChange={(e) => setFormData({ 
                          ...formData, 
                          event_configuration: { 
                            ...formData.event_configuration, 
                            change_detection: {
                              ...formData.event_configuration?.change_detection,
                              method: e.target.value
                            }
                          }
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      >
                        <option value="new_items">New Items (Track IDs)</option>
                        <option value="modified_since">Modified Since (Timestamp)</option>
                        <option value="hash_comparison">Hash Comparison</option>
                        <option value="count_change">Count Change</option>
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        How to detect changes in the data
                      </p>
                    </div>
                  </div>

                  {formData.event_configuration?.change_detection?.method === 'new_items' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Identifier Field
                      </label>
                      <input
                        type="text"
                        value={formData.event_configuration?.change_detection?.identifier_field || 'id'}
                        onChange={(e) => setFormData({ 
                          ...formData, 
                          event_configuration: { 
                            ...formData.event_configuration, 
                            change_detection: {
                              ...formData.event_configuration?.change_detection,
                              identifier_field: e.target.value
                            }
                          }
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                        placeholder="id"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Field name that uniquely identifies each item (e.g., 'id', 'uid', 'message_id')
                      </p>
                    </div>
                  )}

                  {formData.event_configuration?.change_detection?.method === 'modified_since' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Timestamp Field
                      </label>
                      <input
                        type="text"
                        value={formData.event_configuration?.change_detection?.timestamp_field || 'updated_at'}
                        onChange={(e) => setFormData({ 
                          ...formData, 
                          event_configuration: { 
                            ...formData.event_configuration, 
                            change_detection: {
                              ...formData.event_configuration?.change_detection,
                              timestamp_field: e.target.value
                            }
                          }
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                        placeholder="updated_at"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Field containing the last modified timestamp
                      </p>
                    </div>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Polling Parameters
                    </label>
                    {(() => {
                      // Find the selected service to get its parameter schema
                      const selectedService = services.find(s => s.service_name === formData.event_configuration?.polling_service);
                      const parameterSchema = selectedService?.parameter_schema || selectedService?.input_schema;
                      
                      if (parameterSchema) {
                        return (
                          <div className="border border-gray-300 rounded-md p-4">
                            <ParameterForm
                              serviceId={selectedService?.service_id}
                              parameters={formData.event_configuration?.polling_parameters || {}}
                              onParametersChange={(params) => {
                                setFormData({
                                  ...formData,
                                  event_configuration: {
                                    ...formData.event_configuration,
                                    polling_parameters: params
                                  }
                                });
                              }}
                              inputSchema={parameterSchema}
                              subscriptionId={application?.subscription_id}
                            />
                            <p className="mt-2 text-xs text-gray-500">
                              Configure parameters for the polling service. Supports template variables like {'{{state.last_id}}'}
                            </p>
                          </div>
                        );
                      } else if (formData.event_configuration?.polling_service) {
                        // Service selected but no schema available, show JSON editor as fallback
                        return (
                          <>
                            <textarea
                              value={JSON.stringify(formData.event_configuration?.polling_parameters || {}, null, 2)}
                              onChange={(e) => {
                                try {
                                  const params = JSON.parse(e.target.value);
                                  setFormData({ 
                                    ...formData, 
                                    event_configuration: { 
                                      ...formData.event_configuration, 
                                      polling_parameters: params
                                    }
                                  });
                                } catch (err) {
                                  // Invalid JSON, don't update
                                }
                              }}
                              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary font-mono text-sm"
                              rows="4"
                              placeholder='{\n  "limit": 100,\n  "status": "active"\n}'
                            />
                            <p className="mt-1 text-xs text-gray-500">
                              Parameters to pass to the polling service (JSON format). Supports template variables like {'{{state.last_id}}'}
                            </p>
                          </>
                        );
                      } else {
                        return (
                          <p className="text-sm text-gray-500 italic">
                            Select a service first to configure parameters
                          </p>
                        );
                      }
                    })()}
                  </div>

                  {formData.event_configuration?.polling_service && (
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            const response = await fetch(`${API_BASE_URL}/api/v1/polling/test`, {
                              method: 'POST',
                              headers: {
                                'Content-Type': 'application/json',
                                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                              },
                              body: JSON.stringify({
                                app_id: appId,
                                service_name: formData.event_configuration.polling_service,
                                parameters: formData.event_configuration.polling_parameters || {}
                              })
                            });
                            
                            const result = await response.json();
                            
                            if (result.success) {
                              showSuccessToast('Polling test successful! Check console for details.');
                              console.log('Polling test result:', result);
                              
                              // Auto-suggest identifier field if found
                              if (result.recommendations?.suggested_identifier && 
                                  formData.event_configuration?.change_detection?.method === 'new_items') {
                                setFormData({
                                  ...formData,
                                  event_configuration: {
                                    ...formData.event_configuration,
                                    change_detection: {
                                      ...formData.event_configuration.change_detection,
                                      identifier_field: result.recommendations.suggested_identifier
                                    }
                                  }
                                });
                                showSuccessToast(`Suggested identifier field: ${result.recommendations.suggested_identifier}`);
                              }
                            } else {
                              showErrorToast(`Test failed: ${result.error || 'Unknown error'}`);
                            }
                          } catch (error) {
                            showErrorToast(`Test error: ${error.message}`);
                          }
                        }}
                        className="px-4 py-2 bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition-colors"
                      >
                        Test Polling Configuration
                      </button>
                    </div>
                  )}
                </div>
              )}

              {formData.event_type === 'webhook' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Webhook URL (Optional)
                  </label>
                  <input
                    type="text"
                    value={formData.event_configuration.webhook_url || ''}
                    onChange={(e) => setFormData({ 
                      ...formData, 
                      event_configuration: { ...formData.event_configuration, webhook_url: e.target.value }
                    })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="https://api.example.com/webhook"
                  />
                </div>
              )}
              
              {formData.event_type === 'api_call' && (
                <div className="col-span-2 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Custom API Endpoint (Optional)
                    </label>
                    <div className="relative">
                      <input
                        type="text"
                        value={formData.api_endpoint || ''}
                        onChange={(e) => setFormData({ ...formData, api_endpoint: e.target.value })}
                        className={`w-full px-3 py-2 pr-10 border rounded-md focus:outline-none focus:ring-1 ${
                          checkingEndpoint 
                            ? 'border-gray-300' 
                            : endpointAvailable === true 
                              ? 'border-green-500 focus:ring-green-500' 
                              : endpointAvailable === false 
                                ? 'border-red-500 focus:ring-red-500' 
                                : 'border-gray-300 focus:ring-primary'
                        }`}
                        placeholder="/my-custom-endpoint"
                      />
                      {checkingEndpoint && (
                        <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-700"></div>
                        </div>
                      )}
                      {!checkingEndpoint && endpointAvailable === true && (
                        <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                          <CheckCircleIcon className="h-5 w-5 text-green-500" />
                        </div>
                      )}
                      {!checkingEndpoint && endpointAvailable === false && (
                        <div className="absolute inset-y-0 right-0 pr-3 flex items-center">
                          <XCircleIcon className="h-5 w-5 text-red-500" />
                        </div>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {formData.api_endpoint ? (
                        endpointAvailable === false ? (
                          <span className="text-red-600">This endpoint is already in use</span>
                        ) : endpointAvailable === true ? (
                          <span className="text-green-600">This endpoint is available</span>
                        ) : (
                          `Full URL: ${API_BASE_URL}${formData.api_endpoint}`
                        )
                      ) : (
                        `Default: ${API_BASE_URL}/api/v1/events/${appId}/${formData.event_name || '{event_name}'}`
                      )}
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      HTTP Method
                    </label>
                    <select
                      value={formData.event_configuration.http_method || 'POST'}
                      onChange={(e) => setFormData({ 
                        ...formData, 
                        event_configuration: { ...formData.event_configuration, http_method: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                      <option value="PUT">PUT</option>
                      <option value="PATCH">PATCH</option>
                      <option value="DELETE">DELETE</option>
                    </select>
                  </div>
                </div>
              )}
              
              {/* Synchronicity Mode - Available for webhook and api_call events */}
              {(formData.event_type === 'webhook' || formData.event_type === 'api_call') && (
                <div className="col-span-2">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Synchronicity Mode
                    </label>
                    <select
                      value={formData.sync_mode}
                      onChange={(e) => setFormData({ ...formData, sync_mode: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="asynchronous">Asynchronous (Default)</option>
                      <option value="synchronous">Synchronous (Wait for response)</option>
                      <option value="optional">Optional (Let flow decide)</option>
                    </select>
                    <p className="mt-1 text-xs text-gray-500">
                      {formData.sync_mode === 'synchronous' 
                        ? `${formData.event_type === 'webhook' ? 'Webhook calls' : 'API calls'} will wait for flow completion and return the response`
                        : formData.sync_mode === 'optional'
                          ? 'Flows can override this setting'
                          : `${formData.event_type === 'webhook' ? 'Webhook calls' : 'API calls'} will return immediately with 202 Accepted`}
                    </p>
                  </div>
                </div>
              )}
            </div>

            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Event Schema & Parameter Extraction</h4>
              <p className="text-xs text-gray-500 mb-3">
                Define the structure of data for this event. For webhooks, use "extracted from $.path" in field descriptions to specify JSONPath expressions for parameter extraction.
              </p>
              
              {formData.event_type === 'webhook' && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
                  <div className="flex items-start">
                    <InformationCircleIcon className="w-4 h-4 text-primary mt-0.5 mr-2 flex-shrink-0" />
                    <div className="text-xs text-blue-700">
                      <strong>Parameter Extraction:</strong> When defining fields below, include "extracted from $.path" in the description to automatically extract values from webhook payloads.
                      <br />
                      <strong>Example:</strong> Field "user_id" with description "User ID extracted from $.user.id"
                    </div>
                  </div>
                </div>
              )}
              <SchemaBuilder
                initialSchema={{
                  json_schema: formData.output_schema
                }}
                onSchemaChange={handleSchemaChange}
                parameterMethod="json_payload"
                mode="edit"
              />
            </div>
          </div>

          <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : event ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Service Modal Component
function ServiceModal({ service, appId, onSave, onClose, isLoading }) {
  // For API call services, endpoint_template might be in service_config
  const getEndpointTemplate = () => {
    if (service?.service_type === 'api_call' && service?.service_config?.endpoint_template) {
      return service.service_config.endpoint_template;
    }
    return service?.endpoint_template || '';
  };
  
  // Initialize service_config with proper values
  const initializeServiceConfig = () => {
    // Parse service_config if it's a string
    const parsedConfig = service?.service_config ? 
      (typeof service.service_config === 'string' ? JSON.parse(service.service_config) : service.service_config) : {};
    const config = parsedConfig || {};
    
    // For api_call services, ensure endpoint_template is in service_config
    if (service?.service_type === 'api_call' && service?.endpoint_template && !config.endpoint_template) {
      config.endpoint_template = service.endpoint_template;
    }
    
    // Copy query_params_template if exists
    if (service?.query_params_template && !config.query_params_template) {
      config.query_params_template = service.query_params_template;
    }
    
    // Copy headers_template to service_config for the form
    if (service?.headers_template && !config.headers_template) {
      console.log('Copying headers_template to service_config:', service.headers_template);
      // Parse if string
      const headers = typeof service.headers_template === 'string' ? 
        JSON.parse(service.headers_template) : service.headers_template;
      config.headers_template = headers;
    }
    
    // Include response_config from service level into service_config
    if (service?.response_config && !config.response_config) {
      console.log('Copying response_config to service_config:', service.response_config);
      const responseConfig = typeof service.response_config === 'string' ? 
        JSON.parse(service.response_config) : service.response_config;
      config.response_config = responseConfig;
    }
    
    // Include request_config from service level into service_config
    if (service?.request_config && !config.request_config) {
      console.log('Copying request_config to service_config:', service.request_config);
      const requestConfig = typeof service.request_config === 'string' ? 
        JSON.parse(service.request_config) : service.request_config;
      config.request_config = requestConfig;
    }
    
    // Ensure request_config has parameter_method set (align with seed applications)
    if (!config.request_config) {
      config.request_config = {};
    }
    if (!config.request_config.parameter_method) {
      // Default to json_payload for API services
      config.request_config.parameter_method = 'json_payload';
    }
    
    console.log('ServiceModal initializeServiceConfig - service:', service);
    console.log('ServiceModal initializeServiceConfig - final config:', config);
    
    return config;
  };

  const [formData, setFormData] = useState(() => {
    const config = initializeServiceConfig();
    // Ensure request_config is properly initialized for new services
    if (!service && !config.request_config) {
      config.request_config = {
        parameter_method: 'json_payload',
        method: 'POST'
      };
    }
    
    return {
      service_name: service?.service_name || '',
      display_name: service?.display_name || '',
      description: service?.description || '',
      service_type: service?.service_type || 'api_call',
      service_config: config,
      url_pattern: service?.url_pattern || service?.service_config?.url_pattern || '',
      parameters: service?.parameters || service?.service_config?.parameters || [],
      input_schema: service?.input_schema || null,
      output_schema: service?.output_schema || null,
      error_schema: service?.error_schema || null,
      is_async: service?.is_async || false,
      async_config: service?.async_config || {},
      retry_config: service?.retry_config || {},
      sync_mode: service?.sync_mode || 'synchronous',
      is_active: service?.is_active !== false,
      // Legacy fields removed - all configuration is in service_config
    };
  });

  const [parameterSchema, setParameterSchema] = useState(null);

  const handleParameterSchemaChange = useCallback((data) => {
    setParameterSchema(data);
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    
    // Use parameterSchema if available (from SchemaBuilder), otherwise use formData.parameters
    const parameters = parameterSchema?.fields || formData.parameters || [];
    let parameter_schema = null;
    
    // Always build parameter_schema if we have parameters
    if (parameters && parameters.length > 0) {
      // Build parameter_schema in JSON Schema format
      const properties = {};
      const required = [];
      
      parameters.forEach(param => {
        const fieldName = param.field_name || param.param_name;
        if (!fieldName) return; // Skip if no field name
        
        properties[fieldName] = {
          type: param.data_type || 'string',
          description: param.description || param.friendly_name || '',
        };
        
        if (param.friendly_name) {
          properties[fieldName].title = param.friendly_name;
        }
        
        if (param.is_required || param.required) {
          required.push(fieldName);
        }
      });
      
      parameter_schema = {
        type: 'object',
        properties: properties,
      };
      
      if (required.length > 0) {
        parameter_schema.required = required;
      }
    }
    
    // Start with form data
    const submitData = {
      ...formData,
      url_pattern: parameterSchema?.url_pattern || formData.url_pattern,
    };
    
    // Always ensure service_config exists
    if (!submitData.service_config) {
      submitData.service_config = {};
    }
    
    // Ensure request_config is properly set with parameter_method
    if (!submitData.service_config.request_config) {
      submitData.service_config.request_config = {
        parameter_method: 'json_payload',
        method: 'POST'
      };
    } else {
      // Ensure parameter_method is always set
      if (!submitData.service_config.request_config.parameter_method) {
        submitData.service_config.request_config.parameter_method = 'json_payload';
      }
      // Ensure method is set
      if (!submitData.service_config.request_config.method) {
        submitData.service_config.request_config.method = 'POST';
      }
    }
    
    // Add parameters to service_config
    if (parameters && parameters.length > 0) {
      submitData.service_config.parameters = parameters;
      if (parameter_schema) {
        submitData.service_config.parameter_schema = parameter_schema;
      }
    }
    
    // Set input_schema to parameter_schema for consistency
    if (parameter_schema) {
      submitData.input_schema = parameter_schema;
    }
    
    // Also set parameter_schema at top level (some backend code might expect it)
    if (parameter_schema) {
      submitData.parameter_schema = parameter_schema;
    }
    
    // Debug: Log what we're sending
    console.log('Service Form - Submitting data:', JSON.stringify(submitData, null, 2));
    console.log('Service Config request_config:', submitData.service_config?.request_config);
    console.log('Service Config parameters:', submitData.service_config?.parameters);
    console.log('Input Schema:', submitData.input_schema);
    
    onSave(submitData);
  };

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9998]">
      <div className="bg-white rounded-lg max-w-5xl w-full max-h-[90vh] overflow-y-auto z-[9999]">
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">
              {service ? 'Edit Service' : 'Add Service'}
            </h3>
          </div>

          <div className="px-6 py-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Service Name
                </label>
                <input
                  type="text"
                  value={formData.service_name}
                  onChange={(e) => setFormData({ ...formData, service_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="send_email"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Display Name
                </label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Send Email"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Send an email to specified recipients"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Service Type
                </label>
                <select
                  value={formData.service_type}
                  onChange={(e) => setFormData({ ...formData, service_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="api_call">API Call</option>
                  <option value="graphql">GraphQL</option>
                  <option value="webhook">Webhook</option>
                  <option value="email_send">Email Send</option>
                  <option value="smtp_send">SMTP Send</option>
                  <option value="pop3_receive">POP3 Receive</option>
                  <option value="imap_receive">IMAP Receive</option>
                  <option value="llm_api_call">LLM API Call</option>
                  <option value="mcp_call">MCP Call</option>
                  <option value="database_query">Database Query</option>
                  <option value="action">Action (Legacy)</option>
                  <option value="search">Search (Legacy)</option>
                  <option value="create">Create (Legacy)</option>
                  <option value="update">Update (Legacy)</option>
                  <option value="delete">Delete (Legacy)</option>
                  <option value="custom">Custom (Legacy)</option>
                </select>
              </div>

            </div>

            {/* Service Type Configuration */}
            {['api_call', 'graphql', 'webhook', 'email_send', 'smtp_send', 'pop3_receive', 'imap_receive', 'llm_api_call', 'mcp_call', 'database_query'].includes(formData.service_type) && (
              <div className="border-t pt-4">
                <ServiceTypeConfig
                  serviceType={formData.service_type}
                  config={formData.service_config || {}}
                  onChange={(newConfig) => setFormData({ ...formData, service_config: newConfig })}
                  mode="edit"
                />
              </div>
            )}

            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Service Parameters</h4>
              {(() => {
                // Debug logging
                console.log('Service:', service);
                console.log('FormData parameters:', formData.parameters);
                console.log('Service config:', formData.service_config);
                
                return (
                  <SchemaBuilder
                    initialSchema={{
                      fields: formData.parameters,
                      url_pattern: formData.url_pattern,
                      json_schema: formData.input_schema
                    }}
                    onSchemaChange={handleParameterSchemaChange}
                    parameterMethod={formData.service_config?.request_config?.parameter_method || 'json_payload'}
                    mode="edit"
                  />
                );
              })()}
            </div>

            {/* Advanced Configuration */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Advanced Configuration</h4>
              
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Sync Mode
                  </label>
                  <select
                    value={formData.sync_mode}
                    onChange={(e) => setFormData({ ...formData, sync_mode: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="synchronous">Synchronous</option>
                    <option value="asynchronous">Asynchronous</option>
                    <option value="optional">Optional</option>
                  </select>
                  <p className="mt-1 text-xs text-gray-500">
                    How the service should be executed within flows
                  </p>
                </div>

                <div className="flex items-start">
                  <div className="flex items-center h-5 mt-2">
                    <input
                      type="checkbox"
                      id="is_active"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="h-4 w-4 text-indigo-600 focus:ring-primary border-gray-300 rounded"
                    />
                  </div>
                  <div className="ml-3">
                    <label htmlFor="is_active" className="text-sm font-medium text-gray-700">
                      Service Active
                    </label>
                    <p className="text-xs text-gray-500">
                      Inactive services cannot be used in flows
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center mb-4">
                <input
                  type="checkbox"
                  id="is_async"
                  checked={formData.is_async}
                  onChange={(e) => setFormData({ ...formData, is_async: e.target.checked })}
                  className="h-4 w-4 text-indigo-600 focus:ring-primary border-gray-300 rounded"
                />
                <label htmlFor="is_async" className="ml-2 block text-sm text-gray-900">
                  Enable Asynchronous Processing
                </label>
                <p className="ml-6 text-xs text-gray-500 mt-1">
                  Service will poll for results or use callbacks
                </p>
              </div>

              {formData.is_async && (
                <div className="ml-6 mb-4 space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Callback URL
                    </label>
                    <input
                      type="url"
                      value={formData.async_config.callback_url || ''}
                      onChange={(e) => setFormData({ 
                        ...formData, 
                        async_config: { ...formData.async_config, callback_url: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      placeholder="https://api.example.com/callback"
                    />
                    <p className="mt-1 text-xs text-gray-500">URL to receive completion notifications</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Timeout (seconds)
                      </label>
                      <input
                        type="number"
                        value={formData.async_config.timeout_seconds || 300}
                        onChange={(e) => setFormData({ 
                          ...formData, 
                          async_config: { ...formData.async_config, timeout_seconds: parseInt(e.target.value) }
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                        min="1"
                        max="3600"
                      />
                      <p className="mt-1 text-xs text-gray-500">Max wait time (1-3600s)</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Polling Interval (seconds)
                      </label>
                      <input
                        type="number"
                        value={formData.async_config.polling_interval || 5}
                        onChange={(e) => setFormData({ 
                          ...formData, 
                          async_config: { ...formData.async_config, polling_interval: parseInt(e.target.value) }
                        })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                        min="1"
                        max="60"
                      />
                      <p className="mt-1 text-xs text-gray-500">Check frequency (1-60s)</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Retry Configuration */}
              <div className="border-t pt-4">
                <h5 className="text-sm font-medium text-gray-900 mb-3">Retry Configuration</h5>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Max Retries
                    </label>
                    <input
                      type="number"
                      value={formData.retry_config.max_retries || 3}
                      onChange={(e) => setFormData({ 
                        ...formData, 
                        retry_config: { ...formData.retry_config, max_retries: parseInt(e.target.value) }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      min="0"
                      max="10"
                    />
                    <p className="mt-1 text-xs text-gray-500">0 = no retries</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Initial Delay (ms)
                    </label>
                    <input
                      type="number"
                      value={formData.retry_config.initial_delay_ms || 1000}
                      onChange={(e) => setFormData({ 
                        ...formData, 
                        retry_config: { ...formData.retry_config, initial_delay_ms: parseInt(e.target.value) }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                      min="100"
                      max="60000"
                      step="100"
                    />
                    <p className="mt-1 text-xs text-gray-500">Wait before first retry</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Backoff Strategy
                    </label>
                    <select
                      value={formData.retry_config.backoff_strategy || 'exponential'}
                      onChange={(e) => setFormData({ 
                        ...formData, 
                        retry_config: { ...formData.retry_config, backoff_strategy: e.target.value }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                    >
                      <option value="fixed">Fixed</option>
                      <option value="linear">Linear</option>
                      <option value="exponential">Exponential</option>
                    </select>
                    <p className="mt-1 text-xs text-gray-500">
                      {formData.retry_config.backoff_strategy === 'exponential' 
                        ? 'Delay doubles each retry'
                        : formData.retry_config.backoff_strategy === 'linear'
                          ? 'Delay increases linearly'
                          : 'Same delay each retry'}
                    </p>
                  </div>
                </div>
                <div className="mt-3">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Retry On Status Codes
                  </label>
                  <input
                    type="text"
                    value={(formData.retry_config.retry_on_status_codes || []).join(', ')}
                    onChange={(e) => setFormData({ 
                      ...formData, 
                      retry_config: { 
                        ...formData.retry_config, 
                        retry_on_status_codes: e.target.value.split(',').map(s => s.trim()).filter(s => s).map(Number)
                      }
                    })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
                    placeholder="500, 502, 503, 504"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Comma-separated HTTP status codes that should trigger a retry
                  </p>
                </div>
              </div>

              {/* Error Schema */}
              <div className="border-t pt-4">
                <h5 className="text-sm font-medium text-gray-900 mb-3">Error Schema</h5>
                <p className="text-xs text-gray-500 mb-3">
                  Define the structure of error responses from this service
                </p>
                <textarea
                  value={JSON.stringify(formData.error_schema || {}, null, 2)}
                  onChange={(e) => {
                    try {
                      setFormData({ ...formData, error_schema: JSON.parse(e.target.value) });
                    } catch (err) {
                      // Invalid JSON, ignore
                    }
                  }}
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary font-mono text-sm"
                  placeholder='{
  "type": "object",
  "properties": {
    "error": { "type": "string" },
    "code": { "type": "string" }
  }
}'
                />
              </div>
            </div>
          </div>

          <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : service ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}

// Sample Code Modal Component
function SampleCodeModal({ event, application, subscription, onClose }) {
  const [activeLanguage, setActiveLanguage] = useState('curl');
  const [copied, setCopied] = useState(false);
  const [sampleData, setSampleData] = useState(null);
  const [isLoadingSample, setIsLoadingSample] = useState(true);

  const API_BASE_URL = import.meta.env.VITE_API_URL || window.location.origin;
  
  // Fetch sample data from API
  useEffect(() => {
    const fetchSampleData = async () => {
      try {
        setIsLoadingSample(true);
        const token = localStorage.getItem('access_token');
        const response = await axios.get(
          `${API_BASE_URL}/api/v1/applications/${application.app_id}/events/${event.event_id}/sample`,
          {
            headers: { Authorization: `Bearer ${token}` }
          }
        );
        setSampleData(response.data);
      } catch (error) {
        console.error('Failed to fetch sample data:', error);
        // Fall back to generating sample data locally
        setSampleData(null);
      } finally {
        setIsLoadingSample(false);
      }
    };

    if (event && application) {
      fetchSampleData();
    }
  }, [event, application, API_BASE_URL]);
  
  // Helper function to get schema fields in a consistent format
  const getSchemaFields = () => {
    console.log('Event output_schema:', event.output_schema);
    if (!event.output_schema) return [];
    
    if (event.output_schema._fields && Array.isArray(event.output_schema._fields)) {
      // Filter out any fields without a field_name
      const fields = event.output_schema._fields.filter(field => field && field.field_name);
      console.log('Fields from _fields:', fields);
      return fields;
    } else if (event.output_schema.properties) {
      // Handle JSON Schema format
      const fields = Object.entries(event.output_schema.properties).map(([key, value]) => ({
        field_name: key,
        data_type: value.type || 'string',
        description: value.description || '',
        is_required: event.output_schema.required?.includes(key) || false
      }));
      console.log('Fields from properties:', fields);
      return fields;
    }
    return [];
  };
  
  // Generate sample payload based on output schema
  const generateSamplePayload = () => {
    console.log('=== Generating sample payload ===');
    console.log('Event:', event);
    console.log('Event output_schema:', JSON.stringify(event.output_schema, null, 2));
    console.log('Sample data from API:', sampleData);
    console.log('Event sample_payload:', event.sample_payload);
    console.log('Subscription data:', subscription);
    
    // If we have sample data from the API, use it
    if (sampleData && sampleData.sample_data && Object.keys(sampleData.sample_data).length > 0) {
      console.log('Path 1: Using sample data from API');
      return sampleData.sample_data;
    }
    
    // If event has a sample_payload defined, use it
    if (event.sample_payload && typeof event.sample_payload === 'object' && Object.keys(event.sample_payload).length > 0) {
      console.log('Path 2: Using event sample_payload');
      return event.sample_payload;
    }
    
    // Try to generate from the full schema if it has properties (proper JSON schema format)
    if (event.output_schema && event.output_schema.properties && !event.output_schema._fields) {
      console.log('Path 3: Generating from JSON schema properties');
      console.log('Schema properties:', event.output_schema.properties);
      const generatedPayload = generateSampleFromSchema(event.output_schema);
      if (generatedPayload) {
        console.log('Generated payload from JSON schema:', generatedPayload);
        return generatedPayload;
      }
    }
    
    const fields = getSchemaFields();
    console.log('Fields for payload generation:', fields);
    
    // If we have fields from the schema, generate sample data
    if (fields.length > 0) {
      const payload = {};
      
      // Sort fields by their path depth to ensure parent objects are created first
      const sortedFields = [...fields].sort((a, b) => {
        const aDepth = (a.field_name || '').split('.').length;
        const bDepth = (b.field_name || '').split('.').length;
        return aDepth - bDepth;
      });
      
      // First, identify which object fields have child properties
      const objectFieldsWithChildren = new Set();
      sortedFields.forEach(field => {
        if (!field.field_name) return;
        const parts = field.field_name.split('.');
        if (parts.length > 1) {
          // This is a nested field, so its parent is an object with children
          for (let i = 0; i < parts.length - 1; i++) {
            const parentPath = parts.slice(0, i + 1).join('.');
            objectFieldsWithChildren.add(parentPath);
          }
        }
      });
      
      sortedFields.forEach(field => {
        if (!field.field_name) return;
        
        const parts = field.field_name.split('.');
        let current = payload;
        
        // Navigate/create nested structure
        for (let i = 0; i < parts.length - 1; i++) {
          const part = parts[i];
          if (!current[part]) {
            current[part] = {};
          }
          current = current[part];
        }
        
        // Set the final value
        const lastPart = parts[parts.length - 1];
        if (field.data_type === 'object') {
          // Only initialize as empty object if it doesn't have child properties
          if (!current[lastPart] && !objectFieldsWithChildren.has(field.field_name)) {
            current[lastPart] = {};
          }
          // If it has children, they will be populated by subsequent iterations
        } else {
          // Generate value for the field
          current[lastPart] = generateSampleValue(field);
        }
      });
      
      console.log('Generated payload from schema fields:', payload);
      return payload;
    }
    
    console.log('No fields found, using default payload');
    // Return a sample payload with common fields
    return {
      "event_type": event.event_name,
      "timestamp": new Date().toISOString(),
      "data": {
        "example_field": "example_value"
      }
    };
  };
  
  // Helper function to generate realistic sample data based on field name
  const generateSampleValue = (field) => {
      const fieldName = (field.field_name || '').toLowerCase();
      const dataType = field.data_type || 'string';
      
      // Common field patterns
      if (fieldName.includes('email')) return 'user@example.com';
      if (fieldName.includes('phone')) return '+1-555-123-4567';
      if (fieldName.includes('url') || fieldName.includes('link')) return 'https://example.com';
      if (fieldName.includes('name')) {
        if (fieldName.includes('first')) return 'John';
        if (fieldName.includes('last')) return 'Doe';
        if (fieldName.includes('full')) return 'John Doe';
        if (fieldName.includes('company') || fieldName.includes('org')) return 'Acme Corp';
        if (fieldName.includes('product')) return 'Widget Pro';
        if (fieldName.includes('user') || fieldName.includes('customer')) return 'john.doe';
        return 'Sample Name';
      }
      if (fieldName.includes('address')) return '123 Main St, City, State 12345';
      if (fieldName.includes('city')) return 'San Francisco';
      if (fieldName.includes('state')) return 'CA';
      if (fieldName.includes('country')) return 'USA';
      if (fieldName.includes('zip') || fieldName.includes('postal')) return '12345';
      if (fieldName.includes('price') || fieldName.includes('amount') || fieldName.includes('total')) return 99.99;
      if (fieldName.includes('quantity') || fieldName.includes('count')) return 5;
      if (fieldName.includes('id')) {
        if (fieldName.includes('order')) return 'ORD-' + Math.floor(Math.random() * 10000);
        if (fieldName.includes('user') || fieldName.includes('customer')) return 'USR-' + Math.floor(Math.random() * 10000);
        if (fieldName.includes('product')) return 'PRD-' + Math.floor(Math.random() * 10000);
        if (fieldName.includes('transaction')) return 'TXN-' + Math.floor(Math.random() * 10000);
        return 'ID-' + Math.floor(Math.random() * 10000);
      }
      if (fieldName.includes('status')) {
        if (fieldName.includes('order')) return 'pending';
        if (fieldName.includes('payment')) return 'completed';
        return 'active';
      }
      if (fieldName.includes('description')) return 'This is a sample description';
      if (fieldName.includes('message')) return 'Sample message content';
      if (fieldName.includes('title')) return 'Sample Title';
      if (fieldName.includes('date') || fieldName.includes('time')) return new Date().toISOString();
      if (fieldName.includes('created') || fieldName.includes('updated')) return new Date().toISOString();
      if (fieldName.includes('currency')) return 'USD';
      if (fieldName.includes('sku')) return 'SKU-12345';
      if (fieldName.includes('category')) return 'Electronics';
      if (fieldName.includes('type')) return 'standard';
      if (fieldName.includes('method')) {
        if (fieldName.includes('payment')) return 'credit_card';
        if (fieldName.includes('shipping')) return 'standard';
        return 'default';
      }
      
      // Type-based defaults
      switch (dataType) {
        case 'string':
          return field.description || `Sample ${field.field_name}`;
        case 'number':
          if (fieldName.includes('age')) return 25;
          if (fieldName.includes('year')) return new Date().getFullYear();
          if (fieldName.includes('month')) return new Date().getMonth() + 1;
          if (fieldName.includes('day')) return new Date().getDate();
          return 42;
        case 'boolean':
          if (fieldName.includes('is_') || fieldName.includes('has_') || fieldName.includes('can_')) return true;
          return false;
        case 'date':
          return new Date().toISOString();
        case 'array':
          if (fieldName.includes('tags')) return ['tag1', 'tag2', 'tag3'];
          if (fieldName.includes('items')) return [{ id: 1, name: 'Item 1' }, { id: 2, name: 'Item 2' }];
          if (fieldName.includes('ids')) return ['id1', 'id2', 'id3'];
          return ['value1', 'value2'];
        case 'object':
          if (fieldName.includes('metadata')) return { source: 'api', version: '1.0' };
          if (fieldName.includes('config')) return { enabled: true, timeout: 30 };
          if (fieldName.includes('settings')) return { theme: 'dark', language: 'en' };
          if (fieldName.includes('address')) return { 
            street: '123 Main St', 
            city: 'San Francisco', 
            state: 'CA', 
            zip: '94105' 
          };
          return { key: 'value', nested: { prop: 'data' } };
        default:
          return 'sample value';
      }
  };

  // Generate webhook URL for the event
  const getWebhookUrl = () => {
    if (event.event_type === 'webhook' && event.event_configuration?.webhook_url) {
      return event.event_configuration.webhook_url;
    }
    // Webhooks are at root level, not under /api/v1
    return `${API_BASE_URL}/webhooks/${application.app_id}/${event.event_name}`;
  };

  // Generate API endpoint for API call events
  const getApiEndpoint = () => {
    if (event.event_type === 'api_call') {
      // Check if custom endpoint is defined
      if (event.api_endpoint) {
        // Custom endpoints are already at the root level
        return `${API_BASE_URL}${event.api_endpoint}`;
      }
      // Default API call endpoint
      return `${API_BASE_URL}/api/v1/events/${application.app_id}/${event.event_name}`;
    }
    // This shouldn't be used for non-api_call events
    return `${API_BASE_URL}/api/v1/events/${application.app_id}/${event.event_name}`;
  };

  // Generate code samples
  const generateCode = () => {
    const samplePayload = generateSamplePayload();
    const webhookUrl = getWebhookUrl();
    const apiEndpoint = getApiEndpoint();
    const httpMethod = event.event_configuration?.http_method || 'POST';
    
    // Use the actual API key if available, otherwise show placeholder
    let apiKey = 'YOUR_API_KEY';
    if (subscription && subscription.invocation_api_key) {
      apiKey = subscription.invocation_api_key;
      console.log('Using actual API key from subscription');
    } else {
      console.log('No API key found in subscription, using placeholder');
    }
    
    const codes = {
      curl: `# Trigger ${event.display_name} event
curl -X ${httpMethod} \\
  '${event.event_type === 'api_call' ? apiEndpoint : webhookUrl}' \\
  -H 'Content-Type: application/json' \\
  -H 'Authorization: Bearer ${apiKey}' \\
  -d '${JSON.stringify(samplePayload, null, 2)}'`,
      
      python: `import requests
import json

# Trigger ${event.display_name} event
url = "${event.event_type === 'api_call' ? apiEndpoint : webhookUrl}"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer ${apiKey}"
}
payload = ${JSON.stringify(samplePayload, null, 4)}

response = requests.${httpMethod.toLowerCase()}(url, headers=headers, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")`,
      
      javascript: `// Trigger ${event.display_name} event
const url = "${event.event_type === 'api_call' ? apiEndpoint : webhookUrl}";
const headers = {
  "Content-Type": "application/json",
  "Authorization": "Bearer ${apiKey}"
};
const payload = ${JSON.stringify(samplePayload, null, 2)};

fetch(url, {
  method: "${httpMethod}",
  headers: headers,
  body: JSON.stringify(payload)
})
.then(response => response.json())
.then(data => {
  console.log("Success:", data);
})
.catch(error => {
  console.error("Error:", error);
});`,
      
      java: `import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class TriggerEvent {
    public static void main(String[] args) {
        try {
            // Trigger ${event.display_name} event
            URL url = new URL("${event.event_type === 'api_call' ? apiEndpoint : webhookUrl}");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            
            conn.setRequestMethod("${httpMethod}");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Authorization", "Bearer ${apiKey}");
            conn.setDoOutput(true);
            
            String payload = ${JSON.stringify(JSON.stringify(samplePayload))};
            
            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = payload.getBytes("utf-8");
                os.write(input, 0, input.length);
            }
            
            int responseCode = conn.getResponseCode();
            System.out.println("Response Code: " + responseCode);
            
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), "utf-8"))) {
                StringBuilder response = new StringBuilder();
                String responseLine;
                while ((responseLine = br.readLine()) != null) {
                    response.append(responseLine.trim());
                }
                System.out.println("Response: " + response.toString());
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}`
    };
    
    return codes[activeLanguage];
  };

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(generateCode());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const languages = [
    { id: 'curl', name: 'cURL' },
    { id: 'python', name: 'Python' },
    { id: 'javascript', name: 'JavaScript' },
    { id: 'java', name: 'Java' }
  ];

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9999]">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col z-[9999]">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">
            Sample Code for {event.display_name}
          </h3>
          <p className="text-sm text-gray-500 mt-1">
            {event.event_type === 'webhook' ? 'Webhook' : event.event_type === 'api_call' ? 'API Call' : 'Event'} Trigger
          </p>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="px-6 py-4">
            {isLoadingSample ? (
              <div className="flex items-center justify-center py-12">
                <div className="text-gray-500">Loading sample data...</div>
              </div>
            ) : (
            <>
            {/* Language Tabs */}
            <div className="border-b border-gray-200 mb-4">
              <nav className="-mb-px flex space-x-8">
                {languages.map((lang) => (
                  <button
                    key={lang.id}
                    onClick={() => setActiveLanguage(lang.id)}
                    className={`py-2 px-1 border-b-2 font-medium text-sm ${
                      activeLanguage === lang.id
                        ? 'border-primary text-primary'
                        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                    }`}
                  >
                    {lang.name}
                  </button>
                ))}
              </nav>
            </div>

            {/* Code Display */}
            <div className="relative">
              <CodeBlock code={generateCode()} language={activeLanguage} />
              <button
                onClick={copyToClipboard}
                className="absolute top-2 right-2 inline-flex items-center px-3 py-1 border border-transparent text-xs font-medium rounded-md text-white bg-gray-700 hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500"
              >
                {copied ? (
                  <>
                    <DocumentDuplicateIcon className="w-4 h-4 mr-1" />
                    Copied!
                  </>
                ) : (
                  <>
                    <DocumentDuplicateIcon className="w-4 h-4 mr-1" />
                    Copy
                  </>
                )}
              </button>
            </div>

            {/* Schema Information */}
            {getSchemaFields().length > 0 && (
              <div className="mt-6">
                <h4 className="text-sm font-medium text-gray-900 mb-2">Expected Payload Schema</h4>
                <div className="bg-gray-50 rounded-lg p-4">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead>
                      <tr>
                        <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Field</th>
                        <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                        <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Description</th>
                        <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Required</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {getSchemaFields().map((field, index) => (
                        <tr key={index}>
                          <td className="py-2 text-sm font-mono text-gray-900">{field.field_name || `field_${index + 1}`}</td>
                          <td className="py-2 text-sm text-gray-500">{field.data_type || 'string'}</td>
                          <td className="py-2 text-sm text-gray-500">{field.description || '-'}</td>
                          <td className="py-2 text-sm text-gray-500">{field.is_required ? 'Yes' : 'No'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Additional Information */}
            <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-blue-900 mb-2">Important Notes:</h4>
              <ul className="list-disc list-inside text-sm text-blue-700 space-y-1">
                {subscription?.invocation_api_key ? (
                  <li>The API key shown is your actual invocation key for this application</li>
                ) : (
                  <li>Replace YOUR_API_KEY with your actual invocation API key (found in Connection Settings)</li>
                )}
                {event.event_type === 'webhook' && (
                  <li>Ensure your webhook endpoint is publicly accessible</li>
                )}
                {event.event_type === 'api_call' && (
                  <li>This API endpoint should be called from your application</li>
                )}
                <li>The sample payload is based on the event's output schema</li>
                <li>Modify the payload values according to your actual data</li>
                <li>You can use either X-API-Key header or Authorization: Bearer header</li>
              </ul>
            </div>
            </>
            )}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export default ApplicationDetails;