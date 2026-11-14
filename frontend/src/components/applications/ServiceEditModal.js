import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import {
  XMarkIcon,
  InformationCircleIcon,
  DocumentTextIcon,
  CodeBracketIcon
} from '@heroicons/react/24/outline';
import { showSuccessToast, showErrorToast } from '../../utils/customToast';
import CodeBlock from '../CodeBlock';

const ServiceEditModal = ({ service, application, onClose, onSave }) => {
  const [activeTab, setActiveTab] = useState('basic');
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    display_name: '',
    description: '',
    input_schema: {},
    output_schema: {},
    sample_input: {},
    sample_output: {},
    timeout_seconds: 30,
    is_active: true
  });
  const [jsonErrors, setJsonErrors] = useState({});

  useEffect(() => {
    if (service) {
      // Parse service data
      const parseJsonField = (field) => {
        if (!field) return {};
        if (typeof field === 'string') {
          try {
            return JSON.parse(field);
          } catch {
            return {};
          }
        }
        return field;
      };

      setFormData({
        display_name: service.display_name || '',
        description: service.description || '',
        input_schema: parseJsonField(service.input_schema),
        output_schema: parseJsonField(service.output_schema),
        sample_input: parseJsonField(service.sample_input),
        sample_output: parseJsonField(service.sample_output),
        timeout_seconds: service.timeout_seconds || 30,
        is_active: service.is_active !== false
      });
    }
  }, [service]);

  if (!service) return null;

  const tabs = [
    { id: 'basic', name: 'Basic Info', icon: InformationCircleIcon },
    { id: 'schemas', name: 'Schemas', icon: DocumentTextIcon },
    { id: 'samples', name: 'Sample Data', icon: CodeBracketIcon }
  ];

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleJsonChange = (field, value) => {
    try {
      const parsed = JSON.parse(value);
      setFormData(prev => ({
        ...prev,
        [field]: parsed
      }));
      setJsonErrors(prev => ({
        ...prev,
        [field]: null
      }));
    } catch (err) {
      setJsonErrors(prev => ({
        ...prev,
        [field]: `Invalid JSON: ${err.message}`
      }));
    }
  };

  const formatJson = (field) => {
    try {
      const formatted = JSON.stringify(formData[field], null, 2);
      return formatted;
    } catch {
      return '{}';
    }
  };

  const handleSave = async () => {
    // Check for JSON errors
    if (Object.values(jsonErrors).some(error => error)) {
      showErrorToast('Please fix JSON errors before saving');
      return;
    }

    setLoading(true);
    try {
      const updateData = {
        display_name: formData.display_name,
        description: formData.description,
        input_schema: formData.input_schema,
        output_schema: formData.output_schema,
        sample_input: formData.sample_input,
        sample_output: formData.sample_output,
        timeout_seconds: formData.timeout_seconds,
        is_active: formData.is_active
      };

      await onSave(service.service_id, updateData);
      showSuccessToast('Service updated successfully');
      onClose();
    } catch (error) {
      showErrorToast(error.message || 'Failed to update service');
    } finally {
      setLoading(false);
    }
  };

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9998]">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col z-[9999]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-medium text-gray-900">Edit Service</h2>
            <p className="text-sm text-gray-500">{service.service_name}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="w-6 h-6" />
          </button>
        </div>

        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6" aria-label="Tabs">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`
                  flex items-center py-2 px-1 border-b-2 font-medium text-sm
                  ${activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }
                `}
              >
                <tab.icon className="w-4 h-4 mr-2" />
                {tab.name}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'basic' && (
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Display Name
                </label>
                <input
                  type="text"
                  value={formData.display_name}
                  onChange={(e) => handleInputChange('display_name', e.target.value)}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => handleInputChange('description', e.target.value)}
                  rows={3}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Timeout (seconds)
                </label>
                <input
                  type="number"
                  value={formData.timeout_seconds}
                  onChange={(e) => handleInputChange('timeout_seconds', parseInt(e.target.value))}
                  min={1}
                  max={600}
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
                />
              </div>

              <div className="flex items-center">
                <input
                  id="is_active"
                  type="checkbox"
                  checked={formData.is_active}
                  onChange={(e) => handleInputChange('is_active', e.target.checked)}
                  className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                />
                <label htmlFor="is_active" className="ml-2 block text-sm text-gray-900">
                  Service is active
                </label>
              </div>
            </div>
          )}

          {activeTab === 'schemas' && (
            <div className="space-y-6">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Input Schema (JSON Schema)
                  </label>
                  {jsonErrors.input_schema && (
                    <span className="text-xs text-red-600">{jsonErrors.input_schema}</span>
                  )}
                </div>
                <textarea
                  value={formatJson('input_schema')}
                  onChange={(e) => handleJsonChange('input_schema', e.target.value)}
                  rows={10}
                  className={`
                    font-mono text-xs block w-full rounded-md shadow-sm
                    ${jsonErrors.input_schema 
                      ? 'border-red-300 focus:border-red-500 focus:ring-red-500' 
                      : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                    }
                  `}
                />
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Output Schema (JSON Schema)
                  </label>
                  {jsonErrors.output_schema && (
                    <span className="text-xs text-red-600">{jsonErrors.output_schema}</span>
                  )}
                </div>
                <textarea
                  value={formatJson('output_schema')}
                  onChange={(e) => handleJsonChange('output_schema', e.target.value)}
                  rows={10}
                  className={`
                    font-mono text-xs block w-full rounded-md shadow-sm
                    ${jsonErrors.output_schema 
                      ? 'border-red-300 focus:border-red-500 focus:ring-red-500' 
                      : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                    }
                  `}
                />
              </div>
            </div>
          )}

          {activeTab === 'samples' && (
            <div className="space-y-6">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Sample Input (Example JSON)
                  </label>
                  {jsonErrors.sample_input && (
                    <span className="text-xs text-red-600">{jsonErrors.sample_input}</span>
                  )}
                </div>
                <textarea
                  value={formatJson('sample_input')}
                  onChange={(e) => handleJsonChange('sample_input', e.target.value)}
                  rows={10}
                  className={`
                    font-mono text-xs block w-full rounded-md shadow-sm
                    ${jsonErrors.sample_input 
                      ? 'border-red-300 focus:border-red-500 focus:ring-red-500' 
                      : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                    }
                  `}
                  placeholder='{"key": "value"}'
                />
                <p className="mt-1 text-xs text-gray-500">
                  Provide an example of valid input data for this service
                </p>
              </div>

              <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    Sample Output (Example JSON)
                  </label>
                  {jsonErrors.sample_output && (
                    <span className="text-xs text-red-600">{jsonErrors.sample_output}</span>
                  )}
                </div>
                <textarea
                  value={formatJson('sample_output')}
                  onChange={(e) => handleJsonChange('sample_output', e.target.value)}
                  rows={10}
                  className={`
                    font-mono text-xs block w-full rounded-md shadow-sm
                    ${jsonErrors.sample_output 
                      ? 'border-red-300 focus:border-red-500 focus:ring-red-500' 
                      : 'border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
                    }
                  `}
                  placeholder='{"result": "success", "data": {...}}'
                />
                <p className="mt-1 text-xs text-gray-500">
                  Provide an example of the expected output from this service
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            disabled={loading}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700 disabled:opacity-50"
            disabled={loading || Object.values(jsonErrors).some(error => error)}
          >
            {loading ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ServiceEditModal;