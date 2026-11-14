// Utility functions for handling node ID changes in flows

/**
 * Updates all references to a node ID throughout the flow
 * @param {string} oldId - The old node ID
 * @param {string} newId - The new node ID
 * @param {Array} nodes - Current nodes array
 * @param {Array} edges - Current edges array
 * @returns {Object} Updated nodes and edges
 */
export const updateNodeIdReferences = (oldId, newId, nodes, edges) => {
  // Update the node itself
  const updatedNodes = nodes.map(node => {
    if (node.id === oldId) {
      return { ...node, id: newId };
    }
    
    // Update any references in node data (e.g., for loop nodes that might reference other nodes)
    if (node.data) {
      const updatedData = { ...node.data };
      
      // Check for any properties that might contain node IDs
      Object.keys(updatedData).forEach(key => {
        if (typeof updatedData[key] === 'string' && updatedData[key] === oldId) {
          updatedData[key] = newId;
        } else if (Array.isArray(updatedData[key])) {
          // Check arrays for node ID references
          updatedData[key] = updatedData[key].map(item => 
            item === oldId ? newId : item
          );
        } else if (typeof updatedData[key] === 'object' && updatedData[key] !== null) {
          // Recursively check nested objects
          updatedData[key] = updateNestedReferences(updatedData[key], oldId, newId);
        }
      });
      
      return { ...node, data: updatedData };
    }
    
    return node;
  });
  
  // Update edges
  const updatedEdges = edges.map(edge => {
    const updates = {};
    
    if (edge.source === oldId) {
      updates.source = newId;
    }
    
    if (edge.target === oldId) {
      updates.target = newId;
    }
    
    // Update edge ID if it contains the node ID
    if (Object.keys(updates).length > 0) {
      const newEdgeId = edge.id.replace(oldId, newId);
      return { ...edge, ...updates, id: newEdgeId };
    }
    
    return edge;
  });
  
  return { nodes: updatedNodes, edges: updatedEdges };
};

/**
 * Recursively updates node ID references in nested objects
 * @param {Object} obj - Object to search for references
 * @param {string} oldId - The old node ID
 * @param {string} newId - The new node ID
 * @returns {Object} Updated object
 */
const updateNestedReferences = (obj, oldId, newId) => {
  if (Array.isArray(obj)) {
    return obj.map(item => {
      if (typeof item === 'string' && item === oldId) {
        return newId;
      } else if (typeof item === 'object' && item !== null) {
        return updateNestedReferences(item, oldId, newId);
      }
      return item;
    });
  }
  
  const updated = {};
  Object.keys(obj).forEach(key => {
    if (typeof obj[key] === 'string' && obj[key] === oldId) {
      updated[key] = newId;
    } else if (Array.isArray(obj[key])) {
      updated[key] = obj[key].map(item => 
        item === oldId ? newId : (typeof item === 'object' ? updateNestedReferences(item, oldId, newId) : item)
      );
    } else if (typeof obj[key] === 'object' && obj[key] !== null) {
      updated[key] = updateNestedReferences(obj[key], oldId, newId);
    } else {
      updated[key] = obj[key];
    }
  });
  
  return updated;
};

/**
 * Validates if a node ID is unique
 * @param {string} nodeId - The node ID to validate
 * @param {Array} nodes - Current nodes array
 * @param {string} currentNodeId - The current node's ID (for editing existing nodes)
 * @returns {Object} Validation result { isValid: boolean, error: string }
 */
export const validateNodeId = (nodeId, nodes, currentNodeId = null) => {
  // Check if empty
  if (!nodeId || nodeId.trim() === '') {
    return { isValid: false, error: 'Node ID cannot be empty' };
  }
  
  // Check if it contains only valid characters (alphanumeric, underscore, hyphen)
  const validIdPattern = /^[a-zA-Z0-9_-]+$/;
  if (!validIdPattern.test(nodeId)) {
    return { isValid: false, error: 'Node ID can only contain letters, numbers, underscores, and hyphens' };
  }
  
  // Check if it's a reserved word
  const reservedWords = ['trigger', 'action', 'condition', 'transform', 'response', 'loop'];
  if (reservedWords.includes(nodeId.toLowerCase())) {
    return { isValid: false, error: `"${nodeId}" is a reserved word` };
  }
  
  // Check for duplicates
  const duplicate = nodes.find(node => 
    node.id === nodeId && node.id !== currentNodeId
  );
  
  if (duplicate) {
    return { isValid: false, error: 'A node with this ID already exists' };
  }
  
  return { isValid: true, error: null };
};

/**
 * Generates a unique node ID based on node type
 * @param {string} type - The node type
 * @param {Array} nodes - Current nodes array
 * @returns {string} A unique node ID
 */
export const generateUniqueNodeId = (type, nodes) => {
  const baseId = type.toLowerCase();
  let counter = 1;
  let newId = `${baseId}_${counter}`;
  
  // Find a unique ID
  while (nodes.some(node => node.id === newId)) {
    counter++;
    newId = `${baseId}_${counter}`;
  }
  
  return newId;
};