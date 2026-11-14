import React, { useState } from 'react';
import { XMarkIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline';

const VariablePickerModal = ({ isOpen, onClose, onSelect, availableVariables = {} }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedPath, setSelectedPath] = useState('');

  if (!isOpen) return null;

  // Common variables that are always available
  const commonVariables = {
    input: {
      description: 'Variables from the trigger or manual input',
      example: '{{input.userName}}',
      subfields: Object.keys(availableVariables.input || {})
    },
    data: {
      description: 'Current flow data',
      example: '{{data.result}}',
      subfields: []
    },
    node_outputs: {
      description: 'Outputs from previous nodes',
      example: '{{node_outputs.node_id.fieldName}}',
      subfields: Object.keys(availableVariables.node_outputs || {})
    }
  };

  const handleSelect = () => {
    if (selectedPath) {
      onSelect(selectedPath);
      onClose();
      setSelectedPath('');
      setSearchTerm('');
    }
  };

  const filteredVariables = Object.entries(commonVariables).filter(([key, value]) =>
    key.toLowerCase().includes(searchTerm.toLowerCase()) ||
    value.description.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        <div className="px-4 py-3 border-b flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">Insert Variable</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4">
          {/* Search */}
          <div className="relative mb-4">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" />
            </div>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              placeholder="Search variables..."
            />
          </div>

          {/* Variable List */}
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {filteredVariables.map(([key, value]) => (
              <div key={key} className="border rounded-lg p-3">
                <div className="font-medium text-gray-900">{key}</div>
                <div className="text-sm text-gray-500 mt-1">{value.description}</div>
                <div className="text-xs text-gray-400 mt-1">Example: {value.example}</div>
                
                {value.subfields.length > 0 && (
                  <div className="mt-2">
                    <div className="text-xs font-medium text-gray-700 mb-1">Available fields:</div>
                    <div className="flex flex-wrap gap-1">
                      {value.subfields.map((field) => (
                        <button
                          key={field}
                          onClick={() => setSelectedPath(`${key}.${field}`)}
                          className={`text-xs px-2 py-1 rounded ${
                            selectedPath === `${key}.${field}`
                              ? 'bg-blue-100 text-blue-700 border border-blue-300'
                              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                          }`}
                        >
                          {field}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                
                {value.subfields.length === 0 && (
                  <button
                    onClick={() => setSelectedPath(key)}
                    className={`mt-2 text-xs px-2 py-1 rounded ${
                      selectedPath === key
                        ? 'bg-blue-100 text-blue-700 border border-blue-300'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    Use {key}
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Custom Path Input */}
          <div className="mt-4 pt-4 border-t">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Or enter custom path:
            </label>
            <input
              type="text"
              value={selectedPath}
              onChange={(e) => setSelectedPath(e.target.value)}
              placeholder="e.g., input.customField"
              className="block w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        <div className="px-4 py-3 border-t flex justify-end space-x-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSelect}
            disabled={!selectedPath}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-600 border border-transparent rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Insert Variable
          </button>
        </div>
      </div>
    </div>
  );
};

export default VariablePickerModal;