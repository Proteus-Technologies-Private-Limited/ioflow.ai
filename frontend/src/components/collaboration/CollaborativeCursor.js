import React, { useEffect, useRef } from 'react';
import { MousePointer2 } from 'lucide-react';

const CollaborativeCursor = ({ 
  participant, 
  position, 
  containerRef,
  scale = 1 
}) => {
  const cursorRef = useRef(null);
  const labelRef = useRef(null);

  useEffect(() => {
    if (!cursorRef.current || !containerRef?.current) return;

    // Get container bounds
    const containerBounds = containerRef.current.getBoundingClientRect();
    
    // Calculate relative position
    const relativeX = position.x - containerBounds.left;
    const relativeY = position.y - containerBounds.top;

    // Apply position with scale
    cursorRef.current.style.transform = `translate(${relativeX * scale}px, ${relativeY * scale}px)`;
    
    // Ensure label stays within bounds
    if (labelRef.current) {
      const labelBounds = labelRef.current.getBoundingClientRect();
      const labelWidth = labelBounds.width;
      const labelHeight = labelBounds.height;

      // Adjust label position if it goes out of bounds
      let labelX = 20;
      let labelY = 20;

      if (relativeX + labelWidth + 20 > containerBounds.width) {
        labelX = -labelWidth - 5;
      }

      if (relativeY + labelHeight + 20 > containerBounds.height) {
        labelY = -labelHeight - 5;
      }

      labelRef.current.style.transform = `translate(${labelX}px, ${labelY}px)`;
    }
  }, [position, containerRef, scale]);

  const getInitials = (name) => {
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <div
      ref={cursorRef}
      className="absolute pointer-events-none z-50 transition-transform duration-100"
      style={{
        left: 0,
        top: 0,
      }}
    >
      {/* Cursor icon */}
      <div
        className="relative"
        style={{ color: participant.color }}
      >
        <MousePointer2 
          className="w-5 h-5 drop-shadow-md"
          fill={participant.color}
        />
        
        {/* Participant label */}
        <div
          ref={labelRef}
          className="absolute flex items-center space-x-1 px-2 py-1 rounded-md shadow-md bg-white border"
          style={{ 
            borderColor: participant.color,
            minWidth: '80px'
          }}
        >
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-semibold"
            style={{ backgroundColor: participant.color }}
          >
            {getInitials(participant.display_name)}
          </div>
          <span className="text-xs font-medium text-gray-700 whitespace-nowrap">
            {participant.display_name}
          </span>
        </div>
      </div>
    </div>
  );
};

// Container component to manage multiple cursors
export const CollaborativeCursors = ({ 
  participants, 
  containerRef,
  scale = 1 
}) => {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden">
      {participants.map(participant => (
        participant.cursor_position && (
          <CollaborativeCursor
            key={participant.id}
            participant={participant}
            position={participant.cursor_position}
            containerRef={containerRef}
            scale={scale}
          />
        )
      ))}
    </div>
  );
};

export default CollaborativeCursor;