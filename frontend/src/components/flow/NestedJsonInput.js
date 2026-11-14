import React, { useState, useCallback, useEffect } from 'react';
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline';
import Matrix2DArrayInput from './Matrix2DArrayInput';
import ArrayOfObjectsInput from './ArrayOfObjectsInput';
import TabularArrayInput from './TabularArrayInput';

const NestedJsonInput = ({ variable, value = {}, onChange }) => {
  const [localValue, setLocalValue] = useState(value || {});
  const [expandedFields, setExpandedFields] = useState({});

  // Update local value when prop changes
  useEffect(() => {
    setLocalValue(value || {});
  }, [value]);

  // Handle field value changes
  const handleFieldChange = useCallback((fieldPath, fieldValue) => {
    const pathParts = fieldPath.split('.');
    const newValue = { ...localValue };

    let current = newValue;
    for (let i = 0; i < pathParts.length - 1; i++) {
      if (!current[pathParts[i]]) {
        current[pathParts[i]] = {};
      }
      current = current[pathParts[i]];
    }
    current[pathParts[pathParts.length - 1]] = fieldValue;

    setLocalValue(newValue);
    onChange(variable.name, newValue);
  }, [localValue, onChange, variable.name]);

  // Toggle field expansion
  const toggleExpanded = useCallback((fieldId) => {
    setExpandedFields(prev => ({
      ...prev,
      [fieldId]: !prev[fieldId]
    }));
  }, []);

  // Get value at a specific path
  const getValueAtPath = (obj, path) => {
    if (!path) return obj;
    const parts = path.split('.');
    let current = obj;
    for (const part of parts) {
      if (current == null || typeof current !== 'object') return undefined;
      current = current[part];
    }
    return current;
  };

  // Render a single field based on its type
  const renderField = (field, parentPath = '', depth = 0) => {
    const fieldPath = parentPath ? `${parentPath}.${field.name}` : field.name;
    const fieldValue = getValueAtPath(localValue, fieldPath) ?? field.defaultValue;
    const fieldId = fieldPath;
    const isExpanded = expandedFields[fieldId];
    const hasNestedProperties = field.properties && field.properties.length > 0;
    const isArrayType = field.dataType === 'array' || field.dataType === 'ARRAY';
    const isObjectType = field.dataType === 'json' || field.dataType === 'object' || field.dataType === 'JSON' || field.dataType === 'OBJECT';

    return (
      <div key={fieldId} className={`${depth > 0 ? 'ml-6' : ''} mb-3`}>
        <div className="flex items-start">
          {hasNestedProperties && (
            <button
              type="button"
              onClick={() => toggleExpanded(fieldId)}
              className="mr-2 mt-1 text-gray-400 hover:text-gray-600"
            >
              {isExpanded ?
                <ChevronDownIcon className="w-4 h-4" /> :
                <ChevronRightIcon className="w-4 h-4" />
              }
            </button>
          )}

          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {field.displayName || field.name}
              {field.required && <span className="text-red-500 ml-1">*</span>}
              {field.description && (
                <span className="text-xs text-gray-500 ml-2">({field.description})</span>
              )}
            </label>

            {/* Render input based on field type */}
            {isArrayType && (field.itemType === 'object' || field.itemType === 'OBJECT') &&
             field.properties && field.properties.length > 0 ? (
              // Array of objects with defined schema - check if tabular UI control is set
              <div className="border border-gray-200 rounded p-2">
                {field.uiControl === 'tabular' ? (
                  // Use TabularArrayInput for tabular view
                  <TabularArrayInput
                    value={fieldValue || []}
                    onChange={(val) => handleFieldChange(fieldPath, val)}
                    properties={field.properties}
                    minItems={field.validation?.minItems}
                    maxItems={field.validation?.maxItems}
                  />
                ) : (
                  // Use ArrayOfObjectsInput for regular view
                  <ArrayOfObjectsInput
                    value={fieldValue || []}
                    onChange={(val) => handleFieldChange(fieldPath, val)}
                    properties={field.properties}
                    itemType={field.itemType}
                  />
                )}
              </div>
            ) : isArrayType ? (
              // Simple array without defined schema
              <div className="border border-gray-200 rounded p-2">
                <Matrix2DArrayInput
                  value={fieldValue || []}
                  onChange={(val) => handleFieldChange(fieldPath, val)}
                  itemType={field.itemType || 'string'}
                  minItems={field.validation?.minItems}
                  maxItems={field.validation?.maxItems}
                />
              </div>
            ) : isObjectType && hasNestedProperties ? (
              // For objects with defined properties, show nested fields
              isExpanded && (
                <div className="mt-2 border-l-2 border-blue-200 pl-4 bg-blue-50 rounded-lg p-3">
                  <div className={`grid grid-cols-1 ${depth === 0 ? 'md:grid-cols-2 lg:grid-cols-3' : ''} gap-3`}>
                    {field.properties.map(nestedField => {
                      const nestedHasProps = nestedField.properties && nestedField.properties.length > 0;
                      const nestedIsArray = nestedField.dataType === 'array' &&
                                           (nestedField.itemType === 'object' || nestedField.itemType === 'OBJECT') &&
                                           nestedHasProps;
                      const nestedIsComplex = nestedHasProps ||
                                             nestedIsArray ||
                                             nestedField.uiControl === 'textarea' ||
                                             nestedField.uiControl === 'code' ||
                                             nestedField.dataType === 'json' ||
                                             nestedField.dataType === 'object';

                      return (
                        <div
                          key={nestedField.id || nestedField.name}
                          className={nestedIsComplex && depth === 0 ? 'md:col-span-2 lg:col-span-3' : ''}
                        >
                          {renderField(nestedField, fieldPath, depth + 1)}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )
            ) : isObjectType ? (
              // For objects without defined properties, show a JSON input
              <textarea
                value={typeof fieldValue === 'object' ? JSON.stringify(fieldValue, null, 2) : fieldValue || '{}'}
                onChange={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value);
                    handleFieldChange(fieldPath, parsed);
                  } catch {
                    // Keep the text value if it's not valid JSON yet
                    handleFieldChange(fieldPath, e.target.value);
                  }
                }}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder='{"key": "value"}'
              />
            ) : field.dataType === 'boolean' || field.dataType === 'BOOLEAN' ? (
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={fieldValue === true}
                  onChange={(e) => handleFieldChange(fieldPath, e.target.checked)}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">{fieldValue ? 'Yes' : 'No'}</span>
              </div>
            ) : field.dataType === 'number' || field.dataType === 'NUMBER' || field.dataType === 'integer' || field.dataType === 'INTEGER' ? (
              <input
                type="number"
                value={fieldValue || ''}
                onChange={(e) => {
                  const val = e.target.value === '' ? null : parseFloat(e.target.value);
                  handleFieldChange(fieldPath, val);
                }}
                className="w-full px-3 py-2 text-right border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Enter number"
              />
            ) : field.dataType === 'date' || field.dataType === 'DATE' ? (
              <input
                type="date"
                value={fieldValue || ''}
                onChange={(e) => handleFieldChange(fieldPath, e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            ) : field.dataType === 'datetime' || field.dataType === 'DATETIME' ? (
              <input
                type="datetime-local"
                value={fieldValue || ''}
                onChange={(e) => handleFieldChange(fieldPath, e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            ) : field.dataType === 'select' && field.options ? (
              <select
                value={fieldValue || ''}
                onChange={(e) => handleFieldChange(fieldPath, e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="">Select...</option>
                {field.options.map(option => (
                  <option key={option.value || option} value={option.value || option}>
                    {option.label || option}
                  </option>
                ))}
              </select>
            ) : (
              // Default text input
              field.uiControl === 'textarea' ? (
                <textarea
                  value={fieldValue || ''}
                  onChange={(e) => handleFieldChange(fieldPath, e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder={`Enter ${field.displayName || field.name}`}
                />
              ) : (
                <input
                  type="text"
                  value={fieldValue || ''}
                  onChange={(e) => handleFieldChange(fieldPath, e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder={`Enter ${field.displayName || field.name}`}
                />
              )
            )}
          </div>
        </div>
      </div>
    );
  };

  // Check if this is a JSON object with defined properties
  if (variable.properties && variable.properties.length > 0) {
    return (
      <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {variable.properties.map(field => {
            // Check if this field should span multiple columns
            const hasNestedProps = field.properties && field.properties.length > 0;
            const isArrayOfObjects = field.dataType === 'array' &&
                                    (field.itemType === 'object' || field.itemType === 'OBJECT') &&
                                    hasNestedProps;
            const isComplexField = hasNestedProps ||
                                  isArrayOfObjects ||
                                  field.uiControl === 'textarea' ||
                                  field.uiControl === 'code' ||
                                  field.dataType === 'json' ||
                                  field.dataType === 'object';

            return (
              <div
                key={field.id || field.name}
                className={isComplexField ? 'md:col-span-2 lg:col-span-3' : ''}
              >
                {renderField(field)}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  // Fallback to simple JSON input
  return (
    <textarea
      value={typeof localValue === 'object' ? JSON.stringify(localValue, null, 2) : localValue || '{}'}
      onChange={(e) => {
        try {
          const parsed = JSON.parse(e.target.value);
          setLocalValue(parsed);
          onChange(variable.name, parsed);
        } catch {
          // Keep the text value if it's not valid JSON yet
        }
      }}
      rows={6}
      className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
      placeholder='{"key": "value"}'
    />
  );
};

export default NestedJsonInput;