import React, { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import {
  ExclamationTriangleIcon,
  XMarkIcon,
  ExclamationCircleIcon
} from '@heroicons/react/24/outline';

const ValidationDetailsModal = ({ open, onClose, application }) => {
  if (!application || !application.validation_status) {
    return null;
  }

  const { valid, errors, warnings } = application.validation_status;

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
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl sm:p-6">
                <div className="absolute right-0 top-0 hidden pr-4 pt-4 sm:block">
                  <button
                    type="button"
                    className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
                    onClick={onClose}
                  >
                    <span className="sr-only">Close</span>
                    <XMarkIcon className="h-6 w-6" aria-hidden="true" />
                  </button>
                </div>
                
                <div>
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-yellow-100">
                    <ExclamationTriangleIcon className="h-6 w-6 text-yellow-600" aria-hidden="true" />
                  </div>
                  <div className="mt-3 text-center sm:mt-5">
                    <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900">
                      Schema Validation Report
                    </Dialog.Title>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        {application.name} - {valid ? 'Valid with warnings' : 'Validation failed'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-5 space-y-4">
                  {errors && errors.length > 0 && (
                    <div>
                      <h4 className="flex items-center text-sm font-medium text-red-800 mb-2">
                        <ExclamationCircleIcon className="h-5 w-5 mr-2" />
                        Validation Errors ({errors.length})
                      </h4>
                      <div className="bg-red-50 border border-red-200 rounded-md p-3">
                        <ul className="list-disc list-inside space-y-1">
                          {errors.map((error, index) => (
                            <li key={index} className="text-sm text-red-700">
                              {typeof error === 'object' ? (
                                <div>
                                  <span className="font-medium">
                                    {error.path?.join(' > ') || 'Unknown path'}:
                                  </span>{' '}
                                  {error.message}
                                </div>
                              ) : (
                                error
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  {warnings && warnings.length > 0 && (
                    <div>
                      <h4 className="flex items-center text-sm font-medium text-yellow-800 mb-2">
                        <ExclamationTriangleIcon className="h-5 w-5 mr-2" />
                        Warnings ({warnings.length})
                      </h4>
                      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3">
                        <ul className="list-disc list-inside space-y-1">
                          {warnings.map((warning, index) => (
                            <li key={index} className="text-sm text-yellow-700">
                              {typeof warning === 'object' ? (
                                <div>
                                  <span className="font-medium">
                                    {warning.path?.join(' > ') || 'Unknown path'}:
                                  </span>{' '}
                                  {warning.message}
                                  {warning.valid_values && (
                                    <div className="mt-1 text-xs">
                                      Valid values: {warning.valid_values.join(', ')}
                                    </div>
                                  )}
                                  {warning.suggestion && (
                                    <div className="mt-1 text-xs italic">
                                      {warning.suggestion}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                warning
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  {(!errors || errors.length === 0) && (!warnings || warnings.length === 0) && (
                    <div className="bg-green-50 border border-green-200 rounded-md p-3">
                      <p className="text-sm text-green-700">
                        No validation issues found. The application schema is valid.
                      </p>
                    </div>
                  )}
                </div>

                <div className="mt-5 sm:mt-6">
                  <button
                    type="button"
                    className="inline-flex w-full justify-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600"
                    onClick={onClose}
                  >
                    Close
                  </button>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition.Root>
  );
};

export default ValidationDetailsModal;