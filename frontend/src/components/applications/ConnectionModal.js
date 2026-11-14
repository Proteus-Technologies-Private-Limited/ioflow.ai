import React, { useState, useEffect } from 'react';
import { 
  XMarkIcon, 
  LinkIcon, 
  KeyIcon, 
  Cog6ToothIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  EyeIcon,
  EyeSlashIcon,
  DocumentDuplicateIcon,
  ArrowPathIcon,
  ArrowLeftIcon,
  ArrowRightIcon
} from '@heroicons/react/24/outline';
import axios from 'axios';
import toast from 'react-hot-toast';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';
import OAuth2FlowButton from './OAuth2FlowButton';
import CustomParametersConfig from './CustomParametersConfig';
import { formatDateTime } from '../../utils/dateFormatter';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const ConnectionModal = ({ application, subscription, onClose, onSuccess }) => {
  const [activeTab, setActiveTab] = useState('incoming');
  const [isLoading, setIsLoading] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [credentialSchema, setCredentialSchema] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});
  const [currentSubscription, setCurrentSubscription] = useState(subscription);
  const [hasDefaultOAuthCredentials, setHasDefaultOAuthCredentials] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const [isRegeneratingKey, setIsRegeneratingKey] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    webhook_url: subscription?.webhook_url || '',
    base_url: subscription?.subscription_config?.base_url || application?.base_url || '',
    use_custom_credentials: false,
    auth_credentials: {},
    custom_params: {},
    test_endpoint: subscription?.subscription_config?.test_endpoint || application?.auth_config?.test_endpoint || ''
  });

  // Fetch credential schema when modal opens
  useEffect(() => {
    const fetchSchema = async () => {
      try {
        const token = localStorage.getItem('access_token');
        const response = await axios.get(
          `${API_BASE_URL}/api/v1/applications/${application.app_id}/credential-schema`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        setCredentialSchema(response.data);
        
        // Initialize auth_credentials with default values from schema
        if (response.data?.credential_schema?.properties && !subscription) {
          const defaultCreds = {};
          Object.entries(response.data.credential_schema.properties).forEach(([key, field]) => {
            if (field.default !== undefined) {
              defaultCreds[key] = field.default;
            }
          });
          if (Object.keys(defaultCreds).length > 0) {
            setFormData(prev => ({
              ...prev,
              auth_credentials: { ...defaultCreds, ...prev.auth_credentials }
            }));
          }
        }
        
        // Check if OAuth2 app has default credentials
        if (application.auth_type === 'oauth2' && response.data?.has_default_credentials) {
          setHasDefaultOAuthCredentials(true);
        }
        
        // Set default state based on existing subscription
        if (subscription) {
          const isUsingDefaults = subscription.subscription_config?.using_default_credentials;
          
          // Handle masked credentials - extract header config for API key auth
          let authCreds = {};
          if (subscription.auth_credentials?.masked && subscription.auth_credentials?.header_config) {
            // For API key auth, use the header config from masked response
            authCreds = {
              api_key: '', // Don't show the actual API key
              header_name: subscription.auth_credentials.header_config.header_name,
              header_prefix: subscription.auth_credentials.header_config.header_prefix
            };
          } else if (!subscription.auth_credentials?.masked) {
            // If not masked, use as is
            authCreds = subscription.auth_credentials || {};
          }
          
          setFormData(prev => ({
            ...prev,
            use_custom_credentials: !isUsingDefaults,
            auth_credentials: authCreds,
            custom_params: subscription.subscription_config?.custom_params || {},
            test_endpoint: subscription.subscription_config?.test_endpoint || ''
          }));
        }
      } catch (error) {
        console.error('Failed to fetch credential schema:', error);
      }
    };

    if (application?.app_id) {
      fetchSchema();
    }
  }, [application, subscription]);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleCredentialChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      auth_credentials: {
        ...prev.auth_credentials,
        [field]: value
      },
      // For OAuth2, automatically set use_custom_credentials to true when credentials are entered
      use_custom_credentials: application.auth_type === 'oauth2' && (value || prev.auth_credentials.client_id || prev.auth_credentials.client_secret) ? true : prev.use_custom_credentials
    }));
  };

  const handleCustomParamsChange = (params) => {
    setFormData(prev => ({
      ...prev,
      custom_params: params
    }));
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    try {
      const token = localStorage.getItem('access_token');
      
      // Check if we should use stored credentials
      let useStoredCredentials = false;
      let authCredentials = {};
      
      // For OAuth2, check if we should use default credentials
      if (application.auth_type === 'oauth2') {
        if (!formData.use_custom_credentials) {
          // Backend will use default credentials
          authCredentials = null;
        } else {
          authCredentials = formData.auth_credentials;
        }
      } else {
        // For non-OAuth2, check if credentials are provided
        authCredentials = { ...formData.auth_credentials };
        
        // Check if we should use stored credentials
        if (application.auth_type === 'api_key' && 
            (!authCredentials.api_key || authCredentials.api_key === '') && 
            currentSubscription?.auth_credentials?.has_credentials) {
          useStoredCredentials = true;
          authCredentials = null; // Don't send empty credentials
        }
      }
      
      // Handle test endpoint URL
      let testEndpoint = formData.test_endpoint || application?.auth_config?.test_endpoint || '';
      let baseUrl = formData.base_url || application.base_url;
      
      // If test endpoint is absolute URL, use it as base URL and empty endpoint
      if (testEndpoint.startsWith('http://') || testEndpoint.startsWith('https://')) {
        baseUrl = testEndpoint;
        testEndpoint = '';
      }
      
      // Build test payload
      const testPayload = {
        base_url: baseUrl,
        test_endpoint: testEndpoint,
        auth_type: application.auth_type,
        auth_config: application.auth_config || {},
        method: 'GET',
        timeout: 10,
        headers: formData.custom_params.header || {}
      };
      
      // If using stored credentials, add subscription_id
      if (useStoredCredentials && currentSubscription?.subscription_id) {
        testPayload.subscription_id = currentSubscription.subscription_id;
      } else if (authCredentials !== null && authCredentials !== undefined) {
        // Merge custom parameters with auth credentials
        let mergedCredentials = { ...authCredentials };
        
        // Add custom headers if any
        if (formData.custom_params.header) {
          mergedCredentials.headers = {
            ...(mergedCredentials.headers || {}),
            ...formData.custom_params.header
          };
        }
        
        // Add custom query params if any
        if (formData.custom_params.query) {
          mergedCredentials.query_params = {
            ...(mergedCredentials.query_params || {}),
            ...formData.custom_params.query
          };
        }
        
        // Add custom body params if any
        if (formData.custom_params.body) {
          mergedCredentials.body_params = {
            ...(mergedCredentials.body_params || {}),
            ...formData.custom_params.body
          };
        }
        
        testPayload.auth_credentials = mergedCredentials;
      }

      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/test-connection`,
        testPayload,
        { headers: { Authorization: `Bearer ${token}` } }
      );

      if (response.data.success) {
        showSuccessToast('Connection test successful!');
        if (useStoredCredentials) {
          toast('Used stored credentials for testing', {
            duration: 3000,
            icon: '🔐'
          });
        }
      } else {
        showErrorToast(response.data.error || 'Connection test failed');
      }
    } catch (error) {
      showErrorToast('Connection test failed: ' + ((error.response?.data?.message || error.response?.data?.detail) || error.message));
    } finally {
      setIsTesting(false);
    }
  };

  const handleCopyApiKey = () => {
    if (currentSubscription?.invocation_api_key) {
      navigator.clipboard.writeText(currentSubscription.invocation_api_key);
      showSuccessToast('API key copied to clipboard!');
    }
  };

  const handleRegenerateApiKey = async () => {
    if (!window.confirm('Are you sure you want to regenerate the API key? The old key will stop working immediately.')) {
      return;
    }

    setIsRegeneratingKey(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/applications/subscriptions/${currentSubscription.subscription_id}/regenerate-api-key`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );

      showSuccessToast('API key regenerated successfully!');
      
      // Update the subscription with the new API key
      setCurrentSubscription({
        ...currentSubscription,
        invocation_api_key: response.data.invocation_api_key,
        api_key_created_at: response.data.api_key_created_at
      });
      
      if (onSuccess) {
        onSuccess();
      }
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to regenerate API key');
    } finally {
      setIsRegeneratingKey(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      
      // For OAuth2, determine which credentials to use
      let authCredentials = null;
      if (application.auth_type === 'oauth2') {
        // If user has entered credentials, use them
        if (formData.auth_credentials.client_id && formData.auth_credentials.client_secret) {
          authCredentials = formData.auth_credentials;
        }
        // Otherwise, backend will use default credentials if available
      } else {
        // For non-OAuth2, handle credentials properly
        authCredentials = { ...formData.auth_credentials };
        
        // For API key auth, if the key is empty and we have stored credentials, remove the empty key
        if (application.auth_type === 'api_key' && authCredentials.api_key === '' && 
            subscription?.auth_credentials?.has_credentials) {
          // Remove empty api_key to let backend use stored one
          delete authCredentials.api_key;
        }
      }
      
      // For OAuth2 applications, start the OAuth flow immediately
      if (application.auth_type === 'oauth2' && !subscription) {
        console.log('OAuth2 flow - formData:', formData);
        console.log('OAuth2 flow - authCredentials:', authCredentials);
        console.log('OAuth2 flow - hasDefaultOAuthCredentials:', hasDefaultOAuthCredentials);
        
        // Start OAuth flow directly
        try {
          const currentUrl = window.location.href.split('?')[0];
          
          // Build params for authorization
          const params = {
            app_id: application.app_id,
            redirect_uri: currentUrl,
            webhook_url: formData.webhook_url,
            subscription_config: JSON.stringify({
              base_url: formData.base_url,
              custom_params: formData.custom_params,
              test_endpoint: formData.test_endpoint
            })
          };
          
          // If user has provided credentials, add them
          if (authCredentials && authCredentials.client_id && authCredentials.client_secret) {
            params.use_custom_credentials = true;
            params.client_id = authCredentials.client_id;
            params.client_secret = authCredentials.client_secret;
            console.log('Using custom credentials:', params.client_id);
          } else {
            console.log('No custom credentials provided, will use defaults if available');
          }
          
          // Get authorization URL from backend
          const response = await axios.get(
            `${API_BASE_URL}/api/v1/oauth2/authorize`,
            {
              params,
              headers: { Authorization: `Bearer ${token}` }
            }
          );
          
          const { authorization_url, use_popup } = response.data;
          
          // Show message about redirection
          toast('Redirecting to authorization...', { duration: 2000 });
          
          // Handle OAuth flow (popup or redirect)
          if (use_popup) {
            const width = 600;
            const height = 700;
            const left = (window.screen.width - width) / 2;
            const top = (window.screen.height - height) / 2;
            
            const popup = window.open(
              authorization_url,
              'oauth2_popup',
              `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
            );
            
            if (!popup || popup.closed) {
              // Popup blocked, use redirect
              setTimeout(() => {
                window.location.href = authorization_url;
              }, 1500);
              return;
            }
            
            // Listen for popup completion
            const messageHandler = (event) => {
              if (event.origin !== window.location.origin) return;
              
              if (event.data.type === 'oauth-success') {
                window.removeEventListener('message', messageHandler);
                showSuccessToast(`Successfully connected to ${application.app_name}`);
                if (onSuccess) onSuccess();
                onClose();
              } else if (event.data.type === 'oauth-error') {
                window.removeEventListener('message', messageHandler);
                showErrorToast('OAuth2 authorization failed');
                setIsLoading(false);
              }
            };
            
            window.addEventListener('message', messageHandler);
            
            // Check for popup close
            const checkPopup = setInterval(() => {
              if (popup.closed) {
                clearInterval(checkPopup);
                window.removeEventListener('message', messageHandler);
                setIsLoading(false);
              }
            }, 1000);
          } else {
            // Direct redirect
            setTimeout(() => {
              window.location.href = authorization_url;
            }, 1500);
          }
        } catch (error) {
          console.error('Failed to start OAuth flow:', error);
          showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to start authorization');
          setIsLoading(false);
        }
        return;
      }
      
      // Validate base URL for database and email applications
      if ((application.app_type === 'database' || application.app_type === 'email') && !formData.base_url) {
        const message = application.app_type === 'database' 
          ? 'Please enter the database connection URL'
          : 'Please enter the email server URL (e.g., smtp://smtp.gmail.com:587)';
        showErrorToast(message);
        setIsLoading(false);
        return;
      }
      
      // Prepare subscription data
      const subscriptionData = {
        app_id: application.app_id,
        webhook_url: formData.webhook_url,
        auth_credentials: authCredentials,
        subscription_config: {
          base_url: formData.base_url,
          custom_params: formData.custom_params,
          test_endpoint: formData.test_endpoint
        },
        status: 'active'
      };

      // Create or update subscription
      let response;
      if (subscription) {
        response = await axios.put(
          `${API_BASE_URL}/api/v1/applications/subscriptions/${subscription.subscription_id}`,
          subscriptionData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
      } else {
        response = await axios.post(
          `${API_BASE_URL}/api/v1/applications/subscriptions/`,
          subscriptionData,
          { headers: { Authorization: `Bearer ${token}` } }
        );
      }
      
      // For existing OAuth subscriptions or non-OAuth apps, proceed normally
      if (application.auth_type === 'oauth2') {
        setCurrentSubscription(response.data);
        
        // Check if OAuth tokens already exist (connected state)
        const hasTokens = response.data.auth_credentials && 
                         (response.data.auth_credentials.access_token || 
                          response.data.auth_credentials.refresh_token);
        
        if (!hasTokens) {
          // Not connected yet - need OAuth authorization
          setActiveTab('outgoing');
          toast('Subscription updated. Now authorize with OAuth2 to complete the connection.', { 
            duration: 5000,
            icon: '⚠️'
          });
          
          // Don't call onSuccess yet - wait for OAuth completion
          return;
        } else {
          // Already has tokens - connection is complete
          showSuccessToast('Connection updated successfully!');
        }
      } else {
        // Non-OAuth2 apps are connected immediately
        showSuccessToast(subscription ? 'Connection updated successfully!' : 'Connected successfully!');
      }

      onSuccess();
    } catch (error) {
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || 'Connection failed';
      showErrorToast(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const renderCredentialFields = () => {
    if (!credentialSchema?.credential_schema?.properties) return null;

    const schema = credentialSchema.credential_schema;
    const hasDefaults = credentialSchema.has_default_credentials;

    return (
      <div className="space-y-4">
        {/* Default credentials indicator */}
        {hasDefaults && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start">
              <InformationCircleIcon className="h-5 w-5 text-blue-400 mt-0.5" />
              <div className="ml-3">
                <p className="text-sm text-blue-800">
                  {credentialSchema.default_credentials_message}
                </p>
                {credentialSchema.credential_help_text && (
                  <p className="text-sm text-blue-600 mt-1">
                    {credentialSchema.credential_help_text}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Toggle for custom credentials */}
        {hasDefaults && (
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg mb-4">
            <div>
              <label className="text-sm font-medium text-gray-700">
                Use custom OAuth credentials
              </label>
              <p className="text-xs text-gray-500 mt-1">
                Enable this to use your own OAuth application credentials instead of the defaults
              </p>
            </div>
            <input
              type="checkbox"
              checked={formData.use_custom_credentials}
              onChange={(e) => handleInputChange('use_custom_credentials', e.target.checked)}
              className="h-4 w-4 text-primary focus:ring-primary border-gray-300 rounded"
            />
          </div>
        )}
        
        {/* Show info when using defaults */}
        {hasDefaults && !formData.use_custom_credentials && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-blue-800">
              Using default OAuth credentials. No need to enter Client ID or Secret.
            </p>
          </div>
        )}

        {/* Info for API key auth about optional fields */}
        {application.auth_type === 'api_key' && credentialSchema?.auth_config && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
            <p className="text-sm text-blue-800">
              <InformationCircleIcon className="h-4 w-4 inline mr-1" />
              Header configuration is optional. If not specified, defaults will be used:
            </p>
            <ul className="text-xs text-blue-700 mt-1 ml-5 list-disc">
              <li>Header Name: {credentialSchema.auth_config.header_name || 'Authorization'}</li>
              <li>Header Prefix: {credentialSchema.auth_config.header_prefix || 'No prefix (API key sent as-is)'}</li>
            </ul>
          </div>
        )}
        
        {/* Info about stored API key when editing */}
        {application.auth_type === 'api_key' && subscription?.auth_credentials?.masked && subscription?.auth_credentials?.has_credentials && (
          <div className="bg-green-50 border border-green-200 rounded-lg p-3 mb-4">
            <p className="text-sm text-green-800">
              <CheckCircleIcon className="h-4 w-4 inline mr-1" />
              API key is already stored securely. Leave the API key field empty to keep using the existing key.
            </p>
          </div>
        )}

        {/* Credential fields */}
        <div className={`space-y-4 ${hasDefaults && !formData.use_custom_credentials ? 'opacity-50 pointer-events-none' : ''}`}>
          {Object.entries(schema.properties).map(([key, field]) => {
            if (key === 'access_token' || key === 'refresh_token' || key === 'expires_at') {
              return null; // Skip OAuth token fields
            }

            const isSecret = key.includes('secret') || key.includes('password');
            const showField = showSecrets[key];

            // Get placeholder based on field
            let placeholder = '';
            if (hasDefaults && !formData.use_custom_credentials) {
              placeholder = 'Using default credentials';
            } else {
              // Use field-specific placeholders
              const placeholders = {
                username: 'Enter your email address',
                email: 'Enter your email address',
                password: 'Enter your password',
                handle_type: 'Select handle type',
                api_key: 'Enter your API key',
                client_id: 'Enter OAuth2 client ID',
                client_secret: 'Enter OAuth2 client secret'
              };
              placeholder = placeholders[key] || `Enter ${field.title || key}`;
              
              // Special handling for API key auth
              if (application.auth_type === 'api_key' && credentialSchema?.auth_config) {
                if (key === 'header_name' && !formData.auth_credentials[key]) {
                  placeholder = credentialSchema.auth_config.header_name || 'Authorization';
                } else if (key === 'header_prefix' && !formData.auth_credentials[key]) {
                  placeholder = credentialSchema.auth_config.header_prefix || 'No prefix';
                }
              }
            }

            // Determine if field is required
            // For basic auth: only username and password are required (private_key, domain are optional)
            // For API key: header_name and header_prefix are optional
            // Check schema's required array to determine if field is required
            const schemaRequired = schema.required || [];
            let isRequired = schemaRequired.includes(key);
            
            // Special cases for API key auth
            if (application.auth_type === 'api_key') {
              if (key === 'header_name' || key === 'header_prefix') {
                isRequired = false; // These are always optional
              } else if (key === 'api_key' && subscription?.auth_credentials?.masked && subscription?.auth_credentials?.has_credentials) {
                isRequired = false; // API key is optional when editing existing subscription
              }
            }
            
            // If there are default credentials and not using custom, nothing is required
            if (hasDefaults && !formData.use_custom_credentials) {
              isRequired = false;
            }

            // Determine input type based on field format
            let inputType = 'text';
            if (isSecret && !showField) {
              inputType = 'password';
            } else if (field.format === 'email') {
              inputType = 'email';
            } else if (field.format === 'url') {
              inputType = 'url';
            } else if (field.type === 'integer' || field.type === 'number') {
              inputType = 'number';
            }

            // Render select for enum fields
            if (field.enum && field.enum.length > 0) {
              return (
                <div key={key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {field.title || key}
                    {field.description && (
                      <span className="text-xs text-gray-500 ml-2">
                        ({field.description})
                      </span>
                    )}
                  </label>
                  <select
                    value={formData.auth_credentials[key] || field.default || ''}
                    onChange={(e) => handleCredentialChange(key, e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
                    required={isRequired}
                  >
                    {!field.default && <option value="">Select {field.title || key}</option>}
                    {field.enum.map(option => (
                      <option key={option} value={option}>
                        {option.charAt(0).toUpperCase() + option.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
              );
            }

            // Check if this should be a textarea (for private_key or other multi-line fields)
            const isTextarea = field.type === 'textarea' || key === 'private_key' || 
                              (field.placeholder && field.placeholder.includes('-----BEGIN'));
            
            return (
              <div key={key}>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {field.title || key}
                  {field.description && (
                    <span className="text-xs text-gray-500 ml-2">
                      ({field.description})
                    </span>
                  )}
                  {/* Show optional/default indicator for API key headers */}
                  {application.auth_type === 'api_key' && (key === 'header_name' || key === 'header_prefix') && (
                    <span className="text-xs text-gray-500 ml-2">
                      (Optional - default: {key === 'header_name' ? credentialSchema?.auth_config?.header_name || 'Authorization' : credentialSchema?.auth_config?.header_prefix || 'No prefix'})
                    </span>
                  )}
                  {/* Show optional indicator for API key when editing */}
                  {application.auth_type === 'api_key' && key === 'api_key' && subscription?.auth_credentials?.masked && subscription?.auth_credentials?.has_credentials && (
                    <span className="text-xs text-gray-500 ml-2">
                      (Optional - leave empty to keep existing key)
                    </span>
                  )}
                </label>
                <div className="relative">
                  {isTextarea ? (
                    <textarea
                      value={formData.auth_credentials[key] || ''}
                      onChange={(e) => handleCredentialChange(key, e.target.value)}
                      placeholder={field.placeholder || placeholder}
                      rows={8}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary font-mono text-sm"
                      required={isRequired}
                    />
                  ) : (
                    <input
                      type={inputType}
                      value={formData.auth_credentials[key] || ''}
                      onChange={(e) => handleCredentialChange(key, e.target.value)}
                      placeholder={
                        key === 'api_key' && subscription?.auth_credentials?.masked && subscription?.auth_credentials?.has_credentials
                          ? 'API key is stored securely (hidden for security)'
                          : placeholder
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
                      required={isRequired}
                    />
                  )}
                  {isSecret && !isTextarea && (
                    <button
                      type="button"
                      onClick={() => setShowSecrets(prev => ({ ...prev, [key]: !prev[key] }))}
                      className="absolute inset-y-0 right-0 pr-3 flex items-center"
                    >
                      {showField ? (
                        <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                      ) : (
                        <EyeIcon className="h-5 w-5 text-gray-400" />
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* OAuth2 flow button for existing subscriptions only */}
        {application.auth_type === 'oauth2' && subscription && (
          <div className="mt-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <div className="flex items-start">
                <InformationCircleIcon className="h-5 w-5 text-blue-400 mt-0.5" />
                <div className="ml-3">
                  <p className="text-sm text-blue-800">
                    To re-authorize or refresh your OAuth connection, use the button below.
                  </p>
                </div>
              </div>
            </div>
            <OAuth2FlowButton
              application={application}
              subscription={currentSubscription}
              onSuccess={onSuccess}
              credentials={formData.use_custom_credentials ? formData.auth_credentials : null}
              webhookUrl={formData.webhook_url}
              subscriptionConfig={{
                base_url: formData.base_url,
                custom_params: formData.custom_params,
                test_endpoint: formData.test_endpoint
              }}
            />
          </div>
        )}
        
        {/* Info for new OAuth connections */}
        {application.auth_type === 'oauth2' && !subscription && (
          <div className="mt-4">
            {hasDefaults && !formData.use_custom_credentials ? (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-start">
                  <CheckCircleIcon className="h-5 w-5 text-green-400 mt-0.5" />
                  <div className="ml-3">
                    <p className="text-sm text-green-800 font-medium">
                      Default OAuth credentials configured
                    </p>
                    <p className="text-sm text-green-700 mt-1">
                      Click "Connect" below to authorize access to your {application.app_name} account.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex items-start">
                  <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400 mt-0.5" />
                  <div className="ml-3">
                    <p className="text-sm text-yellow-800">
                      After entering your OAuth credentials, click "Connect" to authorize access.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9999]">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden z-[9999]">
        <div className="px-6 py-4 border-b bg-gray-50">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-medium text-gray-900">
              {subscription ? 'Update Connection' : 'Connect to'} {application.app_name}
            </h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          {/* Tabs */}
          <div className="border-b">
            <nav className="flex -mb-px">
              <button
                type="button"
                onClick={() => setActiveTab('incoming')}
                className={`py-2 px-6 border-b-2 font-medium text-sm ${
                  activeTab === 'incoming'
                    ? 'border-indigo-500 text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <ArrowLeftIcon className="h-4 w-4 inline mr-2 text-blue-500" />
                Incoming Configuration
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('outgoing')}
                className={`py-2 px-6 border-b-2 font-medium text-sm ${
                  activeTab === 'outgoing'
                    ? 'border-indigo-500 text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <ArrowRightIcon className="h-4 w-4 inline mr-2 text-green-500" />
                Outgoing Configuration
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('advanced')}
                className={`py-2 px-6 border-b-2 font-medium text-sm ${
                  activeTab === 'advanced'
                    ? 'border-indigo-500 text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Cog6ToothIcon className="h-4 w-4 inline mr-2" />
                Advanced
              </button>
            </nav>
          </div>

          <div className="px-6 py-4 overflow-y-auto max-h-[60vh]">
            {/* Incoming Configuration Tab */}
            {activeTab === 'incoming' && (
              <div className="space-y-6">
                {/* Header explanation */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <ArrowLeftIcon className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div className="ml-3">
                      <h4 className="text-sm font-medium text-blue-900">Incoming Configuration</h4>
                      <p className="text-sm text-blue-700 mt-1">
                        Configure how external systems send data TO IOFlow
                      </p>
                    </div>
                  </div>
                </div>

                {/* Invocation API Key Section */}
                {currentSubscription?.invocation_api_key && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-900 mb-3">Invocation API Key</h4>
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                      <div className="flex items-start">
                        <KeyIcon className="w-5 h-5 text-yellow-600 mr-2 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                          <p className="text-sm text-yellow-800 mb-2">
                            Use this API key to authenticate webhook and API calls to IOFlow for this application.
                          </p>
                          <div className="space-y-2">
                            <div className="flex items-center space-x-2">
                              <input
                                type={showApiKey ? 'text' : 'password'}
                                value={currentSubscription.invocation_api_key}
                                readOnly
                                className="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-md font-mono text-sm"
                              />
                              <button
                                type="button"
                                onClick={() => setShowApiKey(!showApiKey)}
                                className="p-2 text-gray-500 hover:text-gray-700"
                                title={showApiKey ? 'Hide API key' : 'Show API key'}
                              >
                                {showApiKey ? (
                                  <EyeSlashIcon className="w-5 h-5" />
                                ) : (
                                  <EyeIcon className="w-5 h-5" />
                                )}
                              </button>
                              <button
                                type="button"
                                onClick={handleCopyApiKey}
                                className="p-2 text-gray-500 hover:text-gray-700"
                                title="Copy API key"
                              >
                                <DocumentDuplicateIcon className="w-5 h-5" />
                              </button>
                              <button
                                type="button"
                                onClick={handleRegenerateApiKey}
                                disabled={isRegeneratingKey}
                                className="p-2 text-yellow-600 hover:text-yellow-700 disabled:opacity-50"
                                title="Regenerate API key"
                              >
                                <ArrowPathIcon className={`w-5 h-5 ${isRegeneratingKey ? 'animate-spin' : ''}`} />
                              </button>
                            </div>
                            {currentSubscription.api_key_created_at && (
                              <p className="text-xs text-gray-500">
                                Created: {formatDateTime(currentSubscription.api_key_created_at)}
                              </p>
                            )}
                            {currentSubscription.api_key_last_used_at && (
                              <p className="text-xs text-gray-500">
                                Last used: {formatDateTime(currentSubscription.api_key_last_used_at)}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Webhook URL Section */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Webhook URL (Where IOFlow receives webhook data)
                  </label>
                  <input
                    type="url"
                    value={formData.webhook_url}
                    onChange={(e) => handleInputChange('webhook_url', e.target.value)}
                    placeholder="https://ioflow.com/webhooks/your-endpoint"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    This is IOFlow's endpoint where external systems should send webhook requests.
                  </p>
                </div>

                {/* Available Event Endpoints */}
                {application.app_events && application.app_events.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Available Event Endpoints</h4>
                    <div className="bg-gray-50 rounded-md p-3">
                      <ul className="space-y-2 text-sm">
                        {application.app_events.map((event) => (
                          <li key={event.event_id} className="flex items-center justify-between">
                            <span className="text-gray-700">{event.display_name}</span>
                            <code className="text-xs bg-gray-200 px-2 py-1 rounded">
                              /api/v1/events/{application.app_id}/{event.event_name}
                            </code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Outgoing Configuration Tab */}
            {activeTab === 'outgoing' && (
              <div className="space-y-6">
                {/* Header explanation */}
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-start">
                    <ArrowRightIcon className="h-5 w-5 text-green-600 mt-0.5" />
                    <div className="ml-3">
                      <h4 className="text-sm font-medium text-green-900">Outgoing Configuration</h4>
                      <p className="text-sm text-green-700 mt-1">
                        Configure how IOFlow sends data TO external systems
                      </p>
                    </div>
                  </div>
                </div>

                {/* Base URL Section */}
                {(application.base_url || application.app_type === 'database' || application.app_type === 'email' || application.auth_type === 'basic') && (() => {
                  // Use ui_config from seed application if available, else fall back to hardcoded logic
                  const uiConfig = application.ui_config?.connection_fields?.base_url;
                  const label = uiConfig?.label || (
                    application.app_type === 'database' ? 'Database Connection URL' :
                    application.app_type === 'email' ? 'Email Server URL' :
                    application.auth_type === 'basic' ? 'Server URL' : 'External API Base URL'
                  );
                  const placeholder = uiConfig?.placeholder || (
                    application.app_type === 'database'
                      ? 'postgresql://username:password@host:port/database'
                      : application.app_type === 'email'
                        ? application.app_services?.some(s => s.service_type === 'smtp_send')
                          ? 'smtp://smtp.gmail.com:587 or smtps://smtp.gmail.com:465'
                          : application.app_services?.some(s => s.service_type === 'pop3_receive')
                            ? 'pop3://pop.gmail.com:110 or pop3s://pop.gmail.com:995'
                            : application.app_services?.some(s => s.service_type === 'imap_receive')
                              ? 'imap://imap.gmail.com:143 or imaps://imap.gmail.com:993'
                              : 'smtp://mail.example.com:587'
                        : application.base_url || 'https://api.example.com'
                  );
                  const helpText = uiConfig?.help_text || (
                    application.app_type === 'database'
                      ? 'Full database connection URL including host, port, and database name. Credentials will be replaced with the authenticated user\'s credentials.'
                      : application.app_type === 'email'
                        ? 'Server URL with protocol and port. Use smtp:// or smtps:// for SMTP, pop3:// or pop3s:// for POP3, imap:// or imaps:// for IMAP. The "s" suffix enables SSL.'
                        : 'Base URL for making API calls to the external system. Services can append paths to this base.'
                  );
                  return (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {label}
                        {(application.app_type === 'database' || application.app_type === 'email') && (
                          <span className="text-red-500 ml-1">*</span>
                        )}
                      </label>
                      <input
                        type="text"
                        value={formData.base_url}
                        onChange={(e) => handleInputChange('base_url', e.target.value)}
                        placeholder={placeholder}
                        required={application.app_type === 'database' || application.app_type === 'email'}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
                      />
                      {application.ui_config?.connection_help_text && (
                        <p className="text-xs text-blue-600 mt-1">{application.ui_config.connection_help_text}</p>
                      )}
                      <p className="text-xs text-gray-500 mt-1">{helpText}</p>
                    </div>
                  );
                })()}

                {/* Test Endpoint Section - Only show for non-OAuth or connected OAuth apps */}
                {(application.auth_type !== 'oauth2' || (subscription && subscription.auth_credentials?.access_token)) && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Test Endpoint (optional)
                    </label>
                    <input
                      type="text"
                      value={formData.test_endpoint}
                      onChange={(e) => handleInputChange('test_endpoint', e.target.value)}
                      placeholder={application?.auth_config?.test_endpoint || "/api/v1/test"}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary focus:border-primary"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Endpoint to test the API connection after authentication (e.g., /health, /api/v1/test)
                    </p>
                    <p className="text-xs text-gray-400 mt-1">
                      Note: This is NOT the OAuth token URL. OAuth endpoints are pre-configured.
                    </p>
                  </div>
                )}

                {/* Authentication Section */}
                <div>
                  <h4 className="text-sm font-medium text-gray-900 mb-3">Authentication for Outgoing API Calls</h4>
                  
                  {/* OAuth Info Box */}
                  {application.auth_type === 'oauth2' && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4">
                      <p className="text-sm text-blue-800">
                        <InformationCircleIcon className="h-4 w-4 inline mr-1" />
                        OAuth endpoints are pre-configured for {application.app_name}:
                      </p>
                      <ul className="text-xs text-blue-700 mt-1 ml-5 list-disc">
                        <li>Authorization URL and Token URL are built-in</li>
                        <li>You only need to provide Client ID and Secret</li>
                        <li>The OAuth flow will handle token exchange automatically</li>
                      </ul>
                    </div>
                  )}
                  
                  {/* Token Exchange Info Box */}
                  {application.auth_type === 'token_exchange' && (
                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 mb-4">
                      <p className="text-sm text-purple-800">
                        <InformationCircleIcon className="h-4 w-4 inline mr-1" />
                        Token Exchange authentication for {application.app_name}:
                      </p>
                      <ul className="text-xs text-purple-700 mt-1 ml-5 list-disc">
                        <li>Your credentials will be exchanged for JWT tokens</li>
                        <li>Tokens will be automatically refreshed before expiry</li>
                        <li>Handle type determines how your username is processed</li>
                      </ul>
                    </div>
                  )}
                  
                  {application.auth_type === 'none' ? (
                    <div className="text-center py-8 text-gray-500">
                      <KeyIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                      <p>No authentication required for this application</p>
                    </div>
                  ) : (
                    renderCredentialFields()
                  )}
                </div>

                {/* Test Connection Button */}
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={isTesting}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
                >
                  {isTesting ? 'Testing...' : 'Test Outgoing Connection'}
                </button>
              </div>
            )}

            {/* Advanced Tab */}
            {activeTab === 'advanced' && (
              <div>
                <CustomParametersConfig
                  parameters={formData.custom_params}
                  onChange={handleCustomParamsChange}
                  onGetPendingParam={() => {}}
                />
              </div>
            )}
          </div>

          <div className="px-6 py-4 bg-gray-50 border-t flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50"
            >
              {isLoading ? (application.auth_type === 'oauth2' && !subscription ? 'Authorizing...' : 'Saving...') : (subscription ? 'Update' : 'Connect')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ConnectionModal;