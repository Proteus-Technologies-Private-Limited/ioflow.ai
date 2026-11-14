import React from 'react';
import { Handle, Position } from 'reactflow';
import { ArrowUpTrayIcon } from '@heroicons/react/24/outline';
import { withResize } from './ResizableNode';
import OverlapIndicator from './OverlapIndicator';

const ResponseNodeBase = ({ data, isConnectable, id }) => {
  return (
    <div className="bg-red-50 border-2 border-red-300 rounded-lg p-4 w-full h-full overflow-hidden relative">
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
        <ArrowUpTrayIcon className="w-5 h-5 text-red-600" />
        <span className="text-xs text-red-600 font-medium">Response</span>
      </div>
      
      <div className="font-medium text-gray-800">{data.label || 'Response'}</div>
      
      {data.variable ? (
        <div className="text-xs text-gray-500 mt-1">
          <div className="truncate">{data.variable}</div>
          {data.statusCode && (
            <div className="">
              Status: {data.statusCode}
            </div>
          )}
        </div>
      ) : (
        <div className="text-xs text-gray-500 italic mt-1">
          Configure response
        </div>
      )}
      <div className="absolute bottom-1 right-2 text-[10px] text-gray-400">{id}</div>
      
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

const ResponseNode = withResize(ResponseNodeBase);

export default ResponseNode;