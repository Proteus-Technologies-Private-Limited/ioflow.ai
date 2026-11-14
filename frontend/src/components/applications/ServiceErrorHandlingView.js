import React, { useState } from 'react';
import {
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  CodeBracketIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DocumentTextIcon,
  BoltIcon
} from '@heroicons/react/24/outline';
import CodeBlock from '../CodeBlock';

const ServiceErrorHandlingView = ({ service }) => {
  const [expandedSections, setExpandedSections] = useState({
    responseConfig: false,
    outputSchema: false,
    errorSchema: false,
    commonErrors: false,
    retryConfig: false
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  // Parse JSON configs
  const responseConfig = service.response_config ? 
    (typeof service.response_config === 'string' ? JSON.parse(service.response_config) : service.response_config) : null;
  const errorSchema = service.error_schema ? 
    (typeof service.error_schema === 'string' ? JSON.parse(service.error_schema) : service.error_schema) : null;
  const outputSchema = service.output_schema ? 
    (typeof service.output_schema === 'string' ? JSON.parse(service.output_schema) : service.output_schema) : null;

  if (!responseConfig && !errorSchema && !outputSchema) {
    return (
      <div className="text-gray-500 text-sm p-4">
        <InformationCircleIcon className="w-5 h-5 inline-block mr-2" />
        No error handling configuration available for this service.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Response Configuration */}
      {responseConfig && (
        <div className="bg-white rounded-lg border border-gray-200">
          <button
            onClick={() => toggleSection('responseConfig')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center">
              <BoltIcon className="w-5 h-5 text-gray-400 mr-2" />
              <h3 className="text-sm font-medium text-gray-900">Response Configuration</h3>
            </div>
            {expandedSections.responseConfig ? 
              <ChevronDownIcon className="w-4 h-4 text-gray-400" /> : 
              <ChevronRightIcon className="w-4 h-4 text-gray-400" />
            }
          </button>
          
          {expandedSections.responseConfig && (
            <div className="px-4 pb-4 border-t border-gray-100">
              {/* Response Type */}
              <div className="mt-3">
                <h4 className="text-xs font-medium text-gray-700 mb-1">Response Type</h4>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
                  {responseConfig.response_type || 'json'}
                </span>
              </div>
              
              {/* Info about custom status codes */}
              {responseConfig.success_check?.success_status_codes && responseConfig.success_check.success_status_codes.includes(400) && (
                <div className="mt-3 bg-blue-50 border border-blue-200 rounded p-2">
                  <div className="flex items-start">
                    <InformationCircleIcon className="w-4 h-4 text-blue-400 mt-0.5 mr-2 flex-shrink-0" />
                    <div className="text-xs text-blue-700">
                      <span className="font-medium">Note:</span> This service treats HTTP 400 responses as valid. 
                      This is useful when the API returns 400 for "no data found" scenarios, allowing the flow to continue normally.
                    </div>
                  </div>
                </div>
              )}

              {/* Success Check */}
              {responseConfig.success_check && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium text-gray-700 mb-1">Success Validation</h4>
                  <div className="bg-gray-50 rounded p-2">
                    <div className="text-xs text-gray-600">
                      <span className="font-medium">Type:</span> {responseConfig.success_check.type}
                    </div>
                    
                    {/* Status Code Configuration */}
                    {responseConfig.success_check.type === 'status_code' && (
                      <>
                        {responseConfig.success_check.success_status_codes ? (
                          <div className="text-xs text-gray-600 mt-1">
                            <span className="font-medium">Success Status Codes:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {responseConfig.success_check.success_status_codes.map(code => (
                                <span key={code} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                  {code}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <div className="text-xs text-gray-600 mt-1">
                            <span className="font-medium">Default Behavior:</span>
                            <div className="mt-1">
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 mr-1">
                                200-399
                              </span>
                              <span className="text-gray-500">Success</span>
                              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800 ml-2 mr-1">
                                400+
                              </span>
                              <span className="text-gray-500">Error</span>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                    
                    {/* Field Value Configuration */}
                    {responseConfig.success_check.field && (
                      <div className="text-xs text-gray-600 mt-1">
                        <span className="font-medium">Field:</span> <code className="bg-gray-200 px-1 rounded">{responseConfig.success_check.field}</code>
                      </div>
                    )}
                    {responseConfig.success_check.expected !== undefined && (
                      <div className="text-xs text-gray-600 mt-1">
                        <span className="font-medium">Expected:</span> <code className="bg-gray-200 px-1 rounded">{String(responseConfig.success_check.expected)}</code>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Error Extraction */}
              {responseConfig.error_extraction && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium text-gray-700 mb-1">Error Extraction</h4>
                  <div className="bg-gray-50 rounded p-2 space-y-1">
                    {responseConfig.error_extraction.error_field && (
                      <div className="text-xs text-gray-600">
                        <span className="font-medium">Error Field:</span> <code className="bg-gray-200 px-1 rounded">{responseConfig.error_extraction.error_field}</code>
                      </div>
                    )}
                    {responseConfig.error_extraction.message_field && (
                      <div className="text-xs text-gray-600">
                        <span className="font-medium">Message Field:</span> <code className="bg-gray-200 px-1 rounded">{responseConfig.error_extraction.message_field}</code>
                      </div>
                    )}
                    {responseConfig.error_extraction.code_field && (
                      <div className="text-xs text-gray-600">
                        <span className="font-medium">Code Field:</span> <code className="bg-gray-200 px-1 rounded">{responseConfig.error_extraction.code_field}</code>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Common Errors */}
      {responseConfig?.common_errors && (
        <div className="bg-white rounded-lg border border-gray-200">
          <button
            onClick={() => toggleSection('commonErrors')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center">
              <ExclamationTriangleIcon className="w-5 h-5 text-yellow-500 mr-2" />
              <h3 className="text-sm font-medium text-gray-900">Common Error Codes</h3>
              <span className="ml-2 text-xs text-gray-500">({Object.keys(responseConfig.common_errors).length})</span>
            </div>
            {expandedSections.commonErrors ? 
              <ChevronDownIcon className="w-4 h-4 text-gray-400" /> : 
              <ChevronRightIcon className="w-4 h-4 text-gray-400" />
            }
          </button>
          
          {expandedSections.commonErrors && (
            <div className="px-4 pb-4 border-t border-gray-100">
              <div className="mt-3 space-y-2">
                {Object.entries(responseConfig.common_errors).map(([code, description]) => (
                  <div key={code} className="border border-gray-200 rounded-md p-2">
                    <div className="flex items-start">
                      <code className="text-xs font-mono bg-red-50 text-red-700 px-2 py-0.5 rounded">
                        {code}
                      </code>
                      <p className="ml-3 text-xs text-gray-600 flex-1">{description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Retry Configuration */}
      {responseConfig?.retry_config && (
        <div className="bg-white rounded-lg border border-gray-200">
          <button
            onClick={() => toggleSection('retryConfig')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center">
              <ArrowPathIcon className="w-5 h-5 text-gray-400 mr-2" />
              <h3 className="text-sm font-medium text-gray-900">Retry Configuration</h3>
            </div>
            {expandedSections.retryConfig ? 
              <ChevronDownIcon className="w-4 h-4 text-gray-400" /> : 
              <ChevronRightIcon className="w-4 h-4 text-gray-400" />
            }
          </button>
          
          {expandedSections.retryConfig && (
            <div className="px-4 pb-4 border-t border-gray-100">
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <h4 className="text-xs font-medium text-gray-700">Max Retries</h4>
                  <p className="text-sm text-gray-900">{responseConfig.retry_config.max_retries || 0}</p>
                </div>
                <div>
                  <h4 className="text-xs font-medium text-gray-700">Backoff Strategy</h4>
                  <p className="text-sm text-gray-900">{responseConfig.retry_config.backoff_strategy || 'none'}</p>
                </div>
                <div>
                  <h4 className="text-xs font-medium text-gray-700">Initial Delay</h4>
                  <p className="text-sm text-gray-900">{responseConfig.retry_config.initial_delay || 0}ms</p>
                </div>
                <div>
                  <h4 className="text-xs font-medium text-gray-700">Max Delay</h4>
                  <p className="text-sm text-gray-900">{responseConfig.retry_config.max_delay || 0}ms</p>
                </div>
              </div>
              
              {responseConfig.retry_config.retry_on_errors && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium text-gray-700 mb-1">Retry on Errors</h4>
                  <div className="flex flex-wrap gap-1">
                    {responseConfig.retry_config.retry_on_errors.map(error => (
                      <span key={error} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-800">
                        {error}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Output Schema */}
      {outputSchema && (
        <div className="bg-white rounded-lg border border-gray-200">
          <button
            onClick={() => toggleSection('outputSchema')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center">
              <CheckCircleIcon className="w-5 h-5 text-green-500 mr-2" />
              <h3 className="text-sm font-medium text-gray-900">Success Response Schema</h3>
            </div>
            {expandedSections.outputSchema ? 
              <ChevronDownIcon className="w-4 h-4 text-gray-400" /> : 
              <ChevronRightIcon className="w-4 h-4 text-gray-400" />
            }
          </button>
          
          {expandedSections.outputSchema && (
            <div className="px-4 pb-4 border-t border-gray-100">
              <div className="mt-3">
                <CodeBlock
                  code={JSON.stringify(outputSchema, null, 2)}
                  language="json"
                  title="Output Schema"
                />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error Schema */}
      {errorSchema && (
        <div className="bg-white rounded-lg border border-gray-200">
          <button
            onClick={() => toggleSection('errorSchema')}
            className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center">
              <ExclamationTriangleIcon className="w-5 h-5 text-red-500 mr-2" />
              <h3 className="text-sm font-medium text-gray-900">Error Response Schema</h3>
            </div>
            {expandedSections.errorSchema ? 
              <ChevronDownIcon className="w-4 h-4 text-gray-400" /> : 
              <ChevronRightIcon className="w-4 h-4 text-gray-400" />
            }
          </button>
          
          {expandedSections.errorSchema && (
            <div className="px-4 pb-4 border-t border-gray-100">
              <div className="mt-3">
                <CodeBlock
                  code={JSON.stringify(errorSchema, null, 2)}
                  language="json"
                  title="Error Schema"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ServiceErrorHandlingView;