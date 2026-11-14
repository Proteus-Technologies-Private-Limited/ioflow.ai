import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  CheckCircleIcon,
  XCircleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  ClockIcon,
  BoltIcon,
  CommandLineIcon,
  ArrowPathRoundedSquareIcon,
  ArrowsRightLeftIcon,
  PaperAirplaneIcon,
  CogIcon,
} from '@heroicons/react/24/outline';
import TaskReviewModal from '../../../components/flows/TaskReviewModal';

/**
 * Display modes:
 *   minimal_steps    - Compact: spinner + progress bar + log list
 *   standard_steps   - Node cards with type icons, timing, and status
 *   standard         - Full IOFlow-style with currently executing banner + node cards
 *   flow_only        - Visual node pill flow
 *   flow_with_steps  - Visual node flow + step cards
 *   flow_design      - Full ReactFlow diagram with zoom-to-node
 */

let ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState;
let reactFlowLoaded = false;
let TriggerNode, ActionNode, ConditionNode, TransformNode, ResponseNode, LoopNode, HumanInLoopNode, WaitForEventNode, CustomEdge;

// Lazy-load ReactFlow only when flow_design mode is used
function loadReactFlow() {
  if (reactFlowLoaded) return Promise.resolve();
  return Promise.all([
    import('reactflow'),
    import('reactflow/dist/style.css'),
    import('../../../components/flow/TriggerNode'),
    import('../../../components/flow/ActionNode'),
    import('../../../components/flow/ConditionNode'),
    import('../../../components/flow/TransformNode'),
    import('../../../components/flow/ResponseNode'),
    import('../../../components/flow/LoopNode'),
    import('../../../components/flow/HumanInLoopNode'),
    import('../../../components/flow/WaitForEventNode'),
    import('../../../components/flow/CustomEdge'),
  ]).then(([rf, , tn, an, cn, trn, rn, ln, hiln, wfen, ce]) => {
    ReactFlow = rf.default;
    Background = rf.Background;
    Controls = rf.Controls;
    MiniMap = rf.MiniMap;
    useNodesState = rf.useNodesState;
    useEdgesState = rf.useEdgesState;
    TriggerNode = tn.default;
    ActionNode = an.default;
    ConditionNode = cn.default;
    TransformNode = trn.default;
    ResponseNode = rn.default;
    LoopNode = ln.default;
    HumanInLoopNode = hiln.default;
    WaitForEventNode = wfen.default;
    CustomEdge = ce.default;
    reactFlowLoaded = true;
  });
}

const getNodeTypeIcon = (nodeType) => {
  const cls = 'w-5 h-5';
  switch (nodeType?.toLowerCase()) {
    case 'trigger': return <BoltIcon className={`${cls} text-purple-600`} />;
    case 'action': return <CommandLineIcon className={`${cls} text-primary`} />;
    case 'transform': return <ArrowPathRoundedSquareIcon className={`${cls} text-green-600`} />;
    case 'condition': return <ArrowsRightLeftIcon className={`${cls} text-yellow-600`} />;
    case 'response': return <PaperAirplaneIcon className={`${cls} text-secondary`} />;
    case 'loop': return <ArrowPathIcon className={`${cls} text-pink-600`} />;
    case 'human_in_loop': return <HandRaisedIconFallback className={`${cls} text-amber-600`} />;
    case 'wait_for_event': return <ClockIconFallback className={`${cls} text-amber-600`} />;
    default: return <CogIcon className={`${cls} text-gray-600`} />;
  }
};

function HandRaisedIconFallback({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.05 4.575a1.575 1.575 0 10-3.15 0v3m3.15-3v-1.5a1.575 1.575 0 013.15 0v1.5m-3.15 0l.075 5.925m3.075-5.925a1.575 1.575 0 013.15 0v1.5m-3.15-1.5v5.926M7.5 11.25a.75.75 0 01-.75-.75V7.5a1.575 1.575 0 00-3.15 0v5.25a7.5 7.5 0 0015 0v-5.25a1.575 1.575 0 00-3.15 0" />
    </svg>
  );
}

