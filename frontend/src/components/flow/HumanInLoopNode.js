import React from 'react';
import { Handle, Position } from 'reactflow';
import { HandRaisedIcon } from '@heroicons/react/24/outline';
import { withResize } from './ResizableNode';
import ValidationErrorTooltip from './ValidationErrorTooltip';
import OverlapIndicator from './OverlapIndicator';

const taskTypeLabels = {
  review: 'Review',
  edit: 'Edit',
  approve_reject: 'Approve/Reject',
};

const priorityColors = {
  low: 'bg-green-100 text-green-700',
  medium: 'bg-yellow-100 text-yellow-700',
  high: 'bg-orange-100 text-orange-700',
  critical: 'bg-red-100 text-red-700',
};

const HumanInLoopNodeBase = ({ id, data, isConnectable }) => {
  const isExecuting = data?.isExecuting || false;
  const hasErrors = data?.validationErrors && data.validationErrors.length > 0;
  const hasWarnings = data?.validationErrors && data.validationErrors.some(e => e.type === 'warning');
  const hasCriticalErrors = data?.validationErrors && data.validationErrors.some(e => e.type === 'error');

  const taskType = data?.taskType || 'review';
  const priority = data?.priority || 'medium';
  const assignmentConfig = data?.assignmentConfig || {};

  const getAssignmentSummary = () => {
    if (assignmentConfig.type === 'user') {
      const count = assignmentConfig.users?.length || 0;
      return count === 0 ? 'Unassigned' : `${count} user${count > 1 ? 's' : ''}`;
    } else if (assignmentConfig.type === 'role') {
      const count = assignmentConfig.roles?.length || 0;
      return count === 0 ? 'No role' : `${count} role${count > 1 ? 's' : ''}`;
    }
    return 'Unassigned';
  };

  return (
    <div className={`bg-blue-50 border-2 ${hasCriticalErrors ? 'border-red-400' : hasWarnings ? 'border-yellow-400' : 'border-blue-300'} rounded-lg p-4 w-full h-full overflow-hidden relative`}>
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
        <HandRaisedIcon className="w-5 h-5 text-blue-600" />
        <div className="flex items-center gap-2">
          {isExecuting && (
            <svg className="animate-spin h-4 w-4 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )}
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${priorityColors[priority] || priorityColors.medium}`}>
            {priority}
          </span>
          <span className="text-xs text-blue-600 font-medium">
            {taskTypeLabels[taskType] || 'Review'}
          </span>
        </div>
      </div>
      <div className="font-medium text-gray-800">{data.label}</div>
      <div className="text-xs text-gray-500 mt-1">{getAssignmentSummary()}</div>
      <div className="absolute bottom-1 right-2 flex items-center gap-1 text-[10px] text-gray-400">
        <HandRaisedIcon className="w-3 h-3" />
        <span>{id}</span>
      </div>

      {hasErrors && (
        <ValidationErrorTooltip
          errors={data.validationErrors}
          className="absolute top-1 right-1"
          onRevalidate={data.onRevalidate}
        />
      )}

      {data?.showOverlapIndicator && (
        <OverlapIndicator
          overlappingCount={data.overlappingNodes?.length || 0}
          type="node"
          position="bottom-left"
          showWarning={data.overlappingNodes?.length > 2}
        />
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
    </div>
  );
};

const HumanInLoopNode = withResize(HumanInLoopNodeBase);

export default HumanInLoopNode;
