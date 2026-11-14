import React, { useState, useCallback } from 'react';
import {
  PlusIcon,
  TrashIcon,
  TableCellsIcon,
  Squares2X2Icon,
  Square3Stack3DIcon
} from '@heroicons/react/24/outline';

const Matrix2DArrayInput = React.memo(({ value = [], onChange, itemType = 'string', minItems, maxItems }) => {
  // Initialize with minItems if needed
  React.useEffect(() => {
    if (!Array.isArray(value) || value === null || value === undefined) {
      if (minItems && minItems > 0) {
        // Initialize with minimum number of items
        const defaultValue = getDefaultValueForType(itemType);
        const initialArray = Array(minItems).fill(defaultValue);
        onChange(initialArray);
      } else {
        onChange([]);
      }
    } else if (minItems && value.length < minItems) {
      // Add items to meet minimum requirement
      const defaultValue = getDefaultValueForType(itemType);
      const itemsToAdd = minItems - value.length;
      const newArray = [...value, ...Array(itemsToAdd).fill(defaultValue)];
      onChange(newArray);
    }
  }, []);

  // Helper function to get default value based on type
  const getDefaultValueForType = (type) => {
    switch (type) {
      case 'number':
      case 'integer':
        return 0;
      case 'boolean':
        return false;
      case 'array':
        return [];
      case 'object':
      case 'json':
        return {};
      default:
        return '';
    }
  };

  // Helper function to convert value to correct type
  const convertToType = (val, type) => {
    switch (type) {
      case 'number':
        const num = Number(val);
        return isNaN(num) ? 0 : num;
      case 'integer':
        const int = parseInt(val);
        return isNaN(int) ? 0 : int;
      case 'boolean':
        return val === 'true' || val === true;
      case 'string':
      default:
        return String(val);
    }
  };

  // State to track if we're in 2D mode
  const [is2DMode, setIs2DMode] = useState(() => {
    // Check if the current value is a 2D array
    return Array.isArray(value) && value.length > 0 && Array.isArray(value[0]);
  });

  // Convert between 1D and 2D arrays
  const convertTo2D = useCallback((arr) => {
    if (!Array.isArray(arr) || arr.length === 0) return [[]];
    if (Array.isArray(arr[0])) return arr; // Already 2D
    // Convert 1D to 2D with single column
    return arr.map(item => [item]);
  }, []);

  const convertTo1D = useCallback((arr) => {
    if (!Array.isArray(arr) || arr.length === 0) return [];
    if (!Array.isArray(arr[0])) return arr; // Already 1D
    // Only convert if all rows have single column
    if (arr.every(row => Array.isArray(row) && row.length === 1)) {
      return arr.map(row => row[0]);
    }
    // Can't convert multi-column to 1D, keep as 2D
    return arr;
  }, []);

  // Get dimensions
  const getColumns = useCallback(() => {
    if (!is2DMode || !Array.isArray(value) || value.length === 0) return 1;
    return Math.max(...value.map(row => Array.isArray(row) ? row.length : 1));
  }, [is2DMode, value]);

  const getRows = useCallback(() => {
    if (!Array.isArray(value)) return 0;
    return value.length;
  }, [value]);

  // Handle mode toggle
  const toggleMode = useCallback(() => {
    if (is2DMode) {
      // Converting from 2D to 1D
      const result = convertTo1D(value);
      if (Array.isArray(result[0])) {
        // Can't convert (has multiple columns)
        alert("Cannot convert to 1D array: matrix has multiple columns. Remove extra columns first.");
        return;
      }
      setIs2DMode(false);
      onChange(result);
    } else {
      // Converting from 1D to 2D
      setIs2DMode(true);
      onChange(convertTo2D(value));
    }
  }, [is2DMode, value, onChange, convertTo1D, convertTo2D]);

  // 1D Array handlers
  const handle1DAddItem = useCallback(() => {
    // Check if we've reached maxItems
    if (maxItems && value.length >= maxItems) {
      return; // Don't add more items
    }
    const defaultValue = getDefaultValueForType(itemType);
    const newValue = [...(value || []), defaultValue];
    onChange(newValue);
  }, [value, onChange, maxItems, itemType]);

  const handle1DRemoveItem = useCallback((index) => {
    // Check if we're at minItems
    if (minItems && value.length <= minItems) {
      return; // Don't remove items below minimum
    }
    const newValue = value.filter((_, i) => i !== index);
    onChange(newValue);
  }, [value, onChange, minItems]);

  const handle1DItemChange = useCallback((index, newItemValue) => {
    const newValue = [...value];
    // Convert to correct type
    newValue[index] = convertToType(newItemValue, itemType);
    onChange(newValue);
  }, [value, onChange, itemType]);

  // 2D Array handlers
  const handle2DAddRow = useCallback(() => {
    // Check if we've reached maxItems (for rows)
    if (maxItems && value.length >= maxItems) {
      return; // Don't add more rows
    }
    const cols = getColumns();
    const defaultValue = getDefaultValueForType(itemType);
    const newRow = new Array(cols).fill(defaultValue);
    const newValue = [...(value || []), newRow];
    onChange(newValue);
  }, [value, onChange, getColumns, maxItems, itemType]);

  const handle2DRemoveRow = useCallback((rowIndex) => {
    // Check if we're at minItems
    if (minItems && value.length <= minItems) {
      return; // Don't remove rows below minimum
    }
    const newValue = value.filter((_, i) => i !== rowIndex);
    onChange(newValue);
  }, [value, onChange, minItems]);

  const handle2DAddColumn = useCallback(() => {
    const defaultValue = getDefaultValueForType(itemType);
    const newValue = (value || []).map(row => {
      const safeRow = Array.isArray(row) ? row : [row];
      return [...safeRow, defaultValue];
    });
    // If array is empty, add a first row
    if (newValue.length === 0) {
      newValue.push([defaultValue, defaultValue]);
    }
    onChange(newValue);
  }, [value, onChange, itemType]);

  const handle2DRemoveColumn = useCallback((colIndex) => {
    const newValue = value.map(row => {
      const safeRow = Array.isArray(row) ? row : [row];
      return safeRow.filter((_, i) => i !== colIndex);
    });
    onChange(newValue);
  }, [value, onChange]);

  const handle2DCellChange = useCallback((rowIndex, colIndex, newCellValue) => {
    const newValue = [...value];
    if (!Array.isArray(newValue[rowIndex])) {
      newValue[rowIndex] = [newValue[rowIndex]];
    }
    newValue[rowIndex] = [...newValue[rowIndex]];
    // Convert to correct type
    newValue[rowIndex][colIndex] = convertToType(newCellValue, itemType);
    onChange(newValue);
  }, [value, onChange, itemType]);

  // Render based on mode
  if (!is2DMode) {
    // 1D Array Mode
    return (
      <div className="space-y-3">
        {/* Mode Toggle and Validation Info */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Squares2X2Icon className="w-5 h-5 text-gray-500" />
            <span className="text-sm font-medium text-gray-700">1D Array</span>
            <span className="text-xs text-gray-500">
              ({getRows()} items
              {minItems && `, min: ${minItems}`}
              {maxItems && `, max: ${maxItems}`})
            </span>
          </div>
          <button
            type="button"
            onClick={toggleMode}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded flex items-center space-x-1"
            title="Convert to 2D array (matrix)"
          >
            <Square3Stack3DIcon className="w-4 h-4" />
            <span>Add Columns</span>
          </button>
        </div>

        {/* 1D Array Items */}
        <div className="space-y-2">
          {(value || []).map((item, index) => (
            <div key={index} className="flex items-center space-x-2">
              <span className="text-xs text-gray-500 w-10">[{index}]</span>
              <input
                type={itemType === 'number' || itemType === 'integer' ? 'number' : 'text'}
                value={item || ''}
                onChange={(e) => handle1DItemChange(index, e.target.value)}
                className={`flex-1 px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 ${
                  itemType === 'number' || itemType === 'integer' ? 'text-right' : ''
                }`}
                placeholder={`Enter ${itemType}...`}
                step={itemType === 'integer' ? '1' : 'any'}
              />
              <button
                type="button"
                onClick={() => handle1DRemoveItem(index)}
                className="p-1 text-red-500 hover:text-red-600"
              >
                <TrashIcon className="w-4 h-4" />
              </button>
            </div>
          ))}
          
          <button
            type="button"
            onClick={handle1DAddItem}
            disabled={maxItems && value.length >= maxItems}
            className="flex items-center px-3 py-1 text-sm text-blue-600 hover:text-blue-700 border border-dashed border-blue-300 rounded hover:border-blue-400 disabled:opacity-50 disabled:cursor-not-allowed"
            title={maxItems && value.length >= maxItems ? `Maximum ${maxItems} items allowed` : 'Add new item'}
          >
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Row
          </button>
        </div>
      </div>
    );
  }

  // 2D Array Mode (Matrix)
  const columns = getColumns();
  const rows = getRows();

  return (
    <div className="space-y-3">
      {/* Mode Toggle and Info */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <TableCellsIcon className="w-5 h-5 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">2D Array (Matrix)</span>
          <span className="text-xs text-gray-500">({rows} × {columns})</span>
        </div>
        <div className="flex items-center space-x-2">
          {columns === 1 && (
            <button
              type="button"
              onClick={toggleMode}
              className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
              title="Convert to 1D array"
            >
              <Squares2X2Icon className="w-3 h-3 inline mr-1" />
              Convert to 1D
            </button>
          )}
          <button
            type="button"
            onClick={handle2DAddColumn}
            className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded flex items-center"
          >
            <PlusIcon className="w-4 h-4 mr-1" />
            Add Column
          </button>
        </div>
      </div>

      {/* Matrix Table */}
      <div className="overflow-x-auto border border-gray-200 rounded">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-2 py-1 text-xs font-medium text-gray-500"></th>
              {Array.from({ length: columns }, (_, i) => (
                <th key={i} className="px-2 py-1 text-xs font-medium text-gray-500">
                  <div className="flex items-center justify-between">
                    <span>[{i}]</span>
                    {columns > 1 && (
                      <button
                        type="button"
                        onClick={() => handle2DRemoveColumn(i)}
                        className="ml-2 text-red-400 hover:text-red-600"
                      >
                        <TrashIcon className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {(value || []).map((row, rowIndex) => {
              const safeRow = Array.isArray(row) ? row : [row];
              return (
                <tr key={rowIndex}>
                  <td className="px-2 py-1 text-xs text-gray-500 flex items-center">
                    <span className="mr-2">[{rowIndex}]</span>
                    <button
                      type="button"
                      onClick={() => handle2DRemoveRow(rowIndex)}
                      className="text-red-400 hover:text-red-600"
                    >
                      <TrashIcon className="w-3 h-3" />
                    </button>
                  </td>
                  {Array.from({ length: columns }, (_, colIndex) => (
                    <td key={colIndex} className="px-2 py-1">
                      <input
                        type={itemType === 'number' || itemType === 'integer' ? 'number' : 'text'}
                        value={safeRow[colIndex] || ''}
                        onChange={(e) => handle2DCellChange(rowIndex, colIndex, e.target.value)}
                        className={`w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 ${
                          itemType === 'number' || itemType === 'integer' ? 'text-right' : ''
                        }`}
                        placeholder={itemType === 'number' ? '0' : itemType === 'boolean' ? 'true/false' : '...'}
                        step={itemType === 'integer' ? '1' : 'any'}
                      />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <button
        type="button"
        onClick={handle2DAddRow}
        disabled={maxItems && value.length >= maxItems}
        className="flex items-center px-3 py-1 text-sm text-blue-600 hover:text-blue-700 border border-dashed border-blue-300 rounded hover:border-blue-400 disabled:opacity-50 disabled:cursor-not-allowed"
        title={maxItems && value.length >= maxItems ? `Maximum ${maxItems} rows allowed` : 'Add new row'}
      >
        <PlusIcon className="w-4 h-4 mr-1" />
        Add Row
      </button>
    </div>
  );
});

Matrix2DArrayInput.displayName = 'Matrix2DArrayInput';

export default Matrix2DArrayInput;