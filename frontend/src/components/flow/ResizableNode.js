import React from 'react';
import { Handle, Position } from 'reactflow';
import { NodeResizer } from '@reactflow/node-resizer';
import { DEFAULT_NODE_DIMENSIONS, RESIZE_HANDLE_STYLES } from './nodeConfig';
import { ERROR_HANDLE_ID } from './NodeErrorHandlingConfig';
import '@reactflow/node-resizer/dist/style.css';

// Error output + policy badge, rendered outside the node body so node
// components with overflow-hidden don't clip them
const ErrorHandlingDecorations = ({ type, data, isConnectable }) => {
  const errorHandling = data?.errorHandling;
  if (!errorHandling || type === 'trigger') return null;

  const onError = errorHandling.onError || 'stop';
  const retry = errorHandling.retry;
  const showRetry = retry?.enabled && !['loop', 'parallel', 'human_in_loop', 'wait_for_event'].includes(type);
  const badges = [];
  if (showRetry) badges.push(`↻ ${retry.maxAttempts || 3}`);
  if (onError === 'continue') badges.push('on error: continue');

  return (
    <>
      {badges.length > 0 && (
        <div
          className="absolute -top-5 left-1 flex gap-1 pointer-events-none"
          style={{ zIndex: 10 }}
        >
          {badges.map(badge => (
            <span key={badge} className="px-1.5 py-0.5 text-[10px] leading-none rounded bg-red-50 text-red-600 border border-red-200 whitespace-nowrap">
              {badge}
            </span>
          ))}
        </div>
      )}
      {onError === 'error_branch' && (
        <>
          <Handle
            type="source"
            position={Position.Bottom}
            id={ERROR_HANDLE_ID}
            isConnectable={isConnectable}
            title="On error"
            style={{
              left: '85%',
              background: '#ef4444',
              border: '2px solid #fff',
              width: 12,
              height: 12,
              zIndex: 10,
            }}
            onClick={(e) => e.stopPropagation()}
          />
          <div
            className="absolute text-[10px] font-medium text-red-600 pointer-events-none whitespace-nowrap"
            style={{ left: '85%', bottom: -20, transform: 'translateX(-50%)', zIndex: 10 }}
          >
            on error
          </div>
        </>
      )}
    </>
  );
};

// Higher-order component to add resize functionality to any node
export const withResize = (Component) => {
  return (props) => {
    const { selected } = props;

    return (
      <>
        <NodeResizer
          isVisible={!!selected}
          minWidth={DEFAULT_NODE_DIMENSIONS.minWidth}
          minHeight={DEFAULT_NODE_DIMENSIONS.minHeight}
          maxWidth={DEFAULT_NODE_DIMENSIONS.maxWidth}
          maxHeight={DEFAULT_NODE_DIMENSIONS.maxHeight}
          handleClassName="corner"
          lineClassName="line"
        />
        <Component {...props} />
        <ErrorHandlingDecorations type={props.type} data={props.data} isConnectable={props.isConnectable} />
      </>
    );
  };
};
