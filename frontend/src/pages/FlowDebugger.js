import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Panel,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import '../components/flow/nodeStyles.css';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../utils/customToast';
import { getFullErrorMessage } from '../utils/errorHandler';
import HierarchicalExecutionLog from '../components/execution/HierarchicalExecutionLog';
import TransformDebugger from '../components/debug/TransformDebugger';
import TaskReviewModal from '../components/flows/TaskReviewModal';
import {
  ArrowLeftIcon,
  PlayIcon,
  PauseIcon,
  ForwardIcon,
  StopIcon,
  ArrowPathIcon,
  InformationCircleIcon,
  ClipboardDocumentListIcon,
  EyeIcon,
  EyeSlashIcon,
  XMarkIcon,
  PencilIcon,
  CodeBracketSquareIcon,
  HandRaisedIcon,
} from '@heroicons/react/24/outline';
import IsolatedField from '../components/flow/IsolatedParameterInput';

// Import node components from FlowDesigner
import TriggerNode from '../components/flow/TriggerNode';
import ActionNode from '../components/flow/ActionNode';
import ConditionNode from '../components/flow/ConditionNode';
import TransformNode from '../components/flow/TransformNode';
import ResponseNode from '../components/flow/ResponseNode';
import LoopNode from '../components/flow/LoopNode';
import HumanInLoopNode from '../components/flow/HumanInLoopNode';
import WaitForEventNode from '../components/flow/WaitForEventNode';
import CustomEdge from '../components/flow/CustomEdge';

// Node types configuration
const nodeTypes = {
  trigger: TriggerNode,
  action: ActionNode,
  condition: ConditionNode,
  transform: TransformNode,
  response: ResponseNode,
  loop: LoopNode,
  human_in_loop: HumanInLoopNode,
  wait_for_event: WaitForEventNode,
};

// Edge types configuration
const edgeTypes = {
  default: CustomEdge,
};

