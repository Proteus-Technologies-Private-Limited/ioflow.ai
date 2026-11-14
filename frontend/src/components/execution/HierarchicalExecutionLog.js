import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  ChevronDownIcon,
  ChevronRightIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  InformationCircleIcon,
  XCircleIcon,
  CodeBracketIcon,
  BoltIcon,
  CpuChipIcon,
  ArrowPathIcon,
  ArrowUpTrayIcon,
  PauseCircleIcon,
} from '@heroicons/react/24/outline';
import { formatTimestamp as formatTimestampUtil, formatDuration as formatDurationUtil, formatDateTime } from '../../utils/dateFormatter';

const HierarchicalExecutionLog = ({
  logs = [],
  timezone = 'local',
  totalLogs,
  hasMore,
  onLoadMore,
  isLoadingMore,
  executionId,
  flowId,
  flowName,
  flowDescription
}) => {
  const [expandedNodes, setExpandedNodes] = useState(new Set());
  const [expandedIterations, setExpandedIterations] = useState(new Set());
  const [autoExpandedErrors, setAutoExpandedErrors] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [showRawData, setShowRawData] = useState(new Set());
  const [loadedLogData, setLoadedLogData] = useState({});
  const [loadingLogData, setLoadingLogData] = useState(new Set());
  const [isLoadingAllData, setIsLoadingAllData] = useState(false);
  const [showCopyDialog, setShowCopyDialog] = useState(false);
  const [expandedDataKeys, setExpandedDataKeys] = useState(new Set());

  // Use ref to always have the latest loaded data for copy
  const loadedLogDataRef = useRef({});
  useEffect(() => {
    loadedLogDataRef.current = loadedLogData;
  }, [loadedLogData]);

  // Group logs by node and detect loop iterations
  const groupedLogsData = useMemo(() => {
    // Ensure logs is an array
    const logsArray = Array.isArray(logs) ? logs : [];

    const groups = {};
    const nodeStartTimes = {};
    const nodeEndTimes = {};
    let currentLoopContext = null;

    // Find the earliest timestamp to use as the execution start time
    const executionStartTime = logsArray.length > 0
      ? Math.min(...logsArray.map(log => new Date(log.timestamp).getTime()))
      : null;
    
    logsArray.forEach((log, logIndex) => {
      // For error logs, try to get the actual node_id from the data if available
      let nodeId = log.step_id || 'flow';

      // If this is an error log with node information in data, use that instead
      if (log.level === 'error' && log.data?.node_id && log.data.node_id !== 'flow' && log.step_id === 'flow') {
        nodeId = log.data.node_id;
      }
      
      // Check if this log belongs to a loop
      const belongsToLoop = log.data?.loop_node_id || log.data?.loop_context?.loop_node_id;
      
      // Only initialize group if it doesn't belong to a loop OR if it's the loop node itself
      if (!groups[nodeId] && (!belongsToLoop || nodeId === belongsToLoop)) {
        groups[nodeId] = {
          nodeId,
          logs: [],
          nodeType: null,
          nodeLabel: null,
          startTime: null,
          endTime: null,
          duration: null,
          hasError: false,
          hasWarning: false,
          hasSuccess: false,
          hasPaused: false,
          iterations: {},
          isLoop: false,
        };
      }
      
      // Extract node info from log data (only if group exists)
      if (groups[nodeId]) {
        // Extract node type
        if (log.data?.node_type) {
          groups[nodeId].nodeType = log.data.node_type;
          if (log.data.node_type === 'loop') {
            groups[nodeId].isLoop = true;
          }
        }

        // Extract node label - always prefer the label from data fields
        let extractedLabel = null;
        let labelSource = null;

        // Priority 1: Direct label fields from data (most reliable)
        if (log.data?.label && typeof log.data.label === 'string' && log.data.label.trim()) {
          extractedLabel = log.data.label.trim();
          labelSource = 'data.label';
        } else if (log.data?.node_label && typeof log.data.node_label === 'string' && log.data.node_label.trim()) {
          extractedLabel = log.data.node_label.trim();
          labelSource = 'data.node_label';
        } else if (log.data?.node_name && typeof log.data.node_name === 'string' && log.data.node_name.trim()) {
          extractedLabel = log.data.node_name.trim();
          labelSource = 'data.node_name';
        }

        // Priority 2: Extract from specific action/transform messages
        if (!extractedLabel && log.message) {
          // Pattern for "Executing [type] node: [Label]"
          const execPattern = log.message.match(/executing\s+(?:action|transform|trigger|condition|response|loop|human_in_loop)\s+node:\s*(.+?)$/i);
          if (execPattern) {
            extractedLabel = execPattern[1].trim();
            labelSource = 'exec_message';
          }
          // Pattern for completion messages with labels (skip generic suffixes like "flow resuming")
          else if (log.message.includes('✅') && log.message.includes(' - ')) {
            const completionMatch = log.message.match(/✅.*?[-–]\s*(.+?)$/);
            if (completionMatch) {
              const candidate = completionMatch[1].trim();
              // Skip generic completion suffixes
              if (!candidate.match(/^(flow resuming|flow completed|completed|done)$/i)) {
                extractedLabel = candidate;
                labelSource = 'completion_message';
              }
            }
          }
        }

        // Only update if we found a meaningful label (not a service name or generic ID)
        if (extractedLabel) {
          // Skip if it looks like a service/method name (e.g., generate_content, create_spreadsheet)
          const looksLikeServiceName = /^[a-z_]+$/.test(extractedLabel) && !extractedLabel.includes(' ');

          // Always update if current label is missing or is the node ID
          if (!groups[nodeId].nodeLabel || groups[nodeId].nodeLabel === nodeId) {
            if (!looksLikeServiceName) {
              groups[nodeId].nodeLabel = extractedLabel;
            }
          }
          // Update if we have a better label (with spaces/proper name) than current
          else if (!looksLikeServiceName && groups[nodeId].nodeLabel && /^[a-z_]+$/.test(groups[nodeId].nodeLabel)) {
            groups[nodeId].nodeLabel = extractedLabel;
          }
          // Always prefer data labels over message-extracted labels
          else if ((labelSource === 'data.label' || labelSource === 'data.node_label') &&
                   !looksLikeServiceName) {
            groups[nodeId].nodeLabel = extractedLabel;
          }
        }

        // If we still don't have a label and nodeId looks like a service name,
        // try to find a better label from other logs in this group
        if ((!groups[nodeId].nodeLabel || groups[nodeId].nodeLabel === nodeId) && nodeId && /^[a-z_]+$/.test(nodeId)) {
          // This will be updated as more logs are processed for this node
          groups[nodeId].needsLabelUpdate = true;
        }
      }
      
      // Check if this is a loop start
      if (log.message?.includes('Starting') && log.message?.includes('loop')) {
        currentLoopContext = {
          nodeId: nodeId,
          currentIteration: -1,
          lastSeenNodeExecution: {},
          detectedIterations: new Set()
        };
        // Add this log to the loop node (if group exists)
        if (groups[nodeId]) {
          groups[nodeId].logs.push(log);
        }
      }
      // Check if loop is ending
      else if ((log.message?.includes('Node completed successfully') && log.step_id === currentLoopContext?.nodeId) ||
               log.message?.includes('loop completed')) {
        // Add completion log to the loop node (if group exists)
        if (groups[nodeId]) {
          groups[nodeId].logs.push(log);
        }
        currentLoopContext = null;
      }
      // If we're in a loop context OR if the log has loop context
      else if (currentLoopContext || log.data?.loop_node_id || log.data?.loop_context) {
        // Determine which loop this belongs to
        const loopNodeId = log.data?.loop_context?.loop_node_id || log.data?.loop_node_id || currentLoopContext?.nodeId;
        
        // Check if this is part of the loop node itself
        if (nodeId === loopNodeId && groups[nodeId]) {
          groups[nodeId].logs.push(log);
        } 
        // Check if this log explicitly belongs to a loop (has loop context)
        else if (log.data?.loop_node_id || log.data?.loop_context) {
          // This is definitely a node inside the loop
          let iterationNumber = -1;
          
          // First check if backend provided loop context
          if (log.data?.loop_context?.iteration_count !== undefined) {
            iterationNumber = log.data.loop_context.iteration_count - 1; // Convert to 0-based index
            if (currentLoopContext) {
              currentLoopContext.currentIteration = iterationNumber;
              currentLoopContext.detectedIterations.add(iterationNumber);
            }
          }
          // Fallback to simple loop_iteration field
          else if (log.data?.loop_iteration !== undefined) {
            iterationNumber = log.data.loop_iteration - 1; // Convert to 0-based index
            if (currentLoopContext) {
              currentLoopContext.currentIteration = iterationNumber;
              currentLoopContext.detectedIterations.add(iterationNumber);
            }
          }
          // Fallback: Try to detect iteration from mapped parameters
          else if (log.data?.mapped && typeof log.data.mapped === 'object') {
            Object.values(log.data.mapped).forEach(value => {
              if (typeof value === 'string' && value.includes('Processing item:')) {
                const match = value.match(/Processing item: (\d+) of: (\d+)/);
                if (match) {
                  iterationNumber = parseInt(match[1]) - 1; // Convert to 0-based
                  currentLoopContext.currentIteration = iterationNumber;
                  currentLoopContext.detectedIterations.add(iterationNumber);
                }
              }
            });
          }
          
          // If we still don't have an iteration number and this is a new node execution
          if (iterationNumber === -1 && log.message?.includes('Executing') && log.message?.includes('node:')) {
            // Check if we've seen this node execute before
            if (currentLoopContext.lastSeenNodeExecution[nodeId] !== undefined) {
              // We've seen this node before, so this must be a new iteration
              iterationNumber = currentLoopContext.detectedIterations.size;
              currentLoopContext.currentIteration = iterationNumber;
              currentLoopContext.detectedIterations.add(iterationNumber);
            } else {
              // First time seeing this node, it's iteration 0
              iterationNumber = 0;
              currentLoopContext.currentIteration = 0;
              currentLoopContext.detectedIterations.add(0);
            }
            currentLoopContext.lastSeenNodeExecution[nodeId] = logIndex;
          }
          
          // Use the current iteration if we have one
          if (iterationNumber === -1 && currentLoopContext.currentIteration !== -1) {
            iterationNumber = currentLoopContext.currentIteration;
          }
          
          // If we still don't have an iteration, default to 0
          if (iterationNumber === -1) {
            iterationNumber = 0;
            currentLoopContext.currentIteration = 0;
          }
          
          // Store logs in the loop iterations
          const loopNodeId = log.data?.loop_node_id || currentLoopContext.nodeId;
          
          // Ensure the loop node group exists
          if (!groups[loopNodeId]) {
            groups[loopNodeId] = {
              nodeId: loopNodeId,
              logs: [],
              nodeType: 'loop',
              nodeLabel: 'Loop',
              startTime: null,
              endTime: null,
              duration: null,
              hasError: false,
              hasWarning: false,
              hasSuccess: false,
              hasPaused: false,
              iterations: {},
              isLoop: true,
            };
          }
          
          if (!groups[loopNodeId].iterations[iterationNumber]) {
            groups[loopNodeId].iterations[iterationNumber] = {
              logs: [],
              nodes: {},
              iterationNumber: iterationNumber + 1
            };
          }
          
          // Add log to iteration
          groups[loopNodeId].iterations[iterationNumber].logs.push(log);
          
          // Group by node within iteration
          if (!groups[loopNodeId].iterations[iterationNumber].nodes[nodeId]) {
            // Extract label using the same logic as main nodes
            let iterNodeLabel = null;
            if (log.data?.node_label && typeof log.data.node_label === 'string') {
              iterNodeLabel = log.data.node_label;
            } else if (log.data?.label && typeof log.data.label === 'string') {
              iterNodeLabel = log.data.label;
            } else if (log.data?.node_name && typeof log.data.node_name === 'string') {
              iterNodeLabel = log.data.node_name;
            }

            groups[loopNodeId].iterations[iterationNumber].nodes[nodeId] = {
              nodeId,
              nodeType: log.data?.node_type,
              nodeLabel: iterNodeLabel || nodeId,
              logs: [],
              hasError: false
            };
          }
          groups[loopNodeId].iterations[iterationNumber].nodes[nodeId].logs.push(log);
          // Track errors in iteration nodes
          if (log.level === 'error') {
            groups[loopNodeId].iterations[iterationNumber].nodes[nodeId].hasError = true;
          }
        }
        // If currentLoopContext exists but this log doesn't have loop_node_id, it's outside the loop
        else if (currentLoopContext && !log.data?.loop_node_id && !log.data?.loop_context) {
          // This node is executed after the loop context started but is not part of the loop
          if (groups[nodeId]) {
            groups[nodeId].logs.push(log);
          }
        }
      } else {
        // Not in a loop, add to regular node logs (only if group exists)
        if (groups[nodeId]) {
          groups[nodeId].logs.push(log);
        }
      }
      
      // Track start and end times
      const timestamp = new Date(log.timestamp);
      if (!nodeStartTimes[nodeId] || timestamp < nodeStartTimes[nodeId]) {
        nodeStartTimes[nodeId] = timestamp;
      }
      if (!nodeEndTimes[nodeId] || timestamp > nodeEndTimes[nodeId]) {
        nodeEndTimes[nodeId] = timestamp;
      }
      
      // Track errors, warnings, and success (only if group exists)
      if (groups[nodeId]) {
        if (log.level === 'error') groups[nodeId].hasError = true;
        if (log.level === 'warning') groups[nodeId].hasWarning = true;

        // Check for paused indicators (HITL)
        if (log.message?.includes('⏸️') || log.message?.includes('waiting for human')) {
          groups[nodeId].hasPaused = true;
          // Store paused timestamp and assignment info
          const pausedAt = log.data?.paused_at || log.timestamp;
          groups[nodeId].pausedAt = pausedAt;
          groups[nodeId].hitlAssignedTo = log.data?.assigned_to;
          groups[nodeId].hitlTaskId = log.data?.task_id;
        }

        // Track HITL completion time — use completed_at from data, or the log timestamp of any success log
        if (groups[nodeId].hasPaused) {
          if (log.data?.completed_at) {
            groups[nodeId].hitlCompletedAt = log.data.completed_at;
          } else if (
            !groups[nodeId].hitlCompletedAt &&
            (log.message?.includes('✅') || log.data?.execution_stage === 'node_complete')
          ) {
            groups[nodeId].hitlCompletedAt = log.timestamp;
          }
        }

        // Check for success indicators
        if (log.message?.includes('✅') ||
            log.message?.includes('completed') ||
            log.message?.includes('successful') ||
            log.data?.execution_stage === 'node_complete') {
          groups[nodeId].hasSuccess = true;
        }
      }
    });
    
    // Process iterations to add timing metadata
    Object.keys(groups).forEach(nodeId => {
      const group = groups[nodeId];
      if (group.isLoop && Object.keys(group.iterations).length > 0) {
        Object.keys(group.iterations).forEach(iterNum => {
          const iteration = group.iterations[iterNum];
          let iterStartTime = null;
          let iterEndTime = null;
          
          // Calculate timing from all logs in the iteration
          iteration.logs.forEach(log => {
            const timestamp = new Date(log.timestamp);
            if (!iterStartTime || timestamp < iterStartTime) {
              iterStartTime = timestamp;
            }
            if (!iterEndTime || timestamp > iterEndTime) {
              iterEndTime = timestamp;
            }
          });
          
          iteration.startTime = iterStartTime;
          iteration.endTime = iterEndTime;
          iteration.duration = iterEndTime && iterStartTime ? iterEndTime - iterStartTime : null;
        });
      }
    });
    
    // Calculate durations
    Object.keys(groups).forEach(nodeId => {
      if (nodeStartTimes[nodeId] && nodeEndTimes[nodeId]) {
        groups[nodeId].startTime = nodeStartTimes[nodeId];
        groups[nodeId].endTime = nodeEndTimes[nodeId];
        groups[nodeId].duration = nodeEndTimes[nodeId] - nodeStartTimes[nodeId];
      }
    });
    
    // Post-process groups to clean up labels
    Object.values(groups).forEach(group => {
      // Fix groups where nodeId looks wrong (e.g., "extracted 4 parameters")
      if (group.nodeId && group.nodeId.includes(' ') && !group.nodeLabel) {
        // This nodeId is probably wrong, try to extract actual label
        const match = group.nodeId.match(/^(.+?)\s+\(/);
        if (match) {
          group.nodeLabel = match[1];
        } else {
          group.nodeLabel = group.nodeId;
        }
        // Mark this as needing ID correction
        group.nodeId = 'unknown_' + Math.random().toString(36).substr(2, 9);
      }

      // If nodeLabel is still missing or same as nodeId, check for service names
      if (!group.nodeLabel || group.nodeLabel === group.nodeId) {
        // Check if nodeId is a service name (like generate_content, create_spreadsheet)
        if (group.nodeId && /^[a-z_]+$/.test(group.nodeId)) {
          // Look through logs for a better label
          for (const log of group.logs) {
            if (log.data?.label && typeof log.data.label === 'string' && !log.data.label.includes('_')) {
              group.nodeLabel = log.data.label;
              break;
            } else if (log.data?.node_label && typeof log.data.node_label === 'string' && !log.data.node_label.includes('_')) {
              group.nodeLabel = log.data.node_label;
              break;
            } else if (log.message && log.message.includes('Executing action node:')) {
              const match = log.message.match(/Executing action node:\s*(.+?)$/);
              if (match) {
                group.nodeLabel = match[1].trim();
                break;
              }
            }
          }
        }
      }
    });

    // Sort by start time
    const sortedGroups = Object.values(groups).sort((a, b) =>
      (a.startTime || 0) - (b.startTime || 0)
    );

    return { groups: sortedGroups, executionStartTime };
  }, [logs]);

  // Destructure the result from useMemo
  const { groups: groupedLogs, executionStartTime } = groupedLogsData || { groups: [], executionStartTime: null };

  // Compute HITL wait times once (stable, no flickering)
  const hitlSummary = useMemo(() => {
    const parseTS = (ts) => {
      if (!ts) return null;
      const s = String(ts);
      return new Date(!s.endsWith('Z') && !s.includes('+') ? s + 'Z' : s);
    };
    const hitlGroups = groupedLogs.filter(g => g.hasPaused);
    if (hitlGroups.length === 0) return null;
    const now = new Date();
    let totalWaitMs = 0;
    let hasWaiting = false;
    hitlGroups.forEach(g => {
      const paused = parseTS(g.pausedAt);
      const resumed = g.hasSuccess ? parseTS(g.hitlCompletedAt || g.endTime) : null;
      const waitMs = paused ? (resumed || now) - paused : 0;
      g._hitlWaitMs = waitMs;
      totalWaitMs += waitMs;
      if (!g.hasSuccess) hasWaiting = true;
    });
    return { totalWaitMs, hitlCount: hitlGroups.length, hasWaiting };
  }, [groupedLogs]);

  // Auto-expand nodes with errors on first load
  useEffect(() => {
    if (!autoExpandedErrors && groupedLogs.length > 0) {
      const nodesWithErrors = new Set();
      groupedLogs.forEach(group => {
        if (group.hasError) {
          nodesWithErrors.add(group.nodeId);
        }
      });
      if (nodesWithErrors.size > 0) {
        setExpandedNodes(prev => new Set([...prev, ...nodesWithErrors]));
        setAutoExpandedErrors(true);
      }
    }
  }, [groupedLogs, autoExpandedErrors]);

  // Load all log data for all logs
  const loadAllLogData = useCallback(async (shouldShowData = false) => {
    setIsLoadingAllData(true);
    
    try {
      // Get all logs that need data loading
      const logsToLoad = [];
      const allLogIds = []; // Track all log IDs that have or will have data
      const existingDataToStore = {}; // Track logs that already have data
      
      // Collect all logs from grouped structure
      groupedLogs.forEach(group => {
        // Regular logs
        group.logs.forEach(log => {
          if (!loadedLogData[log.log_id] && !log.data) {
            // Need to load this log's data
            logsToLoad.push(log);
          } else if (log.data && !loadedLogData[log.log_id]) {
            // Log already has data but not in loadedLogData state
            existingDataToStore[log.log_id] = log.data;
            allLogIds.push(log.log_id);
          } else if (loadedLogData[log.log_id]) {
            // Data already loaded
            allLogIds.push(log.log_id);
          }
        });
        
        // Loop iteration logs
        if (group.isLoop && group.iterations) {
          Object.values(group.iterations).forEach(iteration => {
            Object.values(iteration.nodes).forEach(iterNode => {
              iterNode.logs.forEach(log => {
                if (!loadedLogData[log.log_id] && !log.data) {
                  // Need to load this log's data
                  logsToLoad.push(log);
                } else if (log.data && !loadedLogData[log.log_id]) {
                  // Log already has data but not in loadedLogData state
                  existingDataToStore[log.log_id] = log.data;
                  allLogIds.push(log.log_id);
                } else if (loadedLogData[log.log_id]) {
                  // Data already loaded
                  allLogIds.push(log.log_id);
                }
              });
            });
          });
        }
      });
      
      // Store any existing data that wasn't in loadedLogData
      if (Object.keys(existingDataToStore).length > 0) {
        console.log('[loadAllLogData] Storing existing data:', Object.keys(existingDataToStore).length);
        setLoadedLogData(prev => ({
          ...prev,
          ...existingDataToStore
        }));
      }
      
      if (logsToLoad.length === 0) {
        console.log('[loadAllLogData] No logs to load, all data already present');
        // If shouldShowData is true and all data is already loaded, expand all
        if (shouldShowData && allLogIds.length > 0) {
          setShowRawData(new Set(allLogIds));
        }
        setIsLoadingAllData(false);
        return true; // All data already loaded
      }
      
      // Load data for each log in batches to avoid overwhelming the server
      const batchSize = 10;
      const loadedLogIds = [];
      
      for (let i = 0; i < logsToLoad.length; i += batchSize) {
        const batch = logsToLoad.slice(i, i + batchSize);
        const promises = batch.map(log => {
          if (log.execution_id && log.log_id) {
            return axios.get(
              `/api/v1/executions/${log.execution_id}/logs?log_id=${log.log_id}&include_data=true&fields=log_id,data`
            ).then(response => {
              const logs = response.data.logs;
              if (logs && logs.length > 0 && logs[0].data) {
                loadedLogIds.push(log.log_id);
                return { log_id: log.log_id, data: logs[0].data };
              }
              return null;
            }).catch(error => {
              console.error(`Failed to load data for log ${log.log_id}:`, error);
              return null;
            });
          }
          return Promise.resolve(null);
        });
        
        const results = await Promise.all(promises);
        
        // Update loaded data state
        const newLoadedData = {};
        results.forEach(result => {
          if (result && result.log_id && result.data) {
            newLoadedData[result.log_id] = result.data;
          }
        });
        
        if (Object.keys(newLoadedData).length > 0) {
          console.log('[loadAllLogData] Batch loaded:', Object.keys(newLoadedData).length, 'logs');
          setLoadedLogData(prev => {
            const updated = {
              ...prev,
              ...newLoadedData
            };
            console.log('[loadAllLogData] Total loaded data after batch:', Object.keys(updated).length);
            return updated;
          });
        }
      }
      
      // If shouldShowData is true, expand all logs that now have data
      if (shouldShowData) {
        // Combine all sources of log data
        const allLogsWithData = new Set([
          ...loadedLogIds,
          ...Object.keys(existingDataToStore),
          ...Object.keys(loadedLogData),
          ...allLogIds // Use the allLogIds we already collected
        ]);
        
        setShowRawData(allLogsWithData);
      }
      
      setIsLoadingAllData(false);
      return true;
    } catch (error) {
      console.error('Failed to load all log data:', error);
      setIsLoadingAllData(false);
      return false;
    }
  }, [groupedLogs, loadedLogData]);

  // Fetch log data on demand
  const fetchLogData = useCallback(async (log) => {
    // Check if data is already loaded or currently loading
    if (loadedLogData[log.log_id] || loadingLogData.has(log.log_id)) {
      return;
    }
    
    // If data is already present in the log object, use it directly
    if (log.data) {
      setLoadedLogData(prev => ({
        ...prev,
        [log.log_id]: log.data
      }));
      return;
    }
    
    // Mark as loading
    setLoadingLogData(prev => new Set(prev).add(log.log_id));
    
    try {
      // Extract execution_id from the log if available
      const executionId = log.execution_id;
      if (!executionId) {
        console.error('No execution_id found for log:', log.log_id);
        return;
      }
      
      // Fetch just this specific log's data by ID
      const response = await axios.get(
        `/api/v1/executions/${executionId}/logs?log_id=${log.log_id}&include_data=true&fields=log_id,data`
      );
      
      // The API should return only the requested log
      const logs = response.data.logs;
      if (logs && logs.length > 0 && logs[0].data) {
        setLoadedLogData(prev => ({
          ...prev,
          [log.log_id]: logs[0].data
        }));
      }
    } catch (error) {
      console.error('Failed to fetch log data:', error);
    } finally {
      // Remove from loading
      setLoadingLogData(prev => {
        const newSet = new Set(prev);
        newSet.delete(log.log_id);
        return newSet;
      });
    }
  }, [loadedLogData, loadingLogData]);

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

  // Toggle iteration expansion
  const toggleIteration = useCallback((iterationKey) => {
    setExpandedIterations(prev => {
      const newSet = new Set(prev);
      if (newSet.has(iterationKey)) {
        newSet.delete(iterationKey);
      } else {
        newSet.add(iterationKey);
      }
      return newSet;
    });
  }, []);

  // Expand/Collapse all
  const expandAll = useCallback(() => {
    setExpandedNodes(new Set(groupedLogs.map(g => g.nodeId)));
    // Also expand all iterations
    const iterationKeys = [];
    groupedLogs.forEach(group => {
      if (group.isLoop && group.iterations) {
        Object.keys(group.iterations).forEach(iterNum => {
          iterationKeys.push(`${group.nodeId}-${iterNum}`);
        });
      }
    });
    setExpandedIterations(new Set(iterationKeys));
  }, [groupedLogs]);

  const collapseAll = useCallback(() => {
    setExpandedNodes(new Set());
    setExpandedIterations(new Set());
  }, []);

  // Helper function to truncate large content for clipboard and display
  const truncateFileContent = useCallback((data) => {
    if (!data || typeof data !== 'object') return data;
    
    const MAX_STRING_LENGTH = 1000; // Maximum characters for any string field
    const PREVIEW_LENGTH = 200; // Preview length for truncated content
    const MAX_ARRAY_ITEMS = 10; // Maximum array items to show
    
    const truncateValue = (value, key = '') => {
      if (value === null || value === undefined) {
        return value;
      }
      
      if (typeof value === 'string') {
        if (value.length > MAX_STRING_LENGTH) {
          // For any long string, show just a preview
          const preview = value.substring(0, PREVIEW_LENGTH);
          const totalLength = value.length;
          const lineCount = value.split('\n').length;
          
          // Show line count if it's multiline content
          if (lineCount > 1) {
            return `${preview}... [TRUNCATED - ${totalLength} chars, ${lineCount} lines]`;
          } else {
            return `${preview}... [TRUNCATED - ${totalLength} chars]`;
          }
        }
        return value;
      }
      
      if (Array.isArray(value)) {
        if (value.length > MAX_ARRAY_ITEMS) {
          // Show first few items and indicate total count
          const preview = value.slice(0, MAX_ARRAY_ITEMS).map(item => truncateValue(item));
          return [...preview, `... and ${value.length - MAX_ARRAY_ITEMS} more items`];
        }
        return value.map(item => truncateValue(item));
      }
      
      if (typeof value === 'object') {
        const result = {};
        for (const [k, v] of Object.entries(value)) {
          result[k] = truncateValue(v, k);
        }
        return result;
      }
      
      return value;
    };
    
    return truncateValue(data);
  }, []);

  // Copy to clipboard
  const copyToClipboard = useCallback(async (content, id) => {
    try {
      // If content is an object, truncate file content before copying
      const processedContent = typeof content === 'object' && content !== null
        ? truncateFileContent(content)
        : content;
      const text = typeof processedContent === 'string' ? processedContent : JSON.stringify(processedContent, null, 2);
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, [truncateFileContent]);

  // Use the imported formatTimestamp utility
  const formatTimestamp = formatTimestampUtil;

  // Helper to format elapsed time from execution start
  const formatElapsedTime = (timestamp) => {
    if (!executionStartTime || !timestamp) return '';
    const elapsed = new Date(timestamp).getTime() - executionStartTime;
    if (elapsed < 0) return '0ms';

    // Format the elapsed time
    if (elapsed < 1000) {
      return `${elapsed}ms`;
    } else if (elapsed < 60000) {
      const seconds = Math.floor(elapsed / 1000);
      const ms = elapsed % 1000;
      return ms > 0 ? `${seconds}.${String(ms).padStart(3, '0')}s` : `${seconds}s`;
    } else {
      const minutes = Math.floor(elapsed / 60000);
      const seconds = Math.floor((elapsed % 60000) / 1000);
      return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
    }
  };

  // Helper to format duration in milliseconds
  const formatDurationMs = (durationMs) => {
    if (durationMs === null || durationMs === undefined || durationMs < 0) return '';

    if (durationMs < 1000) {
      return `${Math.round(durationMs)}ms`;
    } else if (durationMs < 60000) {
      const seconds = Math.floor(durationMs / 1000);
      const ms = Math.round(durationMs % 1000);
      return ms > 0 ? `${seconds}.${String(ms).padStart(3, '0').replace(/0+$/, '')}s` : `${seconds}s`;
    } else {
      const minutes = Math.floor(durationMs / 60000);
      const seconds = Math.floor((durationMs % 60000) / 1000);
      return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`;
    }
  };

  // Check if all data is loaded
  const checkAllDataLoaded = useCallback(() => {
    let hasUnloadedData = false;
    
    groupedLogs.forEach(group => {
      // Check regular logs
      group.logs.forEach(log => {
        if (!loadedLogData[log.log_id] && !log.data) {
          hasUnloadedData = true;
        }
      });
      
      // Check loop iteration logs
      if (group.isLoop && group.iterations) {
        Object.values(group.iterations).forEach(iteration => {
          Object.values(iteration.nodes).forEach(iterNode => {
            iterNode.logs.forEach(log => {
              if (!loadedLogData[log.log_id] && !log.data) {
                hasUnloadedData = true;
              }
            });
          });
        });
      }
    });
    
    return !hasUnloadedData;
  }, [groupedLogs, loadedLogData]);

  // Perform the actual copy operation
  const performCopy = useCallback(async () => {
    // Use the ref to get the latest loaded data
    const currentLoadedData = loadedLogDataRef.current;

    console.log('[performCopy] Starting copy with:', {
      groupedLogsCount: groupedLogs.length,
      loadedLogDataKeys: Object.keys(currentLoadedData).length,
      totalLogs: groupedLogs.reduce((sum, g) => sum + g.logs.length, 0)
    });

    // Add flow information header
    let flowHeader = '═══════════════════════════════════════════════════════════════\n';
    flowHeader += 'FLOW EXECUTION LOG\n';
    flowHeader += '═══════════════════════════════════════════════════════════════\n\n';

    if (flowName) flowHeader += `Flow Name: ${flowName}\n`;
    if (flowId) flowHeader += `Flow ID: ${flowId}\n`;
    if (flowDescription) flowHeader += `Description: ${flowDescription}\n`;
    if (executionId) flowHeader += `Execution ID: ${executionId}\n`;

    flowHeader += `Generated: ${formatDateTime(new Date())}\n`;
    flowHeader += `Total Nodes: ${groupedLogs.length}\n`;
    flowHeader += `Total Logs: ${groupedLogs.reduce((sum, g) => sum + g.logs.length, 0)}\n`;
    flowHeader += '\n═══════════════════════════════════════════════════════════════\n\n';

    const logText = groupedLogs.map(group => {
      // Include node ID in the header
      const nodeInfo = group.nodeLabel && group.nodeLabel !== group.nodeId
        ? `${group.nodeLabel} [${group.nodeId}]`
        : group.nodeId;
      const header = `=== ${nodeInfo} (${group.nodeType || 'flow'}) ===`;
      const duration = group.duration ? `Duration: ${formatDurationMs(group.duration)}` : '';
      
      // Process regular logs
      const regularLogs = group.logs.map(log => {
        // Use loaded data from ref if available, otherwise use log.data
        const logData = currentLoadedData[log.log_id] || log.data;
        // Truncate file content in log data before copying
        const truncatedData = logData ? truncateFileContent(logData) : null;
        return `[${formatTimestampUtil(log.timestamp)}] ${log.level.toUpperCase()}: ${log.message}${
          truncatedData ? '\nData: ' + JSON.stringify(truncatedData, null, 2) : ''
        }`;
      }).join('\n');
      
      // Process loop iterations if present
      let iterationLogs = '';
      if (group.isLoop && Object.keys(group.iterations).length > 0) {
        iterationLogs = Object.entries(group.iterations)
          .sort(([a], [b]) => parseInt(a) - parseInt(b))
          .map(([iterNum, iteration]) => {
            const iterHeader = `\n  --- Iteration ${iteration.iterationNumber} ---`;
            const iterDuration = iteration.duration ? `  Duration: ${formatDurationMs(iteration.duration)}` : '';
            
            const iterNodeLogs = Object.values(iteration.nodes).map(iterNode => {
              const nodeHeader = `    [${iterNode.nodeLabel || iterNode.nodeId}] (${iterNode.nodeType})`;
              const nodeLogs = iterNode.logs.map(log => {
                // Use loaded data from ref if available, otherwise use log.data
                const logData = currentLoadedData[log.log_id] || log.data;
                // Truncate file content in log data before copying
                const truncatedData = logData ? truncateFileContent(logData) : null;
                return `      [${formatTimestampUtil(log.timestamp)}] ${log.level.toUpperCase()}: ${log.message}${
                  truncatedData ? '\n      Data: ' + JSON.stringify(truncatedData, null, 2).split('\n').join('\n      ') : ''
                }`;
              }).join('\n');
              
              return `${nodeHeader}\n${nodeLogs}`;
            }).join('\n\n');
            
            return [iterHeader, iterDuration, iterNodeLogs].filter(Boolean).join('\n');
          }).join('\n');
      }
      
      return [header, duration, regularLogs, iterationLogs].filter(Boolean).join('\n');
    }).join('\n\n');

    // Combine flow header with log text
    const fullText = flowHeader + logText;
    await copyToClipboard(fullText, 'all-logs');
  }, [groupedLogs, copyToClipboard, truncateFileContent, flowName, flowId, flowDescription, executionId, formatDurationMs]); // Added flow props and formatDurationMs

  // Copy all logs with dialog for loading data
  const copyAllLogs = useCallback(async () => {
    // Check if all data is loaded
    const allDataLoaded = checkAllDataLoaded();
    
    if (!allDataLoaded) {
      // Show dialog asking user whether to load all data
      setShowCopyDialog(true);
    } else {
      // All data already loaded, perform copy directly
      await performCopy();
    }
  }, [checkAllDataLoaded, performCopy]);

  // Handle dialog response for loading data
  const handleCopyDialogResponse = useCallback(async (shouldLoadData) => {
    setShowCopyDialog(false);
    
    if (shouldLoadData) {
      // User wants to load all data first and show it
      console.log('[handleCopyDialogResponse] Loading all data before copy');
      await loadAllLogData(true); // Pass true to show the data after loading
      
      // Use setTimeout to ensure state updates are complete
      setTimeout(() => {
        console.log('[handleCopyDialogResponse] Performing copy after delay');
        performCopy();
      }, 500); // Increased delay to ensure state updates
    } else {
      // User wants to copy only loaded data
      console.log('[handleCopyDialogResponse] Copying only loaded data');
      await performCopy();
    }
  }, [loadAllLogData, performCopy]);

  // Toggle expansion of data keys
  const toggleDataKey = useCallback((key) => {
    setExpandedDataKeys(prev => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  }, []);

  // Render expandable data value
  const renderDataValue = useCallback((value, key = '', depth = 0, logId = '') => {
    const fullKey = `${logId}:${key}`;
    const isExpanded = expandedDataKeys.has(fullKey);
    const MAX_STRING_DISPLAY = 500;
    const MAX_ARRAY_DISPLAY = 5;

    if (value === null) {
      return <span className="text-gray-400 italic">null</span>;
    }

    if (value === undefined) {
      return <span className="text-gray-400 italic">undefined</span>;
    }

    if (typeof value === 'boolean') {
      return (
        <span className={value ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
          {String(value)}
        </span>
      );
    }

    if (typeof value === 'string') {
      // Check if it's a URL
      if (value.match(/^https?:\/\//)) {
        return (
          <a
            href={value}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline text-xs"
          >
            {value.length > MAX_STRING_DISPLAY ? value.substring(0, MAX_STRING_DISPLAY) + '...' : value}
          </a>
        );
      }

      // Handle long strings with show more/less
      if (value.length > MAX_STRING_DISPLAY) {
        return (
          <span className="text-gray-900">
            <span className="text-xs">
              "{isExpanded ? value : value.substring(0, MAX_STRING_DISPLAY)}..."
            </span>
            <button
              onClick={() => toggleDataKey(fullKey)}
              className="ml-2 text-xs text-blue-600 hover:text-blue-800"
            >
              {isExpanded ? 'Show less' : `Show all (${value.length} chars)`}
            </button>
          </span>
        );
      }

      return <span className="text-gray-900 text-xs">"{value}"</span>;
    }

    if (typeof value === 'number') {
      return <span className="text-blue-600 font-medium text-xs">{value}</span>;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return <span className="text-gray-400 text-xs">[]</span>;
      }

      const displayItems = isExpanded ? value : value.slice(0, MAX_ARRAY_DISPLAY);
      const hasMore = value.length > MAX_ARRAY_DISPLAY;

      return (
        <div className="inline-block w-full">
          <button
            onClick={() => toggleDataKey(fullKey)}
            className="inline-flex items-center text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <ChevronDownIcon className="h-3 w-3" />
            ) : (
              <ChevronRightIcon className="h-3 w-3" />
            )}
            <span className="ml-1 text-gray-500 text-xs">
              Array[{value.length}]
            </span>
          </button>
          {(isExpanded || (!isExpanded && value.length <= MAX_ARRAY_DISPLAY)) && (
            <div className="mt-1 ml-4 space-y-1">
              {displayItems.map((item, index) => (
                <div key={index} className="flex items-start">
                  <span className="text-gray-500 mr-2 font-mono text-xs">
                    [{index}]:
                  </span>
                  <div className="flex-1">
                    {renderDataValue(item, `${key}[${index}]`, depth + 1, logId)}
                  </div>
                </div>
              ))}
              {!isExpanded && hasMore && (
                <div className="text-gray-500 text-xs italic">
                  ... and {value.length - MAX_ARRAY_DISPLAY} more items
                </div>
              )}
            </div>
          )}
        </div>
      );
    }

    if (typeof value === 'object') {
      const entries = Object.entries(value);
      if (entries.length === 0) {
        return <span className="text-gray-400 text-xs">{'{}'}</span>;
      }

      return (
        <div className="inline-block w-full">
          <button
            onClick={() => toggleDataKey(fullKey)}
            className="inline-flex items-center text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <ChevronDownIcon className="h-3 w-3" />
            ) : (
              <ChevronRightIcon className="h-3 w-3" />
            )}
            <span className="ml-1 text-gray-500 text-xs">
              Object{entries.length > 0 && `{${entries.length}}`}
            </span>
          </button>
          {isExpanded && (
            <div className="mt-1 ml-4 space-y-1">
              {entries.map(([k, v]) => (
                <div key={k} className="flex items-start">
                  <span className="text-purple-600 font-medium mr-2 text-xs">
                    {k}:
                  </span>
                  <div className="flex-1">
                    {renderDataValue(v, `${key}.${k}`, depth + 1, logId)}
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      copyToClipboard(v, `${logId}-${k}`);
                    }}
                    className="ml-2 text-gray-400 hover:text-gray-600"
                    title="Copy value"
                  >
                    <ClipboardDocumentIcon className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return <span className="text-gray-900 text-xs">{String(value)}</span>;
  }, [expandedDataKeys, toggleDataKey, copyToClipboard]);

  // Use the imported formatDuration utility
  const formatDuration = formatDurationUtil;

  // Get node icon
  const getNodeIcon = (nodeType) => {
    switch (nodeType) {
      case 'trigger': return CpuChipIcon;
      case 'action': return BoltIcon;
      case 'condition': return CodeBracketIcon;
      case 'loop': return ArrowPathIcon;
      case 'transform': return CodeBracketIcon;
      case 'response': return ArrowUpTrayIcon;
      default: return InformationCircleIcon;
    }
  };

  // Get log level icon
  const getLogIcon = (level, message) => {
    if (level === 'error') return XCircleIcon;
    if (level === 'warning') return ExclamationTriangleIcon;
    if (message?.includes('[DEBUG PRINT]')) return CodeBracketIcon;
    if (level === 'info') return CheckCircleIcon;
    return InformationCircleIcon;
  };

  // Get log level color
  const getLogColor = (level, message) => {
    if (level === 'error') return 'text-red-600 bg-red-50';
    if (level === 'warning') return 'text-yellow-600 bg-yellow-50';
    if (message?.includes('[DEBUG PRINT]')) return 'text-purple-600 bg-purple-50';
    if (level === 'info') return 'text-blue-600 bg-blue-50';
    return 'text-gray-600 bg-gray-50';
  };

  // Render log entry
  const renderLogEntry = (log, compact = false) => {
    const LogIcon = getLogIcon(log.level, log.message);
    const isRawDataShown = showRawData.has(log.log_id);
    const logData = loadedLogData[log.log_id] || log.data;
    const isLoading = loadingLogData.has(log.log_id);
    const hasData = logData && Object.keys(logData).length > 0;
    
    return (
      <div key={log.log_id} className={`${compact ? 'px-3 py-2' : 'px-4 py-3'} ${
        log.level === 'error' ? 'bg-red-50' :
        log.level === 'warning' ? 'bg-yellow-50' :
        ''
      }`}>
        <div className="flex items-start gap-3">
          <LogIcon className={`${compact ? 'w-4 h-4' : 'w-5 h-5'} mt-0.5 flex-shrink-0 ${
            getLogColor(log.level, log.message).split(' ')[0]
          }`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2 mb-1">
              <p className={`${compact ? 'text-xs' : 'text-sm'} font-medium ${
                log.level === 'error' ? 'text-red-900' :
                log.level === 'warning' ? 'text-yellow-900' :
                'text-gray-900'
              }`}>
                {log.message}
              </p>
              <span className="text-xs text-gray-500 flex-shrink-0" title={formatTimestamp(log.timestamp)}>
                {formatElapsedTime(log.timestamp)}
              </span>
            </div>
          
            {/* Log Data - with lazy loading */}
            {(hasData || (!loadedLogData[log.log_id] && !log.data)) && (
              <div className="mt-2">
                <button
                  onClick={async (e) => {
                    e.stopPropagation();
                    
                    // If data not loaded yet, fetch it first
                    if (!loadedLogData[log.log_id] && !log.data) {
                      await fetchLogData(log);
                    }
                    
                    setShowRawData(prev => {
                      const newSet = new Set(prev);
                      if (newSet.has(log.log_id)) {
                        newSet.delete(log.log_id);
                      } else {
                        newSet.add(log.log_id);
                      }
                      return newSet;
                    });
                  }}
                  className="text-xs text-blue-600 hover:text-blue-800 mb-1"
                  disabled={isLoading}
                >
                  {isLoading ? 'Loading...' : (isRawDataShown ? 'Hide' : 'Show')} Data
                </button>
                
                {isRawDataShown && logData && (
                  <div className="relative">
                    <div className={`bg-gray-50 rounded ${compact ? 'p-2' : 'p-3'} overflow-x-auto`}>
                      {renderDataValue(logData, 'root', 0, log.log_id)}
                    </div>
                    <button
                      onClick={() => copyToClipboard(logData, log.log_id)}
                      className={`absolute ${compact ? 'top-1 right-1' : 'top-2 right-2'} p-1 text-gray-500 hover:text-gray-700`}
                    >
                      {copiedId === log.log_id ? (
                        <CheckIcon className={`${compact ? 'w-3 h-3' : 'w-4 h-4'} text-green-500`} />
                      ) : (
                        <ClipboardDocumentIcon className={`${compact ? 'w-3 h-3' : 'w-4 h-4'}`} />
                      )}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className={`relative ${isFullscreen ? 'fixed inset-0 z-50 bg-white overflow-hidden' : ''}`}>
      {/* Header */}
      <div className="sticky top-0 bg-white border-b px-4 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <h3 className="text-lg font-medium text-gray-900">Execution Log</h3>
          {totalLogs && (
            <span className="text-sm text-gray-500">
              ({logs.length} of {totalLogs} logs loaded)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={expandAll}
            className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md"
          >
            Expand All
          </button>
          <button
            onClick={collapseAll}
            className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md"
          >
            Collapse All
          </button>
          <button
            onClick={() => loadAllLogData(true)}
            className="px-3 py-1 text-sm text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded-md"
            title="Load and show all log data"
          >
            Show All Data
          </button>
          <button
            onClick={copyAllLogs}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-md"
            title="Copy all logs"
          >
            {copiedId === 'all-logs' ? (
              <CheckIcon className="w-5 h-5 text-green-500" />
            ) : (
              <ClipboardDocumentIcon className="w-5 h-5" />
            )}
          </button>
          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded-md"
            title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          >
            {isFullscreen ? (
              <ArrowsPointingInIcon className="w-5 h-5" />
            ) : (
              <ArrowsPointingOutIcon className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {/* HITL Wait Time Summary */}
      {hitlSummary && (
        <div className="mx-4 mt-3 px-4 py-2.5 bg-orange-50 border border-orange-200 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-orange-800">
            <PauseCircleIcon className="w-4 h-4 text-orange-500" />
            <span className="font-medium">
              Review Wait Time: {formatDurationMs(hitlSummary.totalWaitMs)}
            </span>
            {hitlSummary.hasWaiting && <span className="text-orange-500 animate-pulse text-xs">(still waiting)</span>}
          </div>
          <span className="text-xs text-orange-600">
            {hitlSummary.hitlCount} review node{hitlSummary.hitlCount > 1 ? 's' : ''}
          </span>
        </div>
      )}

      {/* Log Content */}
      <div className={`${isFullscreen ? 'h-[calc(100vh-60px)] overflow-y-auto' : ''} p-4`}>
        {/* Warning if logs might be truncated - removed since we now have pagination */}
        
        {groupedLogs.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p>No execution logs available</p>
          </div>
        ) : (
          <div className="space-y-4">
            {groupedLogs.map(group => {
              const NodeIcon = getNodeIcon(group.nodeType);
              const isExpanded = expandedNodes.has(group.nodeId);
              
              return (
                <div
                  key={group.nodeId}
                  className={`border rounded-lg ${
                    group.hasError ? 'border-red-400 shadow-red-100 shadow-sm' :
                    group.hasWarning ? 'border-yellow-300' :
                    group.hasSuccess ? 'border-green-300' :
                    (group.hasPaused && !group.hasSuccess) ? 'border-orange-300' :
                    'border-gray-200'
                  }`}
                >
                  {/* Node Header */}
                  <div
                    className={`px-4 py-3 cursor-pointer hover:bg-opacity-75 ${
                      group.hasError ? 'bg-red-50 hover:bg-red-100' :
                      group.hasSuccess && !group.hasError ? 'bg-green-50' :
                      (group.hasPaused && !group.hasSuccess) ? 'bg-orange-50 hover:bg-orange-100' :
                      'bg-white hover:bg-gray-50'
                    }`}
                    onClick={() => toggleNode(group.nodeId)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <button className="p-1">
                          {isExpanded ? (
                            <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                          ) : (
                            <ChevronRightIcon className="w-4 h-4 text-gray-500" />
                          )}
                        </button>
                        <NodeIcon className={`w-5 h-5 ${
                          group.hasError ? 'text-red-600' :
                          group.hasWarning ? 'text-yellow-600' :
                          group.hasSuccess ? 'text-green-600' :
                          (group.hasPaused && !group.hasSuccess) ? 'text-orange-500' :
                          'text-gray-600'
                        }`} />
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-gray-900">
                            <span className="break-words">{group.nodeLabel || group.nodeId}</span>
                            {/* Always show node ID in brackets */}
                            <span className="text-xs text-gray-500 ml-1">
                              [{group.nodeId}]
                            </span>
                          </h4>
                          <p className="text-xs text-gray-500">
                            <span className="capitalize">{group.nodeType || 'flow'}</span>
                            {' • '}
                            {group.logs.length} log{group.logs.length !== 1 ? 's' : ''}
                            {group.isLoop && Object.keys(group.iterations).length > 0 &&
                              ` • ${Object.keys(group.iterations).length} iteration${Object.keys(group.iterations).length !== 1 ? 's' : ''} shown`}
                            {group.isLoop && Object.keys(group.iterations).length >= 100 &&
                              ' (may be truncated)'}
                          </p>
                          {/* HITL detail row */}
                          {group.hasPaused && (() => {
                            const parseTS = (ts) => {
                              if (!ts) return null;
                              const s = String(ts);
                              return new Date(!s.endsWith('Z') && !s.includes('+') ? s + 'Z' : s);
                            };
                            const fmtTime = (d) => d ? d.toLocaleTimeString() : null;
                            const paused = parseTS(group.pausedAt);
                            const resumed = group.hasSuccess
                              ? parseTS(group.hitlCompletedAt || group.endTime)
                              : null;
                            return (
                              <div className="flex items-center gap-3 mt-0.5 text-[11px]">
                                {group.hitlAssignedTo && (
                                  <span className="text-orange-600">
                                    Assigned: <strong>{group.hitlAssignedTo}</strong>
                                  </span>
                                )}
                                {paused && (
                                  <span className="text-orange-500">
                                    Paused: {fmtTime(paused)}
                                  </span>
                                )}
                                {resumed && (
                                  <span className="text-green-600">
                                    Resumed: {fmtTime(resumed)}
                                  </span>
                                )}
                                {!group.hasSuccess && paused && (
                                  <span className="text-orange-500 animate-pulse">
                                    Waiting...
                                  </span>
                                )}
                              </div>
                            );
                          })()}
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        {group.hasSuccess && !group.hasError && (
                          <CheckCircleIcon className="w-5 h-5 text-green-600" />
                        )}
                        {group.hasPaused && !group.hasSuccess && !group.hasError && (
                          <PauseCircleIcon className="w-5 h-5 text-orange-500" />
                        )}
                        {group.hasError && (
                          <XCircleIcon className="w-5 h-5 text-red-600" />
                        )}
                        {/* HITL wait time */}
                        {group.hasPaused && group._hitlWaitMs != null && (
                          <div className="flex items-center gap-1 text-xs text-orange-600" title="Review wait time">
                            <PauseCircleIcon className="w-3.5 h-3.5" />
                            {formatDurationMs(group._hitlWaitMs)}
                            {!group.hasSuccess && <span className="animate-pulse">...</span>}
                          </div>
                        )}
                        {group.duration !== null && group.duration !== undefined && (
                          <div className="flex items-center gap-1 text-sm text-gray-600">
                            <ClockIcon className="w-4 h-4" />
                            {formatDurationMs(group.duration)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Node Content */}
                  {isExpanded && (
                    <div className="border-t">
                      {/* Loop node with iterations */}
                      {group.isLoop && Object.keys(group.iterations).length > 0 ? (
                        <div>
                          {/* Loop node's own logs */}
                          {group.logs.length > 0 && (
                            <div className="border-b bg-gray-50">
                              <div className="px-4 py-2 text-sm font-medium text-gray-700">
                                Loop Configuration
                              </div>
                              <div className="divide-y divide-gray-200">
                                {group.logs.map(log => renderLogEntry(log))}
                              </div>
                            </div>
                          )}
                          
                          {/* Loop iterations */}
                          <div className="p-4 space-y-3">
                            {Object.entries(group.iterations)
                              .sort(([a], [b]) => parseInt(a) - parseInt(b))
                              .map(([iterNum, iteration]) => {
                                const iterationKey = `${group.nodeId}-${iterNum}`;
                                const isIterationExpanded = expandedIterations.has(iterationKey);
                                
                                return (
                                  <div key={iterNum} className="border border-gray-300 rounded-lg bg-gray-50">
                                    {/* Iteration Header */}
                                    <div
                                      className="px-4 py-3 cursor-pointer hover:bg-gray-100"
                                      onClick={() => toggleIteration(iterationKey)}
                                    >
                                      <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-3">
                                          <button className="p-1">
                                            {isIterationExpanded ? (
                                              <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                                            ) : (
                                              <ChevronRightIcon className="w-4 h-4 text-gray-500" />
                                            )}
                                          </button>
                                          <ArrowPathIcon className="w-5 h-5 text-blue-600" />
                                          <div>
                                            <h5 className="font-medium text-gray-900">
                                              Iteration {iteration.iterationNumber}
                                            </h5>
                                            <p className="text-xs text-gray-500">
                                              {iteration.logs.length} logs • {Object.keys(iteration.nodes).length} nodes
                                            </p>
                                          </div>
                                        </div>
                                        <div className="flex items-center gap-4">
                                          {iteration.duration !== null && iteration.duration !== undefined && (
                                            <div className="flex items-center gap-1 text-sm text-gray-600">
                                              <ClockIcon className="w-4 h-4" />
                                              {formatDurationMs(iteration.duration)}
                                            </div>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                    
                                    {/* Iteration Content */}
                                    {isIterationExpanded && (
                                      <div className="border-t border-gray-300">
                                        {/* Render nodes within iteration */}
                                        {Object.values(iteration.nodes).map(iterNode => {
                                          const IterNodeIcon = getNodeIcon(iterNode.nodeType);
                                          return (
                                            <div key={iterNode.nodeId} className={`border-b last:border-b-0 ${iterNode.hasError ? 'bg-red-50' : ''}`}>
                                              <div className={`px-4 py-2 ${iterNode.hasError ? 'bg-red-100' : 'bg-gray-50'}`}>
                                                <div className="flex items-center gap-2">
                                                  <IterNodeIcon className={`w-4 h-4 ${iterNode.hasError ? 'text-red-600' : 'text-gray-600'}`} />
                                                  <span className="font-medium text-sm text-gray-900">
                                                    {iterNode.nodeLabel || iterNode.nodeId}
                                                  </span>
                                                  <span className="text-xs text-gray-500">
                                                    ({iterNode.nodeType || 'node'})
                                                  </span>
                                                  {iterNode.hasError && (
                                                    <XCircleIcon className="w-4 h-4 text-red-600 ml-auto" title="Error in this node" />
                                                  )}
                                                </div>
                                              </div>
                                              <div className="divide-y divide-gray-200 bg-white">
                                                {iterNode.logs.map(log => renderLogEntry(log, true))}
                                              </div>
                                            </div>
                                          );
                                        })}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                          </div>
                        </div>
                      ) : (
                        // Regular node logs
                        <div className="divide-y divide-gray-200">
                          {group.logs.map(log => renderLogEntry(log))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
        
        {/* Load More Button */}
        {console.log('Load More Button check:', { 
          hasMore, 
          hasMoreType: typeof hasMore,
          onLoadMore: !!onLoadMore, 
          totalLogs, 
          logsLength: logs.length,
          showButton: hasMore && onLoadMore
        })}
        {hasMore && onLoadMore && (
          <div className="mt-6 text-center pb-4" style={{ backgroundColor: '#f3f4f6', padding: '20px', border: '2px dashed #9ca3af' }}>
            <button
              onClick={onLoadMore}
              disabled={isLoadingMore}
              className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoadingMore ? (
                <>
                  <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-gray-700" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  Loading more...
                </>
              ) : (
                <>
                  Load More Logs
                  {totalLogs && (
                    <span className="ml-2 text-gray-500">
                      ({logs.length} of {totalLogs})
                    </span>
                  )}
                </>
              )}
            </button>
          </div>
        )}
      </div>

      {/* Copy Dialog - asks user whether to load all data */}
      {showCopyDialog && (
        <div className="fixed inset-0 z-[100] overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setShowCopyDialog(false)} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
              <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <div className="sm:flex sm:items-start">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                    <InformationCircleIcon className="h-6 w-6 text-blue-600" />
                  </div>
                  <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left">
                    <h3 className="text-base font-semibold leading-6 text-gray-900">
                      Load All Log Data?
                    </h3>
                    <div className="mt-2">
                      <p className="text-sm text-gray-500">
                        Not all log data is currently loaded. Would you like to load all data before copying to clipboard, or only export the data that's currently loaded?
                      </p>
                    </div>
                  </div>
                </div>
              </div>
              <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                <button
                  type="button"
                  className="inline-flex w-full justify-center rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 sm:ml-3 sm:w-auto"
                  onClick={() => handleCopyDialogResponse(true)}
                >
                  Load All Data
                </button>
                <button
                  type="button"
                  className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                  onClick={() => handleCopyDialogResponse(false)}
                >
                  Copy Only Loaded Data
                </button>
                <button
                  type="button"
                  className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:ml-3 sm:mt-0 sm:w-auto"
                  onClick={() => setShowCopyDialog(false)}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Loading indicator when fetching all data */}
      {isLoadingAllData && (
        <div className="fixed inset-0 z-[100] overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:w-full sm:max-w-sm">
              <div className="mx-auto flex items-center justify-center">
                <svg className="animate-spin h-10 w-10 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              </div>
              <div className="mt-3 text-center">
                <p className="text-sm text-gray-500">Loading all log data...</p>
                <p className="mt-1 text-xs text-gray-400">This may take a moment for large execution logs</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default HierarchicalExecutionLog;