import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CodeBracketIcon,
  DocumentTextIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { validateValue, getDefaultValue, detectValueType, DataTypes } from '../../utils/dataTypeUtils';
import Matrix2DArrayInput from './Matrix2DArrayInput';

const EnhancedParameterInput = React.memo(({ 
  variable, 
  value, 
  onChange,
  className = '',
  showModeToggle = true // Allow hiding mode toggle when used inside TypeSpecificParameterInput
}) => {
  const [inputMode, setInputMode] = useState('visual'); // 'visual' or 'json'
  const [localValue, setLocalValue] = useState(value || getDefaultValue(variable.dataType));
  const [jsonError, setJsonError] = useState('');
  const [expandedKeys, setExpandedKeys] = useState(new Set());
  const [validationError, setValidationError] = useState('');
  const debounceRef = useRef(null);

  useEffect(() => {
    setLocalValue(value || getDefaultValue(variable.dataType));
  }, [value, variable.dataType]);

  const handleChange = (newValue) => {
    setLocalValue(newValue);
    
    // Validate the value
    const validation = validateValue(newValue, variable.dataType, variable.validation);
    if (!validation.isValid) {
      setValidationError(validation.error);
    } else {
      setValidationError('');
    }
    
    onChange(variable.name, newValue);
  };

  const handleJsonChange = (jsonString) => {
    try {
      const parsed = JSON.parse(jsonString);
      setJsonError('');
      handleChange(parsed);
    } catch (e) {
      setJsonError('Invalid JSON format');
      setLocalValue(jsonString);
    }
  };

  const toggleExpanded = (key) => {
    const newExpanded = new Set(expandedKeys);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedKeys(newExpanded);
  };

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);


  // JSON Object Input Component
  const JsonObjectInput = ({ obj = {}, path = [], onChange: onObjChange }) => {
    // Ensure obj is always an object
    const safeObj = (obj && typeof obj === 'object' && !Array.isArray(obj)) ? obj : {};
    const pathKey = path.join('.');
    const isExpanded = expandedKeys.has(pathKey);

    const handleAddProperty = () => {
      const newKey = `property${Object.keys(safeObj).length + 1}`;
      const newObj = { ...safeObj, [newKey]: '' };
      onObjChange(newObj);
    };

    const handleRemoveProperty = (key) => {
      const newObj = { ...safeObj };
      delete newObj[key];
      onObjChange(newObj);
    };

    const handleKeyChange = (oldKey, newKey) => {
      if (oldKey === newKey) return;
      const newObj = {};
      Object.keys(safeObj).forEach(k => {
        if (k === oldKey) {
          newObj[newKey] = safeObj[k];
        } else {
          newObj[k] = safeObj[k];
        }
      });
      onObjChange(newObj);
    };

    const handleValueChange = (key, value) => {
      const newObj = { ...safeObj, [key]: value };
      onObjChange(newObj);
    };

    const renderValueInput = (key, value) => {
      const valueType = detectValueType(value);
      
      switch (valueType) {
        case 'object':
          return (
            <div className="mt-2">
              <button
                onClick={() => toggleExpanded(`${pathKey}.${key}`)}
                className="flex items-center text-xs text-gray-600 hover:text-gray-800"
              >
                {expandedKeys.has(`${pathKey}.${key}`) ? 
                  <ChevronDownIcon className="w-3 h-3 mr-1" /> : 
                  <ChevronRightIcon className="w-3 h-3 mr-1" />
                }
                Object ({Object.keys(value).length} properties)
              </button>
              {expandedKeys.has(`${pathKey}.${key}`) && (
                <div className="ml-4 mt-2">
                  <JsonObjectInput 
                    obj={value} 
                    path={[...path, key]}
                    onChange={(newObj) => handleValueChange(key, newObj)}
                  />
                </div>
              )}
            </div>
          );
        
        case 'array':
          return (
            <div className="mt-2">
              <button
                onClick={() => toggleExpanded(`${pathKey}.${key}`)}
                className="flex items-center text-xs text-gray-600 hover:text-gray-800"
              >
                {expandedKeys.has(`${pathKey}.${key}`) ? 
                  <ChevronDownIcon className="w-3 h-3 mr-1" /> : 
                  <ChevronRightIcon className="w-3 h-3 mr-1" />
                }
                Array ({value.length} items)
              </button>
              {expandedKeys.has(`${pathKey}.${key}`) && (
                <div className="ml-4 mt-2">
                  <Matrix2DArrayInput 
                    value={value} 
                    onChange={(newValue) => handleValueChange(key, newValue)}
                    itemType={variable.itemType || 'string'}
                  />
                </div>
              )}
            </div>
          );
        
        case 'boolean':
          return (
            <select
              value={value.toString()}
              onChange={(e) => handleValueChange(key, e.target.value === 'true')}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="false">false</option>
              <option value="true">true</option>
            </select>
          );
        
        case 'number':
          return (
            <input
              type="number"
              value={value}
              onChange={(e) => handleValueChange(key, parseFloat(e.target.value) || 0)}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          );
        
        default:
          return (
            <input
              type="text"
              value={value || ''}
              onChange={(e) => handleValueChange(key, e.target.value)}
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="Enter value"
            />
          );
      }
    };

    return (
      <div className="space-y-3">
        {Object.entries(safeObj).map(([key, value]) => (
          <div key={key} className="border border-gray-200 rounded p-3 bg-gray-50">
            <div className="flex items-start space-x-2 mb-2">
              <input
                type="text"
                value={key}
                onChange={(e) => handleKeyChange(key, e.target.value)}
                className="flex-1 px-2 py-1 text-sm font-medium border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Property name"
              />
              <button
                onClick={() => handleRemoveProperty(key)}
                className="p-1 text-red-400 hover:text-red-600"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
            {renderValueInput(key, value)}
          </div>
        ))}
        <button
          onClick={handleAddProperty}
          className="flex items-center px-3 py-1 text-sm text-blue-600 hover:text-blue-700 border border-dashed border-blue-300 rounded hover:border-blue-400"
        >
          <PlusIcon className="w-4 h-4 mr-1" />
          Add Property
        </button>
      </div>
    );
  };

  // Helper to add type information to nested structures
  const addTypeInfo = () => {
    return (
      <div className="flex items-center space-x-2 text-xs text-gray-500 mb-1">
        <InformationCircleIcon className="w-4 h-4" />
        <span>
          {variable.dataType === DataTypes.ARRAY && variable.itemType && 
            `Array of ${variable.itemType}s`}
          {variable.dataType === DataTypes.OBJECT && 
            `Object with ${Object.keys(localValue || {}).length} properties`}
        </span>
      </div>
    );
  };

  // Render the appropriate input based on data type
  const renderInput = () => {
    if (inputMode === 'json') {
      return (
        <div>
          <textarea
            value={typeof localValue === 'string' ? localValue : JSON.stringify(localValue, null, 2)}
            onChange={(e) => handleJsonChange(e.target.value)}
            rows={10}
            className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
              jsonError ? 'border-red-300' : 'border-gray-300'
            } focus:outline-none focus:ring-1 focus:ring-blue-500`}
            placeholder={variable.dataType === 'array' ? '["item1", "item2"]' : '{"key": "value"}'}
          />
          {jsonError && (
            <p className="mt-1 text-sm text-red-600">{jsonError}</p>
          )}
        </div>
      );
    }

    // Visual mode
    if (variable.dataType === 'array' || variable.dataType === DataTypes.ARRAY) {
      return <Matrix2DArrayInput 
        value={localValue || []} 
        onChange={handleChange}
        itemType={variable.itemType || 'string'}
      />;
    }

    if (variable.dataType === 'json' || variable.dataType === 'object' || 
        variable.dataType === DataTypes.JSON || variable.dataType === DataTypes.OBJECT) {
      return <JsonObjectInput obj={localValue || {}} onChange={handleChange} />;
    }

    // For other types, fall back to simple inputs
    switch (variable.dataType) {
      case 'boolean':
        return (
          <select
            value={(localValue || false).toString()}
            onChange={(e) => handleChange(e.target.value === 'true')}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="false">False</option>
            <option value="true">True</option>
          </select>
        );

      case 'number':
        return (
          <input
            type="number"
            value={localValue || ''}
            onChange={(e) => {
              const val = e.target.value;
              setLocalValue(val);
              // Debounce the parent update
              if (debounceRef.current) {
                clearTimeout(debounceRef.current);
              }
              debounceRef.current = setTimeout(() => {
                handleChange(parseFloat(val) || 0);
              }, 300);
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            min={variable.validation?.min}
            max={variable.validation?.max}
          />
        );

      case 'date':
        return (
          <input
            type="date"
            value={localValue || ''}
            onChange={(e) => {
              const val = e.target.value;
              setLocalValue(val);
              // Debounce the parent update
              if (debounceRef.current) {
                clearTimeout(debounceRef.current);
              }
              debounceRef.current = setTimeout(() => {
                handleChange(val);
              }, 300);
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        );

      default:
        return (
          <input
            type="text"
            value={localValue || ''}
            onChange={(e) => {
              const val = e.target.value;
              setLocalValue(val);
              // Debounce the parent update
              if (debounceRef.current) {
                clearTimeout(debounceRef.current);
              }
              debounceRef.current = setTimeout(() => {
                handleChange(val);
              }, 300);
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder={variable.description || ''}
          />
        );
    }
  };

  return (
    <div className={className}>
      {showModeToggle && (variable.dataType === DataTypes.ARRAY || variable.dataType === DataTypes.JSON || variable.dataType === DataTypes.OBJECT) && (
        <div className="flex justify-between items-center mb-2">
          {inputMode === 'visual' && addTypeInfo()}
          <div className="flex items-center space-x-1">
            <button
              onClick={() => setInputMode('visual')}
              className={`px-2 py-1 text-xs rounded ${
                inputMode === 'visual' 
                  ? 'bg-blue-100 text-blue-700' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <DocumentTextIcon className="w-3 h-3 inline mr-1" />
              Visual
            </button>
            <button
              onClick={() => setInputMode('json')}
              className={`px-2 py-1 text-xs rounded ${
                inputMode === 'json' 
                  ? 'bg-blue-100 text-blue-700' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <CodeBracketIcon className="w-3 h-3 inline mr-1" />
              JSON
            </button>
          </div>
        </div>
      )}
      {renderInput()}
      {validationError && (
        <div className="flex items-center mt-1 text-red-500 text-xs">
          <ExclamationCircleIcon className="w-4 h-4 mr-1" />
          {validationError}
        </div>
      )}
    </div>
  );
});

EnhancedParameterInput.displayName = 'EnhancedParameterInput';

export default EnhancedParameterInput;