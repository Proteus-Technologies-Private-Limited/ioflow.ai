import React, { useState, useEffect } from 'react';
import { Switch } from '@headlessui/react';
import axios from 'axios';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';
import { InformationCircleIcon } from '@heroicons/react/24/outline';

function classNames(...classes) {
  return classes.filter(Boolean).join(' ');
}

const CachePreferences = () => {
  const [retainCache, setRetainCache] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchPreferences();
  }, []);

  const fetchPreferences = async () => {
    try {
      const response = await axios.get('/api/v1/ui-preferences');
      setRetainCache(response.data?.retain_cache_on_logout || false);
    } catch (error) {
      console.error('Failed to fetch UI preferences:', error);
      // Default to false if we can't fetch
      setRetainCache(false);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (checked) => {
    setRetainCache(checked);
    setSaving(true);

    try {
      await axios.patch('/api/v1/ui-preferences/cache-retention', null, {
        params: { retain_cache: checked }
      });
      showSuccessToast(
        checked
          ? 'Local cache will be retained on logout'
          : 'Local cache will be cleared on logout'
      );
    } catch (error) {
      console.error('Failed to update cache preference:', error);
      showErrorToast('Failed to update cache preference');
      // Revert the toggle on error
      setRetainCache(!checked);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-2"></div>
        <div className="h-4 bg-gray-200 rounded w-3/4"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-base font-medium text-gray-900">Cache Preferences</h3>
        <p className="mt-1 text-sm text-gray-600">
          Control how your local data is handled when you log out.
        </p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center">
              <h4 className="text-sm font-medium text-gray-900">
                Retain Local Cache on Logout
              </h4>
              <div className="ml-2 group relative">
                <InformationCircleIcon className="h-4 w-4 text-gray-400 hover:text-gray-500" />
                <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block w-64 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg z-10">
                  When enabled, your search history, favorite services, and other preferences will be preserved when you log out.
                  <div className="absolute left-4 top-full -mt-1">
                    <div className="border-4 border-transparent border-t-gray-900"></div>
                  </div>
                </div>
              </div>
            </div>
            <p className="mt-1 text-sm text-gray-600">
              Keep your preferences and recent items after logging out
            </p>
          </div>
          <Switch
            checked={retainCache}
            onChange={handleToggle}
            disabled={saving}
            className={classNames(
              retainCache ? 'bg-blue-600' : 'bg-gray-200',
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
              saving ? 'opacity-50 cursor-not-allowed' : ''
            )}
          >
            <span className="sr-only">Retain local cache on logout</span>
            <span
              className={classNames(
                retainCache ? 'translate-x-6' : 'translate-x-1',
                'inline-block h-4 w-4 transform rounded-full bg-white transition-transform'
              )}
            />
          </Switch>
        </div>

        {retainCache && (
          <div className="mt-3 p-3 bg-blue-50 rounded-md">
            <p className="text-xs text-blue-800">
              <strong>Note:</strong> Your authentication tokens will still be cleared for security.
              Only non-sensitive preferences like favorites and UI settings will be retained.
            </p>
          </div>
        )}

        <div className="mt-4 border-t pt-4">
          <h5 className="text-xs font-medium text-gray-700 mb-2">Currently cached items:</h5>
          <ul className="text-xs text-gray-600 space-y-1">
            <li>• Application service favorites and recent items</li>
            <li>• Properties panel layout preferences</li>
            <li>• Search history and filters</li>
            <li>• UI theme and display settings</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default CachePreferences;