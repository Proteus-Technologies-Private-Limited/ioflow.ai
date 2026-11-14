import React, { useState } from 'react';
import { ArrowTopRightOnSquareIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast, showWarningToast, showInfoToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const OAuth2FlowButton = ({ application, subscription, onSuccess, credentials, webhookUrl, subscriptionConfig }) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isRevoking, setIsRevoking] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);

  const checkConnectionStatus = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/oauth2/status/${application.app_id}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      setConnectionStatus(response.data);
      return response.data;
    } catch (error) {
      console.error('Error checking OAuth2 status:', error);
      // Check if app has default credentials even without subscription
      const hasDefaults = application.auth_config?.default_credentials?.client_id && 
                         application.auth_config?.default_credentials?.client_secret;
      setConnectionStatus({ connected: false, has_credentials: hasDefaults });
      return { connected: false, has_credentials: hasDefaults };
    }
  };

  React.useEffect(() => {
    checkConnectionStatus();
  }, [application.app_id]);

  const forceReconnect = async () => {
    setIsRevoking(true);
    
    try {
      const token = localStorage.getItem('access_token');
      
      // First revoke existing tokens
      const revokeResponse = await axios.post(
        `${API_BASE_URL}/api/v1/oauth2/revoke/${application.app_id}`,
        {},
        {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );
      
      if (revokeResponse.data.success) {
        showSuccessToast('Tokens revoked successfully. Reconnecting...');
        // Wait a moment before initiating new flow
        setTimeout(() => {
          initiateOAuth2Flow();
        }, 1000);
      }
    } catch (error) {
      console.error('Error revoking tokens:', error);
      // If revocation fails, still try to connect
      showWarningToast('Could not revoke tokens, but trying to reconnect anyway...');
      setTimeout(() => {
        initiateOAuth2Flow();
      }, 1000);
    } finally {
      setIsRevoking(false);
    }
  };

  const initiateOAuth2Flow = async () => {
    setIsLoading(true);
    
    // Check if we have credentials (either passed in, from subscription, or default app credentials)
    const hasProvidedCreds = credentials && credentials.client_id && credentials.client_secret;
    const hasDefaultCreds = application.auth_config?.default_credentials?.client_id && 
                           application.auth_config?.default_credentials?.client_secret;
    
    // First, ensure we have a valid subscription with credentials (if no credentials provided)
    if (!hasProvidedCreds && !hasDefaultCreds) {
      const status = await checkConnectionStatus();
      if (!status?.has_credentials) {
        showErrorToast('Please configure OAuth2 credentials first');
        setIsLoading(false);
        return;
      }
    }
    
    try {
      const token = localStorage.getItem('access_token');
      const currentUrl = window.location.href.split('?')[0]; // Remove query params
      
      console.log('Initiating OAuth2 flow for app:', application.app_id);
      console.log('Has subscription:', !!subscription);
      console.log('Has provided credentials:', hasProvidedCreds);
      console.log('Has default credentials:', hasDefaultCreds);
      
      // Build params for authorization
      const params = {
        app_id: application.app_id,
        redirect_uri: currentUrl
      };
      
      // If credentials are provided, pass them
      if (hasProvidedCreds) {
        params.use_custom_credentials = true;
        params.client_id = credentials.client_id;
        params.client_secret = credentials.client_secret;
      }
      
      // Add webhook URL and subscription config if provided
      if (webhookUrl !== undefined) {
        params.webhook_url = webhookUrl;
      }
      if (subscriptionConfig) {
        params.subscription_config = JSON.stringify(subscriptionConfig);
      }
      
      // Get authorization URL from backend
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/oauth2/authorize`,
        {
          params,
          headers: {
            'Authorization': `Bearer ${token}`
          }
        }
      );

      console.log('OAuth authorize response:', response.data);
      const { authorization_url, use_popup } = response.data;

      if (use_popup) {
        // Open OAuth flow in popup
        const width = 600;
        const height = 700;
        const left = (window.screen.width - width) / 2;
        const top = (window.screen.height - height) / 2;
        
        const popup = window.open(
          authorization_url,
          'oauth2_popup',
          `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=yes`
        );
        
        if (!popup || popup.closed || typeof popup.closed === 'undefined') {
          // Popup was blocked, fall back to redirect
          console.warn('Popup blocked, falling back to redirect');
          showWarningToast('Popup was blocked. Redirecting to authorization page...');
          setTimeout(() => {
            window.location.href = authorization_url;
          }, 1500);
          return;
        }

        // Listen for messages from the popup
        const messageHandler = (event) => {
          // Verify the message is from our domain
          if (event.origin !== window.location.origin) return;
          
          if (event.data.type === 'oauth-success') {
            window.removeEventListener('message', messageHandler);
            setIsLoading(false);
            // Set flag to prevent duplicate success messages
            window._oauth_success_shown = true;
            showSuccessToast(`Successfully connected to ${event.data.app || application.app_name}`);
            checkConnectionStatus();
            if (onSuccess) onSuccess();
          } else if (event.data.type === 'oauth-error') {
            window.removeEventListener('message', messageHandler);
            setIsLoading(false);
            showErrorToast('OAuth2 authorization failed');
          }
        };
        
        window.addEventListener('message', messageHandler);

        // Also check for popup close
        const checkPopup = setInterval(() => {
          if (popup.closed) {
            clearInterval(checkPopup);
            window.removeEventListener('message', messageHandler);
            setIsLoading(false);
            
            // Check if auth was successful after a delay to avoid showing duplicate messages
            setTimeout(() => {
              checkConnectionStatus().then(status => {
                // Only show success if we haven't already shown it from the message handler
                if (status && status.connected && !window._oauth_success_shown) {
                  showSuccessToast(`Successfully connected to ${application.app_name}`);
                  if (onSuccess) onSuccess();
                }
                // Reset the flag
                delete window._oauth_success_shown;
              });
            }, 500);
          }
        }, 1000);
      } else {
        // Redirect to OAuth provider
        window.location.href = authorization_url;
      }
    } catch (error) {
      console.error('Error initiating OAuth2 flow:', error);
      console.error('Error response:', error.response);
      const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || error.message || 'Failed to start OAuth2 authorization';
      showErrorToast(errorMessage);
      
      // If it's a credentials issue, provide more context
      if (error.response?.status === 400 && errorMessage.includes('credentials')) {
        showInfoToast('Please ensure the subscription is created first');
      }
      setIsLoading(false);
    }
  };

  // Check URL params for OAuth callback result
  React.useEffect(() => {
    // Skip if OAuth flow is in progress
    if (sessionStorage.getItem('oauth_flow_in_progress') === 'true') {
      sessionStorage.removeItem('oauth_flow_in_progress');
      return;
    }
    
    const urlParams = new URLSearchParams(window.location.search);
    const authResult = urlParams.get('auth');
    const appName = urlParams.get('app');
    const error = urlParams.get('error');
    const errorDescription = urlParams.get('description');

    if (authResult === 'success') {
      // Only show success message if it's for this specific app
      if (appName === application.app_name || !appName) {
        showSuccessToast(`Successfully connected to ${appName || application.app_name}`);
        // Remove query params
        window.history.replaceState({}, document.title, window.location.pathname);
        // Delay status check to avoid race condition
        setTimeout(() => {
          checkConnectionStatus();
          if (onSuccess) onSuccess();
        }, 1000);
      }
    } else if (authResult === 'error') {
      const errorMessage = errorDescription || error || 'OAuth2 authorization failed';
      showErrorToast(`Failed to connect: ${errorMessage}`);
      // Remove query params
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  // Show button if:
  // 1. We have provided credentials (for new OAuth setup)
  // 2. We have default credentials
  // 3. We have a subscription with credentials
  const hasProvidedCredentials = credentials && credentials.client_id && credentials.client_secret;
  const hasDefaultCredentials = application.auth_type === 'oauth2' && 
    application.auth_config?.default_credentials?.client_id && 
    application.auth_config?.default_credentials?.client_secret;
  
  if (!hasProvidedCredentials && !hasDefaultCredentials && (!subscription || !connectionStatus?.has_credentials)) {
    return null;
  }

  return (
    <div className="space-y-3">
      {/* Connection Status */}
      {connectionStatus && (
        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
          <div className="flex items-center space-x-2">
            {connectionStatus.connected ? (
              <>
                <CheckCircleIcon className="h-5 w-5 text-green-500" />
                <span className="text-sm text-gray-700">Connected</span>
              </>
            ) : (
              <>
                <XCircleIcon className="h-5 w-5 text-gray-400" />
                <span className="text-sm text-gray-700">Not Connected</span>
              </>
            )}
          </div>
          {connectionStatus.connected && connectionStatus.token_expired && (
            <span className="text-xs text-orange-600">Token expired - will refresh automatically</span>
          )}
        </div>
      )}

      {/* OAuth2 Buttons */}
      <div className="space-y-2">
        <button
          onClick={initiateOAuth2Flow}
          disabled={isLoading || isRevoking}
          className={`w-full flex items-center justify-center space-x-2 px-4 py-2 rounded-md transition-colors ${
            connectionStatus?.connected
              ? 'bg-gray-600 hover:bg-gray-700 text-white'
              : 'bg-indigo-600 hover:bg-indigo-700 text-white'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          <ArrowTopRightOnSquareIcon className="h-5 w-5" />
          <span>
            {isLoading 
              ? 'Connecting...' 
              : connectionStatus?.connected 
                ? 'Reconnect with OAuth2' 
                : 'Connect with OAuth2'
            }
          </span>
        </button>

        {/* Force Reconnect Button - Show for Google Sheets when connected */}
        {connectionStatus?.connected && application.app_name === 'Google Sheets' && (
          <button
            onClick={forceReconnect}
            disabled={isLoading || isRevoking}
            className="w-full flex items-center justify-center space-x-2 px-4 py-2 border border-orange-600 text-orange-600 rounded-md hover:bg-orange-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ArrowTopRightOnSquareIcon className="h-5 w-5" />
            <span>
              {isRevoking ? 'Revoking tokens...' : 'Force Reconnect (Revoke & Connect)'}
            </span>
          </button>
        )}
      </div>

      {/* Instructions */}
      <div className="text-xs text-gray-500 text-center mt-2">
        {connectionStatus?.connected ? (
          <>
            <p>You can reconnect to refresh your authorization</p>
            {application.app_name === 'Google Sheets' && (
              <p className="mt-1 text-orange-600">
                If you're having refresh token issues, use "Force Reconnect"
              </p>
            )}
          </>
        ) : (
          <p>You'll be redirected to {application.app_name} to authorize access</p>
        )}
      </div>
    </div>
  );
};

export default OAuth2FlowButton;