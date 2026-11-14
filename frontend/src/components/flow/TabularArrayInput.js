import React, { useCallback } from 'react';
import {
  PlusIcon,
  TrashIcon,
} from '@heroicons/react/24/outline';

const TabularArrayInput = ({ value = [], onChange, properties = [], minItems, maxItems }) => {
  // Add a new row with default values
  const addRow = useCallback(() => {
    if (maxItems && value.length >= maxItems) {
      return; // Don't add more items
    }

    const newRow = {};
    properties.forEach(prop => {
      if (prop.defaultValue !== undefined) {
        newRow[prop.name] = prop.defaultValue;
      } else if (prop.dataType === 'boolean' || prop.dataType === 'BOOLEAN') {
        newRow[prop.name] = false;
      } else if (prop.dataType === 'number' || prop.dataType === 'NUMBER' ||
                 prop.dataType === 'integer' || prop.dataType === 'INTEGER') {
        newRow[prop.name] = 0;
      } else {
        newRow[prop.name] = '';
      }
    });

    onChange([...value, newRow]);
  }, [value, onChange, properties, maxItems]);

  // Remove a row
  const removeRow = useCallback((index) => {
    if (minItems && value.length <= minItems) {
      return; // Don't remove items below minimum
    }
    onChange(value.filter((_, i) => i !== index));
  }, [value, onChange, minItems]);

  // Update a cell value
  const updateCell = useCallback((rowIndex, fieldName, fieldValue) => {
    const newValue = [...value];
    newValue[rowIndex] = { ...newValue[rowIndex], [fieldName]: fieldValue };
    onChange(newValue);
  }, [value, onChange]);

  // Convert value to correct type based on field dataType
  const convertToType = (val, dataType) => {
    switch (dataType) {
      case 'number':
      case 'NUMBER':
        const num = Number(val);
        return isNaN(num) ? 0 : num;
      case 'integer':
      case 'INTEGER':
        const int = parseInt(val);
        return isNaN(int) ? 0 : int;
      case 'boolean':
      case 'BOOLEAN':
        return val === 'true' || val === true;
      case 'string':
      case 'STRING':
      default:
        return String(val);
    }
  };

  // Render input based on field type
  const renderCellInput = (item, rowIndex, field) => {
    const fieldValue = item[field.name] ?? field.defaultValue ?? '';
    const fieldType = field.dataType;

    if (fieldType === 'boolean' || fieldType === 'BOOLEAN') {
      return (
        <input
          type="checkbox"
          checked={fieldValue === true}
          onChange={(e) => updateCell(rowIndex, field.name, e.target.checked)}
          className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
        />
      );
    } else if (fieldType === 'number' || fieldType === 'NUMBER' ||
               fieldType === 'integer' || fieldType === 'INTEGER') {
      return (
        <input
          type="number"
          value={fieldValue}
          onChange={(e) => {
            const val = convertToType(e.target.value, fieldType);
            updateCell(rowIndex, field.name, val);
          }}
          className="w-full px-2 py-1 text-sm text-right border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
          step={fieldType === 'integer' || fieldType === 'INTEGER' ? '1' : 'any'}
        />
      );
    } else if (fieldType === 'date' || fieldType === 'DATE') {
      return (
        <input
          type="date"
          value={fieldValue}
          onChange={(e) => updateCell(rowIndex, field.name, e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      );
    } else if (fieldType === 'datetime' || fieldType === 'DATETIME') {
      return (
        <input
          type="datetime-local"
          value={fieldValue}
          onChange={(e) => updateCell(rowIndex, field.name, e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      );
    } else if (field.uiControl === 'select' && field.options) {
      return (
        <select
          value={fieldValue}
          onChange={(e) => updateCell(rowIndex, field.name, e.target.value)}
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
    } else {
      // Default to text input
      return (
        <input
          type="text"
          value={fieldValue}
          onChange={(e) => updateCell(rowIndex, field.name, e.target.value)}
          className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
          placeholder={field.placeholder || ''}
        />
      );
    }
  };

  // Initialize with minItems if needed
  React.useEffect(() => {
    if (minItems && value.length < minItems) {
      const itemsToAdd = minItems - value.length;
      const newRows = [];
      for (let i = 0; i < itemsToAdd; i++) {
        const newRow = {};
        properties.forEach(prop => {
          if (prop.defaultValue !== undefined) {
            newRow[prop.name] = prop.defaultValue;
          } else if (prop.dataType === 'boolean' || prop.dataType === 'BOOLEAN') {
            newRow[prop.name] = false;
          } else if (prop.dataType === 'number' || prop.dataType === 'NUMBER' ||
                     prop.dataType === 'integer' || prop.dataType === 'INTEGER') {
            newRow[prop.name] = 0;
          } else {
            newRow[prop.name] = '';
          }
        });
        newRows.push(newRow);
      }
      onChange([...value, ...newRows]);
    }
  }, []); // Only run on mount

  if (!properties || properties.length === 0) {
    return (
      <div className="text-sm text-gray-500 p-4 text-center border border-gray-200 rounded">
        No columns defined for table view
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Validation info */}
      {(minItems || maxItems) && (
        <div className="text-xs text-gray-500">
          Rows: {value.length}
          {minItems && ` (min: ${minItems})`}
          {maxItems && ` (max: ${maxItems})`}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto border border-gray-200 rounded">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {properties.map(prop => {
                const isNumeric = prop.dataType === 'number' || prop.dataType === 'NUMBER' ||
                                  prop.dataType === 'integer' || prop.dataType === 'INTEGER';
                return (
                  <th
                    key={prop.name}
                    className={`px-3 py-2 text-xs font-medium text-gray-700 uppercase tracking-wider ${
                      isNumeric ? 'text-right' : 'text-left'
                    }`}
                  >
                    {prop.displayName || prop.name}
                    {prop.required && <span className="text-red-500 ml-1">*</span>}
                  </th>
                );
              })}
              <th className="px-3 py-2 text-center text-xs font-medium text-gray-700 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {value.length === 0 ? (
              <tr>
                <td
                  colSpan={properties.length + 1}
                  className="px-3 py-4 text-center text-sm text-gray-500"
                >
                  No data. Click "Add Row" to add items.
                </td>
              </tr>
            ) : (
              value.map((item, index) => (
                <tr key={index} className="hover:bg-gray-50">
                  {properties.map(prop => {
                    const isNumeric = prop.dataType === 'number' || prop.dataType === 'NUMBER' ||
                                      prop.dataType === 'integer' || prop.dataType === 'INTEGER';
                    return (
                      <td key={prop.name} className={`px-3 py-2 ${isNumeric ? 'text-right' : ''}`}>
                        {renderCellInput(item, index, prop)}
                      </td>
                    );
                  })}
                  <td className="px-3 py-2 text-center">
                    <button
                      type="button"
                      onClick={() => removeRow(index)}
                      disabled={minItems && value.length <= minItems}
                      className="p-1 text-red-500 hover:text-red-600 disabled:opacity-50 disabled:cursor-not-allowed"
                      title={minItems && value.length <= minItems ? `Minimum ${minItems} rows required` : 'Remove row'}
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add row button */}
      <button
        type="button"
        onClick={addRow}
        disabled={maxItems && value.length >= maxItems}
        className="flex items-center px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 border border-dashed border-blue-300 rounded hover:border-blue-400 disabled:opacity-50 disabled:cursor-not-allowed"
        title={maxItems && value.length >= maxItems ? `Maximum ${maxItems} rows allowed` : 'Add new row'}
      >
        <PlusIcon className="w-4 h-4 mr-1" />
        Add Row
      </button>
    </div>
  );
};

export default TabularArrayInput;