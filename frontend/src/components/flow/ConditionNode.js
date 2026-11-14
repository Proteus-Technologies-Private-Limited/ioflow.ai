import React from 'react';
import { Handle, Position } from 'reactflow';
import { CodeBracketIcon } from '@heroicons/react/24/outline';
import { withResize } from './ResizableNode';
import ValidationErrorTooltip from './ValidationErrorTooltip';
import OverlapIndicator from './OverlapIndicator';

const ConditionNodeBase = ({ data, isConnectable, id }) => {
  // Check if node is executing
  const isExecuting = data?.isExecuting || false;
  
  // Check for validation errors
  const hasErrors = data?.validationErrors && data.validationErrors.length > 0;
  const hasWarnings = data?.validationErrors && data.validationErrors.some(e => e.type === 'warning');
  const hasCriticalErrors = data?.validationErrors && data.validationErrors.some(e => e.type === 'error');
  
  return (
    <div className={`bg-yellow-50 border-2 ${hasCriticalErrors ? 'border-red-400' : hasWarnings ? 'border-yellow-400' : 'border-yellow-300'} rounded-lg p-4 w-full h-full relative overflow-hidden`}>
      <Handle
        type="target"
        position={Position.Top}
        id="a"
        isConnectable={isConnectable}
      />
      <div className="flex items-center justify-between mb-2">
        <CodeBracketIcon className="w-5 h-5 text-yellow-600" />
        <div className="flex items-center gap-2">
          {isExecuting && (
            <svg className="animate-spin h-4 w-4 text-yellow-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )}
          <span className="text-xs text-yellow-600 font-medium">Condition</span>
        </div>
      </div>
      <div className="font-medium text-gray-800">{data.label}</div>
      {data.expression && (
        <div className="text-xs text-gray-500 mt-1 font-mono truncate">
          {data.expression}
        </div>
      )}
      {/* True output */}
      <div className="absolute -right-12 top-1/2 -translate-y-1/2 text-xs font-medium text-green-600">
        True
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="true"
        isConnectable={isConnectable}
        style={{ top: '50%' }}
      />
      {/* False output */}
      <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs font-medium text-red-600">
        False
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        isConnectable={isConnectable}
      />
      <div className="absolute bottom-1 right-2 text-[10px] text-gray-400">{id}</div>
      
      {/* Validation error tooltip */}
      {hasErrors && (
        <ValidationErrorTooltip 
          errors={data.validationErrors}
          className="absolute top-1 right-1"
          onRevalidate={data.onRevalidate}
        />
      )}
      
      {/* Overlap indicator */}
      {data?.showOverlapIndicator && (
        <OverlapIndicator
          overlappingCount={data.overlappingNodes?.length || 0}
          type="node"
          position="top-left"
          showWarning={data.overlappingNodes?.length > 2}
        />
      )}
    </div>
  );
};

const ConditionNode = withResize(ConditionNodeBase);

export default ConditionNode;