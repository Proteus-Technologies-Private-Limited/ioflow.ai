/**
 * Utility functions for detecting overlapping nodes and edges in the flow designer
 */

/**
 * Check if two rectangles overlap
 * @param {Object} rect1 - First rectangle {x, y, width, height}
 * @param {Object} rect2 - Second rectangle {x, y, width, height}
 * @returns {boolean} True if rectangles overlap
 */
export const doRectanglesOverlap = (rect1, rect2) => {
  return !(
    rect1.x + rect1.width <= rect2.x ||
    rect2.x + rect2.width <= rect1.x ||
    rect1.y + rect1.height <= rect2.y ||
    rect2.y + rect2.height <= rect1.y
  );
};

/**
 * Get the bounding box of a node
 * @param {Object} node - Node object with position and dimensions
 * @returns {Object} Bounding box {x, y, width, height}
 */
export const getNodeBounds = (node) => {
  const width = node.width || node.measured?.width || 200;
  const height = node.height || node.measured?.height || 100;
  
  return {
    x: node.position.x,
    y: node.position.y,
    width,
    height
  };
};

/**
 * Check if a point is near a line segment (for edge overlap detection)
 * @param {Object} point - Point {x, y}
 * @param {Object} lineStart - Line start point {x, y}
 * @param {Object} lineEnd - Line end point {x, y}
 * @param {number} threshold - Distance threshold for considering "near"
 * @returns {boolean} True if point is near the line
 */
export const isPointNearLine = (point, lineStart, lineEnd, threshold = 5) => {
  const A = point.x - lineStart.x;
  const B = point.y - lineStart.y;
  const C = lineEnd.x - lineStart.x;
  const D = lineEnd.y - lineStart.y;

  const dot = A * C + B * D;
  const lenSq = C * C + D * D;
  let param = -1;
  
  if (lenSq !== 0) {
    param = dot / lenSq;
  }

  let xx, yy;

  if (param < 0) {
    xx = lineStart.x;
    yy = lineStart.y;
  } else if (param > 1) {
    xx = lineEnd.x;
    yy = lineEnd.y;
  } else {
    xx = lineStart.x + param * C;
    yy = lineStart.y + param * D;
  }

  const dx = point.x - xx;
  const dy = point.y - yy;
  const distance = Math.sqrt(dx * dx + dy * dy);

  return distance <= threshold;
};

/**
 * Check if two edges overlap (cross or are very close)
 * @param {Object} edge1Path - First edge path points
 * @param {Object} edge2Path - Second edge path points
 * @returns {boolean} True if edges overlap
 */
export const doEdgesOverlap = (edge1Path, edge2Path) => {
  // Simple check: if edges share significant path segments
  // This is a simplified version - can be enhanced for more complex cases
  
  if (!edge1Path || !edge2Path || edge1Path.length < 2 || edge2Path.length < 2) {
    return false;
  }

  // Check if any segment of edge1 is close to any segment of edge2
  for (let i = 0; i < edge1Path.length - 1; i++) {
    for (let j = 0; j < edge2Path.length - 1; j++) {
      const seg1Start = edge1Path[i];
      const seg1End = edge1Path[i + 1];
      const seg2Start = edge2Path[j];
      const seg2End = edge2Path[j + 1];

      // Check if segments are parallel and close
      if (areSegmentsClose(seg1Start, seg1End, seg2Start, seg2End)) {
        return true;
      }
    }
  }

  return false;
};

/**
 * Check if two line segments are close to each other
 */
const areSegmentsClose = (seg1Start, seg1End, seg2Start, seg2End, threshold = 10) => {
  // Check if any endpoint of seg2 is close to seg1
  if (isPointNearLine(seg2Start, seg1Start, seg1End, threshold) ||
      isPointNearLine(seg2End, seg1Start, seg1End, threshold)) {
    return true;
  }
  
  // Check if any endpoint of seg1 is close to seg2
  if (isPointNearLine(seg1Start, seg2Start, seg2End, threshold) ||
      isPointNearLine(seg1End, seg2Start, seg2End, threshold)) {
    return true;
  }

  return false;
};

