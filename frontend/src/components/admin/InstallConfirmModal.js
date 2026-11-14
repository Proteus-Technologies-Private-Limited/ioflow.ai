import React, { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import {
  ExclamationTriangleIcon,
  CheckCircleIcon,
  TrashIcon,
  CloudArrowDownIcon
} from '@heroicons/react/24/outline';

const InstallConfirmModal = ({
  open,
  onClose,
  application,
  warning,
  onConfirm,
  installing
}) => {
  if (!application) return null;

  const isReinstall = application.status === 'installed';
  const isUpdate = application.status === 'update_available';

  const handleInstall = () => {
    onConfirm(false);
  };

  const handleForceReinstall = () => {
    onConfirm(true);
  };

  return (
    <Transition.Root show={open} as={Fragment}>
      <Dialog as="div" className="relative z-10" onClose={onClose}>
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
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              enterTo="opacity-100 translate-y-0 sm:scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 translate-y-0 sm:scale-100"
              leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
            >
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                <div>
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-primary-100">
                    <CloudArrowDownIcon className="h-6 w-6 text-primary-600" />
                  </div>
                  <div className="mt-3 text-center sm:mt-5">
                    <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900">
                      {isUpdate ? 'Update' : isReinstall ? 'Reinstall' : 'Install'} {application.name}
                    </Dialog.Title>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        {application.description}
                      </p>
                    </div>
                  </div>
                </div>

                {warning && (
                  <div className={`mt-4 ${isUpdate ? 'bg-blue-50 border-blue-200' : 'bg-yellow-50 border-yellow-200'} border rounded-md p-4`}>
                    <div className="flex">
                      <ExclamationTriangleIcon className={`h-5 w-5 ${isUpdate ? 'text-blue-400' : 'text-yellow-400'}`} />
                      <div className="ml-3">
                        <h3 className={`text-sm font-medium ${isUpdate ? 'text-blue-800' : 'text-yellow-800'}`}>
                          {isUpdate ? 'Update Available' : 'Warning: Application Already Installed'}
                        </h3>
                        <div className={`mt-2 text-sm ${isUpdate ? 'text-blue-700' : 'text-yellow-700'}`}>
                          <p>{warning.message}</p>
                          {isUpdate && warning.subscription_count > 0 ? (
                            <p className="mt-1 font-semibold text-green-600">
                              ✓ Your {warning.subscription_count} subscription(s) will be preserved during the update!
                            </p>
                          ) : (
                            warning.subscription_count > 0 && (
                              <p className="mt-1 font-semibold">
                                {warning.subscription_count} subscription(s) will be permanently deleted!
                              </p>
                            )
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="mt-4 space-y-3">
                  <div className="flex items-center text-sm text-gray-600">
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span>
                      Version: {isUpdate ? `${application.installed_version} → ${application.version}` : application.version}
                    </span>
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span>Authentication: {application.auth_type}</span>
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span>{application.service_count} service(s) will be added</span>
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                    <span>{application.event_count} event(s) will be configured</span>
                  </div>
                  {warning && warning.subscription_count > 0 && (
                    <div className={`flex items-center text-sm ${isUpdate ? 'text-green-600' : 'text-red-600'}`}>
                      {isUpdate ? (
                        <CheckCircleIcon className="h-5 w-5 text-green-500 mr-2" />
                      ) : (
                        <TrashIcon className="h-5 w-5 text-red-500 mr-2" />
                      )}
                      <span>
                        {isUpdate 
                          ? `${warning.subscription_count} existing subscription(s) will be safely preserved`
                          : `${warning.subscription_count} existing subscription(s) and all associated data will be deleted`
                        }
                      </span>
                    </div>
                  )}
                </div>

                {!warning && isReinstall && (
                  <div className="mt-4 bg-blue-50 border border-blue-200 rounded-md p-4">
                    <div className="flex">
                      <ExclamationTriangleIcon className="h-5 w-5 text-blue-400" />
                      <div className="ml-3 text-sm text-blue-700">
                        Application is already installed. Reinstalling will remove all existing subscriptions and data.
                      </div>
                    </div>
                  </div>
                )}

                <div className="mt-5 sm:mt-6 sm:grid sm:grid-flow-row-dense sm:grid-cols-2 sm:gap-3">
                  {warning ? (
                    <>
                      {/* For updates, show safe update button first */}
                      {isUpdate ? (
                        <>
                          <button
                            type="button"
                            className="inline-flex w-full justify-center rounded-md bg-green-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-green-500 disabled:opacity-50 sm:col-start-2"
                            onClick={handleInstall}
                            disabled={installing}
                          >
                            {installing ? (
                              <>
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                Updating...
                              </>
                            ) : (
                              <>
                                <CloudArrowDownIcon className="h-5 w-5 mr-1" />
                                Update (Preserve Subscriptions)
                              </>
                            )}
                          </button>
                          <button
                            type="button"
                            className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50 sm:col-start-1 sm:mt-0"
                            onClick={onClose}
                            disabled={installing}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 disabled:opacity-50 sm:col-start-2"
                            onClick={handleForceReinstall}
                            disabled={installing}
                          >
                            {installing ? (
                              <>
                                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                                Installing...
                              </>
                            ) : (
                              <>
                                <ExclamationTriangleIcon className="h-5 w-5 mr-1" />
                                Force Reinstall
                              </>
                            )}
                          </button>
                          <button
                            type="button"
                            className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50 sm:col-start-1 sm:mt-0"
                            onClick={onClose}
                            disabled={installing}
                          >
                            Cancel
                          </button>
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="inline-flex w-full justify-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 disabled:opacity-50 sm:col-start-2"
                        onClick={handleInstall}
                        disabled={installing}
                      >
                        {installing ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                            Installing...
                          </>
                        ) : (
                          <>
                            <CloudArrowDownIcon className="h-5 w-5 mr-1" />
                            {isUpdate ? 'Update' : 'Install'}
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 disabled:opacity-50 sm:col-start-1 sm:mt-0"
                        onClick={onClose}
                        disabled={installing}
                      >
                        Cancel
                      </button>
                    </>
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

export default InstallConfirmModal;