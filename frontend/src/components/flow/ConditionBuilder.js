import React, { useState, useEffect } from 'react';
import {
  CodeBracketIcon,
  CursorArrowRaysIcon,
  PlusIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CalculatorIcon,
  ClipboardDocumentIcon,
  XMarkIcon,
  ArrowPathIcon,
  GlobeAltIcon,
} from '@heroicons/react/24/outline';
import NestedVariableSelector from './NestedVariableSelector';

const ConditionBuilder = ({
  expression = '',
  onExpressionChange,
  availableVariables = {},
  mode = 'edit' // 'edit' or 'view'
}) => {
  // Check if expression can be parsed for visual builder
  const canUseVisualBuilder = (expr) => {
    if (!expr) return true;
    // Simple check for expressions that can be parsed
    // If expression contains function calls, complex logic, or other non-parseable elements, use text mode
    const complexPatterns = [
      /\b(function|return|if|else|for|while|switch|case|break|continue)\b/,
      /\[.*\]/,  // Array access
      /\(.*\)/,  // Function calls (except for simple comparisons)
      /[{}]/,     // Object literals or blocks
      /\?.*:/,    // Ternary operators
    ];

    // Check if it's too complex for visual builder
    for (const pattern of complexPatterns) {
      if (pattern.test(expr)) {
        return false;
      }
    }

    // Also check if it's a simple parseable expression
    const simplePattern = /^(\{\{[^}]+\}\}|[\w.]+)\s*(===|!==|>=|<=|>|<|includes|startsWith|endsWith)\s*(.+)$/;
    const logicalPattern = /\s*(&&|\|\|)\s*/;

    // If it contains logical operators, check each part
    if (logicalPattern.test(expr)) {
      const parts = expr.split(logicalPattern);
      return parts.every(part => !part.match(logicalPattern) || simplePattern.test(part.trim()));
    }

    return simplePattern.test(expr);
  };

  const [activeTab, setActiveTab] = useState(canUseVisualBuilder(expression) ? 'visual' : 'text');
  const [conditions, setConditions] = useState([]);
  const [textExpression, setTextExpression] = useState(expression);
  
  // Debug: Log available variables
  console.log('ConditionBuilder availableVariables:', availableVariables);

  // Operators
  const operators = {
    comparison: [
      { value: '===', label: 'Equals', symbol: '===' },
      { value: '!==', label: 'Not Equals', symbol: '!==' },
      { value: '>', label: 'Greater Than', symbol: '>' },
      { value: '<', label: 'Less Than', symbol: '<' },
      { value: '>=', label: 'Greater Than or Equal', symbol: '>=' },
      { value: '<=', label: 'Less Than or Equal', symbol: '<=' },
      { value: 'includes', label: 'Contains', symbol: 'includes' },
      { value: '!includes', label: 'Does Not Contain', symbol: '!includes' },
      { value: 'startsWith', label: 'Starts With', symbol: 'startsWith' },
      { value: 'endsWith', label: 'Ends With', symbol: 'endsWith' },
    ],
    logical: [
      { value: '&&', label: 'AND', symbol: '&&' },
      { value: '||', label: 'OR', symbol: '||' },
    ],
    special: [
      { value: 'exists', label: 'Exists', symbol: 'exists' },
      { value: '!exists', label: 'Does Not Exist', symbol: '!exists' },
      { value: 'isEmpty', label: 'Is Empty', symbol: 'isEmpty' },
      { value: '!isEmpty', label: 'Is Not Empty', symbol: '!isEmpty' },
    ]
  };

  // Flatten variables for easier access
  const flattenVariables = () => {
    const flattened = [];
    
    // Helper function to recursively flatten nested objects
    const flattenObject = (obj, prefix, category, icon) => {
      if (!obj || typeof obj !== 'object') return;
      
      Object.entries(obj).forEach(([key, value]) => {
        // Skip special fields
        if (key.startsWith('_')) return;
        
        // Handle numeric keys by using bracket notation
        const isNumeric = /^\d+$/.test(key);
        const path = prefix ? 
          (isNumeric ? `${prefix}['${key}']` : `${prefix}.${key}`) : 
          key;
        
        if (typeof value === 'string') {
          // It's a description string
          flattened.push({
            value: path,
            label: value || path,
            category,
            icon
          });
        } else if (typeof value === 'object' && value !== null) {
          // It's a nested object - recursively flatten it
          flattenObject(value, path, category, icon);
        }
      });
    };
    
    // Add input variables
    if (availableVariables.input) {
      flattenObject(availableVariables.input, 'input', 'Input', <CursorArrowRaysIcon className="w-4 h-4" />);
    }
    
    // Add node outputs
    if (availableVariables.node_outputs) {
      flattenObject(availableVariables.node_outputs, 'node_outputs', 'Node Outputs', <CodeBracketIcon className="w-4 h-4" />);
    }
    
    // Add flow variables
    if (availableVariables.flow) {
      flattenObject(availableVariables.flow, 'flow', 'Flow', <CalculatorIcon className="w-4 h-4" />);
    }
    
    // Add loop variables
    if (availableVariables.loop) {
      flattenObject(availableVariables.loop, 'loop', 'Loop', <ArrowPathIcon className="w-4 h-4" />);
    }
    
    // Add global variables
    if (availableVariables.global) {
      flattenObject(availableVariables.global, 'global', 'Global', <GlobeAltIcon className="w-4 h-4" />);
    }
    
    return flattened;
  };

  const allVariables = flattenVariables();
  console.log('ConditionBuilder allVariables:', allVariables);
  console.log('ConditionBuilder has loop?', availableVariables.loop);
  console.log('ConditionBuilder has global?', availableVariables.global);

  // Initialize conditions from expression
  useEffect(() => {
    if (expression) {
      if (canUseVisualBuilder(expression) && activeTab === 'visual' && conditions.length === 0) {
        // Try to parse the expression into visual conditions
        parseExpressionToConditions(expression);
      } else if (!canUseVisualBuilder(expression)) {
        // Complex expression, switch to text mode
        setActiveTab('text');
        setTextExpression(expression);
      }
    }
  }, [expression]);

  // Parse text expression to visual conditions (simplified)
  const parseExpressionToConditions = (expr) => {
    // This is a simplified parser - in production, you'd want a proper expression parser
    try {
      const parts = expr.split(/(\|\||&&)/);
      const parsedConditions = [];
      
      parts.forEach((part, index) => {
        if (part === '||' || part === '&&') {
          // This is a logical operator
          if (parsedConditions.length > 0) {
            parsedConditions[parsedConditions.length - 1].logicalOperator = part;
          }
        } else if (part.trim()) {
          // Try to parse a condition
          const match = part.trim().match(/(.+?)\s*(===|!==|>=|<=|>|<|includes|startsWith|endsWith)\s*(.+)/);
          if (match) {
            let fieldName = match[1].trim();
            let fieldValue = match[3].trim();
            
            // Remove {{}} from field if present
            if (fieldName.startsWith('{{') && fieldName.endsWith('}}')) {
              fieldName = fieldName.slice(2, -2);
            }
            
            // Determine if the value is a variable or literal
            let value = fieldValue;
            let valueType = 'literal';
            
            // Check if value is wrapped in {{}}
            if (fieldValue.startsWith('{{') && fieldValue.endsWith('}}')) {
              // It's a variable reference, remove {{}}
              value = fieldValue.slice(2, -2);
              valueType = 'variable';
            }
            // Check if it's a quoted string
            else if ((fieldValue.startsWith("'") && fieldValue.endsWith("'")) || 
                (fieldValue.startsWith('"') && fieldValue.endsWith('"'))) {
              // It's a literal string, remove quotes
              value = fieldValue.slice(1, -1);
              valueType = 'literal';
            } 
            // Check if it's a variable reference (contains dots or is a known variable)
            else if (fieldValue.includes('.') || 
                     fieldValue.startsWith('input') || 
                     fieldValue.startsWith('node_outputs') || 
                     fieldValue.startsWith('flow') ||
                     fieldValue.startsWith('loop') ||
                     fieldValue.startsWith('global')) {
              // It's a variable reference
              value = fieldValue;
              valueType = 'variable';
            }
            else if (fieldValue === 'true' || 
                     fieldValue === 'false' ||
                     !isNaN(fieldValue)) {
              // It's a boolean/number literal
              value = fieldValue;
              valueType = 'literal';
            }
            
            parsedConditions.push({
              id: Date.now() + index,
              field: fieldName,
              operator: match[2],
              value: value,
              valueType: valueType,
              logicalOperator: index < parts.length - 1 ? '&&' : null
            });
          }
        }
      });
      
      if (parsedConditions.length > 0) {
        setConditions(parsedConditions);
      }
    } catch (error) {
      console.error('Error parsing expression:', error);
    }
  };

  // Convert visual conditions to expression
  const buildExpression = () => {
    return conditions.map((condition, index) => {
      let expr = '';
      
      // Wrap field in {{}} if it's a variable path
      const field = condition.field ? `{{${condition.field}}}` : condition.field;
      
      // Handle special operators
      if (condition.operator === 'exists' || condition.operator === '!exists') {
        expr = `${condition.operator === '!exists' ? '!' : ''}${field}`;
      } else if (condition.operator === 'isEmpty' || condition.operator === '!isEmpty') {
        expr = `${condition.operator === '!isEmpty' ? '!' : ''}(${field} === '' || ${field} === null || ${field} === undefined)`;
      } else if (condition.operator === 'includes' || condition.operator === '!includes') {
        const value = condition.valueType === 'variable' ? `{{${condition.value}}}` : `'${condition.value}'`;
        expr = `${condition.operator === '!includes' ? '!' : ''}${field}.includes(${value})`;
      } else if (condition.operator === 'startsWith' || condition.operator === 'endsWith') {
        const value = condition.valueType === 'variable' ? `{{${condition.value}}}` : `'${condition.value}'`;
        expr = `${field}.${condition.operator}(${value})`;
      } else {
        // Regular comparison
        let value = condition.value;
        if (condition.valueType === 'literal') {
          // Handle boolean and numeric literals
          if (condition.value === 'true' || condition.value === 'false' || !isNaN(condition.value)) {
            value = condition.value;
          } else {
            value = `'${condition.value}'`;
          }
        } else {
          // It's a variable, wrap in {{}}
          value = `{{${condition.value}}}`;
        }
        expr = `${field} ${condition.operator} ${value}`;
      }
      
      // Add logical operator if not last condition
      if (index < conditions.length - 1 && condition.logicalOperator) {
        expr += ` ${condition.logicalOperator} `;
      }
      
      return expr;
    }).join('');
  };

  // Update expression when conditions change
  useEffect(() => {
    if (activeTab === 'visual' && conditions.length > 0) {
      const newExpression = buildExpression();
      setTextExpression(newExpression);
      onExpressionChange(newExpression);
    }
  }, [conditions, activeTab]);

  // Update expression when text changes
  useEffect(() => {
    if (activeTab === 'text') {
      onExpressionChange(textExpression);
    }
  }, [textExpression, activeTab]);

  // Add new condition
  const addCondition = () => {
    const newCondition = {
      id: Date.now(),
      field: '',
      operator: '===',
      value: '',
      valueType: 'literal', // 'literal' or 'variable'
      logicalOperator: conditions.length > 0 ? '&&' : null
    };
    setConditions([...conditions, newCondition]);
  };

  // Update condition
  const updateCondition = (id, updates) => {
    setConditions(conditions.map(c => 
      c.id === id ? { ...c, ...updates } : c
    ));
  };

  // Remove condition
  const removeCondition = (id) => {
    const index = conditions.findIndex(c => c.id === id);
    const updated = conditions.filter(c => c.id !== id);
    
    // Adjust logical operators
    if (index === 0 && updated.length > 0) {
      updated[0].logicalOperator = null;
    }
    
    setConditions(updated);
  };

  // Build available variables structure for NestedVariableSelector
  const buildNestedVariables = () => {
    const nested = {};
    
    // Convert flattened variables to nested structure
    if (availableVariables.input) {
      nested.input = availableVariables.input;
    }
    
    if (availableVariables.node_outputs) {
      nested.node_outputs = availableVariables.node_outputs;
    }
    
    if (availableVariables.flow) {
      nested.flow = availableVariables.flow;
    }
    
    if (availableVariables.data) {
      nested.data = availableVariables.data;
    }
    
    // Add loop variables
    if (availableVariables.loop) {
      nested.loop = availableVariables.loop;
    }
    
    // Add global variables
    if (availableVariables.global) {
      nested.global = availableVariables.global;
    }
    
    return nested;
  };
  
  const nestedVariables = buildNestedVariables();
  console.log('ConditionBuilder nestedVariables:', nestedVariables);

  // Render condition row
  const renderCondition = (condition, index) => {
    const isSpecialOperator = ['exists', '!exists', 'isEmpty', '!isEmpty'].includes(condition.operator);
    
    return (
      <div key={condition.id} className="space-y-3">
        {/* Logical operator (for conditions after the first) */}
        {index > 0 && (
          <div className="flex items-center justify-center">
            <select
              value={conditions[index - 1].logicalOperator || '&&'}
              onChange={(e) => updateCondition(conditions[index - 1].id, { logicalOperator: e.target.value })}
              className="px-3 py-1 text-sm font-medium bg-blue-50 border border-blue-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={mode === 'view'}
            >
              {operators.logical.map(op => (
                <option key={op.value} value={op.value}>{op.label}</option>
              ))}
            </select>
          </div>
        )}
        
        {/* Condition row */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <div className="grid grid-cols-12 gap-3">
            {/* Field selector - takes more space */}
            <div className="col-span-5">
              <label className="block text-xs font-medium text-gray-700 mb-1">Field</label>
              <NestedVariableSelector
                value={condition.field}
                onChange={(value) => updateCondition(condition.id, { field: value })}
                availableVariables={nestedVariables}
                placeholder="Select field..."
                mode={mode}
              />
            </div>
            
            {/* Operator selector */}
            <div className="col-span-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">Operator</label>
              <select
                value={condition.operator}
                onChange={(e) => updateCondition(condition.id, { operator: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={mode === 'view'}
              >
                <optgroup label="Comparison">
                  {operators.comparison.map(op => (
                    <option key={op.value} value={op.value}>{op.label}</option>
                  ))}
                </optgroup>
                <optgroup label="Special">
                  {operators.special.map(op => (
                    <option key={op.value} value={op.value}>{op.label}</option>
                  ))}
                </optgroup>
              </select>
            </div>
            
            {/* Value field (hidden for special operators) */}
            {!isSpecialOperator && (
              <div className="col-span-3">
                <label className="block text-xs font-medium text-gray-700 mb-1">Value</label>
                <div className="flex items-center space-x-2">
                  {/* Value type toggle */}
                  <button
                    type="button"
                    onClick={() => updateCondition(condition.id, { 
                      valueType: condition.valueType === 'literal' ? 'variable' : 'literal' 
                    })}
                    className={`p-2 rounded ${
                      condition.valueType === 'variable' 
                        ? 'bg-blue-100 text-blue-700' 
                        : 'bg-gray-100 text-gray-700'
                    } hover:bg-opacity-80`}
                    title={condition.valueType === 'variable' ? 'Using variable' : 'Using literal value'}
                    disabled={mode === 'view'}
                  >
                    {condition.valueType === 'variable' ? (
                      <CodeBracketIcon className="w-4 h-4" />
                    ) : (
                      <span className="text-xs font-medium px-1">ABC</span>
                    )}
                  </button>
                  
                  {/* Value input */}
                  {condition.valueType === 'variable' ? (
                    <div className="flex-1">
                      <NestedVariableSelector
                        value={condition.value}
                        onChange={(value) => updateCondition(condition.id, { value })}
                        availableVariables={nestedVariables}
                        placeholder="Select variable..."
                        mode={mode}
                      />
                    </div>
                  ) : (
                    <input
                      type="text"
                      value={condition.value}
                      onChange={(e) => updateCondition(condition.id, { value: e.target.value })}
                      placeholder="Enter value..."
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled={mode === 'view'}
                    />
                  )}
                </div>
              </div>
            )}
            
            {/* Remove button */}
            {mode === 'edit' && (
              <div className={`${isSpecialOperator ? 'col-span-4' : 'col-span-1'} flex items-end`}>
                <button
                  onClick={() => removeCondition(condition.id)}
                  className="p-2 text-red-600 hover:bg-red-50 rounded-md"
                  title="Remove condition"
                >
                  <TrashIcon className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {/* Tab selector */}
      <div className="flex items-center justify-between border-b">
        <div className="flex">
          <button
            onClick={() => setActiveTab('visual')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'visual'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <CalculatorIcon className="w-4 h-4 inline mr-2" />
            Visual Builder
          </button>
          <button
            onClick={() => setActiveTab('text')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'text'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-600 hover:text-gray-900'
            }`}
          >
            <CodeBracketIcon className="w-4 h-4 inline mr-2" />
            Text Expression
          </button>
        </div>
      </div>

      {activeTab === 'visual' ? (
        <div>
          <div className="space-y-3">
            {conditions.map((condition, index) => renderCondition(condition, index))}
            
            {mode === 'edit' && (
              <button
                onClick={addCondition}
                className="w-full py-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-gray-400 hover:text-gray-700 flex items-center justify-center transition-colors"
              >
                <PlusIcon className="w-5 h-5 mr-2" />
                Add Condition
              </button>
            )}
            
            {conditions.length === 0 && (
              <div className="text-center py-12 bg-gray-50 rounded-lg">
                <CalculatorIcon className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p className="text-sm text-gray-600">No conditions defined</p>
                <p className="text-xs text-gray-500 mt-1">Click "Add Condition" to start building your expression</p>
              </div>
            )}
          </div>
          
          {/* Expression preview */}
          {conditions.length > 0 && (
            <div className="mt-6 p-4 bg-gray-900 text-gray-100 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium">Generated Expression</h4>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(buildExpression());
                  }}
                  className="p-1 text-gray-400 hover:text-gray-200 transition-colors"
                  title="Copy expression"
                >
                  <ClipboardDocumentIcon className="w-4 h-4" />
                </button>
              </div>
              <pre className="text-sm font-mono overflow-x-auto whitespace-pre-wrap">{buildExpression()}</pre>
            </div>
          )}
        </div>
      ) : (
        <div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                JavaScript Expression
              </label>
              <textarea
                value={textExpression}
                onChange={(e) => setTextExpression(e.target.value)}
                placeholder="Enter JavaScript expression (e.g., input.status === 'active' && node_1.result > 100)"
                rows={8}
                className="w-full px-4 py-3 border border-gray-300 rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-gray-50"
                disabled={mode === 'view'}
              />
            </div>
            
            {/* Variable reference */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="text-sm font-medium text-blue-900 mb-3">Available Variables</h4>
              {allVariables.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                  {['Input', 'Node Outputs', 'Flow', 'Loop', 'Global'].map(category => {
                    const categoryVars = allVariables.filter(v => v.category === category);
                    if (categoryVars.length === 0) return null;
                    
                    return (
                      <div key={category}>
                        <h5 className="font-medium text-blue-800 mb-2 flex items-center">
                          {categoryVars[0]?.icon}
                          <span className="ml-2">{category}</span>
                        </h5>
                        <div className="space-y-1">
                          {categoryVars.slice(0, 5).map(variable => (
                            <div key={variable.value} className="text-blue-700">
                              <code className="text-xs bg-blue-100 px-1 py-0.5 rounded">
                                {variable.value}
                              </code>
                              <span className="text-xs text-blue-600 ml-1">- {variable.label}</span>
                            </div>
                          ))}
                          {categoryVars.length > 5 && (
                            <div className="text-xs text-blue-600 italic">
                              ...and {categoryVars.length - 5} more
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-blue-700">No variables available in this context.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ConditionBuilder;