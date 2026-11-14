import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
  Panel,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import '../components/flow/nodeStyles.css';
import axios from 'axios';
import { showErrorToast, showSuccessToast, showWarningToast, showInfoToast } from '../utils/customToast';
import { getFullErrorMessage } from '../utils/errorHandler';
import { useUndoRedo } from '../hooks/useUndoRedo';
import { useAuth } from '../contexts/AuthContext';
import { updateNodeIdReferences, validateNodeId, generateUniqueNodeId } from '../utils/nodeIdUtils';
import { useCollaboration } from '../hooks/useCollaboration';
import InviteDialog from '../components/collaboration/InviteDialog';
import ParticipantsList from '../components/collaboration/ParticipantsList';
import CollaborationIndicator from '../components/collaboration/CollaborationIndicator';
import { CollaborativeCursors } from '../components/collaboration/CollaborativeCursor';
import { CollaborativeSelections } from '../components/collaboration/SelectionHighlight';
import { throttle } from 'lodash';
import {
  ArrowLeftIcon,
  PlayIcon,
  CloudArrowUpIcon,
  PlusIcon,
  TrashIcon,
  CogIcon,
  BoltIcon,
  CodeBracketIcon,
  ClockIcon,
  DocumentTextIcon,
  CursorArrowRaysIcon,
  ArrowUpTrayIcon,
  ArrowDownTrayIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  ViewColumnsIcon,
  Squares2X2Icon,
  ArrowUturnLeftIcon,
  ArrowUturnRightIcon,
  DocumentTextIcon as JsonIcon,
  BugAntIcon,
  EllipsisVerticalIcon,
  UsersIcon,
  UserIcon,
  CalendarIcon,
  PencilSquareIcon,
  QuestionMarkCircleIcon,
  HandRaisedIcon,
} from '@heroicons/react/24/outline';
import ManualTriggerConfig from '../components/flow/ManualTriggerConfig';
import LoopConfig from '../components/flow/LoopConfig';
import ParameterForm from '../components/flow/ParameterForm';
import ParameterMapper from '../components/flow/ParameterMapper';
import ParameterInput from '../components/flow/ParameterInput';
import ConditionBuilder from '../components/flow/ConditionBuilder';
import EnhancedTransformCodeEditor from '../components/flow/EnhancedTransformCodeEditor';
import EnhancedJsonEditor from '../components/EnhancedJsonEditor';
import ApplicationServiceSelector from '../components/flow/ApplicationServiceSelector';
import TriggerSelector from '../components/flow/TriggerSelector';
import CronExpressionBuilder from '../components/flow/CronExpressionBuilder';
import FileChangeTriggerConfig from '../components/flow/FileChangeTriggerConfig';
import MqttTriggerConfig, { MqttPerformanceSection } from '../components/flow/MqttTriggerConfig';
import ErrorBoundary from '../components/ErrorBoundary';
import { findOverlappingNodes, findOverlappingEdges, calculateOverlapPercentage } from '../utils/overlapDetection';
import { scheduleToCron, describeSchedule, formatScheduleForBackend } from '../utils/scheduleUtils';
import OverlapIndicator, { OverlapSummary } from '../components/flow/OverlapIndicator';
import ApplicationInstallationWizard from '../components/flows/ApplicationInstallationWizard';
import FlowTutorial from '../components/onboarding/FlowTutorial';

// Custom node components
import TriggerNode from '../components/flow/TriggerNode';
import ActionNode from '../components/flow/ActionNode';
import ConditionNode from '../components/flow/ConditionNode';
import TransformNode from '../components/flow/TransformNode';
import ResponseNode from '../components/flow/ResponseNode';
import LoopNode from '../components/flow/LoopNode';
import HumanInLoopNode from '../components/flow/HumanInLoopNode';
import HumanInLoopConfig from '../components/flow/HumanInLoopConfig';
import WaitForEventNode from '../components/flow/WaitForEventNode';
import WaitForEventConfig from '../components/flow/WaitForEventConfig';
import InvalidNode from '../components/flow/InvalidNode';
import CustomEdge from '../components/flow/CustomEdge';
import NodeErrorHandlingConfig, { ERROR_HANDLE_ID } from '../components/flow/NodeErrorHandlingConfig';

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
  invalid: InvalidNode, // Fallback for invalid/unknown node types
};

// Edge types configuration
const edgeTypes = {
  default: CustomEdge,
};

// Initial nodes for new flows
const initialNodes = [
  {
    id: 'trigger_1',
    type: 'trigger',
    position: { x: 250, y: 50 },
    width: 200,
    height: 100,
    style: {
      width: '200px',
      height: '100px'
    },
    data: { 
      label: 'Trigger',
      triggerType: 'manual',
      manualVariables: [], // Initialize with empty array
      config: {},
      width: 200,
      height: 100
    },
  },
];

