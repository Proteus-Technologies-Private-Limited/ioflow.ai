import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { showErrorToast } from '../utils/customToast';
import { showSuccessToast } from '../utils/customToast';

const FlowJsonEditor = ({ isOpen, onClose, flowData, onSave, readOnly = false }) => {
  const [jsonContent, setJsonContent] = useState('');
  const [error, setError] = useState(null);
  const [isValidJson, setIsValidJson] = useState(true);

  useEffect(() => {
    if (isOpen && flowData) {
      // Format the JSON with proper indentation
      const formattedJson = JSON.stringify(flowData, null, 2);
      setJsonContent(formattedJson);
      setError(null);
      setIsValidJson(true);
    }
  }, [isOpen, flowData]);

  const handleJsonChange = (e) => {
    const value = e.target.value;
    setJsonContent(value);
    
    // Validate JSON as user types
    try {
      if (value.trim()) {
        JSON.parse(value);
        setError(null);
        setIsValidJson(true);
      }
    } catch (err) {
      setError(`Invalid JSON: ${err.message}`);
      setIsValidJson(false);
    }
  };

  const handleSave = () => {
    try {
      const parsedJson = JSON.parse(jsonContent);
      
      // Validate flow structure
      if (!parsedJson.nodes || !Array.isArray(parsedJson.nodes)) {
        throw new Error('Flow must have a "nodes" array');
      }
      if (!parsedJson.edges || !Array.isArray(parsedJson.edges)) {
        throw new Error('Flow must have an "edges" array');
      }
      
      // Validate each node has required fields
      parsedJson.nodes.forEach((node, index) => {
        if (!node.id) {
          throw new Error(`Node at index ${index} is missing "id" field`);
        }
        if (!node.type) {
          throw new Error(`Node ${node.id} is missing "type" field`);
        }
        if (!node.position || typeof node.position.x !== 'number' || typeof node.position.y !== 'number') {
          throw new Error(`Node ${node.id} has invalid position`);
        }
        if (!node.data) {
          throw new Error(`Node ${node.id} is missing "data" field`);
        }
      });
      
      // Validate each edge has required fields
      parsedJson.edges.forEach((edge, index) => {
        if (!edge.id) {
          throw new Error(`Edge at index ${index} is missing "id" field`);
        }
        if (!edge.source) {
          throw new Error(`Edge ${edge.id} is missing "source" field`);
        }
        if (!edge.target) {
          throw new Error(`Edge ${edge.id} is missing "target" field`);
        }
      });
      
      onSave(parsedJson);
      showSuccessToast('Flow updated successfully');
      onClose();
    } catch (err) {
      showErrorToast(err.message);
    }
  };

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(jsonContent);
      const formatted = JSON.stringify(parsed, null, 2);
      setJsonContent(formatted);
      setError(null);
      setIsValidJson(true);
    } catch (err) {
      showErrorToast('Cannot format invalid JSON');
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(jsonContent);
    showSuccessToast('JSON copied to clipboard');
  };

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9998]">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col z-[9999]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold text-gray-900">
            {readOnly ? 'View Flow JSON' : 'Edit Flow JSON'}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <XMarkIcon className="h-6 w-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-4 overflow-hidden">
          <div className="h-full flex flex-col">
            {/* Toolbar */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                {!readOnly && (
                  <button
                    onClick={handleFormat}
                    className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                    disabled={!isValidJson}
                  >
                    Format
                  </button>
                )}
                <button
                  onClick={handleCopy}
                  className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  Copy
                </button>
              </div>
              {error && (
                <span className="text-sm text-red-600">{error}</span>
              )}
              {!error && !readOnly && jsonContent && (
                <span className="text-sm text-green-600">Valid JSON</span>
              )}
            </div>

            {/* JSON Editor */}
            <div className="flex-1 relative border rounded-lg overflow-hidden">
              <div className="absolute inset-0 overflow-auto">
                <textarea
                  value={jsonContent}
                  onChange={handleJsonChange}
                  readOnly={readOnly}
                  className={`w-full min-h-full p-4 font-mono text-sm leading-relaxed whitespace-pre focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset resize-none ${
                    error ? 'bg-red-50 text-red-900' : 'bg-gray-50 text-gray-900'
                  } ${readOnly ? 'cursor-not-allowed' : ''}`}
                  style={{
                    minHeight: '100%',
                    tabSize: 2,
                    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                    lineHeight: '1.5'
                  }}
                  spellCheck="false"
                  placeholder="Paste or edit your flow JSON here..."
                />
              </div>
            </div>

            {/* JSON Structure Help */}
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-800">
                JSON Structure Reference
              </summary>
              <div className="mt-2 p-3 bg-gray-100 rounded-md overflow-x-auto">
                <pre className="text-xs font-mono whitespace-pre" style={{ fontFamily: 'Consolas, Monaco, "Courier New", monospace' }}>{`{
  "nodes": [
    {
      "id": "node-1",
      "type": "trigger",
      "position": { "x": 100, "y": 100 },
      "data": {
        "label": "Trigger Node",
        "trigger_type": "manual"
      }
    },
    {
      "id": "node-2",
      "type": "action",
      "position": { "x": 300, "y": 100 },
      "data": {
        "label": "Action Node",
        "action_type": "api_call",
        "appId": "app-id",
        "serviceId": "service-id"
      }
    }
  ],
  "edges": [
    {
      "id": "edge-1",
      "source": "node-1",
      "target": "node-2",
      "type": "smoothstep"
    }
  ]
}`}</pre>
              </div>
            </details>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 p-4 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            Cancel
          </button>
          {!readOnly && (
            <button
              onClick={handleSave}
              disabled={!isValidJson || !jsonContent}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Save Changes
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default FlowJsonEditor;