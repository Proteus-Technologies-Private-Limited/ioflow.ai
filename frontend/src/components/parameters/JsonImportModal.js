import React, { useState } from 'react';
import { XMarkIcon, CheckCircleIcon } from '@heroicons/react/24/outline';
import { flattenJsonSchema } from '../../utils/schemaUtils';

const JsonImportModal = ({ isOpen, onClose, onImport }) => {
  const [jsonInput, setJsonInput] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const analyzeJsonStructure = (obj, path = '') => {
    // Convert sample JSON to JSON Schema format
    const convertToJsonSchema = (value, key = 'root') => {
      const getFieldType = (val) => {
        if (val === null) return 'null';
        if (Array.isArray(val)) return 'array';
        if (typeof val === 'object') return 'object';
        if (typeof val === 'boolean') return 'boolean';
        if (typeof val === 'number') return Number.isInteger(val) ? 'integer' : 'number';
        if (typeof val === 'string') {
          // Try to detect date strings
          if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(val)) return 'string';
          if (/^\d{4}-\d{2}-\d{2}$/.test(val)) return 'string';
          return 'string';
        }
        return 'string';
      };

      const type = getFieldType(value);
      const schema = { type };

      if (type === 'object' && value !== null) {
        schema.properties = {};
        schema.description = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        Object.entries(value).forEach(([k, v]) => {
          schema.properties[k] = convertToJsonSchema(v, k);
        });
      } else if (type === 'array' && value.length > 0) {
        schema.items = convertToJsonSchema(value[0], key);
        schema.description = `Array of ${getFieldType(value[0])}s`;
      } else {
        const friendlyName = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        schema.description = friendlyName;
        
        // Add format hints for specific data types
        if (type === 'string' && value) {
          if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) {
            schema.format = 'date-time';
          } else if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
            schema.format = 'date';
          } else if (/^[^@]+@[^@]+\.[^@]+$/.test(value)) {
            schema.format = 'email';
          } else if (/^https?:\/\//.test(value)) {
            schema.format = 'uri';
          }
        }
      }

      return schema;
    };

    // Create JSON Schema from the sample data
    const jsonSchema = {
      type: 'object',
      properties: {}
    };

    Object.entries(obj).forEach(([key, value]) => {
      jsonSchema.properties[key] = convertToJsonSchema(value, key);
    });

    // Use the flattenJsonSchema utility to convert to field list
    return flattenJsonSchema(jsonSchema);
  };

  const handleImport = () => {
    try {
      setError('');
      const parsedJson = JSON.parse(jsonInput);
      
      if (typeof parsedJson !== 'object' || parsedJson === null) {
        setError('JSON must be an object');
        return;
      }

      const fields = analyzeJsonStructure(parsedJson);
      onImport(fields);
      setJsonInput('');
      setSuccess(true);
      setError('');
      
      // Close after a short delay to show success
      setTimeout(() => {
        onClose();
        setSuccess(false);
      }, 1500);
    } catch (e) {
      setError(`Invalid JSON: ${e.message}`);
    }
  };

  const formatJson = () => {
    try {
      const parsed = JSON.parse(jsonInput);
      setJsonInput(JSON.stringify(parsed, null, 2));
      setError('');
    } catch (e) {
      setError(`Invalid JSON: ${e.message}`);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[100]">
      <div className="bg-white rounded-lg max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">Import Schema from JSON</h3>
          <button
            type="button"
            onClick={() => {
              onClose();
              setSuccess(false);
              setError('');
            }}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Paste your sample JSON data
            </label>
            <p className="text-sm text-gray-500 mb-3">
              The structure will be analyzed to create a schema with appropriate field types.
            </p>
            <textarea
              value={jsonInput}
              onChange={(e) => setJsonInput(e.target.value)}
              className="w-full h-64 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono text-sm"
              placeholder={`{
  "customer_id": "12345",
  "order_date": "2024-06-24",
  "items": [
    {
      "product_id": "abc123",
      "quantity": 2,
      "price": 29.99
    }
  ],
  "total": 59.98,
  "is_premium": true
}`}
            />
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md flex items-center">
              <CheckCircleIcon className="w-5 h-5 text-green-600 mr-2" />
              <p className="text-sm text-green-600">Schema imported successfully! Fields have been added.</p>
            </div>
          )}

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="text-sm font-medium text-blue-900 mb-2">How it works:</h4>
            <ul className="list-disc list-inside text-sm text-blue-700 space-y-1">
              <li>Object properties become individual fields</li>
              <li>Field types are automatically detected (string, number, boolean, date, array, object)</li>
              <li>Nested objects are flattened with dot notation (e.g., address.city)</li>
              <li>Arrays are detected and their item type is inferred</li>
              <li>Sample values are included in field descriptions</li>
            </ul>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-gray-200 flex justify-between">
          <button
            type="button"
            onClick={formatJson}
            className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Format JSON
          </button>
          <div className="space-x-3">
            <button
              type="button"
              onClick={() => {
                onClose();
                setSuccess(false);
                setError('');
              }}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleImport}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700"
              disabled={!jsonInput.trim()}
            >
              Import Schema
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default JsonImportModal;