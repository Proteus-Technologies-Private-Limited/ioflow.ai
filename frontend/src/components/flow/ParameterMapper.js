import React, { useState, useEffect } from 'react';
import {
  ArrowRightIcon,
  LinkIcon,
  XMarkIcon,
  PlusIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import ParameterInput from './ParameterInput';

const ParameterMapper = ({
  sourceSchema,
  targetSchema,
  parameterMethod = 'json_payload',
  initialMapping = {},
  availableVariables = {},
  onMappingChange,
  mode = 'edit', // 'edit' or 'view'
  isCompact = false, // Force compact/stacked layout
  subscriptionId = null, // For parameter lookup
}) => {
  const [mapping, setMapping] = useState(initialMapping);
  const [mappingMetadata, setMappingMetadata] = useState({});
  
  // Update mapping when initialMapping changes (e.g., when service is selected)
  useEffect(() => {
    // Process initialMapping to handle nested structure from imports
    const processedMapping = {};
    const metadata = {};
    
    if (initialMapping) {
      Object.entries(initialMapping).forEach(([key, value]) => {
        // Check if value is an object with source and value properties (import format)
        if (value && typeof value === 'object' && 'source' in value && 'value' in value) {
          // Store the source type in metadata
          metadata[key] = { source: value.source };
          // Extract the actual value from the nested structure
          processedMapping[key] = value.value;
        } else if (value && typeof value === 'object' && 'value' in value && !('source' in value)) {
          // Handle case where there's only 'value' property without 'source'
          // Assume it's a static value
          metadata[key] = { source: 'static' };
          processedMapping[key] = value.value;
        } else {
          // Use the value as-is for normal mappings
          // Detect if it's a variable reference
          if (typeof value === 'string' && 
              (value.startsWith('input.') || 
               value.startsWith('node_outputs.') || 
               value.startsWith('trigger.') || 
               value.startsWith('loop.') ||
               value.startsWith('variables.') ||
               value.includes('{{')))
          {
            metadata[key] = { source: 'variable' };
          } else {
            metadata[key] = { source: 'static' };
          }
          processedMapping[key] = value;
        }
      });
    }
    
    setMapping(processedMapping);
    setMappingMetadata(metadata);
  }, [initialMapping]);
  const [errors, setErrors] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [showHelp, setShowHelp] = useState(false);
  const [customParameters, setCustomParameters] = useState([]);
  const [newParamName, setNewParamName] = useState('');
  
  // Get parameter extraction info from unified schema
  const getParameterExtractionInfo = () => {
    if (!sourceSchema) return null;
    return sourceSchema.parameter_extraction || null;
  };

  // Extract parameters from schemas
  const getSourceParameters = () => {
    if (!sourceSchema) return [];
    
    // Support unified output_schema format with parameter_extraction
    if (sourceSchema.properties) {
      return Object.entries(sourceSchema.properties).map(([key, value]) => ({
        name: key,
        type: value.type,
        description: value.description,
        required: sourceSchema.required?.includes(key),
        mapping: value.mapping, // Include mapping info from unified schema
      }));
    } else if (parameterMethod === 'url_pattern' && sourceSchema.parameters) {
      return sourceSchema.parameters;
    }
    
    return [];
  };

  const getTargetParameters = () => {
    if (!targetSchema) return [];
    
    // Prefer properties (new format with parameterLookup) over fields (old format)
    if (targetSchema.properties) {
      return Object.entries(targetSchema.properties).map(([key, value]) => ({
        name: key,
        type: value.type,
        description: value.description,
        required: targetSchema.required?.includes(key),
        parameterLookup: value.parameterLookup,
        default: value.default, // Include default values
      }));
    } else if (targetSchema.fields) {
      return targetSchema.fields.map(field => ({
        name: field.param_name,
        displayName: field.friendly_name,
        type: field.data_type,
        description: field.description,
        required: field.required,
        uiControl: field.ui_control,
        default: field.default, // Include default values
      }));
    }
    
    return [];
  };

  const sourceParams = getSourceParameters();
  const targetParams = getTargetParameters();

  // Check if additional properties are allowed
  const allowsAdditionalProperties = targetSchema?.additionalProperties === true;
  
  // Initialize custom parameters from existing mappings
  useEffect(() => {
    if (allowsAdditionalProperties && initialMapping) {
      // Find parameters in mapping that aren't in the schema
      const schemaParamNames = targetParams.map(p => p.name);
      const customParamNames = Object.keys(initialMapping).filter(
        key => !schemaParamNames.includes(key)
      );
      
      setCustomParameters(customParamNames.map(name => ({
        name,
        type: 'string',
        displayName: name,
        required: false,
        isCustom: true
      })));
    }
  }, []);
  
  // Add custom parameter
  const addCustomParameter = () => {
    if (newParamName && !targetParams.some(p => p.name === newParamName) && 
        !customParameters.some(p => p.name === newParamName)) {
      const newParam = {
        name: newParamName,
        type: 'string',
        displayName: newParamName,
        required: false,
        isCustom: true
      };
      setCustomParameters([...customParameters, newParam]);
      setNewParamName('');
    }
  };
  
  // Remove custom parameter
  const removeCustomParameter = (paramName) => {
    setCustomParameters(customParameters.filter(p => p.name !== paramName));
    const newMapping = { ...mapping };
    const newMetadata = { ...mappingMetadata };
    delete newMapping[paramName];
    delete newMetadata[paramName];
    setMapping(newMapping);
    setMappingMetadata(newMetadata);
    
    // Always use nested structure for consistency
    const finalMapping = {};
    Object.entries(newMapping).forEach(([key, value]) => {
      const metadata = newMetadata[key] || {};
      finalMapping[key] = {
        source: metadata.source || 'static',
        value: value
      };
    });
    
    onMappingChange(finalMapping);
  };

  // Update mapping with source type tracking
  const updateMapping = (targetParam, sourceValue, sourceType = null) => {
    const newMapping = { ...mapping };
    const newMetadata = { ...mappingMetadata };
    
    if (sourceValue !== null && sourceValue !== undefined && sourceValue !== '') {
      newMapping[targetParam] = sourceValue;
      
      // Use explicitly passed sourceType if available
      if (sourceType) {
        newMetadata[targetParam] = { source: sourceType };
      } else {
        // Auto-detect if the new value is a variable reference
        if (typeof sourceValue === 'string' && 
            (sourceValue.startsWith('input.') || 
             sourceValue.startsWith('node_outputs.') || 
             sourceValue.startsWith('trigger.') || 
             sourceValue.startsWith('loop.') ||
             sourceValue.startsWith('variables.') ||
             sourceValue.includes('{{')))
        {
          newMetadata[targetParam] = { source: 'variable' };
        } else {
          newMetadata[targetParam] = { source: 'static' };
        }
      }
    } else {
      delete newMapping[targetParam];
      delete newMetadata[targetParam];
    }
    
    setMapping(newMapping);
    setMappingMetadata(newMetadata);
    
    // Always use nested structure for consistency
    const finalMapping = {};
    Object.entries(newMapping).forEach(([key, value]) => {
      const metadata = newMetadata[key] || {};
      finalMapping[key] = {
        source: metadata.source || 'static',
        value: value
      };
    });
    
    onMappingChange(finalMapping);
  };

  // Use default value for parameter
  const useDefaultValue = (targetParam, defaultValue) => {
    const newMapping = { ...mapping };
    const newMetadata = { ...mappingMetadata };
    newMapping[targetParam] = defaultValue;
    // Default values are usually static
    newMetadata[targetParam] = { source: 'static' };
    setMapping(newMapping);
    setMappingMetadata(newMetadata);
    
    // Always use nested structure for consistency
    const finalMapping = {};
    Object.entries(newMapping).forEach(([key, value]) => {
      const metadata = newMetadata[key] || {};
      finalMapping[key] = {
        source: metadata.source || 'static',
        value: value
      };
    });
    
    onMappingChange(finalMapping);
  };

  // Clear parameter (remove from mapping)
  const clearParameter = (targetParam) => {
    const newMapping = { ...mapping };
    const newMetadata = { ...mappingMetadata };
    delete newMapping[targetParam];
    delete newMetadata[targetParam];
    setMapping(newMapping);
    setMappingMetadata(newMetadata);
    
    // Always use nested structure for consistency
    const finalMapping = {};
    Object.entries(newMapping).forEach(([key, value]) => {
      const metadata = newMetadata[key] || {};
      finalMapping[key] = {
        source: metadata.source || 'static',
        value: value
      };
    });
    
    onMappingChange(finalMapping);
  };

  // Validate mapping
  useEffect(() => {
    const newErrors = [];
    const newWarnings = [];
    
    // Check required fields (only for non-custom parameters)
    targetParams.forEach(param => {
      if (param.required && !mapping[param.name]) {
        newErrors.push(`Required field "${param.displayName || param.name}" is not mapped`);
      }
    });
    
    // Check type compatibility
    Object.entries(mapping).forEach(([target, source]) => {
      const targetParam = [...targetParams, ...customParameters].find(p => p.name === target);
      const sourceParam = sourceParams.find(p => p.name === source);
      
      if (targetParam && sourceParam && targetParam.type !== sourceParam.type) {
        if (canConvert(sourceParam.type, targetParam.type)) {
          newWarnings.push(`Type conversion: ${source} (${sourceParam.type}) → ${target} (${targetParam.type})`);
        } else {
          newErrors.push(`Incompatible types: ${source} (${sourceParam.type}) → ${target} (${targetParam.type})`);
        }
      }
    });
    
    setErrors(newErrors);
    setWarnings(newWarnings);
  }, [mapping, sourceParams, targetParams]);

  const canConvert = (sourceType, targetType) => {
    const conversions = {
      string: ['number', 'integer', 'boolean'],
      number: ['string', 'integer'],
      integer: ['string', 'number'],
      boolean: ['string'],
    };
    
    return conversions[sourceType]?.includes(targetType);
  };

  // Get available source options for a target parameter
  const getSourceOptions = (targetParam) => {
    const options = [];
    
    // Add source parameters
    sourceParams.forEach(param => {
      options.push({
        value: param.name,
        label: param.name,
        type: 'source',
        dataType: param.type,
      });
    });
    
    // Add available variables
    if (availableVariables.input) {
      Object.keys(availableVariables.input).forEach(key => {
        options.push({
          value: `{{input.${key}}}`,
          label: `input.${key}`,
          type: 'variable',
          dataType: 'any',
        });
      });
    }
    
    // Add custom expression option
    options.push({
      value: 'custom',
      label: 'Custom Expression',
      type: 'custom',
    });
    
    return options;
  };

  // State to track input mode for each parameter
  const [paramInputModes, setParamInputModes] = useState({});

  // Get input mode for a parameter
  const getInputMode = (paramName) => {
    if (paramInputModes[paramName]) {
      return paramInputModes[paramName];
    }
    // Default based on metadata
    const metadata = mappingMetadata[paramName];
    return metadata?.source === 'variable' ? 'variable' : 'constant';
  };

  // Set input mode for a parameter
  const setInputMode = (paramName, mode) => {
    setParamInputModes(prev => ({
      ...prev,
      [paramName]: mode
    }));
  };

  // Render mapping row
  const renderMappingRow = (param) => {
    // Extract actual value from nested structure if present
    let currentMapping = mapping[param.name];
    if (currentMapping && typeof currentMapping === 'object' && 'source' in currentMapping && 'value' in currentMapping) {
      // For nested structure from imports, extract the actual value
      currentMapping = currentMapping.value;
    } else if (currentMapping && typeof currentMapping === 'object' && 'value' in currentMapping && !('source' in currentMapping)) {
      // Handle case where there's only 'value' property without 'source'
      // Assume it's a direct value
      currentMapping = currentMapping.value;
    }
    const sourceOptions = getSourceOptions(param);

    const currentInputMode = getInputMode(param.name);

    return (
      <div key={param.name} className="p-2 md:p-3 border rounded-lg hover:bg-gray-50 relative">
        {/* Delete button for custom parameters */}
        {param.isCustom && mode === 'edit' && (
          <button
            onClick={() => removeCustomParameter(param.name)}
            className="absolute top-2 right-2 p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded"
            title="Remove parameter"
          >
            <XMarkIcon className="w-4 h-4" />
          </button>
        )}
        
        {/* Single unified layout - always full width, input below header */}
        <div className="space-y-1">
          {/* Row 1: Parameter name + toggle + action buttons */}
          <div className="flex items-center justify-between gap-2">
            {/* Left: Parameter name */}
            <span className="font-medium text-sm">
              {param.displayName || param.name}
              {param.required && <span className="text-red-500 ml-1">*</span>}
            </span>

            {/* Right: Toggle + Action buttons */}
            <div className="flex items-center gap-2">
              {/* Static/Variable Toggle */}
              <div className="inline-flex rounded-md shadow-sm" role="group">
                <button
                  type="button"
                  onClick={() => setInputMode(param.name, 'constant')}
                  className={`px-2 py-1 text-xs font-medium rounded-l-md border transition-colors ${
                    currentInputMode === 'constant'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Static
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode(param.name, 'variable')}
                  className={`px-2 py-1 text-xs font-medium rounded-r-md border-t border-r border-b transition-colors ${
                    currentInputMode === 'variable'
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  Variable
                </button>
              </div>
              {/* Default value button */}
              {param.default !== null && param.default !== undefined && (
                <button
                  type="button"
                  onClick={() => useDefaultValue(param.name, param.default)}
                  className="text-xs text-blue-600 hover:text-blue-800 border border-blue-300 hover:border-blue-500 px-2 py-0.5 rounded transition-colors whitespace-nowrap"
                  title={`Use default: ${typeof param.default === 'object' ? JSON.stringify(param.default) : String(param.default)}`}
                >
                  Default
                </button>
              )}

              {/* Clear button */}
              {currentMapping && (
                <button
                  type="button"
                  onClick={() => clearParameter(param.name)}
                  className="text-xs text-red-600 hover:text-red-800 border border-red-300 hover:border-red-500 px-2 py-0.5 rounded transition-colors whitespace-nowrap"
                  title="Clear parameter"
                >
                  Clear
                </button>
              )}

              {/* Info icon */}
              {param.description && (
                <div className="group relative flex-shrink-0">
                  <InformationCircleIcon className="w-4 h-4 text-gray-400 cursor-help" />
                  <div className="absolute right-0 top-full mt-2 hidden group-hover:block w-64 p-2 bg-gray-800 text-white text-xs rounded shadow-lg z-10">
                    {param.description}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Row 2: Description and type */}
          {param.description && (
            <div className="text-xs text-gray-600">
              {param.description} ({param.type})
            </div>
          )}
          {!param.description && (
            <div className="text-xs text-gray-500">
              ({param.type})
            </div>
          )}

          {/* Row 3: Parameter Input - full width */}
          <div className="pt-1">
            <ParameterInput
              name={param.name}
              value={currentMapping || ''}
              onChange={(value, sourceType) => {
                console.log('[ParameterMapper] onChange received:', {
                  paramName: param.name,
                  value,
                  sourceType
                });
                updateMapping(param.name, value, sourceType);
                // Update input mode based on the actual change
                if (sourceType) {
                  const newMode = sourceType === 'variable' ? 'variable' : 'constant';
                  console.log('[ParameterMapper] Setting input mode to:', newMode);
                  setInputMode(param.name, newMode);
                }
              }}
              type={param.type || 'string'}
              placeholder={currentInputMode === 'variable' ? "Select variable or enter expression" : "Enter static value"}
              required={param.required}
              description=""
              availableVariables={availableVariables}
              mode={mode}
              parameterLookup={param.parameterLookup}
              subscriptionId={subscriptionId}
              defaultValue={null}
              onClear={() => clearParameter(param.name)}
              initialSourceType={currentInputMode}
              forceInputMode={currentInputMode}
              hideModeToggle={true}
            />
          </div>
        </div>
        
        {/* Custom Expression */}
        {currentMapping === 'custom' && mode === 'edit' && (
          <input
            type="text"
            placeholder="Enter expression..."
            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            onChange={(e) => updateMapping(param.name, e.target.value)}
          />
        )}
      </div>
    );
  };

  // Render URL pattern mapping
  const renderUrlPatternMapping = () => {
    if (!targetSchema.pattern) return null;

    // For url_pattern, we should render ALL parameters from targetParams, not just URL params
    // This includes query params and other parameters defined in parameter_schema
    return (
      <div className="mb-4">
        <div className="flex items-center mb-2">
          <LinkIcon className="w-5 h-5 text-gray-400 mr-2" />
          <span className="font-medium text-sm">Service Parameters</span>
        </div>
        <div className="bg-gray-50 p-3 rounded-md font-mono text-sm mb-3">
          <div className="text-xs text-gray-500 mb-1">Endpoint:</div>
          {targetSchema.pattern}
        </div>
        <div className="space-y-1 md:space-y-2">
          {targetParams.map(param => renderMappingRow(param))}
          {customParameters.map(param => renderMappingRow(param))}
        </div>
      </div>
    );
  };

  // Old implementation that only extracted URL params - no longer needed
  const renderUrlPatternMappingOld = () => {
    if (!targetSchema.pattern) return null;

    const urlParams = targetSchema.pattern.match(/\{(\w+)\}/g)?.map(p => p.slice(1, -1)) || [];

    return (
      <div className="mb-4">
        <div className="flex items-center mb-2">
          <LinkIcon className="w-5 h-5 text-gray-400 mr-2" />
          <span className="font-medium text-sm">URL Pattern</span>
        </div>
        <div className="bg-gray-50 p-3 rounded-md font-mono text-sm">
          {targetSchema.pattern}
        </div>
        <div className="mt-3 space-y-2">
          {urlParams.map(param => (
            isCompact ? (
              <div key={param} className="space-y-1">
                <span className="text-sm font-medium">{param}:</span>
                <div>
                  <ParameterInput
                    name=""
                    value={mapping[param] || ''}
                    onChange={(value, sourceType) => updateMapping(param, value, sourceType)}
                    type="string"
                    placeholder={`Enter ${param}...`}
                    required={false}
                    description=""
                    availableVariables={availableVariables}
                    mode={mode}
                    subscriptionId={subscriptionId}
                    initialSourceType={mappingMetadata[param]?.source || 'static'}
                  />
                </div>
              </div>
            ) : (
              <div key={param} className="grid grid-cols-1 sm:grid-cols-12 gap-2 sm:gap-3 items-center">
                <span className="text-sm font-medium sm:col-span-3">{param}:</span>
                <div className="sm:col-span-9">
                  <ParameterInput
                    name=""
                    value={mapping[param] || ''}
                    onChange={(value, sourceType) => updateMapping(param, value, sourceType)}
                    type="string"
                    placeholder={`Enter ${param}...`}
                    required={false}
                    description=""
                    availableVariables={availableVariables}
                    mode={mode}
                    subscriptionId={subscriptionId}
                    initialSourceType={mappingMetadata[param]?.source || 'static'}
                  />
                </div>
              </div>
            )
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-2 md:space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-base font-medium text-gray-900">Parameter Mapping</h3>
        <button
          onClick={() => setShowHelp(!showHelp)}
          className="text-sm text-blue-600 hover:text-blue-800"
        >
          {showHelp ? 'Hide' : 'Show'} Help
        </button>
      </div>
      
      {/* Help Section */}
      {showHelp && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 md:p-3 text-sm">
          <p className="font-medium text-blue-900 mb-2">How to map parameters:</p>
          <ul className="space-y-1 text-blue-800">
            <li>• Select a source field from the dropdown to map it directly</li>
            <li>• Use variables like <code className="bg-blue-100 px-1 rounded">{'{{input.fieldName}}'}</code></li>
            <li>• Choose "Custom Expression" for complex transformations</li>
            <li>• Required fields are marked with a red asterisk (*)</li>
          </ul>
        </div>
      )}
      
      {/* Validation Messages */}
      {errors.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-2 md:p-3">
          <div className="flex items-center text-red-800 mb-1">
            <ExclamationTriangleIcon className="w-5 h-5 mr-2" />
            <span className="font-medium">Mapping Errors</span>
          </div>
          <ul className="list-disc list-inside text-sm text-red-700 space-y-0.5">
            {errors.map((error, i) => (
              <li key={i}>{error}</li>
            ))}
          </ul>
        </div>
      )}
      
      {warnings.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-2 md:p-3">
          <div className="flex items-center text-yellow-800 mb-1">
            <ExclamationTriangleIcon className="w-5 h-5 mr-2" />
            <span className="font-medium">Warnings</span>
          </div>
          <ul className="list-disc list-inside text-sm text-yellow-700 space-y-0.5">
            {warnings.map((warning, i) => (
              <li key={i}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      
      {/* URL Pattern Mapping */}
      {parameterMethod === 'url_pattern' && renderUrlPatternMapping()}
      
      {/* Field Mappings */}
      {parameterMethod !== 'url_pattern' && (
        <div className="space-y-1 md:space-y-2">
          <div className="text-sm text-gray-600">
            Map Target Parameters to Source Values
          </div>
          {targetParams.map(param => renderMappingRow(param))}
          {customParameters.map(param => renderMappingRow(param))}
          
          {/* Add custom parameter UI */}
          {allowsAdditionalProperties && mode === 'edit' && (
            <div className="mt-2 md:mt-3 p-2 md:p-3 border border-dashed border-gray-300 rounded-lg bg-gray-50">
              <div className="text-sm text-gray-600 mb-2">
                Add additional parameters (e.g., SQL bind variables)
              </div>
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={newParamName}
                  onChange={(e) => setNewParamName(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && addCustomParameter()}
                  placeholder="Parameter name (e.g., status, user_id)"
                  className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <button
                  onClick={addCustomParameter}
                  disabled={!newParamName}
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  <PlusIcon className="w-4 h-4 mr-1" />
                  Add
                </button>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Auto-map Button */}
      {mode === 'edit' && (
        <div className="flex justify-end">
          <button
            onClick={() => {
              // Auto-map fields with matching names
              const autoMapping = {};
              const autoMetadata = {};
              targetParams.forEach(target => {
                const matchingSource = sourceParams.find(
                  source => source.name.toLowerCase() === target.name.toLowerCase()
                );
                if (matchingSource) {
                  autoMapping[target.name] = matchingSource.name;
                  // Auto-mapped fields are typically variables
                  autoMetadata[target.name] = { source: 'variable' };
                }
              });
              setMapping(autoMapping);
              setMappingMetadata(autoMetadata);
              
              // Always use nested structure for consistency
              const finalMapping = {};
              Object.entries(autoMapping).forEach(([key, value]) => {
                const metadata = autoMetadata[key] || {};
                finalMapping[key] = {
                  source: metadata.source || 'variable',
                  value: value
                };
              });
              
              onMappingChange(finalMapping);
            }}
            className="px-4 py-2 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Auto-map Matching Fields
          </button>
        </div>
      )}
    </div>
  );
};

export default ParameterMapper;