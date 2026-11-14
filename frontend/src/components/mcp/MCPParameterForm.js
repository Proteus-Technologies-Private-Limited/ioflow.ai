import React from 'react';
import { InformationCircleIcon } from '@heroicons/react/24/outline';

const MCPParameterForm = ({ parameters, values, onChange }) => {
  const renderField = (name, property) => {
    const isRequired = parameters.required?.includes(name);
    const value = values[name] || '';

    // Determine field type based on property type
    const getFieldType = () => {
      if (property.type === 'boolean') return 'checkbox';
      if (property.type === 'number' || property.type === 'integer') return 'number';
      if (property.type === 'object' || property.type === 'array') return 'json';
      if (property.enum) return 'select';
      return 'text';
    };

    const fieldType = getFieldType();

    return (
      <div key={name} className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium text-gray-700">
            {name}
            {isRequired && <span className="text-red-500 ml-1">*</span>}
          </label>
          {property.description && (
            <div className="group relative">
              <InformationCircleIcon className="h-4 w-4 text-gray-400 cursor-help" />
              <div className="absolute right-0 w-64 p-2 mt-1 text-xs bg-gray-800 text-white rounded-md shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                {property.description}
              </div>
            </div>
          )}
        </div>

        {fieldType === 'checkbox' ? (
          <input
            type="checkbox"
            checked={value === true}
            onChange={(e) => onChange(name, e.target.checked)}
            className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
          />
        ) : fieldType === 'select' ? (
          <select
            value={value}
            onChange={(e) => onChange(name, e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
          >
            <option value="">Select...</option>
            {property.enum.map(option => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        ) : fieldType === 'json' ? (
          <textarea
            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : value}
            onChange={(e) => {
              try {
                const parsed = JSON.parse(e.target.value);
                onChange(name, parsed);
              } catch {
                onChange(name, e.target.value);
              }
            }}
            rows={4}
            placeholder={`Enter valid JSON for ${property.type}`}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500 font-mono text-sm"
          />
        ) : fieldType === 'number' ? (
          <input
            type="number"
            value={value}
            onChange={(e) => onChange(name, e.target.value ? Number(e.target.value) : '')}
            step={property.type === 'integer' ? 1 : 'any'}
            min={property.minimum}
            max={property.maximum}
            placeholder={property.default !== undefined ? `Default: ${property.default}` : ''}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
          />
        ) : (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(name, e.target.value)}
            placeholder={property.default !== undefined ? `Default: ${property.default}` : ''}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary-500 focus:border-primary-500"
          />
        )}

        {property.type && (
          <p className="text-xs text-gray-500">
            Type: {property.type}
            {property.minimum !== undefined && ` (min: ${property.minimum})`}
            {property.maximum !== undefined && ` (max: ${property.maximum})`}
          </p>
        )}
      </div>
    );
  };

  if (!parameters.properties) {
    return (
      <p className="text-sm text-gray-500">No parameters defined</p>
    );
  }

  // Sort parameters: required first, then alphabetical
  const sortedParams = Object.entries(parameters.properties).sort(([a], [b]) => {
    const aRequired = parameters.required?.includes(a);
    const bRequired = parameters.required?.includes(b);
    
    if (aRequired && !bRequired) return -1;
    if (!aRequired && bRequired) return 1;
    return a.localeCompare(b);
  });

  return (
    <div className="space-y-4">
      {sortedParams.map(([name, property]) => renderField(name, property))}
    </div>
  );
};

export default MCPParameterForm;