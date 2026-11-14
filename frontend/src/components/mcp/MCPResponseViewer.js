import React, { useState } from 'react';
import { 
  ChevronRightIcon, 
  ChevronDownIcon,
  DocumentDuplicateIcon,
  ArrowDownTrayIcon 
} from '@heroicons/react/24/outline';
import toast from 'react-hot-toast';

const MCPResponseViewer = ({ response }) => {
  const [expandedKeys, setExpandedKeys] = useState(new Set());

  const toggleExpanded = (key) => {
    const newExpanded = new Set(expandedKeys);
    if (newExpanded.has(key)) {
      newExpanded.delete(key);
    } else {
      newExpanded.add(key);
    }
    setExpandedKeys(newExpanded);
  };

  const copyToClipboard = (value) => {
    const text = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
    navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  const downloadAsJson = () => {
    const blob = new Blob([JSON.stringify(response, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mcp-response-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success('Downloaded as JSON');
  };

  const renderValue = (value, key = '', depth = 0) => {
    const fullKey = key;
    const isExpanded = expandedKeys.has(fullKey);

    if (value === null) {
      return <span className="text-gray-400 italic">null</span>;
    }

    if (value === undefined) {
      return <span className="text-gray-400 italic">undefined</span>;
    }

    if (typeof value === 'boolean') {
      return (
        <span className={value ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
          {String(value)}
        </span>
      );
    }

    if (typeof value === 'string') {
      // Check if it's a URL
      if (value.match(/^https?:\/\//)) {
        return (
          <a 
            href={value} 
            target="_blank" 
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline"
          >
            {value}
          </a>
        );
      }
      // Check if it's JSON string
      try {
        const parsed = JSON.parse(value);
        if (typeof parsed === 'object') {
          return (
            <div className="inline-block">
              <button
                onClick={() => toggleExpanded(fullKey)}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                {isExpanded ? 'Hide JSON' : 'Show JSON'}
              </button>
              {isExpanded && (
                <div className="mt-2 pl-4 border-l-2 border-gray-200">
                  {renderValue(parsed, fullKey + '_parsed', depth)}
                </div>
              )}
            </div>
          );
        }
      } catch {
        // Not JSON, render as string
      }
      return <span className="text-gray-900">"{value}"</span>;
    }

    if (typeof value === 'number') {
      return <span className="text-blue-600 font-medium">{value}</span>;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <span className="text-gray-400">[]</span>;
      }

      return (
        <div className="inline-block">
          <button
            onClick={() => toggleExpanded(fullKey)}
            className="inline-flex items-center text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <ChevronDownIcon className="h-4 w-4" />
            ) : (
              <ChevronRightIcon className="h-4 w-4" />
            )}
            <span className="ml-1 text-gray-500">
              Array[{value.length}]
            </span>
          </button>
          {isExpanded && (
            <div className="mt-1 ml-4 space-y-1">
              {value.map((item, index) => (
                <div key={index} className="flex items-start">
                  <span className="text-gray-500 mr-2 font-mono text-xs">
                    [{index}]:
                  </span>
                  <div className="flex-1">
                    {renderValue(item, `${fullKey}[${index}]`, depth + 1)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (typeof value === 'object') {
      const entries = Object.entries(value);
      if (entries.length === 0) {
        return <span className="text-gray-400">{'{}'}</span>;
      }

      return (
        <div className="inline-block w-full">
          <button
            onClick={() => toggleExpanded(fullKey)}
            className="inline-flex items-center text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <ChevronDownIcon className="h-4 w-4" />
            ) : (
              <ChevronRightIcon className="h-4 w-4" />
            )}
            <span className="ml-1 text-gray-500">
              Object{entries.length > 0 && `{${entries.length}}`}
            </span>
          </button>
          {isExpanded && (
            <div className="mt-1 ml-4 space-y-1">
              {entries.map(([k, v]) => (
                <div key={k} className="flex items-start">
                  <span className="text-purple-600 font-medium mr-2">
                    {k}:
                  </span>
                  <div className="flex-1">
                    {renderValue(v, `${fullKey}.${k}`, depth + 1)}
                  </div>
                  <button
                    onClick={() => copyToClipboard(v)}
                    className="ml-2 text-gray-400 hover:text-gray-600"
                    title="Copy value"
                  >
                    <DocumentDuplicateIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return <span className="text-gray-900">{String(value)}</span>;
  };

  // Auto-expand first level for better visibility
  React.useEffect(() => {
    if (response && typeof response === 'object') {
      setExpandedKeys(new Set(['root']));
    }
  }, [response]);

  return (
    <div className="space-y-4">
      <div className="flex justify-end space-x-2">
        <button
          onClick={() => copyToClipboard(response)}
          className="inline-flex items-center px-3 py-1 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
        >
          <DocumentDuplicateIcon className="h-4 w-4 mr-1" />
          Copy All
        </button>
        <button
          onClick={downloadAsJson}
          className="inline-flex items-center px-3 py-1 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
        >
          <ArrowDownTrayIcon className="h-4 w-4 mr-1" />
          Download
        </button>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-4 font-mono text-sm overflow-x-auto">
        {renderValue(response, 'root')}
      </div>

      {/* Response Summary */}
      {response && typeof response === 'object' && (
        <div className="text-xs text-gray-500 space-y-1">
          <p>Response type: {Array.isArray(response) ? 'Array' : 'Object'}</p>
          {Array.isArray(response) && <p>Items: {response.length}</p>}
          {!Array.isArray(response) && <p>Keys: {Object.keys(response).length}</p>}
        </div>
      )}
    </div>
  );
};

export default MCPResponseViewer;