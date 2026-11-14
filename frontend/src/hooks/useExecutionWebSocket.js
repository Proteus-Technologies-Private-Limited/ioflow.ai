import { useEffect, useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import websocketService from '../services/websocketService';

/**
 * React hook for WebSocket integration with execution updates
 * @param {string} executionId - Specific execution ID to subscribe to (optional)
 * @param {object} options - Hook options
 * @returns {object} WebSocket state and methods
 */
export function useExecutionWebSocket(executionId = null, options = {}) {
  // Remove console.log that might be causing issues
  
  const { 
    onStatusUpdate,
    onLogUpdate,
    onProgressUpdate,
    enabled = true 
  } = options;
  
  const queryClient = useQueryClient();
  const hasConnected = useRef(false);
  const [isConnected, setIsConnected] = useState(false);

  // Handle execution status updates
  const handleExecutionUpdate = useCallback((message) => {
    const { execution_id, data } = message;
    
    console.log('useExecutionWebSocket: Handling execution update', { execution_id, data });
    
    // Handle immediate trigger and execution events with priority
    if (data.type === 'trigger_received' || data.type === 'execution_start') {
      console.log(`useExecutionWebSocket: Processing immediate ${data.type} event`);
      // These are immediate status events that should trigger UI updates immediately
      // They don't necessarily update execution records but provide real-time feedback
    }
    
    // Update all execution queries regardless of filters
    // This will match all queries that start with ['executions']
    queryClient.setQueriesData(
      { queryKey: ['executions'], exact: false },
      (oldData) => {
        if (!oldData) return oldData;

        // Handle both array and paginated data formats
        const isArray = Array.isArray(oldData);
        const executions = isArray ? oldData : (oldData.executions || oldData.items || oldData.data || []);

        // Ensure executions is an array before using array methods
        if (!Array.isArray(executions)) {
          console.warn('Executions data is not in expected format:', oldData);
          return oldData;
        }

        // Check if this execution already exists in the cache
        const existingExecution = executions.find(exec => exec && exec.execution_id === execution_id);

        if (existingExecution) {
          // Update existing execution
          const updatedExecutions = executions.map(execution => {
            if (execution && execution.execution_id === execution_id) {
              return {
                ...execution,
                status: data.status || execution.status,
                completed_at: data.completed_at || execution.completed_at,
                error_message: data.error_message || execution.error_message,
                updated_at: data.updated_at || new Date().toISOString(),
                // Add progress information for real-time feedback
                current_status: data.message || execution.current_status
              };
            }
            return execution;
          });

          // If execution is now completed or failed, unsubscribe from it
          // IMPORTANT: Only unsubscribe on execution-level events, NOT node-level events
          // node_complete also has status 'completed' but we must keep listening for subsequent nodes
          if ((data.type === 'execution_complete' || data.type === 'execution_error') &&
              (data.status === 'completed' || data.status === 'failed')) {
            setTimeout(() => {
              websocketService.unsubscribe(execution_id);
            }, 1000); // Small delay to ensure final updates are received
          }

          // Return data in the same format as received
          return isArray ? updatedExecutions : { ...oldData, executions: updatedExecutions, items: updatedExecutions, data: updatedExecutions };
        } else if ((data.status === 'running' || data.status === 'initializing' || data.type === 'trigger_received') && data.flow_name) {
          // This is a new execution - add it to the beginning of the list
          const newExecution = {
            execution_id,
            flow_id: data.flow_id,
            flow_name: data.flow_name,
            status: data.status || 'running',
            trigger_type: data.trigger_type || 'schedule',
            started_at: data.started_at,
            completed_at: data.completed_at,
            error_message: data.error_message,
            created_at: data.started_at || new Date().toISOString(),
            updated_at: new Date().toISOString(),
            current_status: data.message
          };

          const updatedExecutions = [newExecution, ...executions];

          // Return data in the same format as received
          return isArray ? updatedExecutions : { ...oldData, executions: updatedExecutions, items: updatedExecutions, data: updatedExecutions };
        }

        return oldData;
      }
    );

    // Update single execution details query if it exists
    queryClient.setQueryData(['execution-details', execution_id], (oldData) => {
      if (!oldData) return oldData;
      
      return {
        ...oldData,
        status: data.status || oldData.status,
        completed_at: data.completed_at || oldData.completed_at,
        error_message: data.error_message || oldData.error_message,
        updated_at: data.updated_at || new Date().toISOString()
      };
    });

    // Call custom handler if provided
    if (onStatusUpdateRef.current) {
      onStatusUpdateRef.current(execution_id, data);
    }
  }, [queryClient]);

  // Handle execution log updates
  const handleLogUpdate = useCallback((message) => {
    const { execution_id, data } = message;
    
    // Update execution logs in cache
    queryClient.setQueryData(['execution-logs', execution_id], (oldLogs) => {
      if (!oldLogs) return [data];
      
      // Add new log entry to the end
      return [...oldLogs, {
        ...data,
        log_id: Date.now(), // Temporary ID, will be replaced by server
        execution_id,
        created_at: data.timestamp || new Date().toISOString()
      }];
    });

    // Call custom handler if provided
    if (onLogUpdateRef.current) {
      onLogUpdateRef.current(execution_id, data);
    }
  }, [queryClient]);

  // Handle execution progress updates
  const handleProgressUpdate = useCallback((message) => {
    const { execution_id, data } = message;

    // Update all execution queries regardless of filters
    queryClient.setQueriesData(
      { queryKey: ['executions'], exact: false },
      (oldData) => {
        if (!oldData) return oldData;

        // Handle both array and paginated data formats
        const isArray = Array.isArray(oldData);
        const executions = isArray ? oldData : (oldData.executions || oldData.items || oldData.data || []);

        // Ensure executions is an array before using array methods
        if (!Array.isArray(executions)) {
          console.warn('Executions data is not in expected format for progress update:', oldData);
          return oldData;
        }

        const updatedExecutions = executions.map(execution => {
          if (execution && execution.execution_id === execution_id) {
            return {
              ...execution,
              progress: data.progress || execution.progress,
              current_step: data.current_step || execution.current_step,
              total_steps: data.total_steps || execution.total_steps
            };
          }
          return execution;
        });

        // Return data in the same format as received
        return isArray ? updatedExecutions : { ...oldData, executions: updatedExecutions, items: updatedExecutions, data: updatedExecutions };
      }
    );

    // Call custom handler if provided
    if (onProgressUpdateRef.current) {
      onProgressUpdateRef.current(execution_id, data);
    }
  }, [queryClient]);

  // Store handlers in refs to maintain stable references
  const onStatusUpdateRef = useRef(onStatusUpdate);
  const onLogUpdateRef = useRef(onLogUpdate);
  const onProgressUpdateRef = useRef(onProgressUpdate);
  
  // Update refs when callbacks change
  useEffect(() => {
    onStatusUpdateRef.current = onStatusUpdate;
    onLogUpdateRef.current = onLogUpdate;
    onProgressUpdateRef.current = onProgressUpdate;
  }, [onStatusUpdate, onLogUpdate, onProgressUpdate]);

  // Connect and subscribe
  useEffect(() => {
    if (!enabled) return;

    const connectAndSubscribe = async () => {
      try {
        const token = localStorage.getItem('access_token');
        if (!token) {
          console.warn('No authentication token found');
          return;
        }

        // Connect if not already connected
        console.log('useExecutionWebSocket: Checking connection status');
        console.log('isConnected:', websocketService.isConnected());
        console.log('hasConnected:', hasConnected.current);
        
        if (!websocketService.isConnected() && !hasConnected.current) {
          console.log('useExecutionWebSocket: Attempting to connect with token:', token.substring(0, 20) + '...');
          try {
            await websocketService.connect(token);
            hasConnected.current = true;
            setIsConnected(true);
            
            // Subscribe to tenant-wide updates for new executions
            console.log('useExecutionWebSocket: Subscribing to tenant');
            websocketService.subscribeTenant();
          } catch (error) {
            console.error('useExecutionWebSocket: Failed to connect WebSocket:', error);
            hasConnected.current = false;
          }
        } else {
          console.log('useExecutionWebSocket: Already connected or connecting');
          setIsConnected(websocketService.isConnected());
        }

        // Subscribe to specific execution if provided
        if (executionId) {
          websocketService.subscribe(executionId);
        }

        // Set up event listeners
        websocketService.on('execution_update', handleExecutionUpdate);
        websocketService.on('execution_log', handleLogUpdate);
        websocketService.on('execution_progress', handleProgressUpdate);
        
        // Listen for connection status changes
        websocketService.on('connection', () => setIsConnected(true));
        websocketService.on('disconnect', () => setIsConnected(false));

      } catch (error) {
        console.error('Failed to connect to WebSocket:', error);
        setIsConnected(false);
      }
    };

    connectAndSubscribe();

    // Cleanup
    return () => {
      if (executionId) {
        websocketService.unsubscribe(executionId);
      }
      
      websocketService.off('execution_update', handleExecutionUpdate);
      websocketService.off('execution_log', handleLogUpdate);
      websocketService.off('execution_progress', handleProgressUpdate);
      websocketService.off('connection', () => setIsConnected(true));
      websocketService.off('disconnect', () => setIsConnected(false));
    };
  }, [executionId, enabled]); // Remove handler dependencies to prevent cycles

  // Check connection status periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setIsConnected(websocketService.isConnected());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Public methods
  const subscribeToExecution = useCallback((execId) => {
    websocketService.subscribe(execId);
  }, []);

  const unsubscribeFromExecution = useCallback((execId) => {
    websocketService.unsubscribe(execId);
  }, []);

  return {
    subscribeToExecution,
    unsubscribeFromExecution,
    isConnected
  };
}

/**
 * Hook for managing multiple execution subscriptions
 */
export function useExecutionsWebSocket(options = {}) {
  const hook = useExecutionWebSocket(null, options);
  const subscribedExecutions = useRef(new Set());
  const previousExecutionIds = useRef(new Set());

  const subscribeToExecutions = useCallback((executionIds) => {
    // Create sets for comparison
    const newIds = new Set(executionIds);
    const currentIds = subscribedExecutions.current;
    
    // Find IDs to subscribe to (in new but not in current)
    const toSubscribe = [...newIds].filter(id => !currentIds.has(id));
    
    // Find IDs to unsubscribe from (in current but not in new)
    const toUnsubscribe = [...currentIds].filter(id => !newIds.has(id));
    
    // Unsubscribe from removed IDs
    toUnsubscribe.forEach(id => {
      hook.unsubscribeFromExecution(id);
      subscribedExecutions.current.delete(id);
    });
    
    // Subscribe to new IDs
    toSubscribe.forEach(id => {
      hook.subscribeToExecution(id);
      subscribedExecutions.current.add(id);
    });
  }, [hook]);

  const unsubscribeFromExecutions = useCallback((executionIds) => {
    executionIds.forEach(id => {
      if (subscribedExecutions.current.has(id)) {
        hook.unsubscribeFromExecution(id);
        subscribedExecutions.current.delete(id);
      }
    });
  }, [hook]);

  const unsubscribeAll = useCallback(() => {
    subscribedExecutions.current.forEach(id => {
      hook.unsubscribeFromExecution(id);
    });
    subscribedExecutions.current.clear();
  }, [hook]);

  // Only cleanup when component unmounts
  useEffect(() => {
    return () => {
      // Clear all subscriptions on unmount
      subscribedExecutions.current.forEach(id => {
        hook.unsubscribeFromExecution(id);
      });
      subscribedExecutions.current.clear();
    };
  }, []); // Empty dependency array - only run on unmount

  return {
    ...hook,
    subscribeToExecutions,
    unsubscribeFromExecutions,
    unsubscribeAll,
    subscribedCount: subscribedExecutions.current.size
  };
}