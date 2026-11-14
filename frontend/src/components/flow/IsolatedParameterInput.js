import React, { useState, useEffect, useRef } from 'react';
import {
  DocumentTextIcon,
  CodeBracketIcon,
  ListBulletIcon,
  CubeIcon,
  PlusIcon,
  TrashIcon,
  EllipsisVerticalIcon,
  CheckIcon,
  XMarkIcon,
  ArrowsPointingOutIcon,
  PhotoIcon,
  DocumentIcon,
} from '@heroicons/react/24/outline';
import { DataTypes, getDefaultValue, validateValue } from '../../utils/dataTypeUtils';
import Matrix2DArrayInput from './Matrix2DArrayInput';
import NestedJsonInput from './NestedJsonInput';
import ArrayOfObjectsInput from './ArrayOfObjectsInput';
import TabularArrayInput from './TabularArrayInput';
import WysiwygHtmlEditor from '../common/WysiwygHtmlEditor';


// Full-view file preview dialog (global, event-driven)
const FilePreviewDialog = () => {
  const [file, setFile] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const handler = (e) => {
      setFile(e.detail.file);
      setOpen(true);
    };
    window.addEventListener('ioflow-preview-file', handler);
    return () => window.removeEventListener('ioflow-preview-file', handler);
  }, []);

  // Close on Escape key
  useEffect(() => {
    if (!open) return;
    const handleKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open]);

  if (!open || !file) return null;

  const dataUrl = file.data ? `data:${file.type};base64,${file.data}` : null;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black bg-opacity-70" onClick={() => setOpen(false)}>
      <div className="relative max-w-[90vw] max-h-[90vh] bg-white rounded-lg shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
          <div className="flex items-center min-w-0">
            <span className="text-sm font-medium text-gray-700 truncate">{file.name}</span>
            <span className="text-xs text-gray-400 ml-2 flex-shrink-0">({(file.size / 1024).toFixed(1)} KB)</span>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="p-1 rounded-full hover:bg-gray-200 ml-3 flex-shrink-0"
          >
            <XMarkIcon className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        {/* Content */}
        <div className="flex items-center justify-center p-4 overflow-auto" style={{ maxHeight: 'calc(90vh - 48px)' }}>
          {file.type.startsWith('image/') && dataUrl ? (
            <img src={dataUrl} alt={file.name} className="max-w-full max-h-[80vh] object-contain" />
          ) : file.type.startsWith('video/') && dataUrl ? (
            <video src={dataUrl} controls autoPlay className="max-w-full max-h-[80vh]" />
          ) : file.type === 'application/pdf' && dataUrl ? (
            <iframe src={dataUrl} title={file.name} className="w-[80vw] h-[80vh] border-0" />
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-gray-500">
              <DocumentIcon className="w-16 h-16 mb-3" />
              <p className="text-lg font-medium">{file.name}</p>
              <p className="text-sm text-gray-400 mt-1">Preview not available for this file type</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// Simple Object Editor
const ObjectEditor = ({ value = {}, onChange }) => {
  // Ensure we have a proper object
  const getObj = () => {
    if (typeof value === 'object' && !Array.isArray(value) && value !== null) {
      return value;
    }
    if (typeof value === 'string') {
      try {
        const parsed = JSON.parse(value);
        return typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
      } catch {
        return {};
      }
    }
    return {};
  };
  
  const obj = getObj();
  
  // Create stable identifiers for each entry
  const [entryIds, setEntryIds] = useState({});
  const [editingKeys, setEditingKeys] = useState({});
  
  // Initialize entry IDs for existing keys
  useEffect(() => {
    const newIds = {};
    Object.keys(obj).forEach((key) => {
      if (!entryIds[key]) {
        newIds[key] = `entry_${Date.now()}_${Math.random()}`;
      }
    });
    if (Object.keys(newIds).length > 0) {
      setEntryIds(prev => ({ ...prev, ...newIds }));
    }
  }, [obj]);
  
  const addProperty = () => {
    const key = `key${Object.keys(obj).length + 1}`;
    const entryId = `entry_${Date.now()}_${Math.random()}`;
    setEntryIds(prev => ({ ...prev, [key]: entryId }));
    onChange({ ...obj, [key]: '' });
  };
  
  const handleKeyChange = (oldKey, newKey) => {
    setEditingKeys(prev => ({ ...prev, [oldKey]: newKey }));
  };
  
  const commitKeyChange = (oldKey) => {
    const newKey = editingKeys[oldKey];
    if (newKey && newKey !== oldKey) {
      const newObj = {};
      Object.entries(obj).forEach(([k, v]) => {
        if (k === oldKey) {
          newObj[newKey] = v;
        } else {
          newObj[k] = v;
        }
      });
      
      // Update entry IDs mapping
      setEntryIds(prev => {
        const updated = { ...prev };
        updated[newKey] = updated[oldKey];
        delete updated[oldKey];
        return updated;
      });
      
      // Clear editing state
      setEditingKeys(prev => {
        const updated = { ...prev };
        delete updated[oldKey];
        return updated;
      });
      
      onChange(newObj);
    }
  };
  
  const updateValue = (key, value) => {
    onChange({ ...obj, [key]: value });
  };
  
  const removeProperty = (key) => {
    const newObj = { ...obj };
    delete newObj[key];
    
    // Clean up entry IDs
    setEntryIds(prev => {
      const updated = { ...prev };
      delete updated[key];
      return updated;
    });
    
    // Clean up editing keys if any
    setEditingKeys(prev => {
      const updated = { ...prev };
      delete updated[key];
      return updated;
    });
    
    onChange(newObj);
  };
  
  return (
    <div className="space-y-2">
      {Object.keys(obj).length > 0 ? (
        Object.entries(obj).map(([key, value]) => {
          const entryId = entryIds[key] || key;
          const editingKey = editingKeys[key] !== undefined ? editingKeys[key] : key;
          
          return (
            <div key={entryId} className="flex items-center space-x-2">
              <input
                type="text"
                value={editingKey}
                onChange={(e) => handleKeyChange(key, e.target.value)}
                onBlur={() => commitKeyChange(key)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault(); // Prevent form submission
                    e.stopPropagation(); // Stop event from bubbling
                    e.target.blur();
                  }
                }}
                className="w-24 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Key"
              />
              <span className="text-gray-500">:</span>
              <input
                type="text"
                value={typeof value === 'object' ? JSON.stringify(value) : String(value || '')}
                onChange={(e) => updateValue(key, e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault(); // Prevent form submission
                    e.stopPropagation(); // Stop event from bubbling
                  }
                }}
                className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="Value"
              />
              <button
                type="button"
                onClick={() => removeProperty(key)}
                className="p-1 text-red-500 hover:text-red-700"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
          );
        })
      ) : (
        <p className="text-xs text-gray-500 italic">No properties. Click "Add Property" to start.</p>
      )}
      <button
        type="button"
        onClick={addProperty}
        className="flex items-center px-3 py-1 text-sm text-blue-600 border border-dashed border-blue-300 rounded hover:bg-blue-50"
      >
        <PlusIcon className="w-4 h-4 mr-1" />
        Add Property
      </button>
    </div>
  );
};

