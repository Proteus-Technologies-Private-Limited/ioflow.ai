import React, { useState } from 'react';
import { useForm } from 'react-hook-form';
import { EyeIcon, EyeSlashIcon, LockClosedIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';

const ChangePassword = () => {
  const [loading, setLoading] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const { register, handleSubmit, formState: { errors }, watch, reset } = useForm();
  const newPassword = watch('newPassword');

  const onSubmit = async (data) => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      await axios.post(
        '/api/password/change',
        {
          current_password: data.currentPassword,
          new_password: data.newPassword,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      
      showSuccessToast('Password changed successfully!');
      reset(); // Clear the form
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to change password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900">Change Password</h3>
        <p className="mt-1 text-sm text-gray-600">
          Update your account password. You'll need to enter your current password.
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label htmlFor="currentPassword" className="block text-sm font-medium text-gray-700">
            Current Password
          </label>
          <div className="mt-1 relative">
            <input
              {...register('currentPassword', { required: 'Current password is required' })}
              type={showCurrentPassword ? 'text' : 'password'}
              className="appearance-none block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
              disabled={loading}
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 pr-3 flex items-center"
              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
            >
              {showCurrentPassword ? (
                <EyeSlashIcon className="h-5 w-5 text-gray-400" />
              ) : (
                <EyeIcon className="h-5 w-5 text-gray-400" />
              )}
            </button>
          </div>
          {errors.currentPassword && (
            <p className="mt-1 text-xs text-red-600">{errors.currentPassword.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="newPassword" className="block text-sm font-medium text-gray-700">
            New Password
          </label>
          <div className="mt-1 relative">
            <input
              {...register('newPassword', { 
                required: 'New password is required',
                minLength: {
                  value: 8,
                  message: 'Password must be at least 8 characters'
                },
                validate: (value) => 
                  value !== watch('currentPassword') || 'New password must be different from current password'
              })}
              type={showNewPassword ? 'text' : 'password'}
              className="appearance-none block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
              disabled={loading}
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 pr-3 flex items-center"
              onClick={() => setShowNewPassword(!showNewPassword)}
            >
              {showNewPassword ? (
                <EyeSlashIcon className="h-5 w-5 text-gray-400" />
              ) : (
                <EyeIcon className="h-5 w-5 text-gray-400" />
              )}
            </button>
          </div>
          {errors.newPassword && (
            <p className="mt-1 text-xs text-red-600">{errors.newPassword.message}</p>
          )}
          <p className="mt-1 text-xs text-gray-500">Must be at least 8 characters and different from current password</p>
        </div>

        <div>
          <label htmlFor="confirmPassword" className="block text-sm font-medium text-gray-700">
            Confirm New Password
          </label>
          <div className="mt-1 relative">
            <input
              {...register('confirmPassword', { 
                required: 'Please confirm your password',
                validate: value => value === newPassword || 'Passwords do not match'
              })}
              type={showConfirmPassword ? 'text' : 'password'}
              className="appearance-none block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
              disabled={loading}
            />
            <button
              type="button"
              className="absolute inset-y-0 right-0 pr-3 flex items-center"
              onClick={() => setShowConfirmPassword(!showConfirmPassword)}
            >
              {showConfirmPassword ? (
                <EyeSlashIcon className="h-5 w-5 text-gray-400" />
              ) : (
                <EyeIcon className="h-5 w-5 text-gray-400" />
              )}
            </button>
          </div>
          {errors.confirmPassword && (
            <p className="mt-1 text-xs text-red-600">{errors.confirmPassword.message}</p>
          )}
        </div>

        <div className="pt-4">
          <button
            type="submit"
            disabled={loading}
            className="inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <LockClosedIcon className="h-4 w-4 mr-2" />
            {loading ? 'Changing Password...' : 'Change Password'}
          </button>
        </div>
      </form>

      <div className="mt-6 bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-yellow-800">Password Requirements</h3>
            <div className="mt-2 text-xs text-yellow-700">
              <ul className="list-disc list-inside space-y-1">
                <li>Minimum 8 characters long</li>
                <li>Must be different from your current password</li>
                <li>Recommended: Use a mix of uppercase, lowercase, numbers, and special characters</li>
                <li>Avoid using common words or personal information</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChangePassword;