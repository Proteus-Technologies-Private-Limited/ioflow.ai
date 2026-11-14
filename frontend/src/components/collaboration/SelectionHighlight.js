import React, { useEffect, useState } from 'react';

const SelectionHighlight = ({ 
  participant, 
  selectedNodeIds = [], 
  selectedEdgeIds = [],
  nodes = [],
  edges = [],
  getNodeElement,
  getEdgeElement
}) => {
  const [highlights, setHighlights] = useState([]);

  useEffect(() => {
    const newHighlights = [];

    // Process selected nodes
    selectedNodeIds.forEach(nodeId => {
      const nodeElement = getNodeElement ? getNodeElement(nodeId) : document.querySelector(`[data-node-id="${nodeId}"]`);
      
      if (nodeElement) {
        const rect = nodeElement.getBoundingClientRect();
        newHighlights.push({
          type: 'node',
          id: nodeId,
          x: rect.left,
          y: rect.top,
          width: rect.width,
          height: rect.height
        });
      }
    });

    // Process selected edges
    selectedEdgeIds.forEach(edgeId => {
      const edgeElement = getEdgeElement ? getEdgeElement(edgeId) : document.querySelector(`[data-edge-id="${edgeId}"]`);
      
      if (edgeElement) {
        // For edges, we'll add a glow effect instead of a box
        newHighlights.push({
          type: 'edge',
          id: edgeId,
          element: edgeElement
        });
      }
    });

    setHighlights(newHighlights);
  }, [selectedNodeIds, selectedEdgeIds, nodes, edges, getNodeElement, getEdgeElement]);

  const getInitials = (name) => {
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <>
      {highlights.map(highlight => {
        if (highlight.type === 'node') {
          return (
            <div
              key={`node-${highlight.id}`}
              className="absolute pointer-events-none transition-all duration-200"
              style={{
                left: highlight.x - 4,
                top: highlight.y - 4,
                width: highlight.width + 8,
                height: highlight.height + 8,
                border: `2px dashed ${participant.color}`,
                borderRadius: '8px',
                zIndex: 40
              }}
            >
              {/* Participant indicator */}
              <div
                className="absolute -top-8 left-0 flex items-center space-x-1 px-2 py-1 rounded-md shadow-sm bg-white"
                style={{ borderColor: participant.color, borderWidth: '1px', borderStyle: 'solid' }}
              >
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-white"
                  style={{ backgroundColor: participant.color, fontSize: '10px' }}
                >
                  {getInitials(participant.display_name)}
                </div>
                <span className="text-xs text-gray-700">
                  {participant.display_name}
                </span>
              </div>
            </div>
          );
        } else if (highlight.type === 'edge' && highlight.element) {
          // Apply glow effect to edge
          highlight.element.style.filter = `drop-shadow(0 0 4px ${participant.color})`;
          
          // Clean up the effect after component unmount
          return null;
        }
        return null;
      })}
    </>
  );
};

// Container component to manage multiple participants' selections
export const CollaborativeSelections = ({ 
  participants = [], 
  nodes = [],
  edges = [],
  getNodeElement,
  getEdgeElement
}) => {
  // Filter out participants without selections
  const participantsWithSelections = participants.filter(p => 
    (p.selected_nodes && p.selected_nodes.length > 0) || 
    (p.selected_edges && p.selected_edges.length > 0)
  );

  return (
    <div className="absolute inset-0 pointer-events-none">
      {participantsWithSelections.map(participant => (
        <SelectionHighlight
          key={participant.id}
          participant={participant}
          selectedNodeIds={participant.selected_nodes || []}
          selectedEdgeIds={participant.selected_edges || []}
          nodes={nodes}
          edges={edges}
          getNodeElement={getNodeElement}
          getEdgeElement={getEdgeElement}
        />
      ))}
    </div>
  );
};

export default SelectionHighlight;