import React from 'react';
import { Handle, Position } from 'reactflow';
import { ClockIcon } from '@heroicons/react/24/outline';
import { withResize } from './ResizableNode';
import ValidationErrorTooltip from './ValidationErrorTooltip';
import OverlapIndicator from './OverlapIndicator';

const matchModeLabels = {
  correlation: 'Correlation',
  token: 'Callback Token',
};

const timeoutActionLabels = {
  fail: 'Fail',
  continue_with_defaults: 'Continue',
  skip: 'Skip',
};

const WaitForEventNodeBase = ({ id, data, isConnectable }) => {
  const isExecuting = data?.isExecuting || false;
  const hasErrors = data?.validationErrors && data.validationErrors.length > 0;
  const hasWarnings = data?.validationErrors && data.validationErrors.some(e => e.type === 'warning');
  const hasCriticalErrors = data?.validationErrors && data.validationErrors.some(e => e.type === 'error');

  const matchMode = data?.matchMode || 'token';
  const eventName = data?.eventName || '';
  const timeoutMinutes = data?.timeoutMinutes || 0;
  const timeoutAction = data?.timeoutAction || 'fail';

  return (
    <div className={`bg-amber-50 border-2 ${hasCriticalErrors ? 'border-red-400' : hasWarnings ? 'border-yellow-400' : 'border-amber-300'} rounded-lg p-4 w-full h-full overflow-hidden relative`}>
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
        <ClockIcon className="w-5 h-5 text-amber-600" />
        <div className="flex items-center gap-2">
          {isExecuting && (
            <svg className="animate-spin h-4 w-4 text-amber-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          )}
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
            {matchModeLabels[matchMode] || 'Token'}
          </span>
        </div>
      </div>
      <div className="font-medium text-gray-800">{data.label}</div>
      {data.appName && (
        <div className="flex items-center gap-1 mt-1">
          {data.appIcon && (
            <img
              src={data.appIcon}
              alt={data.appName}
              className="w-4 h-4 object-contain"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          )}
          <span className="text-xs text-gray-600 font-medium truncate">{data.appName}</span>
        </div>
      )}
      {eventName && (
        <div className="text-xs text-gray-500 mt-1 truncate">{eventName}</div>
      )}
      {timeoutMinutes > 0 && (
        <div className="text-[10px] text-gray-400 mt-1">
          Timeout: {timeoutMinutes}m ({timeoutActionLabels[timeoutAction] || 'Fail'})
        </div>
      )}
      <div className="absolute bottom-1 right-2 flex items-center gap-1 text-[10px] text-gray-400">
        <ClockIcon className="w-3 h-3" />
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

const WaitForEventNode = withResize(WaitForEventNodeBase);

export default WaitForEventNode;
