import React from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

const UninstallConfirmModal = ({ open, onClose, application, warning, onConfirm, uninstalling }) => {
  if (!application) return null;

  const hasSubscriptions = warning?.subscription_count > 0;

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
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-red-100 sm:mx-0 sm:h-10 sm:w-10">
                    <ExclamationTriangleIcon className="h-6 w-6 text-red-600" aria-hidden="true" />
                  </div>
                  <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left">
                    <Dialog.Title as="h3" className="text-base font-semibold leading-6 text-gray-900">
                      Uninstall Application
                    </Dialog.Title>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        Are you sure you want to uninstall "{application.name}"? 
                      </p>
                      
                      {hasSubscriptions && warning && (
                        <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-md p-3">
                          <p className="text-sm text-yellow-800 font-medium">
                            {warning.message}
                          </p>
                          <p className="text-sm text-yellow-700 mt-1">
                            This application has {warning.subscription_count} active subscription{warning.subscription_count > 1 ? 's' : ''}.
                          </p>
                          {warning.suggestion && (
                            <p className="text-sm text-yellow-600 mt-2">
                              {warning.suggestion}
                            </p>
                          )}
                        </div>
                      )}

                      {!hasSubscriptions && (
                        <div className="mt-3 bg-gray-50 border border-gray-200 rounded-md p-3">
                          <p className="text-sm text-gray-700">
                            This will remove:
                          </p>
                          <ul className="mt-1 list-disc list-inside text-sm text-gray-600">
                            <li>All services ({application.service_count || 0})</li>
                            <li>All events ({application.event_count || 0})</li>
                            <li>Application configuration</li>
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                  {hasSubscriptions ? (
                    <>
                      <button
                        type="button"
                        className="inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 sm:ml-3 sm:w-auto"
                        onClick={() => onConfirm(true)}
                        disabled={uninstalling}
                      >
                        {uninstalling ? 'Uninstalling...' : 'Force Uninstall'}
                      </button>
                      <button
                        type="button"
                        className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                        onClick={onClose}
                        disabled={uninstalling}
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="inline-flex w-full justify-center rounded-md bg-red-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-red-500 sm:ml-3 sm:w-auto"
                        onClick={() => onConfirm(false)}
                        disabled={uninstalling}
                      >
                        {uninstalling ? 'Uninstalling...' : 'Uninstall'}
                      </button>
                      <button
                        type="button"
                        className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                        onClick={onClose}
                        disabled={uninstalling}
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

export default UninstallConfirmModal;