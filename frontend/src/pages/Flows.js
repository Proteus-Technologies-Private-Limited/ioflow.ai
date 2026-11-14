import React, { useState, useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import axios from 'axios';
import { showErrorToast, showSuccessToast, showInfoToast, showWarningToast } from '../utils/customToast';
import { getFullErrorMessage } from '../utils/errorHandler';
import { formatDate, formatDateTime, formatDuration } from '../utils/dateFormatter';
import ManualTriggerModal from '../components/flows/ManualTriggerModal';
import FlowPublishingModal from '../components/flow/FlowPublishingModal';
import PublishAsExampleModal from '../components/flows/PublishAsExampleModal';
import HierarchicalExecutionLog from '../components/execution/HierarchicalExecutionLog';
import '../styles/FilterIndicators.css';
import {
  PlusIcon,
  MagnifyingGlassIcon,
  PlayIcon,
  PauseIcon,
  PencilIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  BoltIcon,
  ClockIcon,
  CursorArrowRaysIcon,
  RocketLaunchIcon,
  ShareIcon,
  XMarkIcon,
  GlobeAltIcon,
  BuildingOfficeIcon,
  UserIcon,
  CheckCircleIcon,
  PencilSquareIcon,
  ExclamationCircleIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
  ChevronRightIcon,
  ChevronUpDownIcon,
  EllipsisVerticalIcon,
  AcademicCapIcon,
  ShoppingBagIcon,
  CogIcon,
  DocumentTextIcon,
  XCircleIcon,
  BookOpenIcon,
  ArrowDownTrayIcon,
} from '@heroicons/react/24/outline';
import { useFilters } from '../contexts/FilterContext';
import { useSidebar } from '../contexts/SidebarContext';
import { useLayout } from '../contexts/LayoutContext';
import { useAuth } from '../contexts/AuthContext';

const Flows = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { getPageFilters, updatePageFilters, clearPageFilters } = useFilters();
  const { sidebarCollapsed } = useSidebar();
  const { isAssistantLayout } = useLayout();
  const { user } = useAuth();

  // Tooltip state
  const [tooltipData, setTooltipData] = useState(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const [isTooltipHovered, setIsTooltipHovered] = useState(false);
  const [copiedId, setCopiedId] = useState(null);
  const tooltipShowTimeoutRef = useRef(null);
  const tooltipHideTimeoutRef = useRef(null);
  const pendingTooltipData = useRef(null);

  // Get saved filters or use defaults
  const savedFilters = getPageFilters('flows', {
    searchTerm: '',
    statusFilter: 'all',
    scopeFilter: 'all',
    categoryFilter: 'all'
  });

  const [searchTerm, setSearchTerm] = useState(savedFilters.searchTerm);
  const [statusFilter, setStatusFilter] = useState(savedFilters.statusFilter);
  const [scopeFilter, setScopeFilter] = useState(savedFilters.scopeFilter);
  const [categoryFilter, setCategoryFilter] = useState(savedFilters.categoryFilter);
  const [selectedFlow, setSelectedFlow] = useState(null);
  const [showTriggerModal, setShowTriggerModal] = useState(false);
  const [showPublishingModal, setShowPublishingModal] = useState(false);
  const [publishingFlow, setPublishingFlow] = useState(null);
  const [publishType, setPublishType] = useState(null); // 'reusable' or 'frontend'
  const [showPublishAsExampleModal, setShowPublishAsExampleModal] = useState(false);
  const [flowToPublish, setFlowToPublish] = useState(null);
  const [openDropdownId, setOpenDropdownId] = useState(null);
  const [sortBy, setSortBy] = useState('updated_at');
  const [sortOrder, setSortOrder] = useState('desc');

  // Execution details modal state
  const [showExecutionDetails, setShowExecutionDetails] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState(null);
  const [logsOffset, setLogsOffset] = useState(0);
  const [allLogs, setAllLogs] = useState([]);
  const logsLimit = 200;

  // Dynamic column visibility based on available width
  const [columnVisibility, setColumnVisibility] = useState({
    trigger: true,
    scope: true,
    category: true
  });

  // Tooltip helper functions with delay
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
    const tooltipWidth = 300;
    const leftNavWidth = 256;

    // Calculate X position
    let x = rect.left + rect.width / 2;
    if (x - tooltipWidth / 2 < leftNavWidth + 10) {
      x = leftNavWidth + tooltipWidth / 2 + 10;
    } else if (x + tooltipWidth / 2 > viewportWidth - 10) {
      x = viewportWidth - tooltipWidth / 2 - 10;
    }

    // Calculate Y position
    const spaceAbove = rect.top;
    const tooltipHeight = 100;
    let y = spaceAbove > tooltipHeight + 10
      ? rect.top - tooltipHeight - 5
      : rect.bottom + 5;

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

  // Helper function to copy to clipboard
  const copyToClipboard = async (data) => {
    try {
      const jsonStr = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
      await navigator.clipboard.writeText(jsonStr);
      setCopiedId('tooltip-data');
      showSuccessToast('Copied to clipboard');
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      showErrorToast('Failed to copy to clipboard');
    }
  };

  const handleCopyFromTooltip = (value) => {
    copyToClipboard(value);
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

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!event.target.closest('.dropdown-menu')) {
        setOpenDropdownId(null);
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  // Save filters whenever they change
  useEffect(() => {
    updatePageFilters('flows', {
      searchTerm,
      statusFilter,
      scopeFilter,
      categoryFilter
    });
  }, [searchTerm, statusFilter, scopeFilter, categoryFilter, updatePageFilters]);

  // Dynamic column visibility based on effective viewport width
  useEffect(() => {
    const updateColumnVisibility = () => {
      // Calculate effective width available for content
      const windowWidth = window.innerWidth;

      // Get assistant panel width from localStorage (updated when resized)
      const assistantPanelWidth = parseInt(localStorage.getItem('assistantPanelWidth') || '330', 10);

      // Calculate space taken by sidebar and assistant
      let usedWidth = 0;

      // Sidebar width
      if (windowWidth >= 768) { // md breakpoint
        usedWidth += sidebarCollapsed ? 64 : 256;
      }

      // Assistant panel width (only in assistant layout and on lg screens)
      if (isAssistantLayout && windowWidth >= 1024) { // lg breakpoint
        usedWidth += assistantPanelWidth;
      }

      // Calculate effective available width
      const effectiveWidth = windowWidth - usedWidth;

      // Use same responsive breakpoints as Tailwind but based on effective width
      setColumnVisibility({
        category: effectiveWidth >= 1536,  // 2xl equivalent
        scope: effectiveWidth >= 1280,     // xl equivalent
        trigger: effectiveWidth >= 1024    // lg equivalent
      });
    };

    // Update on mount and when dependencies change
    updateColumnVisibility();

    // Listen for window resize
    window.addEventListener('resize', updateColumnVisibility);

    // Listen for storage changes (assistant width change)
    const handleStorageChange = (e) => {
      if (e.key === 'assistantPanelWidth') {
        updateColumnVisibility();
      }
    };
    window.addEventListener('storage', handleStorageChange);

    return () => {
      window.removeEventListener('resize', updateColumnVisibility);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, [sidebarCollapsed, isAssistantLayout]); // Re-run when sidebar or layout changes

  // Fetch flows
  const { data: flows = [], isLoading, error } = useQuery({
    queryKey: ['flows', statusFilter],
    queryFn: async () => {
      let url = '/api/v1/flows/';
      const params = new URLSearchParams();

      if (statusFilter !== 'all') {
        params.append('status', statusFilter);
      }

      // Don't include execution stats by default for performance
      params.append('include_stats', 'false');
      // Include user info for display
      params.append('include_user_info', 'true');

      if (params.toString()) {
        url += `?${params.toString()}`;
      }

      const response = await axios.get(url);
      return response.data;
    },
  });

  // Delete flow mutation
  const deleteFlowMutation = useMutation({
    mutationFn: (flowId) => axios.delete(`/api/v1/flows/${flowId}`),
    onSuccess: () => {
      queryClient.invalidateQueries(['flows']);
      showSuccessToast('Flow deleted successfully');
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to delete flow');
      showErrorToast(errorMessage);
    },
  });

  // Update flow status mutation
  const updateFlowStatusMutation = useMutation({
    mutationFn: ({ flowId, status }) => 
      axios.put(`/api/v1/flows/${flowId}`, { status }),
    onSuccess: (_, { status }) => {
      queryClient.invalidateQueries(['flows']);
      showSuccessToast(`Flow ${status} successfully`);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to update flow status');
      showErrorToast(errorMessage);
    },
  });

  // Trigger flow mutation
  const triggerFlowMutation = useMutation({
    mutationFn: ({ flowId, inputData }) =>
      axios.post(`/api/v1/flows/${flowId}/execute`, {
        trigger_type: 'manual',
        variables: inputData
      }),
    onSuccess: (data, variables) => {
      showSuccessToast('Flow triggered successfully');
      // Only close modal if it's open
      if (showTriggerModal) {
        setShowTriggerModal(false);
        setSelectedFlow(null);
      }
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to trigger flow');
      showErrorToast(errorMessage);
    },
  });

  // Publish flow as example mutation
  const publishAsExampleMutation = useMutation({
    mutationFn: (publishData) =>
      axios.post('/api/v1/flow-examples/publish', publishData),
    onSuccess: (response) => {
      showSuccessToast(`Flow published as example: ${response.data.example_id}`);
      setShowPublishAsExampleModal(false);
      setFlowToPublish(null);
      // Optionally navigate to flow examples page
      setTimeout(() => {
        navigate('/flow-examples');
      }, 1500);
    },
    onError: (error) => {
      const errorMessage = getFullErrorMessage(error, 'Failed to publish flow as example');
      showErrorToast(errorMessage);
    },
  });

  // Helper functions for status changes
  const activateFlow = (flowId) => {
    updateFlowStatusMutation.mutate({ flowId, status: 'active' });
  };

  const deactivateFlow = (flowId) => {
    updateFlowStatusMutation.mutate({ flowId, status: 'inactive' });
  };

  const cancelFlow = (flowId) => {
    if (window.confirm('Are you sure you want to cancel this flow? This will set it back to draft status.')) {
      updateFlowStatusMutation.mutate({ flowId, status: 'draft' });
    }
  };

  // Get unique categories from flows
  const categories = [...new Set(flows.map(flow => flow.category).filter(Boolean))];
  
  // Filter flows based on all criteria
  const filteredFlows = flows.filter(flow => {
    // Search term filter
    const matchesSearch = searchTerm === '' ||
      flow.flow_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      flow.flow_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (flow.description && flow.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (flow.category && flow.category.toLowerCase().includes(searchTerm.toLowerCase()));

    // Scope filter
    const matchesScope = scopeFilter === 'all' || flow.flow_scope === scopeFilter;

    // Category filter
    const matchesCategory = categoryFilter === 'all' || flow.category === categoryFilter;

    return matchesSearch && matchesScope && matchesCategory;
  });

  // Sort flows
  const sortedFlows = [...filteredFlows].sort((a, b) => {
    let compareValue = 0;

    switch (sortBy) {
      case 'flow_name':
        compareValue = (a.flow_name || '').localeCompare(b.flow_name || '');
        break;
      case 'status':
        compareValue = (a.status || '').localeCompare(b.status || '');
        break;
      case 'created_at':
        compareValue = new Date(a.created_at) - new Date(b.created_at);
        break;
      case 'updated_at':
      default:
        compareValue = new Date(a.updated_at || a.created_at) - new Date(b.updated_at || b.created_at);
        break;
    }

    return sortOrder === 'desc' ? -compareValue : compareValue;
  });
  
  // Clear all filters function
  const handleClearFilters = () => {
    setSearchTerm('');
    setStatusFilter('all');
    setScopeFilter('all');
    setCategoryFilter('all');
    clearPageFilters('flows');
  };
  
  // Check if any filters are active
  const hasActiveFilters = searchTerm !== '' ||
    statusFilter !== 'all' ||
    scopeFilter !== 'all' ||
    categoryFilter !== 'all';

  // Count active filters
  const activeFilterCount = [
    searchTerm !== '',
    statusFilter !== 'all',
    scopeFilter !== 'all',
    categoryFilter !== 'all'
  ].filter(Boolean).length;

  const handleDelete = (flowId) => {
    if (window.confirm('Are you sure you want to delete this flow?')) {
      deleteFlowMutation.mutate(flowId);
    }
  };

  const handleExportFlow = async (flow) => {
    try {
      const response = await axios.post(`/api/v1/flows/${flow.flow_id}/export`);
      const exportData = response.data;

      const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${flow.flow_name || 'flow'}_export_${new Date().getTime()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      showSuccessToast('Flow exported successfully');

      if (exportData.metadata?.warnings?.length > 0) {
        exportData.metadata.warnings.forEach(warning => {
          showWarningToast(warning.message);
        });
      }
    } catch (error) {
      const errorMessage = getFullErrorMessage(error, 'Failed to export flow');
      showErrorToast(errorMessage);
    }
  };

  const handleDuplicate = async (flow) => {
    try {
      const newFlow = {
        flow_name: `${flow.flow_name} (Copy)`,
        description: flow.description,
        category: flow.category,
        trigger_config: flow.trigger_config,
        flow_definition: flow.flow_definition,
      };
      await axios.post('/api/v1/flows/', newFlow);
      queryClient.invalidateQueries(['flows']);
      showSuccessToast('Flow duplicated successfully');
    } catch (error) {
      const errorMessage = getFullErrorMessage(error, 'Failed to duplicate flow');
      showErrorToast(errorMessage);
    }
  };

  const handleTriggerFlow = (flow) => {
    setSelectedFlow(flow);
    
    // Check if flow has manual trigger configuration
    const triggerConfig = flow?.trigger_config || {};
    const isManual = triggerConfig.type === 'manual';
    const manualVariables = isManual ? (triggerConfig.manual_variables || []) : [];
    
    // For synchronous flows, always show modal (even without parameters)
    // For async flows without parameters, execute directly
    if (flow.is_synchronous) {
      // Always show modal for synchronous flows
      setShowTriggerModal(true);
    } else if (isManual && manualVariables.length === 0) {
      // For non-synchronous manual triggers with no variables, execute directly
      triggerFlowMutation.mutate({ 
        flowId: flow.flow_id, 
        inputData: {} 
      });
    } else {
      // Show modal for all other cases
      setShowTriggerModal(true);
    }
  };

  const handleTriggerSubmit = (inputData) => {
    if (selectedFlow) {
      triggerFlowMutation.mutate({ 
        flowId: selectedFlow.flow_id, 
        inputData 
      });
    }
  };

  const getTriggerIcon = (triggerType) => {
    switch (triggerType) {
      case 'event':
        return <BoltIcon className="w-4 h-4" />;
      case 'schedule':
        return <ClockIcon className="w-4 h-4" />;
      default:
        return <CursorArrowRaysIcon className="w-4 h-4" />;
    }
  };

  // Publishing handlers
  const handlePublishReusableApp = (flow) => {
    setPublishingFlow(flow);
    setPublishType('reusable');
    setShowPublishingModal(true);
  };

  const handlePublishMicroSaasApp = async (flow) => {
    try {
      // Validate if the flow can be published as Micro SaaS app
      await axios.get(`/api/v1/micro-saas-apps/validate-flow/${flow.flow_id}`);

      // If validation passes, show the modal
      setPublishingFlow(flow);
      setPublishType('frontend');
      setShowPublishingModal(true);
    } catch (error) {
      // Debug: Log the error structure
      console.log('Full error object:', error);
      console.log('Error response:', error.response);
      console.log('Error response data:', error.response?.data);
      console.log('Error response data detail:', (error.response?.data?.message || error.response?.data?.detail));

      // Show validation error using the standard error handler
      const errorMessage = getFullErrorMessage(error, 'This flow cannot be published as a Micro SaaS app');
      console.log('Extracted error message:', errorMessage);
      showErrorToast(errorMessage);
    }
  };

  // Publish as Example handlers
  const handlePublishAsExample = (flow) => {
    setFlowToPublish(flow);
    setShowPublishAsExampleModal(true);
  };

  const handlePublishAsExampleSubmit = (publishData) => {
    publishAsExampleMutation.mutate(publishData);
  };

  // Check if user is instance admin
  const isInstanceAdmin = user?.role === 'INSTANCE_ADMIN';
  const canManageFlows = user?.role !== 'EXECUTION_MONITOR' && user?.role !== 'FLOW_EXECUTOR';
  // EXECUTION_MONITOR is allowed to (re)activate flows; FLOW_EXECUTOR is not.
  const canActivateFlows = user?.role !== 'FLOW_EXECUTOR';

  // Fetch execution details when a flow execution is selected
  const { data: executionDetails } = useQuery({
    queryKey: ['execution-details', selectedExecution?.execution_id],
    queryFn: async () => {
      const response = await axios.get(`/api/v1/executions/${selectedExecution.execution_id}`);
      return response.data;
    },
    enabled: !!selectedExecution && showExecutionDetails,
  });

  // Fetch execution logs with pagination
  const { data: executionLogsData, isLoading: isLoadingLogs, isFetching: isFetchingMoreLogs } = useQuery({
    queryKey: ['execution-logs', selectedExecution?.execution_id, logsOffset],
    queryFn: async () => {
      const response = await axios.get(
        `/api/v1/executions/${selectedExecution.execution_id}/logs?limit=${logsLimit}&offset=${logsOffset}&include_data=false`
      );
      return response.data;
    },
    enabled: !!selectedExecution && showExecutionDetails,
    refetchOnWindowFocus: false,
    refetchOnMount: 'always',
    staleTime: 0,
    gcTime: 0,
  });

  // Update allLogs when new data arrives
  useEffect(() => {
    if (executionLogsData) {
      let logsToAdd = [];

      if (executionLogsData.logs && Array.isArray(executionLogsData.logs)) {
        logsToAdd = executionLogsData.logs;
      } else if (Array.isArray(executionLogsData)) {
        logsToAdd = executionLogsData;
      }

      if (logsToAdd.length > 0) {
        if (logsOffset === 0) {
          setAllLogs(logsToAdd);
        } else {
          setAllLogs(prev => [...prev, ...logsToAdd]);
        }
      }
    }
  }, [executionLogsData, logsOffset]);

  // Reset pagination when execution changes
  useEffect(() => {
    setLogsOffset(0);
    setAllLogs([]);
    if (selectedExecution) {
      queryClient.invalidateQueries(['execution-logs']);
    }
  }, [selectedExecution?.execution_id, queryClient]);

  const loadMoreLogs = () => {
    setLogsOffset(prev => prev + logsLimit);
  };

  // Handler to view last execution log
  const handleViewLastExecution = async (flow) => {
    try {
      // Fetch the last execution for this flow
      const response = await axios.get(`/api/v1/executions/?flow_id=${flow.flow_id}&limit=1`);
      if (response.data && response.data.length > 0) {
        setSelectedExecution(response.data[0]);
        setShowExecutionDetails(true);
        setOpenDropdownId(null);
      } else {
        showInfoToast('No execution history found for this flow');
      }
    } catch (error) {
      const errorMessage = getFullErrorMessage(error, 'Failed to fetch execution history');
      showErrorToast(errorMessage);
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
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusStyles[status] || 'bg-gray-100 text-gray-800'}`}>
        {status}
      </span>
    );
  };


  const getStatusIcon = (status) => {
    switch (status) {
      case 'active':
        return (
          <div className="flex items-center" title="Active">
            <CheckCircleIcon className="w-5 h-5 text-green-600" />
          </div>
        );
      case 'draft':
        return (
          <div className="flex items-center" title="Draft">
            <PencilSquareIcon className="w-5 h-5 text-gray-500" />
          </div>
        );
      case 'inactive':
        return (
          <div className="flex items-center" title="Inactive">
            <ExclamationCircleIcon className="w-5 h-5 text-yellow-600" />
          </div>
        );
      default:
        return null;
    }
  };

  const getScopeIcon = (scope) => {
    const normalizedScope = scope || 'user';
    switch (normalizedScope) {
      case 'global':
        return (
          <div className="flex items-center" title="Global">
            <GlobeAltIcon className="w-5 h-5 text-purple-600" />
          </div>
        );
      case 'tenant':
        return (
          <div className="flex items-center" title="Tenant">
            <BuildingOfficeIcon className="w-5 h-5 text-blue-600" />
          </div>
        );
      case 'user':
        return (
          <div className="flex items-center" title="User">
            <UserIcon className="w-5 h-5 text-gray-600" />
          </div>
        );
      default:
        return (
          <div className="flex items-center" title={normalizedScope}>
            <UserIcon className="w-5 h-5 text-gray-600" />
          </div>
        );
    }
  };

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
        <p className="text-red-600">Failed to load flows</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-50">
      <div className="w-full px-4 sm:px-6 lg:px-8 py-6 pb-8">
      {/* Custom Tooltip */}
      {tooltipData && (
        <div
          className="fixed bg-white rounded-lg shadow-xl border border-gray-200 w-[250px] sm:w-[300px] max-w-[90vw] pointer-events-auto"
          style={{
            left: `${Math.min(Math.max(tooltipPosition.x, 140), window.innerWidth - 140)}px`,
            top: `${tooltipPosition.y}px`,
            transform: 'translateX(-50%)',
            zIndex: 99999
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

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h1 className="text-xl sm:text-2xl font-semibold text-gray-900">Flows</h1>
          <p className="mt-2 text-xs sm:text-sm text-gray-700">
            Create and manage your automation workflows
          </p>
        </div>
        {canManageFlows && (
          <div className="flex-shrink-0">
            <Link
              to="/flows/new"
              className="inline-flex items-center justify-center rounded-md border border-transparent bg-gradient-primary px-3 py-1.5 sm:px-4 sm:py-2 text-xs sm:text-sm font-medium text-white shadow-sm hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
            >
              <PlusIcon className="-ml-0.5 mr-1.5 sm:-ml-1 sm:mr-2 h-4 w-4 sm:h-5 sm:w-5" aria-hidden="true" />
              New Flow
            </Link>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="mt-4 space-y-3 w-full">
        <div className="flex flex-col gap-3 sm:grid sm:grid-cols-2 lg:grid-cols-4">
          <div>
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
                className="block w-full pl-10 pr-3 py-1.5 border border-gray-300 rounded-md leading-5 bg-white placeholder-gray-500 focus:outline-none focus:placeholder-gray-400 focus:ring-1 focus:ring-primary focus:border-primary text-sm"
                placeholder="Search flows..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          <div>
            <select
              className="block w-full pl-3 pr-10 py-1.5 text-sm border-gray-300 focus:outline-none focus:ring-primary focus:border-primary rounded-md"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="all">All Status</option>
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
          </div>
          
          <div>
            <select
              className="block w-full pl-3 pr-10 py-1.5 text-sm border-gray-300 focus:outline-none focus:ring-primary focus:border-primary rounded-md"
              value={scopeFilter}
              onChange={(e) => setScopeFilter(e.target.value)}
            >
              <option value="all">All Scopes</option>
              <option value="global">Global</option>
              <option value="tenant">Tenant</option>
              <option value="user">User</option>
            </select>
          </div>
          
          <div>
            <select
              className="block w-full pl-3 pr-10 py-1.5 text-sm border-gray-300 focus:outline-none focus:ring-primary focus:border-primary rounded-md"
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
            >
              <option value="all">All Categories</option>
              {categories.map(category => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
        </div>
        
        {/* Clear Filters and Sort Controls */}
        <div className="flex justify-between items-center mt-3">
          {/* Clear Filters Button - Left Side */}
          <div>
            {hasActiveFilters ? (
              <div className="relative">
                <button
                  onClick={handleClearFilters}
                  className="clear-filter-glow inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
                >
                  <XMarkIcon className="h-4 w-4 mr-1.5" />
                  Clear Filters
                  <span className="filter-count-badge">{activeFilterCount}</span>
                </button>
              </div>
            ) : (
              <div></div>
            )}
          </div>

          {/* Sort Controls - Right Side */}
          <div className="flex gap-2 ml-auto">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="block rounded-md border-gray-300 py-2 pl-3 pr-10 text-base focus:border-primary focus:outline-none focus:ring-primary sm:text-sm"
            >
              <option value="updated_at">Last Modified</option>
              <option value="flow_name">Name</option>
              <option value="status">Status</option>
              <option value="created_at">Created Date</option>
            </select>

            <button
              type="button"
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="inline-flex items-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50"
              title={sortOrder === 'asc' ? 'Sort descending' : 'Sort ascending'}
            >
              <ChevronUpDownIcon className="h-5 w-5 mr-1" />
              {sortOrder === 'asc' ? 'Asc' : 'Desc'}
            </button>
          </div>
        </div>
      </div>

      {/* Flows List - Mobile Card View */}
      <div className="mt-6 block md:hidden w-full">
        {filteredFlows.length === 0 ? (
          <div className="bg-white rounded-lg shadow-sm p-6 text-center text-gray-500">
            No flows found
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow-sm w-full">
            {sortedFlows.map((flow, index) => (
              <div key={flow.flow_id} className={`${index > 0 ? 'border-t border-gray-200' : ''} cursor-pointer`} onDoubleClick={() => navigate(`/flows/${flow.flow_id}/edit`)}>
                <div className="p-3 box-border">
                  {/* Header with Name and Status */}
                  <div className="flex items-start justify-between mb-3 gap-2">
                    <div className="flex-1 min-w-0 overflow-hidden">
                      <h3
                        className="text-sm font-medium text-gray-900 truncate cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Flow Name', flow.flow_name)}
                        onMouseLeave={handleMouseLeave}
                      >
                        {flow.flow_name}
                      </h3>
                      <p
                        className="text-xs text-gray-500 mt-1 line-clamp-2 cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Description', flow.description || 'No description')}
                        onMouseLeave={handleMouseLeave}
                      >
                        {flow.description || 'No description provided'}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {getScopeIcon(flow.flow_scope)}
                      {getStatusIcon(flow.status)}
                    </div>
                  </div>

                  {/* Details Grid */}
                  <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
                    <div>
                      <dt className="text-gray-500 text-xs uppercase">Category</dt>
                      <dd
                        className="text-gray-900 mt-1 truncate cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Category', flow.category || 'No category')}
                        onMouseLeave={handleMouseLeave}
                      >
                        {flow.category || '-'}
                      </dd>
                    </div>
                    <div className="text-right">
                      <dt className="text-gray-500 text-xs uppercase">Trigger</dt>
                      <dd className="text-gray-900 mt-1 flex items-center justify-end">
                        {getTriggerIcon(flow.trigger_config?.type)}
                        <span className="ml-1 capitalize text-xs truncate">
                          {flow.trigger_config?.type || 'manual'}
                        </span>
                      </dd>
                    </div>
                    <div className="col-span-2">
                      <dt className="text-gray-500 text-xs uppercase">Metadata</dt>
                      <dd
                        className="text-gray-900 mt-1 text-xs cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => {
                          const metadata = `
                            Created: ${formatDate(flow.created_at)}
                            By: ${flow.created_by_user?.email || flow.created_by || 'Unknown'}
                            Modified: ${formatDate(flow.updated_at)}
                            By: ${flow.last_modified_by_user?.email || flow.last_modified_by || 'Unknown'}${
                              flow.execution_count !== undefined
                                ? `\nRuns: ${flow.execution_count}${flow.last_execution_at ? `, Last: ${formatDate(flow.last_execution_at)}` : ''}`
                                : ''
                            }
                          `.trim();
                          handleMouseEnter(e, 'Flow Metadata', metadata);
                        }}
                        onMouseLeave={handleMouseLeave}
                      >
                        <div className="flex items-center space-x-1">
                          <UserIcon className="h-3 w-3 text-gray-400 inline" />
                          <span>{flow.created_by_user?.user_name || 'Unknown'}</span>
                        </div>
                        <div className="text-gray-500">{formatDate(flow.created_at)}</div>
                        {flow.execution_count !== undefined && flow.execution_count > 0 && (
                          <div className="text-gray-500 flex items-center mt-1">
                            <BoltIcon className="h-3 w-3 text-gray-400 mr-1" />
                            {flow.execution_count} runs
                          </div>
                        )}
                      </dd>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center justify-between gap-3 pt-3 border-t border-gray-200">
                    <div className="flex items-center gap-3">
                      {/* Primary action buttons with better spacing */}
                      {canActivateFlows && flow.status === 'draft' && (
                        <button
                          onClick={() => activateFlow(flow.flow_id)}
                          className="text-green-600 hover:text-green-900 p-2 hover:bg-green-50 rounded-lg transition-colors"
                          title="Activate Flow"
                        >
                          <PlayIcon className="h-5 w-5" />
                        </button>
                      )}
                      {canActivateFlows && flow.status === 'active' && (
                        <button
                          onClick={() => deactivateFlow(flow.flow_id)}
                          className="text-yellow-600 hover:text-yellow-900 p-2 hover:bg-yellow-50 rounded-lg transition-colors"
                          title="Pause Flow"
                        >
                          <PauseIcon className="h-5 w-5" />
                        </button>
                      )}
                      {canActivateFlows && flow.status === 'inactive' && (
                        <button
                          onClick={() => activateFlow(flow.flow_id)}
                          className="text-green-600 hover:text-green-900 p-2 hover:bg-green-50 rounded-lg transition-colors"
                          title="Reactivate Flow"
                        >
                          <PlayIcon className="h-5 w-5" />
                        </button>
                      )}
                      {(flow.status === 'draft' || flow.status === 'active') && (
                        <button
                          onClick={() => handleTriggerFlow(flow)}
                          className="text-purple-600 hover:text-purple-900 p-2 hover:bg-purple-50 rounded-lg transition-colors"
                          title="Trigger Flow"
                        >
                          <RocketLaunchIcon className="h-5 w-5" />
                        </button>
                      )}
                      {canManageFlows && (
                        <Link
                          to={`/flows/${flow.flow_id}/edit`}
                          className="text-primary hover:text-primary-dark p-2 hover:bg-primary-10 rounded-lg transition-colors"
                          title="Edit Flow"
                        >
                          <PencilIcon className="h-5 w-5" />
                        </Link>
                      )}
                    </div>

                    <div className="relative dropdown-menu">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenDropdownId(openDropdownId === flow.flow_id ? null : flow.flow_id);
                        }}
                        className="text-gray-600 hover:text-gray-900 p-2 hover:bg-gray-50 rounded-lg transition-colors"
                        title="More actions"
                      >
                        <EllipsisVerticalIcon className="h-5 w-5" />
                      </button>

                      {openDropdownId === flow.flow_id && (
                        <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg z-10 border border-gray-200">
                          <div className="py-1">
                            <button
                              onClick={() => {
                                navigate(`/flows/${flow.flow_id}/api-docs`);
                                setOpenDropdownId(null);
                              }}
                              className="flex items-center w-full px-4 py-2 text-sm text-primary hover:bg-primary-10"
                            >
                              <BookOpenIcon className="h-4 w-4 mr-2" />
                              API Documentation
                            </button>
                            <button
                              onClick={() => handleViewLastExecution(flow)}
                              className="flex items-center w-full px-4 py-2 text-sm text-blue-700 hover:bg-primary-10"
                            >
                              <DocumentTextIcon className="h-4 w-4 mr-2" />
                              Last Execution Log
                            </button>
                            {canManageFlows && (flow.status === 'active' || flow.status === 'inactive') && (
                              <button
                                onClick={() => {
                                  cancelFlow(flow.flow_id);
                                  setOpenDropdownId(null);
                                }}
                                className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                              >
                                <XMarkIcon className="h-4 w-4 mr-2" />
                                Cancel (to Draft)
                              </button>
                            )}
                            {canManageFlows && (
                              <>
                                <button
                                  onClick={() => {
                                    handlePublishReusableApp(flow);
                                    setOpenDropdownId(null);
                                  }}
                                  className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                >
                                  <CogIcon className="h-4 w-4 mr-2" />
                                  Publish as Reusable App
                                </button>
                                <button
                                  onClick={() => {
                                    handlePublishMicroSaasApp(flow);
                                    setOpenDropdownId(null);
                                  }}
                                  className="flex items-center w-full px-4 py-2 text-sm text-secondary hover:bg-secondary/10"
                                >
                                  <ShoppingBagIcon className="h-4 w-4 mr-2" />
                                  Publish as Micro SaaS App
                                </button>
                                <button
                                  onClick={() => {
                                    handleDuplicate(flow);
                                    setOpenDropdownId(null);
                                  }}
                                  className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                >
                                  <DocumentDuplicateIcon className="h-4 w-4 mr-2" />
                                  Duplicate
                                </button>
                              </>
                            )}
                            <button
                              onClick={() => {
                                handleExportFlow(flow);
                                setOpenDropdownId(null);
                              }}
                              className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                            >
                              <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                              Export Flow
                            </button>
                            {canManageFlows && flow.status !== 'active' && (
                              <button
                                onClick={() => {
                                  handleDelete(flow.flow_id);
                                  setOpenDropdownId(null);
                                }}
                                className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                              >
                                <TrashIcon className="h-4 w-4 mr-2" />
                                Delete
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Flows List - Desktop Table View */}
      <div className="mt-6 hidden md:block shadow ring-1 ring-black ring-opacity-5 rounded-lg">
        <div className="w-full">
          <table className="w-full min-w-0 divide-y divide-gray-300 table-fixed">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-2 py-1.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Flow
              </th>
              <th scope="col" className="px-1 py-1.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                Modified
              </th>
              {columnVisibility.scope && (
                <th scope="col" className="px-1 py-1.5 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-12">
                  Scope
                </th>
              )}
              {columnVisibility.category && (
                <th scope="col" className="px-1.5 py-1.5 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                  Category
                </th>
              )}
              {columnVisibility.trigger && (
                <th scope="col" className="px-1 py-1.5 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-10">
                  <span className="sr-only">Trigger</span>
                </th>
              )}
              <th scope="col" className="px-1 py-1.5 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-12">
                Status
              </th>
              <th scope="col" className="px-2 py-1.5 text-right w-32">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredFlows.length === 0 ? (
              <tr>
                <td colSpan="8" className="px-6 py-4 text-center text-gray-500">
                  No flows found
                </td>
              </tr>
            ) : (
              sortedFlows.map((flow) => (
                <tr key={flow.flow_id} className="hover:bg-gray-50 cursor-pointer" onDoubleClick={() => navigate(`/flows/${flow.flow_id}/edit`)}>
                  <td className="px-2 py-1.5 min-w-0">
                    <div className="min-w-0">
                      <div
                        className="text-sm font-medium text-gray-900 truncate cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Flow Name', flow.flow_name)}
                        onMouseLeave={handleMouseLeave}
                      >
                        {flow.flow_name}
                      </div>
                      {flow.description && (
                        <div
                          className="text-xs text-gray-500 truncate cursor-pointer hover:text-primary"
                          onMouseEnter={(e) => handleMouseEnter(e, 'Description', flow.description)}
                          onMouseLeave={handleMouseLeave}
                        >
                          {flow.description}
                        </div>
                      )}
                    </div>
                  </td>
                  <td
                    className="px-1 py-1.5 cursor-pointer"
                    onMouseEnter={(e) => {
                      const metadata = `Owner: ${flow.created_by_user?.email || flow.created_by || 'Unknown'}\nModified: ${formatDateTime(flow.updated_at || flow.created_at)}\nBy: ${flow.last_modified_by_user?.email || flow.last_modified_by || flow.created_by || 'Unknown'}`;
                      handleMouseEnter(e, 'Details', metadata);
                    }}
                    onMouseLeave={handleMouseLeave}
                  >
                    <div className="text-xs text-gray-600 truncate">{flow.created_by_user?.user_name || 'Unknown'}</div>
                    <div className="text-xs text-gray-400">{formatDate(flow.updated_at || flow.created_at)}</div>
                  </td>
                  {columnVisibility.scope && (
                    <td
                      className="px-1 py-1.5 text-center cursor-pointer"
                      onMouseEnter={(e) => handleMouseEnter(e, 'Scope', flow.flow_scope || 'user')}
                      onMouseLeave={handleMouseLeave}
                    >
                      {getScopeIcon(flow.flow_scope)}
                    </td>
                  )}
                  {columnVisibility.category && (
                    <td className="px-1.5 py-1.5">
                      <div
                        className="text-sm text-gray-900 truncate cursor-pointer hover:text-primary"
                        onMouseEnter={(e) => handleMouseEnter(e, 'Category', flow.category || 'No category')}
                        onMouseLeave={handleMouseLeave}
                      >
                        {flow.category || '-'}
                      </div>
                    </td>
                  )}
                  {columnVisibility.trigger && (
                    <td
                      className="px-1 py-1.5 text-center cursor-pointer"
                      onMouseEnter={(e) => handleMouseEnter(e, 'Trigger', flow.trigger_config?.type || 'manual')}
                      onMouseLeave={handleMouseLeave}
                    >
                      {getTriggerIcon(flow.trigger_config?.type)}
                    </td>
                  )}
                  <td
                    className="px-1 py-1.5 text-center cursor-pointer"
                    onMouseEnter={(e) => handleMouseEnter(e, 'Status', flow.status)}
                    onMouseLeave={handleMouseLeave}
                  >
                    {getStatusIcon(flow.status)}
                  </td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-right text-sm font-medium">
                    <div className="flex items-center justify-end gap-1.5">
                      {/* Primary action buttons with better spacing */}
                      {canActivateFlows && flow.status === 'draft' && (
                        <button
                          onClick={() => activateFlow(flow.flow_id)}
                          className="text-green-600 hover:text-green-900 p-1 hover:bg-green-50 rounded-lg transition-colors"
                          title={flow.trigger_config?.type === 'schedule' ? "Start Scheduler" : "Activate Flow"}
                        >
                          <PlayIcon className="h-5 w-5" />
                        </button>
                      )}
                      {canActivateFlows && flow.status === 'active' && (
                        <button
                          onClick={() => deactivateFlow(flow.flow_id)}
                          className="text-yellow-600 hover:text-yellow-900 p-1 hover:bg-yellow-50 rounded-lg transition-colors"
                          title={flow.trigger_config?.type === 'schedule' ? "Stop Scheduler" : "Deactivate Flow"}
                        >
                          <PauseIcon className="h-5 w-5" />
                        </button>
                      )}
                      {canActivateFlows && flow.status === 'inactive' && (
                        <button
                          onClick={() => activateFlow(flow.flow_id)}
                          className="text-green-600 hover:text-green-900 p-1 hover:bg-green-50 rounded-lg transition-colors"
                          title={flow.trigger_config?.type === 'schedule' ? "Restart Scheduler" : "Reactivate Flow"}
                        >
                          <PlayIcon className="h-5 w-5" />
                        </button>
                      )}

                      {/* Trigger button for draft/active flows */}
                      {(flow.status === 'draft' || flow.status === 'active') && (
                        <button
                          onClick={() => handleTriggerFlow(flow)}
                          className="text-purple-600 hover:text-purple-900 p-1 hover:bg-purple-50 rounded-lg transition-colors"
                          title="Trigger Flow"
                        >
                          <RocketLaunchIcon className="h-5 w-5" />
                        </button>
                      )}

                      {canManageFlows && (
                        <button
                          onClick={() => navigate(`/flows/${flow.flow_id}/edit`)}
                          className="text-primary hover:text-primary-dark p-1 hover:bg-primary-10 rounded-lg transition-colors"
                          title="Edit"
                        >
                          <PencilIcon className="h-5 w-5" />
                        </button>
                      )}

                      {/* Dropdown menu for secondary actions */}
                      <div className="relative dropdown-menu">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setOpenDropdownId(openDropdownId === flow.flow_id ? null : flow.flow_id);
                          }}
                          className="text-gray-600 hover:text-gray-900 p-1 hover:bg-gray-50 rounded-lg transition-colors"
                          title="More actions"
                        >
                          <EllipsisVerticalIcon className="h-5 w-5" />
                        </button>

                        {openDropdownId === flow.flow_id && (
                          <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg z-10 border border-gray-200">
                            <div className="py-1">
                              <button
                                onClick={() => {
                                  navigate(`/flows/${flow.flow_id}/api-docs`);
                                  setOpenDropdownId(null);
                                }}
                                className="flex items-center w-full px-4 py-2 text-sm text-primary hover:bg-primary-10"
                              >
                                <BookOpenIcon className="h-4 w-4 mr-2" />
                                API Documentation
                              </button>
                              <button
                                onClick={() => handleViewLastExecution(flow)}
                                className="flex items-center w-full px-4 py-2 text-sm text-blue-700 hover:bg-primary-10"
                              >
                                <DocumentTextIcon className="h-4 w-4 mr-2" />
                                Last Execution Log
                              </button>
                              {canManageFlows && (flow.status === 'active' || flow.status === 'inactive') && (
                                <button
                                  onClick={() => {
                                    cancelFlow(flow.flow_id);
                                    setOpenDropdownId(null);
                                  }}
                                  className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                >
                                  <XMarkIcon className="h-4 w-4 mr-2" />
                                  Cancel (to Draft)
                                </button>
                              )}
                              {canManageFlows && (
                                <>
                                  <button
                                    onClick={() => {
                                      handlePublishReusableApp(flow);
                                      setOpenDropdownId(null);
                                    }}
                                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                  >
                                    <CogIcon className="h-4 w-4 mr-2" />
                                    Publish as Reusable App
                                  </button>
                                  <button
                                    onClick={() => {
                                      handlePublishMicroSaasApp(flow);
                                      setOpenDropdownId(null);
                                    }}
                                    className="flex items-center w-full px-4 py-2 text-sm text-secondary hover:bg-secondary/10"
                                  >
                                    <ShoppingBagIcon className="h-4 w-4 mr-2" />
                                    Publish as Micro SaaS App
                                  </button>
                                  {isInstanceAdmin && (
                                    <button
                                      onClick={() => {
                                        handlePublishAsExample(flow);
                                        setOpenDropdownId(null);
                                      }}
                                      className="flex items-center w-full px-4 py-2 text-sm text-secondary hover:bg-secondary/10"
                                    >
                                      <AcademicCapIcon className="h-4 w-4 mr-2" />
                                      Publish as Example
                                    </button>
                                  )}
                                  <button
                                    onClick={() => {
                                      handleDuplicate(flow);
                                      setOpenDropdownId(null);
                                    }}
                                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                                  >
                                    <DocumentDuplicateIcon className="h-4 w-4 mr-2" />
                                    Duplicate
                                  </button>
                                </>
                              )}
                              <button
                                onClick={() => {
                                  handleExportFlow(flow);
                                  setOpenDropdownId(null);
                                }}
                                className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                              >
                                <ArrowDownTrayIcon className="h-4 w-4 mr-2" />
                                Export Flow
                              </button>
                              {canManageFlows && flow.status !== 'active' && (
                                <button
                                  onClick={() => {
                                    handleDelete(flow.flow_id);
                                    setOpenDropdownId(null);
                                  }}
                                  className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                                >
                                  <TrashIcon className="h-4 w-4 mr-2" />
                                  Delete
                                </button>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              ))
            )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Trigger Modal */}
      {showTriggerModal && selectedFlow && (
        <ManualTriggerModal
          flow={selectedFlow}
          onClose={() => {
            setShowTriggerModal(false);
            setSelectedFlow(null);
          }}
          onTrigger={handleTriggerSubmit}
        />
      )}

      {/* Flow Publishing Modal */}
      {showPublishingModal && publishingFlow && (
        <FlowPublishingModal
          isOpen={showPublishingModal}
          flowId={publishingFlow.flow_id}
          flowName={publishingFlow.flow_name}
          flowDescription={publishingFlow.description}
          publishType={publishType}
          onClose={() => {
            setShowPublishingModal(false);
            setPublishingFlow(null);
            setPublishType(null);
          }}
          onPublishSuccess={() => {
            setShowPublishingModal(false);
            setPublishingFlow(null);
            setPublishType(null);
            // Optionally refresh the published apps list
          }}
        />
      )}

      {/* Publish As Example Modal */}
      {showPublishAsExampleModal && flowToPublish && (
        <PublishAsExampleModal
          open={showPublishAsExampleModal}
          flow={flowToPublish}
          onClose={() => {
            setShowPublishAsExampleModal(false);
            setFlowToPublish(null);
          }}
          onPublish={handlePublishAsExampleSubmit}
          publishing={publishAsExampleMutation.isLoading}
        />
      )}

      {/* Execution Details Modal */}
      {showExecutionDetails && selectedExecution && (
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
                      setShowExecutionDetails(false);
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
                      </dl>
                    </div>

                    {/* Input Data Section */}
                    {executionDetails.trigger_data && Object.keys(executionDetails.trigger_data).length > 0 && (
                      <div>
                        <h4 className="text-base sm:text-lg font-medium text-gray-900 mb-2 sm:mb-3">Input Data</h4>
                        <div
                          className="bg-blue-50 border border-blue-200 rounded-lg p-3 sm:p-4 overflow-hidden cursor-help"
                          title="Click to copy full data to clipboard"
                          onClick={() => copyToClipboard(executionDetails.trigger_data)}
                        >
                          <pre className="text-xs overflow-x-auto text-blue-900 max-h-40 sm:max-h-60 select-none">
                            {JSON.stringify(executionDetails.trigger_data, null, 2)}
                          </pre>
                          {JSON.stringify(executionDetails.trigger_data).length > 500 && (
                            <p className="text-xs text-blue-600 mt-2">
                              Click to copy full data • {JSON.stringify(executionDetails.trigger_data).length} chars
                            </p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Activity Trace Section */}
                    <div className="mt-4 sm:mt-6">
                      <h4 className="text-base sm:text-lg font-medium text-gray-900 mb-2 sm:mb-3">Activity Trace</h4>

                      {/* Show loading indicator */}
                      {isLoadingLogs && allLogs.length === 0 && (
                        <div className="flex items-center justify-center py-8">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mr-3"></div>
                          <span className="text-gray-600">Loading execution logs...</span>
                        </div>
                      )}

                      {/* Show logs if available */}
                      {!isLoadingLogs && allLogs.length > 0 && (
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
                      )}

                      {/* Show message if no logs */}
                      {!isLoadingLogs && allLogs.length === 0 && (
                        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
                          <p className="text-gray-600">No execution logs available</p>
                          <p className="text-sm text-gray-500 mt-2">
                            This execution may not have generated any logs.
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
                          onClick={() => copyToClipboard(executionDetails.execution_data)}
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

export default Flows;