import React, { useState, useEffect } from 'react';
import { 
  ArrowPathIcon,
  CloudArrowDownIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowDownTrayIcon,
  MagnifyingGlassIcon,
  ChevronUpDownIcon
} from '@heroicons/react/24/outline';
import { useAuth } from '../../contexts/AuthContext';
import seedApplicationService from '../../services/seedApplicationService';
import { useDebounce } from '../../hooks/useDebounce';
import SeedApplicationCard from '../../components/admin/SeedApplicationCard';
import InstallConfirmModal from '../../components/admin/InstallConfirmModal';
import DeleteConfirmModal from '../../components/admin/DeleteConfirmModal';
import UninstallConfirmModal from '../../components/admin/UninstallConfirmModal';
import JsonEditorModal from '../../components/admin/JsonEditorModal';
import VerificationModal from '../../components/admin/VerificationModal';
import ValidationErrorDisplay from '../../components/admin/ValidationErrorDisplay';
import { getFullErrorMessage } from '../../utils/errorHandler';
import { showSuccessToast } from '../../utils/customToast';
import { showErrorToast } from '../../utils/customToast';

const SeedApplications = () => {
  const { user } = useAuth();
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [selectedApp, setSelectedApp] = useState(null);
  const [installModalOpen, setInstallModalOpen] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [warning, setWarning] = useState(null);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [uninstallModalOpen, setUninstallModalOpen] = useState(false);
  const [uninstalling, setUninstalling] = useState(false);
  const [jsonEditorOpen, setJsonEditorOpen] = useState(false);
  const [jsonEditorApp, setJsonEditorApp] = useState(null);
  const [savingJson, setSavingJson] = useState(false);
  const [verificationModalOpen, setVerificationModalOpen] = useState(false);
  const [verificationData, setVerificationData] = useState(null);
  const [verifyingApp, setVerifyingApp] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState('last_modified');
  const [sortOrder, setSortOrder] = useState('desc');

  // Debounce search query to avoid too many API calls
  const debouncedSearchQuery = useDebounce(searchQuery, 500);

  // Check if user is admin
  const isAdmin = user?.role === 'INSTANCE_ADMIN';

  // Initial load
  useEffect(() => {
    if (isAdmin) {
      loadApplications(true); // Show loader on initial load
    }
  }, [isAdmin]);

  // Search and sort changes (no loader)
  useEffect(() => {
    if (isAdmin && !loading) {
      loadApplications(false); // Don't show loader for search/sort changes
    }
  }, [debouncedSearchQuery, sortBy, sortOrder]);

  const loadApplications = async (showLoader = true) => {
    try {
      // Only show loading state on initial load or manual refresh, not on search/sort changes
      if (showLoader) {
        setLoading(true);
      }
      setError(null);
      const response = await seedApplicationService.getApplications({
        search: debouncedSearchQuery,
        sort_by: sortBy,
        sort_order: sortOrder
      });
      setApplications(response.applications || []);
    } catch (err) {
      setError(getFullErrorMessage(err));
      console.error('Error loading seed applications:', err);
    } finally {
      if (showLoader) {
        setLoading(false);
      }
    }
  };

  const handleRefreshCache = async () => {
    try {
      setRefreshing(true);
      await seedApplicationService.refreshCache();
      await loadApplications();
      showSuccessToast('Application cache refreshed');
    } catch (err) {
      setError(getFullErrorMessage(err));
    } finally {
      setRefreshing(false);
    }
  };

  const handleInstallClick = async (application) => {
    setSelectedApp(application);
    
    // Check for warnings if already installed
    if (application.status === 'installed' || application.status === 'update_available') {
      try {
        const warningData = await seedApplicationService.getInstallationWarning(application.key);
        setWarning(warningData);
      } catch (err) {
        console.error('Error fetching warning:', err);
      }
    }
    
    setInstallModalOpen(true);
  };

  const handleDeleteClick = (application) => {
    setSelectedApp(application);
    setDeleteModalOpen(true);
  };

  const handleUninstallClick = (application) => {
    setSelectedApp(application);
    setUninstallModalOpen(true);
  };

  const handleEditJsonClick = async (application) => {
    try {
      // Fetch the full JSON data
      const jsonData = await seedApplicationService.getApplicationJson(application.key);
      setJsonEditorApp({
        ...application,
        json_data: jsonData
      });
      setJsonEditorOpen(true);
    } catch (err) {
      showErrorToast('Failed to load JSON: ' + getFullErrorMessage(err));
    }
  };

  const handleJsonSave = async (updatedJson) => {
    try {
      setSavingJson(true);
      const result = await seedApplicationService.updateApplicationJson(jsonEditorApp.key, updatedJson);
      
      // Refresh the applications list
      await loadApplications();
      
      // Close the editor
      setJsonEditorOpen(false);
      setJsonEditorApp(null);
      
      // Show success message
      showSuccessToast(result.message || 'JSON updated successfully');
      
      // Show warnings if any
      if (result.warnings && result.warnings.length > 0) {
        result.warnings.forEach(warning => {
          toast(warning, {
            icon: '⚠️',
            duration: 5000,
          });
        });
      }
    } catch (err) {
      const errorData = getFullErrorMessage(err);
      
      // Check if it's a validation error
      if (err.response?.data?.detail && typeof err.response.data.detail === 'object') {
        const detail = err.response.data.detail;
        showErrorToast(detail.message || 'Validation failed');
        
        // Show specific validation errors
        if (detail.errors && Array.isArray(detail.errors)) {
          detail.errors.forEach(error => {
            showErrorToast(error);
          });
        }
      } else {
        showErrorToast('Failed to save JSON: ' + errorData);
      }
    } finally {
      setSavingJson(false);
    }
  };

  const handleVerifyClick = async (application) => {
    try {
      setVerifyingApp(application);
      const data = await seedApplicationService.verifyApplication(application.key);
      setVerificationData(data);
      setVerificationModalOpen(true);
    } catch (err) {
      showErrorToast('Failed to verify application: ' + getFullErrorMessage(err));
    }
  };

  const handleDeleteConfirm = async () => {
    try {
      setDeleting(true);
      const result = await seedApplicationService.deleteApplication(selectedApp.key);
      
      // Refresh the applications list
      await loadApplications();
      
      // Close modal
      setDeleteModalOpen(false);
      setSelectedApp(null);
      
      // Show success message
      showSuccessToast(result.message || 'Application deleted successfully');
    } catch (err) {
      // Handle errors
      if (err.response?.status === 400) {
        const detail = err.response.data.detail;
        showErrorToast(detail.message || 'Cannot delete application');
      } else {
        showErrorToast(getFullErrorMessage(err));
      }
    } finally {
      setDeleting(false);
    }
  };

  const handleUninstallConfirm = async (force = false) => {
    try {
      setUninstalling(true);
      const result = await seedApplicationService.uninstallApplication(selectedApp.key, force);
      
      // Refresh the applications list
      await loadApplications();
      
      // Close modal
      setUninstallModalOpen(false);
      setSelectedApp(null);
      
      // Show success message
      showSuccessToast(result.message || 'Application uninstalled successfully');
    } catch (err) {
      // Handle 400 error (has subscriptions)
      if (err.response?.status === 400) {
        const detail = err.response.data.detail;
        if (detail && typeof detail === 'object' && detail.subscription_count > 0) {
          // Show warning about subscriptions
          setWarning({
            message: detail.message,
            subscription_count: detail.subscription_count,
            suggestion: detail.suggestion
          });
        } else {
          showErrorToast(detail.message || detail || 'Cannot uninstall application');
          setUninstallModalOpen(false);
        }
      } else {
        showErrorToast(getFullErrorMessage(err));
        setUninstallModalOpen(false);
      }
    } finally {
      setUninstalling(false);
    }
  };

  const handleInstallConfirm = async (forceReinstall = false) => {
    try {
      setInstalling(true);
      let result;
      
      // If it's an update, use the update endpoint
      if (selectedApp.status === 'update_available' && !forceReinstall) {
        result = await seedApplicationService.updateApplication(selectedApp.key);
      } else {
        // Otherwise use install endpoint
        result = await seedApplicationService.installApplication(
          selectedApp.key,
          forceReinstall
        );
      }
      
      // Refresh the applications list
      await loadApplications();
      
      // Close modal
      setInstallModalOpen(false);
      setSelectedApp(null);
      setWarning(null);
      
      // Show success message
      showSuccessToast(result.message || 'Application installed successfully');
    } catch (err) {
      // Handle 409 conflict (already installed)
      if (err.response?.status === 409) {
        const detail = err.response.data.detail;
        setWarning({
          message: detail.message,
          subscription_count: detail.warnings?.[0]?.match(/(\d+) active subscriptions/)?.[1] || 0
        });
      } else {
        const errorData = getFullErrorMessage(err);
        
        // Check if it's a validation error with structured data
        if (errorData && typeof errorData === 'object' && errorData.type === 'validation') {
          setError(errorData);
        } else {
          setError(errorData);
        }
        
        setInstallModalOpen(false);
      }
    } finally {
      setInstalling(false);
    }
  };

  if (!isAdmin) {
    return (
      <div className="px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md">
          You need administrator privileges to access this page.
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  const installedCount = applications.filter(app => app.status !== 'not_installed').length;

  return (
    <div className="px-4 sm:px-6 lg:px-8 py-8">
      <div className="sm:flex sm:items-center sm:justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold leading-6 text-gray-900">
            Seed Applications
          </h1>
          <p className="mt-2 text-sm text-gray-700">
            Manage pre-configured application integrations
          </p>
        </div>
        <div className="mt-4 sm:mt-0">
          <button
            type="button"
            onClick={handleRefreshCache}
            disabled={refreshing}
            className="inline-flex items-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50"
          >
            <ArrowPathIcon className={`-ml-0.5 mr-1.5 h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Search and Sort Controls */}
      <div className="mb-6 flex flex-col sm:flex-row gap-4">
        {/* Search Bar */}
        <div className="flex-1">
          <div className="relative">
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="block w-full rounded-md border-0 py-2 pl-10 pr-3 text-gray-900 ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-primary sm:text-sm sm:leading-6"
              placeholder="Search applications by name, category, or description..."
              autoComplete="off"
            />
          </div>
        </div>
        
        {/* Sort Controls */}
        <div className="flex gap-2">
          {/* Sort By Dropdown */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="block rounded-md border-0 py-2 pl-3 pr-10 text-gray-900 ring-1 ring-inset ring-gray-300 focus:ring-2 focus:ring-primary sm:text-sm sm:leading-6"
          >
            <option value="last_modified">Last Modified</option>
            <option value="app_name">Name</option>
            <option value="category">Category</option>
            <option value="status">Status</option>
            <option value="created_at">Created Date</option>
            <option value="installed_at">Installed Date</option>
          </select>
          
          {/* Sort Order Button */}
          <button
            type="button"
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="inline-flex items-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
            title={sortOrder === 'asc' ? 'Sort descending' : 'Sort ascending'}
          >
            <ChevronUpDownIcon className="h-5 w-5" />
            {sortOrder === 'asc' ? 'Asc' : 'Desc'}
          </button>
        </div>
      </div>

      {/* Statistics */}
      <div className="mb-6 flex flex-wrap gap-3">
        <span className="inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-800">
          Total: {applications.length}
        </span>
        <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800">
          <CheckCircleIcon className="mr-1 h-4 w-4" />
          Installed: {installedCount}
        </span>
        <span className="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800">
          <CloudArrowDownIcon className="mr-1 h-4 w-4" />
          Available: {applications.length - installedCount}
        </span>
      </div>

      {error && (
        <>
          {typeof error === 'object' && error.type === 'validation' ? (
            <div className="mb-6 bg-white border border-red-200 rounded-lg shadow-sm p-4">
              <ValidationErrorDisplay 
                errors={error.errors} 
                warnings={error.warnings}
                onClose={() => setError(null)}
              />
            </div>
          ) : (
            <div className="mb-6 bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-md relative">
              <div className="flex">
                <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
                <span>{error}</span>
              </div>
              <button
                onClick={() => setError(null)}
                className="absolute top-3 right-3 text-red-500 hover:text-red-700"
              >
                <span className="sr-only">Close</span>
                <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
          )}
        </>
      )}

      {/* Applications Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {applications.map((app) => (
          <SeedApplicationCard
            key={app.key}
            application={app}
            onInstall={() => handleInstallClick(app)}
            onDelete={() => handleDeleteClick(app)}
            onUninstall={() => handleUninstallClick(app)}
            onEditJson={() => handleEditJsonClick(app)}
            onVerify={() => handleVerifyClick(app)}
          />
        ))}
      </div>

      {applications.length === 0 && (
        <div className="text-center bg-white py-12 px-4 shadow rounded-lg">
          <h3 className="text-lg font-medium text-gray-900">No seed applications found</h3>
          <p className="mt-2 text-sm text-gray-500">
            Make sure seed applications are properly configured in the backend.
          </p>
          <div className="mt-6">
            <button
              type="button"
              onClick={handleRefreshCache}
              className="inline-flex items-center rounded-md bg-gradient-primary px-3 py-2 text-sm font-semibold text-white shadow-sm hover:shadow-lg"
            >
              <ArrowPathIcon className="mr-2 h-4 w-4" />
              Refresh Cache
            </button>
          </div>
        </div>
      )}

      <InstallConfirmModal
        open={installModalOpen}
        onClose={() => {
          setInstallModalOpen(false);
          setSelectedApp(null);
          setWarning(null);
        }}
        application={selectedApp}
        warning={warning}
        onConfirm={handleInstallConfirm}
        installing={installing}
      />

      <DeleteConfirmModal
        open={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setSelectedApp(null);
        }}
        application={selectedApp}
        onConfirm={handleDeleteConfirm}
        deleting={deleting}
      />

      <UninstallConfirmModal
        open={uninstallModalOpen}
        onClose={() => {
          setUninstallModalOpen(false);
          setSelectedApp(null);
          setWarning(null);
        }}
        application={selectedApp}
        warning={warning}
        onConfirm={handleUninstallConfirm}
        uninstalling={uninstalling}
      />

      <JsonEditorModal
        open={jsonEditorOpen}
        onClose={() => {
          setJsonEditorOpen(false);
          setJsonEditorApp(null);
        }}
        application={jsonEditorApp}
        onSave={handleJsonSave}
        loading={savingJson}
      />

      <VerificationModal
        open={verificationModalOpen}
        onClose={() => {
          setVerificationModalOpen(false);
          setVerificationData(null);
          setVerifyingApp(null);
        }}
        application={verifyingApp}
        verificationData={verificationData}
      />
    </div>
  );
};

export default SeedApplications;