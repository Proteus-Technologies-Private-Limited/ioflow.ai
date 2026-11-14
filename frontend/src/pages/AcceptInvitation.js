import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import axios from 'axios';
import { API_BASE_URL } from '../config';
import logo from '../assets/logo.png';

const AcceptInvitation = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [invitationData, setInvitationData] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const { register, handleSubmit, formState: { errors }, watch } = useForm();
  const password = watch('password');

  useEffect(() => {
    if (token) {
      validateToken();
    } else {
      setError('No invitation token provided');
      setLoading(false);
    }
  }, [token]);

  const validateToken = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/invitations/validate/${token}`);
      if (response.data.valid) {
        setInvitationData(response.data);
      } else {
        setError(response.data.error || 'Invalid invitation');
      }
    } catch (err) {
      console.error('Failed to validate invitation:', err);
      setError('Failed to validate invitation. Please try again or contact support.');
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = async (data) => {
    setSubmitting(true);
    setError('');

    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/invitations/accept`, {
        token: token,
        username: data.username,
        password: data.password
      });

      setSuccess(true);

      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login', {
          state: {
            message: 'Account created successfully! Please sign in.',
            email: invitationData.email
          }
        });
      }, 3000);

    } catch (err) {
      console.error('Failed to accept invitation:', err);
      setError(err.response?.data?.detail || 'Failed to create account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const getRoleLabel = (role) => {
    const labels = {
      'INSTANCE_ADMIN': 'Instance Admin',
      'TENANT_ADMIN': 'Tenant Admin',
      'FLOW_DESIGNER': 'Flow Designer',
      'FLOW_EXECUTOR': 'Flow Executor',
      'EXECUTION_MONITOR': 'Execution Monitor',
      'APPLICATION_PROVIDER': 'Application Provider'
    };
    return labels[role] || role;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-600">Validating invitation...</p>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 text-center">
          <div className="flex justify-center mb-4">
            <img src={logo} alt="IOFlow" className="h-16 w-16" />
          </div>
          <div className="rounded-md bg-green-50 p-6">
            <div className="flex justify-center mb-4">
              <svg className="h-12 w-12 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-green-800 mb-2">Account Created!</h2>
            <p className="text-green-700 mb-4">
              Your account has been created successfully. You will be redirected to the login page shortly.
            </p>
            <Link
              to="/login"
              className="inline-flex items-center text-primary hover:text-primary-dark font-medium"
            >
              Go to Login
              <svg className="ml-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (error && !invitationData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 text-center">
          <div className="flex justify-center mb-4">
            <img src={logo} alt="IOFlow" className="h-16 w-16" />
          </div>
          <div className="rounded-md bg-red-50 p-6">
            <div className="flex justify-center mb-4">
              <svg className="h-12 w-12 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h2 className="text-xl font-bold text-red-800 mb-2">Invalid Invitation</h2>
            <p className="text-red-700 mb-4">{error}</p>
            <Link
              to="/login"
              className="inline-flex items-center text-primary hover:text-primary-dark font-medium"
            >
              <svg className="mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    );
  }

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
            Accept Invitation
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            You've been invited to join <span className="font-semibold text-primary">{invitationData?.tenant_name}</span>
          </p>
        </div>

        {/* Invitation Details */}
        <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Invited by:</span>
              <span className="text-sm font-medium text-gray-900">{invitationData?.inviter_name}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Your email:</span>
              <span className="text-sm font-medium text-gray-900">{invitationData?.email}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Role:</span>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-10 text-primary">
                {getRoleLabel(invitationData?.role)}
              </span>
            </div>
          </div>
          {invitationData?.message && (
            <div className="mt-3 pt-3 border-t border-blue-200">
              <p className="text-sm text-gray-600 italic">"{invitationData.message}"</p>
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="rounded-md bg-red-50 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-800">{error}</p>
              </div>
            </div>
          </div>
        )}

        <form className="mt-6 space-y-6" onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-1">
                Your Name
              </label>
              <input
                {...register('username', {
                  required: 'Name is required',
                  minLength: {
                    value: 2,
                    message: 'Name must be at least 2 characters'
                  }
                })}
                type="text"
                autoComplete="name"
                className="input-primary sm:text-sm"
                placeholder="Enter your full name"
              />
              {errors.username && (
                <p className="mt-1 text-xs text-red-600">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                {...register('password', {
                  required: 'Password is required',
                  minLength: {
                    value: 8,
                    message: 'Password must be at least 8 characters'
                  },
                  maxLength: {
                    value: 72,
                    message: 'Password cannot exceed 72 characters'
                  }
                })}
                type="password"
                autoComplete="new-password"
                className="input-primary sm:text-sm"
                placeholder="Create a password"
              />
              {errors.password && (
                <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
              )}
              <p className="mt-1 text-xs text-gray-500">Must be between 8 and 72 characters</p>
            </div>

            <div>
              <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700 mb-1">
                Confirm Password
              </label>
              <input
                {...register('confirmPassword', {
                  required: 'Please confirm your password',
                  validate: value => value === password || 'Passwords do not match'
                })}
                type="password"
                autoComplete="new-password"
                className="input-primary sm:text-sm"
                placeholder="Confirm your password"
              />
              {errors.confirmPassword && (
                <p className="mt-1 text-xs text-red-600">{errors.confirmPassword.message}</p>
              )}
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={submitting}
              className="btn-primary w-full py-2.5 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? 'Creating Account...' : 'Accept Invitation & Create Account'}
            </button>
          </div>

          <p className="text-center text-sm text-gray-500">
            Already have an account?{' '}
            <Link to="/login" className="link-primary font-medium">
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
};

export default AcceptInvitation;
