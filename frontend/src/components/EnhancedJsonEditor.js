import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { showErrorToast, showSuccessToast } from '../utils/customToast';

const EnhancedJsonEditor = ({ isOpen, onClose, flowData, onSave, readOnly = false }) => {
  const [jsonContent, setJsonContent] = useState('');
  const [error, setError] = useState(null);
  const [isValidJson, setIsValidJson] = useState(true);
  const [lineNumbers, setLineNumbers] = useState([]);
  const textareaRef = useRef(null);
  const lineNumbersRef = useRef(null);

  useEffect(() => {
    if (isOpen && flowData) {
      // Format the JSON with proper indentation
      const formattedJson = JSON.stringify(flowData, null, 2);
      setJsonContent(formattedJson);
      setError(null);
      setIsValidJson(true);
      updateLineNumbers(formattedJson);
    }
  }, [isOpen, flowData]);

  const updateLineNumbers = (content) => {
    const lines = content.split('\n');
    setLineNumbers(lines.map((_, i) => i + 1));
  };

  const handleJsonChange = (e) => {
    const value = e.target.value;
    setJsonContent(value);
    updateLineNumbers(value);
    
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

  const handleScroll = (e) => {
    // Sync scroll position between textarea and line numbers
    if (lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = e.target.scrollTop;
    }
  };

  const handleFileImport = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    // Check if file is JSON
    if (!file.name.endsWith('.json') && file.type !== 'application/json') {
      showErrorToast('Please select a valid JSON file');
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const content = e.target.result;
        // Try to parse to validate it's valid JSON
        let parsed = JSON.parse(content);
        
        // Check if it's in export/import format or direct flow format
        if (parsed.version && parsed.flow) {
          // Export/Import format - validate the nested structure
          if (!parsed.flow.flow_definition) {
            throw new Error('Export format must contain flow.flow_definition');
          }
          if (!parsed.flow.flow_definition.nodes || !Array.isArray(parsed.flow.flow_definition.nodes)) {
            throw new Error('File must contain a "nodes" array in flow_definition');
          }
          if (!parsed.flow.flow_definition.edges || !Array.isArray(parsed.flow.flow_definition.edges)) {
            throw new Error('File must contain an "edges" array in flow_definition');
          }
        } else if (parsed.nodes || parsed.edges) {
          // Direct flow format (legacy) - convert to export format
          parsed = {
            version: '1.0',
            export_timestamp: new Date().toISOString(),
            flow: {
              flow_name: 'Imported Flow',
              description: '',
              category: 'general',
              trigger_config: {},
              flow_definition: {
                nodes: parsed.nodes || [],
                edges: parsed.edges || []
              },
              is_synchronous: false,
              sync_timeout: 30
            },
            metadata: {
              required_applications: [],
              source_instance: {
                mode: 'imported'
              },
              warnings: []
            }
          };
        } else {
          throw new Error('File must be in export format (with version and flow) or contain nodes/edges arrays');
        }

        // Format and set the content
        const formatted = JSON.stringify(parsed, null, 2);
        setJsonContent(formatted);
        updateLineNumbers(formatted);
        setError(null);
        setIsValidJson(true);
        
        showSuccessToast(`Successfully imported ${file.name}`);
      } catch (err) {
        showErrorToast(`Failed to import file: ${err.message}`);
      }
    };

    reader.onerror = () => {
      showErrorToast('Failed to read file');
    };

    reader.readAsText(file);
    
    // Reset the input value so the same file can be imported again
    event.target.value = '';
  };

  const handleSave = () => {
    try {
      const parsedJson = JSON.parse(jsonContent);
      
      // Check if it's in export/import format
      let nodesToValidate, edgesToValidate;
      
      if (parsedJson.version && parsedJson.flow && parsedJson.flow.flow_definition) {
        // Export format
        nodesToValidate = parsedJson.flow.flow_definition.nodes;
        edgesToValidate = parsedJson.flow.flow_definition.edges;
        
        if (!nodesToValidate || !Array.isArray(nodesToValidate)) {
          throw new Error('Flow definition must have a "nodes" array');
        }
        if (!edgesToValidate || !Array.isArray(edgesToValidate)) {
          throw new Error('Flow definition must have an "edges" array');
        }
      } else if (parsedJson.nodes || parsedJson.edges) {
        // Direct format
        nodesToValidate = parsedJson.nodes;
        edgesToValidate = parsedJson.edges;
        
        if (!nodesToValidate || !Array.isArray(nodesToValidate)) {
          throw new Error('Flow must have a "nodes" array');
        }
        if (!edgesToValidate || !Array.isArray(edgesToValidate)) {
          throw new Error('Flow must have an "edges" array');
        }
      } else {
        throw new Error('JSON must be in export format or contain nodes/edges arrays');
      }
      
      // Validate each node has required fields
      nodesToValidate.forEach((node, index) => {
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
      edgesToValidate.forEach((edge, index) => {
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
      updateLineNumbers(formatted);
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

  const insertAtCursor = (text) => {
    if (textareaRef.current) {
      const start = textareaRef.current.selectionStart;
      const end = textareaRef.current.selectionEnd;
      const newContent = jsonContent.substring(0, start) + text + jsonContent.substring(end);
      setJsonContent(newContent);
      updateLineNumbers(newContent);
      
      // Set cursor position after inserted text
      setTimeout(() => {
        textareaRef.current.selectionStart = textareaRef.current.selectionEnd = start + text.length;
        textareaRef.current.focus();
      }, 0);
    }
  };

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[9998]">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full h-[90vh] flex flex-col z-[9999]">
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
                  <>
                    <button
                      onClick={handleFormat}
                      className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                      disabled={!isValidJson}
                    >
                      Format
                    </button>
                    {/* Import from File Button */}
                    <label className="px-3 py-1 text-sm bg-purple-100 hover:bg-purple-200 rounded-md transition-colors cursor-pointer">
                      Import from File
                      <input
                        type="file"
                        accept=".json,application/json"
                        onChange={handleFileImport}
                        className="hidden"
                      />
                    </label>
                    {/* Quick Insert Buttons */}
                    <div className="flex items-center space-x-1 ml-4">
                      <span className="text-xs text-gray-500">Insert:</span>
                      <button
                        onClick={() => insertAtCursor('{\n  "id": "",\n  "type": "",\n  "position": { "x": 0, "y": 0 },\n  "data": {}\n}')}
                        className="px-2 py-1 text-xs bg-blue-100 hover:bg-blue-200 rounded"
                      >
                        Node
                      </button>
                      <button
                        onClick={() => insertAtCursor('{\n  "id": "",\n  "source": "",\n  "target": ""\n}')}
                        className="px-2 py-1 text-xs bg-green-100 hover:bg-green-200 rounded"
                      >
                        Edge
                      </button>
                    </div>
                  </>
                )}
                <button
                  onClick={handleCopy}
                  className="px-3 py-1 text-sm bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  Copy
                </button>
              </div>
              <div className="flex items-center space-x-2">
                {error && (
                  <span className="text-sm text-red-600">{error}</span>
                )}
                {!error && !readOnly && jsonContent && (
                  <span className="text-sm text-green-600">Valid JSON</span>
                )}
              </div>
            </div>

            {/* JSON Editor with Line Numbers */}
            <div className="flex-1 flex border rounded-lg overflow-hidden bg-gray-50">
              {/* Line Numbers */}
              <div 
                ref={lineNumbersRef}
                className="w-12 bg-gray-100 border-r border-gray-200 overflow-hidden"
                style={{ overflow: 'hidden' }}
              >
                <div className="p-4 pr-2 text-right">
                  {lineNumbers.map(num => (
                    <div key={num} className="text-xs text-gray-500 leading-relaxed" style={{ height: '1.5rem' }}>
                      {num}
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Editor */}
              <div className="flex-1 relative">
                <textarea
                  ref={textareaRef}
                  value={jsonContent}
                  onChange={handleJsonChange}
                  onScroll={handleScroll}
                  readOnly={readOnly}
                  className={`absolute inset-0 w-full h-full p-4 font-mono text-sm leading-relaxed bg-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset resize-none ${
                    error ? 'text-red-900' : 'text-gray-900'
                  } ${readOnly ? 'cursor-not-allowed' : ''}`}
                  style={{
                    tabSize: 2,
                    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                    lineHeight: '1.5rem'
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
              <div className="mt-2 p-3 bg-gray-100 rounded-md overflow-x-auto max-h-48">
                <pre className="text-xs font-mono whitespace-pre" style={{ fontFamily: 'Consolas, Monaco, "Courier New", monospace' }}>{`// Export/Import Format (Recommended)
{
  "version": "1.0",
  "export_timestamp": "2024-01-01T00:00:00Z",
  "flow": {
    "flow_name": "My Flow",
    "description": "Flow description",
    "category": "general",
    "trigger_config": {
      "type": "manual|webhook|schedule|event"
      // Type-specific config
    },
    "flow_definition": {
      "nodes": [
        {
          "id": "unique-node-id",
          "type": "trigger|action|condition|transform|response|loop",
          "position": { "x": 100, "y": 100 },
          "data": {
            "label": "Node Label"
            // Type-specific data
          }
        }
      ],
      "edges": [
        {
          "id": "unique-edge-id",
          "source": "source-node-id",
          "target": "target-node-id"
        }
      ]
    },
    "is_synchronous": false,
    "sync_timeout": 30
  },
  "metadata": {
    "required_applications": [],
    "warnings": []
  }
}

// Direct Format (Legacy - auto-converted to export format)
{
  "nodes": [...],
  "edges": [...]
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

export default EnhancedJsonEditor;