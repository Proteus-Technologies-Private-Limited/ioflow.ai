import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  ChevronRightIcon,
  ChevronDownIcon,
  CursorArrowRaysIcon,
  CodeBracketIcon,
  CalculatorIcon,
  DocumentTextIcon,
  FolderIcon,
  DocumentIcon,
  ArrowPathIcon,
  GlobeAltIcon,
  BoltIcon,
} from '@heroicons/react/24/outline';

const NestedVariableSelector = ({
  value,
  onChange,
  availableVariables = {},
  placeholder = "Select variable...",
  mode = 'edit', // 'edit' or 'view'
  allowManualInput = false, // Allow typing custom values
  inline = false // Show expanded tree directly without button/dropdown
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [expandedNodes, setExpandedNodes] = useState({});
  const hasAutoExpandedRef = useRef(false);
  const dropdownRef = useRef(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Helper to check if a key is metadata that should be hidden
  const isMetadataKey = (key) => {
    return key === '_description' || key === '{any_variable}' || key.startsWith('_');
  };

  // Detect nested structure in variables
  const detectStructure = (obj, path = '', depth = 0, skipMetadata = false) => {
    const items = [];
    const maxDepth = 5; // Prevent infinite recursion

    if (!obj || typeof obj !== 'object' || depth > maxDepth) return items;

    Object.entries(obj).forEach(([key, value]) => {
      // Skip metadata fields if requested
      if (skipMetadata && isMetadataKey(key)) {
        return;
      }
      // Use dot notation for all keys - backend now handles both formats
      const currentPath = path ? `${path}.${key}` : key;
      
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        // This is a nested object
        const children = detectStructure(value, currentPath, depth + 1, skipMetadata);
        
        // Check if this object contains arrays (useful for nested data structures)
        const containsArrays = children.some(child => child.type === 'array');
        
        items.push({
          path: currentPath,
          key: key,
          type: 'object',
          hasChildren: true,
          children: children,
          containsArrays: containsArrays,
          description: containsArrays ? '📦 Contains arrays' : `Object with ${children.length} properties`
        });
      } else if (Array.isArray(value)) {
        // This is an array
        let arrayDescription = `Array[${value.length}]`;
        let sampleStructure = null;
        
        // If array has items, show sample structure
        if (value.length > 0) {
          const firstItem = value[0];
          if (typeof firstItem === 'object' && firstItem !== null) {
            // Show structure of first item
            const sampleKeys = Object.keys(firstItem).slice(0, 3);
            arrayDescription = `Array[${value.length}] of objects {${sampleKeys.join(', ')}${sampleKeys.length < Object.keys(firstItem).length ? '...' : ''}}`;
            
            // Also allow exploring the structure of array items
            sampleStructure = detectStructure(firstItem, `${currentPath}[0]`, depth + 1, skipMetadata);
          } else {
            arrayDescription = `Array[${value.length}] of ${typeof firstItem}s`;
          }
        }
        
        items.push({
          path: currentPath,
          key: key,
          type: 'array',
          hasChildren: sampleStructure && sampleStructure.length > 0,
          children: sampleStructure || [],
          description: arrayDescription,
          arrayLength: value.length,
          isLoopable: true // Mark arrays as loopable for visual indication
        });
      } else {
        // This is a leaf value
        let description = '';
        if (typeof value === 'string') {
          description = value.length > 50 ? value.substring(0, 50) + '...' : value;
        } else if (typeof value === 'boolean') {
          description = value ? 'true' : 'false';
        } else if (typeof value === 'number') {
          description = String(value);
        } else {
          description = String(value);
        }
        
        items.push({
          path: currentPath,
          key: key,
          type: typeof value,
          hasChildren: false,
          value: value,
          description: description
        });
      }
    });
    
    return items;
  };

  // Helper function to check if an object has any data
  const hasData = (obj) => {
    if (!obj) return false;
    if (typeof obj !== 'object') return false;
    return Object.keys(obj).length > 0;
  };

  // Build variable tree structure with business-friendly labels
  const buildVariableTree = () => {
    const tree = [];

    // Input variables (Trigger Input / Form Fields)
    if (hasData(availableVariables.input)) {
      const children = detectStructure(availableVariables.input, 'input', 0, false);
      if (children.length > 0) {
        tree.push({
          path: 'input',
          key: 'Trigger Input', // Business-friendly label
          technicalKey: 'input', // Keep original for reference
          type: 'category',
          icon: <CursorArrowRaysIcon className="w-4 h-4" />,
          hasChildren: true,
          children: children,
          description: 'Data from the trigger that started this flow',
          autoExpand: true // Auto-expand if has data
        });
      }
    }

    // Node outputs (Previous Steps)
    if (hasData(availableVariables.node_outputs)) {
      const nodeChildren = [];
      const nodeMetadata = availableVariables._nodeMetadata || {};

      // Get all node entries and sort by execution order (if available)
      const nodeEntries = Object.entries(availableVariables.node_outputs);

      nodeEntries.forEach(([nodeId, nodeData], index) => {
        // Use dot notation for all node IDs - backend now handles both formats
        const nodePath = `node_outputs.${nodeId}`;

        // Get node label from metadata or use node ID as fallback
        const nodeInfo = nodeMetadata[nodeId] || {};
        const nodeLabel = nodeInfo.label || nodeId;

        const childData = detectStructure(nodeData, nodePath, 0, false);
        if (childData.length > 0) {
          // Only auto-expand the last node in the list
          const isLastNode = index === nodeEntries.length - 1;

          nodeChildren.push({
            path: nodePath,
            key: nodeLabel, // Display the label instead of ID
            actualKey: nodeId, // Keep the actual ID for reference
            type: 'object',
            nodeType: nodeInfo.type, // Store node type for icon
            hasChildren: true,
            children: childData,
            autoExpand: isLastNode // Only expand last node
          });
        }
      });

      // Only add category if there are actual nodes with data
      if (nodeChildren.length > 0) {
        tree.push({
          path: 'node_outputs',
          key: 'Previous Steps', // Business-friendly label
          technicalKey: 'node_outputs', // Keep original for reference
          type: 'category',
          icon: <CodeBracketIcon className="w-4 h-4" />,
          hasChildren: true,
          children: nodeChildren,
          description: 'Data from earlier steps in this flow',
          autoExpand: true // Auto-expand category
        });
      }
    }

    // Flow variables (Flow Information)
    if (hasData(availableVariables.flow)) {
      const children = detectStructure(availableVariables.flow, 'flow', 0, false);
      if (children.length > 0) {
        tree.push({
          path: 'flow',
          key: 'Flow Information', // Business-friendly label
          technicalKey: 'flow', // Keep original for reference
          type: 'category',
          icon: <CalculatorIcon className="w-4 h-4" />,
          hasChildren: true,
          children: children,
          description: 'Information about this flow execution',
          autoExpand: false // Don't auto-expand - rarely used
        });
      }
    }

    // Data variables
    if (hasData(availableVariables.data)) {
      const children = detectStructure(availableVariables.data, 'data', 0, true); // Skip metadata
      if (children.length > 0) {
        tree.push({
          path: 'data',
          key: 'Data', // Already business-friendly
          technicalKey: 'data', // Keep original for reference
          type: 'category',
          icon: <DocumentTextIcon className="w-4 h-4" />,
          hasChildren: true,
          children: children,
          description: 'Additional data available in this context',
          autoExpand: true // Auto-expand if has data
        });
      }
    }

    // Loop variables (Current Item)
    if (hasData(availableVariables.loop)) {
      const children = detectStructure(availableVariables.loop, 'loop', 0, false);
      if (children.length > 0) {
        tree.push({
          path: 'loop',
          key: 'Current Item', // Business-friendly label
          technicalKey: 'loop', // Keep original for reference
          type: 'category',
          icon: <ArrowPathIcon className="w-4 h-4" />,
          hasChildren: true,
          children: children,
          description: 'The current item being processed in the loop',
          autoExpand: true // Auto-expand if has data
        });
      }
    }

    // Global variables
    if (hasData(availableVariables.global)) {
      const children = detectStructure(availableVariables.global, 'global', 0, true); // Skip metadata
      if (children.length > 0) {
        tree.push({
          path: 'global',
          key: 'Global Variables', // Business-friendly label
          technicalKey: 'global', // Keep original for reference
          type: 'category',
          icon: <GlobeAltIcon className="w-4 h-4" />,
          hasChildren: true,
          children: children,
          description: 'Variables available across all flows',
          autoExpand: true // Auto-expand if has data
        });
      }
    }

    return tree;
  };

  const variableTree = useMemo(() => buildVariableTree(), [availableVariables]);

  // Auto-expand nodes based on autoExpand property (only once)
  useEffect(() => {
    if ((inline || isOpen) && !hasAutoExpandedRef.current && variableTree.length > 0) {
      const autoExpanded = {};

      // Recursively expand nodes that have autoExpand = true
      const expandTree = (nodes) => {
        nodes.forEach(node => {
          if (node.autoExpand) {
            autoExpanded[node.path] = true;
            // Recursively expand children if they also have autoExpand
            if (node.children) {
              expandTree(node.children);
            }
          }
        });
      };

      expandTree(variableTree);
      setExpandedNodes(autoExpanded);
      hasAutoExpandedRef.current = true;
    }
  }, [inline, isOpen, variableTree]);

  // Reset auto-expand flag when modal closes
  useEffect(() => {
    if (!inline && !isOpen) {
      hasAutoExpandedRef.current = false;
    }
  }, [inline, isOpen]);

  // Toggle node expansion
  const toggleExpanded = (path) => {
    setExpandedNodes(prev => ({
      ...prev,
      [path]: !prev[path]
    }));
  };

  // Filter tree based on search
  const filterTree = (items, searchTerm) => {
    if (!searchTerm) return items;
    
    return items.reduce((acc, item) => {
      const matches = item.path.toLowerCase().includes(searchTerm.toLowerCase()) ||
                     item.key.toLowerCase().includes(searchTerm.toLowerCase());
      
      if (item.hasChildren) {
        const filteredChildren = filterTree(item.children, searchTerm);
        if (matches || filteredChildren.length > 0) {
          acc.push({
            ...item,
            children: filteredChildren,
            expanded: true // Auto-expand when searching
          });
        }
      } else if (matches) {
        acc.push(item);
      }
      
      return acc;
    }, []);
  };

  const filteredTree = filterTree(variableTree, search);

  // Render tree node
  const renderTreeNode = (node, level = 0) => {
    const isExpanded = search ? true : expandedNodes[node.path];
    const indent = level * 16;
    
    return (
      <div key={node.path}>
        <div
          className={`flex items-center px-2 py-1 hover:bg-gray-100 cursor-pointer ${
            value === node.path ? 'bg-blue-50 text-blue-700' : ''
          }`}
          style={{ paddingLeft: `${indent + 8}px` }}
          onClick={(e) => {
            if (node.hasChildren) {
              // Allow selecting parent nodes with double-click or alt/option-click
              if (e.detail === 2 || e.altKey) {
                onChange(node.path);
                setIsOpen(false);
                setSearch('');
              } else {
                toggleExpanded(node.path);
              }
            } else {
              onChange(node.path);
              setIsOpen(false);
              setSearch('');
            }
          }}
        >
          {node.hasChildren && (
            <span className="mr-1" onClick={(e) => {
              e.stopPropagation();
              toggleExpanded(node.path);
            }}>
              {isExpanded ? (
                <ChevronDownIcon className="w-3 h-3" />
              ) : (
                <ChevronRightIcon className="w-3 h-3" />
              )}
            </span>
          )}
          
          {node.icon || (
            node.nodeType === 'action' ? <BoltIcon className="w-4 h-4 mr-2 text-blue-500" /> :
            node.nodeType === 'transform' ? <CodeBracketIcon className="w-4 h-4 mr-2 text-purple-500" /> :
            node.type === 'object' && node.containsArrays ? <FolderIcon className="w-4 h-4 mr-2 text-orange-500" /> :
            node.type === 'object' ? <FolderIcon className="w-4 h-4 mr-2 text-gray-400" /> :
            node.type === 'array' ? <ArrowPathIcon className="w-4 h-4 mr-2 text-green-500" /> :
            <DocumentIcon className="w-4 h-4 mr-2 text-gray-400" />
          )}
          
          <span className={`font-medium truncate flex-1 ${node.isLoopable ? 'text-green-700' : ''}`}>
            {node.key}
          </span>
          
          {node.type !== 'category' && (
            <>
              {node.isLoopable && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-green-100 text-green-700 rounded">
                  Loopable
                </span>
              )}
              {node.arrayLength !== undefined && (
                <span className="ml-1 text-xs text-gray-500">
                  [{node.arrayLength}]
                </span>
              )}
              {node.type === 'object' && !node.containsArrays && (
                <span className="ml-2 text-xs text-gray-500">
                  Object
                </span>
              )}
              {node.hasChildren && !node.isLoopable && (
                <span className="ml-1 text-xs text-gray-400" title="Double-click or Alt+click to select parent">
                  (Alt+click)
                </span>
              )}
            </>
          )}
          
          {node.description && (
            <span className="ml-2 text-xs text-gray-400 truncate" title={node.description}>
              {node.description}
            </span>
          )}
        </div>
        
        {node.hasChildren && isExpanded && (
          <div>
            {node.children.map(child => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    );
  };

  if (mode === 'view') {
    return <span className="text-gray-900">{value || '-'}</span>;
  }

  // Inline mode - show tree directly without button/dropdown
  if (inline) {
    return (
      <div className="w-full">
        <div className="mb-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search variables..."
            className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            autoFocus
          />
          <div className="mt-2 text-xs text-gray-500">
            💡 Tip: Alt+click or double-click to select object/array nodes
          </div>
        </div>

        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <div className="overflow-y-auto max-h-96 bg-white">
            {filteredTree.length > 0 ? (
              filteredTree.map(node => renderTreeNode(node))
            ) : variableTree.length === 0 ? (
              <div className="px-4 py-12 text-center">
                <div className="text-sm text-gray-500 mb-2">No data available yet</div>
                <div className="text-xs text-gray-400">
                  Add previous steps or configure your trigger to see available data
                </div>
              </div>
            ) : (
              <div className="px-4 py-8 text-center text-sm text-gray-500">
                No variables match your search
              </div>
            )}
          </div>
        </div>

        <div className="mt-3">
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Or type custom path manually..."
            className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono"
          />
        </div>
      </div>
    );
  }

  // Regular dropdown mode
  return (
    <div className="relative" ref={dropdownRef}>
      {allowManualInput ? (
        <div className="relative">
          <input
            type="text"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className={`w-full px-3 py-2 pr-8 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 ${
              value ? 'bg-blue-50 border-blue-300 text-blue-900' : 'bg-white border-gray-300'
            }`}
          />
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
          >
            <ChevronDownIcon className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className="w-full px-3 py-2 text-left bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
        >
          <span className={`${value ? 'text-gray-900' : 'text-gray-500'} block truncate`}>
            {value || placeholder}
          </span>
        </button>
      )}

      {isOpen && (
        <div className="absolute z-10 mt-1 bg-white border border-gray-300 rounded-md shadow-lg max-h-96 overflow-hidden" style={{ minWidth: '300px', width: 'max-content', maxWidth: '600px' }}>
          <div className="p-2 border-b">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search variables..."
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="mt-1 text-xs text-gray-500">
              Tip: Alt+click or double-click to select object/array nodes
            </div>
          </div>

          <div className="overflow-y-auto max-h-80">
            {filteredTree.length > 0 ? (
              filteredTree.map(node => renderTreeNode(node))
            ) : variableTree.length === 0 ? (
              <div className="px-3 py-8 text-center">
                <div className="text-sm text-gray-500 mb-1">No data available yet</div>
                <div className="text-xs text-gray-400">
                  Add previous steps or configure your trigger to see available data
                </div>
              </div>
            ) : (
              <div className="px-3 py-2 text-sm text-gray-500">No variables match your search</div>
            )}
          </div>

          <div className="p-2 border-t">
            <input
              type="text"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder="Or type custom path..."
              className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default NestedVariableSelector;