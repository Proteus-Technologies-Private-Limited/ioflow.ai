import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CheckCircleIcon, XCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

const OAuth2Callback = () => {
  const [searchParams] = useSearchParams();
  const [status, setStatus] = useState('processing');
  const [countdown, setCountdown] = useState(3);

  const authResult = searchParams.get('auth');
  const appName = searchParams.get('app');
  const error = searchParams.get('error');
  const errorDescription = searchParams.get('description');

  useEffect(() => {
    if (authResult === 'success') {
      setStatus('success');
      // Start countdown to close window
      const interval = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(interval);
            // Try to close the popup window
            if (window.opener && !window.opener.closed) {
              window.opener.postMessage({ type: 'oauth-success', app: appName }, '*');
            }
            window.close();
            // If window.close() doesn't work, show message
            setTimeout(() => {
              setStatus('close-manually');
            }, 500);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      return () => clearInterval(interval);
    } else if (authResult === 'error') {
      setStatus('error');
      // Notify parent window about the error
      if (window.opener && !window.opener.closed) {
        window.opener.postMessage({ type: 'oauth-error', error: error || 'Authorization failed' }, '*');
      }
    }
  }, [authResult, appName]);

  const handleCloseWindow = () => {
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage({ type: 'oauth-close', status: authResult }, '*');
    }
    window.close();
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        {status === 'processing' && (
          <div className="text-center">
            <ArrowPathIcon className="mx-auto h-12 w-12 text-gray-400 animate-spin" />
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
              Processing OAuth2 callback...
            </h2>
          </div>
        )}

        {status === 'success' && (
          <div className="text-center">
            <CheckCircleIcon className="mx-auto h-12 w-12 text-green-500" />
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
              Successfully connected!
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              You have successfully connected to {appName || 'the application'}.
            </p>
            <p className="mt-4 text-sm text-gray-500">
              This window will close in {countdown} seconds...
            </p>
            <button
              onClick={handleCloseWindow}
              className="mt-4 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              Close Window Now
            </button>
          </div>
        )}

        {status === 'error' && (
          <div className="text-center">
            <XCircleIcon className="mx-auto h-12 w-12 text-red-500" />
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
              Connection Failed
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              {errorDescription || error || 'OAuth2 authorization failed'}
            </p>
            <button
              onClick={handleCloseWindow}
              className="mt-6 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
            >
              Close Window
            </button>
          </div>
        )}

        {status === 'close-manually' && (
          <div className="text-center">
            <CheckCircleIcon className="mx-auto h-12 w-12 text-green-500" />
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
              Connection Successful!
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              You can now close this window and return to IOFlow.
            </p>
            <button
              onClick={() => window.close()}
              className="mt-6 inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              Close Window
            </button>
          </div>
        )}
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <div className="text-center text-sm text-gray-500">
            <p>This is the OAuth2 callback handler for IOFlow.</p>
            <p className="mt-2">
              If this window doesn't close automatically, you can close it manually.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OAuth2Callback;