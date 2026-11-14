import React, { useState, useCallback, useMemo } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import { autocompletion } from '@codemirror/autocomplete';
import {
  VariableIcon,
  CodeBracketIcon,
  InformationCircleIcon,
  ChevronRightIcon,
  ChevronDownIcon,
} from '@heroicons/react/24/outline';

const TransformCodeEditor = ({
  value,
  onChange,
  availableVariables = {},
  placeholder = '',
  theme = 'light'
}) => {
  const [showVariablePanel, setShowVariablePanel] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState({
    input: true,
    global: false,
    node_outputs: false
  });

  // Create autocomplete suggestions from available variables
  const createCompletions = useCallback(() => {
    const completions = [];
    
    // Add built-in objects
    completions.push(
      { label: 'input', type: 'variable', info: 'Data from previous node' },
      { label: 'local', type: 'variable', info: 'Local variables dictionary' },
      { label: 'global', type: 'variable', info: 'Global flow variables' },
      { label: 'node_outputs', type: 'variable', info: 'Outputs from all nodes' },
      { label: 'output', type: 'variable', info: 'Set your return value here' },
    );

    // Add functions
    completions.push(
      { label: 'set_global', type: 'function', info: 'Set a global variable', apply: 'set_global("", )' },
      { label: 'string["upper"]', type: 'function', info: 'Convert to uppercase' },
      { label: 'string["lower"]', type: 'function', info: 'Convert to lowercase' },
      { label: 'string["split"]', type: 'function', info: 'Split string' },
      { label: 'string["join"]', type: 'function', info: 'Join strings' },
      { label: 'string["replace"]', type: 'function', info: 'Replace in string' },
      { label: 'math["add"]', type: 'function', info: 'Add numbers' },
      { label: 'math["subtract"]', type: 'function', info: 'Subtract numbers' },
      { label: 'math["multiply"]', type: 'function', info: 'Multiply numbers' },
      { label: 'math["divide"]', type: 'function', info: 'Divide numbers' },
      { label: 'math["power"]', type: 'function', info: 'Power operation' },
      { label: 'math["sqrt"]', type: 'function', info: 'Square root' },
    );

    // Add variable paths from availableVariables
    if (availableVariables.input) {
      Object.keys(availableVariables.input).forEach(key => {
        if (key !== '_description') {
          completions.push({
            label: `input.get('${key}')`,
            type: 'variable',
            info: availableVariables.input[key] || key
          });
        }
      });
    }

    if (availableVariables.global) {
      Object.keys(availableVariables.global).forEach(key => {
        if (key !== '_description' && key !== '[any_variable]') {
          completions.push({
            label: `global.get('${key}')`,
            type: 'variable',
            info: availableVariables.global[key] || key
          });
        }
      });
    }

    if (availableVariables.node_outputs) {
      Object.keys(availableVariables.node_outputs).forEach(nodeId => {
        completions.push({
          label: `node_outputs['${nodeId}']`,
          type: 'variable',
          info: `Output from ${nodeId}`
        });
      });
    }

    return completions;
  }, [availableVariables]);

  // Custom autocomplete function
  const myCompletions = useCallback((context) => {
    let word = context.matchBefore(/\w*/);
    if (word.from === word.to && !context.explicit) return null;
    
    return {
      from: word.from,
      options: createCompletions()
    };
  }, [createCompletions]);

  // Extensions for CodeMirror
  const extensions = useMemo(() => [
    python(),
    autocompletion({ override: [myCompletions] })
  ], [myCompletions]);

  // Toggle category expansion
  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  // Insert variable at cursor
  const insertVariable = (variable) => {
    // This is a simple implementation - in production you'd want to insert at cursor position
    onChange(value + (value ? '\n' : '') + variable);
  };

  // Helper function to render nested node output structure
  const renderNodeOutputStructure = (obj, path, depth) => {
    if (!obj || typeof obj !== 'object' || depth > 5) return null;
    
    return Object.entries(obj).filter(([key]) => !key.startsWith('_')).map(([key, value]) => {
      const fullPath = /^\d+$/.test(key) ? `${path}['${key}']` : `${path}['${key}']`;
      
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        // Nested object - make it expandable
        return (
          <div key={key} className="mb-1">
            <button
              onClick={() => toggleCategory(`${path}_${key}`)}
              className="flex items-center text-xs text-gray-600 hover:text-gray-800"
            >
              {expandedCategories[`${path}_${key}`] ? <ChevronDownIcon className="w-3 h-3 mr-1" /> : <ChevronRightIcon className="w-3 h-3 mr-1" />}
              {key}
            </button>
            {expandedCategories[`${path}_${key}`] && (
              <div className="ml-3 mt-1">
                {renderNodeOutputStructure(value, fullPath, depth + 1)}
              </div>
            )}
          </div>
        );
      } else {
        // Leaf value - show with insert button
        return (
          <div key={key} className="flex items-center justify-between py-0.5">
            <span className="text-xs text-gray-600">
              {key}: <span className="text-gray-500">{typeof value === 'string' ? value : typeof value}</span>
            </span>
            <button
              onClick={() => insertVariable(fullPath)}
              className="text-xs text-blue-600 hover:text-blue-800 ml-2"
            >
              Insert
            </button>
          </div>
        );
      }
    });
  };

  // Example snippets
  const snippets = [
    {
      name: 'Basic transformation',
      code: `# Basic data transformation
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['processed'] = True
output['count'] = len(input.get('items', []))`
    },
    {
      name: 'Loop through items',
      code: `# Process list of items
local['items'] = input.get('items', [])
local['processed'] = []

for item in local['items']:
    local['processed'].append({
        'id': item.get('id'),
        'name': string['upper'](item.get('name', '')),
        'processed': True
    })

output['items'] = local['processed']
output['count'] = len(local['processed'])`
    },
    {
      name: 'Conditional logic',
      code: `# Conditional processing
local['value'] = input.get('value', 0)

if local['value'] > 100:
    output['category'] = 'high'
    output['discount'] = 0.2
elif local['value'] > 50:
    output['category'] = 'medium'
    output['discount'] = 0.1
else:
    output['category'] = 'low'
    output['discount'] = 0

output['final_value'] = math['multiply'](local['value'], 1 - output['discount'])`
    },
    {
      name: 'Set global variable',
      code: `# Set and use global variables
set_global('total_processed', global.get('total_processed', 0) + 1)
set_global('last_run', str(input.get('timestamp', '')))

output['run_count'] = global.get('total_processed')
output['status'] = 'completed'`
    }
  ];

  return (
    <div className="transform-code-editor">
      <div className="mb-2 flex justify-between items-center">
        <div className="flex items-center space-x-2">
          <CodeBracketIcon className="w-5 h-5 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">Transform Script</span>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => setShowVariablePanel(!showVariablePanel)}
            className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
          >
            <VariableIcon className="w-4 h-4 mr-1" />
            {showVariablePanel ? 'Hide' : 'Show'} Variables
          </button>
        </div>
      </div>

      <div className="flex space-x-4">
        {/* Code Editor */}
        <div className="flex-1">
          <div className="border rounded-lg overflow-hidden">
            <CodeMirror
              value={value}
              height="400px"
              theme={theme === 'dark' ? oneDark : undefined}
              extensions={extensions}
              onChange={onChange}
              placeholder={placeholder}
            />
          </div>

          {/* Snippets */}
          <div className="mt-3">
            <div className="text-xs text-gray-600 mb-2">Quick snippets:</div>
            <div className="flex flex-wrap gap-2">
              {snippets.map((snippet, index) => (
                <button
                  key={index}
                  onClick={() => onChange(snippet.code)}
                  className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                >
                  {snippet.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Variable Panel */}
        {showVariablePanel && (
          <div className="w-80 border rounded-lg p-4 bg-gray-50">
            <h4 className="text-sm font-semibold text-gray-700 mb-3">Available Variables</h4>
            
            {/* Input Variables */}
            <div className="mb-3">
              <button
                onClick={() => toggleCategory('input')}
                className="flex items-center text-sm font-medium text-gray-700 mb-1 hover:text-gray-900"
              >
                {expandedCategories.input ? <ChevronDownIcon className="w-4 h-4 mr-1" /> : <ChevronRightIcon className="w-4 h-4 mr-1" />}
                Input Variables
              </button>
              {expandedCategories.input && (
                <div className="ml-5 space-y-1">
                  {renderNodeOutputStructure(availableVariables.input || {}, 'input', 0)}
                </div>
              )}
            </div>

            {/* Global Variables */}
            <div className="mb-3">
              <button
                onClick={() => toggleCategory('global')}
                className="flex items-center text-sm font-medium text-gray-700 mb-1 hover:text-gray-900"
              >
                {expandedCategories.global ? <ChevronDownIcon className="w-4 h-4 mr-1" /> : <ChevronRightIcon className="w-4 h-4 mr-1" />}
                Global Variables
              </button>
              {expandedCategories.global && (
                <div className="ml-5 space-y-1">
                  <div className="text-xs text-gray-500 italic mb-1">Set by transform nodes</div>
                  {Object.entries(availableVariables.global || {}).map(([key, desc]) => (
                    key !== '_description' && key !== '[any_variable]' && (
                      <div key={key} className="flex items-center justify-between">
                        <span className="text-xs text-gray-600">{key}</span>
                        <button
                          onClick={() => insertVariable(`global.get('${key}')`)}
                          className="text-xs text-blue-600 hover:text-blue-800"
                        >
                          Insert
                        </button>
                      </div>
                    )
                  ))}
                </div>
              )}
            </div>

            {/* Node Outputs */}
            <div className="mb-3">
              <button
                onClick={() => toggleCategory('node_outputs')}
                className="flex items-center text-sm font-medium text-gray-700 mb-1 hover:text-gray-900"
              >
                {expandedCategories.node_outputs ? <ChevronDownIcon className="w-4 h-4 mr-1" /> : <ChevronRightIcon className="w-4 h-4 mr-1" />}
                Node Outputs
              </button>
              {expandedCategories.node_outputs && (
                <div className="ml-5 space-y-2">
                  {Object.entries(availableVariables.node_outputs || {}).map(([nodeId, nodeData]) => (
                    <div key={nodeId} className="border-l-2 border-gray-200 pl-2">
                      <button
                        onClick={() => toggleCategory(`node_${nodeId}`)}
                        className="flex items-center text-xs font-medium text-gray-700 hover:text-gray-900"
                      >
                        {expandedCategories[`node_${nodeId}`] ? <ChevronDownIcon className="w-3 h-3 mr-1" /> : <ChevronRightIcon className="w-3 h-3 mr-1" />}
                        {nodeId}
                      </button>
                      {expandedCategories[`node_${nodeId}`] && (
                        <div className="ml-3 mt-1 space-y-1">
                          {/* Helper function to render nested structure */}
                          {renderNodeOutputStructure(nodeData, `node_outputs['${nodeId}']`, 0)}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Built-in Functions */}
            <div className="mt-4 p-3 bg-white rounded border">
              <h5 className="text-xs font-semibold text-gray-700 mb-2">Built-in Functions</h5>
              <div className="space-y-1 text-xs text-gray-600">
                <div><code>set_global(name, value)</code></div>
                <div><code>string['upper'](text)</code></div>
                <div><code>string['lower'](text)</code></div>
                <div><code>string['split'](text, sep)</code></div>
                <div><code>math['add'](a, b)</code></div>
                <div><code>math['multiply'](a, b)</code></div>
                <div><code>len(items)</code></div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TransformCodeEditor;