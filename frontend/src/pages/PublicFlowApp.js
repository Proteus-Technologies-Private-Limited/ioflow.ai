import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  ReactFlowProvider,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  PlayIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  DocumentTextIcon,
  GlobeAltIcon,
  ClockIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  BoltIcon,
  CogIcon,
  ArrowPathRoundedSquareIcon,
  ArrowsRightLeftIcon,
  PaperAirplaneIcon,
  CommandLineIcon
} from '@heroicons/react/24/outline';
import IsolatedField from '../components/flow/IsolatedParameterInput';
import toast from 'react-hot-toast';
import PrerequisiteCard from '../components/microsaas/PrerequisiteCard';
import FollowupCard from '../components/microsaas/FollowupCard';
import { fetchPublicRelatedFlows } from '../services/microSaasService';
import CustomLandingPageRenderer from '../components/landing-page-builder/renderers/CustomLandingPageRenderer';

// Import node components
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

const PublicFlowAppContent = () => {
  const { slug } = useParams();

  const [appInfo, setAppInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState({});
  const [executing, setExecuting] = useState(false);
  const [executionId, setExecutionId] = useState(null);
  const [executionLogs, setExecutionLogs] = useState([]);
  const [executionStatus, setExecutionStatus] = useState(null); // 'running', 'completed', 'failed'
  const [finalResult, setFinalResult] = useState(null);
  const [executionError, setExecutionError] = useState(null);
  const [showLogs, setShowLogs] = useState(true);
  const [nodeStatus, setNodeStatus] = useState({}); // Track status of each node
  const [currentNode, setCurrentNode] = useState(null);
  const [executedNodes, setExecutedNodes] = useState([]); // Track all executed nodes
  const [executingNodeId, setExecutingNodeId] = useState(null); // Track currently executing node
  const [showFlowDiagram, setShowFlowDiagram] = useState(false);
  const [activeTab, setActiveTab] = useState('input'); // 'input', 'execution', 'result'
  const [nodeExecutionData, setNodeExecutionData] = useState({}); // Track start/end times for each node

  // Related flows state
  const [relatedFlows, setRelatedFlows] = useState({ prerequisites: [], followups: [] });
  const [prerequisiteStatuses, setPrerequisiteStatuses] = useState({}); // Track status of each prerequisite
  const [prerequisiteOutputs, setPrerequisiteOutputs] = useState({}); // Track outputs from prerequisites
  const [followupStatuses, setFollowupStatuses] = useState({}); // Track status of each follow-up
  const [allPrerequisitesComplete, setAllPrerequisitesComplete] = useState(true); // Track if all mandatory prereqs done

  // ReactFlow state
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const reactFlowInstance = useRef(null);

  const wsRef = useRef(null);

  useEffect(() => {
    fetchAppInfo();
    fetchRelatedFlows();
  }, [slug]);

  // Fetch related flows (prerequisites and follow-ups)
  const fetchRelatedFlows = async () => {
    try {
      const data = await fetchPublicRelatedFlows(slug);
      setRelatedFlows(data);

      // Initialize prerequisite statuses
      const initialStatuses = {};
      (data.prerequisites || []).forEach(prereq => {
        initialStatuses[prereq.frontend_app_id] = 'not_run';
      });
      setPrerequisiteStatuses(initialStatuses);

      // Initialize follow-up statuses
      const initialFollowupStatuses = {};
      (data.followups || []).forEach(followup => {
        initialFollowupStatuses[followup.frontend_app_id] = 'available';
      });
      setFollowupStatuses(initialFollowupStatuses);

      // Check if all mandatory prerequisites are complete
      checkPrerequisitesComplete(data.prerequisites || [], initialStatuses);
    } catch (err) {
      console.log('No related flows found or error fetching:', err);
      // Not an error - app may not have related flows configured
    }
  };

  // Check if all mandatory prerequisites are complete
  const checkPrerequisitesComplete = (prerequisites, statuses) => {
    const mandatoryPrereqs = prerequisites.filter(p => p.is_mandatory);
    const allMandatoryComplete = mandatoryPrereqs.every(
      p => statuses[p.frontend_app_id] === 'completed' || statuses[p.frontend_app_id] === 'skipped'
    );
    setAllPrerequisitesComplete(mandatoryPrereqs.length === 0 || allMandatoryComplete);
  };

  // Handle running a prerequisite flow
  const handleRunPrerequisite = async (prerequisite, inputData) => {
    setPrerequisiteStatuses(prev => ({
      ...prev,
      [prerequisite.frontend_app_id]: 'running'
    }));

    try {
      const response = await fetch(`/api/v1/public-apps/${prerequisite.public_url_slug}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputData)
      });

      const result = await response.json();

      if (result.success || result.data) {
        setPrerequisiteStatuses(prev => ({
          ...prev,
          [prerequisite.frontend_app_id]: 'completed'
        }));
        setPrerequisiteOutputs(prev => ({
          ...prev,
          [prerequisite.frontend_app_id]: result.data || result
        }));

        // Update allPrerequisitesComplete check
        const newStatuses = {
          ...prerequisiteStatuses,
          [prerequisite.frontend_app_id]: 'completed'
        };
        checkPrerequisitesComplete(relatedFlows.prerequisites, newStatuses);

        return { success: true, data: result.data || result };
      } else {
        setPrerequisiteStatuses(prev => ({
          ...prev,
          [prerequisite.frontend_app_id]: 'failed'
        }));
        return { success: false, error: result.error || 'Execution failed' };
      }
    } catch (err) {
      setPrerequisiteStatuses(prev => ({
        ...prev,
        [prerequisite.frontend_app_id]: 'failed'
      }));
      return { success: false, error: err.message || 'Network error' };
    }
  };

  // Handle skipping an optional prerequisite
  const handleSkipPrerequisite = (prerequisite) => {
    setPrerequisiteStatuses(prev => ({
      ...prev,
      [prerequisite.frontend_app_id]: 'skipped'
    }));

    // Update allPrerequisitesComplete check
    const newStatuses = {
      ...prerequisiteStatuses,
      [prerequisite.frontend_app_id]: 'skipped'
    };
    checkPrerequisitesComplete(relatedFlows.prerequisites, newStatuses);
  };

  // Handle running a follow-up flow
  const handleRunFollowup = async (followup, inputData) => {
    setFollowupStatuses(prev => ({
      ...prev,
      [followup.frontend_app_id]: 'running'
    }));

    try {
      const response = await fetch(`/api/v1/public-apps/${followup.public_url_slug}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputData)
      });

      const result = await response.json();

      if (result.success || result.data) {
        setFollowupStatuses(prev => ({
          ...prev,
          [followup.frontend_app_id]: 'completed'
        }));
        return { success: true, data: result.data || result };
      } else {
        setFollowupStatuses(prev => ({
          ...prev,
          [followup.frontend_app_id]: 'failed'
        }));
        return { success: false, error: result.error || 'Execution failed' };
      }
    } catch (err) {
      setFollowupStatuses(prev => ({
        ...prev,
        [followup.frontend_app_id]: 'failed'
      }));
      return { success: false, error: err.message || 'Network error' };
    }
  };

  // Calculate auto-mapped values for follow-ups based on main flow output
  const getAutoMappedValues = (followup) => {
    if (!finalResult || !followup.input_parameters) {
      return {};
    }

    const mapped = {};
    const resultObj = typeof finalResult === 'object' ? finalResult : {};

    (followup.input_parameters || []).forEach(param => {
      // Try exact name match (case-insensitive)
      const exactMatch = Object.keys(resultObj).find(
        key => key.toLowerCase() === param.name.toLowerCase()
      );
      if (exactMatch) {
        mapped[param.name] = resultObj[exactMatch];
        return;
      }

      // Try partial match
      const partialMatch = Object.keys(resultObj).find(
        key => key.toLowerCase().includes(param.name.toLowerCase()) ||
               param.name.toLowerCase().includes(key.toLowerCase())
      );
      if (partialMatch) {
        mapped[param.name] = resultObj[partialMatch];
      }
    });

    return mapped;
  };

  // WebSocket connection for execution updates
  useEffect(() => {
    if (executionId && executing) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      // Use public websocket endpoint (no auth required)
      const ws = new WebSocket(`${protocol}//${host}/ws/public/${executionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Public execution WebSocket connected');
        // Don't add log - keep it cleaner
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('==== WebSocket message received ====');
        console.log('Message type:', data.type);
        console.log('Full message:', JSON.stringify(data, null, 2));
        if (data.data) {
          console.log('Inner data type:', data.data.type);
          console.log('Inner data:', JSON.stringify(data.data, null, 2));
        }
        console.log('====================================');
        handleExecutionUpdate(data);
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        addLog('error', 'Connection error occurred');
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
      };

      return () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    }
  }, [executionId, executing]);

  const fetchAppInfo = async () => {
    try {
      const response = await fetch(`/api/v1/public-apps/${slug}/info`);

      if (!response.ok) {
        if (response.status === 404) {
          setError('Application not found');
        } else {
          setError('Failed to load application');
        }
        return;
      }

      const data = await response.json();
      setAppInfo(data);

      // Initialize form data with default values
      const initialFormData = {};
      data.manual_variables?.forEach(variable => {
        if (variable.defaultValue) {
          initialFormData[variable.name] = variable.defaultValue;
        }
      });
      setFormData(initialFormData);
    } catch (err) {
      setError('Network error: Could not connect to server');
    } finally {
      setLoading(false);
    }
  };

  const handleFieldChange = useCallback((name, value) => {
    setFormData(prev => ({ ...prev, [name]: value }));
  }, []);

  const addLog = (type, message, nodeId = null, data = null) => {
    setExecutionLogs(prev => [...prev, {
      type,
      message,
      nodeId,
      data,
      timestamp: new Date().toISOString()
    }]);
  };

  // Update node display based on execution status
  useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => {
        const status = nodeStatus[node.id];
        const isExecuting = node.id === executingNodeId;
        const isExecuted = executedNodes.includes(node.id);

        return {
          ...node,
          data: {
            ...node.data,
            isExecuting: isExecuting,
            isExecuted: isExecuted,
            executionStatus: status
          }
        };
      })
    );
  }, [executingNodeId, executedNodes, nodeStatus, setNodes]);

  // Auto-zoom to executing node
  useEffect(() => {
    if (executingNodeId && reactFlowInstance.current) {
      const node = nodes.find(n => n.id === executingNodeId);
      if (node) {
        reactFlowInstance.current.fitView({
          padding: 0.3,
          includeHiddenNodes: false,
          minZoom: 1,
          maxZoom: 1.5,
          duration: 400,
          nodes: [{ id: executingNodeId }]
        });
      }
    }
  }, [executingNodeId, nodes]);

  // Auto-switch to result tab when execution completes
  useEffect(() => {
    if (executionStatus === 'completed' && finalResult) {
      setActiveTab('result');
    } else if (executionStatus === 'failed' && executionError) {
      setActiveTab('result');
    }
  }, [executionStatus, finalResult, executionError]);

  const handleExecutionUpdate = (message) => {
    console.log('📥 handleExecutionUpdate called with message type:', message.type);

    // Handle initial connection with flow definition
    if (message.type === 'connected' && message.flow_definition) {
      console.log('✓ Handling connected message with flow definition');
      const flowDef = message.flow_definition;
      if (flowDef.nodes && flowDef.edges) {
        // Clone nodes to avoid reference issues
        const clonedNodes = flowDef.nodes.map(node => ({
          ...node,
          data: { ...node.data, executionMode: true },
          style: { ...node.style },
        }));
        setNodes(clonedNodes);
        setEdges(flowDef.edges || []);
        setShowFlowDiagram(true);
      }
      return;
    }

    // Handle connection and subscription confirmation messages
    if (message.type === 'connection' || message.type === 'subscription') {
      console.log('✓ Connection/subscription message, skipping:', message.type);
      return;
    }

    // Unwrap execution_update and execution_log messages
    let event;
    if (message.type === 'execution_update' || message.type === 'execution_log') {
      console.log('📦 Unwrapping message...');
      console.log('   Wrapper type:', message.type);
      console.log('   Inner data:', message.data);
      event = message.data;
      console.log('   Unwrapped event type:', event?.type);
    } else {
      console.log('📨 Direct message (not wrapped)');
      event = message;
    }

    // Skip non-execution events
    if (!event || !event.type) {
      console.warn('⚠️ Skipping message without event type:', message);
      return;
    }

    console.log('🔄 Processing event type:', event.type);

    switch (event.type) {
      case 'execution_start':
        console.log('✅ EXECUTION_START event');
        console.log('   Setting status to: running');
        setExecutionStatus('running');
        // Don't add log - keep it cleaner
        break;

      case 'node_start':
        console.log('✅ NODE_START event');
        console.log('   Node ID:', event.node_id);
        console.log('   Node label:', event.node_label);
        console.log('   Setting as executing node');
        setCurrentNode(event.node_id);
        setExecutingNodeId(event.node_id);
        setNodeStatus(prev => ({
          ...prev,
          [event.node_id]: 'running'
        }));
        // Track start time
        setNodeExecutionData(prev => ({
          ...prev,
          [event.node_id]: {
            nodeId: event.node_id,
            nodeName: event.node_label || event.node_id,
            nodeType: event.node_type,
            startTime: new Date(),
            status: 'running'
          }
        }));
        break;

      case 'node_complete':
        console.log('✅ NODE_COMPLETE event');
        console.log('   Node ID:', event.node_id);
        console.log('   Clearing executing node, marking as completed');
        setExecutingNodeId(null);
        setNodeStatus(prev => ({
          ...prev,
          [event.node_id]: 'completed'
        }));
        setExecutedNodes(prev => [...prev, event.node_id]);
        // Track end time and calculate duration
        setNodeExecutionData(prev => ({
          ...prev,
          [event.node_id]: {
            ...prev[event.node_id],
            endTime: new Date(),
            status: 'completed'
          }
        }));
        break;

      case 'node_error':
        console.log('❌ NODE_ERROR event');
        console.log('   Node ID:', event.node_id);
        console.log('   Error:', event.error);
        console.log('   Error type:', event.error_type);
        setExecutingNodeId(null);
        setNodeStatus(prev => ({
          ...prev,
          [event.node_id]: 'error'
        }));
        // Track error in node execution data
        setNodeExecutionData(prev => ({
          ...prev,
          [event.node_id]: {
            ...prev[event.node_id],
            endTime: new Date(),
            status: 'error',
            error: event.error,
            errorType: event.error_type
          }
        }));
        addLog('error', `Error in ${event.node_label || event.node_id}: ${event.error}`, event.node_id);
        break;

      case 'log':
        addLog('info', event.message, event.node_id);
        break;

      case 'execution_complete':
        console.log('✅ EXECUTION_COMPLETE event');
        console.log('   Has result:', !!event.result);
        if (event.result) {
          console.log('   Result type:', typeof event.result);
          console.log('   Result preview:', JSON.stringify(event.result).substring(0, 100));
        }
        setExecutionStatus('completed');
        setExecuting(false);
        setCurrentNode(null);
        setExecutingNodeId(null);
        if (event.result) {
          console.log('   ✓ Setting final result');
          setFinalResult(event.result);
          // Don't add generic "completed" log - the result tab shows completion
        } else {
          console.warn('   ⚠️ No result in execution_complete event');
        }
        break;

      case 'execution_error':
        console.log('❌ EXECUTION_ERROR event');
        console.log('   Error:', event.error);
        console.log('   Error type:', event.error_type);
        setExecutionStatus('failed');
        setExecuting(false);
        setCurrentNode(null);
        setExecutingNodeId(null);
        setExecutionError(event.error || 'Execution failed');
        addLog('error', `Execution failed: ${event.error}`);
        break;

      default:
        console.warn('⚠️ UNKNOWN event type:', event.type);
        console.warn('   Full event:', event);
    }
  };

  const handleExecute = async (e) => {
    e.preventDefault();
    setExecuting(true);
    setExecutionId(null);
    setExecutionLogs([]);
    setExecutionStatus(null);
    setFinalResult(null);
    setExecutionError(null);
    setNodeStatus({});
    setCurrentNode(null);
    setExecutedNodes([]);
    setExecutingNodeId(null);
    setNodeExecutionData({});
    setActiveTab('execution'); // Switch to execution tab when starting

    try {
      // Start execution
      const response = await fetch(`/api/v1/public-apps/${slug}/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      const data = await response.json();

      if (data.execution_id) {
        // Async execution - use WebSocket for updates
        setExecutionId(data.execution_id);
        // Don't add "Execution initiated" log - too technical
      } else if (data.success) {
        // Synchronous execution - show result immediately
        setExecutionStatus('completed');
        setFinalResult(data.data);
        setExecuting(false);
      } else {
        setExecutionStatus('failed');
        setExecutionError(data.error || 'Execution failed');
        setExecuting(false);
        addLog('error', data.error || 'Execution failed');
      }
    } catch (err) {
      setExecutionStatus('failed');
      setExecutionError('Network error: Could not execute application');
      setExecuting(false);
      addLog('error', 'Network error occurred');
    }
  };

  const formatResult = (data) => {
    if (typeof data === 'string') {
      const trimmedData = data.trim();

      // Check if it's HTML content - look for common HTML tags
      const htmlTagPattern = /^<(!doctype html|html|div|span|p|h[1-6]|section|article|main|header|footer|nav|table|ul|ol|form|img)/i;
      const isHtml = htmlTagPattern.test(trimmedData);

      if (isHtml) {
        return (
          <div
            className="w-full"
            dangerouslySetInnerHTML={{ __html: data }}
          />
        );
      }
      return <div className="whitespace-pre-wrap break-words">{data}</div>;
    }
    if (typeof data === 'object') {
      return (
        <div className="max-h-[600px] overflow-y-auto">
          <pre className="whitespace-pre-wrap break-words text-sm font-mono bg-gray-50 p-4 rounded border border-gray-200">
            {JSON.stringify(data, null, 2)}
          </pre>
        </div>
      );
    }
    return <div className="whitespace-pre-wrap break-words">{String(data)}</div>;
  };

  const renderFormField = (variable) => {
    return (
      <div key={variable.id || variable.name} className="mb-6">
        <IsolatedField
          variable={variable}
          value={formData[variable.name]}
          onChange={handleFieldChange}
        />
      </div>
    );
  };

  const getLogIcon = (type) => {
    switch (type) {
      case 'success':
        return <CheckCircleIcon className="w-5 h-5 text-green-600" />;
      case 'error':
        return <XCircleIcon className="w-5 h-5 text-red-600" />;
      case 'info':
        return <InformationCircleIcon className="w-5 h-5 text-primary" />;
      case 'data':
        return <DocumentTextIcon className="w-5 h-5 text-purple-600" />;
      case 'node_start':
        return <ArrowPathIcon className="w-5 h-5 text-primary animate-spin" />;
      case 'node_complete':
        return <CheckCircleIcon className="w-5 h-5 text-green-600" />;
      default:
        return <ClockIcon className="w-5 h-5 text-gray-600" />;
    }
  };

  const getNodeTypeIcon = (nodeType) => {
    // Use the same icons as flow design
    const iconClass = "w-5 h-5";
    switch (nodeType?.toLowerCase()) {
      case 'trigger':
        return <BoltIcon className={`${iconClass} text-purple-600`} />;
      case 'action':
        return <CommandLineIcon className={`${iconClass} text-primary`} />;
      case 'transform':
        return <ArrowPathRoundedSquareIcon className={`${iconClass} text-green-600`} />;
      case 'condition':
        return <ArrowsRightLeftIcon className={`${iconClass} text-yellow-600`} />;
      case 'response':
        return <PaperAirplaneIcon className={`${iconClass} text-secondary`} />;
      case 'loop':
        return <ArrowPathIcon className={`${iconClass} text-pink-600`} />;
      default:
        return <CogIcon className={`${iconClass} text-gray-600`} />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-gray-600">Loading application...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <XCircleIcon className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Application Not Available</h1>
          <p className="text-gray-600 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Render custom landing page if page_definition exists
  if (appInfo?.page_definition) {
    return (
      <CustomLandingPageRenderer
        definition={appInfo.page_definition}
        appInfo={appInfo}
        slug={slug}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto pt-8 pb-16 px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 rounded-full mb-4">
            <GlobeAltIcon className="w-8 h-8 text-primary" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            {appInfo?.frontend_app_name}
          </h1>
          {appInfo?.description && (
            <p className="text-lg text-gray-600">
              {appInfo.description}
            </p>
          )}
          <div className="mt-4 inline-flex items-center text-sm text-gray-500">
            <ClockIcon className="w-4 h-4 mr-1" />
            Powered by <span className="font-medium ml-1">{appInfo?.flow_name}</span>
          </div>
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8" aria-label="Tabs">
              <button
                onClick={() => setActiveTab('input')}
                className={`${
                  activeTab === 'input'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
              >
                Input
              </button>
              <button
                onClick={() => setActiveTab('execution')}
                className={`${
                  activeTab === 'execution'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
              >
                Execution Log
                {executing && (
                  <ArrowPathIcon className="w-4 h-4 animate-spin" />
                )}
                {!executing && executionStatus === 'completed' && !executionError && (
                  <CheckCircleIcon className="w-4 h-4 text-green-500" />
                )}
                {!executing && (executionStatus === 'failed' || executionError) && (
                  <XCircleIcon className="w-4 h-4 text-red-500" />
                )}
              </button>
              <button
                onClick={() => setActiveTab('result')}
                className={`${
                  activeTab === 'result'
                    ? 'border-primary text-primary'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
              >
                Result
                {finalResult && <CheckCircleIcon className="w-4 h-4 text-green-600" />}
                {executionError && <XCircleIcon className="w-4 h-4 text-red-600" />}
              </button>
            </nav>
          </div>
        </div>

        {/* Tab Content */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200">
          {/* Input Tab */}
          {activeTab === 'input' && (
            <div className="p-6">
              {/* Prerequisites Section */}
              {relatedFlows.prerequisites && relatedFlows.prerequisites.length > 0 && (
                <div className="mb-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-3">
                    Prerequisites
                  </h2>
                  <p className="text-sm text-gray-600 mb-4">
                    Complete these steps before running the main application.
                  </p>
                  <div className="space-y-3">
                    {relatedFlows.prerequisites.map((prereq) => (
                      <PrerequisiteCard
                        key={prereq.relationship_id || prereq.frontend_app_id}
                        prerequisite={prereq}
                        status={prerequisiteStatuses[prereq.frontend_app_id] || 'not_run'}
                        onRun={handleRunPrerequisite}
                        onSkip={handleSkipPrerequisite}
                        outputs={prerequisiteOutputs[prereq.frontend_app_id]}
                      />
                    ))}
                  </div>

                  {/* Warning if mandatory prerequisites not complete */}
                  {!allPrerequisitesComplete && (
                    <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                      <div className="flex items-center gap-2">
                        <ExclamationTriangleIcon className="w-5 h-5 text-yellow-600" />
                        <p className="text-sm text-yellow-800">
                          Please complete all required prerequisites before executing the main application.
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}

              <h2 className="text-lg font-semibold text-gray-900 mb-4">Input Parameters</h2>
              <form onSubmit={handleExecute}>
                {appInfo?.manual_variables?.length > 0 ? (
                  <>
                    {appInfo.manual_variables.map(renderFormField)}

                    <div className="border-t border-gray-200 pt-4 mt-4">
                      <button
                        type="submit"
                        disabled={executing || !allPrerequisitesComplete}
                        className="w-full flex items-center justify-center px-6 py-3 bg-gradient-primary text-white font-medium rounded-md hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {executing ? (
                          <>
                            <ArrowPathIcon className="w-5 h-5 mr-2 animate-spin" />
                            Processing...
                          </>
                        ) : !allPrerequisitesComplete ? (
                          <>
                            <ExclamationTriangleIcon className="w-5 h-5 mr-2" />
                            Complete Prerequisites First
                          </>
                        ) : (
                          <>
                            <PlayIcon className="w-5 h-5 mr-2" />
                            Execute
                          </>
                        )}
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-6">
                    <DocumentTextIcon className="w-10 h-10 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 mb-4 text-sm">
                      This application doesn't require any input parameters.
                    </p>
                    <button
                      type="submit"
                      disabled={executing || !allPrerequisitesComplete}
                      className="inline-flex items-center px-6 py-3 bg-gradient-primary text-white font-medium rounded-md hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 disabled:opacity-50"
                    >
                      {executing ? (
                        <>
                          <ArrowPathIcon className="w-5 h-5 mr-2 animate-spin" />
                          Processing...
                        </>
                      ) : !allPrerequisitesComplete ? (
                        <>
                          <ExclamationTriangleIcon className="w-5 h-5 mr-2" />
                          Complete Prerequisites First
                        </>
                      ) : (
                        <>
                          <PlayIcon className="w-5 h-5 mr-2" />
                          Execute
                        </>
                      )}
                    </button>
                  </div>
                )}
              </form>
            </div>
          )}

          {/* Execution Log Tab */}
          {activeTab === 'execution' && (
            <div className="p-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Flow Diagram */}
                {showFlowDiagram && nodes.length > 0 && (
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Flow Visualization</h3>
                    <div style={{ height: '600px' }} className="border border-gray-200 rounded-lg overflow-hidden">
                      <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onInit={(instance) => { reactFlowInstance.current = instance; }}
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
                        elementsSelectable={false}
                      >
                        <Background />
                        <Controls showInteractive={false} />
                        <MiniMap nodeStrokeWidth={3} zoomable pannable />
                      </ReactFlow>
                    </div>
                  </div>
                )}

                {/* Execution Logs */}
                <div>
                  <div className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-base font-semibold text-gray-900">Execution Progress</h3>
                      {Object.keys(nodeExecutionData).length > 0 && (
                        <button
                          onClick={() => setShowLogs(!showLogs)}
                          className="text-sm text-gray-600 hover:text-gray-900 flex items-center gap-1"
                        >
                          {showLogs ? <ChevronUpIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
                          {showLogs ? 'Hide' : 'Show'} Logs
                        </button>
                      )}
                    </div>

                {/* Execution Status Summary */}
                {executing && (
                  <div className="mb-4 space-y-3">
                    {/* Currently Executing Node */}
                    {executingNodeId && (
                      <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <div className="flex items-center gap-2">
                          <ArrowPathIcon className="w-5 h-5 text-primary animate-spin" />
                          <div className="flex-1">
                            <div className="text-sm font-medium text-blue-900">
                              Currently Executing
                            </div>
                            <div className="text-xs text-blue-700">
                              {nodes.find(n => n.id === executingNodeId)?.data?.label || executingNodeId}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Progress Stats */}
                    {nodes.length > 0 && (
                      <div className="flex items-center gap-4 text-sm">
                        <div className="flex items-center gap-1">
                          <CheckCircleIcon className="w-4 h-4 text-green-600" />
                          <span className="text-gray-600">
                            {executedNodes.length} / {nodes.length} completed
                          </span>
                        </div>
                        {executionStatus === 'running' && (
                          <div className="flex items-center gap-1">
                            <ClockIcon className="w-4 h-4 text-primary" />
                            <span className="text-gray-600">In Progress</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {showLogs && (
                  <div className="space-y-3 max-h-96 overflow-y-auto">
                    {Object.values(nodeExecutionData).map((nodeData, index) => {
                      const duration = nodeData.endTime && nodeData.startTime
                        ? ((nodeData.endTime - nodeData.startTime) / 1000).toFixed(2)
                        : null;

                      const isRunning = nodeData.status === 'running';
                      const isCompleted = nodeData.status === 'completed';
                      const isError = nodeData.status === 'error';

                      return (
                        <div
                          key={nodeData.nodeId}
                          className={`p-3 rounded-lg border ${
                            isError
                              ? 'bg-red-50 border-red-200'
                              : 'bg-gray-50 border-gray-200'
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            {/* Node Type Icon */}
                            <div className="flex-shrink-0 mt-1">
                              {getNodeTypeIcon(nodeData.nodeType)}
                            </div>

                            {/* Node Info */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-2">
                                <span className={`font-semibold text-sm ${
                                  isError ? 'text-red-900' : 'text-gray-900'
                                }`}>
                                  {nodeData.nodeName}
                                </span>
                                <span className={`text-xs uppercase tracking-wide ${
                                  isError ? 'text-red-500' : 'text-gray-500'
                                }`}>
                                  {nodeData.nodeType}
                                </span>
                                {/* Status Icon */}
                                {isRunning && (
                                  <ArrowPathIcon className="w-4 h-4 text-primary animate-spin ml-auto" />
                                )}
                                {isCompleted && (
                                  <CheckCircleIcon className="w-4 h-4 text-green-600 ml-auto" />
                                )}
                                {isError && (
                                  <XCircleIcon className="w-4 h-4 text-red-600 ml-auto" />
                                )}
                              </div>

                              {/* Error Message */}
                              {isError && nodeData.error && (
                                <div className="mb-2 p-2 bg-red-100 border border-red-200 rounded text-xs text-red-800">
                                  <div className="font-semibold mb-1">Error:</div>
                                  <div>{nodeData.error}</div>
                                </div>
                              )}

                              {/* Timing Information */}
                              <div className={`text-xs space-y-1 ${
                                isError ? 'text-red-600' : 'text-gray-600'
                              }`}>
                                <div className="flex items-center gap-4">
                                  <span>
                                    <span className={isError ? 'text-red-500' : 'text-gray-500'}>Started:</span>{' '}
                                    {nodeData.startTime?.toLocaleTimeString()}
                                  </span>
                                  {nodeData.endTime && (
                                    <span>
                                      <span className={isError ? 'text-red-500' : 'text-gray-500'}>
                                        {isError ? 'Failed:' : 'Ended:'}
                                      </span>{' '}
                                      {nodeData.endTime.toLocaleTimeString()}
                                    </span>
                                  )}
                                  {duration && (
                                    <span className={`ml-auto font-medium ${
                                      isError ? 'text-red-700' : 'text-gray-700'
                                    }`}>
                                      {duration}s
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                    {executing && Object.keys(nodeExecutionData).length === 0 && (
                      <div className="flex items-center justify-center gap-2 text-sm text-gray-500 py-8">
                        <ArrowPathIcon className="w-5 h-5 animate-spin" />
                        <span>Starting execution...</span>
                      </div>
                    )}
                  </div>
                )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Result Tab */}
          {activeTab === 'result' && (
            <div className="p-6">
              {/* Success Result */}
              {finalResult && executionStatus === 'completed' && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-6">
                  <div className="flex items-start gap-3">
                    <CheckCircleIcon className="w-6 h-6 text-green-600 flex-shrink-0 mt-1" />
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-green-900 mb-3">
                        Execution Successful
                      </h3>
                      <div className="text-green-800 overflow-hidden">
                        {formatResult(finalResult)}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Error Result */}
              {executionError && executionStatus === 'failed' && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                  <div className="flex items-start gap-3">
                    <ExclamationTriangleIcon className="w-6 h-6 text-red-600 flex-shrink-0 mt-1" />
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-semibold text-red-900 mb-2">
                        Execution Failed
                      </h3>
                      <p className="text-red-800 text-sm whitespace-pre-wrap break-words">
                        {executionError}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* No Result Yet */}
              {!finalResult && !executionError && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
                  <InformationCircleIcon className="w-12 h-12 text-primary mx-auto mb-3" />
                  <div className="text-sm text-blue-800">
                    <p className="mb-2 font-medium">No results yet</p>
                    <p>
                      Execute the application to see results here.
                    </p>
                  </div>
                </div>
              )}

              {/* Follow-ups Section - shown after successful execution */}
              {relatedFlows.followups && relatedFlows.followups.length > 0 && finalResult && executionStatus === 'completed' && (
                <div className="mt-6 border-t border-gray-200 pt-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-3">
                    What's Next?
                  </h2>
                  <p className="text-sm text-gray-600 mb-4">
                    Continue with these related applications. Values from your results have been auto-filled where possible.
                  </p>
                  <div className="space-y-3">
                    {relatedFlows.followups.map((followup) => (
                      <FollowupCard
                        key={followup.relationship_id || followup.frontend_app_id}
                        followup={followup}
                        status={followupStatuses[followup.frontend_app_id] || 'available'}
                        autoMappedValues={getAutoMappedValues(followup)}
                        onRun={handleRunFollowup}
                        mainFlowOutputs={finalResult}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Info */}
        <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <InformationCircleIcon className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-800">
              <p>
                This is a public IOFlow application. Your data will be processed according to the
                application's configuration and our privacy policy.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Wrap with ReactFlowProvider
const PublicFlowAppEnhanced = () => {
  return (
    <ReactFlowProvider>
      <PublicFlowAppContent />
    </ReactFlowProvider>
  );
};

export default PublicFlowAppEnhanced;
