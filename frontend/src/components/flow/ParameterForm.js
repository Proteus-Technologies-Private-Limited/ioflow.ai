import React, { useState, useEffect } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  InformationCircleIcon,
  CodeBracketIcon,
} from '@heroicons/react/24/outline';
import ParameterInput from './ParameterInput';

const ParameterForm = ({ 
  serviceId, 
  parameters = {}, 
  onParametersChange, 
  inputSchema,
  availableVariables = {},
  subscriptionId
}) => {
  const [formData, setFormData] = useState({});
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showJsonEditor, setShowJsonEditor] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [expandedSections, setExpandedSections] = useState({});

  // Initialize form data from parameters
  useEffect(() => {
    if (parameters && Object.keys(parameters).length > 0) {
      setFormData(parameters);
      setJsonText(JSON.stringify(parameters, null, 2));
    }
  }, [parameters]);

  // Parse input schema to determine field types
  const parseSchema = (schema) => {
    if (!schema || !schema.properties) return [];
    
    const fields = [];
    const required = schema.required || [];
    
    Object.entries(schema.properties).forEach(([key, value]) => {
      fields.push({
        name: key,
        type: value.type || 'string',
        description: value.description || '',
        required: required.includes(key),
        enum: value.enum || null,
        format: value.format || null,
        properties: value.properties || null,
        items: value.items || null,
        default: value.default || null,
        examples: value.examples || [],
        parameterLookup: value.parameterLookup || null,
      });
    });
    
    return fields;
  };

  const fields = inputSchema ? parseSchema(inputSchema) : [];

  // Handle field value changes
  const handleFieldChange = (fieldName, value) => {
    const newFormData = { ...formData, [fieldName]: value };
    
    // Filter out null, undefined, and empty string values before sending to parent
    const filteredData = Object.entries(newFormData).reduce((acc, [key, val]) => {
      if (val !== null && val !== undefined && val !== '') {
        acc[key] = val;
      }
      return acc;
    }, {});
    
    setFormData(newFormData);
    setJsonText(JSON.stringify(filteredData, null, 2));
    onParametersChange(filteredData);
  };

  // Handle array field operations
  const addArrayItem = (fieldName) => {
    const currentArray = formData[fieldName] || [];
    const newArray = [...currentArray, ''];
    handleFieldChange(fieldName, newArray);
  };

  const removeArrayItem = (fieldName, index) => {
    const currentArray = formData[fieldName] || [];
    const newArray = currentArray.filter((_, i) => i !== index);
    handleFieldChange(fieldName, newArray);
  };

  const updateArrayItem = (fieldName, index, value) => {
    const currentArray = formData[fieldName] || [];
    const newArray = [...currentArray];
    newArray[index] = value;
    handleFieldChange(fieldName, newArray);
  };

  // Handle object field operations
  const updateObjectField = (fieldName, subFieldName, value) => {
    const currentObject = formData[fieldName] || {};
    const newObject = { ...currentObject, [subFieldName]: value };
    handleFieldChange(fieldName, newObject);
  };

  // Toggle section expansion
  const toggleSection = (sectionName) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionName]: !prev[sectionName]
    }));
  };


  // Render field based on type
  const renderField = (field, value, onChange, path = '') => {
    const fieldPath = path ? `${path}.${field.name}` : field.name;

    switch (field.type) {
      case 'string':
        if (field.enum) {
          // Dropdown for enum values
          return (
            <select
              value={value || ''}
              onChange={(e) => onChange(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select {field.name}...</option>
              {field.enum.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          );
        } else if (field.format === 'email') {
          // Email input
          return (
            <input
              type="email"
              value={value || ''}
              onChange={(e) => onChange(e.target.value)}
              placeholder={field.examples[0] || 'user@example.com'}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          );
        } else {
          // Text input with variable button
          return (
            <div className="relative">
              <input
                type="text"
                value={value || ''}
                onChange={(e) => onChange(e.target.value)}
                placeholder={field.description || `Enter ${field.name}`}
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
              <button
                type="button"
                onClick={() => {
                  setActiveField(field.name);
                  setShowVariablePicker(true);
                }}
                className="absolute right-2 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                title="Insert variable"
              >
                <CodeBracketIcon className="w-5 h-5" />
              </button>
            </div>
          );
        }

      case 'number':
        return (
          <input
            type="number"
            value={value || ''}
            onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
            placeholder={field.description || `Enter ${field.name}`}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
          />
        );

      case 'boolean':
        return (
          <div className="flex items-center">
            <input
              type="checkbox"
              id={fieldPath}
              checked={value || false}
              onChange={(e) => onChange(e.target.checked)}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor={fieldPath} className="ml-2 text-sm text-gray-700">
              {field.description || 'Enable'}
            </label>
          </div>
        );

      case 'array':
        const arrayValue = value || [];
        return (
          <div className="space-y-2">
            {arrayValue.map((item, index) => (
              <div key={index} className="flex items-center space-x-2">
                <input
                  type="text"
                  value={item}
                  onChange={(e) => updateArrayItem(field.name, index, e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                  placeholder={`Item ${index + 1}`}
                />
                <button
                  type="button"
                  onClick={() => removeArrayItem(field.name, index)}
                  className="p-2 text-red-600 hover:text-red-800"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => addArrayItem(field.name)}
              className="flex items-center text-sm text-blue-600 hover:text-blue-800"
            >
              <PlusIcon className="w-4 h-4 mr-1" />
              Add item
            </button>
          </div>
        );

      case 'object':
        if (!field.properties) {
          // Simple key-value editor
          return (
            <div className="text-sm text-gray-500">
              Use JSON editor for complex objects
            </div>
          );
        }
        
        // Nested object fields
        const objectValue = value || {};
        const isExpanded = expandedSections[field.name];
        
        return (
          <div className="border border-gray-200 rounded-md">
            <button
              type="button"
              onClick={() => toggleSection(field.name)}
              className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-gray-50"
            >
              <span className="font-medium text-sm">{field.name}</span>
              {isExpanded ? (
                <ChevronDownIcon className="w-4 h-4" />
              ) : (
                <ChevronRightIcon className="w-4 h-4" />
              )}
            </button>
            {isExpanded && (
              <div className="p-3 space-y-3 bg-gray-50">
                {Object.entries(field.properties).map(([subKey, subField]) => (
                  <div key={subKey}>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      {subKey}
                      {subField.required && <span className="text-red-500 ml-1">*</span>}
                    </label>
                    {renderField(
                      { ...subField, name: subKey },
                      objectValue[subKey],
                      (val) => updateObjectField(field.name, subKey, val),
                      field.name
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      default:
        return (
          <div className="text-sm text-gray-500">
            Unsupported field type: {field.type}
          </div>
        );
    }
  };

  // Handle JSON editor changes
  const handleJsonChange = (text) => {
    setJsonText(text);
    try {
      const parsed = JSON.parse(text);
      
      // Apply the same filtering logic to JSON editor changes
      const filteredData = Object.entries(parsed).reduce((acc, [key, val]) => {
        if (val !== null && val !== undefined && val !== '') {
          acc[key] = val;
        }
        return acc;
      }, {});
      
      setFormData(parsed);
      onParametersChange(filteredData);
    } catch (err) {
      // Invalid JSON, just keep the text
    }
  };

  if (!serviceId) {
    return (
      <div className="text-sm text-gray-500 italic">
        Select a service to configure parameters
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toggle between form and JSON editor */}
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-700">Parameters</h4>
        <button
          type="button"
          onClick={() => setShowJsonEditor(!showJsonEditor)}
          className="text-xs text-blue-600 hover:text-blue-800 flex items-center"
        >
          <CodeBracketIcon className="w-4 h-4 mr-1" />
          {showJsonEditor ? 'Form Editor' : 'JSON Editor'}
        </button>
      </div>

      {showJsonEditor ? (
        // JSON Editor
        <div>
          <textarea
            value={jsonText}
            onChange={(e) => handleJsonChange(e.target.value)}
            rows={10}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 font-mono text-xs"
            placeholder="{}"
          />
          <div className="mt-1 text-xs text-gray-500">
            {(() => {
              try {
                JSON.parse(jsonText);
                return <span className="text-green-600">✓ Valid JSON</span>;
              } catch {
                return <span className="text-red-600">✗ Invalid JSON</span>;
              }
            })()}
          </div>
        </div>
      ) : (
        // Form Editor
        <div className="space-y-4">
          {fields.length > 0 ? (
            <>
              {/* Required fields */}
              {fields.filter(f => f.required).map((field) => (
                <div key={field.name}>
                  <ParameterInput
                    name={field.name}
                    value={formData[field.name]}
                    onChange={(value) => handleFieldChange(field.name, value)}
                    type={field.type}
                    placeholder={field.examples?.[0] || field.description || `Enter ${field.name}`}
                    required={true}
                    description={field.description}
                    availableVariables={availableVariables}
                    parameterLookup={field.parameterLookup}
                    subscriptionId={subscriptionId}
                    defaultValue={field.default}
                    onClear={() => handleFieldChange(field.name, null)}
                    mode="edit"
                  />
                </div>
              ))}

              {/* Optional fields */}
              {fields.filter(f => !f.required).length > 0 && (
                <>
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="text-sm text-gray-600 hover:text-gray-800 flex items-center justify-between w-full"
                  >
                    <div className="flex items-center">
                      {showAdvanced ? (
                        <ChevronDownIcon className="w-4 h-4 mr-1" />
                      ) : (
                        <ChevronRightIcon className="w-4 h-4 mr-1" />
                      )}
                      Optional Fields ({fields.filter(f => !f.required).length})
                    </div>
                    <div className="flex items-center space-x-2 text-xs">
                      <div className="flex items-center space-x-1">
                        <div className="w-2 h-2 bg-blue-100 border border-blue-300 rounded"></div>
                        <span>Default</span>
                      </div>
                      <div className="flex items-center space-x-1">
                        <div className="w-2 h-2 bg-white border border-gray-300 rounded"></div>
                        <span>Custom</span>
                      </div>
                    </div>
                  </button>

                  {showAdvanced && (
                    <div className="space-y-3 pl-5 border-l-2 border-gray-200">
                      {fields.filter(f => !f.required).map((field) => (
                        <div key={field.name}>
                          <ParameterInput
                            name={field.name}
                            value={formData[field.name]}
                            onChange={(value) => handleFieldChange(field.name, value)}
                            type={field.type}
                            placeholder={field.examples?.[0] || field.description || `Enter ${field.name}`}
                            required={false}
                            description={field.description}
                            availableVariables={availableVariables}
                            parameterLookup={field.parameterLookup}
                            subscriptionId={subscriptionId}
                            defaultValue={field.default}
                            onClear={() => handleFieldChange(field.name, null)}
                            mode="edit"
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </>
          ) : (
            // No schema available, show simple key-value editor
            <div className="text-sm text-gray-500">
              <InformationCircleIcon className="w-5 h-5 inline mr-1" />
              No parameter schema available. Use JSON editor for manual configuration.
            </div>
          )}

          {/* Variable reference help */}
          <div className="mt-4 p-3 bg-blue-50 rounded-md">
            <p className="text-xs text-blue-800">
              <strong>Tip:</strong> Use <code className="bg-blue-100 px-1 py-0.5 rounded">{'{{input.variableName}}'}</code> to 
              reference variables from previous steps or trigger data.
            </p>
          </div>
        </div>
      )}

    </div>
  );
};

export default ParameterForm;