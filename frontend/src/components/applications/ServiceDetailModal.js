import React, { useState } from 'react';
import ReactDOM from 'react-dom';
import {
  XMarkIcon,
  InformationCircleIcon,
  DocumentTextIcon,
  BoltIcon,
  CodeBracketIcon,
  CogIcon,
  PencilSquareIcon
} from '@heroicons/react/24/outline';
import ServiceErrorHandlingView from './ServiceErrorHandlingView';
import ServiceEditModal from './ServiceEditModal';
import CodeBlock from '../CodeBlock';
import { applicationService } from '../../services/applicationService';

const ServiceDetailModal = ({ service, application, onClose, onServiceUpdated }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [showEditModal, setShowEditModal] = useState(false);
  const [currentService, setCurrentService] = useState(service);

  console.log('ServiceDetailModal received service:', service);
  console.log('Service headers_template:', service?.headers_template);

  if (!service) return null;

  // Parse configurations
  const serviceConfig = service.service_config ? 
    (typeof service.service_config === 'string' ? JSON.parse(service.service_config) : service.service_config) : {};
  // Look for input schema in multiple places
  const inputSchema = service.input_schema ? 
    (typeof service.input_schema === 'string' ? JSON.parse(service.input_schema) : service.input_schema) : 
    (service.parameter_schema ? 
      (typeof service.parameter_schema === 'string' ? JSON.parse(service.parameter_schema) : service.parameter_schema) :
      (serviceConfig.parameter_schema || null));
  const outputSchema = service.output_schema ? 
    (typeof service.output_schema === 'string' ? JSON.parse(service.output_schema) : service.output_schema) : null;
  const sampleInput = service.sample_input ? 
    (typeof service.sample_input === 'string' ? JSON.parse(service.sample_input) : service.sample_input) : null;
  const sampleOutput = service.sample_output ? 
    (typeof service.sample_output === 'string' ? JSON.parse(service.sample_output) : service.sample_output) : null;
  
  // Get parameters from service or service_config
  const parameters = service.parameters || serviceConfig.parameters || [];

  const handleServiceUpdate = async (serviceId, updateData) => {
    const updatedService = await applicationService.updateService(application.app_id, serviceId, updateData);
    setCurrentService(updatedService);
    setShowEditModal(false);
    if (onServiceUpdated) {
      onServiceUpdated(updatedService);
    }
  };

  const tabs = [
    { id: 'overview', name: 'Overview', icon: InformationCircleIcon },
    { id: 'parameters', name: 'Parameters', icon: CogIcon },
    { id: 'error-handling', name: 'Error Handling', icon: BoltIcon },
    { id: 'schemas', name: 'Schemas', icon: DocumentTextIcon },
    { id: 'raw-config', name: 'Raw Config', icon: CodeBracketIcon }
  ];

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9998]">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col z-[9999]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900">{(currentService || service).display_name}</h2>
            <p className="text-sm text-gray-500">{(currentService || service).service_name}</p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowEditModal(true)}
              className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              <PencilSquareIcon className="w-4 h-4 mr-1.5" />
              Edit
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex items-center py-2 px-1 border-b-2 font-medium text-sm
                  ${activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                <tab.icon className="w-4 h-4 mr-2" />
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Basic Information */}
              <div>
                <h3 className="text-sm font-medium text-gray-900 mb-3">Basic Information</h3>
                <dl className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Service Type</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
                        {service.service_type}
                      </span>
                    </dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Parameter Method</dt>
                    <dd className="mt-1 text-sm text-gray-900">{serviceConfig?.request_config?.parameter_method || 'Not specified'}</dd>
                  </div>
                  {serviceConfig?.request_config?.method && (
                    <div>
                      <dt className="text-sm font-medium text-gray-500">HTTP Method</dt>
                      <dd className="mt-1 text-sm text-gray-900">{serviceConfig.request_config.method}</dd>
                    </div>
                  )}
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Status</dt>
                    <dd className="mt-1 text-sm text-gray-900">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        service.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {service.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </dd>
                  </div>
                </dl>
              </div>

              {/* Description */}
              {service.description && (
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-2">Description</h3>
                  <p className="text-sm text-gray-600">{service.description}</p>
                </div>
              )}

              {/* Endpoint */}
              {service.endpoint_template && (
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-2">Endpoint Template</h3>
                  <div className="bg-gray-50 rounded-md p-3">
                    <code className="text-sm text-gray-900">{service.endpoint_template}</code>
                  </div>
                </div>
              )}

              {/* Headers - From service config request_config or top-level */}
              {(() => {
                // Look for headers_template in multiple locations
                const headers = serviceConfig?.request_config?.headers_template || 
                               serviceConfig?.headers_template || 
                               service.headers_template;
                
                console.log('Looking for headers_template in:', {
                  'serviceConfig.request_config.headers_template': serviceConfig?.request_config?.headers_template,
                  'serviceConfig.headers_template': serviceConfig?.headers_template,
                  'service.headers_template': service.headers_template
                });
                
                // Check if we have headers and they're not empty
                const hasHeaders = headers && (
                  typeof headers === 'string' ? headers.trim() !== '{}' : 
                  (typeof headers === 'object' && Object.keys(headers).length > 0)
                );
                
                if (!hasHeaders) return null;
                
                return (
                  <div>
                    <h3 className="text-sm font-medium text-gray-900 mb-2">Headers Template</h3>
                    <CodeBlock
                      code={JSON.stringify(
                        typeof headers === 'string' ? JSON.parse(headers) : headers, 
                        null, 
                        2
                      )}
                      language="json"
                    />
                  </div>
                );
              })()}

              {/* Body Template */}
              {service.body_template && (
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-2">Body Template</h3>
                  <CodeBlock
                    code={JSON.stringify(
                      typeof service.body_template === 'string' ? 
                        JSON.parse(service.body_template) : 
                        service.body_template, 
                      null, 
                      2
                    )}
                    language="json"
                  />
                </div>
              )}
            </div>
          )}

          {activeTab === 'parameters' && (
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-gray-900">Service Parameters</h3>
              {(() => {
                // If we have direct parameters, use them
                if (parameters.length > 0) {
                  return (
                    <div className="space-y-3">
                      {parameters.map((param, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h4 className="text-sm font-medium text-gray-900">
                            {param.friendly_name || param.param_name}
                          </h4>
                          <p className="text-sm text-gray-500 mt-1">
                            <code className="bg-gray-100 px-1 rounded">{param.param_name}</code>
                            {param.required && (
                              <span className="ml-2 text-xs text-red-600 font-medium">Required</span>
                            )}
                          </p>
                        </div>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-800">
                          {param.data_type}
                        </span>
                      </div>
                      
                      {param.description && (
                        <p className="mt-2 text-sm text-gray-600">{param.description}</p>
                      )}
                      
                      <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                        {param.ui_control && (
                          <div>
                            <span className="text-gray-500">UI Control:</span>{' '}
                            <span className="text-gray-900">{param.ui_control}</span>
                          </div>
                        )}
                        {param.default_value !== undefined && (
                          <div>
                            <span className="text-gray-500">Default:</span>{' '}
                            <span className="text-gray-900">{String(param.default_value)}</span>
                          </div>
                        )}
                        {param.min_value !== undefined && (
                          <div>
                            <span className="text-gray-500">Min:</span>{' '}
                            <span className="text-gray-900">{param.min_value}</span>
                          </div>
                        )}
                        {param.max_value !== undefined && (
                          <div>
                            <span className="text-gray-500">Max:</span>{' '}
                            <span className="text-gray-900">{param.max_value}</span>
                          </div>
                        )}
                        {param.pattern && (
                          <div className="col-span-2">
                            <span className="text-gray-500">Pattern:</span>{' '}
                            <code className="text-gray-900 bg-gray-100 px-1 rounded">{param.pattern}</code>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                    </div>
                  );
                }
                
                // Fallback to input schema
                if (inputSchema?.properties) {
                  const schemaParams = Object.entries(inputSchema.properties).map(([key, schema]) => ({
                    param_name: key,
                    friendly_name: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                    description: schema.description || '',
                    data_type: schema.type || 'string',
                    required: inputSchema.required?.includes(key) || false,
                    pattern: schema.pattern,
                    example: schema.example,
                    format: schema.format,
                    enum_values: schema.enum,
                    default_value: schema.default,
                    min_value: schema.minimum,
                    max_value: schema.maximum,
                    parameter_lookup: schema.parameterLookup
                  }));
                  
                  return (
                    <div className="space-y-3">
                      {schemaParams.map((param, index) => (
                        <div key={index} className="border border-gray-200 rounded-lg p-4">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <h4 className="text-sm font-medium text-gray-900">
                                {param.friendly_name}
                              </h4>
                              <p className="text-sm text-gray-500 mt-1">
                                <code className="bg-gray-100 px-1 rounded">{param.param_name}</code>
                                {param.required && (
                                  <span className="ml-2 text-xs text-red-600 font-medium">Required</span>
                                )}
                              </p>
                            </div>
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-800">
                              {param.data_type}
                              {param.format && ` (${param.format})`}
                            </span>
                          </div>
                          
                          {param.description && (
                            <p className="mt-2 text-sm text-gray-600">{param.description}</p>
                          )}
                          
                          {param.parameter_lookup && (
                            <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
                              <div className="flex items-center mb-2">
                                <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
                                  Parameter Lookup
                                </span>
                              </div>
                              <div className="text-xs space-y-1">
                                <div><span className="font-medium text-blue-900">Type:</span> <span className="text-blue-700">{param.parameter_lookup.type}</span></div>
                                {param.parameter_lookup.service && (
                                  <div><span className="font-medium text-blue-900">Service:</span> <span className="text-blue-700">{param.parameter_lookup.service}</span></div>
                                )}
                                {param.parameter_lookup.extractPath && (
                                  <div><span className="font-medium text-blue-900">Extract Path:</span> <span className="text-blue-700">{param.parameter_lookup.extractPath}</span></div>
                                )}
                                {param.parameter_lookup.valueField && (
                                  <div><span className="font-medium text-blue-900">Value Field:</span> <span className="text-blue-700">{param.parameter_lookup.valueField}</span></div>
                                )}
                                {param.parameter_lookup.displayField && (
                                  <div><span className="font-medium text-blue-900">Display Field:</span> <span className="text-blue-700">{param.parameter_lookup.displayField}</span></div>
                                )}
                                {param.parameter_lookup.description && (
                                  <div><span className="font-medium text-blue-900">Lookup Description:</span> <span className="text-blue-700">{param.parameter_lookup.description}</span></div>
                                )}
                              </div>
                            </div>
                          )}
                          
                          {param.example && (
                            <div className="mt-2 text-xs text-gray-500">
                              <span className="font-medium">Example:</span>{' '}
                              <code className="bg-gray-100 px-1 rounded">{param.example}</code>
                            </div>
                          )}
                          
                          <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                            {param.enum_values && (
                              <div className="col-span-2">
                                <span className="text-gray-500">Options:</span>{' '}
                                <span className="text-gray-900">{param.enum_values.join(', ')}</span>
                              </div>
                            )}
                            {param.default_value !== undefined && (
                              <div>
                                <span className="text-gray-500">Default:</span>{' '}
                                <span className="text-gray-900">{String(param.default_value)}</span>
                              </div>
                            )}
                            {param.min_value !== undefined && (
                              <div>
                                <span className="text-gray-500">Min:</span>{' '}
                                <span className="text-gray-900">{param.min_value}</span>
                              </div>
                            )}
                            {param.max_value !== undefined && (
                              <div>
                                <span className="text-gray-500">Max:</span>{' '}
                                <span className="text-gray-900">{param.max_value}</span>
                              </div>
                            )}
                            {param.pattern && (
                              <div className="col-span-2">
                                <span className="text-gray-500">Pattern:</span>{' '}
                                <code className="text-gray-900 bg-gray-100 px-1 rounded">{param.pattern}</code>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                }
                
                // Check if additional properties are allowed
                if (inputSchema?.additionalProperties) {
                  const schemaParams = inputSchema.properties ? Object.entries(inputSchema.properties).map(([key, schema]) => ({
                    param_name: key,
                    friendly_name: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                    description: schema.description || '',
                    data_type: schema.type || 'string',
                    required: inputSchema.required?.includes(key) || false,
                    pattern: schema.pattern,
                    example: schema.example,
                    format: schema.format,
                    enum_values: schema.enum,
                    default_value: schema.default,
                    min_value: schema.minimum,
                    max_value: schema.maximum,
                    parameter_lookup: schema.parameterLookup
                  })) : [];
                  
                  // Show info about dynamic SQL parameters
                  return (
                    <div className="space-y-4">
                      {schemaParams.length > 0 && (
                        <div className="space-y-3">
                          {schemaParams.map((param, index) => (
                            <div key={index} className="border border-gray-200 rounded-lg p-4">
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <h4 className="text-sm font-medium text-gray-900">
                                    {param.friendly_name}
                                  </h4>
                                  <p className="text-sm text-gray-500 mt-1">
                                    <code className="bg-gray-100 px-1 rounded">{param.param_name}</code>
                                    {param.required && (
                                      <span className="ml-2 text-xs text-red-600 font-medium">Required</span>
                                    )}
                                  </p>
                                </div>
                                <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-gray-100 text-gray-800">
                                  {param.data_type}
                                  {param.format && ` (${param.format})`}
                                </span>
                              </div>
                              
                              {param.description && (
                                <p className="mt-2 text-sm text-gray-600">{param.description}</p>
                              )}
                              
                              {param.parameter_lookup && (
                                <div className="mt-2 p-3 bg-blue-50 border border-blue-200 rounded-md">
                                  <div className="flex items-center mb-2">
                                    <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-800">
                                      Parameter Lookup
                                    </span>
                                  </div>
                                  <div className="text-xs space-y-1">
                                    <div><span className="font-medium text-blue-900">Type:</span> <span className="text-blue-700">{param.parameter_lookup.type}</span></div>
                                    {param.parameter_lookup.service && (
                                      <div><span className="font-medium text-blue-900">Service:</span> <span className="text-blue-700">{param.parameter_lookup.service}</span></div>
                                    )}
                                    {param.parameter_lookup.extractPath && (
                                      <div><span className="font-medium text-blue-900">Extract Path:</span> <span className="text-blue-700">{param.parameter_lookup.extractPath}</span></div>
                                    )}
                                    {param.parameter_lookup.valueField && (
                                      <div><span className="font-medium text-blue-900">Value Field:</span> <span className="text-blue-700">{param.parameter_lookup.valueField}</span></div>
                                    )}
                                    {param.parameter_lookup.displayField && (
                                      <div><span className="font-medium text-blue-900">Display Field:</span> <span className="text-blue-700">{param.parameter_lookup.displayField}</span></div>
                                    )}
                                    {param.parameter_lookup.description && (
                                      <div><span className="font-medium text-blue-900">Lookup Description:</span> <span className="text-blue-700">{param.parameter_lookup.description}</span></div>
                                    )}
                                  </div>
                                </div>
                              )}
                              
                              {param.example && (
                                <div className="mt-2 text-xs text-gray-500">
                                  <span className="font-medium">Example:</span>{' '}
                                  <code className="bg-gray-100 px-1 rounded">{param.example}</code>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <h4 className="text-sm font-medium text-blue-900 mb-2">Additional Properties Supported</h4>
                        <p className="text-sm text-blue-800 mb-3">
                          This service accepts additional properties beyond the defined parameters. You can pass any extra parameters needed for your use case.
                        </p>
                        
                        {service.service_type === 'database_query' && (
                          <>
                            <div className="mt-3">
                              <p className="text-xs font-medium text-blue-900 mb-1">Example SQL Query:</p>
                              <code className="block bg-white p-2 rounded text-xs text-gray-800">
                                SELECT * FROM users WHERE status = :status AND created_at &gt; :start_date
                              </code>
                            </div>
                            
                            <div className="mt-3">
                              <p className="text-xs font-medium text-blue-900 mb-1">Required Parameters:</p>
                              <div className="bg-white p-2 rounded">
                                <code className="text-xs text-gray-800">
                                  {`{
  "sql": "SELECT * FROM users WHERE status = :status AND created_at > :start_date",
  "status": "active",
  "start_date": "2024-01-01"
}`}
                                </code>
                              </div>
                            </div>
                            
                            <p className="text-xs text-blue-700 mt-3">
                              <strong>Note:</strong> All bind variables (parameters with : prefix) referenced in your SQL must be provided as parameters when calling this service.
                            </p>
                          </>
                        )}
                        
                        {service.service_type !== 'database_query' && (
                          <div className="mt-3">
                            <p className="text-xs text-blue-700">
                              <strong>Note:</strong> Additional properties can be passed as needed. Check the service documentation for specific requirements.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                }
                
                return <p className="text-sm text-gray-500">No parameters defined for this service.</p>;
              })()}
            </div>
          )}

          {activeTab === 'error-handling' && (
            <ServiceErrorHandlingView service={service} />
          )}

          {activeTab === 'schemas' && (
            <div className="space-y-6">
              {/* Input Schema */}
              {inputSchema && Object.keys(inputSchema).length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-3">Input Schema</h3>
                  <CodeBlock
                    code={JSON.stringify(inputSchema, null, 2)}
                    language="json"
                    title="JSON Schema"
                  />
                </div>
              )}

              {/* Sample Input */}
              {sampleInput && Object.keys(sampleInput).length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-3">Sample Input</h3>
                  <CodeBlock
                    code={JSON.stringify(sampleInput, null, 2)}
                    language="json"
                    title="Example Input Data"
                  />
                </div>
              )}

              {/* Output Schema */}
              {outputSchema && Object.keys(outputSchema).length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-3">Output Schema</h3>
                  <CodeBlock
                    code={JSON.stringify(outputSchema, null, 2)}
                    language="json"
                    title="JSON Schema"
                  />
                </div>
              )}

              {/* Sample Output */}
              {sampleOutput && Object.keys(sampleOutput).length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-900 mb-3">Sample Output</h3>
                  <CodeBlock
                    code={JSON.stringify(sampleOutput, null, 2)}
                    language="json"
                    title="Example Output Data"
                  />
                </div>
              )}

              {!inputSchema && !outputSchema && !sampleInput && !sampleOutput && (
                <p className="text-sm text-gray-500">No schemas or examples defined for this service.</p>
              )}
            </div>
          )}

          {activeTab === 'raw-config' && (
            <div>
              <h3 className="text-sm font-medium text-gray-900 mb-3">Raw Service Configuration</h3>
              <CodeBlock
                code={JSON.stringify(currentService || service, null, 2)}
                language="json"
                title="Complete Service Object"
              />
            </div>
          )}
        </div>
      </div>
      
      {/* Edit Modal */}
      {showEditModal && (
        <ServiceEditModal
          service={currentService || service}
          application={application}
          onClose={() => setShowEditModal(false)}
          onSave={handleServiceUpdate}
        />
      )}
    </div>,
    document.body
  );
};

export default ServiceDetailModal;