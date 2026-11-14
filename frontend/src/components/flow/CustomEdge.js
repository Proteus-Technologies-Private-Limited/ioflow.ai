import React from 'react';
import { getBezierPath, EdgeLabelRenderer, BaseEdge } from 'reactflow';

const CustomEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
  selected,
  sourceHandleId,
}) => {
  // Edges leaving a node's error output only run when that node fails
  const isErrorEdge = sourceHandleId === 'error';
  const label = data?.label || (isErrorEdge ? 'on error' : null);

  // Custom path calculation for smoother curves
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    curvature: 0.25,
  });

  return (
    <>
      <BaseEdge 
        id={id} 
        path={edgePath} 
        style={{
          ...style,
          strokeWidth: selected ? 3 : 2,
          // blue-500 when selected, red-500 for error branches, slate-400 default
          stroke: selected ? '#3b82f6' : isErrorEdge ? '#ef4444' : '#94a3b8',
          ...(isErrorEdge ? { strokeDasharray: '6 4' } : {}),
          transition: 'stroke 0.2s ease, stroke-width 0.2s ease',
        }} 
        markerEnd={markerEnd}
        className="react-flow__edge-path"
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className={`px-2 py-1 text-xs bg-white border rounded shadow-sm ${isErrorEdge ? 'border-red-200 text-red-600' : 'border-gray-200'}`}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};

export default CustomEdge;