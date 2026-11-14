import React, { useState, useEffect } from 'react';
import {
  ServerIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  PlayIcon,
  InformationCircleIcon,
  ChevronRightIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  CogIcon
} from '@heroicons/react/24/outline';
import axios from 'axios';
import toast from 'react-hot-toast';
import MCPToolExecutor from '../components/mcp/MCPToolExecutor';
import MCPResponseViewer from '../components/mcp/MCPResponseViewer';
import { formatDateTime } from '../utils/dateFormatter';

const MCPServices = () => {
  const [tools, setTools] = useState([]);
  const [filteredTools, setFilteredTools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedTool, setSelectedTool] = useState(null);
  const [showExecutor, setShowExecutor] = useState(false);
  const [executionHistory, setExecutionHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Categories for filtering
  const categories = [
    { value: 'all', label: 'All Tools', icon: ServerIcon },
    { value: 'exploration', label: 'Exploration', icon: MagnifyingGlassIcon },
    { value: 'management', label: 'Management', icon: CogIcon },
    { value: 'testing', label: 'Testing', icon: PlayIcon },
    { value: 'deployment', label: 'Deployment', icon: ServerIcon },
    { value: 'documentation', label: 'Documentation', icon: InformationCircleIcon },
    { value: 'flow_design', label: 'Flow Design', icon: FunnelIcon },
    { value: 'flow_assistant', label: 'Flow Assistant', icon: FunnelIcon }
  ];

  useEffect(() => {
    fetchTools();
  }, []);

  useEffect(() => {
    filterTools();
  }, [tools, searchTerm, selectedCategory]);

  const fetchTools = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/mcp/tools');
      setTools(response.data);
    } catch (error) {
      console.error('Error fetching MCP tools:', error);
      toast.error('Failed to load MCP tools');
    } finally {
      setLoading(false);
    }
  };

  const filterTools = () => {
    let filtered = [...tools];

    // Filter by category
    if (selectedCategory !== 'all') {
      filtered = filtered.filter(tool => tool.category === selectedCategory);
    }

    // Filter by search term
    if (searchTerm) {
      const search = searchTerm.toLowerCase();
      filtered = filtered.filter(tool => 
        tool.name.toLowerCase().includes(search) ||
        tool.description?.toLowerCase().includes(search)
      );
    }

    setFilteredTools(filtered);
  };

  const handleExecuteTool = (tool) => {
    setSelectedTool(tool);
    setShowExecutor(true);
  };

  const handleExecutionComplete = (result) => {
    const historyEntry = {
      id: Date.now(),
      tool: selectedTool.name,
      timestamp: new Date().toISOString(),
      ...result
    };
    setExecutionHistory([historyEntry, ...executionHistory.slice(0, 19)]);
    // Don't close the modal - let the user see the response and close it manually
    // setShowExecutor(false);
    // setSelectedTool(null);
  };

  const getCategoryIcon = (category) => {
    const cat = categories.find(c => c.value === category);
    return cat ? cat.icon : ServerIcon;
  };

  const getParameterCount = (tool) => {
    if (!tool.parameters || !tool.parameters.properties) return 0;
    return Object.keys(tool.parameters.properties).length;
  };

  const getRequiredParameterCount = (tool) => {
    if (!tool.parameters || !tool.parameters.required) return 0;
    return tool.parameters.required.length;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">MCP Services</h1>
          <p className="mt-1 text-sm text-gray-500">
            Explore and test Model Context Protocol tools exposed through the MCP bridge
          </p>
        </div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="flex items-center px-4 py-2 bg-white border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <ClockIcon className="h-4 w-4 mr-2" />
          History ({executionHistory.length})
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <div className="relative">
              <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search tools..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
              />
            </div>
          </div>

          {/* Category Filter */}
          <div className="flex gap-2 flex-wrap">
            {categories.map(category => (
              <button
                key={category.value}
                onClick={() => setSelectedCategory(category.value)}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  selectedCategory === category.value
                    ? 'bg-primary-100 text-primary-900'
                    : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300'
                }`}
              >
                <category.icon className="inline h-4 w-4 mr-1" />
                {category.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tools Grid */}
      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      ) : filteredTools.length === 0 ? (
        <div className="bg-white shadow rounded-lg p-8 text-center">
          <ServerIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">No tools found</h3>
          <p className="mt-1 text-sm text-gray-500">
            {searchTerm || selectedCategory !== 'all' 
              ? 'Try adjusting your filters'
              : 'No MCP tools are available'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredTools.map(tool => {
            const CategoryIcon = getCategoryIcon(tool.category);
            const paramCount = getParameterCount(tool);
            const requiredCount = getRequiredParameterCount(tool);
            
            return (
              <div key={tool.name} className="bg-white shadow rounded-lg hover:shadow-lg transition-shadow">
                <div className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center">
                      <CategoryIcon className="h-8 w-8 text-primary" />
                      <div className="ml-3">
                        <h3 className="text-lg font-medium text-gray-900">
                          {tool.name}
                        </h3>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800 mt-1">
                          {tool.category}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <p className="mt-3 text-sm text-gray-600 line-clamp-2">
                    {tool.description}
                  </p>

                  <div className="mt-4 flex items-center justify-between">
                    <div className="text-sm text-gray-500">
                      {paramCount > 0 ? (
                        <span>
                          {requiredCount} required, {paramCount - requiredCount} optional params
                        </span>
                      ) : (
                        <span>No parameters</span>
                      )}
                    </div>
                    
                    <button
                      onClick={() => handleExecuteTool(tool)}
                      className="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
                    >
                      <PlayIcon className="h-4 w-4 mr-1" />
                      Test
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Execution History Panel */}
      {showHistory && executionHistory.length > 0 && (
        <div className="fixed right-0 top-0 h-full w-96 bg-white shadow-xl z-40 overflow-y-auto">
          <div className="sticky top-0 bg-white border-b px-4 py-3 flex items-center justify-between">
            <h3 className="text-lg font-medium">Execution History</h3>
            <button
              onClick={() => setShowHistory(false)}
              className="text-gray-400 hover:text-gray-500"
            >
              <XCircleIcon className="h-6 w-6" />
            </button>
          </div>
          <div className="p-4 space-y-3">
            {executionHistory.map(entry => (
              <div key={entry.id} className="border rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-sm">{entry.tool}</span>
                  {entry.success ? (
                    <CheckCircleIcon className="h-5 w-5 text-green-500" />
                  ) : (
                    <XCircleIcon className="h-5 w-5 text-red-500" />
                  )}
                </div>
                <div className="text-xs text-gray-500">
                  {formatDateTime(entry.timestamp)}
                </div>
                {entry.execution_time && (
                  <div className="text-xs text-gray-500 mt-1">
                    Execution time: {entry.execution_time.toFixed(2)}s
                  </div>
                )}
                {entry.error && (
                  <div className="mt-2 text-sm text-red-600">
                    {entry.error}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tool Executor Modal */}
      {showExecutor && selectedTool && (
        <MCPToolExecutor
          tool={selectedTool}
          onClose={() => {
            setShowExecutor(false);
            setSelectedTool(null);
          }}
          onExecute={handleExecutionComplete}
        />
      )}
    </div>
  );
};

export default MCPServices;