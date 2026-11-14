import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  DocumentDuplicateIcon,
  CodeBracketIcon,
  GlobeAltIcon,
  LinkIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline';
import JsonImportModal from './JsonImportModal';
import { buildNestedSchema, validateJsonSchema, flattenJsonSchema } from '../../utils/schemaUtils';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const SchemaBuilder = ({ 
  initialSchema = null, 
  onSchemaChange, 
  parameterMethod = 'json_payload',
  mode = 'edit' // 'edit' or 'view'
}) => {
  // Extract parameters from URL pattern
  const extractUrlParameters = useCallback((pattern) => {
    const regex = /\{(\w+)\}/g;
    const params = [];
    let match;
    let position = 0;
    
    while ((match = regex.exec(pattern)) !== null) {
      params.push({
        id: Date.now() + position,
        param_name: match[1],
        friendly_name: match[1].replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
        data_type: 'string',
        required: true,
        url_position: position++,
      });
    }
    
    return params;
  }, []);

  // Initialize state with lazy initialization to prevent re-running on every render
  const [fields, setFields] = useState(() => {
    if (initialSchema) {
      if (parameterMethod === 'url_pattern' && initialSchema.url_pattern) {
        return extractUrlParameters(initialSchema.url_pattern);
      } else if (initialSchema.fields && initialSchema.fields.length > 0) {
        // Only use fields if it's not empty
        return initialSchema.fields;
      } else if (initialSchema.json_schema) {
        // Convert JSON Schema to flattened fields
        return flattenJsonSchema(initialSchema.json_schema);
      }
    }
    return [];
  });
  
  const [urlPattern, setUrlPattern] = useState(() => {
    return (parameterMethod === 'url_pattern' && initialSchema?.url_pattern) || '';
  });
  
  const [showPreview, setShowPreview] = useState(false);
  const [activeTab, setActiveTab] = useState('builder'); // 'builder' or 'code'
  const [schemaCode, setSchemaCode] = useState(() => {
    return initialSchema?.json_schema ? JSON.stringify(initialSchema.json_schema, null, 2) : '';
  });
  const [showJsonImportModal, setShowJsonImportModal] = useState(false);

  // Data type options
  const dataTypes = [
    { value: 'string', label: 'String', icon: '📝' },
    { value: 'number', label: 'Number', icon: '🔢' },
    { value: 'integer', label: 'Integer', icon: '🔢' },
    { value: 'boolean', label: 'Boolean', icon: '✓' },
    { value: 'date', label: 'Date', icon: '📅' },
    { value: 'datetime', label: 'DateTime', icon: '🕐' },
    { value: 'array', label: 'Array', icon: '📚' },
    { value: 'object', label: 'Object', icon: '📦' },
    { value: 'file', label: 'File', icon: '📄' },
  ];

  // UI control options
  const uiControls = [
    { value: 'text', label: 'Text Input' },
    { value: 'textarea', label: 'Text Area' },
    { value: 'number', label: 'Number Input' },
    { value: 'dropdown', label: 'Dropdown' },
    { value: 'checkbox', label: 'Checkbox' },
    { value: 'toggle', label: 'Toggle Switch' },
    { value: 'radio', label: 'Radio Buttons' },
    { value: 'date', label: 'Date Picker' },
    { value: 'datetime', label: 'DateTime Picker' },
    { value: 'email', label: 'Email Input' },
    { value: 'url', label: 'URL Input' },
    { value: 'range', label: 'Range Slider' },
    { value: 'tags', label: 'Tag Input' },
    { value: 'code', label: 'Code Editor' },
    { value: 'html', label: 'HTML Editor' },
    { value: 'wysiwyg', label: 'WYSIWYG HTML Editor' },
    { value: 'json', label: 'JSON Editor' },
    { value: 'file', label: 'File Upload' },
    { value: 'hidden', label: 'Hidden Field' },
  ];


  // Add new field
  const addField = () => {
    const newField = {
      id: Date.now(),
      field_name: '',
      param_name: '',
      friendly_name: '',
      description: '',
      data_type: 'string',
      is_required: false,
      required: false,
      ui_control: 'text',
      display_order: fields.length,
    };
    setFields([...fields, newField]);
  };

  // Update field
  const updateField = (id, updates) => {
    setFields(fields.map(field => 
      field.id === id ? { ...field, ...updates } : field
    ));
  };

  // Remove field
  const removeField = (id) => {
    setFields(fields.filter(field => field.id !== id));
  };

  // Move field up/down
  const moveField = (id, direction) => {
    const index = fields.findIndex(f => f.id === id);
    if ((direction === 'up' && index === 0) || 
        (direction === 'down' && index === fields.length - 1)) {
      return;
    }
    
    const newFields = [...fields];
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    [newFields[index], newFields[newIndex]] = [newFields[newIndex], newFields[index]];
    
    // Update display order
    newFields.forEach((field, i) => {
      field.display_order = i;
    });
    
    setFields(newFields);
  };

  // Generate schema from fields - memoized to prevent infinite loops
  const generatedSchema = useMemo(() => {
    if (parameterMethod === 'json_payload') {
      // Filter out fields with no name and prepare them for buildNestedSchema
      const validFields = fields
        .filter(field => field && (field.field_name || field.param_name))
        .map(field => ({
          ...field,
          field_name: field.field_name || field.param_name,
          is_required: field.is_required || field.required
        }));
      
      // Use buildNestedSchema to properly handle nested objects
      return buildNestedSchema(validFields);
    } else if (parameterMethod === 'xml_payload') {
      // Generate XML schema
      const elements = fields.map(field => ({
        name: field.param_name,
        type: field.data_type,
        required: field.required,
        description: field.description,
      }));
      
      return {
        root: 'request',
        elements,
      };
    } else if (parameterMethod === 'url_pattern') {
      // Generate URL pattern with parameters
      return {
        pattern: urlPattern,
        parameters: fields.map(f => ({
          name: f.param_name,
          type: f.data_type,
          required: f.required,
          position: f.url_position,
        })),
      };
    }
    return null;
  }, [fields, urlPattern, parameterMethod]);


  // Track if component is mounting to prevent initial callback
  const isMountingRef = useRef(true);
  
  // Update parent component
  useEffect(() => {
    // Skip the first render to prevent loops when editing
    if (isMountingRef.current) {
      isMountingRef.current = false;
      return;
    }
    
    if (onSchemaChange && generatedSchema !== null) {
      onSchemaChange({
        fields,
        schema: generatedSchema,
        url_pattern: urlPattern,
      });
    }
  }, [fields, urlPattern, generatedSchema, onSchemaChange]);

  // Update schema code when switching to code tab or when fields change
  useEffect(() => {
    if (activeTab === 'code' && generatedSchema) {
      setSchemaCode(JSON.stringify(generatedSchema, null, 2));
    }
  }, [activeTab, generatedSchema]);

  // Handle JSON import
  const handleJsonImport = (importedFields) => {
    console.log('Importing fields:', importedFields);
    // Convert imported fields to match our schema format
    const convertedFields = importedFields.map(field => ({
      id: field.id,
      param_name: field.field_name.replace(/\./g, '_'), // Replace dots with underscores
      friendly_name: field.friendly_name,
      description: field.description,
      data_type: field.data_type,
      required: field.is_required,
      ui_control: getDefaultUIControl(field.data_type),
      display_order: field.display_order,
    }));
    
    console.log('Converted fields:', convertedFields);
    setFields(convertedFields);
    setShowJsonImportModal(false);
  };

  // Get default UI control based on data type
  const getDefaultUIControl = (dataType) => {
    switch (dataType) {
      case 'boolean': return 'checkbox';
      case 'number':
      case 'integer': return 'number';
      case 'date': return 'date';
      case 'datetime': return 'datetime';
      case 'array': return 'dropdown';
      case 'object': return 'textarea';
      case 'file': return 'file';
      default: return 'text';
    }
  };

  // Render field editor
  const renderFieldEditor = (field) => {
    // Calculate indentation level based on dot notation
    const fieldName = field.field_name || field.param_name || '';
    const nestingLevel = fieldName.split('.').length - 1;
    const isNested = nestingLevel > 0;
    
    return (
      <div 
        key={field.id} 
        className={`border rounded-lg p-4 bg-white ${field.data_type === 'object' ? 'border-blue-200 bg-blue-50' : ''}`}
        style={isNested ? { marginLeft: `${nestingLevel * 2}rem` } : {}}
      >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Parameter Name
            </label>
            <input
              type="text"
              value={field.field_name || field.param_name}
              onChange={(e) => updateField(field.id, { field_name: e.target.value, param_name: e.target.value })}
              placeholder="variable_name or nested.path"
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={mode === 'view' || field.data_type === 'object'}
            />
          </div>
          
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Display Name
            </label>
            <input
              type="text"
              value={field.friendly_name}
              onChange={(e) => updateField(field.id, { friendly_name: e.target.value })}
              placeholder="Friendly Name"
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              disabled={mode === 'view'}
            />
          </div>
        </div>
        
        {mode === 'edit' && (
          <div className="flex items-center ml-3 space-x-1">
            <button
              type="button"
              onClick={() => moveField(field.id, 'up')}
              className="p-1 text-gray-400 hover:text-gray-600"
              disabled={fields[0]?.id === field.id}
            >
              <ChevronUpIcon className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => moveField(field.id, 'down')}
              className="p-1 text-gray-400 hover:text-gray-600"
              disabled={fields[fields.length - 1]?.id === field.id}
            >
              <ChevronDownIcon className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => removeField(field.id)}
              className="p-1 text-red-400 hover:text-red-600"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
      
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Data Type
          </label>
          <select
            value={field.data_type}
            onChange={(e) => updateField(field.id, { data_type: e.target.value })}
            className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={mode === 'view'}
          >
            {dataTypes.map(type => (
              <option key={type.value} value={type.value}>
                {type.icon} {type.label}
              </option>
            ))}
          </select>
        </div>
        
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            UI Control
          </label>
          <select
            value={field.ui_control}
            onChange={(e) => updateField(field.id, { ui_control: e.target.value })}
            className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
            disabled={mode === 'view'}
          >
            {uiControls.map(control => (
              <option key={control.value} value={control.value}>
                {control.label}
              </option>
            ))}
          </select>
        </div>
        
        <div className="flex items-center mt-5">
          <input
            type="checkbox"
            id={`required-${field.id}`}
            checked={field.is_required || field.required}
            onChange={(e) => updateField(field.id, { is_required: e.target.checked, required: e.target.checked })}
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            disabled={mode === 'view'}
          />
          <label htmlFor={`required-${field.id}`} className="ml-2 text-sm text-gray-700">
            Required
          </label>
        </div>
      </div>
      
      <div className="mb-3">
        <label className="block text-xs font-medium text-gray-700 mb-1">
          Description
        </label>
        <input
          type="text"
          value={field.description || ''}
          onChange={(e) => updateField(field.id, { description: e.target.value })}
          placeholder="Brief description of this parameter"
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
          disabled={mode === 'view'}
        />
      </div>
      
      {/* Additional options based on data type */}
      {field.data_type === 'string' && (
        <details className="mt-3">
          <summary className="text-xs font-medium text-gray-600 cursor-pointer">
            Validation Options
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-gray-600">Min Length</label>
              <input
                type="number"
                value={field.min_length || ''}
                onChange={(e) => updateField(field.id, { min_length: parseInt(e.target.value) || null })}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                disabled={mode === 'view'}
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600">Max Length</label>
              <input
                type="number"
                value={field.max_length || ''}
                onChange={(e) => updateField(field.id, { max_length: parseInt(e.target.value) || null })}
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded"
                disabled={mode === 'view'}
              />
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-600">Pattern (Regex)</label>
              <input
                type="text"
                value={field.pattern || ''}
                onChange={(e) => updateField(field.id, { pattern: e.target.value })}
                placeholder="e.g., ^[A-Z][a-z]+$"
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded font-mono"
                disabled={mode === 'view'}
              />
            </div>
          </div>
        </details>
      )}
      
      {/* Parameter Lookup Configuration */}
      <details className="mt-3">
        <summary className="text-xs font-medium text-gray-600 cursor-pointer">
          Parameter Lookup Configuration
        </summary>
        <div className="mt-2 space-y-3 p-3 bg-blue-50 rounded-md border border-blue-200">
          <div className="flex items-center">
            <input
              type="checkbox"
              id={`enable-lookup-${field.id}`}
              checked={field.parameterLookup ? true : false}
              onChange={(e) => {
                if (e.target.checked) {
                  updateField(field.id, { 
                    parameterLookup: {
                      type: 'api_call',
                      service: '',
                      parameters: {},
                      extractPath: '',
                      valueField: 'id',
                      displayField: 'name',
                      description: ''
                    }
                  });
                } else {
                  const { parameterLookup, ...fieldWithoutLookup } = field;
                  setFields(fields.map(f => f.id === field.id ? fieldWithoutLookup : f));
                }
              }}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              disabled={mode === 'view'}
            />
            <label htmlFor={`enable-lookup-${field.id}`} className="ml-2 text-sm text-blue-800 font-medium">
              Enable Parameter Lookup
            </label>
          </div>
          
          {field.parameterLookup && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs text-blue-800 font-medium">Lookup Type</label>
                  <select
                    value={field.parameterLookup.type || 'api_call'}
                    onChange={(e) => updateField(field.id, { 
                      parameterLookup: { ...field.parameterLookup, type: e.target.value } 
                    })}
                    className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                    disabled={mode === 'view'}
                  >
                    <option value="api_call">API Call</option>
                    <option value="static">Static List</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-xs text-blue-800 font-medium">Service Name</label>
                  <input
                    type="text"
                    value={field.parameterLookup.service || ''}
                    onChange={(e) => updateField(field.id, { 
                      parameterLookup: { ...field.parameterLookup, service: e.target.value } 
                    })}
                    placeholder="list_files"
                    className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                    disabled={mode === 'view'}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs text-blue-800 font-medium">Extract Path</label>
                  <input
                    type="text"
                    value={field.parameterLookup.extractPath || ''}
                    onChange={(e) => updateField(field.id, { 
                      parameterLookup: { ...field.parameterLookup, extractPath: e.target.value } 
                    })}
                    placeholder="files"
                    className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                    disabled={mode === 'view'}
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-blue-800 font-medium">Value Field</label>
                  <input
                    type="text"
                    value={field.parameterLookup.valueField || 'id'}
                    onChange={(e) => updateField(field.id, { 
                      parameterLookup: { ...field.parameterLookup, valueField: e.target.value } 
                    })}
                    placeholder="id"
                    className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                    disabled={mode === 'view'}
                  />
                </div>
                
                <div>
                  <label className="block text-xs text-blue-800 font-medium">Display Field</label>
                  <input
                    type="text"
                    value={field.parameterLookup.displayField || 'name'}
                    onChange={(e) => updateField(field.id, { 
                      parameterLookup: { ...field.parameterLookup, displayField: e.target.value } 
                    })}
                    placeholder="name"
                    className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                    disabled={mode === 'view'}
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-xs text-blue-800 font-medium">Description</label>
                <input
                  type="text"
                  value={field.parameterLookup.description || ''}
                  onChange={(e) => updateField(field.id, { 
                    parameterLookup: { ...field.parameterLookup, description: e.target.value } 
                  })}
                  placeholder="Select from available options"
                  className="w-full px-2 py-1 text-sm border border-blue-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                  disabled={mode === 'view'}
                />
              </div>
              
              <div>
                <label className="block text-xs text-blue-800 font-medium">Lookup Parameters (JSON)</label>
                <textarea
                  value={JSON.stringify(field.parameterLookup.parameters || {}, null, 2)}
                  onChange={(e) => {
                    try {
                      const params = JSON.parse(e.target.value);
                      updateField(field.id, { 
                        parameterLookup: { ...field.parameterLookup, parameters: params } 
                      });
                    } catch (err) {
                      // Keep the text as-is if it's not valid JSON yet
                    }
                  }}
                  placeholder='{"key": "value"}'
                  rows={3}
                  className="w-full px-2 py-1 text-sm border border-blue-300 rounded font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
                  disabled={mode === 'view'}
                />
              </div>
            </div>
          )}
        </div>
      </details>
    </div>
    );
  };

  // Render URL pattern editor
  const renderUrlPatternEditor = () => (
    <div className="mb-4">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        URL Pattern
      </label>
      <div className="flex items-center space-x-2">
        <LinkIcon className="w-5 h-5 text-gray-400" />
        <input
          type="text"
          value={urlPattern}
          onChange={(e) => {
            setUrlPattern(e.target.value);
            const params = extractUrlParameters(e.target.value);
            setFields(params);
          }}
          placeholder="/api/v1/users/{userId}/posts/{postId}"
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500 font-mono"
          disabled={mode === 'view'}
        />
      </div>
      <p className="mt-1 text-xs text-gray-500">
        Use {'{parameterName}'} to define path parameters
      </p>
    </div>
  );

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-gray-900">
          {parameterMethod === 'json_payload' && '📄 JSON Schema'}
          {parameterMethod === 'xml_payload' && '📄 XML Schema'}
          {parameterMethod === 'url_pattern' && '🔗 URL Pattern'}
        </h3>
        
        <div className="flex items-center space-x-2">
          {mode === 'edit' && parameterMethod === 'json_payload' && (
            <button
              type="button"
              onClick={() => setShowJsonImportModal(true)}
              className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
            >
              <ArrowDownTrayIcon className="w-4 h-4 inline mr-1" />
              Import from JSON
            </button>
          )}
          <button
            type="button"
            onClick={() => setActiveTab(activeTab === 'builder' ? 'code' : 'builder')}
            className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            <CodeBracketIcon className="w-4 h-4 inline mr-1" />
            {activeTab === 'builder' ? 'View Code' : 'Visual Builder'}
          </button>
          
          <button
            type="button"
            onClick={() => setShowPreview(!showPreview)}
            className="px-3 py-1 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            {showPreview ? 'Hide' : 'Show'} Preview
          </button>
        </div>
      </div>
      
      {/* URL Pattern Editor */}
      {parameterMethod === 'url_pattern' && renderUrlPatternEditor()}
      
      {/* Builder or Code View */}
      {activeTab === 'builder' ? (
        <>
          {/* Fields */}
          {fields.length > 0 ? (
            <div className="space-y-3">
              {fields.map(field => renderFieldEditor(field))}
            </div>
          ) : (
            <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
              <p className="text-gray-500 mb-2">No schema fields defined</p>
              <p className="text-sm text-gray-400">
                {mode === 'edit' ? 'Click "Add Parameter" to add fields manually or "Import from JSON" to import from sample data' : 'No fields have been defined for this schema'}
              </p>
            </div>
          )}
          
          {/* Add Field Button */}
          {mode === 'edit' && parameterMethod !== 'url_pattern' && (
            <button
              type="button"
              onClick={addField}
              className="w-full py-2 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700 flex items-center justify-center"
            >
              <PlusIcon className="w-5 h-5 mr-2" />
              Add Parameter
            </button>
          )}
        </>
      ) : (
        <div>
          <textarea
            value={schemaCode}
            onChange={(e) => setSchemaCode(e.target.value)}
            rows={15}
            className="w-full px-3 py-2 border border-gray-300 rounded-md font-mono text-sm"
            disabled={mode === 'view'}
            placeholder={`{
  "type": "object",
  "properties": {
    "field_name": {
      "type": "string",
      "description": "Field description"
    }
  },
  "required": ["field_name"]
}`}
          />
          {mode === 'edit' && (
            <div className="mt-3 flex justify-between items-center">
              <p className="text-xs text-gray-500">
                Edit the JSON schema directly. Changes will be applied when you switch back to Visual Builder.
              </p>
              <button
                type="button"
                onClick={() => {
                  const validation = validateJsonSchema(schemaCode);
                  if (!validation.valid) {
                    showErrorToast('Invalid JSON schema: ' + validation.error);
                    return;
                  }
                  
                  // Convert nested schema to flattened fields
                  const convertedFields = flattenJsonSchema(validation.schema);
                  setFields(convertedFields);
                  setActiveTab('builder');
                  showSuccessToast('Schema updated successfully');
                }}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm"
              >
                Apply Changes
              </button>
            </div>
          )}
        </div>
      )}
      
      {/* Preview */}
      {showPreview && (
        <div className="border-t pt-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Schema Preview</h4>
          <pre className="bg-gray-50 p-3 rounded-md text-xs overflow-x-auto">
            {JSON.stringify(generatedSchema, null, 2)}
          </pre>
        </div>
      )}

      {/* JSON Import Modal */}
      <JsonImportModal
        isOpen={showJsonImportModal}
        onClose={() => setShowJsonImportModal(false)}
        onImport={handleJsonImport}
      />
    </div>
  );
};

export default SchemaBuilder;