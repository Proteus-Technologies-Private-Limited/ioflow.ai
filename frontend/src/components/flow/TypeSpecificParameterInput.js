import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  DocumentTextIcon,
  CodeBracketIcon,
  ListBulletIcon,
  CubeIcon,
  CommandLineIcon,
} from '@heroicons/react/24/outline';
import EnhancedParameterInput from './EnhancedParameterInput';
import { DataTypes, getDefaultValue, validateValue } from '../../utils/dataTypeUtils';

const TypeSpecificParameterInput = React.memo(({ 
  variable, 
  value, 
  onChange,
  className = '' 
}) => {
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
        
      case DataTypes.NUMBER:
      case DataTypes.INTEGER:
      case 'number':
      case 'integer':
        modes.push({ id: 'visual', label: 'Number', icon: DocumentTextIcon });
        break;
        
      case DataTypes.DATE:
      case DataTypes.DATETIME:
      case 'date':
      case 'datetime':
        modes.push({ id: 'visual', label: 'Date Picker', icon: DocumentTextIcon });
        break;
        
      default:
        // For string, email, url, etc., visual mode is just a regular input
        modes.push({ id: 'visual', label: 'Input', icon: DocumentTextIcon });
    }
    
    return modes;
  };

  const availableModes = getAvailableModes();
  const [activeMode, setActiveMode] = useState(availableModes[0].id);
  const [textValue, setTextValue] = useState('');
  const [parseError, setParseError] = useState('');
  const timeoutRef = useRef(null);

  // Initialize text value
  useEffect(() => {
    if (value !== undefined && value !== null) {
      if (typeof value === 'object') {
        setTextValue(JSON.stringify(value, null, 2));
      } else {
        setTextValue(String(value));
      }
    } else {
      setTextValue('');
    }
  }, [value]);

  // Handle text input changes with debouncing
  const handleTextChange = useCallback((text) => {
    setTextValue(text);
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
        if (!text.trim()) {
          parsedValue = getDefaultValue(variable.dataType);
          onChange(variable.name, parsedValue);
          return;
        }
        
        // Try to parse based on data type
        switch (variable.dataType) {
          case DataTypes.ARRAY:
          case 'array':
            parsedValue = JSON.parse(text);
            if (!Array.isArray(parsedValue)) {
              throw new Error('Value must be an array');
            }
            break;
            
          case DataTypes.OBJECT:
          case DataTypes.JSON:
          case 'object':
          case 'json':
            parsedValue = JSON.parse(text);
            if (typeof parsedValue !== 'object' || Array.isArray(parsedValue)) {
              throw new Error('Value must be an object');
            }
            break;
            
          case DataTypes.NUMBER:
          case 'number':
            parsedValue = parseFloat(text);
            if (isNaN(parsedValue)) {
              throw new Error('Value must be a number');
            }
            break;
            
          case DataTypes.INTEGER:
          case 'integer':
            parsedValue = parseInt(text);
            if (isNaN(parsedValue)) {
              throw new Error('Value must be an integer');
            }
            break;
            
          case DataTypes.BOOLEAN:
          case 'boolean':
            if (text.toLowerCase() === 'true') {
              parsedValue = true;
            } else if (text.toLowerCase() === 'false') {
              parsedValue = false;
            } else {
              throw new Error('Value must be true or false');
            }
            break;
            
          default:
            parsedValue = text;
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

  // Handle visual change callback - defined outside renderInput to maintain hooks order
  const handleVisualChange = useCallback((name, val) => {
    onChange(name, val);
  }, [onChange]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Render the appropriate input based on mode
  const renderInput = () => {
    switch (activeMode) {
      case 'text':
        return (
          <div>
            <textarea
              value={textValue}
              onChange={(e) => handleTextChange(e.target.value)}
              rows={8}
              className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
                parseError ? 'border-red-300' : 'border-gray-300'
              } focus:outline-none focus:ring-1 focus:ring-blue-500`}
              placeholder={getPlaceholder()}
            />
            {parseError && (
              <p className="mt-1 text-sm text-red-600">{parseError}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              {getHelpText()}
            </p>
          </div>
        );
        
      case 'json':
        return (
          <div>
            <textarea
              value={textValue}
              onChange={(e) => handleTextChange(e.target.value)}
              rows={10}
              className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
                parseError ? 'border-red-300' : 'border-gray-300'
              } focus:outline-none focus:ring-1 focus:ring-blue-500`}
              placeholder={variable.dataType === 'array' ? '["item1", "item2"]' : '{"key": "value"}'}
            />
            {parseError && (
              <p className="mt-1 text-sm text-red-600">{parseError}</p>
            )}
          </div>
        );
        
      case 'visual':
        // Use the enhanced parameter input for visual mode
        return (
          <EnhancedParameterInput
            variable={variable}
            value={value}
            onChange={handleVisualChange}
            showModeToggle={false}
          />
        );
        
      default:
        return null;
    }
  };

  // Get placeholder text based on data type
  const getPlaceholder = () => {
    switch (variable.dataType) {
      case DataTypes.ARRAY:
      case 'array':
        return '["item1", "item2", "item3"]';
      case DataTypes.OBJECT:
      case DataTypes.JSON:
      case 'object':
      case 'json':
        return '{"key": "value", "nested": {"prop": 123}}';
      case DataTypes.NUMBER:
      case 'number':
        return '42.5';
      case DataTypes.INTEGER:
      case 'integer':
        return '42';
      case DataTypes.BOOLEAN:
      case 'boolean':
        return 'true or false';
      case DataTypes.DATE:
      case 'date':
        return 'YYYY-MM-DD';
      case DataTypes.DATETIME:
      case 'datetime':
        return 'YYYY-MM-DDTHH:mm:ss';
      case DataTypes.EMAIL:
      case 'email':
        return 'user@example.com';
      case DataTypes.URL:
      case 'url':
        return 'https://example.com';
      default:
        return 'Enter value...';
    }
  };

  // Get help text based on data type
  const getHelpText = () => {
    switch (variable.dataType) {
      case DataTypes.ARRAY:
      case 'array':
        return 'Enter a JSON array. Example: ["value1", "value2", 123, true]';
      case DataTypes.OBJECT:
      case DataTypes.JSON:
      case 'object':
      case 'json':
        return 'Enter a JSON object. Example: {"name": "John", "age": 30}';
      case DataTypes.NUMBER:
      case 'number':
        return 'Enter a number (decimals allowed)';
      case DataTypes.INTEGER:
      case 'integer':
        return 'Enter a whole number (no decimals)';
      case DataTypes.BOOLEAN:
      case 'boolean':
        return 'Enter true or false';
      case DataTypes.DATE:
      case 'date':
        return 'Enter date in YYYY-MM-DD format';
      case DataTypes.DATETIME:
      case 'datetime':
        return 'Enter datetime in ISO format';
      default:
        return '';
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

TypeSpecificParameterInput.displayName = 'TypeSpecificParameterInput';

export default TypeSpecificParameterInput;