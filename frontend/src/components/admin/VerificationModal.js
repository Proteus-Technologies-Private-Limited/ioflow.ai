import React from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import { XMarkIcon, CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

const VerificationModal = ({ open, onClose, application, verificationData }) => {
  if (!application || !verificationData) return null;

  const hasIssues = verificationData.summary?.total_mismatches > 0;

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
              <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-4xl">
                <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                  <div className="sm:flex sm:items-start">
                    <div className="w-full">
                      <div className="flex items-center justify-between mb-4">
                        <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900">
                          Verification Results - {application.name}
                        </Dialog.Title>
                        <button
                          type="button"
                          className="rounded-md bg-white text-gray-400 hover:text-gray-500"
                          onClick={onClose}
                        >
                          <XMarkIcon className="h-6 w-6" />
                        </button>
                      </div>

                      {!verificationData.installed ? (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
                          <p className="text-sm text-yellow-800">{verificationData.message}</p>
                        </div>
                      ) : (
                        <>
                          {/* Summary */}
                          <div className={`rounded-md p-4 mb-4 ${hasIssues ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'}`}>
                            <div className="flex">
                              {hasIssues ? (
                                <ExclamationTriangleIcon className="h-5 w-5 text-red-400 mr-2" />
                              ) : (
                                <CheckCircleIcon className="h-5 w-5 text-green-400 mr-2" />
                              )}
                              <div>
                                <h4 className={`text-sm font-medium ${hasIssues ? 'text-red-800' : 'text-green-800'}`}>
                                  {hasIssues ? 'Verification Failed' : 'Verification Passed'}
                                </h4>
                                <div className="mt-2 text-sm">
                                  <p className={hasIssues ? 'text-red-700' : 'text-green-700'}>
                                    Total Services: {verificationData.summary.total_seed_services} seed / {verificationData.summary.total_installed_services} installed
                                  </p>
                                  {hasIssues && (
                                    <p className="text-red-700">
                                      Services with issues: {verificationData.summary.services_with_issues}
                                    </p>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Service Comparisons */}
                          <div className="space-y-4 max-h-96 overflow-y-auto">
                            {verificationData.service_comparison.map((service, index) => (
                              <div key={index} className="border rounded-lg p-4">
                                <div className="flex items-center justify-between mb-2">
                                  <h5 className="font-medium text-gray-900">{service.service_name}</h5>
                                  {service.parameter_mismatches.length > 0 ? (
                                    <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
                                      {service.parameter_mismatches.length} issues
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                                      OK
                                    </span>
                                  )}
                                </div>

                                {!service.found_in_installed && (
                                  <div className="bg-yellow-50 border border-yellow-200 rounded p-2 mb-2">
                                    <p className="text-xs text-yellow-800">Service not found in installed application</p>
                                  </div>
                                )}

                                {/* Parameter Comparison */}
                                {(service.seed_parameters.length > 0 || service.installed_parameters.length > 0) && (
                                  <div className="mt-2">
                                    <h6 className="text-xs font-medium text-gray-700 mb-1">Parameters:</h6>
                                    <div className="grid grid-cols-2 gap-4 text-xs">
                                      <div>
                                        <p className="font-medium text-gray-600 mb-1">Seed JSON:</p>
                                        {service.seed_parameters.length > 0 ? (
                                          <ul className="space-y-1">
                                            {service.seed_parameters.map((param, idx) => (
                                              <li key={idx} className="bg-gray-50 p-1 rounded">
                                                <span className="font-medium">{param.name}</span>
                                                {param.mapping !== param.name && (
                                                  <span className="text-gray-500"> → {param.mapping}</span>
                                                )}
                                              </li>
                                            ))}
                                          </ul>
                                        ) : (
                                          <p className="text-gray-500">No parameters</p>
                                        )}
                                      </div>
                                      <div>
                                        <p className="font-medium text-gray-600 mb-1">Installed:</p>
                                        {service.installed_parameters.length > 0 ? (
                                          <ul className="space-y-1">
                                            {service.installed_parameters.map((param, idx) => (
                                              <li key={idx} className="bg-gray-50 p-1 rounded">
                                                <span className="font-medium">{param.name}</span>
                                                {param.mapping !== param.name && (
                                                  <span className="text-gray-500"> → {param.mapping}</span>
                                                )}
                                              </li>
                                            ))}
                                          </ul>
                                        ) : (
                                          <p className="text-gray-500">No parameters</p>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                )}

                                {/* Mismatches */}
                                {service.parameter_mismatches.length > 0 && (
                                  <div className="mt-2 bg-red-50 border border-red-200 rounded p-2">
                                    <h6 className="text-xs font-medium text-red-800 mb-1">Issues:</h6>
                                    <ul className="space-y-1 text-xs">
                                      {service.parameter_mismatches.map((mismatch, idx) => (
                                        <li key={idx} className="text-red-700">
                                          <span className="font-medium">{mismatch.param_name}:</span>
                                          {mismatch.issue === 'missing_in_installed' ? (
                                            <span> Missing in installed (expected mapping: {mismatch.seed_mapping})</span>
                                          ) : (
                                            <span> Mapping mismatch - seed: "{mismatch.seed_mapping}" vs installed: "{mismatch.installed_mapping}"</span>
                                          )}
                                        </li>
                                      ))}
                                    </ul>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>

                          {/* General Mismatches */}
                          {verificationData.mismatches.length > 0 && (
                            <div className="mt-4 bg-red-50 border border-red-200 rounded p-3">
                              <h6 className="text-sm font-medium text-red-800 mb-1">General Issues:</h6>
                              <ul className="list-disc list-inside space-y-1">
                                {verificationData.mismatches.map((issue, idx) => (
                                  <li key={idx} className="text-sm text-red-700">{issue}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                  {hasIssues && verificationData.installed && (
                    <button
                      type="button"
                      onClick={() => {
                        onClose();
                        // Optionally trigger reinstall
                      }}
                      className="inline-flex w-full justify-center rounded-md bg-primary-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-primary-500 sm:ml-3 sm:w-auto"
                    >
                      Reinstall Application
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={onClose}
                    className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
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

export default VerificationModal;