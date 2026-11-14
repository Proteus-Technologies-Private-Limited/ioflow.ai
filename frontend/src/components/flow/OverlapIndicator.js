import React from 'react';
import { Square3Stack3DIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

/**
 * Component to display overlap indicators on nodes and edges
 */
const OverlapIndicator = ({ 
  overlappingCount = 0, 
  type = 'node', // 'node' or 'edge'
  position = 'top-right',
  showWarning = false,
  className = ''
}) => {
  if (overlappingCount === 0) return null;

  // Position classes based on position prop
  const positionClasses = {
    'top-right': 'top-1 right-1',
    'top-left': 'top-1 left-1',
    'bottom-right': 'bottom-1 right-1',
    'bottom-left': 'bottom-1 left-1',
  };

  const baseClasses = `absolute ${positionClasses[position]} z-50 flex items-center gap-1 ${className}`;

  return (
    <div className={baseClasses}>
      {/* Stack indicator */}
      <div 
        className="bg-purple-500 text-white rounded-full p-1 shadow-lg flex items-center justify-center"
        title={`${overlappingCount} overlapping ${type}${overlappingCount > 1 ? 's' : ''}`}
      >
        <div className="relative">
          <Square3Stack3DIcon className="w-4 h-4" />
          {overlappingCount > 1 && (
            <span className="absolute -top-2 -right-2 bg-red-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center font-bold">
              {overlappingCount > 9 ? '9+' : overlappingCount}
            </span>
          )}
        </div>
      </div>

      {/* Warning indicator for significant overlap */}
      {showWarning && (
        <div 
          className="bg-yellow-500 text-white rounded-full p-1 shadow-lg animate-pulse"
          title="Significant overlap detected"
        >
          <ExclamationTriangleIcon className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};

/**
 * Floating overlap summary panel
 */
export const OverlapSummary = ({ nodeOverlaps, edgeOverlaps, onNodeClick, className = '' }) => {
  const totalNodeOverlaps = Object.keys(nodeOverlaps || {}).length;
  const totalEdgeOverlaps = Object.keys(edgeOverlaps || {}).length;

  if (totalNodeOverlaps === 0 && totalEdgeOverlaps === 0) return null;

  return (
    <div className={`bg-white border border-purple-300 rounded-lg shadow-lg p-3 ${className}`}>
      <div className="flex items-center gap-2 mb-2">
        <Square3Stack3DIcon className="w-5 h-5 text-purple-600" />
        <span className="font-semibold text-sm text-gray-700">Overlap Detection</span>
      </div>
      
      {totalNodeOverlaps > 0 && (
        <div className="mb-2">
          <div className="text-xs text-gray-600 mb-1">
            {totalNodeOverlaps} node{totalNodeOverlaps > 1 ? 's' : ''} overlapping
          </div>
          <div className="flex flex-wrap gap-1">
            {Object.entries(nodeOverlaps).slice(0, 5).map(([nodeId, overlappingIds]) => (
              <button
                key={nodeId}
                onClick={() => onNodeClick?.(nodeId)}
                className="bg-purple-100 hover:bg-purple-200 text-purple-700 text-xs px-2 py-1 rounded transition-colors"
                title={`${nodeId} overlaps with ${overlappingIds.join(', ')}`}
              >
                {nodeId}
              </button>
            ))}
            {totalNodeOverlaps > 5 && (
              <span className="text-xs text-gray-500 px-2 py-1">
                +{totalNodeOverlaps - 5} more
              </span>
            )}
          </div>
        </div>
      )}

      {totalEdgeOverlaps > 0 && (
        <div>
          <div className="text-xs text-gray-600 mb-1">
            {totalEdgeOverlaps} edge{totalEdgeOverlaps > 1 ? 's' : ''} overlapping
          </div>
          <div className="text-xs text-gray-500">
            Consider reorganizing the flow for better clarity
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Visual overlay to highlight overlapping areas
 */
export const OverlapHighlight = ({ bounds, color = 'purple', opacity = 0.2 }) => {
  return (
    <div
      className="absolute pointer-events-none"
      style={{
        left: bounds.x,
        top: bounds.y,
        width: bounds.width,
        height: bounds.height,
        backgroundColor: `${color}`,
        opacity: opacity,
        border: `2px dashed ${color}`,
        borderRadius: '4px',
        zIndex: 1000,
      }}
    />
  );
};

export default OverlapIndicator;