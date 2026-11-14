import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useAuth } from '../contexts/AuthContext';
import { showSuccessToast } from '../utils/customToast';
import { API_BASE_URL } from '../config';
import logo from '../assets/logo.png';

const Register = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { register: registerUser, activate } = useAuth();
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleConfigured, setGoogleConfigured] = useState(false);
  const [showActivation, setShowActivation] = useState(false);
  const [email, setEmail] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const { register, handleSubmit, formState: { errors }, watch } = useForm();
  const { register: registerActivation, handleSubmit: handleActivationSubmit, formState: { errors: activationErrors } } = useForm();
  
  const password = watch('password');

  useEffect(() => {
    // Check if Google OAuth is configured
    checkGoogleOAuthStatus();
    
    // Check for OAuth error messages in URL
    const params = new URLSearchParams(location.search);
    const error = params.get('error');
    const message = params.get('message');
    
    if (error) {
      let errorText = message ? message.replace(/_/g, ' ') : '';
      
      switch (error) {
        case 'oauth_error':
          setErrorMessage(errorText || 'Failed to create account. Please try again.');
          break;
        case 'signup_failed':
          setErrorMessage(errorText || 'Failed to create account with Google.');
          break;
        default:
          setErrorMessage('An error occurred during signup. Please try again.');
      }
      
      // Clear the URL parameters
      navigate('/register', { replace: true });
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

  const handleGoogleSignup = async () => {
    setGoogleLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/google/signup`);
      const data = await response.json();
      
      if (data.auth_url) {
        // Redirect to Google OAuth
        window.location.href = data.auth_url;
      }
    } catch (error) {
      console.error('Failed to initiate Google signup:', error);
      alert('Failed to connect with Google. Please try again.');
    } finally {
      setGoogleLoading(false);
    }
  };

  const onSubmit = async (data) => {
    setLoading(true);
    try {
      // Check if the organization field looks like a UUID (tenant ID)
      const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.organization);
      
      const registrationData = {
        email: data.email,
        username: data.username,
        password: data.password,
      };
      
      // If it looks like a UUID, send it as tenant_id, otherwise as organization
      if (isUUID) {
        registrationData.tenant_id = data.organization;
      } else {
        registrationData.organization = data.organization;
      }
      
      const response = await registerUser(registrationData);
      
      // Handle different response statuses
      if (response.status === 'activated') {
        // User is already activated, redirect to login
        setTimeout(() => navigate('/login'), 2000);
      } else if (response.status === 'unactivated' || response.status === 'registered') {
        // Show activation form
        setEmail(data.email);
        setShowActivation(true);
      }
    } catch (error) {
      console.error('Registration failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const onActivate = async (data) => {
    setLoading(true);
    try {
      await activate(email, data.activationCode);
      navigate('/login');
    } catch (error) {
      console.error('Activation failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const resendActivationCode = async () => {
    setLoading(true);
    try {
      const response = await registerUser({
        email: email,
        username: 'dummy', // This will be updated with existing username
        password: 'dummy123', // This will be updated with existing password
        organization: 'dummy',
      });
      
      if (response.status === 'unactivated') {
        showSuccessToast('Activation code resent! Check your email.');
      }
    } catch (error) {
      console.error('Failed to resend activation code:', error);
    } finally {
      setLoading(false);
    }
  };

  if (showActivation) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div>
            <div className="flex justify-center mb-4">
              <img src={logo} alt="IOFlow" className="h-16 w-16" />
            </div>
            <h2 className="text-center text-3xl font-extrabold text-gray-900">
              Activate Your Account
            </h2>
            <p className="mt-2 text-center text-sm text-gray-600">
              We've sent an activation code to {email}
            </p>
          </div>
          <form className="mt-8 space-y-6" onSubmit={handleActivationSubmit(onActivate)}>
            <div>
              <label htmlFor="activationCode" className="block text-sm font-medium text-gray-700">
                Activation Code
              </label>
              <input
                {...registerActivation('activationCode', { 
                  required: 'Activation code is required',
                  minLength: { value: 6, message: 'Activation code must be 6 characters' },
                  maxLength: { value: 6, message: 'Activation code must be 6 characters' }
                })}
                type="text"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm transition-colors"
                placeholder="Enter 6-digit code"
              />
              {activationErrors.activationCode && (
                <p className="mt-1 text-xs text-red-600">{activationErrors.activationCode.message}</p>
              )}
            </div>

            <div>
              <button
                type="submit"
                disabled={loading}
                className="group relative w-full flex justify-center py-2.5 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
              >
                {loading ? 'Activating...' : 'Activate Account'}
              </button>
            </div>

            <div className="text-center">
              <button
                type="button"
                onClick={resendActivationCode}
                disabled={loading}
                className="text-sm text-primary hover:text-secondary transition-colors"
              >
                Didn't receive the code? Resend
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <div className="flex justify-center mb-4">
            <img src={logo} alt="IOFlow" className="h-16 w-16" />
          </div>
          <h2 className="text-center text-3xl font-extrabold text-gray-900">
            Create your account
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Or{' '}
            <Link to="/login" className="font-medium text-primary hover:text-secondary transition-colors">
              sign in to your existing account
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
          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email address
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
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm transition-colors"
                placeholder="Email address"
              />
              {errors.email && (
                <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                Username
              </label>
              <input
                {...register('username', { 
                  required: 'Username is required',
                  minLength: { value: 3, message: 'Username must be at least 3 characters' }
                })}
                type="text"
                autoComplete="username"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm transition-colors"
                placeholder="Username"
              />
              {errors.username && (
                <p className="mt-1 text-xs text-red-600">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="organization" className="block text-sm font-medium text-gray-700">
                Organization / Tenant ID
              </label>
              <input
                {...register('organization', { 
                  required: 'Organization or Tenant ID is required',
                  minLength: { value: 2, message: 'Must be at least 2 characters' }
                })}
                type="text"
                autoComplete="organization"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm transition-colors"
                placeholder="Enter organization name or tenant ID"
              />
              <p className="mt-1 text-xs text-gray-500">
                <strong>New organization?</strong> Enter your organization name and IOFlow will create a new tenant for you.<br />
                <strong>Joining existing tenant?</strong> Enter the specific Tenant ID provided by your administrator to register as a user in that organization.
              </p>
              {errors.organization && (
                <p className="mt-1 text-xs text-red-600">{errors.organization.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                {...register('password', { 
                  required: 'Password is required',
                  minLength: { value: 8, message: 'Password must be at least 8 characters' }
                })}
                type="password"
                autoComplete="new-password"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm transition-colors"
                placeholder="Password"
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
                Confirm Password
              </label>
              <input
                {...register('confirmPassword', { 
                  required: 'Please confirm your password',
                  validate: value => value === password || 'Passwords do not match'
                })}
                type="password"
                autoComplete="new-password"
                className="mt-1 appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary focus:border-primary focus:z-10 sm:text-sm transition-colors"
                placeholder="Confirm password"
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-xs text-red-600">{errors.confirmPassword.message}</p>
              )}
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-2.5 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-300"
            >
              {loading ? 'Creating account...' : 'Create account'}
            </button>
          </div>

          {googleConfigured && (
            <>
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-300" />
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-gray-50 text-gray-500">Or continue with</span>
                </div>
              </div>

              <div>
                <button
                  type="button"
                  onClick={handleGoogleSignup}
                  disabled={googleLoading}
                  className="w-full flex justify-center items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  {googleLoading ? 'Connecting...' : 'Sign up with Google'}
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  );
};

export default Register;