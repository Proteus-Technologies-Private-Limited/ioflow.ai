import React, { useState, useEffect } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  DocumentTextIcon,
  CodeBracketIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline';
import { DataTypes } from '../../utils/dataTypeUtils';

const ManualTriggerConfig = ({
  variables = [],
  onVariablesChange,
  mode = 'edit' // 'edit' or 'view'
}) => {
  const [localVariables, setLocalVariables] = useState(Array.isArray(variables) ? variables : []);
  const [activeTab, setActiveTab] = useState('form');
  const [expandedVariables, setExpandedVariables] = useState({});

  // Data type options
  const dataTypes = [
    { value: DataTypes.STRING, label: 'String' },
    { value: DataTypes.NUMBER, label: 'Number' },
    { value: DataTypes.INTEGER, label: 'Integer' },
    { value: DataTypes.BOOLEAN, label: 'Boolean' },
    { value: DataTypes.JSON, label: 'JSON Object' },
    { value: DataTypes.ARRAY, label: 'Array' },
    { value: DataTypes.DATE, label: 'Date' },
    { value: DataTypes.DATETIME, label: 'Date Time' },
    { value: DataTypes.EMAIL, label: 'Email' },
    { value: DataTypes.URL, label: 'URL' },
    { value: DataTypes.FILE, label: 'File' },
  ];

  // UI control options based on data type
  const getUIControls = (dataType, variable = null) => {
    switch (dataType) {
      case 'string':
        return ['text', 'textarea', 'email', 'url', 'html', 'wysiwyg', 'code'];
      case 'number':
        return ['number', 'range'];
      case 'boolean':
        return ['checkbox', 'toggle'];
      case 'json':
        return ['json', 'code', 'textarea'];
      case 'xml':
        return ['code', 'textarea'];
      case 'array':
      case DataTypes.ARRAY:
        // Add 'tabular' option only if itemType is 'object' and has properties
        const baseControls = ['visual', 'json', 'text'];

        // Debug log for development (uncomment if needed)
        // if (process.env.NODE_ENV === 'development' && variable) {
        //   console.log('[getUIControls] Checking tabular for:', {
        //     name: variable.name,
        //     itemType: variable.itemType,
        //     hasProperties: variable.properties?.length > 0,
        //     properties: variable.properties
        //   });
        // }

        if (variable &&
            (variable.itemType === 'object' || variable.itemType === DataTypes.OBJECT) &&
            variable.properties && variable.properties.length > 0) {
          // Check if any property is a nested array or object
          const hasNestedComplex = variable.properties.some(prop =>
            prop.dataType === 'array' || prop.dataType === DataTypes.ARRAY ||
            prop.dataType === 'json' || prop.dataType === DataTypes.JSON ||
            prop.dataType === 'object' || prop.dataType === DataTypes.OBJECT
          );
          if (!hasNestedComplex) {
            baseControls.push('tabular');
          }
        }
        return baseControls;
      case 'date':
        return ['date', 'datetime'];
      case 'file':
        return ['file', 'file-multiple', 'file-preview', 'file-preview-multiple'];
      default:
        return ['text'];
    }
  };

  // Get UI control label for display
  const getUIControlLabel = (uiControl) => {
    const labels = {
      'visual': 'Visual Editor',
      'text': 'Text Input',
      'textarea': 'Text Area',
      'tabular': 'Table View',
      'email': 'Email Input',
      'url': 'URL Input',
      'html': 'HTML Editor',
      'wysiwyg': 'WYSIWYG HTML Editor',
      'code': 'Code Editor',
      'number': 'Number Input',
      'range': 'Range Slider',
      'checkbox': 'Checkbox',
      'toggle': 'Toggle Switch',
      'json': 'JSON Editor',
      'tags': 'Tag Input',
      'date': 'Date Picker',
      'datetime': 'DateTime Picker',
      'file': 'File Upload',
      'file-multiple': 'Multiple File Upload',
      'file-preview': 'Preview Upload',
      'file-preview-multiple': 'Multiple Preview Upload'
    };
    return labels[uiControl] || uiControl;
  };

  // Get UI control description
  const getUIControlDescription = (uiControl) => {
    const descriptions = {
      'textarea': 'Multi-line text input for longer content',
      'email': 'Email input with validation and appropriate keyboard on mobile',
      'url': 'URL input with validation and appropriate keyboard on mobile',
      'html': 'HTML editor with preview mode toggle for rich text content',
      'wysiwyg': 'Visual HTML editor with toolbar for rich text formatting and HTML code view',
      'code': 'Code editor with monospace font for scripts and configuration',
      'range': 'Slider control for numeric values within a specific range',
      'checkbox': 'Simple checkbox for boolean values',
      'toggle': 'Toggle switch for boolean values with visual on/off states',
      'json': 'JSON editor with visual object editor and code modes',
      'tags': 'Tag input allowing users to add/remove tags by typing and pressing Enter',
      'date': 'Date picker for selecting calendar dates',
      'datetime': 'Date and time picker for scheduling and timestamps',
      'file': 'Single file upload with file type validation',
      'file-multiple': 'Multiple file upload with file type validation',
      'file-preview': 'Single file upload with large thumbnail preview',
      'file-preview-multiple': 'Multiple file upload with large thumbnail previews',
      'tabular': 'Table view with editable rows and columns for structured data'
    };
    return descriptions[uiControl] || 'Standard input control';
  };

  useEffect(() => {
    setLocalVariables(Array.isArray(variables) ? variables : []);
  }, [variables]);

  const addVariable = (parentId = null) => {
    if (parentId) {
      // Adding a nested field to a JSON object or array with object items
      const addFieldToVariable = (variables) => {
        return variables.map(v => {
          // Check if this is the variable we're adding properties to by ID
          if (v.id === parentId) {
            if (!v.properties) {
              v.properties = [];
            }
            const newField = {
              id: Date.now(),
              name: '',
              displayName: '',
              description: '',
              dataType: DataTypes.STRING,
              uiControl: 'text',
              required: false,
              defaultValue: '',
              validation: {},
              order: v.properties.length,
              properties: [], // For nested fields when dataType is 'json' or array with object items
              itemType: null, // For arrays
            };
            v.properties = [...v.properties, newField];
          } else if (v.properties && v.properties.length > 0) {
            // Recursively check nested properties
            v.properties = addFieldToVariable(v.properties);
          }
          return v;
        });
      };

      const updated = addFieldToVariable(localVariables);
      setLocalVariables(updated);
      onVariablesChange(updated);
    } else {
      // Adding a top-level variable
      const newVariable = {
        id: Date.now(),
        name: '',
        displayName: '',
        description: '',
        dataType: DataTypes.STRING,
        uiControl: 'text',
        required: false,
        defaultValue: '',
        validation: {},
        order: localVariables.length,
        properties: [], // For nested fields when dataType is 'json'
        itemType: null, // For arrays
      };
      const updated = [...localVariables, newVariable];
      setLocalVariables(updated);
      onVariablesChange(updated);
    }
  };

  const getVariablePath = (variable, parentPath = '') => {
    if (parentPath) {
      return `${parentPath}.${variable.name}`;
    }
    return variable.name;
  };

  // Helper function to convert variable name to display name
  const generateDisplayName = (name) => {
    if (!name) return '';

    // Split by underscore, capitalize each word, join with space
    return name
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  const updateVariable = (id, updates, parentPath = null) => {
    const updateNestedVariable = (variables) => {
      return variables.map(v => {
        if (v.id === id) {
          // Handle dataType changes for JSON objects
          if (updates.dataType && updates.dataType !== v.dataType) {
            if (updates.dataType === DataTypes.JSON) {
              // Initialize properties array for JSON objects
              updates.properties = [];
              // Set appropriate default UI control
              if (!getUIControls(updates.dataType).includes(v.uiControl)) {
                updates.uiControl = 'json';
              }
            } else if (updates.dataType === DataTypes.ARRAY) {
              // Initialize itemType for arrays
              updates.itemType = DataTypes.STRING;
              updates.properties = [];
              // Set appropriate default UI control for arrays
              updates.uiControl = 'visual';
            } else {
              // Clear properties for non-JSON types
              updates.properties = undefined;
              updates.itemType = undefined;
              // Set appropriate default UI control for the new type
              const availableControls = getUIControls(updates.dataType);
              if (!availableControls.includes(v.uiControl)) {
                updates.uiControl = availableControls[0] || 'text';
              }
            }
          }
          return { ...v, ...updates };
        }
        // Recursively check nested properties
        if (v.properties && v.properties.length > 0) {
          return {
            ...v,
            properties: updateNestedVariable(v.properties)
          };
        }
        return v;
      });
    };

    const updated = updateNestedVariable(localVariables);
    setLocalVariables(updated);
    onVariablesChange(updated);
  };

  const removeVariable = (id) => {
    const removeNestedVariable = (variables) => {
      return variables.filter(v => {
        if (v.id === id) {
          return false;
        }
        if (v.properties && v.properties.length > 0) {
          v.properties = removeNestedVariable(v.properties);
        }
        return true;
      });
    };

    const updated = removeNestedVariable(localVariables);
    // Reorder remaining variables
    updated.forEach((v, index) => {
      v.order = index;
      if (v.properties) {
        v.properties.forEach((p, idx) => {
          p.order = idx;
        });
      }
    });
    setLocalVariables(updated);
    onVariablesChange(updated);
  };

  const toggleVariableExpanded = (variableId) => {
    setExpandedVariables(prev => ({
      ...prev,
      [variableId]: !prev[variableId]
    }));
  };

  const moveVariable = (id, direction, parentVariables = null) => {
    // Helper function to move items within an array
    const moveInArray = (arr) => {
      const index = arr.findIndex(v => v.id === id);

      if (index === -1) {
        // Not found at this level, search in nested properties
        let found = false;
        const newArr = arr.map(v => {
          if (v.properties && v.properties.length > 0) {
            const updatedProperties = moveInArray(v.properties);
            if (updatedProperties !== v.properties) {
              found = true;
              return { ...v, properties: updatedProperties };
            }
          }
          return v;
        });
        return found ? newArr : arr;
      }

      // Found the item at this level
      if (
        (direction === 'up' && index === 0) ||
        (direction === 'down' && index === arr.length - 1)
      ) {
        return arr; // Can't move further
      }

      const newArr = [...arr];
      const newIndex = direction === 'up' ? index - 1 : index + 1;
      [newArr[index], newArr[newIndex]] = [newArr[newIndex], newArr[index]];

      // Update order
      newArr.forEach((v, i) => {
        v.order = i;
      });

      return newArr;
    };

    const newVariables = moveInArray([...localVariables]);
    if (newVariables !== localVariables) {
      setLocalVariables(newVariables);
      onVariablesChange(newVariables);
    }
  };

  const generateSchema = () => {
    const generateFieldSchema = (variable) => {
      const fieldSchema = {
        type: variable.dataType === 'json' ? 'object' : variable.dataType,
        description: variable.description || variable.displayName,
      };

      if (variable.dataType === DataTypes.JSON && variable.properties && variable.properties.length > 0) {
        // Generate nested schema for JSON objects
        fieldSchema.properties = {};
        fieldSchema.required = [];

        variable.properties.forEach(prop => {
          fieldSchema.properties[prop.name] = generateFieldSchema(prop);
          if (prop.required) {
            fieldSchema.required.push(prop.name);
          }
        });
      } else if (variable.dataType === DataTypes.ARRAY) {
        fieldSchema.type = 'array';
        if (variable.itemType === DataTypes.OBJECT && variable.properties && variable.properties.length > 0) {
          // Array of objects with defined schema
          const itemSchema = {
            type: 'object',
            properties: {},
            required: []
          };
          variable.properties.forEach(prop => {
            itemSchema.properties[prop.name] = generateFieldSchema(prop);
            if (prop.required) {
              itemSchema.required.push(prop.name);
            }
          });
          fieldSchema.items = itemSchema;
        } else if (variable.itemType) {
          // Simple typed array
          fieldSchema.items = { type: variable.itemType };
        }
      }

      if (variable.defaultValue) {
        fieldSchema.default = variable.defaultValue;
      }

      if (variable.validation) {
        if (variable.validation.minLength) fieldSchema.minLength = variable.validation.minLength;
        if (variable.validation.maxLength) fieldSchema.maxLength = variable.validation.maxLength;
        if (variable.validation.pattern) fieldSchema.pattern = variable.validation.pattern;
        if (variable.validation.min) fieldSchema.minimum = variable.validation.min;
        if (variable.validation.max) fieldSchema.maximum = variable.validation.max;
        if (variable.validation.minItems) fieldSchema.minItems = variable.validation.minItems;
        if (variable.validation.maxItems) fieldSchema.maxItems = variable.validation.maxItems;
      }

      return fieldSchema;
    };

    const schema = {
      type: 'object',
      properties: {},
      required: [],
    };

    (Array.isArray(localVariables) ? localVariables : []).forEach(variable => {
      schema.properties[variable.name] = generateFieldSchema(variable);

      if (variable.required) {
        schema.required.push(variable.name);
      }
    });

    return schema;
  };

  const renderNestedProperties = (properties, parentPath, depth = 1) => {
    if (!properties || properties.length === 0) return null;

    return (
      <div className={`ml-${Math.min(depth * 4, 12)} mt-3 space-y-2 border-l-2 border-blue-200 pl-3`}>
        {properties.map(prop => renderVariableEditor(prop, parentPath, depth, properties))}
      </div>
    );
  };

  const renderVariableEditor = (variable, parentPath = '', depth = 0, siblings = []) => {
    const variablePath = getVariablePath(variable, parentPath);
    const isJsonType = variable.dataType === DataTypes.JSON;
    const isArrayType = variable.dataType === DataTypes.ARRAY;
    const isObjectArray = isArrayType && variable.itemType === DataTypes.OBJECT;
    const canHaveProperties = isJsonType || isObjectArray;
    const isExpanded = expandedVariables[variable.id];

    // Determine position within siblings array for move buttons
    const siblingsList = siblings.length > 0 ? siblings : localVariables;
    const siblingIndex = siblingsList.findIndex(s => s.id === variable.id);
    const isFirstInList = siblingIndex === 0;
    const isLastInList = siblingIndex === siblingsList.length - 1;

    // Determine responsive classes based on depth and screen size
    const containerPadding = depth > 2 ? 'p-2 sm:p-3' : 'p-3 sm:p-4';
    const borderStyle = depth > 0 ? 'border-gray-200' : 'border-gray-300';
    const bgColor = depth > 0 ? `bg-gray-${Math.min(50 * depth, 100)}` : 'bg-white';

    return (
    <div key={variable.id} className={`border rounded-lg ${containerPadding} ${bgColor} ${borderStyle} transition-all`}>
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between mb-3 gap-3">
        <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
          <div className="col-span-1">
            <label className="block text-xs font-medium text-gray-700 mb-1">
              {depth > 0 ? 'Property Name' : 'Variable Name'}
              {parentPath && (
                <span className="text-gray-400 ml-1 text-[10px] sm:text-xs break-all">
                  ({parentPath}.)
                </span>
              )}
            </label>
            <input
              type="text"
              value={variable.name}
              onChange={(e) => {
                const newName = e.target.value;
                const updates = { name: newName };

                // Auto-generate display name if it's empty or matches the auto-generated pattern of the old name
                if (!variable.displayName || variable.displayName === generateDisplayName(variable.name)) {
                  updates.displayName = generateDisplayName(newName);
                }

                updateVariable(variable.id, updates, parentPath);
              }}
              placeholder={depth > 0 ? "property_name" : "variable_name"}
              className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={mode === 'view'}
            />
            {variablePath && variable.name && (
              <div className="text-[10px] sm:text-xs text-gray-500 mt-1 break-all">Path: {variablePath}</div>
            )}
          </div>

          <div className="col-span-1">
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Display Name
            </label>
            <input
              type="text"
              value={variable.displayName}
              onChange={(e) => updateVariable(variable.id, { displayName: e.target.value })}
              placeholder="Friendly Name"
              className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={mode === 'view'}
            />
          </div>
        </div>
        
        {mode === 'edit' && (
          <div className="flex items-center lg:ml-3 space-x-1 mt-2 lg:mt-0">
            <button
              type="button"
              onClick={() => moveVariable(variable.id, 'up')}
              className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isFirstInList}
            >
              <ChevronUpIcon className="w-3 h-3 sm:w-4 sm:h-4" />
            </button>
            <button
              type="button"
              onClick={() => moveVariable(variable.id, 'down')}
              className="p-1 text-gray-400 hover:text-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={isLastInList}
            >
              <ChevronDownIcon className="w-3 h-3 sm:w-4 sm:h-4" />
            </button>
            <button
              type="button"
              onClick={() => removeVariable(variable.id)}
              className="p-1 text-red-400 hover:text-red-600"
            >
              <TrashIcon className="w-3 h-3 sm:w-4 sm:h-4" />
            </button>
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 sm:gap-3 mb-3">
        <div className="col-span-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Data Type
          </label>
          <select
            value={variable.dataType}
            onChange={(e) => {
              const dataType = e.target.value;
              const updatedVar = { ...variable, dataType };
              const uiControls = getUIControls(dataType, updatedVar);
              updateVariable(variable.id, {
                dataType,
                uiControl: uiControls[0]
              }, parentPath);
              // Auto-expand if JSON or Array type is selected
              if (dataType === DataTypes.JSON || dataType === DataTypes.ARRAY) {
                setExpandedVariables(prev => ({ ...prev, [variable.id]: true }));
              }
            }}
            className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={mode === 'view'}
          >
            {dataTypes.map(type => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <div className="col-span-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            UI Control
          </label>
          <select
            value={variable.uiControl}
            onChange={(e) => updateVariable(variable.id, { uiControl: e.target.value })}
            className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={mode === 'view'}
          >
            {getUIControls(variable.dataType, variable).map(control => (
              <option key={control} value={control}>
                {getUIControlLabel(control)}
              </option>
            ))}
          </select>
        </div>

        <div className="col-span-1 flex items-center sm:mt-0 lg:mt-5">
          <input
            type="checkbox"
            id={`required-${variable.id}`}
            checked={variable.required}
            onChange={(e) => updateVariable(variable.id, { required: e.target.checked })}
            className="h-3 w-3 sm:h-4 sm:w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            disabled={mode === 'view'}
          />
          <label htmlFor={`required-${variable.id}`} className="ml-2 text-xs sm:text-sm text-gray-700">
            Required
          </label>
        </div>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
        <div className="col-span-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Description
          </label>
          <input
            type="text"
            value={variable.description || ''}
            onChange={(e) => updateVariable(variable.id, { description: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
              }
            }}
            placeholder="Brief description"
            className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={mode === 'view'}
          />
        </div>

        <div className="col-span-1">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Default Value
          </label>
          <input
            type="text"
            value={variable.defaultValue || ''}
            onChange={(e) => updateVariable(variable.id, { defaultValue: e.target.value })}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                e.stopPropagation();
              }
            }}
            placeholder="Default value"
            className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      {/* Item Type selector for Arrays - shown immediately below other fields */}
      {variable.dataType === DataTypes.ARRAY && (
        <div className="mt-3">
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Item Type
          </label>
          <select
            value={variable.itemType || DataTypes.STRING}
            onChange={(e) => {
              const itemType = e.target.value;
              const updates = { itemType };

              // Initialize properties array if switching to Object type
              if (itemType === DataTypes.OBJECT && !variable.properties) {
                updates.properties = [];
              }

              updateVariable(variable.id, updates, parentPath);

              // Auto-expand if Object type is selected for array items
              if (itemType === DataTypes.OBJECT) {
                setExpandedVariables(prev => ({ ...prev, [variable.id]: true }));
              }
            }}
            className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={mode === 'view'}
          >
            <option value={DataTypes.STRING}>String</option>
            <option value={DataTypes.NUMBER}>Number</option>
            <option value={DataTypes.INTEGER}>Integer</option>
            <option value={DataTypes.BOOLEAN}>Boolean</option>
            <option value={DataTypes.OBJECT}>Object</option>
            <option value={DataTypes.DATE}>Date</option>
            <option value={DataTypes.DATETIME}>Date Time</option>
          </select>
        </div>
      )}

      {/* Validation options for specific data types */}
      {(variable.dataType === DataTypes.STRING || variable.dataType === DataTypes.NUMBER ||
        variable.dataType === DataTypes.INTEGER || variable.dataType === DataTypes.ARRAY ||
        variable.dataType === DataTypes.FILE) && (
        <details className="mt-3">
          <summary className="text-xs font-medium text-gray-600 cursor-pointer">
            Validation Options
          </summary>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {variable.dataType === DataTypes.STRING && (
              <>
                <div>
                  <label className="block text-xs text-gray-600">Min Length</label>
                  <input
                    type="number"
                    value={variable.validation?.minLength || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, minLength: parseInt(e.target.value) || null }
                    })}
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600">Max Length</label>
                  <input
                    type="number"
                    value={variable.validation?.maxLength || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, maxLength: parseInt(e.target.value) || null }
                    })}
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                  />
                </div>
                <div className="col-span-1 sm:col-span-2">
                  <label className="block text-xs text-gray-600">Pattern (Regex)</label>
                  <input
                    type="text"
                    value={variable.validation?.pattern || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, pattern: e.target.value }
                    })}
                    placeholder="e.g., ^[A-Z][a-z]+$"
                    className="w-full px-2 py-1 text-xs sm:text-sm border border-gray-300 rounded font-mono"
                    disabled={mode === 'view'}
                  />
                </div>
              </>
            )}
            {variable.dataType === DataTypes.ARRAY && (
              <>
                <div>
                  <label className="block text-xs text-gray-600">Min Items</label>
                  <input
                    type="number"
                    value={variable.validation?.minItems || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, minItems: parseInt(e.target.value) || null }
                    })}
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600">Max Items</label>
                  <input
                    type="number"
                    value={variable.validation?.maxItems || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, maxItems: parseInt(e.target.value) || null }
                    })}
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                  />
                </div>
              </>
            )}
            {(variable.dataType === DataTypes.NUMBER || variable.dataType === DataTypes.INTEGER) && (
              <>
                <div>
                  <label className="block text-xs text-gray-600">
                    Min Value {variable.uiControl === 'range' && <span className="text-blue-500">(Range Start)</span>}
                  </label>
                  <input
                    type="number"
                    value={variable.validation?.min || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, min: parseFloat(e.target.value) || null }
                    })}
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                    placeholder={variable.uiControl === 'range' ? '0' : ''}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600">
                    Max Value {variable.uiControl === 'range' && <span className="text-blue-500">(Range End)</span>}
                  </label>
                  <input
                    type="number"
                    value={variable.validation?.max || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, max: parseFloat(e.target.value) || null }
                    })}
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                    placeholder={variable.uiControl === 'range' ? '100' : ''}
                  />
                </div>
                {variable.uiControl === 'range' && (
                  <div className="col-span-1 sm:col-span-2">
                    <div className="text-xs text-blue-600 bg-blue-50 p-2 rounded">
                      🎨 <strong>Range Slider:</strong> Min/Max values define the slider range. 
                      Default value will be the initial position.
                    </div>
                  </div>
                )}
              </>
            )}
            {variable.dataType === DataTypes.FILE && (
              <>
                <div>
                  <label className="block text-xs text-gray-600">Accepted File Types</label>
                  <input
                    type="text"
                    value={variable.validation?.accept || ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, accept: e.target.value }
                    })}
                    placeholder=".pdf,.jpg,.png"
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600">Max File Size (MB)</label>
                  <input
                    type="number"
                    value={variable.validation?.maxSize ? (variable.validation.maxSize / 1048576) : ''}
                    onChange={(e) => updateVariable(variable.id, { 
                      validation: { ...variable.validation, maxSize: e.target.value ? (parseFloat(e.target.value) * 1048576) : null }
                    })}
                    className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                    disabled={mode === 'view'}
                  />
                </div>
                {variable.uiControl === 'file-multiple' && (
                  <div>
                    <label className="block text-xs text-gray-600">Max Number of Files</label>
                    <input
                      type="number"
                      value={variable.validation?.maxFiles || ''}
                      onChange={(e) => updateVariable(variable.id, { 
                        validation: { ...variable.validation, maxFiles: parseInt(e.target.value) || null }
                      })}
                      className="w-full px-2 py-1 text-xs sm:text-sm text-right border border-gray-300 rounded"
                      disabled={mode === 'view'}
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </details>
      )}
      
      {/* UI Control Information */}
      {variable.uiControl && variable.uiControl !== 'text' && !canHaveProperties && (
        <div className="mt-3 p-3 bg-gray-50 rounded-lg border">
          <div className="text-xs font-medium text-gray-700 mb-1">
            🎨 UI Control: {getUIControlLabel(variable.uiControl)}
          </div>
          <div className="text-xs text-gray-600">
            {getUIControlDescription(variable.uiControl)}
          </div>
        </div>
      )}

      {/* Nested Properties for JSON Objects and Object Arrays */}
      {canHaveProperties && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center">
              <button
                onClick={() => toggleVariableExpanded(variable.id)}
                className="text-xs font-medium text-blue-600 hover:text-blue-700 flex items-center"
                type="button"
              >
                {isExpanded ? (
                  <ChevronUpIcon className="w-3 h-3 mr-1" />
                ) : (
                  <ChevronDownIcon className="w-3 h-3 mr-1" />
                )}
                {isJsonType ? 'Object Properties' : 'Array Item Properties'}
              </button>
              {variable.properties && variable.properties.length > 0 && (
                <span className="ml-2 text-xs text-gray-500">
                  ({variable.properties.length} {variable.properties.length === 1 ? 'property' : 'properties'})
                </span>
              )}
            </div>
            {mode === 'edit' && isExpanded && (
              <button
                onClick={() => addVariable(variable.id)}
                className="px-2 py-1 text-[10px] sm:text-xs bg-blue-500 text-white rounded hover:bg-blue-600 flex items-center whitespace-nowrap"
                type="button"
              >
                <PlusIcon className="w-3 h-3 mr-1" />
                <span className="hidden sm:inline">Add {isJsonType ? 'Property' : 'Item Field'}</span>
                <span className="sm:hidden">Add</span>
              </button>
            )}
          </div>

          {isExpanded && (
            <div className={`border-l-2 border-blue-200 ${depth > 1 ? 'pl-2 sm:pl-3 ml-1' : 'pl-3 sm:pl-4 ml-2'}`}>
              {variable.properties && variable.properties.length > 0 ? (
                <div className="space-y-2">
                  {variable.properties.map(prop =>
                    renderVariableEditor(prop, variablePath, depth + 1, variable.properties)
                  )}
                </div>
              ) : (
                <div className="py-4 text-center text-gray-400 text-xs">
                  No {isJsonType ? 'properties' : 'item fields'} defined.
                  {mode === 'edit' && (
                    <span className="block mt-1">
                      Click "Add {isJsonType ? 'Property' : 'Item Field'}" to define nested structure.
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-900">Manual Trigger Variables</h3>
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setActiveTab(activeTab === 'form' ? 'schema' : 'form')}
            className="px-2 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 flex items-center"
          >
            {activeTab === 'form' ? (
              <>
                <CodeBracketIcon className="w-3 h-3 mr-1" />
                View Schema
              </>
            ) : (
              <>
                <DocumentTextIcon className="w-3 h-3 mr-1" />
                Form Editor
              </>
            )}
          </button>
        </div>
      </div>
      
      {activeTab === 'form' ? (
        <>
          <div className="space-y-3">
            {Array.isArray(localVariables) && localVariables.map(variable => renderVariableEditor(variable, '', 0, localVariables))}
          </div>
          
          {mode === 'edit' && (
            <button
              type="button"
              onClick={() => addVariable()}
              className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700 flex items-center justify-center"
            >
              <PlusIcon className="w-4 h-4 mr-2" />
              Add Variable
            </button>
          )}
        </>
      ) : (
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="text-xs font-medium text-gray-700 mb-2">Generated Schema</h4>
          <pre className="text-xs overflow-x-auto">
            {JSON.stringify(generateSchema(), null, 2)}
          </pre>
        </div>
      )}
      
      {localVariables.length === 0 && mode === 'edit' && (
        <div className="text-center py-8 text-gray-500">
          <DocumentTextIcon className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="text-sm">No variables defined</p>
          <p className="text-xs mt-1">Click "Add Variable" to define input variables for manual trigger</p>
        </div>
      )}
    </div>
  );
};

export default ManualTriggerConfig;