const FlowContent = () => {
  const { flowId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const isReadOnlyRole = user?.role === 'FLOW_EXECUTOR' || user?.role === 'EXECUTION_MONITOR';
  const isEditMode = !!flowId;
  const collaborateSessionId = searchParams.get('collaborate');
  const collaborateToken = searchParams.get('token');
  const { fitView } = useReactFlow();

  const [nodes, setNodes, onNodesChangeBase] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChangeBase] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [initialFlowState, setInitialFlowState] = useState(null);
  const [flowName, setFlowName] = useState('');
  const [flowDescription, setFlowDescription] = useState('');
  const [flowCategory, setFlowCategory] = useState('');
  const [flowScope, setFlowScope] = useState('user');  // 'global', 'tenant', 'user'
  const [skipNextHistoryPush, setSkipNextHistoryPush] = useState(false);
  const [editingNodeId, setEditingNodeId] = useState(null);
  const [tempNodeId, setTempNodeId] = useState('');
  const [validationErrors, setValidationErrors] = useState({});
  const [isValidating, setIsValidating] = useState(false);
  const [nodeOverlaps, setNodeOverlaps] = useState({});
  const [edgeOverlaps, setEdgeOverlaps] = useState({});
  const [showOverlapIndicators, setShowOverlapIndicators] = useState(true);

  // Application installation wizard state
  const [wizardOpen, setWizardOpen] = useState(false);
  const [validationData, setValidationData] = useState(null);
  const [pendingImportData, setPendingImportData] = useState(null);

  // Tutorial state
  const [runTutorial, setRunTutorial] = useState(false);

  // Check if user should see tutorial on mount (first-time users with no flows)
  useEffect(() => {
    const hasSeenTutorial = localStorage.getItem('ioflow_flow_tutorial_completed');
    // Only show tutorial for new flows (not editing) and first-time users
    if (!isEditMode && !hasSeenTutorial && nodes.length === 1) {
      // Give a slight delay so the UI is ready
      setTimeout(() => setRunTutorial(true), 1000);
    }
  }, []); // Only run once on mount

  const handleTutorialComplete = () => {
    setRunTutorial(false);
    localStorage.setItem('ioflow_flow_tutorial_completed', 'true');
  };

  const startTutorial = () => {
    setRunTutorial(true);
  };

  // Add keyboard shortcut for tutorial (? key)
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Shift+? or just ? key to show tutorial
      if (e.key === '?' && !e.ctrlKey && !e.altKey && !e.metaKey) {
        // Don't trigger if user is typing in an input field
        const target = e.target;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
          return;
        }
        e.preventDefault();
        startTutorial();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  // Initialize undo/redo with current flow state
  const {
    state: historyState,
    setState: pushToHistory,
    undo: undoAction,
    redo: redoAction,
    canUndo,
    canRedo,
    reset: resetHistory,
  } = useUndoRedo({
    nodes: initialNodes,
    edges: [],
    flowName: '',
    flowDescription: '',
    flowCategory: '',
  });
  
  // Push current state to history (debounced to avoid too many history entries)
  const pushStateToHistory = useCallback(() => {
    if (skipNextHistoryPush) {
      setSkipNextHistoryPush(false);
      return;
    }
    
    const currentState = {
      nodes: nodes,
      edges: edges,
      flowName: flowName,
      flowDescription: flowDescription,
      flowCategory: flowCategory,
    };
    
    pushToHistory(currentState);
  }, [nodes, edges, flowName, flowDescription, flowCategory, pushToHistory, skipNextHistoryPush]);
  
  // Debounced push to history
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      pushStateToHistory();
    }, 500); // 500ms debounce
    
    return () => clearTimeout(timeoutId);
  }, [nodes, edges, flowName, flowDescription, flowCategory]);
  
  // Detect overlapping nodes and edges
  useEffect(() => {
    if (!showOverlapIndicators) return;
    
    const detectOverlaps = () => {
      // Detect node overlaps
      const nodeOverlapMap = findOverlappingNodes(nodes);
      setNodeOverlaps(nodeOverlapMap);
      
      // For edge overlap detection, we'd need edge path data
      // This would typically come from the ReactFlow internals
      // For now, we'll skip edge overlap detection
      // const edgeOverlapMap = findOverlappingEdges(edges);
      // setEdgeOverlaps(edgeOverlapMap);
    };
    
    // Use a small delay to ensure nodes have their dimensions
    const timeoutId = setTimeout(detectOverlaps, 100);
    
    return () => clearTimeout(timeoutId);
  }, [nodes, edges, showOverlapIndicators]);
  
  // Handle undo
  const undo = useCallback(() => {
    setSkipNextHistoryPush(true);
    undoAction();
  }, [undoAction]);
  
  // Handle redo
  const redo = useCallback(() => {
    setSkipNextHistoryPush(true);
    redoAction();
  }, [redoAction]);
  
  // Apply history state when it changes
  useEffect(() => {
    if (historyState) {
      setNodes(historyState.nodes || []);
      setEdges(historyState.edges || []);
      setFlowName(historyState.flowName || '');
      setFlowDescription(historyState.flowDescription || '');
      setFlowCategory(historyState.flowCategory || '');
    }
  }, [historyState, setNodes, setEdges]);
  const [showNodePanel, setShowNodePanel] = useState(false);
  const [showPropertiesPanel, setShowPropertiesPanel] = useState(false);
  const [propertiesPanelMode, setPropertiesPanelMode] = useState(() => {
    // Load preference from localStorage - 'right', 'center', or 'fullscreen'
    return localStorage.getItem('propertiesPanelMode') || 'right';
  });
  const [selectedAppServices, setSelectedAppServices] = useState([]);
  const [loadingServices, setLoadingServices] = useState(false);
  const [appSubscription, setAppSubscription] = useState(null);
  const [selectedAppEvents, setSelectedAppEvents] = useState([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [flowStatus, setFlowStatus] = useState('draft');
  const [isSynchronous, setIsSynchronous] = useState(false);
  const [syncTimeout, setSyncTimeout] = useState(30);
  // Flow-level execution logging (stored in flow_definition.settings — applies to ALL trigger types)
  const [executionLogLevel, setExecutionLogLevel] = useState('full');
  const [logSampleRate, setLogSampleRate] = useState(1.0);
  // Flow started when this flow fails with an unhandled error
  const [errorHandlerFlowId, setErrorHandlerFlowId] = useState('');

  // Candidate error handler flows (every other flow the user can see)
  const { data: errorHandlerFlowOptions = [], isError: errorHandlerFlowsFailed } = useQuery({
    queryKey: ['flows', 'error-handler-options'],
    queryFn: async () => {
      const response = await axios.get('/api/v1/flows/', { params: { include_user_info: false } });
      return Array.isArray(response.data) ? response.data : [];
    },
    staleTime: 60_000,
  });
  const [showJsonEditor, setShowJsonEditor] = useState(false);
  const [viewSourceData, setViewSourceData] = useState(null);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  
  // Collaboration state
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [showParticipantsList, setShowParticipantsList] = useState(false);
  const [collaborationSession, setCollaborationSession] = useState(null);
  const flowCanvasRef = useRef(null);
  
  // Initialize collaboration hook
  const {
    isCollaborating,
    isConnected,
    sessionInfo,
    participants,
    chatMessages,
    error: collaborationError,
    startCollaboration,
    joinCollaboration,
    endCollaboration,
    sendOperation,
    sendCursorPosition,
    sendSelectionChange,
    sendChatMessage
  } = useCollaboration(flowId, {
    enabled: isEditMode || !!collaborateSessionId,
    onOperation: (event) => {
      // Handle incoming operations from other participants
      if (event.operation_type === 'node_add') {
        setNodes(prev => [...prev, event.node_data]);
      } else if (event.operation_type === 'node_update') {
        setNodes(prev => prev.map(n => 
          n.id === event.node_id ? { ...n, ...event.updates } : n
        ));
      } else if (event.operation_type === 'node_delete') {
        setNodes(prev => prev.filter(n => n.id !== event.node_id));
      } else if (event.operation_type === 'edge_add') {
        setEdges(prev => {
          // Check if edge already exists to avoid duplicates
          const exists = prev.some(e => e.id === event.edge_data.id);
          if (exists) {
            return prev;
          }
          return [...prev, event.edge_data];
        });
      } else if (event.operation_type === 'edge_delete') {
        // Always apply edge deletion from collaborators, even if it might cause validation issues
        // This ensures all collaborators stay in sync
        setEdges(prev => prev.filter(e => e.id !== event.edge_id));
      } else if (event.operation_type === 'node_position') {
        setNodes(prev => prev.map(n => 
          n.id === event.node_id ? { ...n, position: event.position } : n
        ));
      } else if (event.operation_type === 'node_dimensions') {
        setNodes(prev => prev.map(n => {
          if (n.id === event.node_id) {
            const newWidth = event.dimensions.width;
            const newHeight = event.dimensions.height;
            return {
              ...n,
              width: newWidth,
              height: newHeight,
              style: {
                ...n.style,
                width: `${newWidth}px`,
                height: `${newHeight}px`
              },
              data: {
                ...n.data,
                width: newWidth,
                height: newHeight
              }
            };
          }
          return n;
        }));
      }
    },
    onParticipantJoined: (participant) => {
      showInfoToast(`${participant.display_name} joined the session`);
    },
    onParticipantLeft: (participant) => {
      showInfoToast(`${participant.display_name} left the session`);
    }
  });

  // Create a safe wrapper for sendOperation
  const safeSendOperation = useCallback((operation) => {
    if (isCollaborating && sendOperation && typeof sendOperation === 'function') {
      sendOperation(operation);
    }
  }, [isCollaborating, sendOperation]);

  // Custom handler for edge changes with collaboration support
  const onEdgesChange = useCallback((changes) => {
    // Send collaboration operations for edge changes FIRST
    // This ensures the operation is transmitted even if local validation fails
    if (isCollaborating) {
      changes.forEach(change => {
        if (change.type === 'remove') {
          // Send edge deletion to collaborators immediately
          safeSendOperation({
            operation_type: 'edge_delete',
            edge_id: change.id
          });
        }
      });
    }
    
    // Then apply changes locally
    // Always allow the change to go through for collaboration consistency
    onEdgesChangeBase(changes);
  }, [onEdgesChangeBase, isCollaborating, safeSendOperation]);
  
  // Remove a node's error-branch edges (its error handle disappears when the
  // node stops routing errors to a branch)
  const removeErrorEdges = useCallback((nodeId) => {
    const changes = edges
      .filter(e => e.source === nodeId && e.sourceHandle === ERROR_HANDLE_ID)
      .map(e => ({ type: 'remove', id: e.id }));
    if (changes.length > 0) {
      onEdgesChange(changes);
    }
  }, [edges, onEdgesChange]);

  // Throttled position sender to avoid flooding with position updates
  const throttledPositionSender = useMemo(
    () => throttle((nodeId, position, safeSendOperation) => {
      safeSendOperation({
        operation_type: 'node_position',
        node_id: nodeId,
        position: position
      });
    }, 100), // Send position updates at most every 100ms
    []
  );
  
  // Custom handler to preserve dimensions during node changes
  const onNodesChange = useCallback((changes) => {
    // Update nodes with dimension and position preservation
    setNodes((nds) => {
      const updatedNodes = [...nds];
      
      changes.forEach((change) => {
        if (change.type === 'dimensions' && change.dimensions) {
          // Find the node and update its dimensions
          const nodeIndex = updatedNodes.findIndex(n => n.id === change.id);
          if (nodeIndex !== -1) {
            const node = updatedNodes[nodeIndex];
            const newWidth = Math.round(change.dimensions.width);
            const newHeight = Math.round(change.dimensions.height);
            
            updatedNodes[nodeIndex] = {
              ...node,
              width: newWidth,
              height: newHeight,
              style: {
                ...node.style,
                width: `${newWidth}px`,
                height: `${newHeight}px`
              },
              data: {
                ...node.data,
                width: newWidth,
                height: newHeight
              }
            };
          }
        } else if (change.type === 'position' && change.position) {
          // Update position for both dragging and final position
          const nodeIndex = updatedNodes.findIndex(n => n.id === change.id);
          if (nodeIndex !== -1) {
            updatedNodes[nodeIndex] = {
              ...updatedNodes[nodeIndex],
              position: change.position
            };
          }
        }
      });
      
      return updatedNodes;
    });
    
    // Send collaboration operations for relevant changes
    if (isCollaborating) {
      changes.forEach(change => {
        if (change.type === 'position' && change.position) {
          // Use throttled sender for position updates during dragging
          if (change.dragging) {
            throttledPositionSender(change.id, change.position, safeSendOperation);
          } else {
            // Send final position immediately when dragging ends
            safeSendOperation({
              operation_type: 'node_position',
              node_id: change.id,
              position: change.position
            });
          }
        } else if (change.type === 'dimensions' && change.dimensions && !change.resizing) {
          // Send dimension update when resizing ends
          safeSendOperation({
            operation_type: 'node_dimensions',
            node_id: change.id,
            dimensions: {
              width: Math.round(change.dimensions.width),
              height: Math.round(change.dimensions.height)
            }
          });
        } else if (change.type === 'remove') {
          // Send node deletion
          safeSendOperation({
            operation_type: 'node_delete',
            node_id: change.id
          });
        }
      });
    }
    
    // Apply other changes normally (for other change types)
    const otherChanges = changes.filter(change => 
      change.type !== 'dimensions' && change.type !== 'position'
    );
    if (otherChanges.length > 0) {
      onNodesChangeBase(otherChanges);
    }
  }, [setNodes, onNodesChangeBase, isCollaborating, safeSendOperation, throttledPositionSender]);

  // Auto-join collaboration if URL params are present
  useEffect(() => {
    if (collaborateSessionId && collaborateToken && !isCollaborating) {
      joinCollaboration(collaborateSessionId, collaborateToken)
        .then(() => {
          showSuccessToast('Joined collaboration session');
        })
        .catch((err) => {
          console.error('Failed to join collaboration:', err);
          showErrorToast('Failed to join collaboration session');
        });
    }
  }, [collaborateSessionId, collaborateToken, joinCollaboration, isCollaborating]);

  // Fetch existing flow data if in edit mode
  const { data: flowData, isLoading } = useQuery({
    queryKey: ['flow', flowId],
    queryFn: async () => {
      const response = await axios.get(`/api/v1/flows/${flowId}`);
      return response.data;
    },
    enabled: isEditMode,
  });

  // Fetch available applications for action nodes
  const { data: applications = [], error: applicationsError } = useQuery({
    queryKey: ['applications'],
    queryFn: async () => {
      const response = await axios.get('/api/v1/applications/');
      return response.data;
    },
    onError: (error) => {
      console.error('Failed to fetch applications:', error);
    }
  });
  
  // Log applications error if any
  if (applicationsError) {
    console.error('Applications query error:', applicationsError);
  }

  // Fetch events for selected application
  const fetchAppEvents = useCallback(async (appId) => {
    if (!appId) {
      setSelectedAppEvents([]);
      return [];
    }
    
    setLoadingEvents(true);
    try {
      const response = await axios.get(`/api/v1/applications/${appId}/events`);
      setSelectedAppEvents(response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch events:', error);
      setSelectedAppEvents([]);
      return [];
    } finally {
      setLoadingEvents(false);
    }
  }, []);

  // Load flow data when fetched
  useEffect(() => {
    if (flowData) {
      console.log('Loading flow data:', flowData);
      console.log('Trigger config from API:', flowData.trigger_config);
      
      setFlowName(flowData.flow_name);
      setFlowDescription(flowData.description || '');
      setFlowCategory(flowData.category || '');
      setFlowScope(flowData.flow_scope || 'user');
      setFlowStatus(flowData.status || 'draft');
      setIsSynchronous(flowData.is_synchronous || false);
      setSyncTimeout(flowData.sync_timeout || 30);
      const flowSettings = flowData.flow_definition?.settings || {};
      setExecutionLogLevel(flowSettings.execution_log_level || 'full');
      setLogSampleRate(flowSettings.flow_log_sample_rate !== undefined ? flowSettings.flow_log_sample_rate : 1.0);
      setErrorHandlerFlowId(flowSettings.error_handler_flow_id || '');

      // Store initial state for change detection (we'll update nodes after processing)
      const initialState = {
        flowName: flowData.flow_name,
        flowDescription: flowData.description || '',
        isSynchronous: flowData.is_synchronous || false,
        syncTimeout: flowData.sync_timeout || 30,
        nodes: [], // Will be set after processing
        edges: flowData.flow_definition?.edges || [],
        loadTime: Date.now(),
      };
      
      if (flowData.flow_definition) {
        // Convert backend 'event' type to frontend 'application_event' type
        const nodes = flowData.flow_definition.nodes || initialNodes;
        const updatedNodes = nodes.map(node => {
          // Get dimensions from node or data
          const width = node.data?.width || node.width || 200;
          const height = node.data?.height || node.height || 100;
          
          // Process parameterMapping to handle nested structure from imports
          let processedData = { ...node.data };

          // Update label for condition nodes based on expression complexity
          if (node.type === 'condition' && processedData.expression) {
            const isComplexExpression = !canUseVisualBuilderForExpression(processedData.expression);
            if (isComplexExpression) {
              processedData.label = 'Advanced Expression';
            } else {
              processedData.label = processedData.label || 'Condition';
            }
          }

          if (processedData.parameterMapping) {
            const processedMapping = {};
            Object.entries(processedData.parameterMapping).forEach(([key, value]) => {
              // Check if value is an object with source and value properties (import format)
              if (value && typeof value === 'object' && 'source' in value && 'value' in value) {
                // Keep the nested structure for proper handling by ParameterMapper
                processedMapping[key] = value;
              } else if (value && typeof value === 'object' && 'value' in value && !('source' in value)) {
                // Handle case where there's only 'value' property without 'source'
                // Keep the nested structure for proper handling by ParameterMapper
                processedMapping[key] = value;
              } else {
                // Use the value as-is for normal mappings
                processedMapping[key] = value;
              }
            });
            processedData.parameterMapping = processedMapping;
          }
          
          // Use style property to enforce dimensions and prevent auto-sizing
          const nodeWithDimensions = {
            ...node,
            width: width,
            height: height,
            style: {
              width: `${width}px`,
              height: `${height}px`
            },
            data: {
              ...processedData,
              width: width,
              height: height
              // No need to preserve instance info - we get it from applications table
            }
          };
          
          if (node.type === 'trigger') {
            // Get trigger config from flow data
            const triggerConfig = flowData.trigger_config || {};
            
            // Convert backend 'event' type to frontend 'application_event' type
            let triggerType = node.data.triggerType;
            if (triggerType === 'event') {
              triggerType = 'application_event';
            }
            
            // Migrate chat_text to message for chat_input triggers
            let manualVars = triggerConfig.manual_variables || [];
            if (triggerType === 'chat_input' && manualVars.length > 0) {
              manualVars = manualVars.map(v => {
                if (v.name === 'chat_text' || v.id === 'chat_text') {
                  return { ...v, id: 'message', name: 'message' };
                }
                return v;
              });
            }
            // Set default message variable if chat_input has no variables
            if (triggerType === 'chat_input' && manualVars.length === 0) {
              manualVars = [{
                id: 'message',
                name: 'message',
                dataType: 'string',
                description: "The user's chat message",
                required: true,
                defaultValue: '',
                uiControl: 'textarea'
              }];
            }

            return {
              ...nodeWithDimensions,
              data: {
                ...nodeWithDimensions.data,
                triggerType: triggerType,
                // Load manual_variables from trigger_config
                manualVariables: manualVars,
                // Also preserve other trigger config data
                appId: triggerConfig.app_id || node.data.appId,
                eventId: triggerConfig.event_id || node.data.eventId,
                eventName: triggerConfig.event_name || node.data.eventName,
                schedule: triggerConfig.schedule?.cron_expression || triggerConfig.schedule || node.data.schedule,
                executeImmediately: triggerConfig.execute_immediately !== undefined ? triggerConfig.execute_immediately : true,
                // Load file_change trigger config
                folderPath: triggerConfig.folder_path || node.data.folderPath,
                listenerType: triggerConfig.listener_type || node.data.listenerType,
                filePattern: triggerConfig.file_pattern || node.data.filePattern,
                recursive: triggerConfig.recursive || node.data.recursive,
                debounceSeconds: triggerConfig.debounce_seconds || node.data.debounceSeconds,
                // Load mqtt trigger config
                mqttHost: triggerConfig.mqtt_host || node.data.mqttHost,
                mqttPort: triggerConfig.mqtt_port || node.data.mqttPort,
                mqttTls: triggerConfig.mqtt_tls !== undefined ? triggerConfig.mqtt_tls : node.data.mqttTls,
                mqttUsername: triggerConfig.mqtt_username || node.data.mqttUsername,
                mqttPassword: triggerConfig.mqtt_password || node.data.mqttPassword,
                mqttClientId: triggerConfig.mqtt_client_id || node.data.mqttClientId,
                mqttTopicFilter: triggerConfig.mqtt_topic_filter || node.data.mqttTopicFilter,
                mqttQos: triggerConfig.mqtt_qos !== undefined ? triggerConfig.mqtt_qos : node.data.mqttQos,
                mqttPayloadFormat: triggerConfig.mqtt_payload_format || node.data.mqttPayloadFormat,
                // Load mqtt Performance & Delivery config
                mqttBatchSize: triggerConfig.mqtt_batch_size !== undefined ? triggerConfig.mqtt_batch_size : node.data.mqttBatchSize,
                mqttBatchWindowSeconds: triggerConfig.mqtt_batch_window_seconds !== undefined ? triggerConfig.mqtt_batch_window_seconds : node.data.mqttBatchWindowSeconds,
                mqttMaxRate: triggerConfig.mqtt_max_rate !== undefined ? triggerConfig.mqtt_max_rate : node.data.mqttMaxRate,
                mqttRateOverflow: triggerConfig.mqtt_rate_overflow || node.data.mqttRateOverflow,
                mqttMaxConcurrent: triggerConfig.mqtt_max_concurrent !== undefined ? triggerConfig.mqtt_max_concurrent : node.data.mqttMaxConcurrent,
                mqttDedup: triggerConfig.mqtt_dedup || node.data.mqttDedup,
                mqttDedupKey: triggerConfig.mqtt_dedup_key !== undefined ? triggerConfig.mqtt_dedup_key : node.data.mqttDedupKey,
                mqttDedupWindowSeconds: triggerConfig.mqtt_dedup_window_seconds !== undefined ? triggerConfig.mqtt_dedup_window_seconds : node.data.mqttDedupWindowSeconds,
                // Restore event trigger kind for MQTT-backed events (older/imported flows don't persist it in node data)
                eventTriggerKind: node.data.eventTriggerKind ||
                  (triggerType === 'application_event' && triggerConfig.mqtt_topic_filter ? 'mqtt' : node.data.eventTriggerKind),
                // Load chat_input trigger config
                placeholderText: triggerConfig.placeholder_text || node.data.placeholderText,
                welcomeMessage: triggerConfig.welcome_message || node.data.welcomeMessage,
                sessionTimeoutMinutes: triggerConfig.session_timeout_minutes || node.data.sessionTimeoutMinutes,
              }
            };
          }
          return nodeWithDimensions;
        });
        
        setNodes(updatedNodes);
        
        // Load edges with arrow markers and deduplicate
        const loadedEdges = (flowData.flow_definition.edges || []).map(edge => ({
          ...edge,
          markerEnd: {
            type: MarkerType.ArrowClosed,
          },
        }));
        
        // Deduplicate edges based on exact matches (including handles)
        const deduplicatedEdges = loadedEdges.reduce((acc, edge) => {
          // Check if this exact edge already exists
          const isDuplicate = acc.some(e => 
            e.source === edge.source && 
            e.target === edge.target &&
            e.sourceHandle === edge.sourceHandle &&
            e.targetHandle === edge.targetHandle
          );
          
          if (!isDuplicate) {
            acc.push(edge);
          }
          return acc;
        }, []);
        
        setEdges(deduplicatedEdges);
        
        // Update initial state with processed nodes and edges
        initialState.nodes = updatedNodes;
        initialState.edges = deduplicatedEdges;
        setInitialFlowState(initialState);
        setHasUnsavedChanges(false);
        
        // Reset undo/redo history with loaded state
        resetHistory({
          nodes: updatedNodes,
          edges: deduplicatedEdges,
          flowName: flowData.flow_name,
          flowDescription: flowData.description || '',
        });
        
        // If there's an application event trigger, load the events for that app
        const triggerNode = updatedNodes.find(n => n.type === 'trigger');
        if (triggerNode?.data?.appId && triggerNode?.data?.triggerType === 'application_event') {
          fetchAppEvents(triggerNode.data.appId).then((events) => {
            // After events are loaded, check if we should update sync mode
            if (triggerNode.data.eventId && events) {
              const event = events.find(e => e.event_id === triggerNode.data.eventId);
              if (event?.sync_mode === 'synchronous' && !flowData.is_synchronous) {
                // Event requires synchronous but flow is not synchronous
                setIsSynchronous(true);
                showInfoToast('Flow set to synchronous mode based on event configuration');
              } else if (event?.sync_mode === 'asynchronous' && flowData.is_synchronous) {
                // Event requires asynchronous but flow is synchronous
                setIsSynchronous(false);
                showInfoToast('Flow set to asynchronous mode based on event configuration');
              }
            }
          });
        }
      }
    }
  }, [flowData, setNodes, setEdges, fetchAppEvents]);
  
  // Fit view when flow loads
  useEffect(() => {
    if (flowData && nodes.length > 0) {
      // Small delay to ensure DOM is ready
      const timer = setTimeout(() => {
        fitView({
          padding: 0.2,
          includeHiddenNodes: false,
          minZoom: 0.5,
          maxZoom: 1.5,
        });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [flowData, nodes.length, fitView]);
  
  // Update node display names when applications are loaded - use app_name directly
  useEffect(() => {
    if (applications.length > 0 && nodes.length > 0) {
      // Update nodes that have appId to use the app_name from applications table
      const updatedNodes = nodes.map(node => {
        if (node.data?.appId && (node.type === 'action' || node.type === 'trigger')) {
          const app = applications.find(a => a.app_id === node.data.appId);
          if (app) {
            // Simply use app_name - it contains the instance name for instances
            const displayName = app.app_name;
            
            // Only update if display name changed
            if (displayName !== node.data.appName) {
              return {
                ...node,
                data: {
                  ...node.data,
                  appName: displayName,
                  appIcon: app.icon_url || app.app_icon || node.data.appIcon,
                  appType: app.app_type || node.data.appType,
                  appCategory: app.category || node.data.appCategory
                }
              };
            }
          }
        }
        return node;
      });
      
      // Only update if any nodes changed
      if (updatedNodes.some((node, index) => node !== nodes[index])) {
        setNodes(updatedNodes);
      }
    }
  }, [applications, nodes.length]); // Depend on nodes.length instead of nodes to avoid infinite loop
  
  // Update selected node when nodes change
  useEffect(() => {
    if (selectedNode) {
      const updatedNode = nodes.find(n => n.id === selectedNode.id);
      if (updatedNode && updatedNode !== selectedNode) {
        setSelectedNode(updatedNode);
      }
    }
  }, [nodes, selectedNode]);

  // Fetch services for all action nodes when flow loads to populate serviceDisplayName
  useEffect(() => {
    const fetchServicesForNodes = async () => {
      if (!flowData || nodes.length === 0) return;
      
      console.log('=== Fetching services for loaded flow nodes ===');
      console.log('Total nodes:', nodes.length);
      
      // Find all unique app IDs from action nodes
      const appIds = new Set();
      const nodeServiceInfo = [];
      nodes.forEach(node => {
        if (node.type === 'action' && node.data?.appId) {
          appIds.add(node.data.appId);
          nodeServiceInfo.push({
            nodeId: node.id,
            appId: node.data.appId,
            serviceId: node.data.serviceId,
            service: node.data.service,
            serviceDisplayName: node.data.serviceDisplayName
          });
        }
      });
      
      console.log('Action nodes with services:', nodeServiceInfo);
      
      if (appIds.size === 0) return;
      
      // Fetch services for each unique app
      const servicesMap = {};
      for (const appId of appIds) {
        try {
          const response = await axios.get(`/api/v1/applications/${appId}/services`);
          servicesMap[appId] = response.data;
          console.log(`Services for app ${appId}:`, response.data);
        } catch (error) {
          console.error(`Failed to fetch services for app ${appId}:`, error);
          servicesMap[appId] = [];
        }
      }
      
      // Update nodes with service display names
      const updatedNodes = nodes.map(node => {
        if (node.type === 'action' && node.data?.appId && node.data?.serviceId) {
          const services = servicesMap[node.data.appId] || [];
          const service = services.find(s => s.service_id === node.data.serviceId);
          
          console.log(`Node ${node.id}: Looking for serviceId ${node.data.serviceId}`);
          console.log(`  Found service:`, service);
          
          if (service && !node.data.serviceDisplayName) {
            console.log(`  Updating node ${node.id} with service display name: ${service.display_name}`);
            return {
              ...node,
              data: {
                ...node.data,
                service: service.service_name,  // Actual service name for backend
                serviceDisplayName: service.display_name,  // Display name for UI
                serviceName: service.display_name  // Also set serviceName for backward compatibility
              }
            };
          }
        }
        return node;
      });
      
      // Only update if any nodes changed
      if (updatedNodes.some((node, index) => node !== nodes[index])) {
        console.log('Updating nodes with service display names');
        setNodes(updatedNodes);
      } else {
        console.log('No nodes needed updating');
      }
    };
    
    fetchServicesForNodes();
  }, [flowData]); // Only run when flowData changes (i.e., when flow is loaded)

  // Check for unsaved changes
  const checkForChanges = useCallback(() => {
    // For new flows, check if any data has been entered
    if (!initialFlowState && !isEditMode) {
      return flowName !== '' || 
             flowDescription !== '' || 
             nodes.length > 1 || 
             edges.length > 0 ||
             isSynchronous !== false ||
             syncTimeout !== 30;
    }
    
    if (!initialFlowState) return false;
    
    // Check basic properties first
    if (flowName !== initialFlowState.flowName ||
        flowDescription !== initialFlowState.flowDescription ||
        isSynchronous !== initialFlowState.isSynchronous ||
        syncTimeout !== initialFlowState.syncTimeout) {
      return true;
    }
    
    // Check edges (excluding markerEnd which might be added by ReactFlow)
    const normalizeEdges = (edgeList) => {
      return edgeList.map(edge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        type: edge.type
      }));
    };
    
    if (JSON.stringify(normalizeEdges(edges)) !== JSON.stringify(normalizeEdges(initialFlowState.edges))) {
      return true;
    }
    
    // Check nodes (excluding position and other ReactFlow internal properties)
    if (nodes.length !== initialFlowState.nodes.length) {
      return true;
    }
    
    // Compare nodes excluding position and ReactFlow internal properties
    for (let i = 0; i < nodes.length; i++) {
      const currentNode = nodes[i];
      const initialNode = initialFlowState.nodes.find(n => n.id === currentNode.id);
      
      if (!initialNode) {
        return true;
      }
      
      // Compare only the properties we care about
      const currentData = JSON.stringify(currentNode.data);
      const initialData = JSON.stringify(initialNode.data);
      
      if (currentData !== initialData ||
          currentNode.type !== initialNode.type ||
          currentNode.id !== initialNode.id) {
        return true;
      }
    }
    
    return false;
  }, [flowName, flowDescription, isSynchronous, syncTimeout, nodes, edges, initialFlowState, isEditMode]);

  // Track changes
  useEffect(() => {
    // Skip change detection for the first 500ms after initial state is set
    // to avoid false positives from ReactFlow initialization
    if (initialFlowState && Date.now() - (initialFlowState.loadTime || 0) < 500) {
      return;
    }
    
    const hasChanges = checkForChanges();
    setHasUnsavedChanges(hasChanges);
  }, [flowName, flowDescription, isSynchronous, syncTimeout, nodes, edges, checkForChanges, initialFlowState]);

  // Navigation guard for unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      // Send leave request synchronously for better reliability
      if (isCollaborating) {
        // Use sendBeacon for more reliable cleanup on page unload
        const token = localStorage.getItem('access_token');
        if (sessionInfo?.session_id) {
          const data = JSON.stringify({
            participant_id: sessionInfo.participant_id
          });
          navigator.sendBeacon(
            `/api/v1/collaborate/session/${sessionInfo.session_id}/leave`,
            new Blob([data], { type: 'application/json' })
          );
        }
      }
      
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
      }
    };

    const handleUnload = () => {
      // Additional cleanup on actual unload
      if (isCollaborating && sessionInfo?.session_id) {
        const token = localStorage.getItem('access_token');
        const data = JSON.stringify({
          participant_id: sessionInfo.participant_id
        });
        navigator.sendBeacon(
          `/api/v1/collaborate/session/${sessionInfo.session_id}/leave`,
          new Blob([data], { type: 'application/json' })
        );
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    window.addEventListener('unload', handleUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      window.removeEventListener('unload', handleUnload);
    };
  }, [hasUnsavedChanges, isCollaborating, sessionInfo]);

  // Handle page visibility changes separately to avoid cleanup issues
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && isCollaborating) {
        // Send a "going inactive" status update
        if (sendOperation && typeof sendOperation === 'function') {
          sendOperation({
            operation_type: 'status_update',
            status: 'inactive'
          });
        }
      } else if (!document.hidden && isCollaborating) {
        // Send an "active" status update
        if (sendOperation && typeof sendOperation === 'function') {
          sendOperation({
            operation_type: 'status_update', 
            status: 'active'
          });
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [isCollaborating, sendOperation]);

  // Use a ref to track collaboration state for cleanup
  const collaborationRef = useRef();
  collaborationRef.current = { isCollaborating, endCollaboration };
  
  // Cleanup collaboration only on actual component unmount
  useEffect(() => {
    return () => {
      // This cleanup only runs when component actually unmounts
      const { isCollaborating: isCollab, endCollaboration: endCollab } = collaborationRef.current || {};
      if (isCollab && endCollab) {
        endCollab().catch(err => {
          console.error('Failed to end collaboration on unmount:', err);
        });
      }
    };
  }, []); // Empty dependency array - only runs on mount/unmount

  // Handle navigation with unsaved changes
  const handleNavigation = useCallback(async (path) => {
    if (hasUnsavedChanges) {
      const confirmLeave = window.confirm('You have unsaved changes. Are you sure you want to leave?');
      if (!confirmLeave) {
        return;
      }
    }
    // End collaboration before navigating away
    if (isCollaborating) {
      try {
        await endCollaboration();
      } catch (err) {
        console.error('Failed to end collaboration before navigation:', err);
      }
    }
    navigate(path);
  }, [hasUnsavedChanges, navigate, isCollaborating, endCollaboration]);

  // Validate flow when structure changes (for synchronous flows)
  useEffect(() => {
    if (isSynchronous && isEditMode && flowId) {
      // Debounce validation to avoid too many API calls
      const timeoutId = setTimeout(() => {
        validateSynchronousFlow();
      }, 500);
      
      return () => clearTimeout(timeoutId);
    }
  }, [nodes, edges, isSynchronous, isEditMode, flowId]);

  // Save flow mutation
  const saveFlowMutation = useMutation({
    mutationFn: async (data) => {
      if (isEditMode) {
        return axios.put(`/api/v1/flows/${flowId}`, data);
      } else {
        return axios.post('/api/v1/flows/', data);
      }
    },
    onSuccess: (response) => {
      // Update initial state after successful save
      const savedData = response.data;
      const newInitialState = {
        flowName: savedData.flow_name,
        flowDescription: savedData.description || '',
        isSynchronous: savedData.is_synchronous || false,
        syncTimeout: savedData.sync_timeout || 30,
        nodes: nodes,
        edges: edges,
      };
      setInitialFlowState(newInitialState);
      setHasUnsavedChanges(false);

      // Show success message with link to go back to flows list
      const successMessage = `Flow ${isEditMode ? 'updated' : 'created'} successfully!`;

      // Always show link to go back to flows list
      showSuccessToast(
        <div>
          {successMessage}
          <br />
          <a
            href="/flows"
            className="underline text-white hover:text-gray-200 mt-1 inline-block"
            onClick={(e) => {
              e.preventDefault();
              navigate('/flows');
            }}
          >
            Go back to flows list
          </a>
        </div>
      );

      // If creating a new flow, navigate to the edit URL with the new flow ID
      if (!isEditMode && savedData.flow_id) {
        // Navigate to the flow designer with the new flow ID
        navigate(`/flow-designer/${savedData.flow_id}`, { replace: true });
      }
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to save flow');
      showErrorToast(errorMessage);
    },
  });

  // Test flow mutation

  // Update flow status mutation
  const updateFlowStatusMutation = useMutation({
    mutationFn: async (newStatus) => {
      const response = await axios.put(`/api/v1/flows/${flowId}`, { status: newStatus });
      return response.data;
    },
    onSuccess: (data, newStatus) => {
      setFlowStatus(newStatus);
      showSuccessToast(`Flow ${newStatus === 'active' ? 'activated' : newStatus === 'inactive' ? 'deactivated' : 'set to draft'} successfully`);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to update flow status');
      showErrorToast(errorMessage);
    },
  });

  // Manual trigger mutation
  const manualTriggerMutation = useMutation({
    mutationFn: async (variables) => {
      return axios.post(`/api/v1/flows/${flowId}/execute`, {
        trigger_type: 'manual',
        variables: variables
      });
    },
    onSuccess: (response) => {
      showSuccessToast('Flow execution started!');
      // Navigate to executions page to see the results
      navigate(`/executions?flow_id=${flowId}`);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to execute flow');
      showErrorToast(errorMessage);
    },
  });

  // Fetch services for selected application
  const fetchAppServices = useCallback(async (appId) => {
    if (!appId) {
      setSelectedAppServices([]);
      setAppSubscription(null);
      return [];
    }
    
    setLoadingServices(true);
    try {
      // Fetch both services and subscription in parallel
      const [servicesResponse, subscriptionsResponse] = await Promise.all([
        axios.get(`/api/v1/applications/${appId}/services`),
        axios.get(`/api/v1/applications/subscriptions/`)
      ]);
      
      console.log('Services fetched for app', appId, ':', servicesResponse.data);
      setSelectedAppServices(servicesResponse.data);
      
      // Find subscription for this app
      const subscriptions = subscriptionsResponse.data;
      const appSub = subscriptions.find(sub => sub.app_id === appId);
      setAppSubscription(appSub);
      
      return servicesResponse.data; // Return services for use in other functions
    } catch (error) {
      console.error('Failed to fetch services:', error);
      setSelectedAppServices([]);
      setAppSubscription(null);
      return [];
    } finally {
      setLoadingServices(false);
    }
  }, []);

  // Handle edge connection
  const onConnect = useCallback(
    (params) => {
      // For special nodes (condition, loop), allow multiple connections with different handles
      const sourceNode = nodes.find(n => n.id === params.source);
      const isSpecialNode = sourceNode && ['condition', 'loop'].includes(sourceNode.type);
      
      // Check current edges to see if we need to replace one
      const currentEdges = edges;
      const identicalConnection = currentEdges.some(
        edge => edge.source === params.source && 
                edge.target === params.target &&
                edge.sourceHandle === params.sourceHandle &&
                edge.targetHandle === params.targetHandle
      );
      
      // If identical connection exists, don't add it
      if (identicalConnection) {
        return;
      }
      
      // Create the new edge object
      const newEdge = {
        ...params,
        id: params.id || `e${params.source}-${params.target}-${params.sourceHandle || 'default'}-${params.targetHandle || 'default'}`,
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };
      
      // For non-special nodes, check if we need to replace an existing edge
      if (!isSpecialNode) {
        const existingEdge = currentEdges.find(
          edge => edge.source === params.source && edge.target === params.target
        );
        
        if (existingEdge && isCollaborating) {
          // Send delete for old edge first
          safeSendOperation({
            operation_type: 'edge_delete',
            edge_id: existingEdge.id
          });
        }
      }
      
      // Send collaboration operation for new edge
      if (isCollaborating) {
        safeSendOperation({
          operation_type: 'edge_add',
          edge_data: newEdge
        });
      }
      
      // Then update local state
      setEdges((eds) => {
        // For non-special nodes, remove any existing connection
        if (!isSpecialNode) {
          const filteredEdges = eds.filter(
            edge => !(edge.source === params.source && edge.target === params.target)
          );
          return addEdge(newEdge, filteredEdges);
        }
        
        return addEdge(newEdge, eds);
      });
    },
    [setEdges, edges, nodes, isCollaborating, safeSendOperation]
  );

  // Handle node selection
  const onNodeClick = useCallback(async (event, node) => {
    console.log('Node clicked:', node);
    console.log('Node data:', node.data);
    console.log('Node serviceId:', node.data?.serviceId);
    setSelectedNode(node);
    setShowPropertiesPanel(true);
    
    // If it's an action node with an app selected, load its services
    if (node.type === 'action' && node.data.appId) {
      const services = await fetchAppServices(node.data.appId);
      console.log('Fetched services for app:', node.data.appId, services);
      console.log('Looking for serviceId:', node.data?.serviceId);
      if (services && node.data?.serviceId) {
        const matchingService = services.find(s => s.service_id === node.data.serviceId);
        console.log('Found matching service:', matchingService);
      }
    }
    
    // If it's a trigger node with application_event type and app selected, load its events
    if (node.type === 'trigger' && node.data.triggerType === 'application_event' && node.data.appId) {
      await fetchAppEvents(node.data.appId);
    }

    // If it's a wait_for_event node with an app selected, load its events
    if (node.type === 'wait_for_event' && node.data.appId) {
      await fetchAppEvents(node.data.appId);
    }
  }, [fetchAppServices, fetchAppEvents]);

  // Manual validation trigger - can be called from other functions
  const validateFlowManual = useCallback(() => {
    if (!isEditMode || !flowId) return;
    
    setIsValidating(true);
    
    // Send the current flow state for validation
    const flowDefinition = {
      nodes: nodes.map(node => ({
        id: node.id,
        type: node.type,
        position: node.position,
        data: node.data
      })),
      edges: edges.map(edge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        label: edge.label
      }))
    };
    
    console.log('Manual validation with state:', flowDefinition);
    
    axios.post(`/api/v1/flows/${flowId}/validate-current`, {
      flow_definition: flowDefinition
    })
    .then(response => {
      const { errors_by_node } = response.data;
      console.log('Validation response:', errors_by_node);
      setValidationErrors(errors_by_node || {});
    })
    .catch(error => {
      console.error('Failed to validate flow:', error);
      setValidationErrors({});
    })
    .finally(() => {
      setIsValidating(false);
    });
  }, [isEditMode, flowId, nodes, edges]);

  // Validate flow when nodes or edges change
  useEffect(() => {
    if (!isEditMode || !flowId) return;
    
    const timer = setTimeout(() => {
      // Inline validation to ensure we use the latest state
      setIsValidating(true);
      
      // Send the current flow state for validation - use the same format as the backend expects
      const flowDefinition = {
        nodes: nodes.map(node => ({
          id: node.id,
          type: node.type,
          position: node.position,
          data: node.data
        })),
        edges: edges.map(edge => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle,
          targetHandle: edge.targetHandle,
          label: edge.label
        }))
      };
      
      console.log('Validating flow with current state:', flowDefinition);
      
      axios.post(`/api/v1/flows/${flowId}/validate-current`, {
        flow_definition: flowDefinition
      })
      .then(response => {
        const { errors_by_node } = response.data;
        console.log('Validation response:', errors_by_node);
        setValidationErrors(errors_by_node || {});
      })
      .catch(error => {
        console.error('Failed to validate flow:', error);
        setValidationErrors({});
      })
      .finally(() => {
        setIsValidating(false);
      });
    }, 500); // Reduced debounce for more responsive validation
    
    return () => clearTimeout(timer);
  }, [nodes, edges, isEditMode, flowId]);

  // Handle node deletion
  const onNodesDelete = useCallback((deleted) => {
    setSelectedNode(null);
    setShowPropertiesPanel(false);
  }, []);

  // Cycle through properties panel modes
  const cyclePropertiesPanelMode = useCallback(() => {
    const modes = ['right', 'center', 'fullscreen'];
    const currentIndex = modes.indexOf(propertiesPanelMode);
    const nextIndex = (currentIndex + 1) % modes.length;
    const newMode = modes[nextIndex];
    setPropertiesPanelMode(newMode);
    localStorage.setItem('propertiesPanelMode', newMode);
  }, [propertiesPanelMode]);

  // Add new node
  const addNode = useCallback((type) => {
    // Use selected node as reference, otherwise find the rightmost node
    const referenceNode = selectedNode || nodes.reduce((rightmost, node) => {
      if (!rightmost || node.position.x > rightmost.position.x) {
        return node;
      }
      return rightmost;
    }, null);

    // Check if we're adding after a loop node (for horizontal arrangement)
    const isAfterLoop = referenceNode && referenceNode.type === 'loop';
    
    // Position new node below the selected node (or rightmost node if none selected)
    const position = referenceNode 
      ? { 
          x: referenceNode.position.x, // Same X position as reference node
          y: referenceNode.position.y + (referenceNode.height || 120) + 80 // Below reference node with spacing
        }
      : { x: 250, y: 150 }; // Default position if no nodes exist

    const newNode = {
      id: generateUniqueNodeId(type, nodes),
      type,
      position,
      width: 200,
      height: 100,
      style: {
        width: '200px',
        height: '100px'
      },
      data: { 
        label: type.charAt(0).toUpperCase() + type.slice(1),
        config: {},
        width: 200,
        height: 100,
        // Default loop configuration
        ...(type === 'loop' ? {
          loopType: 'forEach',
          iteratorName: 'item',
          arrayPath: ''
        } : {}),
        // Default human_in_loop configuration
        ...(type === 'human_in_loop' ? {
          taskType: 'review',
          title: '',
          description: '',
          priority: 'medium',
          assignmentConfig: { type: 'user', users: [], roles: [] },
          displayConfig: { format: 'form', fields: [] },
          inputDataMapping: {},
          timeoutMinutes: 0,
          escalationConfig: {},
        } : {}),
        // Default wait_for_event configuration
        ...(type === 'wait_for_event' ? {
          appId: '',
          eventName: '',
          eventId: '',
          matchMode: 'token',
          correlationConfig: { eventField: '', flowField: '' },
          timeoutMinutes: 0,
          timeoutAction: 'fail',
          defaultData: {},
        } : {})
      },
    };
    setNodes((nds) => nds.concat(newNode));
    
    // Send collaboration operation for new node
    if (isCollaborating) {
      safeSendOperation({
        operation_type: 'node_add',
        node_data: newNode
      });
    }
    
    // Auto-connect from reference node if it exists
    if (referenceNode) {
      const newEdge = {
        id: `e${referenceNode.id}-${newNode.id}`,
        source: referenceNode.id,
        target: newNode.id,
        sourceHandle: 'bottom', // Connect from bottom of source node
        targetHandle: 'top', // Connect to top of target node
        markerEnd: {
          type: MarkerType.ArrowClosed,
        },
      };
      setEdges((eds) => eds.concat(newEdge));
      
      // Send collaboration operation for new edge
      if (isCollaborating) {
        safeSendOperation({
          operation_type: 'edge_add',
          edge_data: newEdge
        });
      }
    }
    
    setShowNodePanel(false);
  }, [setNodes, setEdges, nodes, selectedNode, isCollaborating, safeSendOperation]);

  // Helper function to check if expression can be parsed by visual builder
  const canUseVisualBuilderForExpression = (expr) => {
    if (!expr) return true;

    // Simple check for expressions that can be parsed
    // If expression contains function calls, complex logic, or other non-parseable elements, use text mode
    const complexPatterns = [
      /\b(function|return|if|else|for|while|switch|case|break|continue)\b/,
      /\[.*\]/,  // Array access
      /\(.*\)/,  // Function calls (except for simple comparisons)
      /[{}]/,     // Object literals or blocks
      /\?.*:/,    // Ternary operators
    ];

    // Check if it's too complex for visual builder
    for (const pattern of complexPatterns) {
      if (pattern.test(expr)) {
        return false;
      }
    }

    // Also check if it's a simple parseable expression
    const simplePattern = /^(\{\{[^}]+\}\}|[\w.]+)\s*(===|!==|>=|<=|>|<|includes|startsWith|endsWith)\s*(.+)$/;
    const logicalPattern = /\s*(&&|\|\|)\s*/;

    // If it contains logical operators, check each part
    if (logicalPattern.test(expr)) {
      const parts = expr.split(logicalPattern);
      return parts.every(part => !part.match(logicalPattern) || simplePattern.test(part.trim()));
    }

    return simplePattern.test(expr);
  };

  // Update node data
  const updateNodeData = useCallback(async (nodeId, data) => {
    // Clear validation errors for this node when it's being edited
    setValidationErrors((prevErrors) => {
      const newErrors = { ...prevErrors };
      delete newErrors[nodeId];
      return newErrors;
    });
    
    // If app selection changed, fetch its services (for action nodes) or events (for wait_for_event nodes)
    if (data.appId !== undefined && data.appId !== selectedNode?.data?.appId) {
      if (selectedNode?.type === 'wait_for_event') {
        // For wait_for_event nodes, fetch events instead of services
        await fetchAppEvents(data.appId);
        data.eventName = '';
        data.eventId = '';
      } else {
        await fetchAppServices(data.appId);
        // Reset service selection and all parameter-related data when app changes
        data.serviceId = '';
        data.parameterMapping = {};
        // Don't set parameters - it's deprecated
        delete data.parameters;
        data.parametersRaw = '';
      }

      // Find and update app name from applications table - single source of truth
      const app = applications.find(a => a.app_id === data.appId);
      if (app) {
        // Simply use app_name - it contains the instance name for instances
        data.appName = app.app_name;
        data.appIcon = app.icon_url || app.app_icon || null; // Try different possible field names for icon
        data.appType = app.app_type || null; // Pass app type for icon selection
        data.appCategory = app.category || null; // Pass category for icon selection
      }
    }
    
    // Update service name for display and execution
    if (data.serviceId !== undefined) {
      const service = selectedAppServices.find(s => s.service_id === data.serviceId);
      if (service) {
        data.service = service.service_name;  // Actual service name for backend
        data.serviceDisplayName = service.display_name;  // Display name for UI
        
        // If service changed (not just being set for the first time)
        if (data.serviceId !== selectedNode?.data?.serviceId) {
          // Initialize parameter mapping with default values
          const defaultMapping = {};
          
          // Extract parameters from service configuration
          const serviceConfig = service.service_config || {};
          const requestConfig = serviceConfig.request_config || {};
          const parameterSchema = service.parameters || serviceConfig.parameters;
          
          if (parameterSchema) {
            // Handle properties format (new format)
            if (parameterSchema.properties) {
              Object.entries(parameterSchema.properties).forEach(([key, value]) => {
                if (value.default !== undefined && value.default !== null) {
                  defaultMapping[key] = value.default;
                }
              });
            }
            // Handle fields format (old format) or direct array format
            else if (Array.isArray(parameterSchema)) {
              parameterSchema.forEach(field => {
                if (field.default !== undefined && field.default !== null) {
                  defaultMapping[field.param_name] = field.default;
                }
              });
            }
            else if (parameterSchema.fields) {
              parameterSchema.fields.forEach(field => {
                if (field.default !== undefined && field.default !== null) {
                  defaultMapping[field.param_name] = field.default;
                }
              });
            }
          }
          
          // Set the default mapping as initial parameter mapping
          data.parameterMapping = defaultMapping;
          // Don't set parameters - it's deprecated
          delete data.parameters;
          data.parametersRaw = '';
          
          // Log for debugging
          if (Object.keys(defaultMapping).length > 0) {
            console.log('Initialized parameter mapping with defaults:', defaultMapping);
          }
        }
      }
    }
    
    // Update nodes
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === nodeId) {
          const updatedData = {
            ...node.data,
            ...data,
          };

          // Clean up deprecated parameters field if parameterMapping exists
          if (updatedData.parameterMapping && updatedData.parameters) {
            delete updatedData.parameters;
          }

          // Special handling for condition nodes - update label based on expression
          if (node.type === 'condition' && data.expression !== undefined) {
            // Check if expression is complex (not parseable by visual builder)
            const isComplexExpression = data.expression && !canUseVisualBuilderForExpression(data.expression);
            if (isComplexExpression) {
              updatedData.label = 'Advanced Expression';
            } else if (!data.expression) {
              updatedData.label = 'Condition';
            } else {
              // For simple expressions, keep "Condition" or could parse and show a summary
              updatedData.label = 'Condition';
            }
          }

          return {
            ...node,
            data: updatedData,
          };
        }
        return node;
      })
    );
    
    // Send collaboration operation for node update
    if (isCollaborating) {
      const node = nodes.find(n => n.id === nodeId);
      if (node) {
        safeSendOperation({
          operation_type: 'node_update',
          node_id: nodeId,
          updates: {
            data: {
              ...node.data,
              ...data,
            }
          }
        });
      }
    }
    
    // Update selectedNode if this is the selected node
    if (selectedNode && selectedNode.id === nodeId) {
      setSelectedNode((prevNode) => ({
        ...prevNode,
        data: {
          ...prevNode.data,
          ...data,
        },
      }));
    }
  }, [setNodes, selectedNode, applications, selectedAppServices, fetchAppServices, fetchAppEvents, setSelectedNode, isCollaborating, nodes, safeSendOperation]);

  // Check if a node is inside a loop body
  const isNodeInsideLoop = useCallback((nodeId) => {
    // Find all loop nodes
    const loopNodes = nodes.filter(n => n.type === 'loop');
    
    for (const loopNode of loopNodes) {
      // Find edges from the loop node with sourceHandle 'loop-body'
      const loopBodyEdges = edges.filter(e => 
        e.source === loopNode.id && e.sourceHandle === 'loop-body'
      );
      
      if (loopBodyEdges.length > 0) {
        // Check if current node is reachable from any loop body edge
        const loopBodyStartNodes = loopBodyEdges.map(e => e.target);
        
        // Simple reachability check - traverse from loop body start to see if we reach nodeId
        const visited = new Set();
        const queue = [...loopBodyStartNodes];
        
        while (queue.length > 0) {
          const current = queue.shift();
          if (visited.has(current)) continue;
          visited.add(current);
          
          if (current === nodeId) {
            return { isInLoop: true, loopNode };
          }
          
          // Find all edges from current node (but not loop-back edges)
          const nextEdges = edges.filter(e => 
            e.source === current && 
            !(e.target === loopNode.id && e.targetHandle === 'loop-back')
          );
          
          nextEdges.forEach(e => queue.push(e.target));
        }
      }
    }
    
    return { isInLoop: false, loopNode: null };
  }, [nodes, edges]);
  
  // Handle node ID change
  const handleNodeIdChange = useCallback((oldId, newId) => {
    // Validate new ID
    const validation = validateNodeId(newId, nodes, oldId);
    if (!validation.isValid) {
      showErrorToast(validation.error);
      return false;
    }
    
    // Update all references
    const { nodes: updatedNodes, edges: updatedEdges } = updateNodeIdReferences(oldId, newId, nodes, edges);
    
    // Apply updates
    setNodes(updatedNodes);
    setEdges(updatedEdges);
    
    // Update selected node if it was the one being edited
    if (selectedNode && selectedNode.id === oldId) {
      const updatedSelectedNode = updatedNodes.find(n => n.id === newId);
      setSelectedNode(updatedSelectedNode);
    }
    
    // Clear editing state
    setEditingNodeId(null);
    setTempNodeId('');
    
    showSuccessToast(`Node ID updated from "${oldId}" to "${newId}"`);
    return true;
  }, [nodes, edges, setNodes, setEdges, selectedNode]);

  // Get available variables from trigger and previous nodes
  const getAvailableVariables = useCallback((currentNodeId = null) => {
    // Debug: console.log('🔍 getAvailableVariables called with:', { currentNodeId, nodesCount: nodes?.length, edgesCount: edges?.length });
    
    const variables = {
      input: {},
      node_outputs: {},
      flow: {
        execution_id: 'Unique execution identifier',
        start_time: 'Flow execution start time',
        current_node: 'Current node being executed'
      },
      data: {
        _description: 'Output from the last executed node',
        '[any_property]': 'Any property from the last node output'
      }
    };
    
    // Add metadata for node labels
    const nodeMetadata = {};
    if (nodes && nodes.length > 0) {
      nodes.forEach(node => {
        if (node.type === 'action' || node.type === 'transform') {
          nodeMetadata[node.id] = {
            label: node.data.label || `${node.type} ${node.id}`,
            type: node.type
          };
        }
      });
    }
    
    // Get trigger variables
    const triggerNode = nodes && nodes.length > 0 ? nodes.find(node => node.type === 'trigger') : null;
    if (triggerNode?.data.triggerType === 'manual' || triggerNode?.data.triggerType === 'chat_input') {
      // Manual and Chat Input trigger variables
      if (triggerNode.data.manualVariables?.length > 0) {
        triggerNode.data.manualVariables.forEach(variable => {
          variables.input[variable.name] = variable.description || variable.displayName || variable.name;
        });
      } else {
        // Add placeholder for triggers without variables
        if (triggerNode?.data.triggerType === 'chat_input') {
          // Default message variable
          variables.input['message'] = "The user's chat message";
        } else {
          variables.input['[variable_name]'] = 'Configure variables in the trigger node';
        }
      }
      // Add session variables for chat_input
      if (triggerNode?.data.triggerType === 'chat_input') {
        variables.input['session_id'] = 'The chat session ID for conversation continuity';
        variables.input['is_first_message'] = 'Whether this is the first message in the session';
      }
    } else if (triggerNode?.data.triggerType === 'file_change') {
      // File change trigger variables
      variables.input['file_path'] = 'Full path of the changed file';
      variables.input['file_name'] = 'Name of the file';
      variables.input['event_type'] = 'Type of change (create/modify/delete)';
      variables.input['timestamp'] = 'When the event occurred';
      variables.input['file_size'] = 'Size of the file (if applicable)';
    } else if (triggerNode?.data.triggerType === 'mqtt') {
      // MQTT trigger variables
      variables.input['topic'] = 'Topic the message was published to';
      variables.input['payload'] = 'Decoded payload (parsed object when JSON)';
      variables.input['payload_raw'] = 'Raw payload string';
      variables.input['qos'] = 'QoS level of the received message';
      variables.input['retain'] = 'Whether the message was a retained message';
      variables.input['timestamp'] = 'When the message was received';
    } else if ((triggerNode?.data.triggerType === 'application_event' || triggerNode?.data.triggerType === 'event') && triggerNode?.data.eventId) {
      // Application event trigger variables - use the same format as manual triggers
      if (triggerNode.data.eventVariables?.length > 0) {
        triggerNode.data.eventVariables.forEach(variable => {
          variables.input[variable.name] = variable.description || variable.displayName || variable.name;
        });
      } else {
        // Fallback for events without eventVariables (legacy or incomplete setup)
        const event = selectedAppEvents.find(e => e.event_id === triggerNode.data.eventId);
        if (event && event.output_schema) {
          // Try to extract variables from output_schema for polling and other events
          let outputSchema = event.output_schema;
          if (typeof outputSchema === 'string') {
            try {
              outputSchema = JSON.parse(outputSchema);
            } catch (e) {
              outputSchema = {};
            }
          }
          
          if (outputSchema.properties) {
            Object.entries(outputSchema.properties).forEach(([key, value]) => {
              variables.input[key] = value.description || `${value.type || 'any'} - ${key}`;
            });
          } else {
            variables.input[event.event_name || 'event_data'] = `Data from ${event.display_name || event.event_name} event`;
          }
        } else if (event) {
          variables.input[event.event_name || 'event_data'] = `Data from ${event.display_name || event.event_name} event`;
        } else {
          variables.input['[configure_event]'] = 'Configure event parameters in the trigger node';
        }
      }
    } else {
      // Default case when no trigger is configured or trigger type is not set
      if (!triggerNode) {
        variables.input['[configure_trigger]'] = 'Please configure a trigger node first';
      } else {
        variables.input['[select_trigger_type]'] = 'Please select a trigger type';
      }
    }
    
    // Ensure input always has at least some structure
    if (Object.keys(variables.input).length === 0) {
      variables.input['[no_variables]'] = 'No input variables available';
    }
    
    // Get outputs from all nodes that come before the current node
    if (currentNodeId) {
      // Find all nodes that can reach the current node
      const reachableNodes = findReachableNodes(currentNodeId, edges, nodes);
      // Debug: console.log('🔍 Reachable nodes for', currentNodeId, ':', reachableNodes);
      // Debug: console.log('🔍 All edges:', edges.map(e => ({ source: e.source, target: e.target })));
      
      reachableNodes.forEach(nodeId => {
        const node = nodes && nodes.length > 0 ? nodes.find(n => n.id === nodeId) : null;
        if (node && (node.type === 'action' || node.type === 'transform')) {
          const nodeLabel = node.data.label || `Node ${node.id}`;
          
          // Create nested structure for node outputs
          if (node.type === 'transform') {
            // For transform nodes, the output is directly what the script returns
            // Use node.id directly without 'node_' prefix to match backend storage
            variables.node_outputs[node.id] = {
              _description: `Output from ${nodeLabel} (transform node)`,
              // Transform nodes return the 'output' dictionary directly
              '[any_property]': 'Any property set in the output dictionary (e.g., message, data, etc.)'
            };
            
            // Try to parse the script to find output assignments
            if (node.data.script) {
              const outputPattern = /output\s*\[\s*['"]([^'"]+)['"]\s*\]/g;
              let match;
              const foundOutputs = new Set();
              while ((match = outputPattern.exec(node.data.script)) !== null) {
                const propName = match[1];
                foundOutputs.add(propName);
              }
              foundOutputs.forEach(prop => {
                variables.node_outputs[node.id][prop] = `${prop} from ${nodeLabel}`;
              });
            }
          } else {
            // For action nodes - aligned with new API response structure
            // Use node.id directly without 'node_' prefix to match backend storage
            variables.node_outputs[node.id] = {
              _description: `Output from ${nodeLabel}`,
              data: `Response data from ${nodeLabel}`,
              status: `HTTP status code (e.g., 200, 400)`,
              headers: `Response headers object`,
              success: `Boolean indicating if request was successful`,
              error: `Error from ${nodeLabel} (if any)`
            };
          }
          
          // If it's an action node with a known service, add service-specific outputs
          if (node.type === 'action' && node.data.serviceId) {
            const service = selectedAppServices.find(s => s.service_id === node.data.serviceId);
            if (service?.output_schema?.properties) {
              const buildFromSchema = (schema) => {
                const result = {};
                if (schema.properties) {
                  Object.entries(schema.properties).forEach(([key, prop]) => {
                    if (prop.type === 'object' && prop.properties) {
                      result[key] = buildFromSchema(prop);
                    } else {
                      result[key] = prop.description || key;
                    }
                  });
                }
                return result;
              };
              // Nest the service schema under 'data' to match new API response structure
              const schemaData = buildFromSchema(service.output_schema);
              variables.node_outputs[node.id].data = schemaData;
            }
          }
        }
      });
    } else {
      // If no current node specified, show all action/transform nodes
      if (nodes && nodes.length > 0) {
        nodes.forEach(node => {
        if (node.type === 'action' || node.type === 'transform') {
          const nodeLabel = node.data.label || `Node ${node.id}`;
          if (node.type === 'transform') {
            // Use node.id directly without 'node_' prefix to match backend storage
            variables.node_outputs[node.id] = {
              _description: `Output from ${nodeLabel} (transform node)`
            };
            // Try to parse the script to find output assignments
            if (node.data.script) {
              const outputPattern = /output\s*\[\s*['"]([^'"]+)['"]\s*\]/g;
              let match;
              while ((match = outputPattern.exec(node.data.script)) !== null) {
                const propName = match[1];
                variables.node_outputs[node.id][propName] = `${propName} from ${nodeLabel}`;
              }
            }
          } else {
            // Use node.id directly without prefix - aligned with new API response structure
            variables.node_outputs[node.id] = {
              _description: `Output from ${nodeLabel}`,
              data: `Response data from ${nodeLabel}`,
              status: `HTTP status code (e.g., 200, 400)`,
              headers: `Response headers object`,
              success: `Boolean indicating if request was successful`,
              error: `Error from ${nodeLabel} (if any)`
            };
          }
        }
      });
      }
    }
    
    // Add global variables
    variables.global = {
      _description: 'Global variables accessible across all nodes (set by transform nodes)'
    };
    
    // Scan transform nodes for set_global calls to provide hints
    let hasGlobalVars = false;
    if (nodes && nodes.length > 0) {
      nodes.forEach(node => {
      if (node.type === 'transform' && node.data.script) {
        // Simple regex to find set_global calls
        const setGlobalPattern = /set_global\s*\(\s*['"]([^'"]+)['"]/g;
        let match;
        while ((match = setGlobalPattern.exec(node.data.script)) !== null) {
          const varName = match[1];
          variables.global[varName] = `Global variable set by ${node.data.label || node.id}`;
          hasGlobalVars = true;
        }
      }
    });
    }
    
    // If no specific global vars found, show placeholder
    if (!hasGlobalVars) {
      variables.global['[any_variable]'] = 'Any global variable set by transform nodes';
    }
    
    // Also scan for data properties from previous nodes
    if (currentNodeId) {
      const reachableNodes = findReachableNodes(currentNodeId, edges, nodes);
      reachableNodes.forEach(nodeId => {
        const node = nodes && nodes.length > 0 ? nodes.find(n => n.id === nodeId) : null;
        if (node && node.type === 'transform' && node.data.script) {
          // Parse output assignments to predict data structure
          const outputPattern = /output\s*\[\s*['"]([^'"]+)['"]\s*\]/g;
          let match;
          while ((match = outputPattern.exec(node.data.script)) !== null) {
            const propName = match[1];
            variables.data[propName] = `${propName} from last executed node`;
          }
        }
      });
    }
    
    // Check if current node is inside a loop and add loop variables
    if (currentNodeId) {
      const { isInLoop, loopNode } = isNodeInsideLoop(currentNodeId);
      if (isInLoop && loopNode) {
        const loopType = loopNode.data.loopType || 'forEach';
        
        variables.loop = {
          _description: 'Loop iteration variables',
          index: 'Current iteration index (0-based)',
          count: 'Current iteration count (1-based)',
          first: 'True if this is the first iteration',
          last: 'True if this is the last iteration (forEach only)'
        };
        
        // Add iterator variable based on loop type
        if (loopType === 'forEach') {
          const iteratorName = loopNode.data.iteratorName || 'item';
          variables.loop[iteratorName] = `Current item in the iteration`;
        } else if (loopType === 'for') {
          const iteratorName = loopNode.data.iteratorName || 'i';
          variables.loop[iteratorName] = `Current counter value`;
        }
        
        // No need to duplicate under input - loop variables are top-level
      }
    }
    
    // Add node metadata to help display labels
    variables._nodeMetadata = nodeMetadata;
    
    return variables;
  }, [nodes, edges, selectedAppEvents, isNodeInsideLoop]);
  
  // Helper function to find nodes that can reach a target node
  const findReachableNodes = (targetNodeId, edges, nodes) => {
    const reachable = new Set();
    const visited = new Set();
    
    // Find all nodes that have edges leading to the target
    const findPredecessors = (nodeId) => {
      if (visited.has(nodeId)) return;
      visited.add(nodeId);
      
      edges.forEach(edge => {
        if (edge.target === nodeId && !reachable.has(edge.source)) {
          reachable.add(edge.source);
          findPredecessors(edge.source);
        }
      });
    };
    
    findPredecessors(targetNodeId);
    return Array.from(reachable);
  };

  // Helper function to find next nodes (where the output of this node will be used)
  const getNextNodeInfo = useCallback((currentNodeId) => {
    const nextNodes = [];
    
    // Find all edges where current node is the source
    edges.forEach(edge => {
      if (edge.source === currentNodeId) {
        const targetNode = nodes.find(n => n.id === edge.target);
        if (targetNode) {
          nextNodes.push({
            id: targetNode.id,
            type: targetNode.type,
            label: targetNode.data?.label || `${targetNode.type} ${targetNode.id}`,
            description: targetNode.data?.description || '',
            serviceId: targetNode.data?.serviceId,
            serviceName: targetNode.data?.serviceName
          });
        }
      }
    });

    return {
      nextNodes,
      hasNextNodes: nextNodes.length > 0,
      summary: nextNodes.length > 0 
        ? `Transform output will be used by: ${nextNodes.map(n => n.label).join(', ')}`
        : 'Transform output is not connected to any other nodes'
    };
  }, [nodes, edges]);

  // Get previous node output schema (simplified)
  const getPreviousNodeOutputSchema = useCallback(() => {
    // This would ideally get the actual output schema from the previous node
    // For now, return a basic schema
    return {
      properties: {
        data: { type: 'object', description: 'Previous node output' },
        status: { type: 'string', description: 'Execution status' }
      }
    };
  }, []);

  // Extract trigger configuration from nodes
  const getTriggerConfig = useCallback(() => {
    const triggerNode = nodes.find(node => node.type === 'trigger');
    if (!triggerNode) return { type: 'manual' };

    const {
      triggerType, appId, eventId, eventName, schedule, manualVariables,
      eventVariables, executeImmediately, folderPath, listenerType,
      filePattern, recursive, debounceSeconds,
      mqttHost, mqttPort, mqttTls, mqttUsername, mqttPassword,
      mqttClientId, mqttTopicFilter, mqttQos, mqttPayloadFormat,
      mqttBatchSize, mqttBatchWindowSeconds, mqttMaxRate, mqttRateOverflow,
      mqttMaxConcurrent, mqttDedup, mqttDedupKey, mqttDedupWindowSeconds,
      eventTriggerKind
    } = triggerNode.data;

    // Performance & Delivery keys — shared by the flat 'mqtt' trigger and
    // MQTT application-event triggers (identical trigger_config keys, so the
    // backend resolution logic is shared)
    const applyMqttPerfConfig = (config) => {
      if (mqttBatchSize !== undefined) config.mqtt_batch_size = mqttBatchSize;
      if (mqttBatchWindowSeconds !== undefined) config.mqtt_batch_window_seconds = mqttBatchWindowSeconds;
      if (mqttMaxRate !== undefined) config.mqtt_max_rate = mqttMaxRate;
      if (mqttRateOverflow !== undefined) config.mqtt_rate_overflow = mqttRateOverflow;
      if (mqttMaxConcurrent !== undefined) config.mqtt_max_concurrent = mqttMaxConcurrent;
      if (mqttDedup !== undefined) config.mqtt_dedup = mqttDedup;
      if (mqttDedupKey !== undefined) config.mqtt_dedup_key = mqttDedupKey;
      if (mqttDedupWindowSeconds !== undefined) config.mqtt_dedup_window_seconds = mqttDedupWindowSeconds;
    };
    
    // Map frontend trigger types to backend types
    let backendTriggerType = triggerType || 'manual';
    if (triggerType === 'application_event') {
      backendTriggerType = 'event'; // Backend expects 'event' for application events
    }
    
    // Format schedule as expected by backend
    // (cron string from the builder, or an interval/daily/weekly/monthly object)
    const formattedSchedule = triggerType === 'schedule' ? formatScheduleForBackend(schedule) : null;
    
    // Use the appropriate variables based on trigger type
    // chat_input also uses manualVariables (with message as the default variable)
    const variables = triggerType === 'application_event' ? eventVariables : manualVariables;
    
    // Build the base config
    const config = {
      type: backendTriggerType,
      app_id: appId,
      event_id: eventId,
      event_name: eventName,
      schedule: formattedSchedule,
      manual_variables: variables, // Backend still expects 'manual_variables' field name
      execute_immediately: triggerType === 'schedule' ? (executeImmediately !== false) : undefined,
    };
    
    // Add file_change specific configuration
    if (triggerType === 'file_change') {
      // Log for debugging
      console.log('File change trigger config:', {
        folderPath,
        listenerType,
        filePattern,
        recursive,
        debounceSeconds
      });

      config.folder_path = folderPath || '';
      config.listener_type = listenerType || ['create', 'modify', 'delete'];
      config.file_pattern = filePattern || '*';
      config.recursive = recursive || false;
      config.debounce_seconds = debounceSeconds || 5;

      // Ensure folder_path is set
      if (!config.folder_path) {
        console.error('Warning: folder_path is empty for file_change trigger');
      }
    }

    // Add mqtt specific configuration
    if (triggerType === 'mqtt') {
      config.mqtt_host = mqttHost || '';
      config.mqtt_port = mqttPort || 1883;
      config.mqtt_tls = mqttTls || false;
      config.mqtt_username = mqttUsername || '';
      config.mqtt_password = mqttPassword || '';
      config.mqtt_client_id = mqttClientId || '';
      config.mqtt_topic_filter = mqttTopicFilter || '';
      config.mqtt_qos = mqttQos !== undefined ? mqttQos : 1;
      config.mqtt_payload_format = mqttPayloadFormat || 'json';
      applyMqttPerfConfig(config);

      // Ensure required fields are set
      if (!config.mqtt_host) {
        console.error('Warning: mqtt_host is empty for mqtt trigger');
      }
      if (!config.mqtt_topic_filter) {
        console.error('Warning: mqtt_topic_filter is empty for mqtt trigger');
      }
    }

    // Application-event trigger bound to an MQTT event: persist the per-flow
    // subscription overrides (broker/credentials come from the app connection)
    if (backendTriggerType === 'event' && eventTriggerKind === 'mqtt') {
      if (mqttTopicFilter) config.mqtt_topic_filter = mqttTopicFilter;
      if (mqttQos !== undefined) config.mqtt_qos = mqttQos;
      if (mqttPayloadFormat) config.mqtt_payload_format = mqttPayloadFormat;
      applyMqttPerfConfig(config);
    }

    // Add chat_input specific configuration
    if (triggerType === 'chat_input') {
      const { placeholderText, sessionTimeoutMinutes, systemPrompt, welcomeMessage } = triggerNode.data;
      config.placeholder_text = placeholderText || 'Type your message...';
      config.session_timeout_minutes = sessionTimeoutMinutes || 1440; // 24 hours default
      if (systemPrompt) {
        config.system_prompt = systemPrompt;
      }
      if (welcomeMessage) {
        config.welcome_message = welcomeMessage;
      }
    }

    return config;
  }, [nodes]);

  // Save JSON changes
  const handleJsonSave = useCallback((jsonData) => {
    try {
      let flowDefinition = jsonData;
      
      // Check if it's in export/import format
      if (jsonData.version && jsonData.flow && jsonData.flow.flow_definition) {
        // Extract flow definition from export format
        flowDefinition = jsonData.flow.flow_definition;
        
        // Update flow name and description if provided
        if (jsonData.flow.flow_name) {
          setFlowName(jsonData.flow.flow_name);
        }
        if (jsonData.flow.description !== undefined) {
          setFlowDescription(jsonData.flow.description);
        }
        
        // Update sync settings if provided
        if (jsonData.flow.is_synchronous !== undefined) {
          setIsSynchronous(jsonData.flow.is_synchronous);
        }
        if (jsonData.flow.sync_timeout !== undefined) {
          setSyncTimeout(jsonData.flow.sync_timeout);
        }
      }

      // Update nodes and edges from flow definition
      if (flowDefinition.nodes && Array.isArray(flowDefinition.nodes)) {
        setNodes(flowDefinition.nodes);
      }
      if (flowDefinition.edges && Array.isArray(flowDefinition.edges)) {
        setEdges(flowDefinition.edges);
      }
      // Load flow-level execution settings if present
      if (flowDefinition.settings) {
        if (flowDefinition.settings.execution_log_level) {
          setExecutionLogLevel(flowDefinition.settings.execution_log_level);
        }
        if (flowDefinition.settings.flow_log_sample_rate !== undefined) {
          setLogSampleRate(flowDefinition.settings.flow_log_sample_rate);
        }
        setErrorHandlerFlowId(flowDefinition.settings.error_handler_flow_id || '');
      }
      
      // Close the JSON editor
      setShowJsonEditor(false);
      
      // Fit view to show the updated flow
      setTimeout(() => {
        fitView({
          padding: 0.2,
          includeHiddenNodes: false,
          minZoom: 0.5,
          maxZoom: 1.5,
        });
      }, 100);
    } catch (error) {
      console.error('Error applying JSON changes:', error);
      showErrorToast('Failed to apply JSON changes');
    }
  }, [setNodes, setEdges, fitView]);

  // Export flow handler
  const handleFlowExport = useCallback(async () => {
    try {
      const response = await axios.post(`/api/v1/flows/${flowId}/export`);
      const exportData = response.data;
      
      // Create and download JSON file
      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${flowName || 'flow'}_export_${new Date().getTime()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      showSuccessToast('Flow exported successfully');
      
      // Show warnings if any
      if (exportData.metadata?.warnings?.length > 0) {
        exportData.metadata.warnings.forEach(warning => {
          showWarningToast(warning.message);
        });
      }
    } catch (error) {
      console.error('Export failed:', error);
      showErrorToast('Failed to export flow');
    }
  }, [flowId, flowName]);

  // Import flow handler
  const handleFlowImport = useCallback((event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      let importData;
      try {
        importData = JSON.parse(e.target.result);

        // Validate import format
        if (!importData.version || !importData.flow) {
          showErrorToast('Invalid import file format');
          return;
        }

        // Step 1: Validate applications first
        const validationResponse = await axios.post('/api/v1/flows/validate-import', importData);

        if (validationResponse.data.success && !validationResponse.data.can_import) {
          // There are missing applications - show the wizard
          setValidationData(validationResponse.data);
          setPendingImportData(importData);
          setWizardOpen(true);
          return;
        }

        // Step 2: All applications are ready, proceed with import
        const response = await axios.post('/api/v1/flows/import', importData);

        if (response.data.success) {
          showSuccessToast('Flow imported successfully');

          // Navigate to the imported flow
          navigate(`/flows/${response.data.flow_id}/edit`);
        } else if (response.data.error === 'missing_applications') {
          // Fallback: Show missing applications error
          const missingApps = response.data.missing_applications
            .map(app => app.app_name)
            .join(', ');
          showErrorToast(`Missing applications: ${missingApps}. Please install them first.`);
        } else {
          showErrorToast(response.data.message || 'Import failed');
        }
      } catch (error) {
        console.error('Import failed:', error);
        if (importData) {
          console.error('Import data that was sent:', importData);
        }

        if ((error.response?.data?.message || error.response?.data?.detail)) {
          // Check if detail is an object with more information
          const detail = error.response.data.detail;
          if (typeof detail === 'object' && detail.message) {
            showErrorToast(detail.message);
          } else if (typeof detail === 'string') {
            showErrorToast(detail);
          } else {
            showErrorToast('Failed to import flow: ' + JSON.stringify(detail));
          }
        } else if (error.response?.status === 500) {
          showErrorToast('Server error during import. Check if the flow format is correct.');
        } else {
          showErrorToast('Failed to import flow');
        }
      }
    };

    reader.onerror = () => {
      showErrorToast('Failed to read import file');
    };

    reader.readAsText(file);

    // Reset input
    event.target.value = '';
  }, [navigate]);

  // Handler for when all applications are ready in the wizard
  const handleAllAppsReady = useCallback(async () => {
    if (!pendingImportData) return;

    try {
      // Now that all apps are ready, proceed with the import
      const response = await axios.post('/api/v1/flows/import', pendingImportData);

      if (response.data.success) {
        showSuccessToast('Flow imported successfully');

        // Navigate to the imported flow
        navigate(`/flows/${response.data.flow_id}/edit`);

        // Clean up state
        setPendingImportData(null);
        setValidationData(null);
      } else {
        showErrorToast(response.data.message || 'Import failed');
      }
    } catch (error) {
      console.error('Import failed after app setup:', error);
      showErrorToast('Failed to import flow after setting up applications');
    }
  }, [pendingImportData, navigate]);

  // Save flow
  // Validate synchronous flow
  const validateSynchronousFlow = async () => {
    if (!isSynchronous || !flowId) {
      setValidationErrors({});
      return true;
    }

    try {
      // Use the current state validation endpoint
      const flowDefinition = {
        nodes: nodes.map(node => ({
          id: node.id,
          type: node.type,
          position: node.position,
          data: node.data
        })),
        edges: edges.map(edge => ({
          id: edge.id,
          source: edge.source,
          target: edge.target,
          sourceHandle: edge.sourceHandle,
          targetHandle: edge.targetHandle,
          label: edge.label
        }))
      };
      
      const response = await axios.post(`/api/v1/flows/${flowId}/validate-current`, {
        flow_definition: flowDefinition
      });
      const { is_valid, errors_by_node, errors } = response.data;
      
      // Use errors_by_node if available, otherwise fallback to errors array
      if (errors_by_node) {
        setValidationErrors(errors_by_node);
      } else if (Array.isArray(errors)) {
        // Group errors by node_id if available, otherwise use 'general'
        const errorsByNode = {};
        errors.forEach(error => {
          const nodeId = error.node_id || 'general';
          if (!errorsByNode[nodeId]) {
            errorsByNode[nodeId] = [];
          }
          errorsByNode[nodeId].push(error);
        });
        setValidationErrors(errorsByNode);
      } else {
        setValidationErrors({});
      }
      
      // Don't show toast for validation errors
      // The visual indicators on nodes are sufficient
      // Allow saving even with validation errors
      
      return is_valid;
    } catch (error) {
      console.error('Validation failed:', error);
      return true; // Allow save on validation error
    }
  };

  const handleSave = async () => {
    if (isReadOnlyRole) {
      return;
    }
    if (!flowName) {
      showErrorToast('Please enter a flow name');
      return;
    }
    
    // Run validation but don't block saving
    // This will update visual indicators but allow save to proceed
    if (isSynchronous && isEditMode) {
      await validateSynchronousFlow();
      // Continue with save regardless of validation result
    }

    // Deduplicate edges intelligently
    const deduplicatedEdges = edges.reduce((acc, edge) => {
      // Check if this exact edge already exists
      const isDuplicate = acc.some(e => 
        e.source === edge.source && 
        e.target === edge.target &&
        e.sourceHandle === edge.sourceHandle &&
        e.targetHandle === edge.targetHandle
      );
      
      if (!isDuplicate) {
        acc.push(edge);
      }
      
      return acc;
    }, []);

    const flowData = {
      flow_name: flowName,
      description: flowDescription,
      category: flowCategory,
      flow_scope: flowScope,
      trigger_config: getTriggerConfig(),
      flow_definition: {
        nodes,
        edges: deduplicatedEdges,
        settings: {
          execution_log_level: executionLogLevel,
          flow_log_sample_rate: logSampleRate,
          ...(errorHandlerFlowId ? { error_handler_flow_id: errorHandlerFlowId } : {}),
        },
      },
      is_synchronous: isSynchronous,
      sync_timeout: syncTimeout,
    };

    // Auto-activate scheduled flows when creating new flow
    const triggerConfig = getTriggerConfig();
    if (triggerConfig.type === 'schedule' && !isEditMode) {
      flowData.status = 'active';
    }

    saveFlowMutation.mutate(flowData);
  };

  // Node types for the panel
  const nodeOptions = [
    { type: 'action', label: 'Action', icon: BoltIcon, description: 'Execute an application service' },
    { type: 'condition', label: 'Condition', icon: CodeBracketIcon, description: 'Add conditional logic' },
    { type: 'transform', label: 'Transform', icon: DocumentTextIcon, description: 'Transform data' },
    { type: 'loop', label: 'Loop', icon: ArrowPathIcon, description: 'Iterate over data or repeat actions' },
    { type: 'human_in_loop', label: 'Human Review', icon: HandRaisedIcon, description: 'Pause for human review or approval' },
    { type: 'wait_for_event', label: 'Wait for Event', icon: ClockIcon, description: 'Pause until an application event arrives' },
    // Only show response node for synchronous flows
    ...(isSynchronous ? [{ type: 'response', label: 'Response', icon: ArrowUpTrayIcon, description: 'Define flow response' }] : []),
  ];

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
              onClick={() => handleNavigation('/flows')}
              className="flex items-center text-gray-600 hover:text-gray-900"
            >
              <ArrowLeftIcon className="w-4 h-4 mr-2" />
              Back to Flows
            </button>
            <div className="border-l pl-4">
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  value={flowName}
                  onChange={(e) => setFlowName(e.target.value)}
                  placeholder="Flow name"
                  readOnly={isReadOnlyRole}
                  className="text-lg font-medium border-none focus:outline-none focus:ring-0"
                />
                {hasUnsavedChanges && (
                  <div className="w-2 h-2 bg-amber-500 rounded-full" title="Unsaved changes"></div>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {/* Collaboration Indicator - positioned before controls */}
            {isCollaborating && (
              <>
                <CollaborationIndicator
                  participants={participants}
                  isCollaborating={isCollaborating}
                  isConnected={isConnected}
                  onShowParticipants={() => setShowParticipantsList(true)}
                  currentUserId={user?.user_id || user?.id}
                  currentUserEmail={user?.email}
                  currentUserName={user?.username}
                />
                <div className="h-6 w-px bg-gray-300 mx-1" /> {/* Divider */}
              </>
            )}
            
            {/* Undo/Redo buttons */}
            <div className="flex items-center space-x-1">
              <button
                onClick={undo}
                disabled={!canUndo}
                className="p-2 text-gray-600 hover:text-gray-900 disabled:opacity-40 disabled:cursor-not-allowed rounded-md hover:bg-gray-100"
                title="Undo (Ctrl+Z)"
              >
                <ArrowUturnLeftIcon className="w-4 h-4" />
              </button>
              <button
                onClick={redo}
                disabled={!canRedo}
                className="p-2 text-gray-600 hover:text-gray-900 disabled:opacity-40 disabled:cursor-not-allowed rounded-md hover:bg-gray-100"
                title="Redo (Ctrl+Y)"
              >
                <ArrowUturnRightIcon className="w-4 h-4" />
              </button>
            </div>
            
            {!isReadOnlyRole && (
              <button
                onClick={handleSave}
                disabled={saveFlowMutation.isPending}
                className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg disabled:opacity-50 flex items-center"
              >
                <CloudArrowUpIcon className="w-4 h-4 mr-2" />
                {saveFlowMutation.isPending ? 'Saving...' : 'Save'}
              </button>
            )}
            
            {/* 3-dot menu */}
            <div className="relative">
              <button
                onClick={() => setShowSettingsModal(!showSettingsModal)}
                className="p-2 text-gray-600 hover:text-gray-900 rounded-md hover:bg-gray-100"
                title="More options"
              >
                <EllipsisVerticalIcon className="w-5 h-5" />
              </button>
              
              {/* Dropdown menu */}
              {showSettingsModal && (
                <div className="absolute right-0 top-10 mt-1 w-48 bg-white rounded-md shadow-lg border border-gray-200 py-1 z-[1000]">
                  <button
                    onClick={() => {
                      setShowSettingsModal(false);
                      // Open settings modal
                      const modal = document.getElementById('flow-settings-modal');
                      if (modal) modal.classList.remove('hidden');
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                  >
                    <CogIcon className="w-4 h-4 mr-2" />
                    Flow Settings
                  </button>
                  
                  {/* Collaboration option - only in edit mode */}
                  {isEditMode && (
                    <>
                      <button
                        onClick={async () => {
                          setShowSettingsModal(false);
                          if (!isCollaborating) {
                            try {
                              const session = await startCollaboration({
                                durationHours: 24,
                                maxParticipants: 10,
                                enableChat: true
                              });
                              // Use the returned session directly since state update is async
                              if (session && session.share_link) {
                                // Store session in a ref or state that can be immediately used
                                setCollaborationSession(session);
                                setShowInviteDialog(true);
                                showSuccessToast('Collaboration session started');
                              } else {
                                throw new Error('Session created but missing share link');
                              }
                            } catch (error) {
                              console.error('Collaboration error:', error);
                              showErrorToast('Failed to start collaboration: ' + error.message);
                            }
                          } else {
                            // When already collaborating, use the existing sessionInfo
                            setCollaborationSession(sessionInfo);
                            setShowInviteDialog(true);
                          }
                        }}
                        className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <UsersIcon className="w-4 h-4 mr-2" />
                        {isCollaborating ? 'Manage Collaboration' : 'Invite Co-editor'}
                      </button>
                      
                      {isCollaborating && (
                        <button
                          onClick={() => {
                            setShowSettingsModal(false);
                            setShowParticipantsList(true);
                          }}
                          className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                        >
                          <UsersIcon className="w-4 h-4 mr-2" />
                          Participants ({participants.length})
                        </button>
                      )}
                    </>
                  )}
                  
                  {isEditMode && (
                    <button
                      onClick={() => {
                        setShowSettingsModal(false);
                        // Open flow status modal
                        const modal = document.getElementById('flow-status-modal');
                        if (modal) modal.classList.remove('hidden');
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                    >
                      <BoltIcon className="w-4 h-4 mr-2" />
                      Flow Status
                    </button>
                  )}
                  
                  {/* Debug button - available for all flows */}
                  {isEditMode && (
                    <button
                      onClick={() => {
                        setShowSettingsModal(false);
                        navigate(`/flows/${flowId}/debug`);
                      }}
                      className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                    >
                      <BugAntIcon className="w-4 h-4 mr-2" />
                      Debug
                    </button>
                  )}
                  
                  <button
                    onClick={() => {
                      setShowSettingsModal(false);
                      
                      // Build trigger config from trigger node
                      const triggerNode = nodes.find(n => n.type === 'trigger');
                      let triggerConfig = {};
                      
                      if (triggerNode) {
                        const triggerType = triggerNode.data.triggerType;
                        triggerConfig.type = triggerType;
                        
                        if (triggerType === 'manual') {
                          triggerConfig.manual_variables = triggerNode.data.manualVariables || [];
                        } else if (triggerType === 'webhook') {
                          // Webhook is handled automatically
                        } else if (triggerType === 'schedule') {
                          triggerConfig.schedule = {
                            ...formatScheduleForBackend(triggerNode.data.schedule),
                            execute_immediately: triggerNode.data.executeImmediately !== undefined ? triggerNode.data.executeImmediately : true
                          };
                        } else if (triggerType === 'application_event') {
                          triggerConfig.app_id = triggerNode.data.appId;
                          triggerConfig.event_id = triggerNode.data.eventId;
                          triggerConfig.event_name = triggerNode.data.eventName;
                        } else if (triggerType === 'file_change') {
                          triggerConfig.folder_path = triggerNode.data.folderPath;
                          triggerConfig.listener_type = triggerNode.data.listenerType;
                          triggerConfig.file_pattern = triggerNode.data.filePattern;
                        } else if (triggerType === 'mqtt') {
                          triggerConfig.mqtt_host = triggerNode.data.mqttHost;
                          triggerConfig.mqtt_port = triggerNode.data.mqttPort;
                          triggerConfig.mqtt_tls = triggerNode.data.mqttTls;
                          triggerConfig.mqtt_username = triggerNode.data.mqttUsername;
                          triggerConfig.mqtt_password = triggerNode.data.mqttPassword;
                          triggerConfig.mqtt_client_id = triggerNode.data.mqttClientId;
                          triggerConfig.mqtt_topic_filter = triggerNode.data.mqttTopicFilter;
                          triggerConfig.mqtt_qos = triggerNode.data.mqttQos;
                          triggerConfig.mqtt_payload_format = triggerNode.data.mqttPayloadFormat;
                          if (triggerNode.data.mqttBatchSize !== undefined) triggerConfig.mqtt_batch_size = triggerNode.data.mqttBatchSize;
                          if (triggerNode.data.mqttBatchWindowSeconds !== undefined) triggerConfig.mqtt_batch_window_seconds = triggerNode.data.mqttBatchWindowSeconds;
                          if (triggerNode.data.mqttMaxRate !== undefined) triggerConfig.mqtt_max_rate = triggerNode.data.mqttMaxRate;
                          if (triggerNode.data.mqttRateOverflow !== undefined) triggerConfig.mqtt_rate_overflow = triggerNode.data.mqttRateOverflow;
                          if (triggerNode.data.mqttMaxConcurrent !== undefined) triggerConfig.mqtt_max_concurrent = triggerNode.data.mqttMaxConcurrent;
                          if (triggerNode.data.mqttDedup !== undefined) triggerConfig.mqtt_dedup = triggerNode.data.mqttDedup;
                          if (triggerNode.data.mqttDedupKey !== undefined) triggerConfig.mqtt_dedup_key = triggerNode.data.mqttDedupKey;
                          if (triggerNode.data.mqttDedupWindowSeconds !== undefined) triggerConfig.mqtt_dedup_window_seconds = triggerNode.data.mqttDedupWindowSeconds;
                        }
                      }
                      
                      // Prepare export format for view source
                      const exportFormat = {
                        version: '1.0',
                        export_timestamp: new Date().toISOString(),
                        flow: {
                          flow_name: flowName || 'Untitled Flow',
                          description: flowDescription || '',
                          category: flowCategory || 'general',
                          trigger_config: triggerConfig,
                          flow_definition: {
                            nodes: nodes,
                            edges: edges,
                            settings: {
                              execution_log_level: executionLogLevel,
                              flow_log_sample_rate: logSampleRate,
                              ...(errorHandlerFlowId ? { error_handler_flow_id: errorHandlerFlowId } : {})
                            }
                          },
                          is_synchronous: isSynchronous,
                          sync_timeout: syncTimeout
                        },
                        metadata: {
                          required_applications: [],
                          source_instance: {
                            mode: 'view_source'
                          },
                          warnings: []
                        }
                      };
                      setViewSourceData(exportFormat);
                      setShowJsonEditor(true);
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                  >
                    <CodeBracketIcon className="w-4 h-4 mr-2" />
                    View Source
                  </button>

                  <button
                    onClick={() => {
                      setShowSettingsModal(false);
                      startTutorial();
                    }}
                    className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                  >
                    <QuestionMarkCircleIcon className="w-4 h-4 mr-2" />
                    Show Tutorial
                  </button>

                  {isEditMode && (
                    <>
                      <div className="border-t border-gray-100 my-1"></div>
                      <button
                        onClick={async () => {
                          setShowSettingsModal(false);
                          handleFlowExport();
                        }}
                        className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <ArrowUpTrayIcon className="w-4 h-4 mr-2" />
                        Export Flow
                      </button>
                    </>
                  )}
                  
                  {!isEditMode && (
                    <>
                      <div className="border-t border-gray-100 my-1"></div>
                      <button
                        onClick={() => {
                          setShowSettingsModal(false);
                          document.getElementById('import-flow-input').click();
                        }}
                        className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center"
                      >
                        <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                        Import Flow
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Flow Canvas */}
        <div className="flow-canvas flex-1 relative" ref={flowCanvasRef}>
          <ReactFlow
            nodes={nodes.map(node => {
              // Check if node type is valid
              const validTypes = ['trigger', 'action', 'condition', 'transform', 'loop', 'response', 'human_in_loop', 'wait_for_event'];
              const isInvalidType = !validTypes.includes(node.type);

              return {
                ...node,
                // Map invalid types to 'invalid' which will use InvalidNode component
                type: isInvalidType ? 'invalid' : node.type,
                data: {
                  ...node.data,
                  // Preserve original node type for display in InvalidNode
                  nodeType: node.type,
                  validationErrors: validationErrors[node.id] || [],
                  onRevalidate: validateFlowManual,
                  overlappingNodes: nodeOverlaps[node.id] || [],
                  showOverlapIndicator: showOverlapIndicators && (nodeOverlaps[node.id]?.length > 0)
                }
              };
            })}
            edges={edges}
            onNodesChange={isReadOnlyRole ? undefined : onNodesChange}
            onEdgesChange={isReadOnlyRole ? undefined : onEdgesChange}
            onConnect={isReadOnlyRole ? undefined : onConnect}
            onNodeClick={onNodeClick}
            onNodesDelete={isReadOnlyRole ? undefined : onNodesDelete}
            nodesDraggable={!isReadOnlyRole}
            nodesConnectable={!isReadOnlyRole}
            edgesUpdatable={!isReadOnlyRole}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            deleteKeyCode={isReadOnlyRole ? null : ['Delete', 'Backspace']}
            connectionLineStyle={{
              stroke: '#60a5fa',
              strokeWidth: 2,
              strokeDasharray: '5 5',
            }}
            connectionLineType="bezier"
            fitView={false}
            fitViewOptions={{
              padding: 0.2,
              includeHiddenNodes: false,
              minZoom: 0.5,
              maxZoom: 1.5,
            }}
          >
            <Controls />
            <MiniMap 
              nodeColor={(node) => {
                // Color nodes based on their type
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
            
            {/* Validation Errors Panel */}
            {isSynchronous && Object.keys(validationErrors).length > 0 && (
              <Panel position="top-center" className="bg-red-50 border border-red-200 rounded-lg p-4 max-w-md">
                <div className="flex items-start">
                  <ExclamationTriangleIcon className="w-5 h-5 text-red-600 mr-2 flex-shrink-0" />
                  <div>
                    <h4 className="text-sm font-medium text-red-800 mb-1">Flow Validation Errors</h4>
                    <ul className="text-sm text-red-700 space-y-1">
                      {Object.entries(validationErrors).flatMap(([nodeId, errors]) => {
                        // Ensure errors is an array
                        const errorArray = Array.isArray(errors) ? errors : [errors];
                        return errorArray.map((error, index) => (
                          <li key={`${nodeId}-${index}`} className="flex items-start">
                            <span className="mr-1">•</span>
                            <span>{typeof error === 'object' ? (error.message || JSON.stringify(error)) : error}</span>
                          </li>
                        ));
                      })}
                    </ul>
                  </div>
                </div>
              </Panel>
            )}
            
            {/* Overlap Summary Panel */}
            {showOverlapIndicators && (Object.keys(nodeOverlaps).length > 0 || Object.keys(edgeOverlaps).length > 0) && (
              <Panel position="bottom-left" className="mb-20">
                <OverlapSummary 
                  nodeOverlaps={nodeOverlaps}
                  edgeOverlaps={edgeOverlaps}
                  onNodeClick={(nodeId) => {
                    const node = nodes.find(n => n.id === nodeId);
                    if (node) {
                      setSelectedNode(node);
                      fitView({ nodes: [node], duration: 500 });
                    }
                  }}
                />
              </Panel>
            )}
            
            {/* Toggle Overlap Indicators Button */}
            <Panel position="top-right" className="mr-2">
              <button
                onClick={() => setShowOverlapIndicators(!showOverlapIndicators)}
                className={`px-3 py-2 rounded-md shadow-sm flex items-center ${
                  showOverlapIndicators 
                    ? 'bg-purple-600 text-white hover:bg-purple-700' 
                    : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                }`}
                title={showOverlapIndicators ? 'Hide overlap indicators' : 'Show overlap indicators'}
              >
                <Squares2X2Icon className="w-4 h-4" />
                {Object.keys(nodeOverlaps).length > 0 && (
                  <span className="ml-2 bg-white/20 text-xs px-1.5 py-0.5 rounded-full">
                    {Object.keys(nodeOverlaps).length}
                  </span>
                )}
              </button>
            </Panel>
            
            {/* Add Node Button */}
            <Panel position="top-left">
              <button
                onClick={() => setShowNodePanel(!showNodePanel)}
                className="flow-add-node-button px-4 py-2 bg-white border border-gray-300 rounded-md shadow-sm hover:bg-gray-50 flex items-center"
              >
                <PlusIcon className="w-4 h-4 mr-2" />
                Add Node
              </button>
            </Panel>
          </ReactFlow>

          {/* Node Panel */}
          {showNodePanel && (
            <div className="absolute top-20 left-4 bg-white rounded-lg shadow-lg p-4 w-64 z-[1000]">
              <h3 className="font-medium mb-3">Add Node</h3>
              <div className="space-y-2">
                {nodeOptions.map((option) => (
                  <button
                    key={option.type}
                    onClick={() => addNode(option.type)}
                    className="w-full text-left p-3 rounded-md hover:bg-gray-50 border border-gray-200 transition-colors"
                  >
                    <div className="flex items-start">
                      <option.icon className="w-5 h-5 text-gray-400 mr-3 mt-0.5" />
                      <div>
                        <div className="font-medium">{option.label}</div>
                        <div className="text-xs text-gray-500">{option.description}</div>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Properties Panel */}
          {showPropertiesPanel && selectedNode && ReactDOM.createPortal(
            <>
              {/* Backdrop for center mode */}
              {propertiesPanelMode === 'center' && (
                <div 
                  className="fixed inset-0 bg-black bg-opacity-30 z-[9998] transition-opacity duration-300"
                  onClick={() => {
                    setShowPropertiesPanel(false);
                    setSelectedNode(null);
                    setSelectedAppServices([]);
                  }}
                />
              )}
              
              <div className={`fixed bg-white rounded-lg shadow-lg z-[9999] border border-gray-200 transition-all duration-300 ${
                propertiesPanelMode === 'fullscreen'
                  ? 'top-0 left-0 right-0 bottom-0 max-w-none flex flex-col rounded-none'
                  : propertiesPanelMode === 'center'
                  ? 'top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-[90vw] md:w-[80vw] h-[90vh] md:h-[80vh] max-w-6xl flex flex-col'
                  : 'inset-0 md:inset-auto md:top-16 md:right-4 md:bottom-4 md:w-[400px] lg:w-[450px] overflow-y-auto'
              }`}>
              <div className="flex items-center justify-between mb-4 px-3 md:px-4 pt-4">
                <div>
                  <h3 className="font-medium">Node Properties</h3>
                  <div className="flex items-center mt-1">
                    {editingNodeId === selectedNode.id ? (
                      <div className="flex items-center space-x-2">
                        <input
                          type="text"
                          value={tempNodeId}
                          onChange={(e) => setTempNodeId(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleNodeIdChange(selectedNode.id, tempNodeId);
                            } else if (e.key === 'Escape') {
                              setEditingNodeId(null);
                              setTempNodeId('');
                            }
                          }}
                          className="text-xs border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary"
                          placeholder="Node ID"
                          autoFocus
                        />
                        <button
                          onClick={() => handleNodeIdChange(selectedNode.id, tempNodeId)}
                          className="text-green-600 hover:text-green-700"
                          title="Save"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </button>
                        <button
                          onClick={() => {
                            setEditingNodeId(null);
                            setTempNodeId('');
                          }}
                          className="text-red-600 hover:text-red-700"
                          title="Cancel"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2">
                        <p className="text-xs text-gray-500">
                          ID: {selectedNode.id}
                        </p>
                        <button
                          onClick={() => {
                            setEditingNodeId(selectedNode.id);
                            setTempNodeId(selectedNode.id);
                          }}
                          className="text-gray-400 hover:text-gray-600"
                          title="Edit ID"
                        >
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {/* Delete button - don't show for trigger nodes */}
                  {selectedNode.type !== 'trigger' && (
                    <button
                      onClick={() => {
                        // Delete the selected node
                        setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id));
                        // Also remove any edges connected to this node
                        setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id));
                        // Close the properties panel
                        setShowPropertiesPanel(false);
                        setSelectedNode(null);
                        setSelectedAppServices([]);
                      }}
                      className="text-red-500 hover:text-red-700 p-1"
                      title="Delete node"
                    >
                      <TrashIcon className="w-5 h-5" />
                    </button>
                  )}
                  {/* View mode selector */}
                  <button
                    onClick={cyclePropertiesPanelMode}
                    className="text-gray-400 hover:text-gray-600 p-1"
                    title={`Switch view mode (current: ${propertiesPanelMode})`}
                  >
                    {propertiesPanelMode === 'right' ? (
                      <ViewColumnsIcon className="w-5 h-5" />
                    ) : propertiesPanelMode === 'center' ? (
                      <Squares2X2Icon className="w-5 h-5" />
                    ) : (
                      <ArrowsPointingOutIcon className="w-5 h-5" />
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setShowPropertiesPanel(false);
                      setSelectedNode(null);
                      setSelectedAppServices([]);
                    }}
                    className="text-gray-400 hover:text-gray-600 text-2xl leading-none pb-1"
                  >
                    ×
                  </button>
                </div>
              </div>
              
              <ErrorBoundary resetKey={selectedNode?.id}>
                <fieldset disabled={isReadOnlyRole} className={`space-y-4 border-0 p-0 m-0 min-w-0 ${
                  propertiesPanelMode !== 'right'
                    ? 'flex-1 overflow-y-auto px-3 md:px-4 pb-4'
                    : 'px-3 md:px-4 pb-4'
                }`}>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Label
                    </label>
                    <input
                      type="text"
                      value={selectedNode?.data?.label || ''}
                      onChange={(e) => updateNodeData(selectedNode.id, { label: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary focus:border-primary"
                    />
                  </div>

                {selectedNode?.type === 'trigger' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Trigger Configuration
                      </label>
                      {(() => {
                        try {
                          return (
                            <TriggerSelector
                              applications={applications || []}
                              events={selectedAppEvents || []}
                              selectedTriggerType={selectedNode?.data?.triggerType || 'manual'}
                              selectedAppId={selectedNode?.data?.appId || null}
                              selectedEventId={selectedNode?.data?.eventId || null}
                              onTriggerTypeSelect={(triggerType) => {
                                updateNodeData(selectedNode.id, { triggerType });
                                if (triggerType !== 'application_event') {
                                  // Clear app/event selection if not application event
                                  updateNodeData(selectedNode.id, {
                                    appId: null,
                                    eventId: null,
                                    eventName: null
                                  });
                                }
                                // Set default message variable for chat_input trigger
                                if (triggerType === 'chat_input') {
                                  updateNodeData(selectedNode.id, {
                                    manualVariables: [{
                                      id: 'message',
                                      name: 'message',
                                      dataType: 'string',
                                      description: "The user's chat message",
                                      required: true,
                                      defaultValue: '',
                                      uiControl: 'textarea'
                                    }]
                                  });
                                }
                              }}
                              onApplicationSelect={(appId) => {
                                updateNodeData(selectedNode.id, { 
                                  appId, 
                                  eventId: '', 
                                  eventName: '' 
                                });
                                if (appId) {
                                  fetchAppEvents(appId);
                                }
                              }}
                              onEventSelect={(eventId) => {
                                const selectedEvent = selectedAppEvents.find(evt => evt.event_id === eventId);
                                
                                // Convert parameter mappings to eventVariables format for consistency
                                let eventVariables = [];
                                if (selectedEvent) {
                                  // Parse output_schema once — used both for explicit
                                  // mappings and as the fallback parameter source
                                  let outputSchema = selectedEvent.output_schema || {};
                                  if (typeof outputSchema === 'string') {
                                    try {
                                      outputSchema = JSON.parse(outputSchema);
                                    } catch (e) {
                                      outputSchema = {};
                                    }
                                  }

                                  // Handle both webhook and API events
                                  let parameterMappings = {};

                                  if (selectedEvent.event_type === 'webhook') {
                                    // For webhook events, use extraction_configuration.path_mappings
                                    let extractionConfig = selectedEvent.extraction_configuration || {};
                                    if (typeof extractionConfig === 'string') {
                                      try {
                                        extractionConfig = JSON.parse(extractionConfig);
                                      } catch (e) {
                                        extractionConfig = {};
                                      }
                                    }
                                    parameterMappings = extractionConfig.path_mappings || {};
                                  } else if (selectedEvent.event_type === 'api_call' || selectedEvent.event_type === 'polling' || selectedEvent.event_type === 'mqtt') {
                                    // For API, polling and MQTT events, prefer explicit extraction mappings
                                    if (outputSchema.parameter_extraction && outputSchema.parameter_extraction.mappings) {
                                      parameterMappings = outputSchema.parameter_extraction.mappings;
                                    }
                                  }

                                  const schemaProps = outputSchema.properties || {};

                                  if (Object.keys(parameterMappings).length > 0) {
                                    // Mapping-based parameters, enriched with schema info when available
                                    eventVariables = Object.entries(parameterMappings).map(([paramName, jsonPath]) => {
                                      const propSchema = schemaProps[paramName] || {};
                                      return {
                                        name: paramName,
                                        displayName: propSchema.title || paramName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                                        description: propSchema.description || `Event parameter extracted from ${jsonPath}`,
                                        type: propSchema.type || 'string',
                                        required: outputSchema.required?.includes(paramName) || false
                                      };
                                    });
                                  } else if (Object.keys(schemaProps).length > 0) {
                                    // No explicit mappings — derive parameters directly
                                    // from the event's output schema (api_call/polling/mqtt/webhook)
                                    eventVariables = Object.entries(schemaProps).map(([key, value]) => ({
                                      name: key,
                                      displayName: value.title || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
                                      description: value.description || `${value.type || 'string'} field from the ${selectedEvent.event_type} event`,
                                      type: value.type || 'string',
                                      required: outputSchema.required?.includes(key) || false
                                    }));
                                  }
                                }
                                
                                // Seed MQTT subscription defaults from the event configuration
                                let mqttEventDefaults = {};
                                if (selectedEvent?.event_type === 'mqtt') {
                                  let eventConfig = selectedEvent.event_configuration || {};
                                  if (typeof eventConfig === 'string') {
                                    try {
                                      eventConfig = JSON.parse(eventConfig);
                                    } catch (e) {
                                      eventConfig = {};
                                    }
                                  }
                                  mqttEventDefaults = {
                                    mqttTopicFilter: selectedNode.data.mqttTopicFilter || eventConfig.topic_filter || '#',
                                    mqttQos: selectedNode.data.mqttQos !== undefined ? selectedNode.data.mqttQos : (eventConfig.qos !== undefined ? eventConfig.qos : 1),
                                    mqttPayloadFormat: selectedNode.data.mqttPayloadFormat || eventConfig.payload_format || 'json'
                                  };
                                }

                                updateNodeData(selectedNode.id, {
                                  eventId,
                                  eventName: selectedEvent?.event_name || '',
                                  eventDisplayName: selectedEvent?.display_name || '',
                                  eventTriggerKind: selectedEvent?.event_type || null,
                                  eventVariables, // Add the converted variables
                                  ...mqttEventDefaults
                                });
                                
                                // Auto-set synchronous mode based on event's sync_mode
                                if (selectedEvent?.sync_mode) {
                                  if (selectedEvent.sync_mode === 'synchronous') {
                                    setIsSynchronous(true);
                                    showInfoToast('Flow set to synchronous mode based on event configuration');
                                  } else if (selectedEvent.sync_mode === 'asynchronous') {
                                    setIsSynchronous(false);
                                    showInfoToast('Flow set to asynchronous mode based on event configuration');
                                  }
                                  // If sync_mode is 'optional', don't change the current setting
                                }
                              }}
                              loadingEvents={loadingEvents}
                            />
                          );
                        } catch (error) {
                          console.error('Error rendering TriggerSelector:', error);
                          return <div className="text-red-500">Error loading trigger configuration</div>;
                        }
                      })()}
                    </div>

                    {/* Parameters supplied by the selected application event */}
                    {(selectedNode.data.triggerType === 'application_event' || selectedNode.data.triggerType === 'event') &&
                      selectedNode.data.eventId && (() => {
                        // Prefer the variables captured at event selection; fall
                        // back to deriving them from the event's output schema
                        // (flows saved before eventVariables were stored)
                        let eventParams = selectedNode.data.eventVariables || [];
                        if (eventParams.length === 0) {
                          const evt = selectedAppEvents.find(e => e.event_id === selectedNode.data.eventId);
                          let schema = evt?.output_schema || {};
                          if (typeof schema === 'string') {
                            try { schema = JSON.parse(schema); } catch (e) { schema = {}; }
                          }
                          if (schema.properties) {
                            eventParams = Object.entries(schema.properties).map(([key, value]) => ({
                              name: key,
                              displayName: value.title || key,
                              description: value.description || '',
                              type: value.type || 'string',
                              required: schema.required?.includes(key) || false
                            }));
                          }
                        }
                        if (eventParams.length === 0) {
                          return (
                            <div className="mt-4 bg-gray-50 border border-gray-200 rounded-lg p-3">
                              <p className="text-xs text-gray-500">
                                This event does not declare any output parameters.
                                The raw event payload is still available to downstream nodes.
                              </p>
                            </div>
                          );
                        }
                        return (
                          <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
                            <h4 className="text-sm font-medium text-green-800 mb-2">
                              Event Parameters ({eventParams.length})
                            </h4>
                            <p className="text-xs text-green-700 mb-2">
                              Supplied by this event and available in downstream nodes:
                            </p>
                            <div className="space-y-1.5 max-h-48 overflow-y-auto">
                              {eventParams.map((param) => (
                                <div key={param.name} className="text-xs text-green-700 flex items-start flex-wrap gap-x-2">
                                  <code className="font-mono bg-green-100 px-1.5 py-0.5 rounded whitespace-nowrap">
                                    input.{param.name}
                                  </code>
                                  <span className="text-green-600">
                                    {param.type || 'string'}{param.required ? ' · required' : ''}
                                  </span>
                                  {param.description && (
                                    <span className="w-full text-green-600 pl-1">{param.description}</span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        );
                      })()}

                    {selectedNode.data.triggerType === 'manual' && (
                      <div className="mt-4">
                        <ManualTriggerConfig
                          variables={selectedNode.data.manualVariables || []}
                          onVariablesChange={(variables) =>
                            updateNodeData(selectedNode.id, { manualVariables: variables })
                          }
                          mode="edit"
                        />
                      </div>
                    )}

                    {selectedNode.data.triggerType === 'webhook' && (
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Webhook URL
                        </label>
                        <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
                          <p className="text-sm text-gray-600 mb-2">
                            Your webhook will be available at:
                          </p>
                          <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono break-all">
                            {`${window.location.origin}/webhooks/flows/${flowId || '<flow-id>'}`}
                          </code>
                          <p className="text-xs text-gray-500 mt-2">
                            This URL will be generated after saving the flow.
                          </p>
                        </div>
                      </div>
                    )}

                    {selectedNode.data.triggerType === 'schedule' && (
                      <div className="space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-2">
                            Configure Schedule
                          </label>
                          {selectedNode.data.schedule && typeof selectedNode.data.schedule === 'object' &&
                            !scheduleToCron(selectedNode.data.schedule) && (
                            <p className="mb-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
                              Current schedule: {describeSchedule(selectedNode.data.schedule)}. Choosing a schedule below replaces it.
                            </p>
                          )}
                          <CronExpressionBuilder
                            key={selectedNode.id}
                            value={scheduleToCron(selectedNode.data.schedule) || ''}
                            onChange={(cronExpression) => updateNodeData(selectedNode.id, { schedule: cronExpression })}
                          />
                        </div>
                        
                        <div className="border-t pt-4">
                          <label className="flex items-center space-x-2">
                            <input
                              type="checkbox"
                              checked={selectedNode.data.executeImmediately !== false}
                              onChange={(e) => updateNodeData(selectedNode.id, { executeImmediately: e.target.checked })}
                              className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-primary"
                            />
                            <span className="text-sm text-gray-700">
                              Execute immediately when activated
                            </span>
                          </label>
                          <p className="text-xs text-gray-500 mt-1 ml-6">
                            When enabled, the flow will run once immediately upon activation, then follow the schedule.
                          </p>
                        </div>
                      </div>
                    )}

                    {selectedNode.data.triggerType === 'file_change' && (
                      <div className="mt-4">
                        <FileChangeTriggerConfig
                          value={{
                            folder_path: selectedNode.data.folderPath || '',
                            listener_type: selectedNode.data.listenerType || ['create', 'modify', 'delete'],
                            file_pattern: selectedNode.data.filePattern || '*',
                            recursive: selectedNode.data.recursive || false,
                            debounce_seconds: selectedNode.data.debounceSeconds || 5
                          }}
                          onChange={(config) => {
                            updateNodeData(selectedNode.id, {
                              folderPath: config.folder_path,
                              listenerType: config.listener_type,
                              filePattern: config.file_pattern,
                              recursive: config.recursive,
                              debounceSeconds: config.debounce_seconds
                            });
                          }}
                        />
                      </div>
                    )}

                    {selectedNode.data.triggerType === 'mqtt' && (
                      <div className="mt-4">
                        <MqttTriggerConfig
                          value={{
                            mqtt_host: selectedNode.data.mqttHost || '',
                            mqtt_port: selectedNode.data.mqttPort || 1883,
                            mqtt_tls: selectedNode.data.mqttTls || false,
                            mqtt_username: selectedNode.data.mqttUsername || '',
                            mqtt_password: selectedNode.data.mqttPassword || '',
                            mqtt_client_id: selectedNode.data.mqttClientId || '',
                            mqtt_topic_filter: selectedNode.data.mqttTopicFilter || '',
                            mqtt_qos: selectedNode.data.mqttQos !== undefined ? selectedNode.data.mqttQos : 1,
                            mqtt_payload_format: selectedNode.data.mqttPayloadFormat || 'json',
                            mqtt_batch_size: selectedNode.data.mqttBatchSize ?? 1,
                            mqtt_batch_window_seconds: selectedNode.data.mqttBatchWindowSeconds ?? 0,
                            mqtt_max_rate: selectedNode.data.mqttMaxRate ?? 0,
                            mqtt_rate_overflow: selectedNode.data.mqttRateOverflow || 'fold',
                            mqtt_max_concurrent: selectedNode.data.mqttMaxConcurrent ?? 0,
                            mqtt_dedup: selectedNode.data.mqttDedup || 'off',
                            mqtt_dedup_key: selectedNode.data.mqttDedupKey || '',
                            mqtt_dedup_window_seconds: selectedNode.data.mqttDedupWindowSeconds ?? 300
                          }}
                          onChange={(config) => {
                            updateNodeData(selectedNode.id, {
                              mqttHost: config.mqtt_host,
                              mqttPort: config.mqtt_port,
                              mqttTls: config.mqtt_tls,
                              mqttUsername: config.mqtt_username,
                              mqttPassword: config.mqtt_password,
                              mqttClientId: config.mqtt_client_id,
                              mqttTopicFilter: config.mqtt_topic_filter,
                              mqttQos: config.mqtt_qos,
                              mqttPayloadFormat: config.mqtt_payload_format,
                              mqttBatchSize: config.mqtt_batch_size,
                              mqttBatchWindowSeconds: config.mqtt_batch_window_seconds,
                              mqttMaxRate: config.mqtt_max_rate,
                              mqttRateOverflow: config.mqtt_rate_overflow,
                              mqttMaxConcurrent: config.mqtt_max_concurrent,
                              mqttDedup: config.mqtt_dedup,
                              mqttDedupKey: config.mqtt_dedup_key,
                              mqttDedupWindowSeconds: config.mqtt_dedup_window_seconds
                            });
                          }}
                        />
                      </div>
                    )}

                    {(selectedNode.data.triggerType === 'application_event' || selectedNode.data.triggerType === 'event') &&
                      selectedNode.data.eventTriggerKind === 'mqtt' && (
                      <div className="mt-4 space-y-4">
                        <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
                          <p className="text-sm text-blue-700">
                            <strong>MQTT Subscription:</strong> The broker address and credentials come
                            from this application's connection. Configure which topics trigger this flow below.
                          </p>
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Topic Filter
                          </label>
                          <input
                            type="text"
                            value={selectedNode.data.mqttTopicFilter || ''}
                            onChange={(e) => updateNodeData(selectedNode.id, { mqttTopicFilter: e.target.value })}
                            placeholder="home/#"
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono"
                          />
                          <p className="mt-1 text-xs text-gray-500">
                            Use <code className="font-mono">+</code> for one level, <code className="font-mono">#</code> for all remaining levels
                          </p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">QoS</label>
                            <select
                              value={selectedNode.data.mqttQos !== undefined ? selectedNode.data.mqttQos : 1}
                              onChange={(e) => updateNodeData(selectedNode.id, { mqttQos: parseInt(e.target.value) })}
                              className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                            >
                              <option value={0}>0 - At most once</option>
                              <option value={1}>1 - At least once</option>
                              <option value={2}>2 - Exactly once</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Payload Format</label>
                            <select
                              value={selectedNode.data.mqttPayloadFormat || 'json'}
                              onChange={(e) => updateNodeData(selectedNode.id, { mqttPayloadFormat: e.target.value })}
                              className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
                            >
                              <option value="json">JSON (parsed)</option>
                              <option value="plain">Plain text</option>
                            </select>
                          </div>
                        </div>

                        {/* Same Performance & Delivery section as the flat
                            MQTT trigger — both write identical trigger_config
                            keys, resolved by the shared backend logic */}
                        <MqttPerformanceSection
                          value={{
                            mqtt_batch_size: selectedNode.data.mqttBatchSize ?? 1,
                            mqtt_batch_window_seconds: selectedNode.data.mqttBatchWindowSeconds ?? 0,
                            mqtt_max_rate: selectedNode.data.mqttMaxRate ?? 0,
                            mqtt_rate_overflow: selectedNode.data.mqttRateOverflow || 'fold',
                            mqtt_max_concurrent: selectedNode.data.mqttMaxConcurrent ?? 0,
                            mqtt_dedup: selectedNode.data.mqttDedup || 'off',
                            mqtt_dedup_key: selectedNode.data.mqttDedupKey || '',
                            mqtt_dedup_window_seconds: selectedNode.data.mqttDedupWindowSeconds ?? 300
                          }}
                          onChange={(config) => {
                            updateNodeData(selectedNode.id, {
                              mqttBatchSize: config.mqtt_batch_size,
                              mqttBatchWindowSeconds: config.mqtt_batch_window_seconds,
                              mqttMaxRate: config.mqtt_max_rate,
                              mqttRateOverflow: config.mqtt_rate_overflow,
                              mqttMaxConcurrent: config.mqtt_max_concurrent,
                              mqttDedup: config.mqtt_dedup,
                              mqttDedupKey: config.mqtt_dedup_key,
                              mqttDedupWindowSeconds: config.mqtt_dedup_window_seconds
                            });
                          }}
                        />
                      </div>
                    )}

                    {selectedNode.data.triggerType === 'api_call' && (
                      <div>
                        <div className="bg-blue-50 border border-blue-200 rounded-md p-3 mb-4">
                          <p className="text-sm text-blue-700">
                            <strong>API Call Trigger:</strong> This flow will be triggered by direct API calls.
                          </p>
                        </div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          API Endpoint
                        </label>
                        <div className="bg-gray-50 border border-gray-200 rounded-md p-3">
                          <p className="text-sm text-gray-600 mb-2">
                            Your API endpoint will be available at:
                          </p>
                          <code className="text-xs bg-gray-100 px-2 py-1 rounded font-mono break-all">
                            {`${window.location.origin}/api/v1/flows/${flowId || '<flow-id>'}/trigger`}
                          </code>
                          <p className="text-xs text-gray-500 mt-2">
                            Use POST method with JSON payload to trigger this flow.
                          </p>
                        </div>
                      </div>
                    )}

                    {selectedNode.data.triggerType === 'chat_input' && (
                      <div className="space-y-4 mt-4">
                        <div className="bg-purple-50 border border-purple-200 rounded-md p-3">
                          <p className="text-sm text-purple-700">
                            <strong>Chat Input Trigger:</strong> This flow provides a chat interface for conversational interactions with AI agents.
                          </p>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Welcome Message
                          </label>
                          <textarea
                            value={selectedNode.data.welcomeMessage || ''}
                            onChange={(e) => updateNodeData(selectedNode.id, { welcomeMessage: e.target.value })}
                            placeholder="Hello! How can I help you today?"
                            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            rows={2}
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            This message will be displayed when the chat opens.
                          </p>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Placeholder Text
                          </label>
                          <input
                            type="text"
                            value={selectedNode.data.placeholderText || ''}
                            onChange={(e) => updateNodeData(selectedNode.id, { placeholderText: e.target.value })}
                            placeholder="Type your message..."
                            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            Placeholder text shown in the input field.
                          </p>
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Available Variables
                          </label>
                          <div className="bg-gray-50 border border-gray-200 rounded-md p-3 space-y-1">
                            <div className="text-xs text-blue-600 font-mono bg-blue-50 px-2 py-1 rounded">input.message</div>
                            <div className="text-xs text-blue-600 font-mono bg-blue-50 px-2 py-1 rounded">input.session_id</div>
                            <div className="text-xs text-gray-600 font-mono bg-gray-100 px-2 py-1 rounded">input.is_first_message</div>
                          </div>
                          <p className="text-xs text-gray-500 mt-1">
                            Use these variables in downstream nodes to access chat data.
                          </p>
                        </div>
                      </div>
                    )}
                  </>
                )}

                {selectedNode.type === 'action' && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Application & Service
                      </label>
                      <ApplicationServiceSelector
                        applications={applications}
                        services={selectedAppServices}
                        selectedAppId={selectedNode.data.appId}
                        selectedServiceId={selectedNode.data.serviceId}
                        onApplicationSelect={(appId) => {
                          updateNodeData(selectedNode.id, { appId, serviceId: null });
                          fetchAppServices(appId);
                        }}
                        onServiceSelect={(serviceId) => {
                          updateNodeData(selectedNode.id, { serviceId });
                        }}
                        loadingServices={loadingServices}
                      />
                    </div>
                    
                    {/* Service Parameters */}
                    {selectedNode.data.serviceId && (
                      <div>
                        {(() => {
                          const service = selectedAppServices.find(s => s.service_id === selectedNode.data.serviceId);

                          const hasParameterSchema = (service?.service_config?.request_config?.parameter_method || service?.service_config?.parameter_method) &&
                                                    (service?.parameters || service?.service_config?.parameters || service?.service_config?.parameter_schema);

                          if (hasParameterSchema) {
                            // Get parameters schema (could be in different locations)
                            const parametersSchema = service.parameters ||
                                                   service.service_config?.parameters ||
                                                   service.service_config?.parameter_schema ||
                                                   service.parameter_schema;

                            // Build target schema in the format ParameterMapper expects
                            const targetSchema = {
                              fields: Array.isArray(parametersSchema) ? parametersSchema : null,
                              properties: parametersSchema?.properties || service.input_schema?.properties,
                              pattern: service.url_pattern || service.service_config?.url_pattern || service.service_config?.endpoint_template,
                              required: parametersSchema?.required || []
                            };

                            // Use new parameter mapper
                            // Use parameterMapping if it has values, otherwise use parameters
                            const initialMapping = (selectedNode.data.parameterMapping && Object.keys(selectedNode.data.parameterMapping).length > 0)
                              ? selectedNode.data.parameterMapping
                              : selectedNode.data.parameters || {};
                            const availableVars = getAvailableVariables(selectedNode.id);

                            return (
                              <ParameterMapper
                                sourceSchema={getPreviousNodeOutputSchema()}
                                targetSchema={targetSchema}
                                parameterMethod={service.service_config?.request_config?.parameter_method || service.service_config?.parameter_method}
                                initialMapping={initialMapping}
                                availableVariables={availableVars}
                                subscriptionId={appSubscription?.subscription_id}
                                onMappingChange={(mapping) => {
                                  // Only update parameterMapping (parameters is deprecated)
                                  updateNodeData(selectedNode.id, { 
                                    parameterMapping: mapping
                                  });
                                }}
                                mode="edit"
                                isCompact={propertiesPanelMode === 'right'}
                              />
                            );
                          } else {
                            // Fallback to old parameter form
                            return (
                              <ParameterForm
                                serviceId={selectedNode.data.serviceId}
                                parameters={selectedNode.data.parameters || {}}
                                onParametersChange={(params) => {
                                  updateNodeData(selectedNode.id, { 
                                    parameters: params,
                                    parametersRaw: JSON.stringify(params, null, 2),
                                    useParameterMapping: false // Explicitly false when using raw parameter form
                                  });
                                }}
                                inputSchema={service?.input_schema || null}
                                availableVariables={getAvailableVariables(selectedNode.id)}
                                subscriptionId={appSubscription?.subscription_id}
                              />
                            );
                          }
                        })()}
                      </div>
                    )}
                  </>
                )}

                {selectedNode.type === 'condition' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Condition Expression
                    </label>
                    <ConditionBuilder
                      expression={selectedNode.data.expression || ''}
                      onExpressionChange={(expression) => updateNodeData(selectedNode.id, { expression })}
                      availableVariables={getAvailableVariables(selectedNode.id)}
                      mode="edit"
                    />
                  </div>
                )}

                {selectedNode.type === 'loop' && (
                  <LoopConfig
                    node={selectedNode}
                    updateNodeData={updateNodeData}
                    flowContext={getAvailableVariables(selectedNode.id)}
                  />
                )}

                {selectedNode.type === 'transform' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Transform Script
                      </label>
                      
                      {/* Script template buttons */}
                      <div className="mb-2 flex flex-wrap gap-2">
                        <button
                          onClick={() => {
                            const templates = {
                              basic: `# Basic transformation
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['timestamp'] = str(input.get('timestamp', ''))
output['processed'] = True`,
                              loop: `# Process list with loop
local['items'] = []
local['total'] = 0

for item in input.get('items', []):
    if item.get('active'):
        local['items'].append({
            'id': item['id'],
            'name': string['upper'](item['name']),
            'price': item['price']
        })
        local['total'] = math['add'](local['total'], item['price'])

output['filtered_items'] = local['items']
output['total_price'] = local['total']
output['count'] = len(local['items'])`,
                              string: `# String operations
local['first_name'] = input.get('first_name', '')
local['last_name'] = input.get('last_name', '')

# Create full name
local['full_name'] = string['join'](' ', [local['first_name'], local['last_name']])

# Create email
local['email_name'] = string['lower'](string['replace'](local['full_name'], ' ', '.'))
output['email'] = f"{local['email_name']}@example.com"

# Create initials
output['initials'] = string['upper'](
    local['first_name'][:1] + local['last_name'][:1]
)

output['full_name'] = local['full_name']`,
                              aggregate: `# Data aggregation
local['values'] = input.get('values', [])
local['sum'] = 0
local['count'] = 0

for value in local['values']:
    if isinstance(value, (int, float)):
        local['sum'] = math['add'](local['sum'], value)
        local['count'] = math['add'](local['count'], 1)

# Calculate statistics
output['sum'] = local['sum']
output['count'] = local['count']
output['average'] = math['divide'](local['sum'], local['count']) if local['count'] > 0 else 0
output['min'] = min(local['values']) if local['values'] else None
output['max'] = max(local['values']) if local['values'] else None

# Store in global for other nodes
set_global('statistics', output)`
                            };
                            updateNodeData(selectedNode.id, { script: templates.basic });
                          }}
                          className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                        >
                          Basic
                        </button>
                        <button
                          onClick={() => {
                            const templates = {
                              basic: `# Basic transformation
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['timestamp'] = str(input.get('timestamp', ''))
output['processed'] = True`,
                              loop: `# Process list with loop
local['items'] = []
local['total'] = 0

for item in input.get('items', []):
    if item.get('active'):
        local['items'].append({
            'id': item['id'],
            'name': string['upper'](item['name']),
            'price': item['price']
        })
        local['total'] = math['add'](local['total'], item['price'])

output['filtered_items'] = local['items']
output['total_price'] = local['total']
output['count'] = len(local['items'])`,
                              string: `# String operations
local['first_name'] = input.get('first_name', '')
local['last_name'] = input.get('last_name', '')

# Create full name
local['full_name'] = string['join'](' ', [local['first_name'], local['last_name']])

# Create email
local['email_name'] = string['lower'](string['replace'](local['full_name'], ' ', '.'))
output['email'] = f"{local['email_name']}@example.com"

# Create initials
output['initials'] = string['upper'](
    local['first_name'][:1] + local['last_name'][:1]
)

output['full_name'] = local['full_name']`,
                              aggregate: `# Data aggregation
local['values'] = input.get('values', [])
local['sum'] = 0
local['count'] = 0

for value in local['values']:
    if isinstance(value, (int, float)):
        local['sum'] = math['add'](local['sum'], value)
        local['count'] = math['add'](local['count'], 1)

# Calculate statistics
output['sum'] = local['sum']
output['count'] = local['count']
output['average'] = math['divide'](local['sum'], local['count']) if local['count'] > 0 else 0
output['min'] = min(local['values']) if local['values'] else None
output['max'] = max(local['values']) if local['values'] else None

# Store in global for other nodes
set_global('statistics', output)`
                            };
                            updateNodeData(selectedNode.id, { script: templates.loop });
                          }}
                          className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                        >
                          Loop
                        </button>
                        <button
                          onClick={() => {
                            const templates = {
                              basic: `# Basic transformation
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['timestamp'] = str(input.get('timestamp', ''))
output['processed'] = True`,
                              loop: `# Process list with loop
local['items'] = []
local['total'] = 0

for item in input.get('items', []):
    if item.get('active'):
        local['items'].append({
            'id': item['id'],
            'name': string['upper'](item['name']),
            'price': item['price']
        })
        local['total'] = math['add'](local['total'], item['price'])

output['filtered_items'] = local['items']
output['total_price'] = local['total']
output['count'] = len(local['items'])`,
                              string: `# String operations
local['first_name'] = input.get('first_name', '')
local['last_name'] = input.get('last_name', '')

# Create full name
local['full_name'] = string['join'](' ', [local['first_name'], local['last_name']])

# Create email
local['email_name'] = string['lower'](string['replace'](local['full_name'], ' ', '.'))
output['email'] = f"{local['email_name']}@example.com"

# Create initials
output['initials'] = string['upper'](
    local['first_name'][:1] + local['last_name'][:1]
)

output['full_name'] = local['full_name']`,
                              aggregate: `# Data aggregation
local['values'] = input.get('values', [])
local['sum'] = 0
local['count'] = 0

for value in local['values']:
    if isinstance(value, (int, float)):
        local['sum'] = math['add'](local['sum'], value)
        local['count'] = math['add'](local['count'], 1)

# Calculate statistics
output['sum'] = local['sum']
output['count'] = local['count']
output['average'] = math['divide'](local['sum'], local['count']) if local['count'] > 0 else 0
output['min'] = min(local['values']) if local['values'] else None
output['max'] = max(local['values']) if local['values'] else None

# Store in global for other nodes
set_global('statistics', output)`
                            };
                            updateNodeData(selectedNode.id, { script: templates.string });
                          }}
                          className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                        >
                          String Ops
                        </button>
                        <button
                          onClick={() => {
                            const templates = {
                              basic: `# Basic transformation
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['timestamp'] = str(input.get('timestamp', ''))
output['processed'] = True`,
                              loop: `# Process list with loop
local['items'] = []
local['total'] = 0

for item in input.get('items', []):
    if item.get('active'):
        local['items'].append({
            'id': item['id'],
            'name': string['upper'](item['name']),
            'price': item['price']
        })
        local['total'] = math['add'](local['total'], item['price'])

output['filtered_items'] = local['items']
output['total_price'] = local['total']
output['count'] = len(local['items'])`,
                              string: `# String operations
local['first_name'] = input.get('first_name', '')
local['last_name'] = input.get('last_name', '')

# Create full name
local['full_name'] = string['join'](' ', [local['first_name'], local['last_name']])

# Create email
local['email_name'] = string['lower'](string['replace'](local['full_name'], ' ', '.'))
output['email'] = f"{local['email_name']}@example.com"

# Create initials
output['initials'] = string['upper'](
    local['first_name'][:1] + local['last_name'][:1]
)

output['full_name'] = local['full_name']`,
                              aggregate: `# Data aggregation
local['values'] = input.get('values', [])
local['sum'] = 0
local['count'] = 0

for value in local['values']:
    if isinstance(value, (int, float)):
        local['sum'] = math['add'](local['sum'], value)
        local['count'] = math['add'](local['count'], 1)

# Calculate statistics
output['sum'] = local['sum']
output['count'] = local['count']
output['average'] = math['divide'](local['sum'], local['count']) if local['count'] > 0 else 0
output['min'] = min(local['values']) if local['values'] else None
output['max'] = max(local['values']) if local['values'] else None

# Store in global for other nodes
set_global('statistics', output)`
                            };
                            updateNodeData(selectedNode.id, { script: templates.aggregate });
                          }}
                          className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                        >
                          Aggregate
                        </button>
                      </div>
                      
                      <EnhancedTransformCodeEditor
                        value={selectedNode.data.script || ''}
                        onChange={(value) => updateNodeData(selectedNode.id, { script: value })}
                        availableVariables={getAvailableVariables(selectedNode.id)}
                        placeholder={`# Available objects: input, local, global, node_outputs, output, string, math
# Example:
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['count'] = len(input.get('items', []))
set_global('name', 'hello world')  # Set a global variable
local['value'] = global.get('name', 'default')  # Read a global variable`}
                        theme="light"
                        flowContext={{
                          flowName: flowData?.flow_name || 'Untitled Flow',
                          flowId: flowId
                        }}
                        nodeContext={{
                          label: selectedNode.data.label || 'Transform Node',
                          description: selectedNode.data.description || '',
                          nodeId: selectedNode.id
                        }}
                        nextNodeInfo={getNextNodeInfo(selectedNode.id)}
                      />
                    </div>
                  </div>
                )}

                {selectedNode.type === 'human_in_loop' && (
                  <HumanInLoopConfig
                    node={selectedNode}
                    updateNodeData={updateNodeData}
                    availableVariables={getAvailableVariables(selectedNode.id)}
                  />
                )}

                {selectedNode.type === 'wait_for_event' && (
                  <WaitForEventConfig
                    node={selectedNode}
                    updateNodeData={updateNodeData}
                    availableVariables={getAvailableVariables(selectedNode.id)}
                    applications={applications}
                    events={selectedAppEvents}
                    loadingEvents={loadingEvents}
                  />
                )}

                {selectedNode.type === 'response' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-medium text-gray-900">Response Configuration</h3>
                    
                    {/* Response Data */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Response Data
                      </label>
                      <ParameterInput
                        name="response"
                        value={selectedNode.data.variable || ''}
                        onChange={(value) => updateNodeData(selectedNode.id, { variable: value })}
                        type="any"
                        placeholder="Select variable or enter value"
                        description="The data to return from this flow. Can be a variable reference or a static value."
                        availableVariables={getAvailableVariables(selectedNode.id)}
                        mode="edit"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Examples: {`{{node_outputs.transform_1}}, {{global.name}}, "Success", {status: "ok"}`}
                      </p>
                    </div>
                    
                    {/* Status Code */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        HTTP Status Code
                      </label>
                      <ParameterInput
                        name="statusCode"
                        value={selectedNode.data.statusCode || 200}
                        onChange={(value) => updateNodeData(selectedNode.id, { statusCode: value })}
                        type="number"
                        placeholder="200"
                        description="HTTP status code to return (e.g., 200 for success, 400 for bad request)"
                        availableVariables={getAvailableVariables(selectedNode.id)}
                        mode="edit"
                      />
                    </div>
                    
                    {/* Response Headers (Optional) */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Response Headers (Optional)
                      </label>
                      <ParameterInput
                        name="headers"
                        value={selectedNode.data.headers || ''}
                        onChange={(value) => updateNodeData(selectedNode.id, { headers: value })}
                        type="object"
                        placeholder='{"Content-Type": "application/json"}'
                        description="Additional HTTP headers to include in the response"
                        availableVariables={getAvailableVariables(selectedNode.id)}
                        mode="edit"
                      />
                    </div>
                    
                    {/* Output Format (Optional) */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Output Format (Optional)
                      </label>
                      <select
                        value={selectedNode.data.outputFormat || 'text'}
                        onChange={(e) => updateNodeData(selectedNode.id, { outputFormat: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500 text-sm"
                      >
                        <option value="text">Text (default)</option>
                        <option value="json">JSON</option>
                        <option value="html">HTML</option>
                        <option value="xml">XML</option>
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        Format for displaying the response output. Defaults to text if not specified.
                      </p>
                    </div>

                    {/* Output Fields (for API docs) */}
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <label className="block text-sm font-medium text-gray-700">
                          Output Fields (for API Docs)
                        </label>
                        <button
                          type="button"
                          onClick={() => {
                            const fields = Array.isArray(selectedNode.data.outputFields) ? [...selectedNode.data.outputFields] : [];
                            fields.push({ name: '', type: 'string', description: '', example: '' });
                            updateNodeData(selectedNode.id, { outputFields: fields });
                          }}
                          className="text-xs font-medium text-primary hover:text-primary/80"
                        >
                          + Add Field
                        </button>
                      </div>
                      <p className="mb-2 text-xs text-gray-500">
                        Describe the structure of this response for the generated API documentation. When the output is a plain value, leave this empty.
                      </p>
                      {(selectedNode.data.outputFields || []).length === 0 ? (
                        <p className="text-xs italic text-gray-400 py-2">
                          No fields defined. The sync response will show a generic placeholder in the API docs.
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {(selectedNode.data.outputFields || []).map((field, idx) => (
                            <div key={idx} className="rounded-md border border-gray-200 p-2 bg-gray-50">
                              <div className="flex items-center gap-2 mb-2">
                                <input
                                  type="text"
                                  value={field.name || ''}
                                  placeholder="field_name"
                                  onChange={(e) => {
                                    const fields = [...(selectedNode.data.outputFields || [])];
                                    fields[idx] = { ...fields[idx], name: e.target.value };
                                    updateNodeData(selectedNode.id, { outputFields: fields });
                                  }}
                                  className="flex-1 px-2 py-1 border border-gray-300 rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                                />
                                <select
                                  value={field.type || 'string'}
                                  onChange={(e) => {
                                    const fields = [...(selectedNode.data.outputFields || [])];
                                    fields[idx] = { ...fields[idx], type: e.target.value };
                                    updateNodeData(selectedNode.id, { outputFields: fields });
                                  }}
                                  className="px-2 py-1 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                                >
                                  <option value="string">string</option>
                                  <option value="number">number</option>
                                  <option value="boolean">boolean</option>
                                  <option value="object">object</option>
                                  <option value="array">array</option>
                                </select>
                                <button
                                  type="button"
                                  onClick={() => {
                                    const fields = [...(selectedNode.data.outputFields || [])];
                                    fields.splice(idx, 1);
                                    updateNodeData(selectedNode.id, { outputFields: fields });
                                  }}
                                  className="text-xs font-medium text-red-500 hover:text-red-700 px-1"
                                  title="Remove field"
                                >
                                  &times;
                                </button>
                              </div>
                              <input
                                type="text"
                                value={field.description || ''}
                                placeholder="Description"
                                onChange={(e) => {
                                  const fields = [...(selectedNode.data.outputFields || [])];
                                  fields[idx] = { ...fields[idx], description: e.target.value };
                                  updateNodeData(selectedNode.id, { outputFields: fields });
                                }}
                                className="w-full px-2 py-1 mb-2 border border-gray-300 rounded text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                              />
                              <input
                                type="text"
                                value={field.example ?? ''}
                                placeholder="Example value (shown in the API docs sample)"
                                onChange={(e) => {
                                  const fields = [...(selectedNode.data.outputFields || [])];
                                  fields[idx] = { ...fields[idx], example: e.target.value };
                                  updateNodeData(selectedNode.id, { outputFields: fields });
                                }}
                                className="w-full px-2 py-1 border border-gray-300 rounded text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                              />
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Node error handling: retry, continue, error branch */}
                {selectedNode.type !== 'trigger' && (
                  <NodeErrorHandlingConfig
                    node={selectedNode}
                    updateNodeData={updateNodeData}
                    onErrorBranchDisabled={removeErrorEdges}
                  />
                )}
                </fieldset>
              </ErrorBoundary>
            </div>
            </>,
            document.body
          )}
        </div>

        {/* JSON Editor Modal */}
        <EnhancedJsonEditor
          isOpen={showJsonEditor}
          onClose={() => {
            setShowJsonEditor(false);
            setViewSourceData(null);
          }}
          flowData={viewSourceData || {
            version: '1.0',
            export_timestamp: new Date().toISOString(),
            flow: {
              flow_name: flowName || 'Untitled Flow',
              description: flowDescription || '',
              category: flowCategory || 'general',
              trigger_config: {},
              flow_definition: {
                nodes: nodes,
                edges: edges
              },
              is_synchronous: isSynchronous,
              sync_timeout: syncTimeout
            },
            metadata: {
              required_applications: [],
              source_instance: {
                mode: 'view_source'
              },
              warnings: []
            }
          }}
          onSave={handleJsonSave}
          readOnly={false}
        />
        
        {/* Flow Settings Modal */}
        <div 
          id="flow-settings-modal" 
          className="hidden fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-[9998]"
          onClick={(e) => {
            if (e.target.id === 'flow-settings-modal') {
              e.target.classList.add('hidden');
            }
          }}
        >
          <div className="relative top-20 mx-auto p-5 border w-[480px] max-w-[90vw] shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Flow Settings</h3>
                <button
                  onClick={() => document.getElementById('flow-settings-modal').classList.add('hidden')}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <span className="sr-only">Close</span>
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <fieldset disabled={isReadOnlyRole} className="space-y-4 border-0 p-0 m-0 min-w-0">
                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={flowDescription}
                    onChange={(e) => setFlowDescription(e.target.value)}
                    placeholder="Describe what this flow does..."
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500"
                    rows="3"
                  />
                </div>
                
                {/* Category */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Category
                  </label>
                  <input
                    type="text"
                    value={flowCategory}
                    onChange={(e) => setFlowCategory(e.target.value)}
                    placeholder="e.g., Data Processing, Notifications, etc."
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500"
                  />
                </div>
                
                {/* Flow Scope */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Flow Scope
                  </label>
                  <select
                    value={flowScope}
                    onChange={(e) => setFlowScope(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500"
                  >
                    <option value="user">User (Private)</option>
                    <option value="tenant">Tenant (Team)</option>
                    <option value="global">Global (Everyone)</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    {flowScope === 'user' ? 'Only you can see and use this flow' : 
                     flowScope === 'tenant' ? 'All users in your organization can see and use this flow' : 
                     'All users across all organizations can see and use this flow'}
                  </p>
                </div>
                
                {/* Sync Mode */}
                <div>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={isSynchronous}
                      onChange={(e) => {
                        // Check if there's an event trigger with sync_mode set
                        const triggerNode = nodes.find(n => n.type === 'trigger');
                        if (triggerNode?.data?.eventId && triggerNode?.data?.triggerType === 'application_event') {
                          const event = selectedAppEvents.find(evt => evt.event_id === triggerNode.data.eventId);
                          // Only restrict if sync_mode is explicitly defined and not optional
                          if (event?.sync_mode && event.sync_mode !== 'optional') {
                            // Allow override with confirmation
                            const mode = event.sync_mode === 'synchronous' ? 'synchronous' : 'asynchronous';
                            const override = window.confirm(
                              `This event (${event.display_name || event.event_name}) is configured for ${mode} execution.\n\n` +
                              'Are you sure you want to override this setting? This may cause unexpected behavior.'
                            );
                            if (!override) {
                              return;
                            }
                            showWarningToast(`Overriding event's ${mode} mode setting`);
                          }
                        }
                        setIsSynchronous(e.target.checked);
                      }}
                      className="mr-2 text-primary"
                    />
                    <span className="text-sm font-medium text-gray-700">Synchronous Execution</span>
                  </label>
                  <p className="text-xs text-gray-500 mt-1 ml-6">
                    When enabled, the flow will wait for completion and return the result
                  </p>
                  
                  {(() => {
                    const triggerNode = nodes.find(n => n.type === 'trigger');
                    if (triggerNode?.data?.eventId && triggerNode?.data?.triggerType === 'application_event') {
                      const event = selectedAppEvents.find(evt => evt.event_id === triggerNode.data.eventId);
                      // Only show indicator if sync_mode is explicitly defined and not optional
                      if (event?.sync_mode && event.sync_mode !== 'optional') {
                        const isInherited = (event.sync_mode === 'synchronous') === isSynchronous;
                        return (
                          <div className={`mt-2 text-xs px-2 py-1 rounded ${isInherited ? 'bg-blue-50 text-blue-700' : 'bg-orange-50 text-orange-700'}`}>
                            {isInherited 
                              ? `✓ Inherited from event: ${event.sync_mode}`
                              : `⚠️ Override: Event expects ${event.sync_mode} mode`
                            }
                          </div>
                        );
                      }
                    }
                    return null;
                  })()}
                </div>
                
                {/* Timeout */}
                {isSynchronous && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Timeout (seconds)
                    </label>
                    <input
                      type="number"
                      value={syncTimeout}
                      onChange={(e) => setSyncTimeout(parseInt(e.target.value) || 30)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500"
                      min="1"
                      max="300"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Maximum time to wait for flow completion (1-300 seconds)
                    </p>
                  </div>
                )}

                {/* Execution Logging (all trigger types) */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Execution Logging
                  </label>
                  <select
                    value={executionLogLevel}
                    onChange={(e) => setExecutionLogLevel(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500"
                  >
                    <option value="full">Full (default) — detailed per-step logs</option>
                    <option value="node_summary">Node summary — one line per node</option>
                    <option value="errors_only">Errors only — log only when the flow fails</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">
                    {executionLogLevel === 'full' && 'Every step logs inputs, outputs and timing. Best for design and debugging.'}
                    {executionLogLevel === 'node_summary' && 'One line per node (name, status, summary). Recommended for high-frequency flows.'}
                    {executionLogLevel === 'errors_only' && 'Nothing is stored while the flow succeeds; on failure the buffered logs of the failing run are written.'}
                  </p>

                  {executionLogLevel !== 'errors_only' && (
                    <div className="mt-3">
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Log Sample Rate
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="1"
                        step="0.01"
                        value={logSampleRate}
                        onChange={(e) => {
                          const parsed = parseFloat(e.target.value);
                          setLogSampleRate(Number.isNaN(parsed) ? 1.0 : Math.min(1, Math.max(0, parsed)));
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Fraction of executions logged at the level above (1 = all). Unsampled executions log errors only. Useful for high-frequency flows.
                      </p>
                    </div>
                  )}
                </div>

                {/* Error handler flow */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Error Handler Flow
                  </label>
                  <select
                    value={errorHandlerFlowId}
                    onChange={(e) => setErrorHandlerFlowId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-blue-500"
                  >
                    <option value="">None</option>
                    {errorHandlerFlowOptions
                      .filter(f => f.flow_id !== flowId)
                      .map(f => (
                        <option key={f.flow_id} value={f.flow_id}>{f.flow_name}</option>
                      ))}
                    {errorHandlerFlowId && !errorHandlerFlowOptions.some(f => f.flow_id === errorHandlerFlowId) && (
                      <option value={errorHandlerFlowId}>{errorHandlerFlowId} (not found)</option>
                    )}
                  </select>
                  {errorHandlerFlowsFailed && (
                    <p className="text-xs text-red-600 mt-1">Couldn't load the flow list.</p>
                  )}
                  <p className="text-xs text-gray-500 mt-1">
                    Starts when this flow fails with an error no node handled. It receives <code>{'{{input.error.message}}'}</code>, <code>{'{{input.error.node_id}}'}</code>, <code>{'{{input.execution.execution_id}}'}</code> and <code>{'{{input.flow.flow_name}}'}</code>. Save the flow to apply.
                  </p>
                </div>

                {/* Flow Information - Read Only at Bottom */}
                {flowData && isEditMode && (
                  <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                    <h4 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-3">Flow Information</h4>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                      <div className="flex items-start space-x-2">
                        <CalendarIcon className="h-4 w-4 text-gray-400 mt-0.5" />
                        <div>
                          <span className="text-gray-500 text-xs block">Created</span>
                          <div className="text-gray-900 text-xs font-medium">
                            {new Date(flowData.created_at).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric'
                            })}
                            {' '}
                            {new Date(flowData.created_at).toLocaleTimeString('en-US', {
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <UserIcon className="h-4 w-4 text-gray-400 mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <span className="text-gray-500 text-xs block">Created By</span>
                          <div className="text-gray-900 text-xs font-medium truncate" title={flowData.created_by_user?.email || flowData.created_by}>
                            {flowData.created_by_user?.user_name || flowData.created_by || 'Unknown'}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <PencilSquareIcon className="h-4 w-4 text-gray-400 mt-0.5" />
                        <div>
                          <span className="text-gray-500 text-xs block">Last Modified</span>
                          <div className="text-gray-900 text-xs font-medium">
                            {new Date(flowData.updated_at).toLocaleDateString('en-US', {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric'
                            })}
                            {' '}
                            {new Date(flowData.updated_at).toLocaleTimeString('en-US', {
                              hour: '2-digit',
                              minute: '2-digit'
                            })}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-start space-x-2">
                        <UserIcon className="h-4 w-4 text-gray-400 mt-0.5" />
                        <div className="min-w-0 flex-1">
                          <span className="text-gray-500 text-xs block">Modified By</span>
                          <div className="text-gray-900 text-xs font-medium truncate" title={flowData.last_modified_by_user?.email || flowData.last_modified_by}>
                            {flowData.last_modified_by_user?.user_name ||
                             flowData.last_modified_by ||
                             flowData.created_by_user?.user_name ||
                             flowData.created_by ||
                             'Unknown'}
                          </div>
                        </div>
                      </div>
                      {flowData.execution_count !== undefined && (
                        <>
                          <div className="flex items-start space-x-2">
                            <BoltIcon className="h-4 w-4 text-gray-400 mt-0.5" />
                            <div>
                              <span className="text-gray-500 text-xs block">Executions</span>
                              <div className="text-gray-900 text-xs font-medium">{flowData.execution_count || 0}</div>
                            </div>
                          </div>
                          <div className="flex items-start space-x-2">
                            <ClockIcon className="h-4 w-4 text-gray-400 mt-0.5" />
                            <div>
                              <span className="text-gray-500 text-xs block">Last Run</span>
                              <div className="text-gray-900 text-xs font-medium">
                                {flowData.last_execution_at
                                  ? new Date(flowData.last_execution_at).toLocaleDateString('en-US', {
                                      year: 'numeric',
                                      month: 'short',
                                      day: 'numeric'
                                    }) + ' ' +
                                    new Date(flowData.last_execution_at).toLocaleTimeString('en-US', {
                                      hour: '2-digit',
                                      minute: '2-digit'
                                    })
                                  : 'Never'}
                              </div>
                            </div>
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </fieldset>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => document.getElementById('flow-settings-modal').classList.add('hidden')}
                  className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
        
        {/* Flow Status Modal */}
        {isEditMode && (
          <div 
            id="flow-status-modal" 
            className="hidden fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full z-[9998]"
            onClick={(e) => {
              if (e.target.id === 'flow-status-modal') {
                e.target.classList.add('hidden');
              }
            }}
          >
            <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
              <div className="mt-3">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900">Flow Status</h3>
                  <button
                    onClick={() => document.getElementById('flow-status-modal').classList.add('hidden')}
                    className="text-gray-400 hover:text-gray-500"
                  >
                    <span className="sr-only">Close</span>
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                
                <div className="space-y-4">
                  <div>
                    <p className="text-sm text-gray-600 mb-3">
                      Current Status: 
                      <span className={`ml-2 px-2 py-1 text-xs rounded-full font-medium ${
                        flowStatus === 'active' ? 'bg-green-100 text-green-800' :
                        flowStatus === 'inactive' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {flowStatus}
                      </span>
                    </p>
                    
                    <div className="space-y-2">
                      {flowStatus === 'draft' && (
                        <button
                          onClick={() => {
                            updateFlowStatusMutation.mutate('active');
                            document.getElementById('flow-status-modal').classList.add('hidden');
                          }}
                          className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                          disabled={updateFlowStatusMutation.isPending}
                        >
                          Activate Flow
                        </button>
                      )}
                      
                      {flowStatus === 'active' && (
                        <>
                          <button
                            onClick={() => {
                              updateFlowStatusMutation.mutate('inactive');
                              document.getElementById('flow-status-modal').classList.add('hidden');
                            }}
                            className="w-full px-4 py-2 bg-yellow-600 text-white rounded-md hover:bg-yellow-700"
                            disabled={updateFlowStatusMutation.isPending}
                          >
                            Deactivate Flow
                          </button>
                          <button
                            onClick={() => {
                              if (window.confirm('Are you sure you want to cancel this flow? It will be set back to draft status.')) {
                                updateFlowStatusMutation.mutate('draft');
                                document.getElementById('flow-status-modal').classList.add('hidden');
                              }
                            }}
                            className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                            disabled={updateFlowStatusMutation.isPending}
                          >
                            Cancel Flow
                          </button>
                        </>
                      )}
                      
                      {flowStatus === 'inactive' && (
                        <>
                          <button
                            onClick={() => {
                              updateFlowStatusMutation.mutate('active');
                              document.getElementById('flow-status-modal').classList.add('hidden');
                            }}
                            className="w-full px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                            disabled={updateFlowStatusMutation.isPending}
                          >
                            Reactivate Flow
                          </button>
                          <button
                            onClick={() => {
                              if (window.confirm('Are you sure you want to cancel this flow? It will be set back to draft status.')) {
                                updateFlowStatusMutation.mutate('draft');
                                document.getElementById('flow-status-modal').classList.add('hidden');
                              }
                            }}
                            className="w-full px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
                            disabled={updateFlowStatusMutation.isPending}
                          >
                            Cancel Flow
                          </button>
                        </>
                      )}
                    </div>
                    
                    <div className="mt-4 p-3 bg-gray-50 rounded-md">
                      <p className="text-xs text-gray-600">
                        <strong>Status Guide:</strong><br/>
                        • <span className="font-medium">Draft:</span> Flow is being edited and not active<br/>
                        • <span className="font-medium">Active:</span> Flow is running and processing triggers<br/>
                        • <span className="font-medium">Inactive:</span> Flow is paused and not processing
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Hidden file input for import */}
        <input
          id="import-flow-input"
          type="file"
          accept=".json,application/json"
          onChange={handleFlowImport}
          style={{ display: 'none' }}
        />
        
        {/* Collaboration Overlays */}
        {isCollaborating && (
          <>
            {/* Collaborative Cursors */}
            <CollaborativeCursors 
              participants={participants}
              containerRef={flowCanvasRef}
            />
            
            {/* Collaborative Selections */}
            <CollaborativeSelections
              participants={participants}
              nodes={nodes}
              edges={edges}
            />
            
          </>
        )}
        
        {/* Invite Dialog */}
        {showInviteDialog && (
          <InviteDialog
            sessionInfo={collaborationSession || sessionInfo}
            shareLink={collaborationSession?.share_link || sessionInfo?.share_link}
            onInvite={async (inviteData) => {
              try {
                const currentSession = collaborationSession || sessionInfo;
                const response = await axios.post(
                  `/api/v1/collaborate/session/${currentSession.session_id}/invite`,
                  inviteData,
                  {
                    headers: {
                      'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                    }
                  }
                );
                
                showSuccessToast('Invite sent successfully');
                return response.data;
              } catch (error) {
                showErrorToast('Failed to send invite');
                throw error;
              }
            }}
            onClose={() => setShowInviteDialog(false)}
          />
        )}
        
        {/* Participants List */}
        {showParticipantsList && (
          <div className="absolute top-20 right-4 z-[1000]">
            <ParticipantsList
              participants={participants}
              currentUserId={user?.user_id || user?.id}
              currentUserEmail={user?.email}
              currentUserName={user?.username}
              onClose={() => setShowParticipantsList(false)}
            />
          </div>
        )}

        {/* Application Installation Wizard */}
        <ApplicationInstallationWizard
          open={wizardOpen}
          onClose={() => setWizardOpen(false)}
          validationData={validationData}
          flowName={validationData?.flow_name || 'Imported Flow'}
          onAllAppsReady={handleAllAppsReady}
        />

        {/* Interactive Tutorial for first-time users */}
        <FlowTutorial
          run={runTutorial}
          onComplete={handleTutorialComplete}
        />
      </div>
  );
};

const FlowDesigner = () => {
  return (
    <ReactFlowProvider>
      <FlowContent />
    </ReactFlowProvider>
  );
};

export default FlowDesigner;