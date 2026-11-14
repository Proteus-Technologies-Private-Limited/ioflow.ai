import React, { useRef, useEffect, useState, useCallback } from 'react';
import {
  DocumentTextIcon,
  CodeBracketIcon,
  ListBulletIcon,
  CubeIcon,
} from '@heroicons/react/24/outline';
import EnhancedParameterInput from './EnhancedParameterInput';
import { DataTypes, getDefaultValue, validateValue } from '../../utils/dataTypeUtils';

const StableParameterInput = React.memo(({ 
  variable, 
  value, 
  onChange,
  className = '' 
}) => {
  const textAreaRef = useRef(null);
  const inputRef = useRef(null);
  const timeoutRef = useRef(null);
  const [activeMode, setActiveMode] = useState('visual');
  const [parseError, setParseError] = useState('');
  const [hasInitialized, setHasInitialized] = useState(false);

  // Determine available input modes based on data type
  const getAvailableModes = () => {
    const modes = [];
    
    // All types support free text input
    modes.push({ id: 'text', label: 'Text', icon: DocumentTextIcon });
    
    switch (variable.dataType) {
      case DataTypes.ARRAY:
      case 'array':
        modes.push({ id: 'visual', label: 'Array Editor', icon: ListBulletIcon });
        modes.push({ id: 'json', label: 'JSON', icon: CodeBracketIcon });
        break;
        
      case DataTypes.OBJECT:
      case DataTypes.JSON:
      case 'object':
      case 'json':
        modes.push({ id: 'visual', label: 'Object Editor', icon: CubeIcon });
        modes.push({ id: 'json', label: 'JSON', icon: CodeBracketIcon });
        break;
        
      case DataTypes.BOOLEAN:
      case 'boolean':
        modes.push({ id: 'visual', label: 'Toggle', icon: DocumentTextIcon });
        break;
        
      default:
        // For other types, visual mode is the default
        if (modes.length === 1) {
          return modes; // Only text mode
        }
        modes.push({ id: 'visual', label: 'Input', icon: DocumentTextIcon });
    }
    
    return modes;
  };

  const availableModes = getAvailableModes();

  // Initialize input value only once
  useEffect(() => {
    if (!hasInitialized && (textAreaRef.current || inputRef.current)) {
      const stringValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value || '');
      if (textAreaRef.current) {
        textAreaRef.current.value = stringValue;
      }
      if (inputRef.current) {
        inputRef.current.value = stringValue;
      }
      setHasInitialized(true);
    }
  }, [value, hasInitialized]);

  // Handle input changes with debouncing
  const handleInputChange = useCallback((inputValue) => {
    setParseError('');
    
    // Clear existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    
    // Debounce the parsing and validation
    timeoutRef.current = setTimeout(() => {
      try {
        let parsedValue;
        
        // For empty text, use default value
        if (!inputValue.trim()) {
          parsedValue = getDefaultValue(variable.dataType);
          onChange(variable.name, parsedValue);
          return;
        }
        
        // Try to parse based on data type
        switch (variable.dataType) {
          case DataTypes.ARRAY:
          case 'array':
            parsedValue = JSON.parse(inputValue);
            if (!Array.isArray(parsedValue)) {
              throw new Error('Value must be an array');
            }
            break;
            
          case DataTypes.OBJECT:
          case DataTypes.JSON:
          case 'object':
          case 'json':
            parsedValue = JSON.parse(inputValue);
            if (typeof parsedValue !== 'object' || Array.isArray(parsedValue)) {
              throw new Error('Value must be an object');
            }
            break;
            
          case DataTypes.NUMBER:
          case 'number':
            parsedValue = parseFloat(inputValue);
            if (isNaN(parsedValue)) {
              throw new Error('Value must be a number');
            }
            break;
            
          case DataTypes.INTEGER:
          case 'integer':
            parsedValue = parseInt(inputValue);
            if (isNaN(parsedValue)) {
              throw new Error('Value must be an integer');
            }
            break;
            
          case DataTypes.BOOLEAN:
          case 'boolean':
            if (inputValue.toLowerCase() === 'true') {
              parsedValue = true;
            } else if (inputValue.toLowerCase() === 'false') {
              parsedValue = false;
            } else {
              throw new Error('Value must be true or false');
            }
            break;
            
          default:
            parsedValue = inputValue;
        }
        
        // Validate the parsed value
        const validation = validateValue(parsedValue, variable.dataType, variable.validation);
        if (!validation.isValid) {
          setParseError(validation.error);
        } else {
          onChange(variable.name, parsedValue);
        }
      } catch (e) {
        setParseError(e.message);
      }
    }, 500); // 500ms debounce
  }, [variable.dataType, variable.name, variable.validation, onChange]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Get placeholder text
  const getPlaceholder = () => {
    switch (variable.dataType) {
      case DataTypes.ARRAY:
      case 'array':
        return '["item1", "item2", "item3"]';
      case DataTypes.OBJECT:
      case DataTypes.JSON:
      case 'object':
      case 'json':
        return '{"key": "value"}';
      case DataTypes.NUMBER:
      case 'number':
        return '42.5';
      case DataTypes.INTEGER:
      case 'integer':
        return '42';
      case DataTypes.BOOLEAN:
      case 'boolean':
        return 'true or false';
      default:
        return 'Enter value...';
    }
  };

  // Render the appropriate input based on mode
  const renderInput = () => {
    switch (activeMode) {
      case 'text':
      case 'json':
        return (
          <div>
            <textarea
              ref={textAreaRef}
              onChange={(e) => handleInputChange(e.target.value)}
              rows={activeMode === 'json' ? 10 : 8}
              className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
                parseError ? 'border-red-300' : 'border-gray-300'
              } focus:outline-none focus:ring-1 focus:ring-blue-500`}
              placeholder={getPlaceholder()}
            />
            {parseError && (
              <p className="mt-1 text-sm text-red-600">{parseError}</p>
            )}
            {activeMode === 'text' && (
              <p className="mt-1 text-xs text-gray-500">
                Enter value as text. Arrays and objects should be in JSON format.
              </p>
            )}
          </div>
        );
        
      case 'visual':
        if (variable.dataType === 'array' || variable.dataType === DataTypes.ARRAY ||
            variable.dataType === 'json' || variable.dataType === 'object' ||
            variable.dataType === DataTypes.JSON || variable.dataType === DataTypes.OBJECT) {
          // Use EnhancedParameterInput for complex types
          return (
            <EnhancedParameterInput
              variable={variable}
              value={value}
              onChange={onChange}
              showModeToggle={false}
            />
          );
        }
        
        // Simple input for other types
        return (
          <input
            ref={inputRef}
            type={variable.dataType === 'number' || variable.dataType === 'integer' ? 'number' : 'text'}
            onChange={(e) => handleInputChange(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder={getPlaceholder()}
          />
        );
        
      default:
        return null;
    }
  };

  return (
    <div className={className}>
      {availableModes.length > 1 && (
        <div className="flex items-center space-x-1 mb-2">
          {availableModes.map(mode => {
            const Icon = mode.icon;
            return (
              <button
                key={mode.id}
                onClick={() => setActiveMode(mode.id)}
                className={`px-3 py-1 text-xs rounded flex items-center ${
                  activeMode === mode.id
                    ? 'bg-blue-100 text-blue-700'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <Icon className="w-3 h-3 mr-1" />
                {mode.label}
              </button>
            );
          })}
        </div>
      )}
      {renderInput()}
    </div>
  );
});

StableParameterInput.displayName = 'StableParameterInput';

export default StableParameterInput;