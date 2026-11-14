import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { EnvelopeIcon, ArrowLeftIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import toast from 'react-hot-toast';
import logo from '../../assets/logo.png';

const ForgotPassword = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const { register, handleSubmit, formState: { errors }, watch } = useForm();
  const email = watch('email');

  const onSubmit = async (data) => {
    setLoading(true);
    try {
      await axios.post('/api/password/forgot', { email: data.email });
      setSuccess(true);
      toast.success('Password reset link sent to your email');
    } catch (error) {
      toast.error((error.response?.data?.message || error.response?.data?.detail) || 'Failed to send reset link. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <div className="flex justify-center mb-4">
              <div className="bg-green-100 rounded-full p-3">
                <EnvelopeIcon className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
              Check Your Email
            </h2>
            <p className="mt-2 text-sm text-gray-600">
              If an account exists with <span className="font-medium">{email}</span>, 
              we've sent a password reset link.
            </p>
            <p className="mt-4 text-xs text-gray-500">
              The link will expire in 1 hour. Please check your spam folder if you don't see the email.
            </p>
          </div>
          
          <div className="mt-8">
            <Link
              to="/login"
              className="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
            >
              <ArrowLeftIcon className="h-5 w-5 mr-2" />
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
        <div>
          <div className="flex justify-center mb-4">
            <img src={logo} alt="IOFlow" className="h-16 w-16" />
          </div>
          <h2 className="text-center text-3xl font-extrabold text-gray-900">
            Forgot Password
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Enter your email address and we'll send you a link to reset your password.
          </p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleSubmit(onSubmit)}>
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
              className="appearance-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 focus:z-10 sm:text-sm"
              placeholder="Enter your email"
              disabled={loading}
            />
            {errors.email && (
              <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
            )}
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Sending...' : 'Send Reset Link'}
            </button>
          </div>

          <div className="text-center">
            <Link
              to="/login"
              className="font-medium text-primary-600 hover:text-primary-500 text-sm inline-flex items-center"
            >
              <ArrowLeftIcon className="h-4 w-4 mr-1" />
              Back to Login
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ForgotPassword;