function ClockIconFallback({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

export default function ExecutionDisplaySection({
  config,
  executionStatus,
  executionLogs,
  executing,
  executionError,
  nodeStatus,
  currentNode,
  nodeExecutionData,
  executedNodes,
  executingNodeId,
  flowNodes,
  flowEdges,
  hitlTaskInfo,
  onHitlComplete,
  previewMode,
}) {
  const displayMode = config.displayMode || 'minimal_steps';
  const showOnlyWhenRunning = config.showOnlyWhenRunning || false;
  const hideAfterComplete = config.hideAfterComplete || false;

  // HITL task review modal state
  const [showHitlReview, setShowHitlReview] = useState(false);

  const handleHitlCompleted = useCallback((taskId, action) => {
    setShowHitlReview(false);
    if (onHitlComplete) {
      onHitlComplete(taskId, action);
    }
  }, [onHitlComplete]);

  if (previewMode) {
    return (
      <div className="py-6">
        {config.title && <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>}
        <div className="bg-gray-50 rounded-lg border border-gray-200 p-8 text-center">
          <SignalIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-400 text-sm">
            Execution progress ({displayMode.replace(/_/g, ' ')}) will appear here
          </p>
        </div>
      </div>
    );
  }

  const hasStarted = executionStatus || executing || (executionLogs && executionLogs.length > 0);
  const isComplete = executionStatus === 'completed' || executionStatus === 'failed';

  if (showOnlyWhenRunning && !hasStarted) return null;
  if (hideAfterComplete && isComplete) return null;
  if (!hasStarted) return null;

  const StatusBanner = () => (
    <>
      {executionStatus === 'completed' && !executionError && (
        <div className="mb-4 flex items-center gap-2 p-3 bg-green-50 rounded-lg border border-green-200">
          <CheckCircleIcon className="w-5 h-5 text-green-600" />
          <span className="text-sm font-medium text-green-800">Execution completed successfully</span>
        </div>
      )}
      {(executionStatus === 'failed' || executionError) && (
        <div className="mb-4 flex items-center gap-2 p-3 bg-red-50 rounded-lg border border-red-200">
          <XCircleIcon className="w-5 h-5 text-red-600" />
          <span className="text-sm font-medium text-red-800">{executionError || 'Execution failed'}</span>
        </div>
      )}
      {executionStatus === 'paused' && hitlTaskInfo && (
        <div className="mb-4 p-4 bg-amber-50 rounded-lg border border-amber-200">
          <div className="flex items-start gap-3">
            <div className="shrink-0 mt-0.5">
              <HandRaisedIconFallback className="w-6 h-6 text-amber-600" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-semibold text-amber-900">Waiting for Human Action</span>
                {hitlTaskInfo.priority && (
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                    hitlTaskInfo.priority === 'critical' ? 'bg-red-100 text-red-700 border-red-200' :
                    hitlTaskInfo.priority === 'high' ? 'bg-orange-100 text-orange-700 border-orange-200' :
                    'bg-amber-100 text-amber-700 border-amber-200'
                  }`}>
                    {hitlTaskInfo.priority}
                  </span>
                )}
              </div>
              <p className="text-sm text-amber-800 mb-2">
                {hitlTaskInfo.message || `${hitlTaskInfo.task_type}: ${hitlTaskInfo.title}`}
              </p>
              <div className="flex flex-wrap gap-3 text-xs text-amber-700">
                {hitlTaskInfo.node_label && (
                  <span>Node: <strong>{hitlTaskInfo.node_label}</strong></span>
                )}
                {hitlTaskInfo.assigned_to && (
                  <span>Assigned to: <strong>{hitlTaskInfo.assigned_to}</strong></span>
                )}
                {hitlTaskInfo.timeout_at && (
                  <span>Timeout: {new Date(hitlTaskInfo.timeout_at).toLocaleString()}</span>
                )}
              </div>
              <div className="flex items-center gap-3 mt-3">
                {config.showReviewTask && hitlTaskInfo.can_complete !== false && (
                  <button
                    onClick={() => setShowHitlReview(true)}
                    className="px-4 py-1.5 text-xs font-medium text-white bg-amber-600 rounded-md hover:bg-amber-700 transition-colors"
                  >
                    Complete Task
                  </button>
                )}
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-amber-500"></span>
                </span>
                <span className="text-xs text-amber-600 font-medium">Flow paused — awaiting human response</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );

  // Build a set of completed/errored node IDs for log icon resolution
  const completedNodeIds = new Set(
    Object.entries(nodeStatus || {})
      .filter(([, s]) => s === 'completed' || s === 'error')
      .map(([id]) => id)
  );

  const getLogIcon = (log) => {
    switch (log.type) {
      case 'success':
      case 'node_complete':
        return <CheckCircleIcon className="w-4 h-4 text-green-600 shrink-0" />;
      case 'error':
        return <XCircleIcon className="w-4 h-4 text-red-600 shrink-0" />;
      case 'node_start':
        // If this node has since completed or errored, show final icon instead of spinner
        if (log.nodeId && completedNodeIds.has(log.nodeId)) {
          const status = nodeStatus[log.nodeId];
          if (status === 'completed') return <CheckCircleIcon className="w-4 h-4 text-green-600 shrink-0" />;
          if (status === 'error') return <XCircleIcon className="w-4 h-4 text-red-600 shrink-0" />;
        }
        return <ArrowPathIcon className="w-4 h-4 text-primary animate-spin shrink-0" />;
      default:
        return <InformationCircleIcon className="w-4 h-4 text-blue-500 shrink-0" />;
    }
  };

  // ── Minimal Steps ──
  const renderMinimalSteps = () => {
    const totalNodes = Object.keys(nodeExecutionData || {}).length;
    const doneNodes = Object.values(nodeExecutionData || {}).filter(n => n.status === 'completed').length;
    const pct = totalNodes > 0 ? Math.max(5, (doneNodes / totalNodes) * 100) : (executing ? 10 : 0);

    return (
      <>
        {executing && (
          <div className="mb-4">
            <div className="flex items-center gap-3 mb-2">
              <ArrowPathIcon className="w-5 h-5 text-primary animate-spin" />
              <span className="text-sm font-medium text-gray-700">
                {currentNode ? `Processing: ${currentNode}` : 'Running...'}
              </span>
              {totalNodes > 0 && (
                <span className="text-xs text-gray-400 ml-auto">{doneNodes}/{totalNodes}</span>
              )}
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-gradient-primary h-2 rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}
        <StatusBanner />
        {config.showLogs !== false && executionLogs && executionLogs.length > 0 && (
          <div className="bg-gray-50 rounded-lg border border-gray-200 max-h-80 overflow-y-auto">
            <div className="p-3 space-y-1">
              {executionLogs.map((log, idx) => (
                <div key={idx} className="flex items-start gap-2 text-xs">
                  {getLogIcon(log)}
                  <span className="text-gray-400 shrink-0">
                    {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                  </span>
                  <span className={log.type === 'error' ? 'text-red-600' : 'text-gray-700'}>
                    {log.message}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </>
    );
  };

  // ── Standard Steps ──
  const renderStandardSteps = () => {
    const nodeDataEntries = Object.values(nodeExecutionData || {});
    return (
      <>
        {executing && (
          <div className="mb-4 space-y-3">
            {executingNodeId && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <ArrowPathIcon className="w-5 h-5 text-primary animate-spin" />
                  <div className="flex-1">
                    <div className="text-sm font-medium text-blue-900">Currently Executing</div>
                    <div className="text-xs text-blue-700">{currentNode || executingNodeId}</div>
                  </div>
                </div>
              </div>
            )}
            {nodeDataEntries.length > 0 && (
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-1">
                  <CheckCircleIcon className="w-4 h-4 text-green-600" />
                  <span className="text-gray-600">
                    {(executedNodes || []).length} / {nodeDataEntries.length} completed
                  </span>
                </div>
              </div>
            )}
          </div>
        )}
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {nodeDataEntries.map((nodeData) => {
            const duration = nodeData.endTime && nodeData.startTime
              ? ((nodeData.endTime - nodeData.startTime) / 1000).toFixed(2) : null;
            const isRunning = nodeData.status === 'running';
            const isCompleted = nodeData.status === 'completed';
            const isError = nodeData.status === 'error';
            const isPaused = nodeData.status === 'paused';
            return (
              <div key={nodeData.nodeId} className={`p-3 rounded-lg border ${
                isError ? 'bg-red-50 border-red-200' :
                isPaused ? 'bg-amber-50 border-amber-200' :
                'bg-gray-50 border-gray-200'
              }`}>
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-1">{getNodeTypeIcon(nodeData.nodeType)}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`font-semibold text-sm ${isError ? 'text-red-900' : isPaused ? 'text-amber-900' : 'text-gray-900'}`}>{nodeData.nodeName}</span>
                      <span className={`text-xs uppercase tracking-wide ${isError ? 'text-red-500' : isPaused ? 'text-amber-500' : 'text-gray-500'}`}>{nodeData.nodeType}</span>
                      {isRunning && <ArrowPathIcon className="w-4 h-4 text-primary animate-spin ml-auto" />}
                      {isCompleted && <CheckCircleIcon className="w-4 h-4 text-green-600 ml-auto" />}
                      {isError && <XCircleIcon className="w-4 h-4 text-red-600 ml-auto" />}
                      {isPaused && <HandRaisedIconFallback className="w-4 h-4 text-amber-600 ml-auto" />}
                    </div>
                    {isError && nodeData.error && (
                      <div className="mb-2 p-2 bg-red-100 border border-red-200 rounded text-xs text-red-800">{nodeData.error}</div>
                    )}
                    {isPaused && nodeData.hitlInfo && (
                      <div className="mb-2 p-2 bg-amber-100 border border-amber-200 rounded text-xs text-amber-800">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="font-semibold mb-0.5">Waiting for: {nodeData.hitlInfo.title}</div>
                            <div>Type: {nodeData.hitlInfo.task_type} | Assigned to: {nodeData.hitlInfo.assigned_to || 'Pending'}</div>
                          </div>
                          {config.showReviewTask && hitlTaskInfo?.can_complete !== false && (
                            <button
                              onClick={() => setShowHitlReview(true)}
                              className="px-3 py-1 text-xs font-medium text-white bg-amber-600 rounded hover:bg-amber-700 transition-colors flex-shrink-0 ml-2"
                            >
                              Complete Task
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                    <div className={`text-xs ${isError ? 'text-red-600' : 'text-gray-600'}`}>
                      <div className="flex items-center gap-4">
                        <span>Started: {nodeData.startTime?.toLocaleTimeString()}</span>
                        {nodeData.endTime && <span>{isError ? 'Failed:' : 'Ended:'} {nodeData.endTime.toLocaleTimeString()}</span>}
                        {duration && <span className={`ml-auto font-medium ${isError ? 'text-red-700' : 'text-gray-700'}`}>{duration}s</span>}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {executing && Object.keys(nodeExecutionData || {}).length === 0 && (
            <div className="flex items-center justify-center gap-2 text-sm text-gray-500 py-8">
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
              <span>Starting execution...</span>
            </div>
          )}
        </div>
      </>
    );
  };

  // ── Standard ──
  const renderStandard = () => (<><StatusBanner />{renderStandardSteps()}</>);

  // ── Flow Only (pill badges) ──
  const renderFlowOnly = () => (
    <>
      <StatusBanner />
      <div className="border border-gray-200 rounded-lg p-6 bg-gray-50 min-h-[100px]">
        {executing && Object.keys(nodeExecutionData || {}).length === 0 ? (
          <div className="flex items-center justify-center gap-2 text-sm text-gray-500 py-4">
            <ArrowPathIcon className="w-5 h-5 animate-spin" />
            <span>Starting execution...</span>
          </div>
        ) : (
          <div className="flex items-center gap-1 flex-wrap justify-center">
            {Object.values(nodeExecutionData || {}).map((nd, i, arr) => (
              <React.Fragment key={nd.nodeId}>
                <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border ${
                  nd.status === 'completed' ? 'bg-green-100 text-green-700 border-green-200' :
                  nd.status === 'running' ? 'bg-blue-100 text-blue-700 border-blue-200' :
                  nd.status === 'error' ? 'bg-red-100 text-red-700 border-red-200' :
                  nd.status === 'paused' ? 'bg-amber-100 text-amber-700 border-amber-200 animate-pulse' :
                  'bg-gray-100 text-gray-600 border-gray-200'
                }`}>
                  {nd.status === 'running' && <ArrowPathIcon className="w-3 h-3 animate-spin" />}
                  {nd.status === 'completed' && <CheckCircleIcon className="w-3 h-3" />}
                  {nd.status === 'error' && <XCircleIcon className="w-3 h-3" />}
                  {nd.status === 'paused' && <HandRaisedIconFallback className="w-3 h-3" />}
                  {nd.nodeName}
                </div>
                {i < arr.length - 1 && <span className="text-gray-400 mx-0.5">→</span>}
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </>
  );

  // ── Flow with Steps ──
  const renderFlowWithSteps = () => (<>{renderFlowOnly()}<div className="mt-4">{renderStandardSteps()}</div></>);

  // ── Flow Design (ReactFlow diagram) ──
  const renderFlowDesign = () => (
    <FlowDesignDisplay
      flowNodes={flowNodes}
      flowEdges={flowEdges}
      nodeStatus={nodeStatus}
      executingNodeId={executingNodeId}
      executedNodes={executedNodes}
      executing={executing}
      nodeExecutionData={nodeExecutionData}
    />
  );

  const renderContent = () => {
    switch (displayMode) {
      case 'minimal_steps': return renderMinimalSteps();
      case 'standard': return renderStandard();
      case 'standard_steps': return <><StatusBanner />{renderStandardSteps()}</>;
      case 'flow_only': return renderFlowOnly();
      case 'flow_with_steps': return renderFlowWithSteps();
      case 'flow_design': return <><StatusBanner />{renderFlowDesign()}</>;
      case 'flow_design_steps': return <><StatusBanner />{renderFlowDesign()}<div className="mt-4">{renderStandardSteps()}</div></>;
      case 'flow_design_side_by_side': return (
        <>
          <StatusBanner />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>{renderFlowDesign()}</div>
            <div>{renderStandardSteps()}</div>
          </div>
        </>
      );
      default: return renderMinimalSteps();
    }
  };

  return (
    <div className="py-6">
      {config.title && <h2 className="text-xl font-semibold text-gray-900 mb-4">{config.title}</h2>}
      {renderContent()}

      {/* HITL Task Review Modal */}
      {config.showReviewTask && showHitlReview && hitlTaskInfo && (
        <TaskReviewModal
          task={{
            task_id: hitlTaskInfo.task_id,
            title: hitlTaskInfo.title,
            task_type: hitlTaskInfo.task_type,
            priority: hitlTaskInfo.priority,
            timeout_at: hitlTaskInfo.timeout_at,
            assigned_to: hitlTaskInfo.assigned_to,
            node_label: hitlTaskInfo.node_label,
          }}
          isOpen={true}
          onClose={() => setShowHitlReview(false)}
          onCompleted={handleHitlCompleted}
          fetchFullTask={true}
        />
      )}
    </div>
  );
}


/**
 * FlowDesignDisplay - Renders a ReactFlow diagram with node highlighting and zoom-to-node
 * Lazy-loads ReactFlow on first render.
 */
function FlowDesignDisplay({ flowNodes, flowEdges, nodeStatus, executingNodeId, executedNodes, executing, nodeExecutionData }) {
  const [loaded, setLoaded] = useState(reactFlowLoaded);
  const [rfNodes, setRfNodes] = useState([]);
  const [rfEdges, setRfEdges] = useState([]);
  const rfInstance = useRef(null);

  useEffect(() => {
    if (!loaded) {
      loadReactFlow().then(() => setLoaded(true)).catch(() => {});
    }
  }, []);

  // Initialize nodes/edges from flow definition
  useEffect(() => {
    if (!loaded || !flowNodes || flowNodes.length === 0) return;
    const cloned = flowNodes.map(node => ({
      ...node,
      data: { ...node.data, executionMode: true },
      style: { ...node.style },
    }));
    setRfNodes(cloned);
    setRfEdges(flowEdges || []);
  }, [loaded, flowNodes, flowEdges]);

  // Update node styles based on execution status
  useEffect(() => {
    if (!loaded || rfNodes.length === 0) return;
    setRfNodes(nds =>
      nds.map(node => {
        const status = nodeStatus?.[node.id];
        const isExec = node.id === executingNodeId;
        const isDone = (executedNodes || []).includes(node.id);
        return {
          ...node,
          data: {
            ...node.data,
            isExecuting: isExec,
            isExecuted: isDone,
            isPaused: status === 'paused',
            executionStatus: status,
          },
        };
      })
    );
  }, [nodeStatus, executingNodeId, executedNodes]);

  // Auto-zoom to executing node
  useEffect(() => {
    if (!executingNodeId || !rfInstance.current) return;
    const node = rfNodes.find(n => n.id === executingNodeId);
    if (node) {
      rfInstance.current.fitView({
        padding: 0.3,
        minZoom: 1,
        maxZoom: 1.5,
        duration: 400,
        nodes: [{ id: executingNodeId }],
      });
    }
  }, [executingNodeId, rfNodes]);

  if (!loaded) {
    return (
      <div className="flex items-center justify-center py-12 border border-gray-200 rounded-lg bg-gray-50">
        <ArrowPathIcon className="w-6 h-6 text-primary animate-spin" />
        <span className="ml-2 text-sm text-gray-500">Loading flow diagram...</span>
      </div>
    );
  }

  if (!flowNodes || flowNodes.length === 0) {
    return (
      <div className="border border-gray-200 rounded-lg p-8 bg-gray-50 text-center">
        <p className="text-sm text-gray-400">Flow diagram not available. Start an execution to load the flow.</p>
      </div>
    );
  }

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
  const edgeTypes = { default: CustomEdge };

  return (
    <div style={{ height: '500px' }} className="border border-gray-200 rounded-lg overflow-hidden">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onInit={(instance) => { rfInstance.current = instance; }}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2, minZoom: 0.5, maxZoom: 1.5 }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background />
        <Controls showInteractive={false} />
        <MiniMap nodeStrokeWidth={3} zoomable pannable />
      </ReactFlow>
    </div>
  );
}


function SignalIcon({ className }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.807-3.808-9.98 0-13.788m13.788 0c3.808 3.807 3.808 9.98 0 13.788M12 12h.008v.008H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
    </svg>
  );
}
