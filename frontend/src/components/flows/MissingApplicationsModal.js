import React from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  XMarkIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';

const MissingApplicationsModal = ({
  open,
  onClose,
  requiredApplications = [],
  missingApplications = [],
  exampleName,
  onProceedWithImport
}) => {
  const navigate = useNavigate();

  const handleNavigateToApplications = () => {
    onClose();
    navigate('/applications');
  };

  const allApplicationsAvailable = missingApplications.length === 0;

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
        </Transition.Child>

        <div className="fixed inset-0 z-[100] overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white shadow-xl transition-all w-full max-w-2xl">
                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-200">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      {allApplicationsAvailable ? (
                        <div className="flex-shrink-0">
                          <CheckCircleIcon className="h-8 w-8 text-green-500" />
                        </div>
                      ) : (
                        <div className="flex-shrink-0">
                          <ExclamationTriangleIcon className="h-8 w-8 text-yellow-500" />
                        </div>
                      )}
                      <div>
                        <Dialog.Title as="h3" className="text-lg font-semibold text-gray-900">
                          {allApplicationsAvailable ? 'Ready to Import' : 'Missing Required Applications'}
                        </Dialog.Title>
                        {exampleName && (
                          <p className="mt-1 text-sm text-gray-500">
                            Flow: <span className="font-medium">{exampleName}</span>
                          </p>
                        )}
                      </div>
                    </div>
                    <button
                      type="button"
                      className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none"
                      onClick={onClose}
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="px-6 py-4">
                  {allApplicationsAvailable ? (
                    <div className="space-y-4">
                      <p className="text-sm text-gray-700">
                        All required applications for this flow are available and properly configured.
                        You can proceed with importing this flow example.
                      </p>

                      {/* Show all required applications */}
                      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-green-900 mb-3">
                          Required Applications ({requiredApplications.length})
                        </h4>
                        <div className="space-y-2">
                          {requiredApplications.map((app) => (
                            <div key={app.app_id} className="flex items-center gap-3">
                              <CheckCircleIcon className="h-5 w-5 text-green-500 flex-shrink-0" />
                              <div className="flex-1">
                                <p className="text-sm font-medium text-gray-900">{app.app_name}</p>
                                {app.description && (
                                  <p className="text-xs text-gray-600 line-clamp-1">{app.description}</p>
                                )}
                              </div>
                              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                Subscribed
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <p className="text-sm text-yellow-800">
                          This flow requires {requiredApplications.length} application(s), but you are missing {missingApplications.length} of them.
                          Please subscribe to the missing applications before importing this flow.
                        </p>
                      </div>

                      {/* Missing Applications */}
                      {missingApplications.length > 0 && (
                        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                          <h4 className="text-sm font-medium text-red-900 mb-3">
                            Missing Applications ({missingApplications.length})
                          </h4>
                          <div className="space-y-2">
                            {missingApplications.map((app) => (
                              <div key={app.app_id} className="flex items-start gap-3">
                                <ExclamationTriangleIcon className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                                <div className="flex-1">
                                  <p className="text-sm font-medium text-gray-900">{app.app_name}</p>
                                  {app.description && (
                                    <p className="text-xs text-gray-600 mt-1">{app.description}</p>
                                  )}
                                  <span className="inline-flex items-center mt-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
                                    Type: {app.app_type}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Already Subscribed Applications */}
                      {requiredApplications.length > missingApplications.length && (
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                          <h4 className="text-sm font-medium text-green-900 mb-3">
                            Already Subscribed ({requiredApplications.length - missingApplications.length})
                          </h4>
                          <div className="space-y-2">
                            {requiredApplications
                              .filter(app => app.is_subscribed)
                              .map((app) => (
                                <div key={app.app_id} className="flex items-center gap-3">
                                  <CheckCircleIcon className="h-5 w-5 text-green-500 flex-shrink-0" />
                                  <div className="flex-1">
                                    <p className="text-sm font-medium text-gray-900">{app.app_name}</p>
                                  </div>
                                </div>
                              ))}
                          </div>
                        </div>
                      )}

                      {/* Instructions */}
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-blue-900 mb-2">
                          Next Steps:
                        </h4>
                        <ol className="list-decimal list-inside space-y-1 text-sm text-blue-800">
                          <li>Go to the Applications page</li>
                          <li>Find and subscribe to the missing applications</li>
                          <li>Configure the required credentials for each application</li>
                          <li>Return to this flow example and try importing again</li>
                        </ol>
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={onClose}
                    className="inline-flex justify-center rounded-md bg-white px-4 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
                  >
                    Close
                  </button>

                  {allApplicationsAvailable ? (
                    <button
                      type="button"
                      onClick={() => {
                        onClose();
                        if (onProceedWithImport) {
                          onProceedWithImport();
                        }
                      }}
                      className="inline-flex items-center justify-center rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-green-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-600"
                    >
                      Proceed with Import
                      <ArrowRightIcon className="ml-2 h-4 w-4" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={handleNavigateToApplications}
                      className="inline-flex items-center justify-center rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600"
                    >
                      Go to Applications
                      <ArrowRightIcon className="ml-2 h-4 w-4" />
                    </button>
                  )}
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default MissingApplicationsModal;
