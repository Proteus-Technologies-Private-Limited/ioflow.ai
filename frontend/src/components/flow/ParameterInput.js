import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  VariableIcon,
  PencilIcon,
  CodeBracketIcon,
  ListBulletIcon,
  ChevronDownIcon,
  LightBulbIcon,
  CheckIcon,
} from '@heroicons/react/24/outline';
import NestedVariableSelector from './NestedVariableSelector';
import ParameterLookupPopup from './ParameterLookupPopup';
import VariablePill from './VariablePill';
import QuickVariableButton from './QuickVariableButton';
import InlineVariablePills from './InlineVariablePills';
import { findMatchingVariables, suggestsDynamicData } from '../../utils/fieldMatcher';

const ParameterInput = ({
  name,
  value,
  onChange,
  type = 'string',
  placeholder = '',
  required = false,
  description = '',
  availableVariables = {},
  mode = 'edit', // 'edit' or 'view'
  parameterLookup = null, // Parameter lookup configuration
  subscriptionId = null, // For API calls
  defaultValue = null, // Default value from schema
  onClear = null, // Callback to clear value and use default
  initialSourceType = 'static', // Initial source type from parent
  hideModeToggle = false, // Hide the mode toggle buttons (when parent handles it)
  forceInputMode = null // Force a specific input mode from parent
}) => {
  const [localInputMode, setLocalInputMode] = useState(initialSourceType === 'variable' ? 'variable' : 'constant'); // 'constant', 'variable', or 'lookup'

  // Use forceInputMode if provided, otherwise use local state
  const inputMode = forceInputMode || localInputMode;
  const setInputMode = forceInputMode ? () => {} : setLocalInputMode; // Disable local state updates when forced
  const [tempValue, setTempValue] = useState(value || '');
  const [lookupOptions, setLookupOptions] = useState([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState(null);
  const [showLookupPopup, setShowLookupPopup] = useState(false);
  const [showQuickVariableSelector, setShowQuickVariableSelector] = useState(false);
  const [fieldSuggestions, setFieldSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const inputRef = useRef(null);

  // @ mention autocomplete state
  const [showMentionPicker, setShowMentionPicker] = useState(false);
  const [mentionSearch, setMentionSearch] = useState('');
  const [mentionStartPos, setMentionStartPos] = useState(0);
  const [mentionSelectedIndex, setMentionSelectedIndex] = useState(0);

  // Handle Escape key to close quick variable selector modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && showQuickVariableSelector) {
        setShowQuickVariableSelector(false);
        setTimeout(() => {
          if (inputRef.current) {
            inputRef.current.focus();
          }
        }, 10);
      }
    };

    if (showQuickVariableSelector) {
      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }
  }, [showQuickVariableSelector]);

  // Calculate field suggestions when field name or available variables change
  useEffect(() => {
    // Only show suggestions if:
    // 1. Field is empty (no value set yet)
    // 2. We have available variables
    // 3. Field name suggests it needs dynamic data
    // 4. We're in constant mode (not already using variables)
    const shouldShowSuggestions =
      !value &&
      inputMode === 'constant' &&
      Object.keys(availableVariables).length > 0 &&
      suggestsDynamicData(name);

    if (shouldShowSuggestions) {
      const matches = findMatchingVariables(
        name,
        availableVariables,
        availableVariables._nodeMetadata || {},
        1, // Only show best match
        0.65 // Slightly lower threshold for suggestions
      );

      if (matches.length > 0) {
        setFieldSuggestions(matches);
        setShowSuggestions(true);
      } else {
        setFieldSuggestions([]);
        setShowSuggestions(false);
      }
    } else {
      setFieldSuggestions([]);
      setShowSuggestions(false);
    }
  }, [name, value, inputMode, availableVariables]);

  // Helper functions for default value handling
  const hasDefaultValue = defaultValue !== null && defaultValue !== undefined;
  const isUsingDefault = value === defaultValue && hasDefaultValue;
  const isValueSet = value !== null && value !== undefined && value !== '';
  const isCleared = value === null || value === undefined;
  
  // Format default value for display
  const formatDefaultValue = (defaultVal) => {
    if (defaultVal === null || defaultVal === undefined) return '';
    if (typeof defaultVal === 'object') return JSON.stringify(defaultVal);
    return String(defaultVal);
  };

  // Clear value - pass null (parameter won't be sent)
  const handleClearValue = () => {
    onChange(null);
    setTempValue('');
    // Don't change mode - let user stay in current mode
    if (onClear) onClear();
  };
  
  // Use default value - explicitly pass the default value
  const handleUseDefault = () => {
    setInputMode('constant');
    setTempValue(defaultValue);
    onChange(defaultValue);
  };

  // Helper to detect if value is a pure variable reference (no static text)
  const isPureVariableReference = React.useCallback((val) => {
    if (!val || typeof val !== 'string') return false;

    const trimmed = val.trim();

    // Check if it's a direct variable path (no spaces, no {{ }}, starts with known prefix)
    const isDirectPath = (
      (trimmed.startsWith('input.') ||
       trimmed.startsWith('node_outputs.') ||
       trimmed.startsWith('trigger.') ||
       trimmed.startsWith('loop.') ||
       trimmed.startsWith('variables.') ||
       trimmed.startsWith('global_vars.')) &&
      !trimmed.includes(' ') &&
      !trimmed.includes('{{')
    );

    if (isDirectPath) return true;

    // Check if it's a single variable wrapped in {{ }} with nothing else
    const singleVarMatch = trimmed.match(/^{{([^}]+)}}$/);
    if (singleVarMatch) {
      const allVarMatches = trimmed.match(/{{[^}]+}}/g) || [];
      // Must be exactly one variable and nothing else
      return allVarMatches.length === 1 && trimmed === allVarMatches[0];
    }

    return false;
  }, []);

  // Initialize input mode and temp value based on value content
  React.useEffect(() => {
    const valueToUse = value || '';
    setTempValue(valueToUse);

    // Auto-detect mode based on content
    const isPureVariable = isPureVariableReference(valueToUse);
    setInputMode(isPureVariable ? 'variable' : 'constant');
  }, [value, isPureVariableReference]);

  // Load parameter lookup options
  const loadLookupOptions = async () => {
    if (!parameterLookup || !subscriptionId) return;
    
    setLookupLoading(true);
    setLookupError(null);
    
    try {
      const response = await axios.post(`/api/v1/applications/subscriptions/${subscriptionId}/parameter-lookup`, {
        parameter_name: name,
        parameter_lookup: parameterLookup
      });
      
      const data = response.data;
      setLookupOptions(data.options || []);
    } catch (error) {
      console.error('Error loading parameter lookup options:', error);
      setLookupError(error.message);
    } finally {
      setLookupLoading(false);
    }
  };

  const handleModeChange = async (newMode) => {
    if (newMode === 'lookup') {
      // When switching to lookup mode, show popup immediately and load options
      setInputMode(newMode);
      setShowLookupPopup(true);
      if (!lookupOptions.length && !lookupLoading) {
        loadLookupOptions();
      }
      return;
    }

    if (newMode === 'variable') {
      // Show quick variable selector to help user pick a variable
      setShowQuickVariableSelector(true);
      setIsEditing(true);
      // Focus input after selector appears
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
        }
      }, 50);
      return;
    }

    // For constant mode, just focus the input
    // The actual mode will be auto-detected based on content
    setInputMode('constant');
    setIsEditing(true);
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    }, 10);
  };

  const handleValueChange = (newValue) => {
    setTempValue(newValue);

    // Auto-detect type based on content
    const isPureVariable = isPureVariableReference(newValue);
    const detectedMode = isPureVariable ? 'variable' : 'constant';

    console.log('[ParameterInput] handleValueChange:', {
      newValue,
      isPureVariable,
      detectedMode,
      currentInputMode: inputMode
    });

    // Update mode if it changed
    if (detectedMode !== inputMode) {
      setInputMode(detectedMode);
    }

    const sourceType = isPureVariable ? 'variable' : 'static';

    if (inputMode === 'lookup') {
      // For lookup mode, convert value based on parameter data type
      const convertedValue = convertToDataType(newValue, type);
      if (onChange.length > 1) {
        console.log('[ParameterInput] Calling onChange with:', convertedValue, 'static');
        onChange(convertedValue, 'static');
      } else {
        onChange(convertedValue);
      }
    } else {
      // Always pass the value with the detected source type
      if (onChange.length > 1) {
        console.log('[ParameterInput] Calling onChange with:', newValue, sourceType);
        onChange(newValue || '', sourceType);
      } else {
        onChange(newValue || '');
      }
    }
  };

  // Helper function to convert values based on data type
  const convertToDataType = (value, dataType) => {
    if (!value) return value;
    
    switch (dataType?.toLowerCase()) {
      case 'array':
        // Convert single value to array format
        if (typeof value === 'string' && !value.startsWith('[')) {
          return `["${value}"]`;
        }
        return value;
      
      case 'object':
        // Convert single value to object format if needed
        if (typeof value === 'string' && !value.startsWith('{')) {
          return `{"value": "${value}"}`;
        }
        return value;
      
      case 'number':
      case 'integer':
        // Convert to number
        return isNaN(Number(value)) ? value : Number(value);
      
      case 'boolean':
        // Convert to boolean
        if (value === 'true' || value === true) return true;
        if (value === 'false' || value === false) return false;
        return value;
      
      default:
        // String or unknown types - return as is
        return value;
    }
  };

  // Helper function to get format example
  const getFormatExample = (dataType) => {
    switch (dataType?.toLowerCase()) {
      case 'array':
        return '["item1", "item2"]';
      case 'object':
        return '{"key": "value"}';
      case 'number':
      case 'integer':
        return '123';
      case 'boolean':
        return 'true/false';
      default:
        return 'text';
    }
  };

  // Helper function to get raw value for popup selection
  const getRawValueForPopup = () => {
    // For popup selection, we want to match against the original lookup values
    const selectedOption = lookupOptions.find(opt => {
      if (type?.toLowerCase() === 'array') {
        return value === `["${opt.value}"]` || tempValue === opt.value;
      }
      return value === opt.value || tempValue === opt.value;
    });
    return selectedOption ? selectedOption.value : tempValue;
  };

  // Handler for quick variable selection (from + button)
  const handleQuickVariableSelect = (variablePath) => {
    // For non-string types (boolean, number, array, object), replace entire value
    // For string types, insert at cursor position
    const isStringType = !type || type === 'string' || type === 'text';

    let newValue;
    if (isStringType) {
      const currentValue = tempValue || '';
      const beforeCursor = currentValue.substring(0, cursorPosition);
      const afterCursor = currentValue.substring(cursorPosition);
      // Insert at cursor position
      newValue = `${beforeCursor}{{${variablePath}}}${afterCursor}`;
    } else {
      // For other types, replace entire value with variable
      newValue = `{{${variablePath}}}`;
    }

    console.log('[ParameterInput] handleQuickVariableSelect:', {
      type,
      isStringType,
      variablePath,
      newValue,
      forceInputMode,
      currentInputMode: inputMode
    });

    setTempValue(newValue);
    handleValueChange(newValue);
    setShowQuickVariableSelector(false);

    // Switch to variable mode
    if (!forceInputMode) {
      setLocalInputMode('variable');
    }

    // Restore focus to input after selection (only for text inputs)
    if (isStringType) {
      setTimeout(() => {
        if (inputRef.current) {
          inputRef.current.focus();
          // Put cursor after inserted variable
          const beforeCursor = (tempValue || '').substring(0, cursorPosition);
          const newCursorPos = beforeCursor.length + variablePath.length + 4; // 4 for {{ }}
          inputRef.current.setSelectionRange(newCursorPos, newCursorPos);
        }
      }, 10);
    }
  };

  // Handler for @ mention variable selection
  const handleMentionSelect = (variablePath) => {
    const currentValue = tempValue || '';
    // Replace @searchterm with {{variablePath}}
    const beforeMention = currentValue.substring(0, mentionStartPos);
    const afterMention = currentValue.substring(cursorPosition);
    const newValue = `${beforeMention}{{${variablePath}}}${afterMention}`;

    setTempValue(newValue);
    handleValueChange(newValue);
    setShowMentionPicker(false);
    setMentionSearch('');
    setMentionSelectedIndex(0);

    // Restore focus and set cursor after inserted variable
    setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus();
        const newCursorPos = beforeMention.length + variablePath.length + 4; // 4 for {{ }}
        inputRef.current.setSelectionRange(newCursorPos, newCursorPos);
        setCursorPosition(newCursorPos);
      }
    }, 10);
  };

  // Detect @ mention trigger
  const detectMentionTrigger = (value, cursorPos) => {
    // Find @ before cursor
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    if (lastAtIndex !== -1) {
      // Check if there's whitespace or start of string before @
      const charBeforeAt = lastAtIndex > 0 ? textBeforeCursor[lastAtIndex - 1] : ' ';
      const isValidTrigger = charBeforeAt === ' ' || lastAtIndex === 0;

      if (isValidTrigger) {
        // Extract search term after @
        const searchTerm = textBeforeCursor.substring(lastAtIndex + 1);
        // Check if search term doesn't contain spaces (still typing the mention)
        if (!searchTerm.includes(' ')) {
          setMentionStartPos(lastAtIndex);
          setMentionSearch(searchTerm);
          setShowMentionPicker(true);
          setMentionSelectedIndex(0); // Reset selection
          return;
        }
      }
    }

    // No valid @ trigger found
    setShowMentionPicker(false);
    setMentionSearch('');
    setMentionSelectedIndex(0);
  };

  // Get filtered variables for @ mention picker
  const getFilteredVariables = () => {
    const search = mentionSearch.toLowerCase();
    const allVars = [];

    // Helper to extract variables recursively
    const extractVars = (obj, prefix = '', categoryLabel = '') => {
      if (!obj || typeof obj !== 'object') return;
      Object.entries(obj).forEach(([key, value]) => {
        const path = prefix ? `${prefix}.${key}` : key;
        const label = `${categoryLabel}${categoryLabel ? ' • ' : ''}${key}`;

        allVars.push({
          path,
          label,
          key,
          category: categoryLabel
        });

        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          extractVars(value, path, categoryLabel);
        }
      });
    };

    // Extract from all categories
    if (availableVariables.input) {
      extractVars(availableVariables.input, 'input', 'Trigger Input');
    }
    if (availableVariables.node_outputs) {
      const nodeMetadata = availableVariables._nodeMetadata || {};
      Object.entries(availableVariables.node_outputs).forEach(([nodeId, nodeData]) => {
        const nodeInfo = nodeMetadata[nodeId] || {};
        const nodeLabel = nodeInfo.label || nodeId;
        extractVars(nodeData, `node_outputs.${nodeId}`, nodeLabel);
      });
    }
    if (availableVariables.loop) {
      extractVars(availableVariables.loop, 'loop', 'Current Item');
    }
    if (availableVariables.flow) {
      extractVars(availableVariables.flow, 'flow', 'Flow Info');
    }
    if (availableVariables.global) {
      extractVars(availableVariables.global, 'global', 'Global');
    }

    // Filter by search term
    if (!search) return allVars.slice(0, 10); // Show first 10 if no search

    return allVars.filter(v =>
      v.path.toLowerCase().includes(search) ||
      v.label.toLowerCase().includes(search) ||
      v.key.toLowerCase().includes(search)
    ).slice(0, 10); // Limit to 10 results
  };

  // Handler for applying a suggestion
  const applySuggestion = (suggestion) => {
    // Wrap in {{}} format for proper variable reference
    const wrappedPath = `{{${suggestion.path}}}`;
    setInputMode('variable');
    setTempValue(wrappedPath);
    handleValueChange(wrappedPath);
    setShowSuggestions(false);
  };

  const renderInput = () => {
    // For variable mode (regardless of type), show text input with variable path
    if (inputMode === 'variable') {
      return (
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={tempValue || ''}
            onChange={(e) => handleValueChange(e.target.value)}
            placeholder="Enter variable path or click + to select..."
            disabled={mode === 'view'}
            className="flex-1 px-3 py-2 border border-purple-300 bg-purple-50 rounded-md focus:outline-none focus:ring-1 focus:ring-purple-500 focus:border-purple-500 font-mono text-sm"
          />

          {/* Quick variable button */}
          <QuickVariableButton
            onClick={() => {
              setShowQuickVariableSelector(true);
              setIsEditing(true);
            }}
            disabled={mode === 'view'}
            size="md"
            tooltip="Insert data from previous steps"
          />
        </div>
      );
    }

    if (inputMode === 'lookup') {
      // Show the actual value (converted format) in the input field
      const displayValue = typeof value === 'object' ? JSON.stringify(value) : (value || tempValue || '');

      return (
        <>
          <div className="flex items-center space-x-2">
            <input
              type="text"
              value={displayValue}
              onChange={(e) => handleValueChange(e.target.value)}
              placeholder="Enter value or click lookup..."
              disabled={mode === 'view'}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => {
                if (!lookupOptions.length && !lookupLoading) {
                  loadLookupOptions();
                }
                setShowLookupPopup(true);
              }}
              disabled={mode === 'view'}
              className="px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-50 disabled:bg-gray-100 disabled:cursor-not-allowed"
              title="Browse available options"
            >
              <ListBulletIcon className="w-4 h-4 text-gray-600" />
            </button>
          </div>

          {/* Show type conversion info */}
          {type && (value || tempValue) && (
            <div className="mt-1 text-xs text-blue-600">
              Format: {type} - {getFormatExample(type)}
            </div>
          )}

          <ParameterLookupPopup
            isOpen={showLookupPopup}
            onClose={() => setShowLookupPopup(false)}
            options={lookupOptions}
            value={getRawValueForPopup()}
            onSelect={handleValueChange}
            placeholder="Select an option..."
            loading={lookupLoading}
            error={lookupError}
            title={parameterLookup?.description || `Select ${name}`}
          />
        </>
      );
    }

    // Constant mode inputs
    switch (type) {
      case 'boolean':
        return (
          <div className="flex items-center gap-2">
            <select
              value={tempValue || 'false'}
              onChange={(e) => handleValueChange(e.target.value === 'true')}
              disabled={mode === 'view'}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="false">False</option>
              <option value="true">True</option>
            </select>

            {/* Quick variable button */}
            <QuickVariableButton
              onClick={() => {
                console.log('[ParameterInput] QuickVariableButton clicked for BOOLEAN type', {
                  showQuickVariableSelector,
                  mode,
                  inputMode
                });
                setShowQuickVariableSelector(true);
                setIsEditing(true);
              }}
              disabled={mode === 'view'}
              size="md"
              tooltip="Insert data from previous steps"
            />
          </div>
        );

      case 'number':
      case 'integer':
        return (
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={tempValue || ''}
              onChange={(e) => handleValueChange(e.target.value ? Number(e.target.value) : '')}
              placeholder={
                hasDefaultValue && !placeholder
                  ? `Default: ${formatDefaultValue(defaultValue)}`
                  : placeholder
              }
              disabled={mode === 'view'}
              className={`flex-1 px-3 py-2 text-right border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 ${
                isUsingDefault ? 'border-blue-300 bg-blue-50' : 'border-gray-300'
              }`}
            />

            {/* Quick variable button */}
            <QuickVariableButton
              onClick={() => {
                console.log('[ParameterInput] QuickVariableButton clicked for NUMBER type');
                setShowQuickVariableSelector(true);
                setIsEditing(true);
              }}
              disabled={mode === 'view'}
              size="md"
              tooltip="Insert data from previous steps"
            />
          </div>
        );

      case 'object':
      case 'array':
        return (
          <div className="space-y-2">
            <textarea
              value={typeof tempValue === 'string' ? tempValue : JSON.stringify(tempValue, null, 2)}
              onChange={(e) => {
                try {
                  const parsed = JSON.parse(e.target.value);
                  handleValueChange(parsed);
                } catch {
                  // Keep as string if not valid JSON
                  handleValueChange(e.target.value);
                }
              }}
              placeholder={type === 'object' ? '{"key": "value"}' : '["item1", "item2"]'}
              rows={4}
              disabled={mode === 'view'}
              className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
            />

            {/* Quick variable button - below textarea */}
            <div className="flex justify-end">
              <QuickVariableButton
                onClick={() => {
                  console.log('[ParameterInput] QuickVariableButton clicked for ARRAY/OBJECT type');
                  setShowQuickVariableSelector(true);
                  setIsEditing(true);
                }}
                disabled={mode === 'view'}
                size="md"
                tooltip="Insert data from previous steps"
              />
            </div>
          </div>
        );

      default:
        return (
          <div className="relative">
            <div className="flex items-center gap-2">
              {/* Always show editable input */}
              <input
                  ref={inputRef}
                  type="text"
                  value={tempValue || ''}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    const newCursorPos = e.target.selectionStart || 0;

                    handleValueChange(newValue);
                    setCursorPosition(newCursorPos);

                    // Detect @ mention trigger
                    detectMentionTrigger(newValue, newCursorPos);
                  }}
                  onBlur={(e) => {
                    // Don't blur immediately if selector is open
                    if (showQuickVariableSelector || showMentionPicker) {
                      // Prevent blur when pickers are open
                      e.preventDefault();
                      if (inputRef.current) {
                        inputRef.current.focus();
                      }
                      return;
                    }
                  }}
                  onClick={(e) => {
                    setCursorPosition(e.target.selectionStart || 0);
                  }}
                  onKeyUp={(e) => {
                    setCursorPosition(e.target.selectionStart || 0);
                  }}
                  onKeyDown={(e) => {
                    if (showMentionPicker) {
                      const filteredVars = getFilteredVariables();

                      if (e.key === 'ArrowDown') {
                        e.preventDefault();
                        setMentionSelectedIndex(prev =>
                          prev < filteredVars.length - 1 ? prev + 1 : prev
                        );
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault();
                        setMentionSelectedIndex(prev => prev > 0 ? prev - 1 : 0);
                      } else if (e.key === 'Enter' && filteredVars.length > 0) {
                        e.preventDefault();
                        const selectedVar = filteredVars[mentionSelectedIndex];
                        if (selectedVar) {
                          handleMentionSelect(selectedVar.path);
                        }
                      } else if (e.key === 'Escape') {
                        setShowMentionPicker(false);
                        setMentionSearch('');
                        setMentionSelectedIndex(0);
                        e.preventDefault();
                      }
                    }
                  }}
                  placeholder={
                    hasDefaultValue && !placeholder
                      ? `Default: ${formatDefaultValue(defaultValue)}`
                      : (placeholder || 'Enter a value or click + to use data from previous steps')
                  }
                  disabled={mode === 'view'}
                  className={`flex-1 px-3 py-2 border rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 ${
                    isUsingDefault ? 'border-blue-300 bg-blue-50' : 'border-gray-300'
                  }`}
                />

              {/* Quick variable button - ALWAYS visible */}
              <QuickVariableButton
                onClick={() => {
                  setShowQuickVariableSelector(true);
                  setIsEditing(true);
                  // Focus input after selector appears
                  setTimeout(() => {
                    if (inputRef.current) {
                      inputRef.current.focus();
                    }
                  }, 50);
                }}
                disabled={mode === 'view'}
                size="md"
                tooltip="Insert data from previous steps"
              />
            </div>

            {/* @ mention picker - compact filtered dropdown */}
            {showMentionPicker && (
              <div
                className="absolute z-[100] mt-1 w-full max-w-sm"
                onMouseDown={(e) => {
                  // Prevent blur when clicking inside the picker
                  e.preventDefault();
                }}
              >
                <div className="bg-white border border-gray-300 rounded-md shadow-xl max-h-64 overflow-y-auto">
                  <div className="p-2 border-b bg-gray-50">
                    <div className="text-xs text-gray-600 flex items-center gap-1">
                      <span>Type to filter variables</span>
                      {mentionSearch && (
                        <span className="font-medium text-blue-600">@{mentionSearch}</span>
                      )}
                    </div>
                  </div>
                  <div className="py-1">
                    {getFilteredVariables().map((variable, index) => (
                      <button
                        key={variable.path}
                        onClick={() => handleMentionSelect(variable.path)}
                        className={`w-full text-left px-3 py-2 flex items-center justify-between group transition-colors ${
                          index === mentionSelectedIndex
                            ? 'bg-blue-100 border-l-2 border-blue-500'
                            : 'hover:bg-blue-50'
                        }`}
                      >
                        <div className="flex-1">
                          <div className={`text-sm font-medium ${
                            index === mentionSelectedIndex ? 'text-blue-900' : 'text-gray-900'
                          }`}>
                            {variable.label}
                          </div>
                          <div className={`text-xs font-mono ${
                            index === mentionSelectedIndex ? 'text-blue-700' : 'text-gray-500'
                          }`}>
                            {variable.path}
                          </div>
                        </div>
                        <div className={`text-xs ${
                          index === mentionSelectedIndex ? 'text-blue-600' : 'text-gray-400 group-hover:text-blue-600'
                        }`}>
                          ↵
                        </div>
                      </button>
                    ))}
                    {getFilteredVariables().length === 0 && (
                      <div className="px-3 py-4 text-center text-sm text-gray-500">
                        No variables match "@{mentionSearch}"
                      </div>
                    )}
                  </div>
                  <div className="p-2 border-t bg-gray-50 flex justify-between items-center">
                    <div className="text-xs text-gray-500">
                      <kbd className="px-1 py-0.5 bg-gray-200 rounded text-xs">↑↓</kbd> to navigate,
                      <kbd className="px-1 py-0.5 bg-gray-200 rounded text-xs ml-1">Enter</kbd> to select,
                      <kbd className="px-1 py-0.5 bg-gray-200 rounded text-xs ml-1">Esc</kbd> to cancel
                    </div>
                    <button
                      onClick={() => {
                        setShowMentionPicker(false);
                        setMentionSearch('');
                        setTimeout(() => {
                          if (inputRef.current) {
                            inputRef.current.focus();
                          }
                        }, 10);
                      }}
                      className="text-xs text-gray-600 hover:text-gray-800 px-2 py-1 hover:bg-gray-100 rounded"
                    >
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
    }
  };

  if (mode === 'view') {
    return (
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="block text-sm font-medium text-gray-700">
            {name}
            {required && <span className="text-red-500 ml-1">*</span>}
          </label>
          {inputMode === 'variable' && (
            <span className="text-xs text-blue-600 flex items-center">
              <CodeBracketIcon className="w-3 h-3 mr-1" />
              Variable
            </span>
          )}
        </div>
        {description && (
          <p className="text-xs text-gray-500 mb-1">{description}</p>
        )}
        <div className="text-gray-900">
          {value || '-'}
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Only show header if not hidden by parent */}
      {!hideModeToggle && (
        <>
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center space-x-2">
              <label className="block text-sm font-medium text-gray-700">
                {name}
                {required && <span className="text-red-500 ml-1">*</span>}
              </label>
              {/* Mode indicator and clear options */}
              <div className="flex items-center space-x-2">
                {/* Mode indicator */}
                {tempValue && (
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    inputMode === 'variable'
                      ? 'text-purple-600 bg-purple-50'
                      : 'text-blue-600 bg-blue-50'
                  }`}>
                    {inputMode === 'variable' ? 'Variable' : 'Static'}
                  </span>
                )}

                {/* Status indicators */}
                {hasDefaultValue && isCleared && (
                  <span className="text-xs text-gray-500">
                    Not set (default: {formatDefaultValue(defaultValue)})
                  </span>
                )}
                {hasDefaultValue && isUsingDefault && (
                  <span className="text-xs text-blue-600">
                    Using default: {formatDefaultValue(defaultValue)}
                  </span>
                )}

                {/* Use default button */}
                {hasDefaultValue && !isUsingDefault && (
                  <button
                    type="button"
                    onClick={handleUseDefault}
                    className="text-xs text-blue-500 hover:text-blue-700"
                    title={`Use default: ${formatDefaultValue(defaultValue)}`}
                  >
                    Use default
                  </button>
                )}

                {/* Clear button (always show when there's a value) */}
                {(isValueSet || tempValue || (inputMode === 'variable' && value)) && (
                  <button
                    type="button"
                    onClick={handleClearValue}
                    className="text-xs text-gray-500 hover:text-red-600"
                    title="Clear value"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
            <div className="flex space-x-1">
              <button
                type="button"
                onClick={() => handleModeChange('constant')}
                className={`p-1.5 rounded transition-colors ${
                  inputMode === 'constant'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                }`}
                title="Use constant value"
              >
                <PencilIcon className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => handleModeChange('variable')}
                className={`p-1.5 rounded transition-colors ${
                  inputMode === 'variable'
                    ? 'bg-purple-500 text-white'
                    : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                }`}
                title="Use variable"
              >
                <CodeBracketIcon className="w-4 h-4" />
              </button>
              {parameterLookup && subscriptionId && (
                <button
                  type="button"
                  onClick={() => handleModeChange('lookup')}
                  className={`p-1.5 rounded transition-colors ${
                    inputMode === 'lookup'
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-200 text-gray-500 hover:bg-gray-300'
                  }`}
                  title={parameterLookup.description || 'Select from available options'}
                >
                  <ListBulletIcon className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {description && (
            <p className="text-xs text-gray-500 mb-1">{description}</p>
          )}
        </>
      )}

      {/* Field suggestions */}
      {showSuggestions && fieldSuggestions.length > 0 && (
        <div className="mb-2 space-y-1">
          {fieldSuggestions.map((suggestion, index) => (
            <div
              key={index}
              className="flex items-center justify-between gap-2 p-2 bg-blue-50 border border-blue-200 rounded-lg hover:bg-blue-100 transition-colors group"
            >
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <LightBulbIcon className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-blue-900">
                    Smart suggestion
                  </div>
                  <div className="text-xs text-blue-700 truncate">
                    Use <span className="font-semibold">{suggestion.category}</span> → {suggestion.key}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => applySuggestion(suggestion)}
                className="flex items-center gap-1 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs font-medium transition-colors flex-shrink-0"
              >
                <CheckIcon className="w-3 h-3" />
                <span>Use this</span>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* User-friendly help text */}
      {inputMode === 'constant' && !description && !showSuggestions && Object.keys(availableVariables).length > 0 && (
        <p className="text-xs text-gray-400 mb-1">
          💡 Tip: Click the <span className="font-medium">+</span> button to use data from previous steps
        </p>
      )}

      <div className="relative">
        {renderInput()}
      </div>

      {/* Quick variable selector modal - shared across all input types */}
      {showQuickVariableSelector && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black bg-opacity-50 z-[999]"
            onClick={() => {
              setShowQuickVariableSelector(false);
              setTimeout(() => {
                if (inputRef.current) {
                  inputRef.current.focus();
                }
              }, 10);
            }}
          />

          {/* Modal */}
          <div className="fixed inset-0 z-[1000] overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4">
              <div
                className="bg-white rounded-lg shadow-2xl w-full max-w-2xl"
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-purple-50">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                        <VariableIcon className="w-5 h-5 text-blue-600" />
                        Select Variable
                      </h3>
                      <p className="text-sm text-gray-600 mt-1">
                        Choose data from previous steps to use in this field
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setShowQuickVariableSelector(false);
                        setTimeout(() => {
                          if (inputRef.current) {
                            inputRef.current.focus();
                          }
                        }, 10);
                      }}
                      className="text-gray-400 hover:text-gray-600 transition-colors"
                    >
                      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="p-6">
                  <VariablePickerWithTabs
                    value=""
                    onVariableSelect={(path) => {
                      handleQuickVariableSelect(path);
                      setShowQuickVariableSelector(false);
                    }}
                    onLookupSelect={(selectedValue, selectedLabel) => {
                      // Handle lookup selection similar to existing handleParameterLookupSelect
                      onChange(selectedValue, 'constant');
                      setTempValue(selectedValue);
                      setInputMode('constant');
                      setShowQuickVariableSelector(false);
                    }}
                    availableVariables={availableVariables}
                    parameterLookup={parameterLookup}
                    subscriptionId={subscriptionId}
                    parameterName={name}
                    mode={mode}
                  />
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-lg flex justify-between items-center">
                  <div className="text-xs text-gray-500">
                    <span className="font-medium">Tip:</span> Variables will be inserted as{' '}
                    <code className="px-1.5 py-0.5 bg-gray-200 rounded text-purple-700">{`{{variable_path}}`}</code>
                  </div>
                  <button
                    onClick={() => {
                      setShowQuickVariableSelector(false);
                      setTimeout(() => {
                        if (inputRef.current) {
                          inputRef.current.focus();
                        }
                      }, 10);
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-200 rounded-md transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

// Component for variable picker with tabs (Variables and Lookup)
const VariablePickerWithTabs = ({
  value,
  onVariableSelect,
  onLookupSelect,
  availableVariables,
  parameterLookup,
  subscriptionId,
  parameterName,
  mode
}) => {
  const [activeTab, setActiveTab] = useState('variables');
  const [lookupOptions, setLookupOptions] = useState([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Show Lookup tab only if parameterLookup is configured
  const hasLookup = parameterLookup !== null && parameterLookup !== undefined;

  // Load lookup options when Lookup tab is activated
  useEffect(() => {
    if (activeTab === 'lookup' && hasLookup && !lookupOptions.length && !lookupLoading) {
      loadLookupOptions();
    }
  }, [activeTab]);

  const loadLookupOptions = async () => {
    if (!parameterLookup || !subscriptionId) return;

    setLookupLoading(true);
    setLookupError(null);

    try {
      const response = await axios.post(`/api/v1/applications/subscriptions/${subscriptionId}/parameter-lookup`, {
        parameter_name: parameterName,
        parameter_lookup: parameterLookup
      });

      const data = response.data;
      setLookupOptions(data.options || []);
    } catch (error) {
      console.error('Error loading parameter lookup options:', error);
      setLookupError(error.message);
    } finally {
      setLookupLoading(false);
    }
  };

  // Filter lookup options based on search
  const filteredLookupOptions = lookupOptions.filter(option =>
    option.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
    option.value.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="w-full">
      {/* Tab Headers */}
      <div className="flex border-b border-gray-200 mb-4">
        <button
          onClick={() => setActiveTab('variables')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'variables'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
          }`}
        >
          <div className="flex items-center gap-2">
            <VariableIcon className="w-4 h-4" />
            Variables
          </div>
        </button>

        {hasLookup && (
          <button
            onClick={() => setActiveTab('lookup')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'lookup'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <div className="flex items-center gap-2">
              <ListBulletIcon className="w-4 h-4" />
              Lookup
            </div>
          </button>
        )}
      </div>

      {/* Tab Content */}
      <div className="w-full">
        {activeTab === 'variables' && (
          <NestedVariableSelector
            value={value}
            onChange={onVariableSelect}
            availableVariables={availableVariables}
            placeholder="Select a variable..."
            mode={mode}
            allowManualInput={false}
            inline={true}
          />
        )}

        {activeTab === 'lookup' && hasLookup && (
          <div className="w-full">
            {/* Search Input */}
            <div className="mb-3">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search options..."
                className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                autoFocus
              />
            </div>

            {/* Lookup Options List */}
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <div className="overflow-y-auto max-h-96 bg-white">
                {lookupLoading && (
                  <div className="flex items-center justify-center p-8 text-gray-500">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                    <span className="ml-3">Loading options...</span>
                  </div>
                )}

                {lookupError && (
                  <div className="p-4 text-red-600 bg-red-50 text-center">
                    <p className="font-medium">Error loading options</p>
                    <p className="text-sm mt-1">{lookupError}</p>
                  </div>
                )}

                {!lookupLoading && !lookupError && filteredLookupOptions.length === 0 && (
                  <div className="px-4 py-12 text-center">
                    <div className="text-sm text-gray-500 mb-2">
                      {searchTerm ? `No options match "${searchTerm}"` : 'No options available'}
                    </div>
                  </div>
                )}

                {!lookupLoading && !lookupError && filteredLookupOptions.length > 0 && (
                  <div className="divide-y divide-gray-200">
                    {filteredLookupOptions.map((option, index) => (
                      <div
                        key={index}
                        onClick={() => onLookupSelect(option.value, option.label)}
                        className="px-4 py-3 hover:bg-blue-50 cursor-pointer transition-colors"
                      >
                        <div className="font-medium text-sm text-gray-900">{option.label}</div>
                        {option.value !== option.label && (
                          <div className="text-xs text-gray-500 mt-0.5 font-mono">{option.value}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ParameterInput;