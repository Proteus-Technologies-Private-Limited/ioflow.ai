import React, { useState, useEffect, Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { useForm } from 'react-hook-form';
import {
  EnvelopeIcon,
  EyeIcon,
  EyeSlashIcon,
  TrashIcon,
  CheckCircleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import axios from 'axios';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';

const SMTPConfiguration = () => {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [testModalOpen, setTestModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  
  const { register, handleSubmit, formState: { errors }, reset, setValue } = useForm({
    defaultValues: {
      smtp_host: '',
      smtp_port: 587,
      smtp_username: '',
      smtp_password: '',
      smtp_from_email: '',
      smtp_from_name: 'IOFlow',
      use_tls: true,
      use_ssl: false,
      is_active: true,
    }
  });

  const { 
    register: registerTest, 
    handleSubmit: handleSubmitTest, 
    formState: { errors: testErrors },
    reset: resetTest 
  } = useForm({
    defaultValues: {
      to_email: '',
      subject: 'Test Email from IOFlow',
      body: 'This is a test email to verify SMTP configuration.',
    }
  });

  useEffect(() => {
    fetchSMTPConfig();
  }, []);

  const fetchSMTPConfig = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get('/api/smtp-config', {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.data) {
        setConfig(response.data);
        // Update form with existing config
        Object.keys(response.data).forEach(key => {
          if (key !== 'smtp_password') {
            setValue(key, response.data[key]);
          }
        });
      }
    } catch (err) {
      if (err.response?.status !== 404) {
        showErrorToast('Failed to fetch SMTP configuration');
      }
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = async (data) => {
    setSaving(true);
    try {
      const token = localStorage.getItem('access_token');
      
      // Only send password if it's provided (for updates)
      const dataToSend = { ...data };
      if (config && !data.smtp_password) {
        delete dataToSend.smtp_password;
      }

      const response = await axios.post('/api/smtp-config', dataToSend, {
        headers: { Authorization: `Bearer ${token}` },
      });

      setConfig(response.data);
      showSuccessToast('SMTP configuration saved successfully');
      setValue('smtp_password', ''); // Clear password field after save
    } catch (err) {
      showErrorToast(err.response?.data?.detail || 'Failed to save SMTP configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      const token = localStorage.getItem('access_token');
      await axios.delete('/api/smtp-config', {
        headers: { Authorization: `Bearer ${token}` },
      });

      showSuccessToast('SMTP configuration deleted successfully');
      setConfig(null);
      reset(); // Reset form to defaults
      setDeleteModalOpen(false);
    } catch (err) {
      showErrorToast(err.response?.data?.detail || 'Failed to delete SMTP configuration');
    }
  };

  const onTestSubmit = async (data) => {
    setTesting(true);
    try {
      const token = localStorage.getItem('access_token');
      await axios.post('/api/smtp-config/test', data, {
        headers: { Authorization: `Bearer ${token}` },
      });

      showSuccessToast('Test email sent successfully!');
      setTestModalOpen(false);
      resetTest();
    } catch (err) {
      showErrorToast(err.response?.data?.detail || 'Failed to send test email');
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium text-gray-900">SMTP Email Configuration</h3>
        <p className="mt-1 text-sm text-gray-600">
          Configure SMTP settings to send emails for password reset and user invitations
        </p>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              SMTP Host
            </label>
            <input
              {...register('smtp_host', { required: 'SMTP host is required' })}
              type="text"
              placeholder="smtp.gmail.com"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
            />
            {errors.smtp_host && (
              <p className="mt-1 text-xs text-red-600">{errors.smtp_host.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              SMTP Port
            </label>
            <input
              {...register('smtp_port', { 
                required: 'SMTP port is required',
                valueAsNumber: true
              })}
              type="number"
              placeholder="587"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
            />
            {errors.smtp_port && (
              <p className="mt-1 text-xs text-red-600">{errors.smtp_port.message}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">Common: 587 (TLS), 465 (SSL), 25</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Username
            </label>
            <input
              {...register('smtp_username', { required: 'Username is required' })}
              type="text"
              placeholder="your-email@example.com"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
            />
            {errors.smtp_username && (
              <p className="mt-1 text-xs text-red-600">{errors.smtp_username.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <div className="mt-1 relative">
              <input
                {...register('smtp_password', { 
                  required: !config ? 'Password is required' : false 
                })}
                type={showPassword ? 'text' : 'password'}
                placeholder={config ? 'Leave blank to keep current' : 'Enter password'}
                className="block w-full px-3 py-2 pr-10 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
              />
              <button
                type="button"
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeSlashIcon className="h-5 w-5 text-gray-400" />
                ) : (
                  <EyeIcon className="h-5 w-5 text-gray-400" />
                )}
              </button>
            </div>
            {errors.smtp_password && (
              <p className="mt-1 text-xs text-red-600">{errors.smtp_password.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              From Email
            </label>
            <input
              {...register('smtp_from_email', { 
                required: 'From email is required',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Invalid email address'
                }
              })}
              type="email"
              placeholder="noreply@example.com"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
            />
            {errors.smtp_from_email && (
              <p className="mt-1 text-xs text-red-600">{errors.smtp_from_email.message}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              From Name
            </label>
            <input
              {...register('smtp_from_name')}
              type="text"
              placeholder="IOFlow"
              className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
            />
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center">
            <input
              {...register('use_tls')}
              type="checkbox"
              className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              onChange={(e) => {
                if (e.target.checked) {
                  setValue('use_ssl', false);
                }
              }}
            />
            <label className="ml-2 block text-sm text-gray-900">
              Use TLS
            </label>
          </div>

          <div className="flex items-center">
            <input
              {...register('use_ssl')}
              type="checkbox"
              className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
              onChange={(e) => {
                if (e.target.checked) {
                  setValue('use_tls', false);
                }
              }}
            />
            <label className="ml-2 block text-sm text-gray-900">
              Use SSL
            </label>
          </div>

          <div className="flex items-center">
            <input
              {...register('is_active')}
              type="checkbox"
              className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
            />
            <label className="ml-2 block text-sm text-gray-900">
              Active
            </label>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4">
          <div className="flex space-x-3">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>

            {config && (
              <button
                type="button"
                onClick={() => setTestModalOpen(true)}
                className="inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
              >
                <EnvelopeIcon className="h-4 w-4 mr-2" />
                Test Email
              </button>
            )}
          </div>

          {config && (
            <button
              type="button"
              onClick={() => setDeleteModalOpen(true)}
              className="inline-flex justify-center items-center px-4 py-2 border border-red-300 text-sm font-medium rounded-md text-red-700 bg-white hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
            >
              <TrashIcon className="h-4 w-4 mr-2" />
              Delete
            </button>
          )}
        </div>
      </form>

      {/* Common SMTP Settings Help */}
      <div className="mt-8 bg-gray-50 border border-gray-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-900 mb-4">Common SMTP Settings</h4>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <h5 className="text-xs font-medium text-primary-600">Gmail</h5>
            <p className="mt-1 text-xs text-gray-600">
              Host: smtp.gmail.com<br />
              Port: 587 (TLS) or 465 (SSL)<br />
              Note: Use App Password
            </p>
          </div>
          <div>
            <h5 className="text-xs font-medium text-primary-600">Outlook/Office365</h5>
            <p className="mt-1 text-xs text-gray-600">
              Host: smtp.office365.com<br />
              Port: 587 (TLS)<br />
              Note: May require app password
            </p>
          </div>
          <div>
            <h5 className="text-xs font-medium text-primary-600">SendGrid</h5>
            <p className="mt-1 text-xs text-gray-600">
              Host: smtp.sendgrid.net<br />
              Port: 587 (TLS) or 465 (SSL)<br />
              Username: apikey<br />
              Password: Your API Key
            </p>
          </div>
        </div>
      </div>

      {/* Test Email Modal */}
      <Transition appear show={testModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-10" onClose={() => setTestModalOpen(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-25" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">
                    Send Test Email
                  </Dialog.Title>
                  
                  <form onSubmit={handleSubmitTest(onTestSubmit)} className="mt-4 space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        To Email
                      </label>
                      <input
                        {...registerTest('to_email', { 
                          required: 'Email is required',
                          pattern: {
                            value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                            message: 'Invalid email address'
                          }
                        })}
                        type="email"
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                      />
                      {testErrors.to_email && (
                        <p className="mt-1 text-xs text-red-600">{testErrors.to_email.message}</p>
                      )}
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Subject
                      </label>
                      <input
                        {...registerTest('subject')}
                        type="text"
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700">
                        Message
                      </label>
                      <textarea
                        {...registerTest('body')}
                        rows={4}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 sm:text-sm"
                      />
                    </div>

                    <div className="mt-6 flex justify-end space-x-3">
                      <button
                        type="button"
                        onClick={() => setTestModalOpen(false)}
                        className="inline-flex justify-center px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-transparent rounded-md hover:bg-gray-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-gray-500"
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        disabled={testing}
                        className="inline-flex justify-center px-4 py-2 text-sm font-medium text-white bg-primary-600 border border-transparent rounded-md hover:bg-primary-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {testing ? 'Sending...' : 'Send Test Email'}
                      </button>
                    </div>
                  </form>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>

      {/* Delete Confirmation Modal */}
      <Transition appear show={deleteModalOpen} as={Fragment}>
        <Dialog as="div" className="relative z-10" onClose={() => setDeleteModalOpen(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-25" />
          </Transition.Child>

          <div className="fixed inset-0 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 scale-95"
                enterTo="opacity-100 scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 scale-100"
                leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-6 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title as="h3" className="text-lg font-medium leading-6 text-gray-900">
                    Delete SMTP Configuration
                  </Dialog.Title>
                  <div className="mt-2">
                    <p className="text-sm text-gray-500">
                      Are you sure you want to delete the SMTP configuration? This will disable email sending functionality.
                    </p>
                  </div>

                  <div className="mt-4 flex justify-end space-x-3">
                    <button
                      type="button"
                      onClick={() => setDeleteModalOpen(false)}
                      className="inline-flex justify-center px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-transparent rounded-md hover:bg-gray-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-gray-500"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleDelete}
                      className="inline-flex justify-center px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-red-500"
                    >
                      Delete
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition>
    </div>
  );
};

export default SMTPConfiguration;