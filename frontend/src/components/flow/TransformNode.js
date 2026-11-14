import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom';
import { Handle, Position } from 'reactflow';
import { DocumentTextIcon, SparklesIcon } from '@heroicons/react/24/outline';
import { withResize } from './ResizableNode';
import ValidationErrorTooltip from './ValidationErrorTooltip';
import OverlapIndicator from './OverlapIndicator';

const TransformNodeBase = ({ data, isConnectable, id }) => {
  // Check if node is executing based on data
  const isExecuting = data?.isExecuting || false;

  // Check for validation errors
  const hasErrors = data?.validationErrors && data.validationErrors.length > 0;
  const hasWarnings = data?.validationErrors && data.validationErrors.some(e => e.type === 'warning');
  const hasCriticalErrors = data?.validationErrors && data.validationErrors.some(e => e.type === 'error');

  // Check if node is empty (no script content)
  const isEmpty = !data?.script || data.script.trim() === '';

  // AI Assistant tooltip state
  const [showAITooltip, setShowAITooltip] = useState(false);
  const [hasSeenAITooltip, setHasSeenAITooltip] = useState(false);

  // Check if user has seen the AI tooltip before
  useEffect(() => {
    const seen = localStorage.getItem('ioflow_transform_ai_tooltip_seen');
    setHasSeenAITooltip(seen === 'true');

    // Show tooltip on first render if not seen before and node is empty
    if (!seen && isEmpty) {
      const timer = setTimeout(() => {
        setShowAITooltip(true);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isEmpty]);

  // Mark tooltip as seen when user dismisses it
  const dismissAITooltip = () => {
    setShowAITooltip(false);
    localStorage.setItem('ioflow_transform_ai_tooltip_seen', 'true');
    setHasSeenAITooltip(true);
  };
  
  return (
    <div className={`bg-purple-50 border-2 ${hasCriticalErrors ? 'border-red-400' : hasWarnings ? 'border-yellow-400' : 'border-purple-300'} rounded-lg p-4 w-full h-full overflow-hidden relative`}>
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        isConnectable={isConnectable}
      />
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        isConnectable={isConnectable}
      />
      <div className="flex items-center justify-between mb-2">
        <DocumentTextIcon className="w-5 h-5 text-purple-600" />
        <div className="flex items-center gap-2">
          {isExecuting && (
            <svg className="animate-spin h-4 w-4 text-purple-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )}
          <span className="text-xs text-purple-600 font-medium">Transform</span>
        </div>
      </div>
      <div className="font-medium text-gray-800">{data.label}</div>
      {!isEmpty && data.script && (
        <div className="text-xs text-gray-500 mt-1">
          {data.script.length > 30 ? 'Custom transformation' : data.script}
        </div>
      )}

      {/* Show AI empty state overlay when node is empty - positioned absolutely to cover entire node */}
      {isEmpty && (
        <div className="absolute inset-0 bg-black/70 backdrop-blur-sm rounded-lg flex items-center justify-center p-3">
          <div className="flex items-center gap-2 max-w-full">
            <div className="bg-gradient-to-r from-purple-500 to-pink-500 rounded-full p-1 flex-shrink-0">
              <SparklesIcon className="w-3 h-3 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs font-bold text-white mb-0.5">
                Transform Node code AI can write
              </div>
              <div className="text-[10px] text-gray-200 leading-tight">
                Click to use AI assistant
              </div>
            </div>
          </div>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        isConnectable={isConnectable}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
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
          position="bottom-left"
          showWarning={data.overlappingNodes?.length > 2}
        />
      )}
    </div>
  );
};

const TransformNode = withResize(TransformNodeBase);

export default TransformNode;