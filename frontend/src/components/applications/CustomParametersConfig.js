import React, { useState } from 'react';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/outline';

const CustomParametersConfig = ({ parameters = {}, onChange, title = "Custom Parameters", onGetPendingParam }) => {
  const [newParam, setNewParam] = useState({ key: '', value: '', type: 'header' });
  
  // Create a ref to store the latest newParam value
  const newParamRef = React.useRef(newParam);
  newParamRef.current = newParam;
  
  // Set up the callback once on mount
  React.useEffect(() => {
    if (onGetPendingParam) {
      onGetPendingParam(() => {
        // Use ref to get the latest value
        const current = newParamRef.current;
        if (current.key && current.value) {
          return current;
        }
        return null;
      });
    }
  }, [onGetPendingParam]); // Only run when callback function changes

  const paramTypes = [
    { value: 'header', label: 'Header', description: 'Added to request headers' },
    { value: 'query', label: 'Query Parameter', description: 'Added to URL query string' },
    { value: 'body', label: 'Body Parameter', description: 'Added to request body' }
  ];

  const handleAdd = () => {
    if (newParam.key && newParam.value) {
      const updatedParams = { ...parameters };
      
      // Initialize the type object if it doesn't exist
      if (!updatedParams[newParam.type]) {
        updatedParams[newParam.type] = {};
      }
      
      // Add the new parameter
      updatedParams[newParam.type][newParam.key] = newParam.value;
      
      onChange(updatedParams);
      setNewParam({ key: '', value: '', type: 'header' });
    }
  };

  const handleRemove = (type, key) => {
    const updatedParams = { ...parameters };
    if (updatedParams[type]) {
      delete updatedParams[type][key];
      if (Object.keys(updatedParams[type]).length === 0) {
        delete updatedParams[type];
      }
      onChange(updatedParams);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="space-y-4">
      <h4 className="text-sm font-medium text-gray-900">{title}</h4>
      
      {/* Display existing parameters */}
      <div className="space-y-3">
        {Object.entries(parameters).map(([type, params]) => (
          <div key={type} className="bg-gray-50 rounded-lg p-3">
            <h5 className="text-xs font-medium text-gray-700 mb-2 capitalize">
              {paramTypes.find(pt => pt.value === type)?.label || type}
            </h5>
            <div className="space-y-2">
              {Object.entries(params).map(([key, value]) => (
                <div key={`${type}-${key}`} className="flex items-center justify-between bg-white rounded-md px-3 py-2 border border-gray-200">
                  <div className="flex-1">
                    <span className="text-sm font-mono text-gray-900">{key}</span>
                    <span className="text-sm text-gray-500 mx-2">=</span>
                    <span className="text-sm font-mono text-gray-700">{value}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemove(type, key)}
                    className="ml-2 text-red-600 hover:text-red-800"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Add new parameter form */}
      <div className="border-t pt-4">
        <h5 className="text-sm font-medium text-gray-700 mb-3">Add Custom Parameter</h5>
        <div className="grid grid-cols-12 gap-2">
          <div className="col-span-3">
            <select
              value={newParam.type}
              onChange={(e) => setNewParam({ ...newParam, type: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              {paramTypes.map(type => (
                <option key={type.value} value={type.value}>{type.label}</option>
              ))}
            </select>
          </div>
          <div className="col-span-4">
            <input
              type="text"
              value={newParam.key}
              onChange={(e) => setNewParam({ ...newParam, key: e.target.value })}
              onKeyPress={handleKeyPress}
              placeholder="Parameter name"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <div className="col-span-4">
            <input
              type="text"
              value={newParam.value}
              onChange={(e) => setNewParam({ ...newParam, value: e.target.value })}
              onKeyPress={handleKeyPress}
              placeholder="Parameter value"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <div className="col-span-1">
            <button
              type="button"
              onClick={handleAdd}
              disabled={!newParam.key || !newParam.value}
              className={`w-full px-3 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center ${
                newParam.key && newParam.value 
                  ? 'bg-indigo-600 text-white hover:bg-indigo-700 animate-pulse' 
                  : 'bg-indigo-600 text-white hover:bg-indigo-700'
              }`}
              title={newParam.key && newParam.value ? "Click to add this parameter" : "Enter key and value first"}
            >
              <PlusIcon className="h-5 w-5" />
            </button>
          </div>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          {newParam.key && newParam.value ? (
            <span className="text-indigo-600 font-medium">Click the + button to add this parameter</span>
          ) : (
            paramTypes.find(t => t.value === newParam.type)?.description
          )}
        </p>
      </div>
    </div>
  );
};

export default CustomParametersConfig;