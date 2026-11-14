import React from 'react';
import { Handle, Position } from 'reactflow';
import { ExclamationTriangleIcon } from '@heroicons/react/24/solid';
import { withResize } from './ResizableNode';
import ValidationErrorTooltip from './ValidationErrorTooltip';

const InvalidNodeBase = ({ id, data, isConnectable }) => {
  // This node is used for invalid/unknown node types
  const nodeType = data?.nodeType || 'unknown';

  // Validation errors should always include the invalid type error
  const hasErrors = data?.validationErrors && data.validationErrors.length > 0;

  return (
    <div className={`
      px-4 py-3 shadow-lg rounded-lg border-2
      bg-red-50 border-red-500
      min-w-[180px]
      ${data.width ? '' : 'w-48'}
    `}
    style={{
      width: data.width || 'auto',
      height: data.height || 'auto'
    }}>
      <Handle
        type="target"
        position={Position.Top}
        isConnectable={isConnectable}
        className="w-3 h-3 !bg-red-500"
      />

      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <ExclamationTriangleIcon className="w-5 h-5 text-red-600" />
          <span className="text-red-800 font-bold">Invalid Node</span>
        </div>
      </div>

      <div className="text-xs text-red-700 mb-1">
        Type: <code className="bg-red-100 px-1 py-0.5 rounded">{nodeType}</code>
      </div>

      <div className="text-sm text-red-800 font-medium">
        {data.label || `Invalid ${nodeType} Node`}
      </div>

      <div className="text-xs text-red-600 mt-2">
        ⚠️ This node type is not supported
      </div>

      {/* Validation error tooltip */}
      {hasErrors && (
        <ValidationErrorTooltip
          errors={data.validationErrors}
          className="absolute top-1 right-1"
          onRevalidate={data.onRevalidate}
        />
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        isConnectable={isConnectable}
        className="w-3 h-3 !bg-red-500"
      />
    </div>
  );
};

// Export with resize wrapper
const InvalidNode = withResize(InvalidNodeBase);

export default InvalidNode;