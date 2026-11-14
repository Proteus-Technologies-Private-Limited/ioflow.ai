import { useState, useEffect, useCallback, useRef } from 'react';
import hitlService from '../services/hitlService';

/**
 * Hook for HITL task notifications and badge count.
 * Polls task stats periodically and listens for WebSocket HITL events.
 */
const useHITLNotifications = (wsConnection = null) => {
  const [pendingCount, setPendingCount] = useState(0);
  const [urgentCount, setUrgentCount] = useState(0);
  const [latestTasks, setLatestTasks] = useState([]);
  const intervalRef = useRef(null);

  const fetchStats = useCallback(async () => {
    try {
      const response = await hitlService.getTaskStats();
      const stats = response.data;
      setPendingCount(stats.pending || 0);
      setUrgentCount(stats.urgent || 0);
    } catch (error) {
      // Silently fail - stats are non-critical
    }
  }, []);

  const fetchLatestTasks = useCallback(async () => {
    try {
      const response = await hitlService.getTasks({ status: 'pending', limit: 5 });
      setLatestTasks(response.data?.tasks || []);
    } catch (error) {
      // Silently fail
    }
  }, []);

  const refresh = useCallback(() => {
    fetchStats();
    fetchLatestTasks();
  }, [fetchStats, fetchLatestTasks]);

  // Initial fetch and polling
  useEffect(() => {
    refresh();
    intervalRef.current = setInterval(refresh, 30000); // Poll every 30 seconds
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [refresh]);

  // Handle WebSocket messages for HITL events
  useEffect(() => {
    if (!wsConnection) return;

    const handleMessage = (event) => {
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        if (data.type === 'hitl_task_created' || data.type === 'hitl_task_completed') {
          // Refresh stats and tasks when HITL events are received
          refresh();
        }
      } catch (e) {
        // Ignore non-JSON messages
      }
    };

    wsConnection.addEventListener('message', handleMessage);
    return () => wsConnection.removeEventListener('message', handleMessage);
  }, [wsConnection, refresh]);

  return {
    pendingCount,
    urgentCount,
    latestTasks,
    refresh,
  };
};

export default useHITLNotifications;