/**
 * Find all overlapping nodes in a flow
 * @param {Array} nodes - Array of nodes
 * @returns {Object} Map of node IDs to arrays of overlapping node IDs
 */
export const findOverlappingNodes = (nodes) => {
  const overlaps = {};

  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const node1 = nodes[i];
      const node2 = nodes[j];
      
      const bounds1 = getNodeBounds(node1);
      const bounds2 = getNodeBounds(node2);

      if (doRectanglesOverlap(bounds1, bounds2)) {
        // Add to overlaps map
        if (!overlaps[node1.id]) {
          overlaps[node1.id] = [];
        }
        if (!overlaps[node2.id]) {
          overlaps[node2.id] = [];
        }
        
        overlaps[node1.id].push(node2.id);
        overlaps[node2.id].push(node1.id);
      }
    }
  }

  return overlaps;
};

/**
 * Find overlapping edges
 * @param {Array} edges - Array of edges with path data
 * @returns {Object} Map of edge IDs to arrays of overlapping edge IDs
 */
export const findOverlappingEdges = (edges) => {
  const overlaps = {};

  for (let i = 0; i < edges.length; i++) {
    for (let j = i + 1; j < edges.length; j++) {
      const edge1 = edges[i];
      const edge2 = edges[j];

      // Skip if edges don't have path data
      if (!edge1.path || !edge2.path) continue;

      if (doEdgesOverlap(edge1.path, edge2.path)) {
        if (!overlaps[edge1.id]) {
          overlaps[edge1.id] = [];
        }
        if (!overlaps[edge2.id]) {
          overlaps[edge2.id] = [];
        }

        overlaps[edge1.id].push(edge2.id);
        overlaps[edge2.id].push(edge1.id);
      }
    }
  }

  return overlaps;
};

/**
 * Calculate overlap percentage between two rectangles
 * @param {Object} rect1 - First rectangle
 * @param {Object} rect2 - Second rectangle
 * @returns {number} Overlap percentage (0-100)
 */
export const calculateOverlapPercentage = (rect1, rect2) => {
  if (!doRectanglesOverlap(rect1, rect2)) {
    return 0;
  }

  const xOverlap = Math.max(0, 
    Math.min(rect1.x + rect1.width, rect2.x + rect2.width) - 
    Math.max(rect1.x, rect2.x)
  );
  
  const yOverlap = Math.max(0,
    Math.min(rect1.y + rect1.height, rect2.y + rect2.height) - 
    Math.max(rect1.y, rect2.y)
  );

  const overlapArea = xOverlap * yOverlap;
  const minArea = Math.min(rect1.width * rect1.height, rect2.width * rect2.height);

  return (overlapArea / minArea) * 100;
};

/**
 * Get z-index order of overlapping nodes
 * @param {Array} nodes - Array of nodes
 * @param {Object} overlaps - Map of overlapping nodes
 * @returns {Object} Map of node IDs to their relative z-index
 */
export const getZIndexOrder = (nodes, overlaps) => {
  const zIndexMap = {};
  
  // Initialize all nodes with z-index 0
  nodes.forEach(node => {
    zIndexMap[node.id] = node.zIndex || 0;
  });

  // For overlapping nodes, determine which is on top
  Object.keys(overlaps).forEach(nodeId => {
    const overlappingIds = overlaps[nodeId];
    overlappingIds.forEach(otherId => {
      // The node with higher z-index or later in array is on top
      const node = nodes.find(n => n.id === nodeId);
      const otherNode = nodes.find(n => n.id === otherId);
      
      if (node && otherNode) {
        const nodeIndex = nodes.indexOf(node);
        const otherIndex = nodes.indexOf(otherNode);
        
        if (nodeIndex > otherIndex) {
          zIndexMap[nodeId] = Math.max(zIndexMap[nodeId], zIndexMap[otherId] + 1);
        }
      }
    });
  });

  return zIndexMap;
};