const FlowDebugger = () => {
  const { flowId } = useParams();
  const navigate = useNavigate();
  const { fitView } = useReactFlow();
  const [nodes, setNodes] = useNodesState([]);
  const [edges, setEdges] = useEdgesState([]);
  const [flowName, setFlowName] = useState('');
  const [flowDescription, setFlowDescription] = useState('');
  const [debugState, setDebugState] = useState('idle'); // idle, running, paused, completed
  const [currentNodeId, setCurrentNodeId] = useState(null);
  const [executionId, setExecutionId] = useState(null);
  const [executionLogs, setExecutionLogs] = useState([]);
  const [backendLogs, setBackendLogs] = useState([]);  // Logs fetched from backend
  const [nodeVariables, setNodeVariables] = useState({});
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [showVariables, setShowVariables] = useState(true);
  const [showLogs, setShowLogs] = useState(true);
  const [triggerData, setTriggerData] = useState({});
  const [showTriggerInputDialog, setShowTriggerInputDialog] = useState(false);
  const [manualVariables, setManualVariables] = useState([]);
  const [showNodeEditDialog, setShowNodeEditDialog] = useState(false);
  const [editingNode, setEditingNode] = useState(null);
  const [editedNodeConfig, setEditedNodeConfig] = useState({});
  const [editedVariables, setEditedVariables] = useState({});
  const [lastExecutedNodeId, setLastExecutedNodeId] = useState(null);
  const [executedNodes, setExecutedNodes] = useState([]); // Track all executed nodes
  const [transformDebugInfo, setTransformDebugInfo] = useState(null);
  const [showTransformDebugger, setShowTransformDebugger] = useState(false);
  const [transformDebugNodeId, setTransformDebugNodeId] = useState(null);
  const [executingNodeId, setExecutingNodeId] = useState(null); // Track currently executing node
  const [hitlTask, setHitlTask] = useState(null); // HITL task waiting for human review
  const [showHitlReview, setShowHitlReview] = useState(false); // Show HITL TaskReviewModal
  const [pendingBranches, setPendingBranches] = useState(0); // Fork-join branch tracking
  const wsRef = useRef(null);

  // Fetch flow data
  const { data: flowData, isLoading, error: flowError } = useQuery({
    queryKey: ['flow', flowId],
    queryFn: async () => {
      console.log('Fetching flow data for:', flowId);
      const response = await axios.get(`/api/v1/flows/${flowId}`);
      console.log('Flow data received:', response.data);
      return response.data;
    },
    enabled: !!flowId,
  });
  
  // Log flow fetch error
  useEffect(() => {
    if (flowError) {
      console.error('Error fetching flow:', flowError);
    }
  }, [flowError]);

  // Set flow data when loaded
  useEffect(() => {
    if (flowData) {
      setFlowName(flowData.flow_name);
      setFlowDescription(flowData.description || '');
      
      // Deep clone nodes to avoid reference issues
      const clonedNodes = flowData.flow_definition.nodes.map(node => ({
        ...node,
        data: { ...node.data, executionMode: true },
        style: { ...node.style },
      }));
      
      setNodes(clonedNodes);
      setEdges(flowData.flow_definition.edges || []);
      
      // Extract manual trigger variables
      const triggerConfig = flowData.trigger_config || {};
      const triggerNode = flowData.flow_definition?.nodes?.find(node => node.type === 'trigger');
      
      console.log('Trigger config:', triggerConfig);
      console.log('Trigger node:', triggerNode);
      
      if (triggerConfig.type === 'manual' || triggerNode?.data?.triggerType === 'manual') {
        const variables = triggerConfig.manual_variables || 
                         triggerNode?.data?.manualVariables || 
                         triggerNode?.data?.variables ||
                         [];
        console.log('Manual variables found:', variables);
        setManualVariables(variables);
      } else {
        console.log('Not a manual trigger, type:', triggerConfig.type || triggerNode?.data?.triggerType);
      }
      
      // Fit view after setting nodes
      setTimeout(() => {
        fitView({
          padding: 0.2,
          includeHiddenNodes: false,
          minZoom: 0.5,
          maxZoom: 1.5,
        });
      }, 100);
    }
  }, [flowData, setNodes, setEdges, fitView]);

  // Update node data to include isExecuting flag
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        data: {
          ...node.data,
          isExecuting: node.id === executingNodeId
        }
      }))
    );
  }, [executingNodeId, setNodes]);

  // WebSocket connection for debug events
  useEffect(() => {
    if (executionId) {
      // Get auth token
      const token = localStorage.getItem('access_token');
      console.log('WebSocket token:', token ? 'Found' : 'Not found');
      // Use WSS for HTTPS and WS for HTTP
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      const ws = new WebSocket(`${protocol}//${host}/ws/debug/${executionId}?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Debug WebSocket connected');
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleDebugEvent(data);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        showErrorToast('Debug connection error');
      };

      ws.onclose = () => {
        console.log('Debug WebSocket disconnected');
      };

      return () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    }
  }, [executionId]);

  // Handle debug events from WebSocket
  const handleDebugEvent = (message) => {
    console.log('Debug event received:', JSON.stringify(message, null, 2));
    
    // Handle nested event structure - the actual event is in message.data
    let event = message.data || message;
    
    // If this is an execution_update wrapper, unwrap it
    if (message.type === 'execution_update' && message.data) {
      event = message.data;
    }
    
    switch (event.type) {
      case 'node_start':
        setCurrentNodeId(event.node_id);
        setSelectedNodeId(event.node_id); // Auto-select the current node
        setExecutingNodeId(event.node_id); // Set this node as executing
        highlightNode(event.node_id, 'executing');
        // Set variables from node_start event
        if (event.variables) {
          setNodeVariables(prev => ({
            ...prev,
            [event.node_id]: event.variables
          }));
        }
        addExecutionLog({
          nodeId: event.node_id,
          type: 'start',
          message: `Starting node: ${event.node_label || event.node_id}`,
          timestamp: new Date().toISOString()
        });
        break;
      
      case 'node_complete':
        console.log('Node completed:', event.node_id, 'Type:', event.node_type);
        // Clear executing state if this was the executing node
        setExecutingNodeId(prev => prev === event.node_id ? null : prev);
        highlightNode(event.node_id, 'completed');
        // Update variables for the completed node
        if (event.variables) {
          setNodeVariables(prev => ({
            ...prev,
            [event.node_id]: event.variables
          }));
        }
        // Track the last executed node
        setLastExecutedNodeId(event.node_id);
        // Add to executed nodes list if not already there
        setExecutedNodes(prev => {
          if (!prev.includes(event.node_id)) {
            console.log('Adding node to executed nodes:', event.node_id);
            return [...prev, event.node_id];
          }
          return prev;
        });
        addExecutionLog({
          nodeId: event.node_id,
          type: 'complete',
          message: `Node ${event.node_label || event.node_id} completed`,
          timestamp: new Date().toISOString(),
          result: event.result
        });
        break;
      
      case 'node_error':
        // Clear executing state if this was the executing node
        setExecutingNodeId(prev => prev === event.node_id ? null : prev);
        highlightNode(event.node_id, 'error');
        setSelectedNodeId(event.node_id); // Auto-select error node
        addExecutionLog({
          nodeId: event.node_id,
          type: 'error',
          message: event.error || `Error in node ${event.node_label || event.node_id}`,
          timestamp: new Date().toISOString()
        });
        break;
      
      case 'execution_complete':
        // Ignore completion events from different executions (stale messages)
        if (event.execution_id && event.execution_id !== executionId) {
          console.log('Ignoring execution_complete from different execution:', event.execution_id);
          break;
        }
        setDebugState('completed');
        setCurrentNodeId(null);
        setExecutingNodeId(null); // Clear executing node
        // Close transform debugger if it's open
        setShowTransformDebugger(false);
        setTransformDebugInfo(null);
        setTransformDebugNodeId(null);
        showSuccessToast('Debug execution completed');
        addExecutionLog({
          nodeId: 'flow',
          type: 'complete',
          message: 'Flow execution completed',
          timestamp: new Date().toISOString()
        });
        break;
      
      case 'waiting_for_step':
        console.log('Received waiting_for_step event with node_id:', event.node_id);
        console.log('Executed nodes:', event.executed_nodes);
        setDebugState('paused');
        // Clear executing state when waiting for user input
        setExecutingNodeId(null);
        // Update pending branches count if provided
        if (event.pending_branches !== undefined) {
          setPendingBranches(event.pending_branches);
        }
        if (event.node_id) {
          setCurrentNodeId(event.node_id);
          setSelectedNodeId(event.node_id); // Auto-select the node waiting for step
          highlightNode(event.node_id, 'executing'); // Highlight the node waiting for step
          console.log('Set current node to:', event.node_id);
          console.log('Highlighted node:', event.node_id);
        } else {
          console.warn('No node_id in waiting_for_step event');
        }
        addExecutionLog({
          nodeId: event.node_id || 'flow',
          type: 'info',
          message: `Waiting for step at node: ${event.node_label || event.node_id || 'next'}`,
          timestamp: new Date().toISOString()
        });
        break;
      
      case 'clear_downstream_nodes':
        // Clear execution logs and results for downstream nodes when re-executing
        if (event.downstream_nodes && event.downstream_nodes.length > 0) {
          // Clear execution logs for these nodes
          setExecutionLogs(prev => prev.filter(log => !event.downstream_nodes.includes(log.nodeId)));
          // Refresh logs from backend after clearing downstream nodes
          setTimeout(fetchExecutionLogs, 500);
          
          // Remove these nodes from executed nodes list
          setExecutedNodes(prev => prev.filter(nodeId => !event.downstream_nodes.includes(nodeId)));
          
          // Clear node variables for downstream nodes
          setNodeVariables(prev => {
            const updated = { ...prev };
            event.downstream_nodes.forEach(nodeId => {
              delete updated[nodeId];
            });
            return updated;
          });
          
          // Reset node highlighting for downstream nodes
          event.downstream_nodes.forEach(nodeId => {
            highlightNode(nodeId, 'pending');
          });
          
          console.log(`Cleared results for downstream nodes:`, event.downstream_nodes);
        }
        break;
        
      case 'waiting_for_hitl':
        // HITL node created a task - pause debug and show review UI
        setDebugState('paused');
        setExecutingNodeId(null);
        setHitlTask({
          task_id: event.task_id,
          title: event.title,
          task_type: event.task_type,
          priority: event.priority,
          node_id: event.node_id,
        });
        highlightNode(event.node_id, 'executing');
        addExecutionLog({
          nodeId: event.node_id,
          type: 'info',
          message: `Waiting for human ${event.task_type || 'review'}: ${event.title || event.node_id}`,
          timestamp: new Date().toISOString()
        });
        break;

      case 'hitl_task_completed':
        // HITL task was completed (from inline review or task inbox)
        setHitlTask(null);
        setShowHitlReview(false);
        highlightNode(event.node_id, 'completed');
        addExecutionLog({
          nodeId: event.node_id,
          type: 'complete',
          message: `Human review completed (${event.response_action || 'done'})`,
          timestamp: new Date().toISOString()
        });
        break;

      case 'fork_detected':
        setPendingBranches(event.pending_branches || 0);
        addExecutionLog({
          nodeId: event.source_node_id || 'flow',
          type: 'info',
          message: `Fork: ${event.total_branches} parallel branches detected`,
          timestamp: new Date().toISOString()
        });
        break;

      case 'branch_switch':
        setPendingBranches(event.pending_branches || 0);
        addExecutionLog({
          nodeId: event.node_id || 'flow',
          type: 'info',
          message: event.message || 'Switched to next branch',
          timestamp: new Date().toISOString()
        });
        break;

      case 'debug_connected':
        console.log('Debug WebSocket connected successfully');
        break;
      
      case 'transform_debug_start':
        setTransformDebugInfo(event.debug_info);
        setShowTransformDebugger(true);
        setTransformDebugNodeId(event.node_id);
        addExecutionLog({
          nodeId: event.node_id,
          type: 'info',
          message: `Transform debug mode started for node ${event.node_id}`,
          timestamp: new Date().toISOString()
        });
        break;
      
      case 'transform_debug_step':
        setTransformDebugInfo(event.debug_info);
        break;
      
      case 'transform_debug_continue':
        setTransformDebugInfo(event.debug_info);
        break;
      
      case 'transform_debug_complete':
        setShowTransformDebugger(false);
        setTransformDebugInfo(null);
        setTransformDebugNodeId(null);
        // Update node output
        if (event.output) {
          setNodeVariables(prev => ({
            ...prev,
            [event.node_id]: { output: event.output }
          }));
        }
        addExecutionLog({
          nodeId: event.node_id,
          type: 'complete',
          message: `Transform debug completed for node ${event.node_id}`,
          timestamp: new Date().toISOString()
        });
        // Continue to next node if specified
        if (event.next_node) {
          setCurrentNodeId(event.next_node);
          highlightNode(event.next_node, 'executing');
        }
        break;
    }
  };

  // Highlight node based on execution state
  const highlightNode = (nodeId, state) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          const stateStyles = {
            executing: {
              border: '3px solid #3b82f6',
              boxShadow: '0 0 10px rgba(59, 130, 246, 0.5)',
              backgroundColor: '#eff6ff'
            },
            completed: {
              border: '2px solid #10b981',
              backgroundColor: '#f0fdf4'
            },
            error: {
              border: '2px solid #ef4444',
              backgroundColor: '#fef2f2'
            },
            pending: {
              border: '1px solid #d1d5db',
              backgroundColor: '#ffffff',
              boxShadow: 'none'
            }
          };
          
          return {
            ...node,
            style: {
              ...node.style,
              ...stateStyles[state]
            }
          };
        }
        return node;
      })
    );
  };

  // Add log entry
  const addExecutionLog = (log) => {
    setExecutionLogs(prev => [...prev, log]);
  };
  
  // Fetch execution logs from backend
  const fetchExecutionLogs = async () => {
    if (!executionId) {
      console.log('No execution ID, skipping log fetch');
      return;
    }
    
    console.log('Fetching execution logs for:', executionId);
    
    try {
      // Get the correct token
      const token = localStorage.getItem('access_token') || localStorage.getItem('token');
      
      const response = await axios.get(
        `/api/v1/executions/${executionId}/logs`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      
      console.log('Fetched logs response:', response.data);
      
      // Ensure logs is always an array
      const logs = Array.isArray(response.data) ? response.data : [];
      console.log(`Setting ${logs.length} backend logs`);
      setBackendLogs(logs);
    } catch (error) {
      console.error('Failed to fetch execution logs:', error);
      // If it's a 404, the logs might not exist yet
      if (error.response?.status === 404) {
        console.log('Logs not found yet, will retry');
      }
    }
  };
  
  // Fetch logs when execution ID changes or after each step
  useEffect(() => {
    if (executionId) {
      // Add a small delay to ensure logs are written to DB
      const timer = setTimeout(() => {
        fetchExecutionLogs();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [executionId, executedNodes]);

  // Start debug execution
  const startDebugMutation = useMutation({
    mutationFn: async () => {
      console.log('Starting debug mode for flow:', flowId);
      console.log('Trigger data:', triggerData);
      console.log('Making request to:', `/api/v1/flows/${flowId}/debug`);
      
      // Get the token
      const token = localStorage.getItem('access_token');
      console.log('Token exists:', !!token);
      console.log('Token (first 20 chars):', token ? token.substring(0, 20) + '...' : 'NO TOKEN');
      
      try {
        const response = await axios.post(
          `/api/v1/flows/${flowId}/debug`, 
          {
            trigger_data: {
              variables: triggerData,
              ...triggerData
            },
            mode: 'step'
          },
          {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          }
        );
        console.log('Debug response:', response.data);
        
        // Set execution ID immediately to start WebSocket connection
        setExecutionId(response.data.execution_id);
        
        // Wait a bit for WebSocket to connect before returning
        await new Promise(resolve => setTimeout(resolve, 500));
        
        return response.data;
      } catch (error) {
        console.error('Request failed:', error);
        console.error('Error response:', error.response);
        console.error('Error status:', error.response?.status);
        console.error('Error data:', error.response?.data);
        throw error;
      }
    },
    onSuccess: (data) => {
      console.log('Debug started successfully:', data);
      // executionId already set in mutationFn
      setDebugState('paused');
      
      // Set the current node from the response
      if (data.current_node) {
        console.log('Setting current node from debug start response:', data.current_node);
        setCurrentNodeId(data.current_node);
        setSelectedNodeId(data.current_node); // Also select it
        highlightNode(data.current_node, 'executing');
      }
      
      // Set executed nodes (trigger should be marked as executed)
      if (data.executed_nodes) {
        console.log('Setting executed nodes:', data.executed_nodes);
        setExecutedNodes(data.executed_nodes);
        // Highlight executed nodes as completed
        data.executed_nodes.forEach(nodeId => {
          highlightNode(nodeId, 'completed');
        });
      }
      
      showSuccessToast('Debug mode started');
    },
    onError: (error) => {
      console.error('Debug start failed:', error);
      console.error('Full error object:', error);
      const errorMessage = getFullErrorMessage(error, 'Failed to start debug mode');
      showErrorToast(errorMessage);
    }
  });

  // Step to next node
  const stepMutation = useMutation({
    mutationFn: async () => {
      if (!executionId) return;
      const response = await axios.post(`/api/v1/executions/${executionId}/step`);
      return response.data;
    },
    onSuccess: (data) => {
      // Fetch updated logs from backend with a slightly longer delay
      setTimeout(() => {
        console.log('Fetching logs after step...');
        fetchExecutionLogs();
      }, 1000);
      
      // Check if execution is complete
      if (data?.status === 'completed') {
        setDebugState('stopped');
        showSuccessToast('Debug execution completed');
      } else if (data?.status === 'waiting_for_hitl') {
        // HITL node executed - WebSocket events will set up the review UI
        setDebugState('paused');
      } else if (data?.status === 'error') {
        // Show error but keep in paused state so user can continue stepping
        showErrorToast(`Node execution failed: ${data.error || 'Unknown error'}`);
        // Stay in paused state so user can continue or stop
        setDebugState('paused');
      } else {
        // Keep in paused state for next step
        setDebugState('paused');
      }
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to step');
      showErrorToast(errorMessage);
      // Keep in paused state even on error so user can try again
      setDebugState('paused');
    }
  });

  // Resume execution
  const resumeMutation = useMutation({
    mutationFn: async () => {
      if (!executionId) return;
      const response = await axios.post(`/api/v1/executions/${executionId}/resume`);
      return response.data;
    },
    onSuccess: (data) => {
      // Check if execution completed immediately
      if (data?.status === 'completed') {
        setDebugState('completed');
        showSuccessToast('Execution completed');
      } else {
        setDebugState('running');
        showSuccessToast('Execution resumed - running to completion');
      }
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to resume execution');
      showErrorToast(errorMessage);
      setDebugState('paused'); // Go back to paused state on error
    }
  });

  // Stop execution
  const stopMutation = useMutation({
    mutationFn: async () => {
      if (!executionId) return;
      const response = await axios.post(`/api/v1/executions/${executionId}/stop`);
      return response.data;
    },
    onSuccess: () => {
      setDebugState('idle');
      setExecutionId(null);
      setHitlTask(null);
      setShowHitlReview(false);
      setPendingBranches(0);
      showSuccessToast('Execution stopped');
      // Reset node styles
      setNodes((nds) =>
        nds.map((node) => ({
          ...node,
          style: {}
        }))
      );
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to stop execution');
      showErrorToast(errorMessage);
    }
  });

  // Handle node click
  const onNodeClick = useCallback((event, node) => {
    setSelectedNodeId(node.id);
    // If in debug mode and double-click, open edit dialog
    if (event.detail === 2 && (debugState === 'paused' || debugState === 'running')) {
      openEditNodeDialog(node.id);
    }
  }, [debugState]);

  // Open edit node dialog
  const openEditNodeDialog = (nodeId) => {
    const node = nodes.find(n => n.id === nodeId);
    if (node) {
      console.log('Opening edit dialog for node:', node);
      console.log('Node type:', node.type);
      console.log('Node data:', node.data);
      console.log('Current node:', currentNodeId);
      console.log('Node has been executed:', !!nodeVariables[nodeId]);
      setEditingNode(node);
      setEditedNodeConfig(node.data || {});
      setEditedVariables(nodeVariables[nodeId] || {});
      setShowNodeEditDialog(true);
    }
  };

  // Update node configuration during debug
  const updateNodeMutation = useMutation({
    mutationFn: async ({ nodeId, config, variables, reExecute }) => {
      if (!executionId) {
        throw new Error('No active execution');
      }
      console.log('Sending update-node request:');
      console.log('  Node ID:', nodeId);
      console.log('  Config:', config);
      console.log('  Variables:', variables);
      console.log('  Re-execute:', reExecute);
      const response = await axios.post(`/api/v1/executions/${executionId}/update-node`, {
        node_id: nodeId,
        config,
        variables,
        re_execute: reExecute
      });
      return response.data;
    },
    onSuccess: (data) => {
      showSuccessToast(data.message || 'Node configuration updated');
      setShowNodeEditDialog(false);
      setEditingNode(null);
      
      // Update local node data
      if (editingNode) {
        setNodes((nds) =>
          nds.map((node) =>
            node.id === editingNode.id
              ? { ...node, data: { ...node.data, ...editedNodeConfig } }
              : node
          )
        );
        
        // Update local variables
        if (Object.keys(editedVariables).length > 0) {
          setNodeVariables(prev => ({
            ...prev,
            [editingNode.id]: editedVariables
          }));
        }
      }
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to update node');
      showErrorToast(errorMessage);
    }
  });

  // Reset debug state
  const resetDebug = () => {
    setDebugState('idle');
    setCurrentNodeId(null);
    setExecutionId(null);
    setExecutionLogs([]);
    setBackendLogs([]);
    setNodeVariables({});
    setSelectedNodeId(null);
    setLastExecutedNodeId(null);
    setExecutedNodes([]); // Reset executed nodes list
    setHitlTask(null);
    setShowHitlReview(false);
    setPendingBranches(0);
    // Reset node styles
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        style: {}
      }))
    );
  };

  // Render variable categories (input, global, output, loop, node_outputs)
  const renderVariableCategories = (variables) => {
    // Handle both old format (plain object) and new format (categorized)
    if (!variables || typeof variables !== 'object') {
      return (
        <pre className="text-xs bg-white p-2 rounded border overflow-x-auto">
          {JSON.stringify(variables, null, 2)}
        </pre>
      );
    }

    // Check if this is the new categorized format
    const hasCategories = variables.input !== undefined || 
                          variables.global !== undefined || 
                          variables.output !== undefined || 
                          variables.loop !== undefined ||
                          variables.node_outputs !== undefined;

    if (!hasCategories) {
      // Old format - just display as is
      return (
        <div>
          <div className="text-xs font-medium text-gray-600 mb-1">Variables:</div>
          <pre className="text-xs bg-white p-2 rounded border overflow-x-auto">
            {JSON.stringify(variables, null, 2)}
          </pre>
        </div>
      );
    }

    // New categorized format
    const categories = [
      { key: 'input', label: 'Input Variables', textColor: 'text-blue-700', hoverColor: 'hover:text-blue-800', borderColor: 'border-blue-200' },
      { key: 'global', label: 'Global Variables', textColor: 'text-purple-700', hoverColor: 'hover:text-purple-800', borderColor: 'border-purple-200' },
      { key: 'output', label: 'Node Output', textColor: 'text-green-700', hoverColor: 'hover:text-green-800', borderColor: 'border-green-200' },
      { key: 'loop', label: 'Loop Variables', textColor: 'text-orange-700', hoverColor: 'hover:text-orange-800', borderColor: 'border-orange-200' },
      { key: 'node_outputs', label: 'All Node Outputs', textColor: 'text-gray-700', hoverColor: 'hover:text-gray-800', borderColor: 'border-gray-200' }
    ];

    return (
      <div className="space-y-3">
        {categories.map(({ key, label, textColor, hoverColor, borderColor }) => {
          const data = variables[key];
          const hasData = data && Object.keys(data).length > 0;
          
          if (!hasData && key !== 'loop') return null; // Skip empty categories except loop
          if (key === 'loop' && !variables.loop) return null; // Skip loop if not in a loop
          
          return (
            <details key={key} className="group" open={key === 'input' || key === 'output'}>
              <summary className={`cursor-pointer text-xs font-semibold ${textColor} ${hoverColor} flex items-center`}>
                <span className="mr-1">▶</span>
                <span className="group-open:hidden">▶</span>
                <span className="hidden group-open:inline">▼</span>
                <span className="ml-1">{label}</span>
                {hasData && (
                  <span className="ml-2 text-xs text-gray-500">
                    ({Object.keys(data).length} {Object.keys(data).length === 1 ? 'item' : 'items'})
                  </span>
                )}
              </summary>
              {hasData ? (
                <pre className={`text-xs bg-white p-2 mt-1 rounded border ${borderColor} overflow-x-auto`}>
                  {JSON.stringify(data, null, 2)}
                </pre>
              ) : (
                <p className="text-xs text-gray-500 mt-1 ml-4">No {label.toLowerCase()} defined</p>
              )}
            </details>
          );
        })}
      </div>
    );
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate(`/flows/${flowId}/edit`)}
            className="flex items-center text-gray-600 hover:text-gray-900"
          >
            <ArrowLeftIcon className="w-4 h-4 mr-2" />
            Back to Editor
          </button>
          <div className="border-l pl-4">
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-medium">{flowName} - Debug Mode</h1>
              <span className={`px-2 py-1 text-xs rounded-full font-medium ${
                debugState === 'idle' ? 'bg-gray-100 text-gray-800' :
                debugState === 'running' ? 'bg-blue-100 text-blue-800' :
                debugState === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                'bg-green-100 text-green-800'
              }`}>
                {debugState}
              </span>
            </div>
            {flowDescription && (
              <p className="text-sm text-gray-500">{flowDescription}</p>
            )}
          </div>
        </div>
        <div className="flex items-center space-x-2">
          {/* Debug controls */}
          {debugState === 'idle' && (
            <button
              onClick={(e) => {
                e.preventDefault();
                // If there are manual variables, show the input dialog
                if (manualVariables && manualVariables.length > 0) {
                  setShowTriggerInputDialog(true);
                } else {
                  // No variables needed, start debug directly
                  startDebugMutation.mutate();
                }
              }}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center"
              disabled={startDebugMutation.isPending}
            >
              <PlayIcon className="w-4 h-4 mr-2" />
              Start Debug
            </button>
          )}
          
          {debugState === 'paused' && (
            <>
              {executingNodeId && (
                <div className="flex items-center text-sm text-gray-600 mr-4">
                  <svg className="animate-spin h-4 w-4 text-gray-600 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Executing: {nodes.find(n => n.id === executingNodeId)?.data?.label || executingNodeId}</span>
                </div>
              )}
              {hitlTask && (
                <div className="flex items-center space-x-2">
                  <div className="flex items-center text-sm text-amber-600 mr-2">
                    <HandRaisedIcon className="w-4 h-4 mr-1" />
                    <span>Waiting: {hitlTask.title || 'Human Review'}</span>
                  </div>
                  <button
                    onClick={() => setShowHitlReview(true)}
                    className="px-4 py-2 bg-amber-600 text-white rounded-md hover:bg-amber-700 flex items-center"
                  >
                    <HandRaisedIcon className="w-4 h-4 mr-2" />
                    Review Task
                  </button>
                </div>
              )}
              <button
                onClick={() => stepMutation.mutate()}
                className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg flex items-center disabled:bg-gray-400 disabled:hover:bg-gray-400 disabled:cursor-not-allowed"
                disabled={stepMutation.isPending || executingNodeId !== null || hitlTask !== null}
                title={hitlTask ? "Complete the review task first" : executingNodeId !== null ? "Node is executing, please wait..." : "Execute next node"}
              >
                <ForwardIcon className="w-4 h-4 mr-2" />
                Step
              </button>
              {/* Show Step Into Transform button if current node is a transform node */}
              {currentNodeId && nodes.find(n => n.id === currentNodeId && n.type === 'transform') && (
                <button
                  onClick={async () => {
                    try {
                      // First enable transform debug mode
                      console.log('Enabling transform debug mode for node:', currentNodeId);
                      const debugResponse = await axios.post(`/api/v1/executions/${executionId}/transform/step-into`, {
                        node_id: currentNodeId
                      });
                      console.log('Transform debug mode enabled:', debugResponse.data);
                      
                      // Small delay to ensure the debug mode is set
                      await new Promise(resolve => setTimeout(resolve, 100));
                      
                      // Then step to execute the node which will trigger transform debug
                      console.log('Stepping into transform node...');
                      stepMutation.mutate();
                    } catch (error) {
                      console.error('Error enabling transform debug:', error);
                      showErrorToast('Failed to enable transform debug mode');
                    }
                  }}
                  className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 flex items-center disabled:bg-gray-400 disabled:hover:bg-gray-400 disabled:cursor-not-allowed"
                  disabled={stepMutation.isPending || executingNodeId !== null}
                  title={executingNodeId !== null ? "Node is executing, please wait..." : "Debug transform node step by step"}
                >
                  <CodeBracketSquareIcon className="w-4 h-4 mr-2" />
                  Step Into Transform
                </button>
              )}
              <button
                onClick={() => resumeMutation.mutate()}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center disabled:bg-gray-400 disabled:hover:bg-gray-400 disabled:cursor-not-allowed"
                disabled={resumeMutation.isPending || executingNodeId !== null || hitlTask !== null}
                title={hitlTask ? "Complete the review task first" : executingNodeId !== null ? "Node is executing, please wait..." : "Run to completion"}
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                Resume
              </button>
            </>
          )}
          
          {(debugState === 'running' || debugState === 'paused') && (
            <>
              <button
                onClick={() => stopMutation.mutate()}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 flex items-center"
                disabled={stopMutation.isPending}
              >
                <StopIcon className="w-4 h-4 mr-2" />
                Stop
              </button>
              {pendingBranches > 0 && (
                <div className="flex items-center text-sm text-blue-600 ml-4 bg-blue-50 px-2 py-1 rounded">
                  <InformationCircleIcon className="w-4 h-4 mr-1" />
                  <span>{pendingBranches} branch{pendingBranches > 1 ? 'es' : ''} pending</span>
                </div>
              )}
              <div className="flex items-center text-sm text-gray-600 ml-4">
                <InformationCircleIcon className="w-4 h-4 mr-1" />
                <span>Tip: Double-click any node to edit</span>
              </div>
            </>
          )}
          
          {debugState === 'completed' && (
            <button
              onClick={resetDebug}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 flex items-center"
            >
              <ArrowPathIcon className="w-4 h-4 mr-2" />
              Reset
            </button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex">
        {/* Flow Canvas */}
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodeClick={onNodeClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            fitView
            fitViewOptions={{
              padding: 0.2,
              includeHiddenNodes: false,
              minZoom: 0.5,
              maxZoom: 1.5,
            }}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={true}
            panOnScroll
            panOnDrag
          >
            <Controls />
            <MiniMap 
              nodeColor={(node) => {
                const colors = {
                  trigger: '#10b981',
                  action: '#3b82f6',
                  condition: '#f59e0b',
                  transform: '#8b5cf6',
                  response: '#ec4899',
                  loop: '#6366f1',
                };
                return colors[node.type] || '#94a3b8';
              }}
              pannable
              zoomable
              style={{
                backgroundColor: '#f8fafc',
                border: '1px solid #e2e8f0',
              }}
            />
            <Background variant="dots" gap={12} size={1} />
            
            {/* Current Node Indicator */}
            {currentNodeId && (
              <Panel position="top-center" className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="flex items-center">
                  <InformationCircleIcon className="w-5 h-5 text-primary mr-2" />
                  <span className="text-sm font-medium text-blue-800">
                    Next: {nodes.find(n => n.id === currentNodeId)?.data?.label || currentNodeId}
                  </span>
                </div>
              </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Side Panel */}
        <div className="w-96 bg-white border-l flex flex-col">
          {/* Panel Tabs */}
          <div className="flex border-b">
            <button
              onClick={() => setShowVariables(!showVariables)}
              className={`flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center ${
                showVariables ? 'bg-gray-50 border-b-2 border-primary text-primary' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <EyeIcon className="w-4 h-4 mr-2" />
              Variables
            </button>
            <button
              onClick={() => setShowLogs(!showLogs)}
              className={`flex-1 px-4 py-3 text-sm font-medium flex items-center justify-center ${
                showLogs ? 'bg-gray-50 border-b-2 border-primary text-primary' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <ClipboardDocumentListIcon className="w-4 h-4 mr-2" />
              Execution Log
            </button>
          </div>

          {/* Variables Panel */}
          {showVariables && (
            <div className="flex-1 overflow-y-auto p-4">
              <h3 className="text-lg font-medium mb-4">Debug Variables</h3>
              
              {/* Current Node Variables */}
              {currentNodeId && (
                <div className="mb-6">
                  <h4 className="text-sm font-semibold text-blue-700 mb-2">Current Node</h4>
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-medium text-sm text-blue-900">
                        {nodes.find(n => n.id === currentNodeId)?.data?.label || currentNodeId}
                      </div>
                      {(debugState === 'paused' || debugState === 'running') && (
                        <button
                          onClick={() => openEditNodeDialog(currentNodeId)}
                          className="p-1 text-primary hover:text-primary-dark"
                          title="Edit node configuration"
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    {nodeVariables[currentNodeId] ? (
                      <div className="space-y-2">
                        {renderVariableCategories(nodeVariables[currentNodeId])}
                      </div>
                    ) : (
                      <p className="text-sm text-primary">Waiting to execute...</p>
                    )}
                  </div>
                </div>
              )}
              
              {/* Selected Node Variables */}
              {selectedNodeId && selectedNodeId !== currentNodeId ? (
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Selected Node</h4>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <div className="font-medium text-sm text-gray-900">
                        {nodes.find(n => n.id === selectedNodeId)?.data?.label || selectedNodeId}
                      </div>
                      {(debugState === 'paused' || debugState === 'running') && (
                        <button
                          onClick={() => openEditNodeDialog(selectedNodeId)}
                          className="p-1 text-primary hover:text-primary-dark"
                          title="Edit node configuration"
                        >
                          <PencilIcon className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    {nodeVariables[selectedNodeId] ? (
                      <div className="space-y-2">
                        {renderVariableCategories(nodeVariables[selectedNodeId])}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">
                        {selectedNodeId === currentNodeId ? 'Currently executing...' : 'No variables yet'}
                      </p>
                    )}
                  </div>
                </div>
              ) : !currentNodeId && !selectedNodeId ? (
                <p className="text-sm text-gray-500">Click on a node or start debugging to view variables</p>
              ) : null}
              
              {/* All Node Variables */}
              {Object.keys(nodeVariables).length > 0 && (
                <div className="mt-6">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">All Executed Nodes</h4>
                  <div className="space-y-2">
                    {Object.entries(nodeVariables).map(([nodeId, vars]) => {
                      const node = nodes.find(n => n.id === nodeId);
                      return (
                        <details key={nodeId} className="bg-gray-50 rounded-lg p-2">
                          <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-900">
                            {node?.data?.label || nodeId}
                          </summary>
                          <div className="mt-2">
                            {renderVariableCategories(vars)}
                          </div>
                        </details>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Execution Log Panel */}
          {showLogs && (
            <div className="flex-1 overflow-y-auto">
              {backendLogs && backendLogs.length > 0 ? (
                <HierarchicalExecutionLog logs={backendLogs} />
              ) : (
                <div className="p-4">
                  <h3 className="text-lg font-medium mb-4">Execution Log</h3>
                  <div className="space-y-2">
                    {executionLogs.length > 0 ? (
                      executionLogs.map((log, index) => (
                        <div
                          key={index}
                          className={`p-3 rounded-lg text-sm ${
                            log.type === 'error' ? 'bg-red-50 text-red-800' :
                            log.type === 'complete' ? 'bg-green-50 text-green-800' :
                            'bg-gray-50 text-gray-800'
                          }`}
                        >
                          <div className="flex justify-between items-start mb-1">
                            <span className="font-medium">
                              {nodes.find(n => n.id === log.nodeId)?.data?.label || log.nodeId}
                            </span>
                            <span className="text-xs opacity-75">
                              {new Date(log.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="text-xs">{log.message}</p>
                          {log.result && (
                            <pre className="text-xs mt-2 bg-white bg-opacity-50 p-2 rounded overflow-x-auto">
                              {JSON.stringify(log.result, null, 2)}
                            </pre>
                          )}
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-gray-500">No execution logs yet</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Trigger Input Dialog */}
      {showTriggerInputDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
          <div className="bg-white rounded-lg p-6 max-w-md w-full max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Input Trigger Variables</h2>
              <button
                onClick={() => setShowTriggerInputDialog(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>
            
            <p className="text-sm text-gray-600 mb-4">
              Please provide values for the trigger variables to start debugging:
            </p>
            
            <div className="space-y-4">
              {manualVariables && manualVariables.length > 0 ? (
                manualVariables.map((variable, index) => {
                  // Ensure variable has required properties for IsolatedField
                  const parameterWithDefaults = {
                    ...variable,
                    displayName: variable.displayName || variable.name || `Variable ${index + 1}`,
                    description: variable.description || '',
                    type: variable.type || 'string',
                    required: variable.required !== false
                  };
                  
                  return (
                    <div key={variable.name || index}>
                      <IsolatedField
                        variable={parameterWithDefaults}
                        value={triggerData[variable.name]}
                        onChange={(name, value) => {
                          // IsolatedParameterInput calls onValueChange(variable.name, value)
                          // So we receive the variable name and the actual value
                          setTriggerData(prev => ({
                            ...prev,
                            [name]: value  // Use 'name' as key, 'value' as the actual value
                          }));
                        }}
                      />
                    </div>
                  );
                })
              ) : (
                <p className="text-sm text-gray-500">No trigger variables defined.</p>
              )}
            </div>
            
            <div className="flex justify-end space-x-2 mt-6">
              <button
                onClick={() => setShowTriggerInputDialog(false)}
                className="px-4 py-2 text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setShowTriggerInputDialog(false);
                  startDebugMutation.mutate();
                }}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center"
              >
                <PlayIcon className="w-4 h-4 mr-2" />
                Start Debug
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Node Edit Dialog */}
      {showNodeEditDialog && editingNode && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h3 className="text-lg font-semibold">Edit Node: {editingNode.data?.label || editingNode.id}</h3>
                {editingNode.id === lastExecutedNodeId && (
                  <p className="text-sm text-green-600 mt-1">Last executed node - can be re-executed</p>
                )}
                {editingNode.id !== lastExecutedNodeId && nodeVariables[editingNode.id] && (
                  <p className="text-sm text-gray-500 mt-1">Previously executed - configuration will apply on next run</p>
                )}
                {!nodeVariables[editingNode.id] && (
                  <p className="text-sm text-primary mt-1">Not yet executed - configuration will apply when reached</p>
                )}
              </div>
              <button
                onClick={() => {
                  setShowNodeEditDialog(false);
                  setEditingNode(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {/* Node Configuration */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Node Configuration</h4>
                <div className="bg-gray-50 rounded-lg p-3">
                  {editingNode.type === 'action' && (
                    <div className="space-y-3">
                      {editedNodeConfig.parameters && Object.keys(editedNodeConfig.parameters).length > 0 ? (
                        Object.entries(editedNodeConfig.parameters).map(([key, value]) => (
                          <div key={key}>
                            <label className="block text-sm font-medium text-gray-700 mb-1">{key}</label>
                            {typeof value === 'object' ? (
                              <textarea
                                value={JSON.stringify(value, null, 2)}
                                onChange={(e) => {
                                  try {
                                    const parsed = JSON.parse(e.target.value);
                                    setEditedNodeConfig(prev => ({
                                      ...prev,
                                      parameters: {
                                        ...prev.parameters,
                                        [key]: parsed
                                      }
                                    }));
                                  } catch {
                                    // If it's not valid JSON, treat it as a string
                                    setEditedNodeConfig(prev => ({
                                      ...prev,
                                      parameters: {
                                        ...prev.parameters,
                                        [key]: e.target.value
                                      }
                                    }));
                                  }
                                }}
                                rows={4}
                                className="w-full px-3 py-2 border rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                              />
                            ) : (
                              <input
                                type="text"
                                value={value}
                                onChange={(e) => {
                                  setEditedNodeConfig(prev => ({
                                    ...prev,
                                    parameters: {
                                      ...prev.parameters,
                                      [key]: e.target.value
                                    }
                                  }));
                                }}
                                className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                              />
                            )}
                          </div>
                        ))
                      ) : (
                        <div>
                          <p className="text-sm text-gray-500 mb-2">No parameters configured. You can add parameters as JSON:</p>
                          <textarea
                            value={JSON.stringify(editedNodeConfig.parameters || {}, null, 2)}
                            onChange={(e) => {
                              try {
                                const parsed = JSON.parse(e.target.value);
                                setEditedNodeConfig(prev => ({
                                  ...prev,
                                  parameters: parsed
                                }));
                              } catch {
                                // Invalid JSON, don't update
                              }
                            }}
                            rows={4}
                            className="w-full px-3 py-2 border rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                            placeholder='{"key": "value"}'
                          />
                        </div>
                      )}
                    </div>
                  )}
                  {editingNode.type === 'transform' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Transformation Script</label>
                      <textarea
                        value={editedNodeConfig.script || editedNodeConfig.code || ''}
                        onChange={(e) => {
                          setEditedNodeConfig(prev => ({
                            ...prev,
                            script: e.target.value,
                            code: e.target.value  // Also set code for backend compatibility
                          }));
                        }}
                        rows={8}
                        className="w-full px-3 py-2 border rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        placeholder="# Python transformation script&#10;# Example:&#10;output['result'] = input.get('value', 0) * 2&#10;output['message'] = 'Processed'"
                      />
                    </div>
                  )}
                  {editingNode.type === 'condition' && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Condition Expression</label>
                        <textarea
                          value={editedNodeConfig.expression || editedNodeConfig.condition || ''}
                          onChange={(e) => {
                            setEditedNodeConfig(prev => ({
                              ...prev,
                              expression: e.target.value,
                              condition: e.target.value
                            }));
                          }}
                          rows={3}
                          className="w-full px-3 py-2 border rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                          placeholder="input.value > 10"
                        />
                      </div>
                    </div>
                  )}
                  {editingNode.type === 'loop' && (
                    <div className="space-y-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Loop Type</label>
                        <select
                          value={editedNodeConfig.loopType || 'for'}
                          onChange={(e) => {
                            setEditedNodeConfig(prev => ({
                              ...prev,
                              loopType: e.target.value
                            }));
                          }}
                          className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                        >
                          <option value="for">For Loop</option>
                          <option value="while">While Loop</option>
                          <option value="forEach">For Each</option>
                        </select>
                      </div>
                      {editedNodeConfig.loopType === 'for' && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Iterations</label>
                          <input
                            type="number"
                            value={editedNodeConfig.iterations || 1}
                            onChange={(e) => {
                              setEditedNodeConfig(prev => ({
                                ...prev,
                                iterations: parseInt(e.target.value) || 1
                              }));
                            }}
                            className="w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
                          />
                        </div>
                      )}
                    </div>
                  )}
                  {!['action', 'transform', 'condition', 'loop'].includes(editingNode.type) && (
                    <p className="text-sm text-gray-500">This node type does not have editable configuration during debug.</p>
                  )}
                </div>
              </div>

              {/* Variables */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Variables</h4>
                <div className="bg-gray-50 rounded-lg p-3">
                  <textarea
                    value={JSON.stringify(editedVariables, null, 2)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        setEditedVariables(parsed);
                      } catch {
                        // Invalid JSON, don't update
                      }
                    }}
                    rows={6}
                    className="w-full px-3 py-2 border rounded-md font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder='{"key": "value"}'
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end space-x-3 mt-6">
              <button
                onClick={() => {
                  setShowNodeEditDialog(false);
                  setEditingNode(null);
                }}
                className="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  updateNodeMutation.mutate({
                    nodeId: editingNode.id,
                    config: editedNodeConfig,
                    variables: editedVariables,
                    reExecute: false
                  });
                }}
                className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg"
              >
                Update Configuration
              </button>
              {/* Show Re-execute for any executed node */}
              {executedNodes.includes(editingNode.id) && (
                <button
                  onClick={() => {
                    updateNodeMutation.mutate({
                      nodeId: editingNode.id,
                      config: editedNodeConfig,
                      variables: editedVariables,
                      reExecute: true
                    });
                  }}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                >
                  Update & Re-execute
                </button>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* HITL Task Review Modal */}
      {showHitlReview && hitlTask && (
        <TaskReviewModal
          task={hitlTask}
          isOpen={true}
          onClose={() => setShowHitlReview(false)}
          onCompleted={(taskId, action) => {
            setShowHitlReview(false);
            setHitlTask(null);
            // Backend will send hitl_task_completed + waiting_for_step via WebSocket
          }}
          fetchFullTask={true}
        />
      )}

      {/* Transform Debugger Modal */}
      {showTransformDebugger && transformDebugNodeId && (
        <div className="fixed inset-0 z-[100] bg-black bg-opacity-50 flex items-center justify-center">
          <div className="bg-gray-900 w-full max-w-7xl h-[90vh] mx-4 my-4 rounded-lg overflow-hidden">
            <TransformDebugger
              nodeId={transformDebugNodeId}
              script={(() => {
                // Find the transform node and get its script
                const node = nodes.find(n => n.id === transformDebugNodeId);
                console.log('Looking for node:', transformDebugNodeId);
                console.log('Found node:', node);
                console.log('Node data:', node?.data);
                
                // The script is stored directly in data.script for transform nodes
                const script = node?.data?.script || 
                               node?.data?.config?.script || 
                               node?.data?.transform_script ||
                               node?.data?.parameters?.script ||
                               transformDebugInfo?.script ||
                               '# No script found';
                
                console.log('Extracted script:', script);
                return script;
              })()}
              executionId={executionId}
              websocket={wsRef.current}
              onClose={(output) => {
                setShowTransformDebugger(false);
                setTransformDebugInfo(null);
                setTransformDebugNodeId(null);
                
                // If output is provided, the transform completed successfully
                if (output) {
                  // Update node output
                  setNodeVariables(prev => ({
                    ...prev,
                    [transformDebugNodeId]: { output }
                  }));
                  
                  // The backend already handles moving to the next node via WebSocket
                  // so we don't need to call stepMutation here
                  console.log('Transform debugging completed, backend will handle next node');
                }
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

// Wrap with ReactFlowProvider
const FlowDebuggerWrapper = () => (
  <ReactFlowProvider>
    <FlowDebugger />
  </ReactFlowProvider>
);

export default FlowDebuggerWrapper;