// This component is completely isolated and manages its own state
const IsolatedParameterInput = ({ variable, initialValue, onValueChange, inputModeOverride }) => {
  // Get the default value properly
  const getInitialValue = () => {
    // Don't use initialValue if it's an empty string - let default value take precedence
    if (initialValue !== undefined && initialValue !== null && initialValue !== '') {
      return initialValue;
    }
    
    if (variable.defaultValue !== undefined && variable.defaultValue !== null && variable.defaultValue !== '') {
      try {
        if ((variable.dataType === 'json' || variable.dataType === 'array' || 
             variable.dataType === DataTypes.JSON || variable.dataType === DataTypes.ARRAY || 
             variable.dataType === DataTypes.OBJECT) && 
            typeof variable.defaultValue === 'string') {
          const parsed = JSON.parse(variable.defaultValue);
          return parsed;
        }
        return variable.defaultValue;
      } catch (e) {
        // If parsing fails, check if it's an array represented as string items
        if (variable.dataType === 'array' || variable.dataType === DataTypes.ARRAY) {
          // Try to parse as a simple comma-separated list
          const items = variable.defaultValue.split(',').map(item => item.trim());
          if (items.length > 0 && items[0] !== '') {
            return items;
          }
        }
        return variable.defaultValue;
      }
    }
    return getDefaultValue(variable.dataType);
  };
  
  const [localValue, setLocalValue] = useState(getInitialValue);
  const [inputMode, setInputMode] = useState(() => {
    // Use override if provided
    if (inputModeOverride) return inputModeOverride;
    // Start with visual mode for complex types
    if (['array', 'object', 'json', DataTypes.ARRAY, DataTypes.OBJECT, DataTypes.JSON].includes(variable.dataType)) {
      return 'visual';
    }
    return 'form';
  });
  const [parseError, setParseError] = useState('');
  const timeoutRef = useRef(null);
  const hasInitialized = useRef(false);

  // Update inputMode when override changes
  useEffect(() => {
    if (inputModeOverride) {
      setInputMode(inputModeOverride);
    }
  }, [inputModeOverride]);

  // Initialize value once
  useEffect(() => {
    if (!hasInitialized.current) {
      const initVal = getInitialValue();
      setLocalValue(initVal);
      // Notify parent of initial value
      if (initVal !== undefined && initVal !== null && 
          (Array.isArray(initVal) ? initVal.length > 0 : initVal !== '')) {
        setTimeout(() => {
          onValueChange(variable.name, initVal);
        }, 100);
      }
      hasInitialized.current = true;
    }
  }, []);

  // Only update parent after user stops typing
  const notifyParent = (value) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = setTimeout(() => {
      onValueChange(variable.name, value);
    }, 800);
  };

  // Immediately notify parent without debounce (for blur/submit events)
  const notifyParentImmediate = (value) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    onValueChange(variable.name, value);
  };

  const handleTextChange = (e) => {
    const text = e.target.value;
    setLocalValue(text);
    
    // Try to parse and validate
    try {
      let parsedValue = text;
      
      if (variable.dataType === 'array' || variable.dataType === DataTypes.ARRAY) {
        parsedValue = JSON.parse(text);
        if (!Array.isArray(parsedValue)) throw new Error('Must be an array');
      } else if (variable.dataType === 'object' || variable.dataType === 'json' || 
                 variable.dataType === DataTypes.OBJECT || variable.dataType === DataTypes.JSON) {
        parsedValue = JSON.parse(text);
        if (typeof parsedValue !== 'object' || Array.isArray(parsedValue)) {
          throw new Error('Must be an object');
        }
      } else if (variable.dataType === 'number' || variable.dataType === DataTypes.NUMBER) {
        parsedValue = parseFloat(text);
        if (isNaN(parsedValue)) throw new Error('Must be a number');
      } else if (variable.dataType === 'boolean' || variable.dataType === DataTypes.BOOLEAN) {
        if (text.toLowerCase() !== 'true' && text.toLowerCase() !== 'false') {
          throw new Error('Must be true or false');
        }
        parsedValue = text.toLowerCase() === 'true';
      }
      
      setParseError('');
      notifyParent(parsedValue);
    } catch (e) {
      setParseError(e.message);
    }
  };

  const handleSimpleChange = (e) => {
    const value = e.target.value;
    setLocalValue(value);
    notifyParent(value);
  };

  // Handle blur to immediately save value
  const handleBlur = () => {
    notifyParentImmediate(localValue);
  };

  // Cleanup
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  // Determine if we need mode selector (for complex types)
  const needsModeSelector = ['array', 'object', 'json', DataTypes.ARRAY, DataTypes.OBJECT, DataTypes.JSON]
    .includes(variable.dataType);

  // Helper to get placeholder
  const getPlaceholder = (type) => {
    switch (type) {
      case 'array':
      case DataTypes.ARRAY:
        return '["item1", "item2"]';
      case 'object':
      case 'json':
      case DataTypes.OBJECT:
      case DataTypes.JSON:
        return '{"key": "value"}';
      case 'boolean':
      case DataTypes.BOOLEAN:
        return 'true or false';
      case 'number':
      case 'integer':
      case DataTypes.NUMBER:
      case DataTypes.INTEGER:
        return '123';
      default:
        return 'Enter value';
    }
  };

  const renderInput = () => {
    // Check if this is a JSON/Object with defined nested properties
    const isJsonWithProperties = (variable.dataType === 'json' || variable.dataType === 'object' ||
                                  variable.dataType === DataTypes.JSON || variable.dataType === DataTypes.OBJECT) &&
                                 variable.properties && variable.properties.length > 0;

    if (isJsonWithProperties && inputMode === 'visual') {
      // Use NestedJsonInput for JSON/objects with defined properties
      return (
        <div className="border border-gray-200 rounded-md p-3 bg-gray-50">
          <NestedJsonInput
            variable={variable}
            value={localValue}
            onChange={(name, val) => {
              setLocalValue(val);
              notifyParent(val);
            }}
          />
        </div>
      );
    }

    // For complex types
    if (needsModeSelector) {
      if (inputMode === 'text' || inputMode === 'json') {
        return (
          <div>
            <textarea
              value={typeof localValue === 'object' ? JSON.stringify(localValue, null, 2) : localValue}
              onChange={handleTextChange}
              rows={inputMode === 'json' ? 10 : 6}
              className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
                parseError ? 'border-red-300' : 'border-gray-300'
              } focus:outline-none focus:ring-1 focus:ring-blue-500`}
              placeholder={variable.dataType === 'array' ? '["item1", "item2"]' : '{"key": "value"}'}
            />
            {parseError && <p className="mt-1 text-xs text-red-600">{parseError}</p>}
          </div>
        );
      } else if (inputMode === 'visual') {
        // For visual mode, we'll render a simple editor
        return (
          <div className="border border-gray-200 rounded-md p-3 bg-gray-50">
            {(variable.dataType === 'array' || variable.dataType === DataTypes.ARRAY) &&
             (variable.itemType === 'object' || variable.itemType === DataTypes.OBJECT) &&
             variable.properties && variable.properties.length > 0 ? (
              // Array of objects with defined schema - check if tabular UI control is set
              variable.uiControl === 'tabular' ? (
                // Use TabularArrayInput for tabular view
                <TabularArrayInput
                  value={localValue || []}
                  onChange={(val) => {
                    setLocalValue(val);
                    notifyParent(val);
                  }}
                  properties={variable.properties}
                  minItems={variable.validation?.minItems}
                  maxItems={variable.validation?.maxItems}
                />
              ) : (
                // Use ArrayOfObjectsInput for regular view with Add Item button
                <ArrayOfObjectsInput
                  value={localValue || []}
                  onChange={(val) => {
                    setLocalValue(val);
                    notifyParent(val);
                  }}
                  properties={variable.properties}
                  itemType={variable.itemType}
                />
              )
            ) : variable.dataType === 'array' || variable.dataType === DataTypes.ARRAY ? (
              // Simple array without schema
              <Matrix2DArrayInput
                value={localValue}
                onChange={(val) => {
                  setLocalValue(val);
                  notifyParent(val);
                }}
                itemType={variable.itemType || 'string'}
                minItems={variable.validation?.minItems}
                maxItems={variable.validation?.maxItems}
              />
            ) : (
              <ObjectEditor
                value={localValue}
                onChange={(val) => {
                  setLocalValue(val);
                  notifyParent(val);
                }}
              />
            )}
          </div>
        );
      }
    }

    // Special handling for JSON UI control on any data type
    if (variable.uiControl === 'json') {
      return (
        <div>
          <div className="mb-2">
            <div className="flex space-x-2 text-xs">
              <button
                type="button"
                onClick={() => setInputMode(inputMode === 'visual' ? 'json' : 'visual')}
                className={`px-2 py-1 rounded ${inputMode === 'visual' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}
              >
                {inputMode === 'visual' ? 'Visual' : 'JSON'}
              </button>
            </div>
          </div>
          {inputMode === 'visual' ? (
            <div className="border border-gray-200 rounded-md p-3 bg-gray-50">
              <ObjectEditor 
                value={localValue} 
                onChange={(val) => {
                  setLocalValue(val);
                  notifyParent(val);
                }} 
              />
            </div>
          ) : (
            <div>
              <textarea
                value={typeof localValue === 'object' ? JSON.stringify(localValue, null, 2) : localValue || ''}
                onChange={handleTextChange}
                rows={10}
                className={`w-full px-3 py-2 border rounded-md font-mono text-sm ${
                  parseError ? 'border-red-300' : 'border-gray-300'
                } focus:outline-none focus:ring-1 focus:ring-blue-500`}
                placeholder='{"key": "value"}'
              />
              {parseError && <p className="mt-1 text-xs text-red-600">{parseError}</p>}
            </div>
          )}
        </div>
      );
    }

    // For simple types, always use form mode (no text mode option)
    switch (variable.dataType) {
      case 'boolean':
      case DataTypes.BOOLEAN:
        // Check UI control for boolean types
        if (variable.uiControl === 'checkbox') {
          return (
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                checked={localValue === true || localValue === 'true'}
                onChange={(e) => {
                  const val = e.target.checked;
                  setLocalValue(val);
                  notifyParent(val);
                }}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-sm text-gray-900">
                {variable.displayName || variable.name}
              </span>
            </div>
          );
        }
        // Default to toggle for boolean
        return (
          <div className="flex items-center">
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={localValue === true || localValue === 'true'}
                onChange={(e) => {
                  const val = e.target.checked;
                  setLocalValue(val);
                  notifyParent(val);
                }}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
              <span className="ml-3 text-sm font-medium text-gray-900">{localValue ? 'On' : 'Off'}</span>
            </label>
          </div>
        );

      case 'number':
      case 'integer':
      case DataTypes.NUMBER:
      case DataTypes.INTEGER:
        // Check UI control for number types
        if (variable.uiControl === 'range') {
          const min = variable.validation?.min || 0;
          const max = variable.validation?.max || 100;
          return (
            <div className="space-y-2">
              <input
                type="range"
                min={min}
                max={max}
                value={localValue || min}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setLocalValue(val);
                  notifyParent(val);
                }}
                className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-gray-500">
                <span>{min}</span>
                <span className="font-medium">{localValue || min}</span>
                <span>{max}</span>
              </div>
            </div>
          );
        }
        // Default number input
        return (
          <input
            type="number"
            name={variable.name}
            value={localValue || ''}
            onChange={(e) => {
              const val = e.target.value;
              setLocalValue(val);
              if (val === '') {
                notifyParent('');
              } else {
                const num = parseFloat(val);
                if (!isNaN(num)) {
                  notifyParent(num);
                }
              }
            }}
            onBlur={() => {
              if (localValue === '') {
                notifyParentImmediate('');
              } else {
                const num = parseFloat(localValue);
                if (!isNaN(num)) {
                  notifyParentImmediate(num);
                }
              }
            }}
            className="w-full px-3 py-2 text-right border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Enter number"
          />
        );

      case 'file':
      case DataTypes.FILE:
        const isMultiple = variable.uiControl === 'file-multiple' || variable.uiControl === 'file-preview-multiple';
        const isPreview = variable.uiControl === 'file-preview' || variable.uiControl === 'file-preview-multiple';
        const accept = variable.validation?.accept || '';

        // Helper to build data URL from file object
        const getDataUrl = (file) => {
          if (!file || !file.data) return null;
          return `data:${file.type};base64,${file.data}`;
        };

        // Handle file selection
        const handleFileSelect = async (e) => {
          const files = Array.from(e.target.files);
          if (files.length === 0) {
            if (!isMultiple) {
              setLocalValue(null);
              notifyParent(null);
            }
            return;
          }

          const filePromises = files.map(file => {
            return new Promise((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => {
                resolve({
                  name: file.name,
                  type: file.type,
                  size: file.size,
                  data: reader.result.split(',')[1],
                  lastModified: file.lastModified
                });
              };
              reader.onerror = reject;
              reader.readAsDataURL(file);
            });
          });

          try {
            const fileData = await Promise.all(filePromises);
            if (isMultiple) {
              const existing = Array.isArray(localValue) ? localValue : [];
              const combined = [...existing, ...fileData];
              setLocalValue(combined);
              notifyParent(combined);
            } else {
              setLocalValue(fileData[0]);
              notifyParent(fileData[0]);
            }
          } catch (error) {
            console.error('Error reading files:', error);
          }
          // Reset file input so same file can be re-selected
          if (e.target && e.target.type === 'file') {
            e.target.value = '';
          }
        };

        // Remove a file from multiple upload
        const removeFile = (index) => {
          if (isMultiple && Array.isArray(localValue)) {
            const updated = localValue.filter((_, i) => i !== index);
            setLocalValue(updated.length > 0 ? updated : null);
            notifyParent(updated.length > 0 ? updated : null);
          } else {
            setLocalValue(null);
            notifyParent(null);
          }
        };

        // Render thumbnail for a file
        const renderThumbnail = (file, index = 0) => {
          const dataUrl = getDataUrl(file);
          return (
            <div
              key={index}
              className="relative group border border-gray-200 rounded-lg overflow-hidden bg-gray-50"
              style={{ width: '140px', height: '140px' }}
            >
              {/* Preview content */}
              <div
                className="w-full h-full flex items-center justify-center cursor-pointer"
                onClick={() => {
                  const event = new CustomEvent('ioflow-preview-file', { detail: { file } });
                  window.dispatchEvent(event);
                }}
              >
                {file.type.startsWith('image/') && dataUrl ? (
                  <img
                    src={dataUrl}
                    alt={file.name}
                    className="w-full h-full object-cover"
                  />
                ) : file.type.startsWith('video/') && dataUrl ? (
                  <video
                    src={dataUrl}
                    className="w-full h-full object-cover"
                    muted
                  />
                ) : file.type === 'application/pdf' ? (
                  <div className="flex flex-col items-center justify-center text-red-500">
                    <DocumentIcon className="w-10 h-10" />
                    <span className="text-xs mt-1 font-medium">PDF</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center text-gray-400">
                    <DocumentIcon className="w-10 h-10" />
                    <span className="text-xs mt-1 text-gray-500 font-medium">
                      {file.name.split('.').pop()?.toUpperCase() || 'FILE'}
                    </span>
                  </div>
                )}
              </div>
              {/* Overlay with actions */}
              <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-40 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
                <button
                  type="button"
                  onClick={() => {
                    const event = new CustomEvent('ioflow-preview-file', { detail: { file } });
                    window.dispatchEvent(event);
                  }}
                  className="p-1.5 bg-white rounded-full shadow-md mr-1 hover:bg-gray-100"
                  title="View full size"
                >
                  <ArrowsPointingOutIcon className="w-4 h-4 text-gray-700" />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(index);
                  }}
                  className="p-1.5 bg-white rounded-full shadow-md hover:bg-red-50"
                  title="Remove file"
                >
                  <TrashIcon className="w-4 h-4 text-red-500" />
                </button>
              </div>
              {/* File name */}
              <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-60 px-2 py-1">
                <p className="text-white text-[10px] truncate" title={file.name}>{file.name}</p>
              </div>
            </div>
          );
        };

        // Handle drag-drop for preview upload
        const handleDragOver = (e) => {
          e.preventDefault();
          e.stopPropagation();
        };

        const handleDrop = (e) => {
          e.preventDefault();
          e.stopPropagation();
          const droppedFiles = e.dataTransfer?.files;
          if (droppedFiles && droppedFiles.length > 0) {
            // Reuse the same handler by creating a synthetic event-like object
            handleFileSelect({ target: { files: droppedFiles }, preventDefault: () => {} });
          }
        };

        // Preview upload UI
        if (isPreview) {
          return (
            <div
              className="space-y-3"
              onDragOver={handleDragOver}
              onDrop={handleDrop}
            >
              {/* Thumbnails grid */}
              {localValue && (
                <div className="flex flex-wrap gap-3">
                  {isMultiple && Array.isArray(localValue) ? (
                    localValue.map((file, idx) => renderThumbnail(file, idx))
                  ) : localValue && typeof localValue === 'object' && localValue.name ? (
                    renderThumbnail(localValue, 0)
                  ) : null}
                </div>
              )}
              {/* Upload area */}
              {(isMultiple || !localValue) && (
                <label className="flex flex-col items-center justify-center w-full h-28 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors">
                  <PhotoIcon className="w-8 h-8 text-gray-400 mb-1" />
                  <span className="text-sm text-gray-500">
                    {isMultiple ? 'Click to add files' : 'Click or drag files here'}
                  </span>
                  {accept && (
                    <span className="text-xs text-gray-400 mt-0.5">{accept}</span>
                  )}
                  <input
                    type="file"
                    accept={accept}
                    multiple={isMultiple}
                    onChange={handleFileSelect}
                    className="hidden"
                  />
                </label>
              )}
            </div>
          );
        }

        // Standard file upload UI (unchanged)
        return (
          <div className="space-y-2">
            <input
              type="file"
              accept={accept}
              multiple={isMultiple}
              onChange={handleFileSelect}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {localValue && (
              <div className="text-sm text-gray-600">
                {isMultiple && Array.isArray(localValue) ? (
                  <div>
                    <p>{localValue.length} file(s) selected:</p>
                    <ul className="list-disc list-inside ml-2">
                      {localValue.map((file, idx) => (
                        <li key={idx}>{file.name} ({(file.size / 1024).toFixed(2)} KB)</li>
                      ))}
                    </ul>
                  </div>
                ) : localValue && typeof localValue === 'object' && localValue.name ? (
                  <p>Selected: {localValue.name} ({(localValue.size / 1024).toFixed(2)} KB)</p>
                ) : null}
              </div>
            )}
          </div>
        );

      default:
        // Handle string types with various UI controls
        switch (variable.uiControl) {
          case 'textarea':
            return (
              <textarea
                name={variable.name}
                value={localValue || ''}
                onChange={handleSimpleChange}
                onBlur={handleBlur}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder={variable.description || 'Enter text...'}
              />
            );
          
          case 'code':
            return (
              <textarea
                name={variable.name}
                value={localValue || ''}
                onChange={handleSimpleChange}
                onBlur={handleBlur}
                rows={8}
                className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder={variable.description || 'Enter code...'}
              />
            );
          
          case 'html':
            return (
              <div>
                <div className="mb-2">
                  <div className="flex space-x-2 text-xs">
                    <button
                      type="button"
                      onClick={() => setInputMode(inputMode === 'preview' ? 'code' : 'preview')}
                      className={`px-2 py-1 rounded ${inputMode === 'preview' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-700'}`}
                    >
                      {inputMode === 'preview' ? 'Code' : 'Preview'}
                    </button>
                  </div>
                </div>
                {inputMode === 'preview' ? (
                  <div className="border border-gray-300 rounded-md p-3 min-h-[100px] max-h-[300px] overflow-auto bg-white">
                    <div dangerouslySetInnerHTML={{ __html: localValue || '' }} />
                  </div>
                ) : (
                  <textarea
                    value={localValue || ''}
                    onChange={handleSimpleChange}
                    rows={8}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                    placeholder="Enter HTML content..."
                  />
                )}
              </div>
            );
          
          case 'wysiwyg':
            return (
              <WysiwygHtmlEditor
                value={localValue || ''}
                onChange={(value) => {
                  setLocalValue(value);
                  notifyParent(value);
                }}
                placeholder={variable.description || 'Enter rich text content...'}
                height={200}
              />
            );
          
          case 'email':
            return (
              <input
                type="email"
                name={variable.name}
                value={localValue || ''}
                onChange={handleSimpleChange}
                onBlur={handleBlur}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="example@domain.com"
              />
            );
          
          case 'url':
            return (
              <input
                type="url"
                name={variable.name}
                value={localValue || ''}
                onChange={handleSimpleChange}
                onBlur={handleBlur}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="https://example.com"
              />
            );
          
          case 'date':
            return (
              <input
                type="date"
                name={variable.name}
                value={localValue || ''}
                onChange={handleSimpleChange}
                onBlur={handleBlur}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            );
          
          case 'datetime':
            return (
              <input
                type="datetime-local"
                name={variable.name}
                value={localValue || ''}
                onChange={handleSimpleChange}
                onBlur={handleBlur}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            );
          
          case 'tags':
            const tags = Array.isArray(localValue) ? localValue : (localValue ? localValue.split(',').map(t => t.trim()) : []);
            return (
              <div className="space-y-2">
                <input
                  type="text"
                  placeholder="Type and press Enter to add tags"
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      e.stopPropagation(); // Stop event from bubbling
                      const newTag = e.target.value.trim();
                      if (newTag && !tags.includes(newTag)) {
                        const newTags = [...tags, newTag];
                        setLocalValue(newTags);
                        notifyParent(newTags);
                        e.target.value = '';
                      }
                    }
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                {tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {tags.map((tag, index) => (
                      <span
                        key={index}
                        className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800"
                      >
                        {tag}
                        <button
                          type="button"
                          onClick={() => {
                            const newTags = tags.filter((_, i) => i !== index);
                            setLocalValue(newTags);
                            notifyParent(newTags);
                          }}
                          className="ml-1 text-blue-600 hover:text-blue-800"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          
          default:
            return (
              <input
                type="text"
                name={variable.name}
                value={localValue || ''}
                onChange={handleSimpleChange}
                onBlur={handleBlur}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder={variable.description || 'Enter value'}
              />
            );
        }
    }
  };

  return renderInput();
};

// Wrapper component that prevents re-renders
const IsolatedField = React.memo(({ variable, value, onChange }) => {
  // Don't pass empty string as initial value - let the component use defaults
  const initialValue = (value !== undefined && value !== '') ? value : undefined;
  const [inputMode, setInputMode] = useState('visual');
  const [showModeMenu, setShowModeMenu] = useState(false);
  const menuRef = useRef(null);

  // Determine if we need mode selector
  const needsModeSelector = ['array', 'object', 'json', DataTypes.ARRAY, DataTypes.OBJECT, DataTypes.JSON]
    .includes(variable.dataType);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setShowModeMenu(false);
      }
    };

    if (showModeMenu) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showModeMenu]);

  const getModeIcon = (mode) => {
    switch (mode) {
      case 'visual':
        return variable.dataType === 'array' || variable.dataType === DataTypes.ARRAY ?
          <ListBulletIcon className="w-4 h-4" /> :
          <CubeIcon className="w-4 h-4" />;
      case 'json':
        return <CodeBracketIcon className="w-4 h-4" />;
      case 'text':
        return <DocumentTextIcon className="w-4 h-4" />;
      default:
        return null;
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm font-medium text-gray-700">
          {variable.displayName || variable.name}
          {variable.required && <span className="text-red-500 ml-1">*</span>}
        </label>
        {needsModeSelector && (
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setShowModeMenu(!showModeMenu)}
              className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
              title="Input mode options"
            >
              <EllipsisVerticalIcon className="w-4 h-4" />
            </button>
            {showModeMenu && (
              <div className="absolute right-0 mt-1 w-32 bg-white border border-gray-200 rounded-md shadow-lg z-10">
                <div className="py-1">
                  <button
                    type="button"
                    onClick={() => {
                      setInputMode('visual');
                      setShowModeMenu(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 flex items-center justify-between ${
                      inputMode === 'visual' ? 'text-blue-600' : 'text-gray-700'
                    }`}
                  >
                    <span className="flex items-center">
                      {getModeIcon('visual')}
                      <span className="ml-2">Visual</span>
                    </span>
                    {inputMode === 'visual' && <CheckIcon className="w-3 h-3" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setInputMode('json');
                      setShowModeMenu(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 flex items-center justify-between ${
                      inputMode === 'json' ? 'text-blue-600' : 'text-gray-700'
                    }`}
                  >
                    <span className="flex items-center">
                      <CodeBracketIcon className="w-3 h-3" />
                      <span className="ml-2">JSON</span>
                    </span>
                    {inputMode === 'json' && <CheckIcon className="w-3 h-3" />}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setInputMode('text');
                      setShowModeMenu(false);
                    }}
                    className={`w-full text-left px-3 py-2 text-sm hover:bg-gray-100 flex items-center justify-between ${
                      inputMode === 'text' ? 'text-blue-600' : 'text-gray-700'
                    }`}
                  >
                    <span className="flex items-center">
                      <DocumentTextIcon className="w-3 h-3" />
                      <span className="ml-2">Text</span>
                    </span>
                    {inputMode === 'text' && <CheckIcon className="w-3 h-3" />}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      <IsolatedParameterInput
        key={`${variable.name}-${variable.dataType}`} // Key based on name and type
        variable={variable}
        initialValue={initialValue}
        onValueChange={onChange}
        inputModeOverride={inputMode}
      />
      {variable.description && (
        <p className="mt-1 text-xs text-gray-500">{variable.description}</p>
      )}
    </div>
  );
}, (prevProps, nextProps) => {
  // Only re-render if variable definition changes
  return prevProps.variable.name === nextProps.variable.name &&
         prevProps.variable.dataType === nextProps.variable.dataType &&
         prevProps.variable.defaultValue === nextProps.variable.defaultValue;
});

IsolatedField.displayName = 'IsolatedField';

export { FilePreviewDialog };
export default IsolatedField;