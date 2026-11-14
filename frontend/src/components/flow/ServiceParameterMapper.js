import React, { useState, useEffect } from 'react';
import { ChevronRightIcon, XMarkIcon } from '@heroicons/react/24/outline';
import ParameterMapper from './ParameterMapper';
import { usePluginRegistry } from '../../plugins/registry';

const ServiceParameterMapper = ({ 
  service, 
  sourceSchema, 
  onParametersChange, 
  initialParameters = {},
  availableVariables = []
}) => {
  const [parameters, setParameters] = useState(initialParameters);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const pluginRegistry = usePluginRegistry();

  // Debug logging for service object
  console.log('ServiceParameterMapper - Initial props:', {
    service,
    serviceType: service?.service_type || service?.serviceType,
    serviceConfig: service?.service_config,
    inputSchema: service?.input_schema,
    parameterSchema: service?.parameter_schema,
    seedAppSchema: service?.seed_application_schema,
    allServiceKeys: service ? Object.keys(service) : [],
    sourceSchema,
    initialParameters,
    availableVariables
  });

  // Get service type specific parameter structure
  const getServiceParameterStructure = () => {
    const serviceType = service?.service_type || service?.serviceType;
    // Check for input_schema, parameter_schema, or schema in service_config
    const inputSchema = service?.input_schema || 
                       service?.inputSchema || 
                       service?.parameter_schema ||
                       service?.service_config?.parameter_schema;
    
    console.log('getServiceParameterStructure - Checking schemas:', {
      serviceType,
      inputSchema,
      serviceInputSchema: service?.input_schema,
      serviceParamSchema: service?.parameter_schema,
      configParamSchema: service?.service_config?.parameter_schema
    });
    
    // If custom schema is defined, use it
    if (inputSchema) {
      console.log('getServiceParameterStructure - Using custom inputSchema:', inputSchema);
      return inputSchema;
    }
    
    console.log('getServiceParameterStructure - No custom schema found, using default for type:', serviceType);
    
    // Otherwise, return type-specific default schema
    switch (serviceType) {
      case 'api_call':
        return {
          type: 'object',
          properties: {
            path_params: {
              type: 'object',
              description: 'Path parameters for URL template',
              properties: extractPathParams(service?.service_config?.endpoint_template || '')
            },
            query_params: {
              type: 'object',
              description: 'Query parameters'
            },
            headers: {
              type: 'object',
              description: 'Request headers'
            },
            body: {
              type: 'object',
              description: 'Request body'
            }
          }
        };
        
      case 'webhook':
        return {
          type: 'object',
          properties: {
            payload: {
              type: 'object',
              description: 'Webhook payload data'
            },
            metadata: {
              type: 'object',
              description: 'Additional metadata',
              properties: {
                timestamp: { type: 'string', format: 'date-time' },
                event_type: { type: 'string' },
                source: { type: 'string' }
              }
            }
          }
        };
        
      case 'email_send':
        return {
          type: 'object',
          properties: {
            to: {
              type: 'array',
              items: { type: 'string', format: 'email' },
              description: 'Recipient email addresses'
            },
            cc: {
              type: 'array',
              items: { type: 'string', format: 'email' },
              description: 'CC recipients'
            },
            bcc: {
              type: 'array',
              items: { type: 'string', format: 'email' },
              description: 'BCC recipients'
            },
            template_vars: {
              type: 'object',
              description: 'Variables for email template',
              properties: extractTemplateVars(service?.service_config?.subject_template, service?.service_config?.body_template)
            }
          },
          required: ['to']
        };
        
      case 'llm_api_call':
        return {
          type: 'object',
          properties: {
            prompt_variables: {
              type: 'object',
              description: 'Variables for prompt templates',
              properties: extractTemplateVars(
                service?.service_config?.system_prompt_template,
                service?.service_config?.user_prompt_template
              )
            },
            conversation_history: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  role: { 
                    type: 'string', 
                    enum: ['system', 'user', 'assistant'],
                    description: 'Message role'
                  },
                  content: { 
                    type: 'string',
                    description: 'Message content'
                  }
                },
                required: ['role', 'content']
              },
              description: 'Previous conversation messages'
            }
          }
        };
        
      case 'mcp_call':
        return {
          type: 'object',
          properties: {
            parameters: {
              type: 'object',
              description: 'Tool-specific parameters',
              properties: {} // This would be populated from MCP tool definition
            }
          }
        };
        
      case 'database_query':
        // Database queries use dynamic parameters based on SQL
        return {
          type: 'object',
          properties: {
            sql: {
              type: 'string',
              description: 'SQL query with :param_name placeholders',
              format: 'sql'
            }
          },
          required: ['sql'],
          additionalProperties: true // Allow dynamic parameters
        };
        
      default: {
        // Try plugin registry for parameter hints
        const pluginSchema = pluginRegistry?.getServiceTypeSchema?.(serviceType);
        if (pluginSchema?.parameter_hints) {
          console.log('getServiceParameterStructure - Using plugin registry parameter_hints for:', serviceType);
          return pluginSchema.parameter_hints;
        }
        // Legacy format
        console.log('getServiceParameterStructure - Using legacy/default format for serviceType:', serviceType);
        return {
          type: 'object',
          properties: {},
          additionalProperties: true
        };
      }
    }
  };

  // Extract path parameters from URL template
  const extractPathParams = (urlTemplate) => {
    const params = {};
    const regex = /\{(\w+)\}/g;
    let match;
    
    while ((match = regex.exec(urlTemplate)) !== null) {
      params[match[1]] = {
        type: 'string',
        description: `Path parameter: ${match[1]}`
      };
    }
    
    return params;
  };

  // Extract template variables from templates
  const extractTemplateVars = (...templates) => {
    const vars = {};
    const regex = /\{\{\s*(\w+)\s*\}\}/g;
    
    templates.forEach(template => {
      if (!template) return;
      
      let match;
      while ((match = regex.exec(template)) !== null) {
        vars[match[1]] = {
          type: 'string',
          description: `Template variable: ${match[1]}`
        };
      }
    });
    
    return vars;
  };

  // Handle parameter changes
  const handleParameterChange = (paramPath, value) => {
    console.log('handleParameterChange - Called with:', { paramPath, value });
    
    const newParams = { ...parameters };
    
    // Handle nested paths (e.g., "body.user.name")
    const pathParts = paramPath.split('.');
    let current = newParams;
    
    for (let i = 0; i < pathParts.length - 1; i++) {
      if (!current[pathParts[i]]) {
        current[pathParts[i]] = {};
      }
      current = current[pathParts[i]];
    }
    
    current[pathParts[pathParts.length - 1]] = value;
    
    console.log('handleParameterChange - New parameters:', newParams);
    
    setParameters(newParams);
    onParametersChange(newParams);
  };

  const targetSchema = getServiceParameterStructure();
  
  console.log('ServiceParameterMapper - Final targetSchema:', targetSchema);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">
          Parameter Mapping
        </h3>
        <span className="text-xs text-gray-500">
          {service?.display_name || service?.service_name}
        </span>
      </div>

      {/* Service type specific UI hints */}
      {service?.service_type === 'api_call' && service?.service_config?.endpoint_template && (
        <div className="bg-blue-50 p-3 rounded-md text-xs">
          <p className="font-medium text-blue-900">Endpoint Template:</p>
          <code className="text-blue-700">{service.service_config.endpoint_template}</code>
        </div>
      )}

      {service?.service_type === 'email_send' && (
        <div className="bg-green-50 p-3 rounded-md text-xs">
          <p className="font-medium text-green-900">Email Template Variables:</p>
          <div className="mt-1 space-y-1">
            {service?.service_config?.subject_template && (
              <p className="text-green-700">Subject: {service.service_config.subject_template}</p>
            )}
          </div>
        </div>
      )}

      {service?.service_type === 'llm_api_call' && (
        <div className="bg-purple-50 p-3 rounded-md text-xs">
          <p className="font-medium text-purple-900">LLM Configuration:</p>
          <p className="text-purple-700">
            Provider: {service?.service_config?.provider}, Model: {service?.service_config?.model}
          </p>
        </div>
      )}

      {/* Parameter mapping interface */}
      {console.log('ServiceParameterMapper - Rendering ParameterMapper with:', {
        sourceSchema,
        targetSchema,
        mappings: parameters,
        availableVariables
      })}
      <ParameterMapper
        sourceSchema={sourceSchema}
        targetSchema={targetSchema}
        mappings={parameters}
        onMappingChange={handleParameterChange}
        availableVariables={availableVariables}
      />

      {/* Advanced options */}
      <div className="border-t pt-3">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ChevronRightIcon 
            className={`w-4 h-4 mr-1 transition-transform ${showAdvanced ? 'rotate-90' : ''}`} 
          />
          Advanced Options
        </button>
        
        {showAdvanced && (
          <div className="mt-3 p-3 bg-gray-50 rounded-md">
            <p className="text-xs text-gray-600 mb-2">
              Raw parameter JSON (for debugging):
            </p>
            <pre className="text-xs bg-white p-2 rounded border overflow-x-auto">
              {JSON.stringify(parameters, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default ServiceParameterMapper;