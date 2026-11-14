import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { flushSync } from 'react-dom';
import ReactFlow, {
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import '../flow/nodeStyles.css';
import {
  XMarkIcon,
  DocumentDuplicateIcon,
  CodeBracketIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  ClockIcon,
  PlayIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ExclamationTriangleIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  HandRaisedIcon,
  PauseCircleIcon,
} from '@heroicons/react/24/outline';
import { useQuery, useMutation } from '@tanstack/react-query';
import axios from 'axios';
import CodeBlock from '../CodeBlock';
import { generateSampleFromSchema } from '../../utils/schemaUtils';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';
import IsolatedField from '../flow/IsolatedParameterInput';
import { useExecutionWebSocket } from '../../hooks/useExecutionWebSocket';
import ChatTriggerView from './ChatTriggerView';
import TaskReviewModal from './TaskReviewModal';
import TriggerNode from '../flow/TriggerNode';
import ActionNode from '../flow/ActionNode';
import ConditionNode from '../flow/ConditionNode';
import TransformNode from '../flow/TransformNode';
import ResponseNode from '../flow/ResponseNode';
import LoopNode from '../flow/LoopNode';
import HumanInLoopNode from '../flow/HumanInLoopNode';
import WaitForEventNode from '../flow/WaitForEventNode';
import CustomEdge from '../flow/CustomEdge';

const flowNodeTypes = {
  trigger: TriggerNode,
  action: ActionNode,
  condition: ConditionNode,
  transform: TransformNode,
  response: ResponseNode,
  loop: LoopNode,
  human_in_loop: HumanInLoopNode,
  wait_for_event: WaitForEventNode,
};

const flowEdgeTypes = {
  default: CustomEdge,
};

const ManualTriggerModal = React.memo(({ flow, onClose, onTrigger }) => {
  const API_BASE_URL = import.meta.env.VITE_API_URL || '';

  // Get trigger configuration from flow
  const triggerConfig = flow?.trigger_config || {};
  const isManual = triggerConfig.type === 'manual';
  const isSchedule = triggerConfig.type === 'schedule';
  const isWebhook = triggerConfig.type === 'webhook' || triggerConfig.type === 'event';
  const isApiCall = triggerConfig.type === 'api_call';
  const isChatInput = triggerConfig.type === 'chat_input';
  
  // Get trigger node data from flow definition
  const triggerNode = flow?.flow_definition?.nodes?.find(node => node.type === 'trigger');
  
  // Get manual variables - check both trigger_config and trigger node data
  // For chat_input, also expose manual variables (message)
  const manualVariables = (isManual || isChatInput) ?
    (Array.isArray(triggerConfig.manual_variables) ? triggerConfig.manual_variables :
     Array.isArray(triggerNode?.data?.manualVariables) ? triggerNode.data.manualVariables : []) : [];

  // Initialize state with empty object, let IsolatedField handle defaults
  const [formData, setFormData] = useState({});
  const [error, setError] = useState('');
  const [showSampleCode, setShowSampleCode] = useState(false);
  const [activeLanguage, setActiveLanguage] = useState('python');
  const [copied, setCopied] = useState(false);
  
  // ReactFlow state for visual flow diagram
  const [flowNodes, setFlowNodes, onFlowNodesChange] = useNodesState([]);
  const [flowEdges, setFlowEdges, onFlowEdgesChange] = useEdgesState([]);
  const reactFlowInstance = useRef(null);

  // Execution state
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionId, setExecutionId] = useState(null);
  const [executionLogs, setExecutionLogs] = useState([]);
  const [nodeStatuses, setNodeStatuses] = useState({});
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const [executionResult, setExecutionResult] = useState(null);
  const [executionError, setExecutionError] = useState(null);
  const [activeTab, setActiveTab] = useState('input');
  const [isMaximized, setIsMaximized] = useState(false); // State for maximized view
  const [isLoadingResult, setIsLoadingResult] = useState(false); // Loading state for result

  // HITL state
  const [hitlTask, setHitlTask] = useState(null); // { task_id, title, assignees, paused_at, ... }
  const [showHitlReview, setShowHitlReview] = useState(false);

  // Chat session state (for chat_input trigger type)
  const [chatSessionId, setChatSessionId] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatError, setChatError] = useState(null);

  // Track if user has manually switched tabs
  const [userHasSwitchedTabs, setUserHasSwitchedTabs] = useState(false);
  
  // Auto-switch to appropriate tab based on execution state (only during initial flow)
  useEffect(() => {
    if (isExecuting && activeTab === 'input' && !userHasSwitchedTabs) {
      // For synchronous flows without parameters, switch to results tab directly
      // For other flows, switch to logs tab
      const isSyncNoParams = flow?.is_synchronous && (!manualVariables || manualVariables.length === 0);
      setActiveTab(isSyncNoParams ? 'results' : 'logs');
    }
  }, [isExecuting, activeTab, userHasSwitchedTabs, flow, manualVariables]);

  // Auto-switch to results when execution completes or HITL pauses
  const [hasAutoSwitchedToResults, setHasAutoSwitchedToResults] = useState(false);

  useEffect(() => {
    if (executionResult && activeTab === 'logs' && !isExecuting && !hasAutoSwitchedToResults && !userHasSwitchedTabs) {
      setActiveTab('results');
      setHasAutoSwitchedToResults(true);
    }
  }, [executionResult, activeTab, isExecuting, hasAutoSwitchedToResults, userHasSwitchedTabs]);

  // Auto-switch to results when HITL pauses so user sees the waiting state
  useEffect(() => {
    if (hitlTask && !isExecuting && activeTab === 'logs' && !userHasSwitchedTabs) {
      setActiveTab('results');
    }
  }, [hitlTask, isExecuting, activeTab, userHasSwitchedTabs]);

  // Reset auto-switch flags when starting new execution
  useEffect(() => {
    if (isExecuting) {
      setHasAutoSwitchedToResults(false);
      setUserHasSwitchedTabs(false);
    }
  }, [isExecuting]);
  
  const eventFields = triggerNode?.data?.eventFields || 
                      triggerNode?.data?.event_fields || 
                      triggerNode?.data?.fields || 
                      triggerNode?.data?.selectedEventFields || 
                      [];
  const eventId = triggerNode?.data?.eventId || triggerNode?.data?.event_id;
  
  // Force WebSocket connection on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      console.log('ManualTriggerModal: Ensuring WebSocket connection');
      import('../../services/websocketService').then(({ default: ws }) => {
        if (!ws.isConnected()) {
          console.log('ManualTriggerModal: WebSocket not connected, connecting now...');
          ws.connect(token).catch(err => {
            console.error('ManualTriggerModal: Failed to connect WebSocket:', err);
          });
        } else {
          console.log('ManualTriggerModal: WebSocket already connected');
        }
      });
    }
  }, []);

  // Track completion to prevent multiple toasts
  const [hasShownCompletionToast, setHasShownCompletionToast] = useState(false);
  
  // WebSocket connection for real-time updates
  const { isConnected, subscribeToExecution, unsubscribeFromExecution } = useExecutionWebSocket(null, {
    onStatusUpdate: useCallback((execId, data) => {
      console.log('WebSocket status update:', execId, data);
      if (execId === executionId) {
        // Handle immediate trigger and execution start notifications
        if (data.type === 'trigger_received') {
          console.log('🚀 Trigger received - updating UI immediately');
          setActiveTab('logs'); // Switch to logs to show real-time feedback
          // Show immediate trigger notification
          setNodeStatuses(prev => ({
            ...prev,
            'trigger': {
              nodeId: 'trigger',
              nodeType: 'trigger',
              nodeLabel: 'Trigger Event',
              status: 'running',
              message: '🚀 Trigger event received',
              timestamp: new Date().toISOString(),
              level: 'info'
            }
          }));
        } else if (data.type === 'execution_start') {
          console.log('⚡ Execution started - updating UI');
          setNodeStatuses(prev => ({
            ...prev,
            'execution': {
              nodeId: 'execution',
              nodeType: 'execution',
              nodeLabel: 'Flow Execution',
              status: 'running',
              message: data.message || '✅ Flow execution started',
              timestamp: new Date().toISOString(),
              level: 'info'
            }
          }));
        } else if (data.type === 'execution_complete') {
          // Handle flow completion - ONLY for execution_complete, not node_complete
          console.log('✅ Flow execution complete - stopping spinner');
          console.log('Completion data:', data);

          // If the completion message includes result data, set it FIRST before stopping spinner
          // Use flushSync to ensure this state update happens immediately before other updates
          const hasResultInMessage = data.result !== null && data.result !== undefined;
          console.log('hasResultInMessage:', hasResultInMessage, 'data.result:', data.result);

          if (hasResultInMessage) {
            console.log('✅ Setting result from WebSocket completion message:', data.result);
            console.log('📋 Response headers:', data.response_headers);
            console.log('📊 Response status:', data.response_status);
            flushSync(() => {
              setExecutionResult({
                execution_id: execId,
                status: 'completed',
                result_data: data.result,
                data: data.result,
                response_data: data.result,
                response_status: data.response_status,
                response_headers: data.response_headers
              });
              setIsLoadingResult(false); // Result is available, not loading
              console.log('✅ isLoadingResult set to FALSE');
            });
          } else {
            // No result in message, we'll need to fetch it
            console.log('⏳ No result in WebSocket message, setting isLoadingResult to TRUE');
            flushSync(() => {
              setIsLoadingResult(true); // Show loading state
              console.log('⏳ isLoadingResult set to TRUE');
            });
          }

          // Now stop the execution spinner AFTER setting result
          setIsExecuting(false);
          setHitlTask(null); // Clear any lingering HITL state

          // Update execution status to completed
          setNodeStatuses(prev => {
            // Create a new status object with execution completed
            const newStatuses = {
              ...prev,
              'execution': {
                nodeId: 'execution',
                nodeType: 'execution',
                nodeLabel: 'Flow Execution',
                status: 'completed',
                message: '✅ Flow execution completed successfully',
                timestamp: new Date().toISOString(),
                level: 'info'
              }
            };

            // Force all nodes that are still 'running' to show as 'completed'
            // This handles race conditions where node_complete messages arrive late
            Object.keys(newStatuses).forEach(nodeId => {
              if (nodeId !== 'execution' && nodeId !== 'trigger' && newStatuses[nodeId].status === 'running') {
                console.log(`Force completing node ${nodeId} on execution complete`);
                newStatuses[nodeId] = {
                  ...newStatuses[nodeId],
                  status: 'completed',
                  message: newStatuses[nodeId].message.replace('🚀', '✅').replace('executing', 'completed').replace('started', 'completed')
                };
              }
            });

            // Also force-complete any flow definition nodes that have no status entry at all
            // This handles cases where node_start/node_complete events were missed (e.g., after HITL resume)
            const flowNodes = flow?.flow_definition?.nodes || [];
            flowNodes.forEach(node => {
              if (!newStatuses[node.id]) {
                console.log(`Force completing missing node ${node.id} on execution complete`);
                newStatuses[node.id] = {
                  nodeId: node.id,
                  nodeType: node.type || 'unknown',
                  nodeLabel: node.data?.label || node.id,
                  status: 'completed',
                  message: '✅ Node completed',
                  timestamp: new Date().toISOString(),
                  level: 'info'
                };
              }
            });

            return newStatuses;
          });

          if (!hasShownCompletionToast) {
            setHasShownCompletionToast(true);
            showSuccessToast('Flow executed successfully!');

            // Only fetch execution details if we didn't get result data in the WebSocket message
            if (!hasResultInMessage) {
              console.log('No result in WebSocket message, fetching from API...');
              fetchExecutionDetails(execId);
            } else {
              console.log('Result already available from WebSocket, skipping API fetch');
            }
          }
        } else if (data.status === 'failed') {
          console.log('❌ Flow execution failed');
          setIsExecuting(false);
          // Update execution status to failed
          setNodeStatuses(prev => ({
            ...prev,
            'execution': {
              nodeId: 'execution',
              nodeType: 'execution',
              nodeLabel: 'Flow Execution',
              status: 'failed',
              message: `❌ Flow execution failed: ${data.error_message || 'Unknown error'}`,
              timestamp: new Date().toISOString(),
              level: 'error'
            }
          }));
          if (!hasShownCompletionToast) {
            setHasShownCompletionToast(true);
            showErrorToast(`Flow execution failed: ${data.error_message || 'Unknown error'}`);
            setExecutionError(data.error_message || 'Unknown error');
          }
        }

        // Handle node-specific status updates with immediate rendering
        if (data.type === 'node_start' && data.node_id) {
          // Use flushSync to force immediate synchronous update
          flushSync(() => {
            setNodeStatuses(prev => ({
              ...prev,
              [data.node_id]: {
                nodeId: data.node_id,
                nodeType: data.node_type || 'unknown',
                nodeLabel: data.node_label || data.node_id,
                status: 'running',
                message: `🚀 ${data.node_type || 'Node'} execution started`,
                timestamp: new Date().toISOString(),
                level: 'info'
              }
            }));

            // Expand only this node, collapse all others
            setExpandedNodes(new Set([data.node_id]));
          });
          console.log(`Node ${data.node_id} UI immediately updated to running and expanded`)
        } else if (data.type === 'node_complete' && data.node_id) {
          // Use flushSync for immediate completion updates too
          flushSync(() => {
            setNodeStatuses(prev => ({
              ...prev,
              [data.node_id]: {
                nodeId: data.node_id,
                nodeType: data.node_type || 'unknown',
                nodeLabel: data.node_label || data.node_id,
                status: 'completed',
                message: data.completion_message || `${data.node_type || 'Node'} completed`,
                timestamp: new Date().toISOString(),
                level: 'info'
              }
            }));
            // Collapse the completed node
            setExpandedNodes(prev => {
              const next = new Set(prev);
              next.delete(data.node_id);
              return next;
            });
          });
          console.log(`Node ${data.node_id} UI immediately updated to completed`)
        }

        // Handle HITL task created - flow is paused waiting for human input
        if (data.type === 'hitl_task_created' && data.node_id) {
          flushSync(() => {
            setHitlTask({
              task_id: data.task_id,
              title: data.title,
              task_type: data.task_type,
              priority: data.priority,
              assigned_to: data.assigned_to,
              assignees: data.assignees || [],
              can_complete: data.can_complete !== false,
              paused_at: data.paused_at || new Date().toISOString(),
              timeout_at: data.timeout_at,
              node_id: data.node_id,
            });
            setIsExecuting(false); // Stop the global spinner
            setNodeStatuses(prev => ({
              ...prev,
              [data.node_id]: {
                nodeId: data.node_id,
                nodeType: 'human_in_loop',
                nodeLabel: data.node_label || data.node_id,
                status: 'paused',
                message: data.message || `⏸️ Waiting for human ${data.task_type}`,
                timestamp: new Date().toISOString(),
                level: 'info',
                data: {
                  task_id: data.task_id,
                  assigned_to: data.assigned_to,
                  priority: data.priority,
                  paused_at: data.paused_at,
                }
              }
            }));
            setExpandedNodes(new Set([data.node_id]));
          });
        }

        // Handle HITL task completed - flow is resuming
        if (data.type === 'hitl_task_completed' && data.node_id) {
          flushSync(() => {
            setHitlTask(null);
            setShowHitlReview(false);
            setIsExecuting(true); // Flow is resuming
            setActiveTab('logs'); // Switch to logs to show flow resuming
            setNodeStatuses(prev => ({
              ...prev,
              [data.node_id]: {
                nodeId: data.node_id,
                nodeType: 'human_in_loop',
                nodeLabel: prev[data.node_id]?.nodeLabel || data.node_id,
                status: 'completed',
                message: data.message || '✅ Human review completed',
                timestamp: data.completed_at || new Date().toISOString(),
                level: 'info'
              }
            }));
          });
        }
      }
    }, [executionId, hasShownCompletionToast]),
    
    onLogUpdate: useCallback((execId, data) => {
      console.log('WebSocket log update:', execId, data);
      if (execId === executionId) {
        setExecutionLogs(prev => [...prev, data]);
        
        // Update node status based on log - but only if we don't already have status from WebSocket updates
        if (data.step_id) {
          const nodeId = data.step_id;
          
          // Check if we need to update based on the log message
          setNodeStatuses(prev => {
            const currentStatus = prev[nodeId];
            const newStatus = {
              nodeId,
              nodeType: data.data?.node_type || currentStatus?.nodeType || 'action',
              nodeLabel: data.data?.label || data.data?.node_label || currentStatus?.nodeLabel || nodeId,
              status: 'running',
              message: data.message,
              timestamp: data.timestamp || new Date().toISOString(),
              level: data.level,
              data: data.data
            };
            
            // Determine status from message
            // Don't let log messages override a 'paused' status (only WebSocket hitl_task_completed can do that)
            if (currentStatus?.status === 'paused') {
              newStatus.status = 'paused';
            } else if (data.message?.includes('⏸️') || data.message?.includes('waiting for human')) {
              newStatus.status = 'paused';
            } else if (data.message?.includes('✅') || data.message?.includes('completed successfully')) {
              newStatus.status = 'completed';
            } else if (data.level === 'error' || data.message?.includes('failed')) {
              newStatus.status = 'failed';
            } else if (data.message?.includes('🚀') || data.message?.includes('Executing')) {
              newStatus.status = 'running';
            } else if (currentStatus) {
              newStatus.status = currentStatus.status;
            }
            
            return {
              ...prev,
              [nodeId]: newStatus
            };
          });
        }
      }
    }, [executionId])
  });
  
  // Fetch subscription data for API key (if flow has app_id)
  const appId = triggerConfig?.app_id;
  const { data: subscription } = useQuery({
    queryKey: ['flow-subscription', appId],
    queryFn: async () => {
      if (!appId) return null;
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/subscriptions/`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      // Find subscription for this app
      return response.data.find(sub => sub.app_id === appId);
    },
    enabled: !!appId,
  });

  // Fetch enhanced sample code with API keys and defaults
  const { data: enhancedSampleCode } = useQuery({
    queryKey: ['flow-sample-code', flow.flow_id, activeLanguage],
    queryFn: async () => {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/flows/${flow.flow_id}/sample-code?language=${activeLanguage}&include_sync=true`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      return response.data;
    },
    enabled: showSampleCode && isManual, // Only fetch when sample code is shown and for manual triggers
    staleTime: 30000, // Cache for 30 seconds
    refetchOnWindowFocus: false,
  });
  
  // Fetch event details to get fields (if we have app_id and event_name)
  const eventName = triggerConfig?.event_name;
  const { data: eventData } = useQuery({
    queryKey: ['flow-event', appId, eventName],
    queryFn: async () => {
      if (!appId || !eventName) return null;
      const token = localStorage.getItem('access_token');
      const response = await axios.get(`${API_BASE_URL}/api/v1/applications/${appId}/events`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      // Find the specific event
      const event = response.data.find(evt => evt.event_name === eventName);
      return event;
    },
    enabled: !!appId && !!eventName && eventFields.length === 0, // Only fetch if we don't have fields
  });
  
  // Flow execution mutation
  const executeFlowMutation = useMutation({
    mutationFn: async (payload) => {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/flows/${flow.flow_id}/execute`,
        payload,
        {
          headers: { 
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      return response.data;
    },
    onSuccess: (data) => {
      console.log('Flow execution response:', data);
      console.log('WebSocket connected:', isConnected);
      setExecutionId(data.execution_id);
      // Subscribe to execution updates
      if (data.execution_id) {
        console.log('Subscribing to execution:', data.execution_id);
        subscribeToExecution(data.execution_id);
        
        // Test WebSocket notification after a short delay
        setTimeout(async () => {
          try {
            console.log('Testing WebSocket notification...');
            const token = localStorage.getItem('access_token');
            const testResponse = await axios.post(
              `${API_BASE_URL}/ws/test?execution_id=${data.execution_id}`,
              {},
              {
                headers: { Authorization: `Bearer ${token}` }
              }
            );
            console.log('WebSocket test response:', testResponse.data);
          } catch (error) {
            console.error('WebSocket test failed:', error);
          }
        }, 1000);
      }
    },
    onError: (error) => {
      setIsExecuting(false);

      // Handle 402 Payment Required - Insufficient Balance
      if (error.response?.status === 402) {
        const data = error.response.data;
        const requiredAmount = data.required_amount || 0;
        const availableAmount = data.available_amount || 0;
        const suggestedTopup = data.suggested_topup || 10;

        const errorMessage = `Insufficient balance. Required: $${requiredAmount.toFixed(2)}, Available: $${availableAmount.toFixed(2)}`;
        showErrorToast(errorMessage);
        setExecutionError(
          <div className="space-y-2">
            <p className="font-semibold text-red-600">Insufficient Balance</p>
            <p>{data.message || errorMessage}</p>
            <p className="text-sm text-gray-600">
              Please top up at least ${suggestedTopup.toFixed(2)} to continue.
            </p>
            <button
              onClick={() => window.location.href = '/billing'}
              className="mt-2 px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
            >
              Go to Billing
            </button>
          </div>
        );
      } else {
        const errorMessage = (error.response?.data?.message || error.response?.data?.detail) || error.response?.data?.message || error.message;
        showErrorToast(`Failed to trigger flow: ${errorMessage}`);
        setExecutionError(errorMessage);
      }
    }
  });

  // Fetch full execution details
  const fetchExecutionDetails = async (execId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.get(
        `${API_BASE_URL}/api/v1/executions/${execId}`,
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );
      
      console.log('Full execution details:', response.data);
      console.log('Steps:', response.data.steps);
      console.log('Result data:', response.data.result_data);
      console.log('Output data:', response.data.output_data);
      console.log('Response data:', response.data.response_data);
      console.log('Result:', response.data.result);
      console.log('Response status:', response.data.response_status);
      console.log('Response headers:', response.data.response_headers);

      // Extract response data from the execution
      // Priority: result_data (from response node) > output_data > response_data > result
      let responseData = response.data.result_data || response.data.output_data || response.data.response_data || response.data.result;
      console.log('Initial responseData extraction:', responseData);
      
      // Check if there's a response_output field
      if (!responseData && response.data.response_output) {
        responseData = response.data.response_output;
      }
      
      // Use flow definition to find the terminal node and get its output
      if (!responseData && response.data.node_outputs) {
        console.log('Checking node_outputs for response data:', response.data.node_outputs);
        const flowNodes = flow?.flow_definition?.nodes || [];
        const flowEdges = flow?.flow_definition?.edges || [];

        // Find terminal node: a node that has no outgoing edges (excluding trigger)
        const sourceNodeIds = new Set(flowEdges.map(e => e.source));
        const terminalNodes = flowNodes.filter(n => n.type !== 'trigger' && !sourceNodeIds.has(n.id));

        if (terminalNodes.length > 0) {
          const terminalNodeId = terminalNodes[terminalNodes.length - 1].id;
          if (response.data.node_outputs[terminalNodeId]) {
            console.log(`Using terminal node output from ${terminalNodeId}:`, response.data.node_outputs[terminalNodeId]);
            responseData = response.data.node_outputs[terminalNodeId];
          }
        }

        // Fallback: use the last entry in node_outputs
        if (!responseData) {
          const nodeIds = Object.keys(response.data.node_outputs);
          if (nodeIds.length > 0) {
            const lastNodeId = nodeIds[nodeIds.length - 1];
            responseData = response.data.node_outputs[lastNodeId];
            console.log(`Fallback: using last node output from ${lastNodeId}:`, responseData);
          }
        }
      }
      
      // If no direct output_data, try to get from steps using the terminal node
      if (!responseData && response.data.steps && response.data.steps.length > 0) {
        const flowNodes = flow?.flow_definition?.nodes || [];
        const flowEdges = flow?.flow_definition?.edges || [];
        const sourceNodeIds = new Set(flowEdges.map(e => e.source));
        const terminalNodes = flowNodes.filter(n => n.type !== 'trigger' && !sourceNodeIds.has(n.id));

        // Find the terminal node's step
        if (terminalNodes.length > 0) {
          const terminalNodeId = terminalNodes[terminalNodes.length - 1].id;
          const terminalStep = response.data.steps.find(step => step.node_id === terminalNodeId);
          if (terminalStep) {
            console.log('Terminal step found:', terminalStep.node_id, terminalStep);
            responseData = terminalStep.output_data || terminalStep.result || terminalStep.output || terminalStep.data;
          }
        }

        // Fallback: last step with output
        if (!responseData) {
          for (const step of [...response.data.steps].reverse()) {
            if (step.output_data || step.result || step.output) {
              console.log('Fallback: found output in step:', step.node_id);
              responseData = step.output_data || step.result || step.output;
              break;
            }
          }
        }
      }
      
      console.log('Final response data:', responseData);
      
      // If we still don't have response data, let's check if it's stored at the execution level
      if (!responseData) {
        // Check if the response is stored in a special field
        if (response.data.flow_response) {
          responseData = response.data.flow_response;
        } else if (response.data.final_output) {
          responseData = response.data.final_output;
        }
      }
      
      setExecutionResult({
        ...response.data,
        response_data: responseData,
        data: responseData  // Add this for consistency with direct API calls
      });

      // Turn off loading state
      setIsLoadingResult(false);

      // If still no response data, log the entire response for debugging
      if (!responseData) {
        console.log('WARNING: No response data found. Full response structure:', JSON.stringify(response.data, null, 2));
      }
    } catch (error) {
      console.error('Failed to fetch execution details:', error);
      setIsLoadingResult(false); // Turn off loading even on error
    }
  };

  // Copy code to clipboard
  const copyToClipboard = async (code) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };
  
  // Get endpoint URL based on trigger type
  const getEndpointUrl = () => {
    if (isWebhook) {
      // For webhook triggers (application events)
      return `${API_BASE_URL}/webhooks/${triggerConfig.app_id}/${triggerConfig.event_name}`;
    } else if (isApiCall) {
      // For API call triggers
      const event = triggerConfig.event || {};
      if (event.api_endpoint) {
        return `${API_BASE_URL}${event.api_endpoint}`;
      }
      return `${API_BASE_URL}/api/v1/events/${triggerConfig.app_id}/${triggerConfig.event_name}`;
    } else {
      // For direct flow trigger
      return `${API_BASE_URL}/api/v1/flows/${flow.flow_id}/execute`;
    }
  };
  
  // Get HTTP method
  const getHttpMethod = () => {
    if (isApiCall && triggerConfig.event?.trigger_config?.http_method) {
      return triggerConfig.event.trigger_config.http_method;
    }
    return 'POST';
  };
  
  // Get authentication header
  const getAuthHeader = () => {
    if (isWebhook || isApiCall) {
      const apiKey = subscription?.invocation_api_key || 'YOUR_INVOCATION_API_KEY';
      return { 'Authorization': `Bearer ${apiKey}` };
    } else {
      return { 'Authorization': 'Bearer YOUR_ACCESS_TOKEN' };
    }
  };
  
  // Convert manual variables to schema format for sample generation
  const convertVariablesToSchema = () => {
    const schema = {
      type: 'object',
      properties: {},
      required: []
    };
    
    (Array.isArray(manualVariables) ? manualVariables : []).forEach(variable => {
      const varSchema = {
        type: variable.dataType || 'string',
        description: variable.description || variable.displayName || variable.name
      };
      
      // Add format based on UI control
      if (variable.uiControl === 'email') varSchema.format = 'email';
      if (variable.uiControl === 'url') varSchema.format = 'uri';
      if (variable.uiControl === 'date') varSchema.format = 'date';
      if (variable.uiControl === 'datetime') varSchema.format = 'date-time';
      
      // Add validation constraints
      if (variable.validation) {
        if (variable.validation.min !== undefined) varSchema.minimum = variable.validation.min;
        if (variable.validation.max !== undefined) varSchema.maximum = variable.validation.max;
        if (variable.validation.pattern) varSchema.pattern = variable.validation.pattern;
      }
      
      schema.properties[variable.name] = varSchema;
      
      if (variable.required) {
        schema.required.push(variable.name);
      }
    });
    
    return schema;
  };
  
  // Convert event fields to schema format
  const convertEventFieldsToSchema = (fields = eventFields) => {
    const schema = {
      type: 'object',
      properties: {},
      required: []
    };
    
    fields.forEach(field => {
      // Parse the field path (e.g., "order.customer.name" -> ["order", "customer", "name"])
      const parts = field.field_name.split('.');
      let current = schema.properties;
      
      // Build nested structure
      for (let i = 0; i < parts.length - 1; i++) {
        const part = parts[i];
        if (!current[part]) {
          current[part] = {
            type: 'object',
            properties: {}
          };
        }
        current = current[part].properties;
      }
      
      // Set the final property
      const lastPart = parts[parts.length - 1];
      current[lastPart] = {
        type: field.data_type || 'string',
        description: field.description || field.friendly_name || field.field_name
      };
      
      // Add to required array if needed
      if (field.is_required) {
        schema.required.push(parts[0]);
      }
    });
    
    return schema;
  };
  
  // Generate sample payload based on trigger type
  const generateSamplePayload = () => {
    if (isManual && Array.isArray(manualVariables) && manualVariables.length > 0) {
      // For manual triggers with variables, generate from schema
      const schema = convertVariablesToSchema();
      return generateSampleFromSchema(schema);
    } else if ((isWebhook || triggerConfig.type === 'event') && eventFields.length > 0) {
      // For webhook/event triggers with event fields from trigger node
      const schema = convertEventFieldsToSchema();
      return generateSampleFromSchema(schema);
    } else if ((isWebhook || triggerConfig.type === 'event') && eventData) {
      // Use schema or sample payload from fetched event data
      if (eventData.output_schema) {
        // Use the output schema directly
        return generateSampleFromSchema(eventData.output_schema);
      } else if (eventData.sample_payload) {
        // Use the sample payload directly
        return eventData.sample_payload;
      } else {
        // Try to use fields if available
        const fields = eventData.fields || eventData._fields || eventData.properties || [];
        if (fields.length > 0) {
          const schema = convertEventFieldsToSchema(fields);
          return generateSampleFromSchema(schema);
        }
      }
    } else if (isWebhook && triggerConfig.event_schema) {
      // Fallback: For webhook triggers with schema in trigger config
      return generateSampleFromSchema(triggerConfig.event_schema);
    } else {
      // Use current form data as fallback
      return formData;
    }
  };
  
  // Generate sample code for different languages
  const generateSampleCode = (language) => {
    const endpoint = getEndpointUrl();
    const method = getHttpMethod();
    const authHeader = getAuthHeader();
    const sampleData = generateSamplePayload();
    
    // For webhook/API triggers, wrap data if needed
    const payload = (isWebhook || isApiCall) ? sampleData : { 
      trigger_type: 'manual',
      variables: sampleData 
    };
    
    const authKey = Object.keys(authHeader)[0];
    const authValue = authHeader[authKey];
    
    switch (language) {
      case 'curl':
        return `# Trigger ${flow.flow_name} flow
curl -X ${method} \\
  '${endpoint}' \\
  -H 'Content-Type: application/json' \\
  -H '${authKey}: ${authValue}' \\
  -d '${JSON.stringify(payload, null, 2)}'`;
      
      case 'python':
        return `import requests
import json

# Trigger ${flow.flow_name} flow
url = "${endpoint}"
headers = {
    "Content-Type": "application/json",
    "${authKey}": "${authValue}"
}
payload = ${JSON.stringify(payload, null, 4)}

response = requests.${method.toLowerCase()}(url, headers=headers, json=payload)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")`;
      
      case 'javascript':
        return `// Trigger ${flow.flow_name} flow
const url = "${endpoint}";
const headers = {
  "Content-Type": "application/json",
  "${authKey}": "${authValue}"
};
const payload = ${JSON.stringify(payload, null, 2)};

fetch(url, {
  method: "${method}",
  headers: headers,
  body: JSON.stringify(payload)
})
.then(response => response.json())
.then(data => {
  console.log("Success:", data);
})
.catch(error => {
  console.error("Error:", error);
});`;
      
      case 'java':
        return `import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class TriggerFlow {
    public static void main(String[] args) {
        try {
            // Trigger ${flow.flow_name} flow
            URL url = new URL("${endpoint}");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            
            conn.setRequestMethod("${method}");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("${authKey}", "${authValue}");
            conn.setDoOutput(true);
            
            String payload = ${JSON.stringify(JSON.stringify(payload))};
            
            try (OutputStream os = conn.getOutputStream()) {
                byte[] input = payload.getBytes("utf-8");
                os.write(input, 0, input.length);
            }
            
            int responseCode = conn.getResponseCode();
            System.out.println("Response Code: " + responseCode);
            
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(conn.getInputStream(), "utf-8"))) {
                StringBuilder response = new StringBuilder();
                String responseLine;
                while ((responseLine = br.readLine()) != null) {
                    response.append(responseLine.trim());
                }
                System.out.println("Response: " + response.toString());
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}`;
      
      default:
        return '';
    }
  };

  
  const handleFieldChange = useCallback((name, value) => {
    setFormData(prev => ({ ...prev, [name]: value }));
  }, []);

  const handleTrigger = (overrideData = null) => {
    try {
      // Reset execution state
      setIsExecuting(true);
      setExecutionId(null);
      setExecutionLogs([]);
      setNodeStatuses({});
      setExecutionResult(null);
      setExecutionError(null);
      setHasShownCompletionToast(false);
      setIsLoadingResult(false); // Reset loading state

      // Use override data if provided, otherwise use formData
      const dataToSubmit = overrideData !== null ? overrideData : formData;

      // Execute the flow
      const payload = {
        trigger_type: 'manual',
        variables: dataToSubmit
      };

      console.log('Triggering flow with data:', dataToSubmit);

      executeFlowMutation.mutate(payload);
    } catch (e) {
      setError('Failed to parse input data');
      setIsExecuting(false);
    }
  };

  // Handle form submission (Enter key or button click)
  const handleFormSubmit = async (e) => {
    e.preventDefault();

    // Capture current form data by reading directly from form elements
    const currentFormData = {};

    // Find all input/textarea elements in the form
    const formElements = e.target.querySelectorAll('input, textarea, select');

    manualVariables.forEach(variable => {
      // Try to find the corresponding form element
      const element = Array.from(formElements).find(el => {
        // Check various attributes that might match the variable name
        return el.name === variable.name ||
               el.getAttribute('data-variable-name') === variable.name ||
               el.id === variable.name;
      });

      if (element) {
        currentFormData[variable.name] = element.value;
        console.log(`Captured ${variable.name}:`, element.value);
      } else {
        // Fallback to formData state
        currentFormData[variable.name] = formData[variable.name];
        console.log(`Using formData for ${variable.name}:`, formData[variable.name]);
      }
    });

    console.log('Final form data to submit:', currentFormData);

    // Trigger with the captured data
    handleTrigger(currentFormData);
  };
  
  // Toggle node expansion
  const toggleNode = useCallback((nodeId) => {
    setExpandedNodes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(nodeId)) {
        newSet.delete(nodeId);
      } else {
        newSet.add(nodeId);
      }
      return newSet;
    });
  }, []);

  // Chat message handlers (for chat_input trigger type)
  const handleChatMessage = useCallback(async (message) => {
    if (!message.trim()) return;

    // Add user message to chat
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    };
    setChatMessages(prev => [...prev, userMessage]);
    setChatError(null);
    setIsExecuting(true);

    // Add streaming placeholder for assistant response
    const assistantPlaceholder = {
      role: 'assistant',
      content: '',
      isStreaming: true,
      timestamp: new Date().toISOString()
    };
    setChatMessages(prev => [...prev, assistantPlaceholder]);

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/flows/${flow.flow_id}/chat`,
        {
          message: message,
          chat_session_id: chatSessionId
        },
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      const data = response.data;

      // Update session ID if this is a new session
      if (data.chat_session_id && data.chat_session_id !== chatSessionId) {
        setChatSessionId(data.chat_session_id);
      }

      // Update the assistant message with the response
      setChatMessages(prev => {
        const updated = [...prev];
        const lastIndex = updated.length - 1;
        if (updated[lastIndex]?.isStreaming) {
          // Extract response content
          let responseContent = '';
          let toolCalls = [];

          if (data.response) {
            if (typeof data.response === 'string') {
              responseContent = data.response;
            } else if (data.response.result) {
              responseContent = data.response.result;
              toolCalls = data.response.tool_calls || [];
            } else if (data.response.data) {
              responseContent = typeof data.response.data === 'string'
                ? data.response.data
                : JSON.stringify(data.response.data, null, 2);
            } else {
              responseContent = JSON.stringify(data.response, null, 2);
            }
          }

          updated[lastIndex] = {
            role: 'assistant',
            content: responseContent,
            toolCalls: toolCalls,
            isStreaming: false,
            timestamp: new Date().toISOString()
          };
        }
        return updated;
      });

    } catch (err) {
      console.error('Chat execution error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Failed to execute chat';
      setChatError(errorMessage);

      // Remove the streaming placeholder
      setChatMessages(prev => prev.filter(m => !m.isStreaming));
    } finally {
      setIsExecuting(false);
    }
  }, [API_BASE_URL, flow?.flow_id, chatSessionId]);

  const handleNewChatSession = useCallback(() => {
    setChatSessionId(null);
    setChatMessages([]);
    setChatError(null);
    setExecutionResult(null);
    setExecutionError(null);
  }, []);

  const handleEndChatSession = useCallback(async () => {
    if (!chatSessionId) return;

    try {
      const token = localStorage.getItem('access_token');
      await axios.post(
        `${API_BASE_URL}/api/v1/flows/${flow.flow_id}/chat/end`,
        { chat_session_id: chatSessionId },
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      // Reset chat state
      handleNewChatSession();
      showSuccessToast('Chat session ended');
    } catch (err) {
      console.error('Failed to end chat session:', err);
      setChatError('Failed to end chat session');
    }
  }, [API_BASE_URL, flow?.flow_id, chatSessionId, handleNewChatSession]);
  
  // Initialize flow diagram from flow definition
  useEffect(() => {
    if (flow?.flow_definition?.nodes && flow?.flow_definition?.edges) {
      const initNodes = flow.flow_definition.nodes.map(node => ({
        ...node,
        data: { ...node.data, executionMode: true },
        style: { ...node.style },
      }));
      setFlowNodes(initNodes);
      setFlowEdges(flow.flow_definition.edges || []);
    }
  }, [flow, setFlowNodes, setFlowEdges]);

  // Update flow diagram nodes with execution status
  useEffect(() => {
    if (flowNodes.length === 0) return;
    setFlowNodes(nds =>
      nds.map(node => {
        const status = nodeStatuses[node.id];
        return {
          ...node,
          data: {
            ...node.data,
            isExecuting: status?.status === 'running',
            isExecuted: status?.status === 'completed',
            executionStatus: status?.status,
            executionMode: true,
          }
        };
      })
    );
  }, [nodeStatuses, setFlowNodes]);

  // Custom tab switching function that tracks user interaction
  const handleTabSwitch = useCallback((tab) => {
    setActiveTab(tab);
    setUserHasSwitchedTabs(true);
  }, []);
  
  // Get node status icon
  const getNodeStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircleIcon className="w-5 h-5 text-red-500" />;
      case 'running':
        return <ArrowPathIcon className="w-5 h-5 text-blue-500 animate-spin" />;
      case 'paused':
        return <PauseCircleIcon className="w-5 h-5 text-orange-500 animate-pulse" />;
      default:
        return <ClockIcon className="w-5 h-5 text-gray-400" />;
    }
  };

  // Get node status color
  const getNodeStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'border-green-200 bg-green-50';
      case 'failed':
        return 'border-red-200 bg-red-50';
      case 'running':
        return 'border-blue-200 bg-blue-50';
      case 'paused':
        return 'border-orange-200 bg-orange-50';
      default:
        return 'border-gray-200 bg-gray-50';
    }
  };
  
  // Format timestamp
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', { 
      hour12: false, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit',
      fractionalSecondDigits: 3 
    });
  };
  
  // Auto-execute for synchronous flows without parameters
  const [hasAutoExecuted, setHasAutoExecuted] = useState(false);
  
  useEffect(() => {
    // Check if this is a synchronous flow without parameters
    if (flow?.is_synchronous && 
        isManual && 
        (!manualVariables || manualVariables.length === 0) && 
        !hasAutoExecuted && 
        !isExecuting && 
        !executionResult && 
        !executionError) {
      console.log('Auto-executing synchronous flow without parameters');
      setHasAutoExecuted(true);
      // Auto-trigger the flow
      handleTrigger();
    }
  }, [flow, isManual, manualVariables, hasAutoExecuted, isExecuting, executionResult, executionError]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (executionId) {
        unsubscribeFromExecution(executionId);
      }
    };
  }, [executionId, unsubscribeFromExecution]);


  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-[100]">
      <div className={`bg-white rounded-lg flex flex-col ${
        isMaximized ? 'fixed inset-4' : 'max-w-6xl w-full max-h-[90vh]'
      }`}>
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-lg font-medium text-gray-900">
            Trigger Flow: {flow.flow_name}
          </h3>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsMaximized(!isMaximized)}
              className="text-gray-400 hover:text-gray-500"
              title={isMaximized ? "Restore" : "Maximize"}
            >
              {isMaximized ? (
                <ArrowsPointingInIcon className="h-5 w-5" />
              ) : (
                <ArrowsPointingOutIcon className="h-5 w-5" />
              )}
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <XMarkIcon className="h-6 w-6" />
            </button>
          </div>
        </div>

        {/* Chat Input Trigger - Full Chat UI */}
        {isChatInput ? (
          <div className="flex-1 overflow-hidden">
            <ChatTriggerView
              flow={flow}
              onSendMessage={handleChatMessage}
              isExecuting={isExecuting}
              messages={chatMessages}
              chatSessionId={chatSessionId}
              onNewSession={handleNewChatSession}
              onEndSession={handleEndChatSession}
              error={chatError}
            />
          </div>
        ) : (
          <>
            {/* HITL Waiting Indicator in header */}
            {hitlTask && !isExecuting && (
              <div className="px-6 py-2.5 bg-orange-50 border-b border-orange-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <PauseCircleIcon className="w-5 h-5 text-orange-500 animate-pulse" />
                  <span className="text-sm font-medium text-orange-800">
                    Waiting for human input
                  </span>
                  <span className="text-xs text-orange-600">
                    — {hitlTask.title}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-orange-700">
                    Assigned to: <strong>{hitlTask.assigned_to || 'Unassigned'}</strong>
                  </span>
                  {hitlTask.can_complete && (
                    <button
                      onClick={() => { setShowHitlReview(true); }}
                      className="px-3 py-1 text-xs font-medium text-white bg-orange-500 rounded hover:bg-orange-600"
                    >
                      Complete Task
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Execution Status Indicator */}
            {(executionResult || executionError) && (
              <div className="px-6 py-2 bg-gray-50 border-b border-gray-200">
                {executionResult && (
                  <div className="flex items-center">
                    <CheckCircleIcon className="w-4 h-4 text-green-600 mr-2" />
                    <span className="text-sm font-medium text-green-800">
                      Flow executed successfully
                    </span>
                    {executionId && (
                      <span className="text-xs text-gray-500 ml-2">
                        ID: {executionId}
                      </span>
                    )}
                  </div>
                )}
                {executionError && (
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <XCircleIcon className="w-4 h-4 text-red-600 mr-2" />
                      <span className="text-sm font-medium text-red-800">
                        Flow execution failed
                      </span>
                    </div>
                    <button
                      onClick={() => handleTabSwitch('input')}
                      className="ml-4 px-2 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors"
                    >
                      Edit Input
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Tab Navigation */}
        <div className="px-6 border-b border-gray-200">
          <div className="flex space-x-8">
            <button
              onClick={() => handleTabSwitch('input')}
              className={`py-3 text-sm font-medium border-b-2 ${
                activeTab === 'input'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Input
            </button>
            <button
              onClick={() => handleTabSwitch('results')}
              className={`py-3 text-sm font-medium border-b-2 flex items-center gap-2 ${
                activeTab === 'results'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Results
              {hitlTask && !isExecuting && (
                <PauseCircleIcon className="w-4 h-4 text-orange-500 animate-pulse" />
              )}
            </button>
            <button
              onClick={() => handleTabSwitch('logs')}
              className={`py-3 text-sm font-medium border-b-2 flex items-center gap-2 ${
                activeTab === 'logs'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Execution Logs
              {isExecuting && (
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
              )}
              {hitlTask && !isExecuting && (
                <PauseCircleIcon className="w-4 h-4 text-orange-500 animate-pulse" />
              )}
              {!isExecuting && !hitlTask && executionId && !executionError && (
                <CheckCircleIcon className="w-4 h-4 text-green-500" />
              )}
              {!isExecuting && executionError && (
                <XCircleIcon className="w-4 h-4 text-red-500" />
              )}
            </button>
          </div>
        </div>

        {/* Tab Content */}
        <div className={`flex-1 min-h-0 ${activeTab === 'logs' ? 'flex flex-col' : 'overflow-y-auto'}`}>
          
          {/* Input Tab */}
          {activeTab === 'input' && (
            <div className="px-6 py-4">
              {isManual && (
                <form
                  onSubmit={handleFormSubmit}
                  onClick={(e) => {
                    // Prevent form submission if a button with type="button" was clicked
                    if (e.target.tagName === 'BUTTON' && e.target.type === 'button') {
                      e.stopPropagation();
                    }
                  }}
                >
                  {Array.isArray(manualVariables) && manualVariables.length > 0 ? (
                    <>
                      <p className="text-sm text-gray-600 mb-4">
                        Enter the input data for this manual trigger:
                      </p>
                      
                      <div className={`mb-6 ${
                        isMaximized
                          ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4'
                          : 'grid grid-cols-1 md:grid-cols-2 gap-4'
                      }`}>
                        {manualVariables.map((variable) => {
                          // Check if field has nested properties (nested JSON or array of objects)
                          const hasNestedProperties = variable.properties && variable.properties.length > 0;
                          const isArrayOfObjects = variable.dataType === 'array' &&
                                                  (variable.itemType === 'object' || variable.itemType === 'OBJECT') &&
                                                  hasNestedProperties;

                          // Nested fields should always use full width
                          const isNestedField = hasNestedProperties || isArrayOfObjects;

                          // Other complex fields that benefit from more space
                          const isComplexField =
                            variable.uiControl === 'textarea' ||
                            variable.uiControl === 'code' ||
                            variable.uiControl === 'wysiwyg' ||
                            (variable.dataType === 'json' && !hasNestedProperties) || // Simple JSON without schema
                            (variable.dataType === 'array' && !isArrayOfObjects); // Simple array

                          // Determine column spanning
                          let colSpanClass = '';
                          if (isNestedField) {
                            // Full width for nested fields
                            colSpanClass = isMaximized
                              ? 'sm:col-span-full lg:col-span-full xl:col-span-full 2xl:col-span-full'
                              : 'md:col-span-full';
                          } else if (isComplexField) {
                            // 2 columns for complex fields
                            colSpanClass = isMaximized
                              ? 'sm:col-span-2 lg:col-span-2 xl:col-span-2 2xl:col-span-2'
                              : 'md:col-span-2';
                          }

                          return (
                            <div key={variable.id || variable.name} className={colSpanClass}>
                              <IsolatedField
                                variable={variable}
                                value={formData[variable.name] !== undefined ? formData[variable.name] : undefined}
                                onChange={handleFieldChange}
                              />
                            </div>
                          );
                        })}
                      </div>
                      
                      <div className="flex flex-wrap gap-3">
                        <button
                          type="submit"
                          disabled={isExecuting}
                          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isExecuting ? (
                            <>
                              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                              <span>Executing...</span>
                            </>
                          ) : (
                            <>
                              <PlayIcon className="w-4 h-4" />
                              <span>Trigger Flow</span>
                            </>
                          )}
                        </button>
                        
                        <button
                          type="button"
                          onClick={() => setShowSampleCode(!showSampleCode)}
                          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200"
                        >
                          <CodeBracketIcon className="w-4 h-4 inline mr-2" />
                          {showSampleCode ? 'Hide' : 'Show'} API Sample
                        </button>
                      </div>
                      
                      {showSampleCode && (
                        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                          <h4 className="text-sm font-medium text-gray-700 mb-3">API Sample</h4>
                          
                          {/* Language Tabs */}
                          <div className="flex space-x-1 mb-4 bg-gray-200 p-1 rounded-md">
                            {['python', 'curl', 'javascript', 'java'].map((lang) => (
                              <button
                                key={lang}
                                type="button"
                                onClick={() => setActiveLanguage(lang)}
                                className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                                  activeLanguage === lang
                                    ? 'bg-white text-gray-900 shadow'
                                    : 'text-gray-600 hover:text-gray-900'
                                }`}
                              >
                                {lang.charAt(0).toUpperCase() + lang.slice(1)}
                              </button>
                            ))}
                          </div>
                          
                          <CodeBlock 
                            code={enhancedSampleCode?.sample_code || generateSampleCode(activeLanguage)} 
                            language={activeLanguage} 
                          />
                        </div>
                      )}
                    </>
                  ) : flow?.is_synchronous ? (
                    // For synchronous flows without parameters, show auto-executing state
                    <>
                      <div className="space-y-4">
                        <p className="text-sm text-gray-600">
                          This synchronous flow has no input parameters and will execute automatically.
                        </p>
                        
                        {isExecuting && (
                          <div className="flex items-center space-x-3 p-4 bg-blue-50 rounded-lg">
                            <div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full"></div>
                            <span className="text-sm text-blue-700">Executing flow...</span>
                          </div>
                        )}
                        
                        {executionError && (
                          <div className="p-4 bg-red-50 border border-red-200 rounded-md">
                            <p className="text-sm text-red-700">{executionError}</p>
                            <button
                              onClick={() => {
                                setExecutionError(null);
                                setHasAutoExecuted(false);
                                // Will trigger auto-execution again
                              }}
                              className="mt-2 px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
                            >
                              Retry
                            </button>
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    // For non-synchronous flows without parameters
                    <>
                      <div className="text-center py-8 bg-gray-50 rounded-lg mb-6">
                        <p className="text-sm text-gray-500 mb-4">
                          This flow has no input parameters defined.
                        </p>
                        <button
                          type="submit"
                          disabled={isExecuting}
                          className="inline-flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                        >
                          {isExecuting ? (
                            <>
                              <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
                              <span>Executing...</span>
                            </>
                          ) : (
                            <>
                              <PlayIcon className="w-4 h-4" />
                              <span>Trigger Flow</span>
                            </>
                          )}
                        </button>
                      </div>
                    </>
                  )}
                </form>
              )}
            </div>
          )}
          
          {/* Results Tab */}
          {activeTab === 'results' && (
            <div className="px-6 py-4">
              {executionError && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-md mb-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <XCircleIcon className="w-5 h-5 text-red-600 mr-2" />
                      <div>
                        <p className="text-sm font-medium text-red-800">
                          Flow execution failed
                        </p>
                        <p className="text-sm text-red-700 mt-1">{executionError}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => handleTabSwitch('input')}
                      className="ml-4 px-3 py-1 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 transition-colors"
                    >
                      Try Again
                    </button>
                  </div>
                </div>
              )}
              
              {hitlTask && !isExecuting ? (
                // Show HITL waiting state
                <div className="text-center py-10">
                  <PauseCircleIcon className="w-12 h-12 text-orange-400 mx-auto mb-3 animate-pulse" />
                  <p className="text-base font-medium text-gray-800">Waiting for Human Input</p>
                  <p className="text-sm text-gray-500 mt-1">{hitlTask.title}</p>
                  <div className="flex items-center justify-center gap-4 mt-3 text-xs text-gray-500">
                    <span>Type: <strong>{hitlTask.task_type}</strong></span>
                    <span>Priority: <strong>{hitlTask.priority}</strong></span>
                    <span>Assigned: <strong>{hitlTask.assigned_to}</strong></span>
                  </div>
                  <p className="text-xs text-gray-400 mt-2">
                    Paused since {new Date(hitlTask.paused_at).toLocaleTimeString()}
                  </p>
                  {hitlTask.can_complete && (
                    <button
                      onClick={() => setShowHitlReview(true)}
                      className="mt-4 px-5 py-2 text-sm font-medium text-white bg-orange-500 rounded-md hover:bg-orange-600 transition-colors"
                    >
                      Complete Task
                    </button>
                  )}
                </div>
              ) : isExecuting || isLoadingResult ? (
                // Show loading while executing or loading result
                <div className="text-center py-12">
                  <div className="inline-flex items-center space-x-3">
                    <div className="animate-spin h-6 w-6 border-2 border-blue-600 border-t-transparent rounded-full"></div>
                    <span className="text-gray-600">
                      {isExecuting ? 'Executing flow...' : 'Loading results...'}
                    </span>
                  </div>
                </div>
              ) : executionResult ? (
                <div className="space-y-4">
                  {(executionResult.data || executionResult.response_data || executionResult.result_data) ? (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-gray-500">
                          Format: {executionResult.headers?.['X-Output-Format'] || executionResult.response_headers?.['X-Output-Format'] || 'text'}
                        </span>
                      </div>
                      <div className="bg-gray-50 rounded-lg p-4 overflow-auto" style={{ minHeight: '200px', maxHeight: '70vh' }}>
                        {(() => {
                          const outputFormat = executionResult.headers?.['X-Output-Format'] ||
                                            executionResult.response_headers?.['X-Output-Format'] || 'text';
                          const responseData = executionResult.data || executionResult.response_data || executionResult.result_data;

                          console.log('🎨 Rendering result with format:', outputFormat);
                          console.log('📦 Response headers:', executionResult.response_headers);
                          console.log('📦 Headers:', executionResult.headers);

                          try {
                            switch (outputFormat) {
                              case 'json':
                                const jsonData = typeof responseData === 'string' ? JSON.parse(responseData) : responseData;
                                return (
                                  <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap">
                                    {JSON.stringify(jsonData, null, 2)}
                                  </pre>
                                );
                              case 'html':
                                return (
                                  <div
                                    className="text-sm"
                                    style={{ maxWidth: '100%' }}
                                    dangerouslySetInnerHTML={{
                                      __html: `<style>.result-html img { max-width: 100%; height: auto; }</style><div class="result-html">${typeof responseData === 'string' ? responseData : JSON.stringify(responseData)}</div>`
                                    }}
                                  />
                                );
                              case 'xml':
                                return (
                                  <pre className="text-sm font-mono text-gray-800 whitespace-pre-wrap">
                                    {typeof responseData === 'string' ? responseData : JSON.stringify(responseData)}
                                  </pre>
                                );
                              case 'text':
                              default:
                                return (
                                  <div className="text-sm text-gray-800 whitespace-pre-wrap">
                                    {typeof responseData === 'string' ? responseData : JSON.stringify(responseData, null, 2)}
                                  </div>
                                );
                            }
                          } catch (error) {
                            return (
                              <div className="text-sm text-gray-800 whitespace-pre-wrap">
                                {typeof responseData === 'string' ? responseData : JSON.stringify(responseData, null, 2)}
                              </div>
                            );
                          }
                        })()}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-12 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <p className="text-sm text-yellow-800 font-medium">No response data found</p>
                      <p className="text-xs text-yellow-600 mt-2">
                        The flow completed but no response data was returned.
                      </p>
                      <details className="mt-4 text-left max-w-2xl mx-auto">
                        <summary className="text-xs text-blue-600 cursor-pointer hover:text-blue-800">
                          Show debug info
                        </summary>
                        <pre className="mt-2 p-3 bg-white rounded text-xs overflow-auto">
                          {JSON.stringify(executionResult, null, 2)}
                        </pre>
                      </details>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <p className="text-sm">Execute the flow to see results here</p>
                </div>
              )}
            </div>
          )}
          
          {/* Execution Logs Tab */}
          {activeTab === 'logs' && (
            <div className="flex flex-1 min-h-0">
              {/* Left: Visual Flow Diagram */}
              {flowNodes.length > 0 && (
                <div className="w-2/5 border-r border-gray-200 relative">
                  <ReactFlow
                    nodes={flowNodes}
                    edges={flowEdges}
                    onNodesChange={onFlowNodesChange}
                    onEdgesChange={onFlowEdgesChange}
                    onInit={(instance) => { reactFlowInstance.current = instance; }}
                    nodeTypes={flowNodeTypes}
                    edgeTypes={flowEdgeTypes}
                    fitView
                    fitViewOptions={{ padding: 0.3, minZoom: 0.3, maxZoom: 1 }}
                    nodesDraggable={false}
                    nodesConnectable={false}
                    elementsSelectable={false}
                    panOnDrag={true}
                    zoomOnScroll={true}
                    preventScrolling={false}
                    proOptions={{ hideAttribution: true }}
                  >
                    <Background gap={16} size={1} color="#f0f0f0" />
                    <Controls showInteractive={false} position="bottom-left" />
                  </ReactFlow>
                </div>
              )}

              {/* Right: Execution Steps */}
              <div className={`${flowNodes.length > 0 ? 'w-3/5' : 'w-full'} overflow-y-auto px-4 py-4`}>
                {isExecuting && !isConnected && (
                  <div className="mb-3 p-2.5 bg-yellow-50 border border-yellow-200 rounded-md">
                    <div className="flex items-center">
                      <ExclamationTriangleIcon className="w-4 h-4 text-yellow-600 mr-2" />
                      <p className="text-xs text-yellow-800">
                        Connecting to real-time updates...
                      </p>
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  {/* Flow Definition Nodes */}
                  {flow?.flow_definition?.nodes?.map(node => {
                    const status = nodeStatuses[node.id];
                    const isExpanded = expandedNodes.has(node.id);
                    const hasLogs = executionLogs.filter(log => log.step_id === node.id).length > 0;
                    const hasContent = status || hasLogs;

                    return (
                      <div
                        key={node.id}
                        className={`border rounded-lg transition-all ${
                          status ? getNodeStatusColor(status.status) : 'border-gray-200 bg-gray-50'
                        }`}
                      >
                        <div
                          className="px-3 py-2 cursor-pointer"
                          onClick={() => hasContent && toggleNode(node.id)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-2">
                              {hasContent && (
                                <button className="p-0.5">
                                  {isExpanded ? (
                                    <ChevronDownIcon className="w-3.5 h-3.5 text-gray-500" />
                                  ) : (
                                    <ChevronRightIcon className="w-3.5 h-3.5 text-gray-500" />
                                  )}
                                </button>
                              )}
                              {status ? getNodeStatusIcon(status.status) : <ClockIcon className="w-4 h-4 text-gray-400" />}
                              <div>
                                <p className="font-medium text-sm text-gray-900">
                                  {node.data?.label || node.id}
                                </p>
                                <p className="text-xs text-gray-500">
                                  {node.type}
                                </p>
                              </div>
                            </div>
                            {status && (
                              <span className="text-xs text-gray-500">
                                {formatTimestamp(status.timestamp)}
                              </span>
                            )}
                          </div>

                          {/* HITL assignment info when paused */}
                          {status?.status === 'paused' && hitlTask && node.id === hitlTask.node_id && (
                            <div className="mt-1.5 flex items-center justify-between">
                              <div className="flex items-center gap-3 text-xs text-orange-700">
                                <span>Assigned to: <strong>{hitlTask.assigned_to}</strong></span>
                                <span>Since {new Date(hitlTask.paused_at).toLocaleTimeString()}</span>
                              </div>
                              {hitlTask.can_complete && (
                                <button
                                  onClick={(e) => { e.stopPropagation(); setShowHitlReview(true); }}
                                  className="px-3 py-1 text-xs font-medium text-white bg-orange-500 rounded hover:bg-orange-600 transition-colors flex-shrink-0"
                                >
                                  Complete Task
                                </button>
                              )}
                            </div>
                          )}
                        </div>

                        {isExpanded && hasContent && (
                          <div className="border-t border-gray-200 px-3 py-2 space-y-1.5 max-h-48 overflow-y-auto">
                            {/* Show status information even without detailed logs */}
                            {status && !hasLogs && (
                              <div className="text-xs">
                                <div className="flex items-start space-x-2">
                                  <span className="text-gray-400 flex-shrink-0">
                                    {formatTimestamp(status.timestamp)}
                                  </span>
                                  <span className={`${
                                    status.level === 'error' ? 'text-red-600' :
                                    status.level === 'warning' ? 'text-yellow-600' :
                                    'text-gray-700'
                                  }`}>
                                    {status.message}
                                  </span>
                                </div>
                                {status.data && Object.keys(status.data).length > 0 && (
                                  <div className="ml-16 mt-1">
                                    <details className="cursor-pointer">
                                      <summary className="text-blue-600 hover:text-blue-800">
                                        Show data
                                      </summary>
                                      <pre className="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
                                        {JSON.stringify(status.data, null, 2)}
                                      </pre>
                                    </details>
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Show detailed execution logs */}
                            {hasLogs && executionLogs
                              .filter(log => log.step_id === node.id)
                              .map((log, idx) => (
                                <div key={idx} className="text-xs">
                                  <div className="flex items-start space-x-2">
                                    <span className="text-gray-400 flex-shrink-0">
                                      {formatTimestamp(log.timestamp || new Date().toISOString())}
                                    </span>
                                    <span className={`${
                                      log.level === 'error' ? 'text-red-600' :
                                      log.level === 'warning' ? 'text-yellow-600' :
                                      'text-gray-700'
                                    }`}>
                                      {log.message}
                                    </span>
                                  </div>
                                  {log.data && Object.keys(log.data).length > 0 && (
                                    <div className="ml-16 mt-1">
                                      <details className="cursor-pointer">
                                        <summary className="text-blue-600 hover:text-blue-800">
                                          Show data
                                        </summary>
                                        <pre className="mt-1 p-2 bg-gray-100 rounded text-xs overflow-x-auto">
                                          {JSON.stringify(log.data, null, 2)}
                                        </pre>
                                      </details>
                                    </div>
                                  )}
                                </div>
                              ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>

                {(!flow?.flow_definition?.nodes || flow.flow_definition.nodes.length === 0) && (
                  <div className="text-center py-12 text-gray-500">
                    <p className="text-sm">No execution logs available</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
          </>
        )}
      </div>

      {/* HITL Task Review Modal */}
      {showHitlReview && hitlTask && (
        <TaskReviewModal
          task={{
            task_id: hitlTask.task_id,
            title: hitlTask.title,
            task_type: hitlTask.task_type,
            priority: hitlTask.priority,
            flow_name: flow?.flow_name,
            timeout_at: hitlTask.timeout_at,
            assignees: hitlTask.assignees,
            assigned_to: hitlTask.assigned_to,
          }}
          isOpen={true}
          onClose={() => setShowHitlReview(false)}
          onCompleted={() => {
            setShowHitlReview(false);
            // Immediately update UI - flow is resuming after HITL completion
            setHitlTask(null);
            setIsExecuting(true);
            setActiveTab('logs');
            if (hitlTask?.node_id) {
              setNodeStatuses(prev => ({
                ...prev,
                [hitlTask.node_id]: {
                  ...prev[hitlTask.node_id],
                  status: 'completed',
                  message: '✅ Human review completed - flow resuming',
                  timestamp: new Date().toISOString(),
                }
              }));
            }
          }}
          fetchFullTask={true}
        />
      )}
    </div>
  );
});

ManualTriggerModal.displayName = 'ManualTriggerModal';

const ManualTriggerModalWithProvider = React.memo((props) => (
  <ReactFlowProvider>
    <ManualTriggerModal {...props} />
  </ReactFlowProvider>
));
ManualTriggerModalWithProvider.displayName = 'ManualTriggerModalWithProvider';

export default ManualTriggerModalWithProvider;
