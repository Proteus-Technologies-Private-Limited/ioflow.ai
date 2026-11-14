import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuth } from '../contexts/AuthContext';
import { API_BASE_URL } from '../config';
import logo from '../assets/logo.png';

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleConfigured, setGoogleConfigured] = useState(false);
  const [twastaAuthorizeUrl, setTwastaAuthorizeUrl] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const { register, handleSubmit, formState: { errors } } = useForm();

  useEffect(() => {
    // Check if Google OAuth is configured
    checkGoogleOAuthStatus();
    // Check if Twasta SSO is configured
    checkTwastaStatus();

    // Check for OAuth error messages in URL
    const params = new URLSearchParams(location.search);
    const error = params.get('error');
    const message = params.get('message');

    if (error) {
      let errorText = message ? message.replace(/_/g, ' ') : '';

      switch (error) {
        case 'oauth_error':
          setErrorMessage(errorText || 'Authentication failed. Please try again.');
          break;
        case 'oauth_failed':
          setErrorMessage(errorText || 'Failed to authenticate with Google.');
          break;
        case 'user_not_found':
          setErrorMessage(errorText || 'No account found. Please sign up first.');
          break;
        default:
          setErrorMessage('An error occurred. Please try again.');
      }

      // Clear the URL parameters but preserve the state
      navigate('/login', { replace: true, state: location.state });
    }
  }, [location, navigate]);

  const checkGoogleOAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/status`);
      const data = await response.json();
      setGoogleConfigured(data.is_configured);
    } catch (error) {
      console.error('Failed to check Google OAuth status:', error);
    }
  };

  const checkTwastaStatus = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/twasta-config`);
      const data = await response.json();
      if (data.enabled && data.authorize_url) {
        setTwastaAuthorizeUrl(data.authorize_url);
      }
    } catch (error) {
      console.error('Failed to check Twasta SSO status:', error);
    }
  };

  const handleTwastaLogin = () => {
    if (!twastaAuthorizeUrl) return;
    // Preserve any post-login destination through the round trip via ?next=
    const redirectUrl = sessionStorage.getItem('redirectAfterLogin');
    const from = redirectUrl || location.state?.from || '';
    let callback = `${window.location.origin}/auth/twasta/callback`;
    if (from && from.startsWith('/')) {
      callback += `?next=${encodeURIComponent(from)}`;
    }
    window.location.href = `${twastaAuthorizeUrl}?redirect_uri=${encodeURIComponent(callback)}`;
  };

  const onSubmit = async (data) => {
    setLoading(true);
    try {
      await login(data.email, data.password);

      // Check sessionStorage for redirect URL first, then location.state, then default to dashboard
      const redirectUrl = sessionStorage.getItem('redirectAfterLogin');
      const from = redirectUrl || location.state?.from || '/dashboard';

      // Clear the stored redirect URL
      sessionStorage.removeItem('redirectAfterLogin');

      console.log('Login successful, redirecting to:', from);
      navigate(from);
    } catch (error) {
      console.error('Login failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setGoogleLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/login`);
      const data = await response.json();

      if (data.auth_url) {
        // Redirect to Google OAuth
        window.location.href = data.auth_url;
      }
    } catch (error) {
      console.error('Failed to initiate Google login:', error);
      alert('Failed to connect with Google. Please try again.');
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Back to Home Link */}
        <div className="flex justify-start">
          <Link
            to="/"
            className="inline-flex items-center text-sm text-gray-500 hover:text-primary transition-colors"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 mr-1"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
            Back to Home
          </Link>
        </div>

        <div>
          <div className="flex justify-center mb-4">
            <img src={logo} alt="IOFlow" className="h-16 w-16" />
          </div>
          <h2 className="text-center text-3xl font-extrabold text-gray-900">
            Sign in to IOFlow
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Or{' '}
            <Link to="/register" className="link-primary font-medium">
              create a new account
            </Link>
          </p>
        </div>

        {/* Error Message */}
        {errorMessage && (
          <div className="rounded-md bg-red-50 p-4 mb-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-800">{errorMessage}</p>
              </div>
              <div className="ml-auto pl-3">
                <button
                  type="button"
                  onClick={() => setErrorMessage('')}
                  className="inline-flex rounded-md bg-red-50 p-1.5 text-red-500 hover:bg-red-100 focus:outline-none"
                >
                  <span className="sr-only">Dismiss</span>
                  <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Success Message */}
        {successMessage && (
          <div className="rounded-md bg-green-50 p-4 mb-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-green-400" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-green-800">{successMessage}</p>
              </div>
            </div>
          </div>
        )}

        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <input type="hidden" name="remember" value="true" />

          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email Address
              </label>
              <input
                {...register('email', {
                  required: 'Email is required',
                  pattern: {
                    value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                    message: 'Invalid email address'
                  }
                })}
                type="email"
                autoComplete="email"
                className="input-primary sm:text-sm"
                placeholder="Enter your email"
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                {...register('password', { required: 'Password is required' })}
                type="password"
                autoComplete="current-password"
                className="input-primary sm:text-sm"
                placeholder="Enter your password"
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                className="checkbox-primary"
              />
              <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-900">
                Remember me
              </label>
            </div>

            <div className="text-sm">
              <Link to="/forgot-password" className="link-primary font-medium">
                Forgot your password?
              </Link>
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
          </div>

          {(googleConfigured || twastaAuthorizeUrl) && (
            <>
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-gray-50 text-gray-500">Or continue with</span>
                </div>
              </div>

              {googleConfigured && (
                <div>
                  <button
                    type="button"
                    onClick={handleGoogleLogin}
                    disabled={googleLoading}
                    className="w-full flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                    {googleLoading ? 'Connecting...' : 'Sign in with Google'}
                  </button>
                </div>
              )}

              {twastaAuthorizeUrl && (
                <div>
                  <button
                    type="button"
                    onClick={handleTwastaLogin}
                    className="w-full flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary transition-colors"
                  >
                    <span className="w-5 h-5 mr-2 rounded bg-indigo-600 text-white text-xs font-bold flex items-center justify-center">T</span>
                    Authenticate with Twasta
                  </button>
                </div>
              )}
            </>
          )}
        </form>
      </div>
    </div>
  );
};

export default Login;
