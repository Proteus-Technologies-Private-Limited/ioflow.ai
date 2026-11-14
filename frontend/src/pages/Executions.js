import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useFilters } from '../contexts/FilterContext';
import { useSidebar } from '../contexts/SidebarContext';
import axios from 'axios';
import '../styles/FilterIndicators.css';
import {
  MagnifyingGlassIcon,
  CheckCircleIcon,
  XCircleIcon,
  ClockIcon,
  PauseIcon,
  ArrowPathIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  FunnelIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  WifiIcon,
  ExclamationTriangleIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline';
import { showErrorToast, showSuccessToast } from '../utils/customToast';
import HierarchicalExecutionLog from '../components/execution/HierarchicalExecutionLog';
import { formatDateTime, formatDuration as formatDurationUtil, formatTime, getTimezoneDisplay } from '../utils/dateFormatter';
import { useExecutionsWebSocket, useExecutionWebSocket } from '../hooks/useExecutionWebSocket';

const Executions = () => {
  const queryClient = useQueryClient();
  const { getPageFilters, updatePageFilters, clearPageFilters } = useFilters();
  const { sidebarCollapsed } = useSidebar();

  // State for tooltip
  const [tooltipData, setTooltipData] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [isTooltipHovered, setIsTooltipHovered] = useState(false);
  const tooltipShowTimeoutRef = useRef(null);
  const tooltipHideTimeoutRef = useRef(null);
  const pendingTooltipData = useRef(null);

  // Helper function to show custom tooltip with delay
  const handleMouseEnter = (e, label, value) => {
    // Clear any pending hide timeout
    if (tooltipHideTimeoutRef.current) {
      clearTimeout(tooltipHideTimeoutRef.current);
      tooltipHideTimeoutRef.current = null;
    }

    // If tooltip is already showing for the same data, don't restart the timer
    if (tooltipData && tooltipData.label === label && tooltipData.value === value) {
      return;
    }

    // Clear any pending show timeout
    if (tooltipShowTimeoutRef.current) {
      clearTimeout(tooltipShowTimeoutRef.current);
      tooltipShowTimeoutRef.current = null;
    }

    const rect = e.currentTarget.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const tooltipWidth = 300; // Approximate tooltip width
    const leftNavWidth = 256; // Width of left navigation panel

    // Calculate X position (center above element, but adjust if near edges)
    let x = rect.left + rect.width / 2;

    // Ensure tooltip doesn't go under left navigation
    if (x - tooltipWidth / 2 < leftNavWidth + 10) {
      x = leftNavWidth + tooltipWidth / 2 + 10; // Adjust for left nav
    } else if (x + tooltipWidth / 2 > viewportWidth - 10) {
      x = viewportWidth - tooltipWidth / 2 - 10; // Too close to right edge
    }

    // Calculate Y position (above element if space, otherwise below)
    const spaceAbove = rect.top;
    const tooltipHeight = 100; // Approximate tooltip height
    let y = spaceAbove > tooltipHeight + 10
      ? rect.top - tooltipHeight - 5  // Show above
      : rect.bottom + 5;  // Show below

    // Store pending tooltip data
    pendingTooltipData.current = { label, value, x, y };

    // Set timeout to show tooltip after delay (500ms)
    tooltipShowTimeoutRef.current = setTimeout(() => {
      if (pendingTooltipData.current) {
        setTooltipPosition({ x: pendingTooltipData.current.x, y: pendingTooltipData.current.y });
        setTooltipData({ label: pendingTooltipData.current.label, value: pendingTooltipData.current.value });
        pendingTooltipData.current = null;
      }
    }, 500); // 500ms delay before showing tooltip
  };

  // Helper function to hide tooltip with small delay
  const handleMouseLeave = () => {
    // Clear any pending show timeout
    if (tooltipShowTimeoutRef.current) {
      clearTimeout(tooltipShowTimeoutRef.current);
      tooltipShowTimeoutRef.current = null;
      pendingTooltipData.current = null;
    }

    // Add a small delay before hiding to allow cursor to move to tooltip
    tooltipHideTimeoutRef.current = setTimeout(() => {
      if (!isTooltipHovered) {
        setTooltipData(null);
      }
    }, 100); // 100ms delay before hiding
  };

  // Helper function to copy and close tooltip
  const handleCopyFromTooltip = (value) => {
    copyToClipboard(value, 'tooltip-data');
    setTooltipData(null);
  };
  
  // Cleanup timeouts on unmount
  useEffect(() => {
    return () => {
      if (tooltipShowTimeoutRef.current) {
        clearTimeout(tooltipShowTimeoutRef.current);
      }
      if (tooltipHideTimeoutRef.current) {
        clearTimeout(tooltipHideTimeoutRef.current);
      }
    };
  }, []);

  // Get saved filters or use defaults
  const savedFilters = getPageFilters('executions', {
    searchTerm: '',
    statusFilter: 'all',
    flowFilter: 'all'
  });
  
  const [searchTerm, setSearchTerm] = useState(savedFilters.searchTerm);
  const [statusFilter, setStatusFilter] = useState(savedFilters.statusFilter);
  const [flowFilter, setFlowFilter] = useState(savedFilters.flowFilter);
  const [selectedExecution, setSelectedExecution] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const [sortBy, setSortBy] = useState('started_at');
  const [sortOrder, setSortOrder] = useState('desc');
  
  // Save filters whenever they change
  useEffect(() => {
    updatePageFilters('executions', {
      searchTerm,
      statusFilter,
      flowFilter
    });
  }, [searchTerm, statusFilter, flowFilter, updatePageFilters]);
  
  // Pagination for main executions list
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 50;

  // Helper function to copy JSON to clipboard
  const copyToClipboard = async (data, id) => {
    try {
      const jsonStr = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
      await navigator.clipboard.writeText(jsonStr);
      setCopiedId(id);
      showSuccessToast('Copied to clipboard!');
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      showErrorToast('Failed to copy to clipboard');
    }
  };

  // Set up WebSocket for real-time updates
  const { 
    subscribeToExecutions, 
    unsubscribeAll, 
    isConnected 
  } = useExecutionsWebSocket({
    onStatusUpdate: (executionId, data) => {
      console.log(`Execution ${executionId} status updated:`, data);
    },
    onLogUpdate: (executionId, data) => {
      console.log(`Execution ${executionId} new log:`, data);
    }
  });

  // Calculate offset from current page
  const offset = (currentPage - 1) * itemsPerPage;

  // Fetch executions with pagination - with better caching
  const { data: executionsResponse, isLoading, error, refetch } = useQuery({
    queryKey: ['executions', statusFilter, flowFilter, currentPage],
    queryFn: async () => {
      let url = '/api/v1/executions/';
      const params = [];
      params.push(`limit=${itemsPerPage}`);
      params.push(`offset=${offset}`);
      if (statusFilter !== 'all') params.push(`status=${statusFilter}`);
      if (flowFilter !== 'all') params.push(`flow_id=${flowFilter}`);
      url += '?' + params.join('&');

      const response = await axios.get(url);
      // Extract total count from response headers
      const totalCount = parseInt(response.headers['x-total-count'] || '0', 10);

      // Return both data and metadata
      return {
        executions: response.data,
        totalCount: totalCount
      };
    },
    staleTime: 30000, // Consider data fresh for 30 seconds
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
  });

  const executions = executionsResponse?.executions || [];
  const totalExecutions = executionsResponse?.totalCount || 0;
  const totalPages = Math.ceil(totalExecutions / itemsPerPage) || 1;

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter, flowFilter]);

  // Subscribe to WebSocket updates for executions
  useEffect(() => {
    // Only subscribe if WebSocket is connected and we have executions
    if (isConnected && executions.length > 0) {
      // Get ALL execution IDs to subscribe to for real-time updates
      const executionIds = executions.map(exec => exec.execution_id);
      
      if (executionIds.length > 0) {
        subscribeToExecutions(executionIds);
      }
    } else if (executions.length === 0) {
      // No executions, unsubscribe from all
      unsubscribeAll();
    }
    // Note: cleanup is handled by the hook itself when component unmounts
  }, [executions, isConnected, subscribeToExecutions, unsubscribeAll]); // Re-subscribe when executions or connection state changes

  // Fetch flows for filter dropdown
  const { data: flows = [] } = useQuery({
    queryKey: ['flows-list'],
    queryFn: async () => {
      const response = await axios.get('/api/v1/flows/');
      return response.data;
    },
  });

  // Memoize WebSocket callbacks to prevent re-renders
  const handleStatusUpdate = useCallback((executionId, data) => {
    console.log(`Selected execution ${executionId} status updated:`, data);
  }, []);

  const handleLogUpdate = useCallback((executionId, data) => {
    console.log(`Selected execution ${executionId} new log:`, data);
  }, []);

  // Memoize WebSocket options
  const wsOptions = useMemo(() => ({
    enabled: !!selectedExecution && showDetails,
    onStatusUpdate: handleStatusUpdate,
    onLogUpdate: handleLogUpdate
  }), [selectedExecution, showDetails, handleStatusUpdate, handleLogUpdate]);

  // WebSocket for selected execution details
  useExecutionWebSocket(selectedExecution?.execution_id, wsOptions);

  // Fetch execution details
  const { data: executionDetails } = useQuery({
    queryKey: ['execution-details', selectedExecution?.execution_id],
    queryFn: async () => {
      const response = await axios.get(`/api/v1/executions/${selectedExecution.execution_id}`);
      return response.data;
    },
    enabled: !!selectedExecution,
  });

  // State for pagination - increased limit for better performance
  const [logsOffset, setLogsOffset] = useState(0);
  const [allLogs, setAllLogs] = useState([]);
  const logsLimit = 200; // Increased from 100 for fewer requests

  // Debug selected execution
  useEffect(() => {
    console.log('selectedExecution changed to:', selectedExecution);
    console.log('selectedExecution is truthy:', !!selectedExecution);
  }, [selectedExecution]);

  // Fetch execution logs with pagination - optimized to not fetch data field initially
  const { data: executionLogsData, isLoading: isLoadingLogs, isFetching: isFetchingMoreLogs, error: logsError, refetch: refetchLogs } = useQuery({
    queryKey: ['execution-logs', selectedExecution?.execution_id, logsOffset],
    queryFn: async () => {
      console.log('Fetching logs for execution:', selectedExecution?.execution_id, 'offset:', logsOffset, 'limit:', logsLimit);
      // Include data field to get the actual log content
      const response = await axios.get(
        `/api/v1/executions/${selectedExecution.execution_id}/logs?limit=${logsLimit}&offset=${logsOffset}&include_data=false`
      );
      console.log('Logs API response:', response.data);
      return response.data;
    },
    enabled: !!selectedExecution && showDetails,  // Also check showDetails
    refetchOnWindowFocus: false,
    refetchOnMount: 'always', // Always refetch when component mounts
    staleTime: 0, // Consider data always stale
    gcTime: 0, // Don't cache the data (gcTime replaced cacheTime in newer versions)
  });
  
  // Log any errors
  useEffect(() => {
    if (logsError) {
      console.error('Error fetching logs:', logsError);
    }
  }, [logsError]);

  // Update allLogs when new data arrives
  useEffect(() => {
    console.log('ExecutionLogsData received:', executionLogsData);
    
    // Handle both old array format and new paginated format
    if (executionLogsData) {
      let logsToAdd = [];
      
      // Check if it's the new paginated format
      if (executionLogsData.logs && Array.isArray(executionLogsData.logs)) {
        logsToAdd = executionLogsData.logs;
      } 
      // Handle old array format (backwards compatibility)
      else if (Array.isArray(executionLogsData)) {
        logsToAdd = executionLogsData;
      }
      
      if (logsToAdd.length > 0) {
        if (logsOffset === 0) {
          // Reset logs for new execution
          setAllLogs(logsToAdd);
        } else {
          // Append new logs
          setAllLogs(prev => [...prev, ...logsToAdd]);
        }
      }
    }
  }, [executionLogsData, logsOffset]);

  // Reset pagination when execution changes
  useEffect(() => {
    console.log('[DEBUG] Execution changed, resetting logs state');
    setLogsOffset(0);
    setAllLogs([]);
    // Invalidate the cache for the previous execution logs
    if (selectedExecution) {
      queryClient.invalidateQueries(['execution-logs']);
    }
  }, [selectedExecution?.execution_id, queryClient]);

  const loadMoreLogs = () => {
    setLogsOffset(prev => prev + logsLimit);
  };

  // Filter executions based on search term
  // Filter and sort executions
  const filteredExecutions = useMemo(() => {
    // Filter
    let filtered = executions.filter(execution =>
      execution.flow_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      execution.execution_id.toLowerCase().includes(searchTerm.toLowerCase())
    );

    // Sort
    filtered.sort((a, b) => {
      let aValue, bValue;

      switch(sortBy) {
        case 'flow_name':
          aValue = a.flow_name || '';
          bValue = b.flow_name || '';
          break;
        case 'status':
          aValue = a.status || '';
          bValue = b.status || '';
          break;
        case 'started_at':
        default:
          aValue = new Date(a.started_at || 0).getTime();
          bValue = new Date(b.started_at || 0).getTime();
          break;
      }

      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1;
      } else {
        return aValue < bValue ? 1 : -1;
      }
    });

    return filtered;
  }, [executions, searchTerm, sortBy, sortOrder]);

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
      case 'failed':
        return <XCircleIcon className="w-5 h-5 text-red-500" />;
      case 'running':
        return <ArrowPathIcon className="w-5 h-5 text-primary animate-spin" />;
      case 'paused':
        return <PauseIcon className="w-5 h-5 text-yellow-500" />;
      default:
        return <ClockIcon className="w-5 h-5 text-gray-500" />;
    }
  };

  const getStatusBadge = (status) => {
    const statusStyles = {
      running: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      paused: 'bg-yellow-100 text-yellow-800',
    };

    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusStyles[status]}`}>
        {status}
      </span>
    );
  };

  // Use the imported formatDuration utility
  const formatDuration = formatDurationUtil;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Failed to load executions</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-50 min-h-full">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-6">
      {/* Custom Tooltip */}
      {tooltipData && (
        <div
          className="fixed bg-white rounded-lg shadow-xl border border-gray-200 min-w-[250px] max-w-[350px] pointer-events-auto"
          style={{
            left: `${tooltipPosition.x}px`,
            top: `${tooltipPosition.y}px`,
            transform: 'translateX(-50%)',
            zIndex: 99999 // Higher than navigation panel
          }}
          onMouseEnter={() => {
            // Clear hide timeout and set hover state
            if (tooltipHideTimeoutRef.current) {
              clearTimeout(tooltipHideTimeoutRef.current);
              tooltipHideTimeoutRef.current = null;
            }
            setIsTooltipHovered(true);
          }}
          onMouseLeave={() => {
            setIsTooltipHovered(false);
            // Hide immediately when leaving tooltip
            setTooltipData(null);
          }}
        >
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 bg-gray-50 rounded-t-lg">
            <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
              {tooltipData.label}
            </span>
            <button
              onClick={() => handleCopyFromTooltip(tooltipData.value)}
              className="ml-2 p-1 text-gray-400 hover:text-primary hover:bg-primary-10 rounded transition-all duration-150"
              title="Copy to clipboard"
            >
              {copiedId === 'tooltip-data' ? (
                <ClipboardDocumentCheckIcon className="h-4 w-4 text-green-500" />
              ) : (
                <ClipboardDocumentIcon className="h-4 w-4" />
              )}
            </button>
          </div>
          <div className="px-3 py-2">
            <div className="text-sm text-gray-800 break-all max-h-32 overflow-y-auto font-mono">
              {tooltipData.value}
            </div>
          </div>
        </div>
      )}

      <div className="sm:flex sm:items-center sm:justify-between">
        <div className="sm:flex-auto">
          <h1 className="text-xl sm:text-2xl font-semibold text-gray-900">Executions</h1>
          <p className="mt-2 text-xs sm:text-sm text-gray-700">
            Monitor and debug your flow executions. <span className="hidden sm:inline">All times shown in {getTimezoneDisplay()}.</span>
          </p>
        </div>
        <div className="mt-4 sm:mt-0 sm:ml-6 flex items-center justify-between sm:justify-end space-x-3 sm:space-x-4">
          {/* WebSocket Connection Status */}
          <div className="flex items-center">
            {isConnected ? (
              <>
                <WifiIcon className="h-4 w-4 sm:h-5 sm:w-5 text-green-500 mr-1" />
                <span className="text-xs sm:text-sm text-green-600">Live</span>
              </>
            ) : (
              <>
                <ExclamationTriangleIcon className="h-4 w-4 sm:h-5 sm:w-5 text-yellow-500 mr-1" />
                <span className="text-xs sm:text-sm text-yellow-600">Offline</span>
              </>
            )}
          </div>

          <button
            onClick={() => refetch()}
            className="inline-flex items-center justify-center rounded-md border border-gray-300 bg-white px-3 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
          >
            <ArrowPathIcon className="-ml-0.5 mr-1.5 sm:-ml-1 sm:mr-2 h-4 w-4 sm:h-5 sm:w-5" aria-hidden="true" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="mt-6 space-y-4 sm:space-y-0 sm:grid sm:grid-cols-2 lg:grid-cols-3 sm:gap-4">
        <div className="sm:col-span-2 lg:col-span-1">
          <label htmlFor="search" className="sr-only">
            Search
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
              <MagnifyingGlassIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
            </div>
            <input
              type="text"
              name="search"
              id="search"
              className="block w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-primary focus:border-primary sm:text-sm"
              placeholder="Search executions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div>
          <label htmlFor="flow-filter" className="sr-only">
            Filter by Flow
          </label>
          <select
            id="flow-filter"
            className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm rounded-md"
            value={flowFilter}
            onChange={(e) => setFlowFilter(e.target.value)}
          >
            <option value="all">All Flows</option>
            {flows.map((flow) => (
              <option key={flow.flow_id} value={flow.flow_id}>
                {flow.flow_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="status-filter" className="sr-only">
            Filter by Status
          </label>
          <select
            id="status-filter"
            className="block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-primary focus:border-primary sm:text-sm rounded-md"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Status</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="paused">Paused</option>
          </select>
        </div>
      </div>

      {/* Clear Filters and Sorting Controls */}
      <div className="mt-4 flex justify-between items-center">
        {/* Clear Filters Button - Left Side */}
        <div>
          {(searchTerm !== '' || statusFilter !== 'all' || flowFilter !== 'all') && (
            <div className="relative inline-block">
              <button
                onClick={() => {
                  setSearchTerm('');
                  setStatusFilter('all');
                  setFlowFilter('all');
                  clearPageFilters('executions');
                }}
                className="clear-filter-glow inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              >
                <XMarkIcon className="h-4 w-4 mr-1.5" />
                Clear Filters
                <span className="filter-count-badge">
                  {[
                    searchTerm !== '',
                    statusFilter !== 'all',
                    flowFilter !== 'all'
                  ].filter(Boolean).length}
                </span>
              </button>
            </div>
          )}
        </div>

        {/* Sorting Controls - Right Side */}
        <div className="flex items-center space-x-2">
          <label className="text-sm text-gray-600">Sort by:</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="text-sm border-gray-300 rounded-md focus:ring-primary focus:border-primary"
          >
            <option value="started_at">Start Time</option>
            <option value="flow_name">Flow Name</option>
            <option value="status">Status</option>
          </select>
          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="inline-flex items-center px-2 py-1 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            title={sortOrder === 'asc' ? 'Sort Ascending' : 'Sort Descending'}
          >
            {sortOrder === 'asc' ? '↑' : '↓'}
          </button>
        </div>
      </div>

      {/* Executions List - Mobile Card View */}
      <div className="mt-8 block md:hidden -mx-4 sm:mx-0">
        {filteredExecutions.length === 0 ? (
          <div className="bg-white shadow-sm sm:rounded-lg sm:shadow p-6 text-center text-gray-500">
            No executions found
          </div>
        ) : (
          <div className="bg-white sm:rounded-lg sm:shadow overflow-hidden">
            {filteredExecutions.map((execution, index) => (
              <div key={execution.execution_id} className={`${index > 0 ? 'border-t border-gray-200' : ''} cursor-pointer`} onDoubleClick={() => { setSelectedExecution(execution); setShowDetails(true); }}>
                <div className="p-4 sm:p-6">
                  {/* Header with Status and Flow Name */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center flex-1 min-w-0">
                      <div>
                        {getStatusIcon(execution.status)}
                      </div>
                      <div className="ml-3 flex-1 min-w-0">
                        <h3
                          className="text-sm font-medium text-gray-900 truncate cursor-pointer hover:text-primary"
                          onMouseEnter={(e) => handleMouseEnter(e, 'Flow Name', execution.flow_name || 'Unknown')}
                          onMouseLeave={handleMouseLeave}
                        >
                          {execution.flow_name || 'Unknown'}
                        </h3>
                        <p
                          className="text-xs text-gray-500 mt-1 cursor-pointer hover:text-primary"
                          onMouseEnter={(e) => handleMouseEnter(e, 'Execution ID', execution.execution_id)}
                          onMouseLeave={handleMouseLeave}
                        >
                          ID: {execution.execution_id.split('-')[0]}...
                        </p>
                      </div>
                    </div>
                    <div
                      className="cursor-pointer"
                      onMouseEnter={(e) => handleMouseEnter(e, 'Status', execution.status)}
                      onMouseLeave={handleMouseLeave}
                    >
                      {getStatusBadge(execution.status)}
                    </div>
                  </div>

                {/* Details Grid */}
                <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
                  <div>
                    <dt className="text-gray-500 text-xs uppercase">Trigger</dt>
                    <dd
                      className="text-gray-900 mt-1 capitalize truncate cursor-pointer hover:text-primary"
                      onMouseEnter={(e) => handleMouseEnter(e, 'Trigger Type', execution.trigger_type)}
                      onMouseLeave={handleMouseLeave}
                    >
                      {execution.trigger_type}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-500 text-xs uppercase">Duration</dt>
                    <dd
                      className="text-gray-900 mt-1 cursor-pointer hover:text-primary"
                      onMouseEnter={(e) => handleMouseEnter(e, 'Duration', formatDuration(execution.started_at, execution.completed_at))}
                      onMouseLeave={handleMouseLeave}
                    >
                      {formatDuration(execution.started_at, execution.completed_at)}
                    </dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-gray-500 text-xs uppercase">Started</dt>
                    <dd
                      className="text-gray-900 mt-1 cursor-pointer hover:text-primary"
                      onMouseEnter={(e) => handleMouseEnter(e, 'Started At', formatDateTime(execution.started_at))}
                      onMouseLeave={handleMouseLeave}
                    >
                      {formatDateTime(execution.started_at)}
                    </dd>
                  </div>
                </div>

                  {/* Action Button */}
                  <button
                    onClick={() => {
                      setSelectedExecution(execution);
                      setShowDetails(true);
                    }}
                    className="w-full inline-flex justify-center items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
                  >
                    View Details
                    <ChevronRightIcon className="ml-2 h-4 w-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Executions List - Tablet & Desktop Table View */}
      <div className="mt-8 hidden md:block overflow-hidden shadow ring-1 ring-black ring-opacity-5 rounded-lg">
        <div className="overflow-x-auto">
          <table className="w-full divide-y divide-gray-300">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-3 lg:px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{width: '20%'}}>
                  Execution
                </th>
                <th scope="col" className="px-3 lg:px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{width: '30%'}}>
                  Flow
                </th>
                <th scope="col" className="px-3 lg:px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{width: '12%'}}>
                  Status
                </th>
                <th scope="col" className="hidden lg:table-cell px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{width: '18%'}}>
                  Started
                </th>
                <th scope="col" className="px-3 lg:px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider" style={{width: '12%'}}>
                  Duration
                </th>
                <th scope="col" className="px-3 lg:px-4 py-3 text-right" style={{width: '8%'}}>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredExecutions.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-4 text-center text-gray-500">
                    No executions found
                  </td>
                </tr>
              ) : (
                filteredExecutions.map((execution) => (
                  <tr key={execution.execution_id} className="hover:bg-gray-50 cursor-pointer" onDoubleClick={() => { setSelectedExecution(execution); setShowDetails(true); }}>
                    <td className="px-3 lg:px-4 py-3">
                      <div className="flex items-center space-x-2">
                        <div className="flex-shrink-0">
                          {getStatusIcon(execution.status)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div
                            className="text-sm font-medium text-gray-900 truncate cursor-pointer hover:text-primary"
                            onMouseEnter={(e) => handleMouseEnter(e, 'Execution ID', execution.execution_id)}
                            onMouseLeave={handleMouseLeave}
                          >
                            {execution.execution_id.split('-')[0]}...
                          </div>
                          <div
                            className="text-xs text-gray-500 capitalize truncate cursor-pointer hover:text-primary"
                            onMouseEnter={(e) => handleMouseEnter(e, 'Trigger Type', execution.trigger_type)}
                            onMouseLeave={handleMouseLeave}
                          >
                            {execution.trigger_type}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 lg:px-4 py-3">
                      <div
                        className="text-sm text-gray-900 truncate cursor-pointer hover:text-primary max-w-xs"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Flow Name', execution.flow_name || 'Unknown')}
                        onMouseLeave={handleMouseLeave}
                      >
                        {execution.flow_name || 'Unknown'}
                      </div>
                    </td>
                    <td
                      className="px-3 lg:px-4 py-3 cursor-pointer"
                      onMouseEnter={(e) => handleMouseEnter(e, 'Status', execution.status)}
                      onMouseLeave={handleMouseLeave}
                    >
                      {getStatusBadge(execution.status)}
                    </td>
                    <td className="hidden lg:table-cell px-4 py-3 text-sm text-gray-500">
                      <div
                        className="truncate cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Started At', formatDateTime(execution.started_at))}
                        onMouseLeave={handleMouseLeave}
                      >
                        {formatDateTime(execution.started_at)}
                      </div>
                    </td>
                    <td className="px-3 lg:px-4 py-3 text-sm text-gray-500">
                      <div
                        className="cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Duration', formatDuration(execution.started_at, execution.completed_at))}
                        onMouseLeave={handleMouseLeave}
                      >
                        {formatDuration(execution.started_at, execution.completed_at)}
                      </div>
                    </td>
                    <td className="px-3 lg:px-4 py-3 text-right text-sm font-medium">
                      <button
                        onClick={() => {
                          console.log('[DEBUG] Setting selectedExecution:', execution);
                          setSelectedExecution(execution);
                          setShowDetails(true);
                        }}
                        className="text-primary hover:text-primary-dark inline-flex items-center justify-end"
                      >
                        <span className="hidden xl:inline">Details</span>
                        <ChevronRightIcon className="h-4 w-4 xl:ml-1" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination Controls */}
      {!isLoading && totalExecutions > itemsPerPage && (
        <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
          <div className="flex-1 flex justify-between sm:hidden">
            <button
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
              className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
              disabled={currentPage === totalPages}
              className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
          <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing{' '}
                <span className="font-medium">
                  {totalExecutions === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1}
                </span>
                {' '}to{' '}
                <span className="font-medium">
                  {Math.min(currentPage * itemsPerPage, totalExecutions)}
                </span>
                {' '}of{' '}
                <span className="font-medium">{totalExecutions}</span>
                {' '}executions
              </p>
            </div>
            <div>
              <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px">
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                  className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeftIcon className="h-5 w-5" />
                </button>
                
                {/* Page numbers */}
                {[...Array(Math.min(5, totalPages))].map((_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                        currentPage === pageNum
                          ? 'z-10 bg-primary-10 border-primary text-primary'
                          : 'bg-white border-gray-300 text-gray-500 hover:bg-gray-50'
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                
                <button
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                  className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronRightIcon className="h-5 w-5" />
                </button>
              </nav>
            </div>
          </div>
        </div>
      )}

      {/* Execution Details Modal */}
      {showDetails && selectedExecution && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 z-[9999]">
          <div className={`flex items-center justify-center min-h-screen p-2 sm:p-4 ${sidebarCollapsed ? 'md:pl-16' : 'md:pl-64'}`}>
            <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[95vh] sm:max-h-[90vh] overflow-hidden">
              <div className="px-4 sm:px-6 py-3 sm:py-4 border-b">
              <div className="flex items-center justify-between">
                <h3 className="text-base sm:text-lg font-medium text-gray-900">
                  Execution Details
                </h3>
                <button
                  onClick={() => {
                    console.log('Closing modal, resetting state');
                    setShowDetails(false);
                    setSelectedExecution(null);
                    setLogsOffset(0);
                    setAllLogs([]);
                  }}
                  className="text-gray-400 hover:text-gray-500 text-2xl leading-none pb-1"
                >
                  ×
                </button>
              </div>
            </div>
            
            <div className="px-4 sm:px-6 py-4 overflow-y-auto max-h-[calc(95vh-60px)] sm:max-h-[calc(90vh-80px)]">
              {executionDetails ? (
                <div className="space-y-4 sm:space-y-6">
                  {/* Summary Section */}
                  <div className="bg-gray-50 rounded-lg p-3 sm:p-4">
                    <h4 className="text-base sm:text-lg font-medium text-gray-900 mb-3">Execution Summary</h4>
                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                      <div className="sm:col-span-2 lg:col-span-1">
                        <dt className="text-sm font-medium text-gray-500">Execution ID</dt>
                        <dd className="mt-1 text-xs sm:text-sm text-gray-900 font-mono break-all">
                          <span className="sm:hidden">{executionDetails.execution_id.substring(0, 8)}...</span>
                          <span className="hidden sm:inline">{executionDetails.execution_id}</span>
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Flow</dt>
                        <dd className="mt-1 text-sm text-gray-900">
                          {executionDetails.flow_name}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Status</dt>
                        <dd className="mt-1">{getStatusBadge(executionDetails.status)}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Duration</dt>
                        <dd className="mt-1 text-sm text-gray-900">
                          {formatDuration(executionDetails.started_at, executionDetails.completed_at)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Trigger Type</dt>
                        <dd className="mt-1 text-sm text-gray-900 capitalize">
                          {executionDetails.trigger_type}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Started At</dt>
                        <dd className="mt-1 text-sm text-gray-900">
                          {formatDateTime(executionDetails.started_at)}
                        </dd>
                      </div>
                      {/* HITL Wait Time - computed from logs */}
                      {allLogs && allLogs.length > 0 && (() => {
                        const parseTS = (ts) => {
                          if (!ts) return null;
                          const s = String(ts);
                          return new Date(!s.endsWith('Z') && !s.includes('+') ? s + 'Z' : s);
                        };
                        // Find paused/completed timestamps from logs
                        let totalWaitMs = 0;
                        let hitlCount = 0;
                        const pausedNodes = {};
                        allLogs.forEach(log => {
                          const nodeId = log.step_id;
                          if (log.message?.includes('⏸️') || log.message?.includes('waiting for human')) {
                            if (nodeId && !pausedNodes[nodeId]) {
                              pausedNodes[nodeId] = { pausedAt: log.data?.paused_at || log.timestamp, hasSuccess: false };
                              hitlCount++;
                            }
                          }
                          if (nodeId && pausedNodes[nodeId]) {
                            if (log.data?.completed_at) {
                              pausedNodes[nodeId].completedAt = log.data.completed_at;
                              pausedNodes[nodeId].hasSuccess = true;
                            } else if (log.message?.includes('✅') || log.data?.execution_stage === 'node_complete') {
                              pausedNodes[nodeId].completedAt = pausedNodes[nodeId].completedAt || log.timestamp;
                              pausedNodes[nodeId].hasSuccess = true;
                            }
                          }
                        });
                        const now = new Date();
                        Object.values(pausedNodes).forEach(p => {
                          const paused = parseTS(p.pausedAt);
                          const resumed = p.hasSuccess ? parseTS(p.completedAt) : null;
                          if (paused) totalWaitMs += (resumed || now) - paused;
                        });
                        if (hitlCount === 0) return null;
                        return (
                          <div>
                            <dt className="text-sm font-medium text-gray-500">Review Wait Time</dt>
                            <dd className="mt-1 text-sm text-orange-700 font-medium">
                              {formatDuration
                                ? (() => {
                                    const secs = Math.floor(totalWaitMs / 1000);
                                    if (secs < 60) return `${secs}s`;
                                    const mins = Math.floor(secs / 60);
                                    const remSecs = secs % 60;
                                    if (mins < 60) return `${mins}m ${remSecs}s`;
                                    const hrs = Math.floor(mins / 60);
                                    const remMins = mins % 60;
                                    return `${hrs}h ${remMins}m`;
                                  })()
                                : `${Math.round(totalWaitMs / 1000)}s`
                              }
                              <span className="text-xs text-gray-500 ml-1">
                                ({hitlCount} node{hitlCount > 1 ? 's' : ''})
                              </span>
                            </dd>
                          </div>
                        );
                      })()}
                    </dl>
                  </div>

                  {/* Input Data Section */}
                  {executionDetails.trigger_data && Object.keys(executionDetails.trigger_data).length > 0 && (
                    <div>
                      <h4 className="text-base sm:text-lg font-medium text-gray-900 mb-2 sm:mb-3">Input Data</h4>
                      <div
                        className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4 overflow-hidden cursor-help"
                        title="Click to copy full data to clipboard"
                        onClick={() => copyToClipboard(executionDetails.trigger_data, 'input-data')}
                      >
                        <pre className="text-xs overflow-x-auto text-blue-900 max-h-40 sm:max-h-60 select-none">
                          {JSON.stringify(executionDetails.trigger_data, null, 2)}
                        </pre>
                        {JSON.stringify(executionDetails.trigger_data).length > 500 && (
                          <p className="text-xs text-primary mt-2">
                            Click to copy full data • {JSON.stringify(executionDetails.trigger_data).length} chars
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Activity Trace Section */}
                  <div className="mt-4 sm:mt-6">
                    <h4 className="text-base sm:text-lg font-medium text-gray-900 mb-2 sm:mb-3">Activity Trace</h4>
                    
                    {/* Debug info */}
                    {console.log('Activity Trace Debug:', {
                      isLoadingLogs,
                      allLogsLength: allLogs.length,
                      executionLogsData,
                      logsError,
                      selectedExecution: selectedExecution?.execution_id
                    })}
                    
                    {/* Show loading indicator */}
                    {isLoadingLogs && allLogs.length === 0 && (
                      <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mr-3"></div>
                        <span className="text-gray-600">Loading execution logs...</span>
                      </div>
                    )}
                    
                    {/* Show error if any */}
                    {logsError && (
                      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                        <p className="text-red-800">Error loading logs: {logsError.message}</p>
                      </div>
                    )}
                    
                    {/* Show logs if available */}
                    {!isLoadingLogs && !logsError && allLogs.length > 0 && (
                      <>
                        {console.log('Rendering HierarchicalExecutionLog with:', {
                          logsCount: allLogs.length,
                          total: executionLogsData?.total,
                          hasMore: executionLogsData?.has_more,
                          executionLogsData,
                          executionDetails,
                          flowId: executionDetails?.flow_id,
                          flowName: executionDetails?.flow_name,
                          flowDescription: executionDetails?.flow_description
                        })}
                        <HierarchicalExecutionLog
                          logs={allLogs}
                          totalLogs={executionLogsData?.total}
                          hasMore={executionLogsData?.has_more}
                          onLoadMore={loadMoreLogs}
                          isLoadingMore={isFetchingMoreLogs}
                          executionId={selectedExecution?.execution_id}
                          flowId={executionDetails?.flow_id}
                          flowName={executionDetails?.flow_name}
                          flowDescription={executionDetails?.flow_description}
                        />
                      </>
                    )}
                    
                    {/* Show message if no logs */}
                    {!isLoadingLogs && !logsError && allLogs.length === 0 && (
                      <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
                        <p className="text-gray-600">No execution logs available</p>
                        <p className="text-sm text-gray-500 mt-2">
                          Logs may not have been fetched. Check console for errors.
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Output Data Section */}
                  {executionDetails.execution_data && Object.keys(executionDetails.execution_data).length > 0 && (
                    <div>
                      <h4 className="text-base sm:text-lg font-medium text-gray-900 mb-2 sm:mb-3">Output Data</h4>
                      <div
                        className="bg-green-50 border border-green-200 rounded-lg p-3 sm:p-4 overflow-hidden cursor-help"
                        title="Click to copy full data to clipboard"
                        onClick={() => copyToClipboard(executionDetails.execution_data, 'output-data')}
                      >
                        <pre className="text-xs overflow-x-auto text-green-900 max-h-40 sm:max-h-60 select-none">
                          {JSON.stringify(executionDetails.execution_data, null, 2)}
                        </pre>
                        {JSON.stringify(executionDetails.execution_data).length > 500 && (
                          <p className="text-xs text-green-600 mt-2">
                            Click to copy full data • {JSON.stringify(executionDetails.execution_data).length} chars
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                </div>
              ) : (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      )}
      </div>
    </div>
  );
};

export default Executions;