import React, { useState, useEffect, useCallback, useRef } from 'react';
import SectionRenderer from './SectionRenderer';
import toast from 'react-hot-toast';
import { fetchPublicRelatedFlows } from '../../../services/microSaasService';

/**
 * CustomLandingPageRenderer - Main orchestrator for custom landing pages
 *
 * Manages all shared execution state (formData, WebSocket, execution results)
 * and passes them down to section renderers via sharedProps.
 */
export default function CustomLandingPageRenderer({
  definition,
  appInfo,
  slug,
  previewMode = false,
}) {
  // Form state
  const [formData, setFormData] = useState({});
  const manualVariables = appInfo?.manual_variables || [];

  // Execution state
  const [executing, setExecuting] = useState(false);
  const [executionId, setExecutionId] = useState(null);
  const [executionLogs, setExecutionLogs] = useState([]);
  const [executionStatus, setExecutionStatus] = useState(null);
  const [finalResult, setFinalResult] = useState(null);
  const [executionError, setExecutionError] = useState(null);
  const [nodeStatus, setNodeStatus] = useState({});
  const [currentNode, setCurrentNode] = useState(null);
  const [nodeExecutionData, setNodeExecutionData] = useState({});
  const [executedNodes, setExecutedNodes] = useState([]);
  const [executingNodeId, setExecutingNodeId] = useState(null);
  const [flowNodes, setFlowNodes] = useState([]);
  const [flowEdges, setFlowEdges] = useState([]);
  const [hitlTaskInfo, setHitlTaskInfo] = useState(null); // { task_id, title, task_type, priority, assigned_to, node_id }

  // Related flows state
  const [relatedFlows, setRelatedFlows] = useState({ prerequisites: [], followups: [] });
  const [prerequisiteStatuses, setPrerequisiteStatuses] = useState({});
  const [prerequisiteOutputs, setPrerequisiteOutputs] = useState({});
  const [followupStatuses, setFollowupStatuses] = useState({});
  const [allPrerequisitesComplete, setAllPrerequisitesComplete] = useState(true);

  // Refs
  const wsRef = useRef(null);
  const sectionRefs = useRef({});

  // Theme
  const theme = definition?.theme || {};

  // Initialize form data with defaults
  useEffect(() => {
    const initialData = {};
    manualVariables.forEach((v) => {
      if (v.defaultValue) initialData[v.name] = v.defaultValue;
    });
    setFormData(initialData);
  }, [manualVariables]);

  // Fetch related flows
  useEffect(() => {
    if (previewMode || !slug) return;
    (async () => {
      try {
        const data = await fetchPublicRelatedFlows(slug);
        setRelatedFlows(data);
        const initStatuses = {};
        (data.prerequisites || []).forEach((p) => (initStatuses[p.frontend_app_id] = 'not_run'));
        setPrerequisiteStatuses(initStatuses);
        const initFollowup = {};
        (data.followups || []).forEach((f) => (initFollowup[f.frontend_app_id] = 'available'));
        setFollowupStatuses(initFollowup);
        checkPrerequisitesComplete(data.prerequisites || [], initStatuses);
      } catch {
        // App may not have related flows
      }
    })();
  }, [slug, previewMode]);

  // Fetch flow definition for diagram
  useEffect(() => {
    if (previewMode || !slug) return;
    (async () => {
      try {
        const resp = await fetch(`/api/v1/public-apps/${slug}/info`);
        if (!resp.ok) return;
        const data = await resp.json();
        // If the info endpoint includes flow_definition with nodes/edges, use them
        // Otherwise we'll build nodes from execution data
        if (data.flow_nodes) {
          setFlowNodes(data.flow_nodes);
          setFlowEdges(data.flow_edges || []);
        }
      } catch {
        // Ignore
      }
    })();
  }, [slug, previewMode]);


  const checkPrerequisitesComplete = (prerequisites, statuses) => {
    const mandatory = prerequisites.filter((p) => p.is_mandatory);
    const allDone = mandatory.every(
      (p) => statuses[p.frontend_app_id] === 'completed' || statuses[p.frontend_app_id] === 'skipped'
    );
    setAllPrerequisitesComplete(mandatory.length === 0 || allDone);
  };

  // WebSocket for execution updates
  // Keep connection open during HITL pauses (executionStatus === 'paused')
  // Only close when execution is terminal (completed/failed) or no executionId
  useEffect(() => {
    if (!executionId || previewMode) return;
    // Don't open a new connection if execution is already terminal
    if (executionStatus === 'completed' || executionStatus === 'failed') return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/public/${executionId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleExecutionUpdate(data);
    };

    ws.onerror = () => addLog('error', 'Connection error occurred');
    ws.onclose = () => {};

    return () => {
      if (ws.readyState === WebSocket.OPEN) ws.close();
    };
  }, [executionId]);

  const addLog = useCallback((type, message, nodeId) => {
    setExecutionLogs((prev) => [...prev, { type, message, nodeId, timestamp: new Date().toISOString() }]);
  }, []);

  const handleExecutionUpdate = useCallback((message) => {
    // Handle connected message with flow definition
    if (message.type === 'connected' && message.flow_definition) {
      const flowDef = message.flow_definition;
      if (flowDef.nodes && flowDef.edges) {
        setFlowNodes(flowDef.nodes);
        setFlowEdges(flowDef.edges);
      }
      return;
    }

    // Skip connection/subscription confirmations
    if (message.type === 'connection' || message.type === 'subscription') return;

    // Unwrap execution_update and execution_log wrappers
    let event;
    if (message.type === 'execution_update' || message.type === 'execution_log') {
      event = message.data;
    } else {
      event = message;
    }

    if (!event || !event.type) return;

    switch (event.type) {
      case 'node_start':
        setCurrentNode(event.node_label || event.node_id);
        setExecutingNodeId(event.node_id);
        setNodeStatus((prev) => ({ ...prev, [event.node_id]: 'running' }));
        setNodeExecutionData((prev) => ({
          ...prev,
          [event.node_id]: {
            nodeId: event.node_id,
            nodeName: event.node_label || event.node_id,
            nodeType: event.node_type,
            startTime: new Date(),
            status: 'running',
          },
        }));
        addLog('node_start', `Starting: ${event.node_label || event.node_id}`, event.node_id);
        break;
      case 'node_complete':
        setExecutingNodeId(null);
        setNodeStatus((prev) => ({ ...prev, [event.node_id]: 'completed' }));
        setExecutedNodes((prev) => [...prev, event.node_id]);
        setNodeExecutionData((prev) => ({
          ...prev,
          [event.node_id]: {
            ...prev[event.node_id],
            endTime: new Date(),
            status: 'completed',
          },
        }));
        addLog('node_complete', `Completed: ${event.node_label || event.node_id}`, event.node_id);
        break;
      case 'node_error':
        setExecutingNodeId(null);
        setNodeStatus((prev) => ({ ...prev, [event.node_id]: 'error' }));
        setNodeExecutionData((prev) => ({
          ...prev,
          [event.node_id]: {
            ...prev[event.node_id],
            endTime: new Date(),
            status: 'error',
            error: event.error,
          },
        }));
        addLog('error', `Error in ${event.node_label || event.node_id}: ${event.error}`, event.node_id);
        break;
      case 'log':
        addLog('info', event.message, event.node_id);
        break;
      case 'hitl_task_created':
        setExecutionStatus('paused');
        setExecuting(false);
        setExecutingNodeId(null);
        setCurrentNode(null);
        setNodeStatus((prev) => ({ ...prev, [event.node_id]: 'paused' }));
        setNodeExecutionData((prev) => ({
          ...prev,
          [event.node_id]: {
            ...prev[event.node_id],
            status: 'paused',
            hitlInfo: {
              task_id: event.task_id,
              title: event.title,
              task_type: event.task_type,
              priority: event.priority,
              assigned_to: event.assigned_to,
              message: event.message,
            },
          },
        }));
        setHitlTaskInfo({
          task_id: event.task_id,
          title: event.title,
          task_type: event.task_type,
          priority: event.priority,
          assigned_to: event.assigned_to,
          can_complete: event.can_complete !== false,
          node_id: event.node_id,
          node_label: event.node_label,
          message: event.message,
          timeout_at: event.timeout_at,
        });
        addLog('info', event.message || `Waiting for human ${event.task_type}: ${event.title}`, event.node_id);
        break;
      case 'hitl_task_completed':
        setHitlTaskInfo(null);
        setExecutionStatus('running');
        setExecuting(true);
        if (event.node_id) {
          setNodeStatus((prev) => ({ ...prev, [event.node_id]: 'completed' }));
          setNodeExecutionData((prev) => ({
            ...prev,
            [event.node_id]: {
              ...prev[event.node_id],
              status: 'completed',
              hitlInfo: null,
              endTime: new Date(),
            },
          }));
          setExecutedNodes((prev) => [...prev, event.node_id]);
        }
        addLog('info', event.message || 'Human review completed — flow resuming', event.node_id);
        break;
      case 'execution_complete':
        setExecutionStatus('completed');
        setExecuting(false);
        setCurrentNode(null);
        setExecutingNodeId(null);
        if (event.result) {
          setFinalResult(event.result);
        }
        // Auto-scroll to result_display section
        setTimeout(() => {
          const sections = definition?.sections || [];
          const resultSection = sections.find((s) => s.type === 'result_display');
          if (resultSection && sectionRefs.current[resultSection.id]) {
            sectionRefs.current[resultSection.id].scrollIntoView({ behavior: 'smooth' });
          }
        }, 300);
        break;
      case 'execution_error':
        setExecutionStatus('failed');
        setExecuting(false);
        setCurrentNode(null);
        setExecutingNodeId(null);
        setExecutionError(event.error || 'Execution failed');
        addLog('error', `Execution failed: ${event.error}`);
        break;
      default:
        break;
    }
  }, [definition]);

  const handleFieldChange = useCallback((name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (previewMode) return;

    setExecuting(true);
    setExecutionId(null);
    setExecutionLogs([]);
    setExecutionStatus(null);
    setFinalResult(null);
    setExecutionError(null);
    setNodeStatus({});
    setCurrentNode(null);
    setNodeExecutionData({});
    setExecutedNodes([]);
    setExecutingNodeId(null);
    setHitlTaskInfo(null);

    // Auto-scroll to execution_display section
    const sections = definition?.sections || [];
    const execSection = sections.find((s) => s.type === 'execution_display');
    if (execSection && sectionRefs.current[execSection.id]) {
      sectionRefs.current[execSection.id].scrollIntoView({ behavior: 'smooth' });
    }

    try {
      const response = await fetch(`/api/v1/public-apps/${slug}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formData),
      });
      const data = await response.json();

      if (data.execution_id) {
        setExecutionId(data.execution_id);
      } else if (data.success) {
        setExecutionStatus('completed');
        setFinalResult(data.data || data.result || data);
        setExecuting(false);
      } else if (data.result) {
        // Some flows return result directly
        setExecutionStatus('completed');
        setFinalResult(data.result);
        setExecuting(false);
      } else {
        setExecutionStatus('failed');
        setExecutionError(data.error || 'Execution failed');
        setExecuting(false);
      }
    } catch {
      setExecutionStatus('failed');
      setExecutionError('Network error: Could not execute application');
      setExecuting(false);
    }
  };

  // Prerequisite handlers
  const handleRunPrerequisite = async (prerequisite, inputData) => {
    setPrerequisiteStatuses((prev) => ({ ...prev, [prerequisite.frontend_app_id]: 'running' }));
    try {
      const resp = await fetch(`/api/v1/public-apps/${prerequisite.public_url_slug}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputData),
      });
      const result = await resp.json();
      if (result.success || result.data) {
        setPrerequisiteStatuses((prev) => ({ ...prev, [prerequisite.frontend_app_id]: 'completed' }));
        setPrerequisiteOutputs((prev) => ({ ...prev, [prerequisite.frontend_app_id]: result.data || result }));
        const newStatuses = { ...prerequisiteStatuses, [prerequisite.frontend_app_id]: 'completed' };
        checkPrerequisitesComplete(relatedFlows.prerequisites, newStatuses);
        return { success: true, data: result.data || result };
      }
      setPrerequisiteStatuses((prev) => ({ ...prev, [prerequisite.frontend_app_id]: 'failed' }));
      return { success: false, error: result.error || 'Execution failed' };
    } catch (err) {
      setPrerequisiteStatuses((prev) => ({ ...prev, [prerequisite.frontend_app_id]: 'failed' }));
      return { success: false, error: err.message };
    }
  };

  const handleSkipPrerequisite = (prerequisite) => {
    setPrerequisiteStatuses((prev) => ({ ...prev, [prerequisite.frontend_app_id]: 'skipped' }));
    const newStatuses = { ...prerequisiteStatuses, [prerequisite.frontend_app_id]: 'skipped' };
    checkPrerequisitesComplete(relatedFlows.prerequisites, newStatuses);
  };

  const handleRunFollowup = async (followup, inputData) => {
    setFollowupStatuses((prev) => ({ ...prev, [followup.frontend_app_id]: 'running' }));
    try {
      const resp = await fetch(`/api/v1/public-apps/${followup.public_url_slug}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputData),
      });
      const result = await resp.json();
      if (result.success || result.data) {
        setFollowupStatuses((prev) => ({ ...prev, [followup.frontend_app_id]: 'completed' }));
        return { success: true, data: result.data || result };
      }
      setFollowupStatuses((prev) => ({ ...prev, [followup.frontend_app_id]: 'failed' }));
      return { success: false, error: result.error };
    } catch (err) {
      setFollowupStatuses((prev) => ({ ...prev, [followup.frontend_app_id]: 'failed' }));
      return { success: false, error: err.message };
    }
  };

  // Handle HITL task completed from inline TaskReviewModal
  const handleHitlComplete = useCallback((taskId, action) => {
    setHitlTaskInfo(null);
    setExecutionStatus('running');
    setExecuting(true);
    // The backend will send hitl_task_completed via WebSocket, which will also update state.
    // This provides immediate UI feedback before the WebSocket event arrives.
  }, []);

  // Shared props passed to all section renderers
  const sharedProps = {
    slug,
    previewMode,
    appInfo,
    manualVariables,
    formData,
    onFieldChange: handleFieldChange,
    onSubmit: handleSubmit,
    executing,
    executionId,
    executionLogs,
    executionStatus,
    finalResult,
    executionError,
    nodeStatus,
    currentNode,
    nodeExecutionData,
    executedNodes,
    executingNodeId,
    flowNodes,
    flowEdges,
    hitlTaskInfo,
    onHitlComplete: handleHitlComplete,
    sectionRefs,
    relatedFlows,
    prerequisiteStatuses,
    prerequisiteOutputs,
    onRunPrerequisite: handleRunPrerequisite,
    onSkipPrerequisite: handleSkipPrerequisite,
    allPrerequisitesComplete,
    followupStatuses,
    onRunFollowup: handleRunFollowup,
    documentationPages: appInfo?.documentation_pages,
  };

  const sections = definition?.sections || [];

  // Apply theme as CSS variables
  const themeStyle = {
    '--lp-primary': theme.primaryColor || 'var(--color-primary)',
    '--lp-bg': theme.backgroundColor || '#f9fafb',
    '--lp-font': theme.fontFamily || 'inherit',
    '--lp-radius': theme.borderRadius || '8px',
    backgroundColor: theme.backgroundColor || '#f9fafb',
    fontFamily: theme.fontFamily || 'inherit',
  };

  return (
    <div className="min-h-screen" style={themeStyle}>
      <div
        className="mx-auto pb-16"
        style={{ maxWidth: theme.maxWidth || '1200px' }}
      >
        {sections.map((section) => (
          <SectionRenderer
            key={section.id}
            section={section}
            sharedProps={sharedProps}
          />
        ))}

        {sections.length === 0 && (
          <div className="flex items-center justify-center min-h-[400px]">
            <p className="text-gray-400">No sections configured for this landing page</p>
          </div>
        )}
      </div>
    </div>
  );
}
