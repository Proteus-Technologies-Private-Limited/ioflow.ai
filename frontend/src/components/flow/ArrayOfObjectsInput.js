import React, { useState, useCallback } from 'react';
import {
  PlusIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline';

const ArrayOfObjectsInput = ({ value = [], onChange, properties = [], itemType }) => {
  const [expandedItems, setExpandedItems] = useState({});

  // Toggle item expansion
  const toggleItemExpanded = useCallback((index) => {
    setExpandedItems(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
  }, []);

  // Add a new item with default values
  const addItem = useCallback(() => {
    const newItem = {};
    properties.forEach(prop => {
      if (prop.defaultValue !== undefined) {
        newItem[prop.name] = prop.defaultValue;
      } else if (prop.dataType === 'boolean' || prop.dataType === 'BOOLEAN') {
        newItem[prop.name] = false;
      } else if (prop.dataType === 'number' || prop.dataType === 'NUMBER' ||
                 prop.dataType === 'integer' || prop.dataType === 'INTEGER') {
        newItem[prop.name] = 0;
      } else if (prop.dataType === 'array' || prop.dataType === 'ARRAY') {
        newItem[prop.name] = [];
      } else if (prop.dataType === 'object' || prop.dataType === 'OBJECT' ||
                 prop.dataType === 'json' || prop.dataType === 'JSON') {
        newItem[prop.name] = {};
      } else {
        newItem[prop.name] = '';
      }
    });

    const newArray = [...value, newItem];
    onChange(newArray);
    // Auto-expand the new item
    setExpandedItems(prev => ({ ...prev, [value.length]: true }));
  }, [value, onChange, properties]);

  // Remove an item
  const removeItem = useCallback((index) => {
    const newArray = value.filter((_, i) => i !== index);
    onChange(newArray);
    // Clean up expanded state
    const newExpanded = {};
    Object.keys(expandedItems).forEach(key => {
      const keyIndex = parseInt(key);
      if (keyIndex < index) {
        newExpanded[key] = expandedItems[key];
      } else if (keyIndex > index) {
        newExpanded[keyIndex - 1] = expandedItems[key];
      }
    });
    setExpandedItems(newExpanded);
  }, [value, onChange, expandedItems]);

  // Update a field within an item
  const updateItemField = useCallback((index, fieldName, fieldValue) => {
    const newArray = [...value];
    newArray[index] = { ...newArray[index], [fieldName]: fieldValue };
    onChange(newArray);
  }, [value, onChange]);

  // Render a field input based on its type
  const renderFieldInput = (item, itemIndex, field) => {
    const fieldValue = item[field.name];
    const fieldType = field.dataType;

    if (fieldType === 'boolean' || fieldType === 'BOOLEAN') {
      return (
        <div className="flex items-center">
          <input
            type="checkbox"
            checked={fieldValue === true}
            onChange={(e) => updateItemField(itemIndex, field.name, e.target.checked)}
            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
          <span className="ml-2 text-sm text-gray-700">{fieldValue ? 'Yes' : 'No'}</span>
        </div>
      );
    } else if (fieldType === 'number' || fieldType === 'NUMBER' ||
               fieldType === 'integer' || fieldType === 'INTEGER') {
      return (
        <input
          type="number"
          value={fieldValue || ''}
          onChange={(e) => {
            const val = e.target.value === '' ? null : parseFloat(e.target.value);
            updateItemField(itemIndex, field.name, val);
          }}
          className="w-full px-2 py-1 text-sm text-right border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder="0"
        />
      );
    } else if (fieldType === 'date' || fieldType === 'DATE') {
      return (
        <input
          type="date"
          value={fieldValue || ''}
          onChange={(e) => updateItemField(itemIndex, field.name, e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      );
    } else if (fieldType === 'datetime' || fieldType === 'DATETIME') {
      return (
        <input
          type="datetime-local"
          value={fieldValue || ''}
          onChange={(e) => updateItemField(itemIndex, field.name, e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      );
    } else if (fieldType === 'select' && field.options) {
      return (
        <select
          value={fieldValue || ''}
          onChange={(e) => updateItemField(itemIndex, field.name, e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">Select...</option>
          {field.options.map(option => (
            <option key={option.value || option} value={option.value || option}>
              {option.label || option}
            </option>
          ))}
        </select>
      );
    } else if (field.uiControl === 'textarea') {
      return (
        <textarea
          value={fieldValue || ''}
          onChange={(e) => updateItemField(itemIndex, field.name, e.target.value)}
          rows={2}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder={`Enter ${field.displayName || field.name}`}
        />
      );
    } else if (fieldType === 'array' || fieldType === 'ARRAY') {
      // For array fields, show as JSON input
      return (
        <textarea
          value={Array.isArray(fieldValue) ? JSON.stringify(fieldValue, null, 2) : '[]'}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              if (Array.isArray(parsed)) {
                updateItemField(itemIndex, field.name, parsed);
              }
            } catch {
              // Keep the text value if it's not valid JSON yet
            }
          }}
          rows={2}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder='["item1", "item2"]'
        />
      );
    } else if (fieldType === 'object' || fieldType === 'OBJECT' ||
               fieldType === 'json' || fieldType === 'JSON') {
      // For object fields, show as JSON input
      return (
        <textarea
          value={typeof fieldValue === 'object' ? JSON.stringify(fieldValue, null, 2) : '{}'}
          onChange={(e) => {
            try {
              const parsed = JSON.parse(e.target.value);
              if (typeof parsed === 'object' && !Array.isArray(parsed)) {
                updateItemField(itemIndex, field.name, parsed);
              }
            } catch {
              // Keep the text value if it's not valid JSON yet
            }
          }}
          rows={2}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded font-mono focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder='{"key": "value"}'
        />
      );
    } else {
      // Default to text input
      return (
        <input
          type="text"
          value={fieldValue || ''}
          onChange={(e) => updateItemField(itemIndex, field.name, e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder={`Enter ${field.displayName || field.name}`}
        />
      );
    }
  };

  // Render an item
  const renderItem = (item, index) => {
    const isExpanded = expandedItems[index];

    return (
      <div key={index} className="border border-gray-200 rounded-lg p-3 bg-white">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center">
            <button
              type="button"
              onClick={() => toggleItemExpanded(index)}
              className="mr-2 text-gray-500 hover:text-gray-700"
            >
              {isExpanded ?
                <ChevronDownIcon className="w-4 h-4" /> :
                <ChevronRightIcon className="w-4 h-4" />
              }
            </button>
            <span className="text-sm font-medium text-gray-700">
              Item {index + 1}
            </span>
            <span className="ml-2 text-xs text-gray-500">
              ({properties.length} properties)
            </span>
          </div>
          <button
            type="button"
            onClick={() => removeItem(index)}
            className="p-1 text-red-500 hover:text-red-600"
          >
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>

        {isExpanded && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
            {properties.map(field => {
              // Check if this field should span multiple columns
              const isComplexField =
                field.uiControl === 'textarea' ||
                field.dataType === 'array' ||
                field.dataType === 'ARRAY' ||
                field.dataType === 'object' ||
                field.dataType === 'OBJECT' ||
                field.dataType === 'json' ||
                field.dataType === 'JSON';

              return (
                <div
                  key={field.name}
                  className={isComplexField ? 'md:col-span-2 lg:col-span-3' : ''}
                >
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    {field.displayName || field.name}
                    {field.required && <span className="text-red-500 ml-1">*</span>}
                  </label>
                  {renderFieldInput(item, index, field)}
                </div>
              );
            })}
          </div>
        )}

        {!isExpanded && (
          <div className="text-xs text-gray-500 mt-1">
            {/* Show a preview of the item data */}
            {Object.entries(item).slice(0, 3).map(([key, val]) => (
              <span key={key} className="mr-3">
                {key}: {typeof val === 'object' ? JSON.stringify(val) : String(val)}
              </span>
            ))}
            {Object.keys(item).length > 3 && <span>...</span>}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-2">
      {/* Render all items */}
      {value.map((item, index) => renderItem(item, index))}

      {/* Add item button */}
      <button
        type="button"
        onClick={addItem}
        className="flex items-center px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 border border-dashed border-blue-300 rounded hover:border-blue-400 w-full justify-center"
      >
        <PlusIcon className="w-4 h-4 mr-1" />
        Add Item
      </button>
    </div>
  );
};

export default ArrayOfObjectsInput;