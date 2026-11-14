import React, { useState } from 'react';
import { ArrowsPointingOutIcon } from '@heroicons/react/24/outline';
import { DEFAULT_NODE_DIMENSIONS } from './nodeConfig';

// Simpler resize wrapper with custom resize indicator
export const withSimpleResize = (Component) => {
  return (props) => {
    const { selected, id } = props;
    const [isResizing, setIsResizing] = useState(false);
    const [showResizeIcon, setShowResizeIcon] = useState(false);

    const handleMouseDown = (e) => {
      e.stopPropagation();
      e.preventDefault();
      
      const node = e.target.closest('.react-flow__node');
      if (!node) return;

      const startX = e.clientX;
      const startY = e.clientY;
      const startWidth = node.offsetWidth;
      const startHeight = node.offsetHeight;

      setIsResizing(true);

      const handleMouseMove = (e) => {
        const deltaX = e.clientX - startX;
        const deltaY = e.clientY - startY;
        
        const newWidth = Math.max(DEFAULT_NODE_DIMENSIONS.minWidth, 
          Math.min(DEFAULT_NODE_DIMENSIONS.maxWidth, startWidth + deltaX));
        const newHeight = Math.max(DEFAULT_NODE_DIMENSIONS.minHeight, 
          Math.min(DEFAULT_NODE_DIMENSIONS.maxHeight, startHeight + deltaY));

        // Update node dimensions through ReactFlow
        const event = new CustomEvent('nodeResize', {
          detail: { id, width: newWidth, height: newHeight }
        });
        window.dispatchEvent(event);
      };

      const handleMouseUp = () => {
        setIsResizing(false);
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    };

    return (
      <div 
        className="relative w-full h-full"
        onMouseEnter={() => selected && setShowResizeIcon(true)}
        onMouseLeave={() => !isResizing && setShowResizeIcon(false)}
      >
        <Component {...props} />
        
        {/* Simple resize handle */}
        {selected && showResizeIcon && (
          <div
            className="absolute bottom-1 right-1 w-5 h-5 bg-white rounded border border-gray-300 shadow-sm flex items-center justify-center cursor-se-resize hover:bg-gray-50 transition-colors"
            onMouseDown={handleMouseDown}
            style={{ zIndex: 10 }}
          >
            <ArrowsPointingOutIcon className="w-3 h-3 text-gray-600" />
          </div>
        )}
      </div>
    );
  };
};