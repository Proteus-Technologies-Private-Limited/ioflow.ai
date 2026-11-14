import React from 'react';
import { Handle, Position } from 'reactflow';
import { ArrowPathIcon } from '@heroicons/react/24/outline';
import { withResize } from './ResizableNode';
import ValidationErrorTooltip from './ValidationErrorTooltip';
import OverlapIndicator from './OverlapIndicator';

const LoopNodeBase = ({ data, isConnectable, id }) => {
  // Check for validation errors
  const hasErrors = data?.validationErrors && data.validationErrors.length > 0;
  const hasWarnings = data?.validationErrors && data.validationErrors.some(e => e.type === 'warning');
  const hasCriticalErrors = data?.validationErrors && data.validationErrors.some(e => e.type === 'error');
  
  const getLoopTypeDisplay = () => {
    switch (data.loopType) {
      case 'forEach':
        return 'For Each';
      case 'while':
        return 'While';
      case 'for':
        return 'For';
      default:
        return 'Loop';
    }
  };

  const getLoopDescription = () => {
    switch (data.loopType) {
      case 'forEach':
        return data.arrayPath || 'array';
      case 'while':
        return data.condition || 'condition';
      case 'for':
        return `${data.startValue || 1} to ${data.endValue || 10}`;
      default:
        return '';
    }
  };
  return (
    <div className={`bg-purple-50 border-2 ${hasCriticalErrors ? 'border-red-400' : hasWarnings ? 'border-yellow-400' : 'border-purple-300'} rounded-lg p-4 w-full h-full relative overflow-hidden`}>
      {/* Input from top */}
      <Handle
        type="target"
        position={Position.Top}
        id="input"
        isConnectable={isConnectable}
      />
      
      
      <div className="flex items-center justify-between mb-2">
        <ArrowPathIcon className="w-5 h-5 text-purple-600" />
        <span className="text-xs text-purple-600 font-medium">{getLoopTypeDisplay()}</span>
      </div>
      
      <div className="font-medium text-gray-800">{data.label}</div>
      
      <div className="text-xs text-gray-600 mt-1 font-mono">
        {getLoopDescription()}
      </div>
      
      {data.iteratorName && (
        <div className="text-xs text-purple-600 mt-1">
          Iterator: {data.iteratorName}
        </div>
      )}
      
      {/* Loop body output to right (upper) */}
      <div className="absolute -right-16 top-1/3 -translate-y-1/2 text-xs font-medium text-purple-600 pointer-events-none">
        Loop Body
      </div>
      <Handle
        type="source"
        position={Position.Right}
        id="loop-body"
        isConnectable={isConnectable}
        className="z-10"
        style={{ top: '33%', zIndex: 10 }}
        onClick={(e) => e.stopPropagation()}
      />
      
      {/* Loop back input to right (lower) */}
      <div className="absolute -right-16 bottom-1/3 translate-y-1/2 text-xs font-medium text-purple-600 pointer-events-none">
        Loop Back
      </div>
      <Handle
        type="target"
        position={Position.Right}
        id="loop-back"
        isConnectable={isConnectable}
        className="z-10"
        style={{ top: '67%', zIndex: 10 }}
        onClick={(e) => e.stopPropagation()}
      />
      
      {/* Continue output to bottom */}
      <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs font-medium text-purple-600 pointer-events-none">
        Continue
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        id="continue"
        isConnectable={isConnectable}
        className="z-10"
        style={{ zIndex: 10 }}
        onClick={(e) => e.stopPropagation()}
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
          position="bottom-left"
          showWarning={data.overlappingNodes?.length > 2}
        />
      )}
    </div>
  );
};

const LoopNode = withResize(LoopNodeBase);

export default LoopNode;