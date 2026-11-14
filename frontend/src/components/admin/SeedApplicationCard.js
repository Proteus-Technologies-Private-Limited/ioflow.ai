import React, { Fragment, useState } from 'react';
import { Menu, Transition } from '@headlessui/react';
import {
  CloudArrowDownIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  BoltIcon,
  UsersIcon,
  TrashIcon,
  CodeBracketIcon,
  MagnifyingGlassIcon,
  EllipsisVerticalIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';
import ValidationDetailsModal from './ValidationDetailsModal';

const SeedApplicationCard = ({ application, onInstall, onDelete, onUninstall, onEditJson, onVerify }) => {
  const [showValidationModal, setShowValidationModal] = useState(false);
  const getStatusBadge = () => {
    switch (application.status) {
      case 'installed':
        return (
          <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
            <CheckCircleIcon className="mr-1 h-3 w-3" />
            Installed
          </span>
        );
      case 'update_available':
        return (
          <span className="inline-flex items-center rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-800">
            <ArrowPathIcon className="mr-1 h-3 w-3" />
            Update Available
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800">
            <CloudArrowDownIcon className="mr-1 h-3 w-3" />
            Not Installed
          </span>
        );
    }
  };

  const getActionButton = () => {
    switch (application.status) {
      case 'installed':
        return (
          <button
            type="button"
            onClick={onInstall}
            className="inline-flex items-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
          >
            <CheckCircleIcon className="-ml-0.5 mr-1.5 h-5 w-5 text-gray-400" />
            Reinstall
          </button>
        );
      case 'update_available':
        return (
          <button
            type="button"
            onClick={onInstall}
            className="inline-flex items-center rounded-md bg-yellow-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500"
          >
            <ArrowPathIcon className="-ml-0.5 mr-1.5 h-5 w-5" />
            Update
          </button>
        );
      default:
        return (
          <button
            type="button"
            onClick={onInstall}
            className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
          >
            <CloudArrowDownIcon className="-ml-0.5 mr-1.5 h-5 w-5" />
            Install
          </button>
        );
    }
  };

  const getAuthTypeColor = (authType) => {
    const colors = {
      oauth2: 'bg-blue-100 text-blue-800',
      api_key: 'bg-purple-100 text-purple-800',
      token_exchange: 'bg-cyan-100 text-cyan-800',
      basic: 'bg-orange-100 text-orange-800',
      none: 'bg-gray-100 text-gray-800',
      custom: 'bg-red-100 text-red-800'
    };
    return colors[authType] || 'bg-gray-100 text-gray-800';
  };

  const hasValidationWarnings = application.validation_status && 
    (!application.validation_status.valid || 
     (application.validation_status.warnings && application.validation_status.warnings.length > 0));

  return (
    <div className="bg-white overflow-hidden shadow rounded-lg border border-gray-200 flex flex-col h-full">
      <div className="px-4 py-5 sm:p-6 flex-grow">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center">
            {application.icon_url ? (
              <img
                src={application.icon_url}
                alt={application.name}
                className="h-10 w-10 rounded-lg mr-3"
                onError={(e) => {
                  e.target.onerror = null;
                  e.target.style.display = 'none';
                  e.target.nextSibling.style.display = 'flex';
                }}
              />
            ) : null}
            <div
              className={`h-10 w-10 rounded-lg bg-gray-200 flex items-center justify-center mr-3 ${
                application.icon_url ? 'hidden' : ''
              }`}
            >
              <span className="text-lg font-semibold text-gray-600">
                {application.name.charAt(0)}
              </span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-medium text-gray-900">{application.name}</h3>
                {hasValidationWarnings && (
                  <span className="inline-flex items-center" title="Schema validation warnings">
                    <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />
                  </span>
                )}
              </div>
              {getStatusBadge()}
            </div>
          </div>
          {/* Dropdown menu */}
          <Menu as="div" className="relative inline-block text-left">
            <div>
              <Menu.Button className="rounded-full p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100">
                <span className="sr-only">Open options</span>
                <EllipsisVerticalIcon className="h-5 w-5" aria-hidden="true" />
              </Menu.Button>
            </div>
            <Transition
              as={Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute right-0 z-10 mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
                <div className="py-1">
                  {(application.status === 'installed' || application.status === 'update_available') && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={() => onVerify(application)}
                          className={`${
                            active ? 'bg-gray-100 text-gray-900' : 'text-gray-700'
                          } flex w-full items-center px-4 py-2 text-sm`}
                        >
                          <MagnifyingGlassIcon className="mr-3 h-5 w-5 text-gray-400" aria-hidden="true" />
                          Verify Installation
                        </button>
                      )}
                    </Menu.Item>
                  )}
                  <Menu.Item>
                    {({ active }) => (
                      <button
                        onClick={() => onEditJson(application)}
                        className={`${
                          active ? 'bg-gray-100 text-gray-900' : 'text-gray-700'
                        } flex w-full items-center px-4 py-2 text-sm`}
                      >
                        <CodeBracketIcon className="mr-3 h-5 w-5 text-gray-400" aria-hidden="true" />
                        Edit JSON
                      </button>
                    )}
                  </Menu.Item>
                  {hasValidationWarnings && (
                    <Menu.Item>
                      {({ active }) => (
                        <button
                          onClick={() => setShowValidationModal(true)}
                          className={`${
                            active ? 'bg-gray-100 text-gray-900' : 'text-gray-700'
                          } flex w-full items-center px-4 py-2 text-sm`}
                        >
                          <ExclamationTriangleIcon className="mr-3 h-5 w-5 text-yellow-500" aria-hidden="true" />
                          View Validation Details
                        </button>
                      )}
                    </Menu.Item>
                  )}
                </div>
              </Menu.Items>
            </Transition>
          </Menu>
        </div>

        <p className="text-sm text-gray-500 mb-4">{application.description}</p>

        <div className="flex flex-wrap gap-2 mb-4">
          <span className="inline-flex items-center rounded-md bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-800">
            {application.category}
          </span>
          <span className={`inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-medium ${getAuthTypeColor(application.auth_type)}`}>
            {application.auth_type}
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-gray-500">
          <div className="flex items-center" title="Services">
            <DocumentTextIcon className="h-4 w-4 mr-1" />
            <span>{application.service_count}</span>
          </div>
          <div className="flex items-center" title="Events">
            <BoltIcon className="h-4 w-4 mr-1" />
            <span>{application.event_count}</span>
          </div>
          {application.subscription_count > 0 && (
            <div className="flex items-center" title="Active Subscriptions">
              <UsersIcon className="h-4 w-4 mr-1" />
              <span>{application.subscription_count}</span>
            </div>
          )}
        </div>

        {(application.version || application.installed_version) && (
          <div className="mt-3 text-xs text-gray-500">
            Version: {application.installed_version || application.version}
            {application.installed_version && application.version !== application.installed_version && (
              <span className="text-yellow-600"> → {application.version}</span>
            )}
          </div>
        )}
        
        {hasValidationWarnings && (
          <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded-md">
            <div className="flex">
              <ExclamationTriangleIcon className="h-4 w-4 text-yellow-400 flex-shrink-0" />
              <div className="ml-2">
                <p className="text-xs text-yellow-700">
                  Schema validation warnings detected
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="bg-gray-50 px-4 py-4 sm:px-6 flex justify-between items-center">
        <div className="flex gap-2">
          {getActionButton()}
          {(application.status === 'installed' || application.status === 'update_available') && (
            <button
              type="button"
              onClick={() => onUninstall(application)}
              className="inline-flex items-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500"
              title="Uninstall application"
            >
              <TrashIcon className="-ml-0.5 mr-1.5 h-5 w-5" />
              Uninstall
            </button>
          )}
          {application.status === 'not_installed' && (
            <button
              type="button"
              onClick={() => onDelete(application)}
              className="inline-flex items-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500"
              title="Delete seed application file"
            >
              <TrashIcon className="-ml-0.5 mr-1.5 h-5 w-5" />
              Delete
            </button>
          )}
        </div>
      </div>
      
      <ValidationDetailsModal
        open={showValidationModal}
        onClose={() => setShowValidationModal(false)}
        application={application}
      />
    </div>
  );
};

export default SeedApplicationCard;