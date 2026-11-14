import React, { useState, useEffect } from 'react';
import { FolderIcon, InformationCircleIcon } from '@heroicons/react/24/outline';

const FileChangeTriggerConfig = ({ value, onChange, disabled = false }) => {
  const [config, setConfig] = useState({
    folder_path: '',
    listener_type: ['create', 'modify', 'delete'],
    file_pattern: '*',
    recursive: false,
    debounce_seconds: 5,
    ...value
  });

  useEffect(() => {
    if (value) {
      setConfig({
        folder_path: value.folder_path || '',
        listener_type: value.listener_type || ['create', 'modify', 'delete'],
        file_pattern: value.file_pattern || '*',
        recursive: value.recursive || false,
        debounce_seconds: value.debounce_seconds || 5,
      });
    }
  }, [value]);

  const handleChange = (field, newValue) => {
    const updatedConfig = { ...config, [field]: newValue };
    setConfig(updatedConfig);
    onChange(updatedConfig);
  };

  const handleListenerTypeChange = (type) => {
    const currentTypes = config.listener_type || [];
    let newTypes;
    if (currentTypes.includes(type)) {
      newTypes = currentTypes.filter(t => t !== type);
    } else {
      newTypes = [...currentTypes, type];
    }
    handleChange('listener_type', newTypes);
  };

  const commonPatterns = [
    { value: '*', label: 'All files (*)' },
    { value: '*.txt', label: 'Text files (*.txt)' },
    { value: '*.csv', label: 'CSV files (*.csv)' },
    { value: '*.json', label: 'JSON files (*.json)' },
    { value: '*.pdf', label: 'PDF files (*.pdf)' },
    { value: '*.docx', label: 'Word files (*.docx)' },
    { value: '*.xlsx', label: 'Excel files (*.xlsx)' },
    { value: '*.xml', label: 'XML files (*.xml)' },
    { value: '*.log', label: 'Log files (*.log)' },
    { value: 'data_*.csv', label: 'Data CSV files (data_*.csv)' },
    { value: 'report_*.pdf', label: 'Report PDFs (report_*.pdf)' },
  ];

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <InformationCircleIcon className="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">File Change Trigger</p>
            <p>Monitor a folder for file changes. The flow will be triggered when files matching your pattern are created, modified, or deleted.</p>
          </div>
        </div>
      </div>

      {/* Folder Path */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Folder Path <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <FolderIcon className="h-5 w-5 text-gray-400" />
          </div>
          <input
            type="text"
            value={config.folder_path}
            onChange={(e) => handleChange('folder_path', e.target.value)}
            disabled={disabled}
            placeholder="/path/to/watch"
            className="pl-10 block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          />
        </div>
        <p className="mt-1 text-xs text-gray-500">
          Absolute path to the folder to monitor
        </p>
      </div>

      {/* Event Types */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Event Types
        </label>
        <div className="space-y-2">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={config.listener_type?.includes('create')}
              onChange={() => handleListenerTypeChange('create')}
              disabled={disabled}
              className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">File Created</span>
          </label>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={config.listener_type?.includes('modify')}
              onChange={() => handleListenerTypeChange('modify')}
              disabled={disabled}
              className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">File Modified</span>
          </label>
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={config.listener_type?.includes('delete')}
              onChange={() => handleListenerTypeChange('delete')}
              disabled={disabled}
              className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">File Deleted</span>
          </label>
        </div>
      </div>

      {/* File Pattern */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          File Pattern
        </label>
        <select
          value={config.file_pattern}
          onChange={(e) => {
            const selectedValue = e.target.value;
            if (selectedValue === 'custom') {
              handleChange('file_pattern', '');
            } else {
              handleChange('file_pattern', selectedValue);
            }
          }}
          disabled={disabled}
          className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
        >
          {commonPatterns.map(pattern => (
            <option key={pattern.value} value={pattern.value}>
              {pattern.label}
            </option>
          ))}
          <option value="custom">Custom pattern...</option>
        </select>
        
        {(!commonPatterns.some(p => p.value === config.file_pattern)) && (
          <input
            type="text"
            value={config.file_pattern}
            onChange={(e) => handleChange('file_pattern', e.target.value)}
            disabled={disabled}
            placeholder="Enter custom pattern (e.g., *.txt, data_*.csv)"
            className="mt-2 block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          />
        )}
        <p className="mt-1 text-xs text-gray-500">
          Wildcard pattern to match files (e.g., *.csv for CSV files)
        </p>
      </div>

      {/* Recursive */}
      <div>
        <label className="flex items-center">
          <input
            type="checkbox"
            checked={config.recursive}
            onChange={(e) => handleChange('recursive', e.target.checked)}
            disabled={disabled}
            className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          />
          <span className="ml-2 text-sm text-gray-700">
            Monitor subdirectories recursively
          </span>
        </label>
        <p className="mt-1 ml-6 text-xs text-gray-500">
          Also watch files in all subdirectories
        </p>
      </div>

      {/* Debounce */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Debounce (seconds)
        </label>
        <input
          type="number"
          min="0"
          max="60"
          value={config.debounce_seconds}
          onChange={(e) => handleChange('debounce_seconds', parseInt(e.target.value) || 0)}
          disabled={disabled}
          className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
        />
        <p className="mt-1 text-xs text-gray-500">
          Minimum time between triggers for the same file (0 to disable)
        </p>
      </div>

      {/* Preview */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-700 mb-2">Configuration Summary</h4>
        <div className="text-xs text-gray-600 space-y-1">
          <p><span className="font-medium">Monitoring:</span> {config.folder_path || '(not set)'}</p>
          <p><span className="font-medium">Pattern:</span> {config.file_pattern}</p>
          <p><span className="font-medium">Events:</span> {config.listener_type?.join(', ') || 'none'}</p>
          <p><span className="font-medium">Recursive:</span> {config.recursive ? 'Yes' : 'No'}</p>
          <p><span className="font-medium">Debounce:</span> {config.debounce_seconds}s</p>
        </div>
      </div>

      {/* Variables Available */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-green-800 mb-2">Available Variables in Flow</h4>
        <div className="text-xs text-green-700 space-y-1 font-mono">
          <p>• input.file_path - Full path of the changed file</p>
          <p>• input.file_name - Name of the file</p>
          <p>• input.event_type - Type of change (create/modify/delete)</p>
          <p>• input.timestamp - When the event occurred</p>
          <p>• input.file_size - Size of the file (if applicable)</p>
        </div>
      </div>
    </div>
  );
};

export default FileChangeTriggerConfig;