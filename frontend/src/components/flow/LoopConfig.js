import React from 'react';
import NestedVariableSelector from './NestedVariableSelector';
import ConditionBuilder from './ConditionBuilder';

const LoopConfig = ({ node, updateNodeData, flowContext }) => {
  const handleLoopTypeChange = (loopType) => {
    const updates = { loopType };
    
    // Reset configuration when changing loop type
    switch (loopType) {
      case 'forEach':
        updates.arrayPath = '';
        updates.iteratorName = 'item';
        delete updates.condition;
        delete updates.start;
        delete updates.end;
        break;
      case 'while':
        updates.condition = '';
        delete updates.arrayPath;
        delete updates.iteratorName;
        delete updates.start;
        delete updates.end;
        break;
      case 'for':
        updates.startValue = '1';
        updates.endValue = '10';
        updates.stepValue = '1';
        updates.iteratorName = 'i';
        delete updates.arrayPath;
        delete updates.condition;
        break;
    }
    
    updateNodeData(node.id, updates);
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Loop Type
        </label>
        <select
          value={node.data.loopType || 'forEach'}
          onChange={(e) => handleLoopTypeChange(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
        >
          <option value="forEach">For Each (Array)</option>
          <option value="while">While (Condition)</option>
          <option value="for">For (Range)</option>
        </select>
      </div>

      {node.data.loopType === 'forEach' && (
        <>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Array to Iterate
            </label>
            <NestedVariableSelector
              value={node.data.arrayPath || ''}
              onChange={(value) => {
                // For array path, always wrap variables with {{}}
                // since this should always be a variable reference
                if (value && !value.startsWith('{{')) {
                  value = `{{${value}}}`;
                }
                updateNodeData(node.id, { arrayPath: value });
              }}
              availableVariables={flowContext}
              placeholder="Select array variable..."
              allowManualInput={true}
            />
            <div className="mt-2 text-xs text-gray-600 bg-blue-50 p-2 rounded">
              <strong>💡 Tip:</strong> For nested data structures, you can select arrays at any depth. 
              For example:
              <ul className="mt-1 ml-4 list-disc">
                <li><code>node_outputs.api_call.result.data</code> for API responses</li>
                <li><code>node_outputs.transform.customers.items</code> for nested objects</li>
              </ul>
              Look for the <span className="text-green-700 font-semibold">green "Loopable"</span> badge to identify arrays.
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Iterator Variable Name
            </label>
            <input
              type="text"
              value={node.data.iteratorName || 'item'}
              onChange={(e) => updateNodeData(node.id, { iteratorName: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="item"
            />
            <p className="text-xs text-gray-500 mt-1">
              Access current item as: {`{{loop.${node.data.iteratorName || 'item'}}}`}
            </p>
          </div>
        </>
      )}

      {node.data.loopType === 'while' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Continue Condition
          </label>
          <ConditionBuilder
            expression={node.data.condition || ''}
            onExpressionChange={(condition) => updateNodeData(node.id, { condition })}
            availableVariables={flowContext}
            mode="edit"
          />
          <p className="text-xs text-gray-500 mt-1">
            Loop continues while this condition is true
          </p>
        </div>
      )}

      {node.data.loopType === 'for' && (
        <>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Start Value
              </label>
              <NestedVariableSelector
                value={node.data.startValue || '1'}
                onChange={(value) => {
                  // Check if it's a variable path (contains dots or starts with known prefixes)
                  const isVariable = value && (
                    value.includes('.') || 
                    value.startsWith('input') || 
                    value.startsWith('node_outputs') || 
                    value.startsWith('flow') ||
                    value.startsWith('loop') ||
                    value.startsWith('global')
                  );
                  
                  // If it's a variable and not already wrapped, wrap it
                  if (isVariable && !value.startsWith('{{')) {
                    value = `{{${value}}}`;
                  }
                  
                  updateNodeData(node.id, { startValue: value });
                }}
                availableVariables={flowContext}
                placeholder="Enter number or select variable..."
                allowManualInput={true}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                End Value
              </label>
              <NestedVariableSelector
                value={node.data.endValue || '10'}
                onChange={(value) => {
                  // Check if it's a variable path (contains dots or starts with known prefixes)
                  const isVariable = value && (
                    value.includes('.') || 
                    value.startsWith('input') || 
                    value.startsWith('node_outputs') || 
                    value.startsWith('flow') ||
                    value.startsWith('loop') ||
                    value.startsWith('global')
                  );
                  
                  // If it's a variable and not already wrapped, wrap it
                  if (isVariable && !value.startsWith('{{')) {
                    value = `{{${value}}}`;
                  }
                  
                  updateNodeData(node.id, { endValue: value });
                }}
                availableVariables={flowContext}
                placeholder="Enter number or select variable..."
                allowManualInput={true}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Step Value
              </label>
              <NestedVariableSelector
                value={node.data.stepValue || '1'}
                onChange={(value) => {
                  // Check if it's a variable path (contains dots or starts with known prefixes)
                  const isVariable = value && (
                    value.includes('.') || 
                    value.startsWith('input') || 
                    value.startsWith('node_outputs') || 
                    value.startsWith('flow') ||
                    value.startsWith('loop') ||
                    value.startsWith('global')
                  );
                  
                  // If it's a variable and not already wrapped, wrap it
                  if (isVariable && !value.startsWith('{{')) {
                    value = `{{${value}}}`;
                  }
                  
                  updateNodeData(node.id, { stepValue: value });
                }}
                availableVariables={flowContext}
                placeholder="Enter number or select variable..."
                allowManualInput={true}
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Iterator Variable Name
            </label>
            <input
              type="text"
              value={node.data.iteratorName || 'i'}
              onChange={(e) => updateNodeData(node.id, { iteratorName: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="i"
            />
            <p className="text-xs text-gray-500 mt-1">
              Access current value as: {`{{loop.${node.data.iteratorName || 'i'}}}`}
            </p>
          </div>
        </>
      )}

      <div className="bg-purple-50 p-3 rounded-md">
        <h4 className="text-sm font-medium text-purple-900 mb-2">Loop Variables Available:</h4>
        <ul className="text-xs text-purple-700 space-y-1">
          <li>• <code>{`{{loop.index}}`}</code> - Current iteration index (0-based)</li>
          <li>• <code>{`{{loop.count}}`}</code> - Current iteration count (1-based)</li>
          <li>• <code>{`{{loop.first}}`}</code> - True if first iteration</li>
          <li>• <code>{`{{loop.last}}`}</code> - True if last iteration</li>
          {node.data.loopType === 'forEach' && (
            <li>• <code>{`{{loop.${node.data.iteratorName || 'item'}}}`}</code> - Current array item</li>
          )}
          {node.data.loopType === 'for' && (
            <li>• <code>{`{{loop.${node.data.iteratorName || 'i'}}}`}</code> - Current counter value</li>
          )}
        </ul>
      </div>

      <div className="bg-yellow-50 p-3 rounded-md">
        <h4 className="text-sm font-medium text-yellow-900 mb-1">Loop Exit</h4>
        <p className="text-xs text-yellow-700">
          To exit the loop early, connect a condition node inside the loop body. 
          When the condition is false, the flow will exit to the "Continue" output.
        </p>
      </div>
    </div>
  );
};

export default LoopConfig;