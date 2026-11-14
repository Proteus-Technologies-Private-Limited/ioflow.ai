import React from 'react';
import { ExclamationTriangleIcon, ChevronDownIcon, ChevronRightIcon, CodeBracketIcon } from '@heroicons/react/24/outline';
import { formatJsonString } from '../../utils/jsonFormatter';

const ValidationErrorDisplay = ({ errors, warnings, onClose }) => {
  const [expandedErrors, setExpandedErrors] = React.useState({});
  const [expandedWarnings, setExpandedWarnings] = React.useState({});

  const toggleExpanded = (index, type) => {
    if (type === 'error') {
      setExpandedErrors(prev => ({ ...prev, [index]: !prev[index] }));
    } else {
      setExpandedWarnings(prev => ({ ...prev, [index]: !prev[index] }));
    }
  };

  const formatPath = (path) => {
    if (!path || !Array.isArray(path)) return '';
    return path.map((part, index) => {
      if (typeof part === 'number') {
        return `[${part}]`;
      }
      return index === 0 ? part : `.${part}`;
    }).join('');
  };

  const formatFieldName = (path) => {
    if (!path || !Array.isArray(path)) return 'Field';
    const lastPart = path[path.length - 1];
    
    // Convert snake_case to Title Case
    const formatted = lastPart
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
    
    // Add context for nested fields
    if (path.length > 1) {
      const parent = path[path.length - 2];
      if (typeof parent === 'number') {
        return `${formatted} (item ${parent + 1})`;
      }
    }
    
    return formatted;
  };

  const renderError = (error, index) => {
    const isExpanded = expandedErrors[index];
    const hasDetails = error.schema_path || error.path?.length > 1;
    const isJsonError = error.message.includes('is not of type') && error.message.includes('\\n');
    
    return (
      <div key={index} className="border-l-4 border-red-500 bg-red-50 p-4 mb-2">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
          </div>
          <div className="ml-3 flex-1">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-red-800">
                {formatFieldName(error.path)}
              </p>
              {(hasDetails || isJsonError) && (
                <button
                  onClick={() => toggleExpanded(index, 'error')}
                  className="ml-2 text-red-600 hover:text-red-800"
                >
                  {isExpanded ? (
                    <ChevronDownIcon className="h-4 w-4" />
                  ) : (
                    <ChevronRightIcon className="h-4 w-4" />
                  )}
                </button>
              )}
            </div>
            
            {isJsonError ? (
              <>
                <p className="mt-1 text-sm text-red-700">
                  This field should be a JSON object, not a string
                </p>
                {isExpanded && (
                  <div className="mt-2">
                    <p className="text-xs text-red-600 mb-1">Current value (JSON string):</p>
                    <pre className="text-xs bg-red-100 p-2 rounded overflow-x-auto">
                      {formatJsonString(error.message.match(/'([^']+)'/)?.[1] || '')}
                    </pre>
                    <p className="text-xs text-red-600 mt-2">
                      <CodeBracketIcon className="inline h-3 w-3 mr-1" />
                      This should be parsed JSON, not a JSON string
                    </p>
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="mt-1 text-sm text-red-700">{error.message}</p>
                
                {isExpanded && hasDetails && (
                  <div className="mt-2 text-xs text-red-600 bg-red-100 p-2 rounded">
                    <p className="font-mono">Path: {formatPath(error.path)}</p>
                    {error.schema_path && (
                      <p className="font-mono mt-1">Schema: {formatPath(error.schema_path)}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderWarning = (warning, index) => {
    const isExpanded = expandedWarnings[index];
    
    return (
      <div key={index} className="border-l-4 border-yellow-500 bg-yellow-50 p-4 mb-2">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <ExclamationTriangleIcon className="h-5 w-5 text-yellow-400" />
          </div>
          <div className="ml-3 flex-1">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-yellow-800">
                {formatFieldName(warning.path)}
              </p>
              {warning.path && (
                <button
                  onClick={() => toggleExpanded(index, 'warning')}
                  className="ml-2 text-yellow-600 hover:text-yellow-800"
                >
                  {isExpanded ? (
                    <ChevronDownIcon className="h-4 w-4" />
                  ) : (
                    <ChevronRightIcon className="h-4 w-4" />
                  )}
                </button>
              )}
            </div>
            <p className="mt-1 text-sm text-yellow-700">{warning.message}</p>
            
            {isExpanded && warning.path && (
              <div className="mt-2 text-xs text-yellow-600 bg-yellow-100 p-2 rounded">
                <p className="font-mono">Path: {formatPath(warning.path)}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-lg font-semibold text-gray-900">Validation Results</h4>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ×
          </button>
        )}
      </div>
      
      {errors && errors.length > 0 && (
        <div className="mb-4">
          <h5 className="text-sm font-medium text-red-800 mb-2">
            Errors ({errors.length})
          </h5>
          <div className="space-y-2">
            {errors.map((error, index) => renderError(error, index))}
          </div>
        </div>
      )}
      
      {warnings && warnings.length > 0 && (
        <div>
          <h5 className="text-sm font-medium text-yellow-800 mb-2">
            Warnings ({warnings.length})
          </h5>
          <div className="space-y-2">
            {warnings.map((warning, index) => renderWarning(warning, index))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ValidationErrorDisplay;