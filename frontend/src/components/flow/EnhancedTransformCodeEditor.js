import React, { useState, useCallback, useMemo, useEffect } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import { autocompletion } from '@codemirror/autocomplete';
import {
  VariableIcon,
  CodeBracketIcon,
  InformationCircleIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  SparklesIcon,
  BeakerIcon,
  PencilIcon,
  ChatBubbleLeftRightIcon,
  CogIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ClipboardDocumentIcon,
  TrashIcon,
  PlusIcon,
  ClockIcon,
  EyeIcon,
  EyeSlashIcon,
  DocumentTextIcon,
  DocumentIcon,
  ArrowPathIcon,
  CheckIcon,
  XMarkIcon
} from '@heroicons/react/24/outline';

const EnhancedTransformCodeEditor = ({
  value,
  onChange,
  availableVariables = {},
  placeholder = '',
  theme = 'light',
  flowContext = {},
  nodeContext = {},
  nextNodeInfo = {}
}) => {
  const [activeTab, setActiveTab] = useState('ai'); // Default to AI Assistant for better discoverability
  const [showVariablePanel, setShowVariablePanel] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState({
    input: true,
    loop: true,
    global: false,
    node_outputs: false
  });

  // AI Assistant state
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiResponse, setAiResponse] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState(null);
  const [aiSettings, setAiSettings] = useState(null);
  
  // Conversation history state
  const [conversationHistory, setConversationHistory] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [isFollowup, setIsFollowup] = useState(false);
  
  // System prompt editing state
  const [showSystemPromptEditor, setShowSystemPromptEditor] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState('');
  const [defaultSystemPrompt, setDefaultSystemPrompt] = useState('');
  const [customSystemPrompt, setCustomSystemPrompt] = useState('');
  const [systemPromptLoading, setSystemPromptLoading] = useState(false);
  const [systemPromptEdit, setSystemPromptEdit] = useState(false);
  const [systemPromptPreview, setSystemPromptPreview] = useState('');

  // Load AI settings on component mount
  useEffect(() => {
    loadAiSettings();
  }, []);

  // Load conversation history when flowContext or nodeContext changes
  useEffect(() => {
    const nodeId = nodeContext?.id || nodeContext?.nodeId || nodeContext?.data?.id;
    console.log('🔄 useEffect triggered for conversation loading', { 
      flowContext, 
      nodeContext,
      flowId: flowContext?.flowId,
      nodeId: nodeId
    });
    loadConversationHistory();
  }, [flowContext?.flowId, nodeContext?.id, nodeContext?.nodeId, nodeContext?.data?.id]);

  const loadConversationHistory = async () => {
    // Try multiple possible node ID sources
    const nodeId = nodeContext?.id || nodeContext?.nodeId || nodeContext?.data?.id;
    
    console.log('🔍 loadConversationHistory called', { 
      flowId: flowContext?.flowId, 
      nodeId: nodeId,
      'nodeContext?.id': nodeContext?.id,
      'nodeContext?.nodeId': nodeContext?.nodeId,
      'nodeContext?.data?.id': nodeContext?.data?.id,
      flowContext, 
      nodeContext 
    });
    
    if (!flowContext?.flowId || !nodeId) {
      console.log('❌ Missing flowId or nodeId, skipping conversation load', {
        hasFlowId: !!flowContext?.flowId,
        hasNodeId: !!nodeId,
        flowId: flowContext?.flowId,
        nodeId: nodeId
      });
      return;
    }
    
    try {
      const url = `/api/v1/ai-settings/conversations/${flowContext.flowId}/${nodeId}`;
      console.log('📡 Fetching conversations from:', url);
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      console.log('📡 Response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('✅ Conversation data received:', data);
        
        // Load the most recent active conversation if any
        if (data.conversations && data.conversations.length > 0) {
          const mostRecent = data.conversations[0];
          console.log('🔄 Loading most recent conversation:', mostRecent.conversation_id);
          setCurrentConversationId(mostRecent.conversation_id);
          await loadFullConversationHistory(mostRecent.conversation_id);
        } else {
          console.log('📝 No conversations found for this node');
        }
      } else {
        const errorText = await response.text();
        console.error('❌ Response not ok:', response.status, errorText);
      }
    } catch (error) {
      console.error('❌ Failed to load conversation history:', error);
    }
  };

  const loadFullConversationHistory = async (conversationId) => {
    console.log('🔄 loadFullConversationHistory called for:', conversationId);
    
    try {
      const url = `/api/v1/ai-settings/conversation/${conversationId}`;
      console.log('📡 Fetching full history from:', url);
      
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      
      console.log('📡 Full history response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('✅ Full conversation history received:', data);
        console.log('📝 Messages count:', data.messages?.length || 0);
        
        setConversationHistory(data.messages || []);
        console.log('✅ Conversation history state updated');
        
        // Auto-show history if there are messages
        if (data.messages && data.messages.length > 0) {
          setShowHistory(true);
          console.log('✅ Auto-showing conversation history');
        }
      } else {
        const errorText = await response.text();
        console.error('❌ Failed to load full history:', response.status, errorText);
      }
    } catch (error) {
      console.error('❌ Exception in loadFullConversationHistory:', error);
    }
  };

  const loadAiSettings = async () => {
    try {
      const response = await fetch('/api/v1/ai-settings/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });
      if (response.ok) {
        const settings = await response.json();
        setAiSettings(settings);
      }
    } catch (error) {
      console.error('Failed to load AI settings:', error);
    }
  };

  const loadSystemPrompt = async () => {
    if (!aiSettings) return;
    
    setSystemPromptLoading(true);
    try {
      const response = await fetch('/api/v1/ai-settings/system-prompt/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          input_schema: {},
          available_variables: availableVariables,
          flow_context: flowContext,
          next_node_info: nextNodeInfo
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        setDefaultSystemPrompt(data.system_prompt);
        setSystemPromptPreview(customSystemPrompt || data.system_prompt);
        setSystemPromptEdit(true);
      } else {
        console.error('Failed to load system prompt');
      }
    } catch (error) {
      console.error('Error loading system prompt:', error);
    } finally {
      setSystemPromptLoading(false);
    }
  };

  const resetSystemPrompt = () => {
    setCustomSystemPrompt('');
    setSystemPromptPreview(defaultSystemPrompt);
  };

  const saveCustomSystemPrompt = () => {
    setCustomSystemPrompt(systemPromptPreview);
    setSystemPromptEdit(false);
  };

  const cancelSystemPromptEdit = () => {
    setSystemPromptPreview(customSystemPrompt || defaultSystemPrompt);
    setSystemPromptEdit(false);
  };

  const generateAiCode = async () => {
    if (!aiPrompt.trim()) return;
    
    setAiLoading(true);
    setAiError(null);
    setAiResponse(null);

    try {
      const endpoint = currentConversationId && isFollowup 
        ? '/api/v1/ai-settings/conversation/followup'
        : '/api/v1/ai-settings/conversation';
      
      const requestBody = currentConversationId && isFollowup 
        ? {
            conversation_id: currentConversationId,
            followup_prompt: aiPrompt
          }
        : {
            flow_id: flowContext?.flowId || 'unknown',
            node_id: nodeContext?.id || nodeContext?.nodeId || nodeContext?.data?.id || 'unknown',
            prompt: aiPrompt,
            flow_name: flowContext?.flowName || 'Unknown Flow',
            node_name: nodeContext?.label || 'Transform Node',
            input_schema: availableVariables.input || {},
            available_variables: availableVariables,
            flow_context: {
              flow_name: flowContext.flowName || 'Unknown Flow',
              node_name: nodeContext.label || 'Transform Node',
              description: nodeContext.description || ''
            },
            next_node_info: nextNodeInfo,
            custom_system_prompt: customSystemPrompt || null
          };

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(requestBody)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to generate code');
      }

      const result = await response.json();
      
      // Update conversation state
      setCurrentConversationId(result.conversation_id);
      setConversationHistory(result.conversation_history);
      setAiResponse({
        generated_code: result.generated_code,
        explanation: result.explanation,
        warnings: result.warnings,
        test_cases: result.test_cases,
        message_id: result.message_id
      });
      
      // Clear prompt for next interaction
      setAiPrompt('');
      setIsFollowup(true); // Next prompt will be a followup
      
    } catch (error) {
      setAiError(error.message);
    } finally {
      setAiLoading(false);
    }
  };

  const applyAiCode = async () => {
    if (aiResponse && aiResponse.generated_code) {
      onChange(aiResponse.generated_code);
      setActiveTab('code'); // Switch to code tab to show the result
      
      // Mark code as applied in conversation
      if (aiResponse.message_id) {
        try {
          await fetch('/api/v1/ai-settings/conversation/apply-code', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
              message_id: aiResponse.message_id
            })
          });
        } catch (error) {
          console.error('Failed to mark code as applied:', error);
        }
      }
    }
  };

  const clearConversationHistory = async () => {
    if (!currentConversationId) return;
    
    try {
      const response = await fetch('/api/v1/ai-settings/conversation/clear', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          conversation_id: currentConversationId
        })
      });
      
      if (response.ok) {
        setConversationHistory([]);
        setCurrentConversationId(null);
        setIsFollowup(false);
        setAiResponse(null);
      }
    } catch (error) {
      console.error('Failed to clear conversation history:', error);
    }
  };

  const startNewConversation = () => {
    setConversationHistory([]);
    setCurrentConversationId(null);
    setIsFollowup(false);
    setAiResponse(null);
    setAiPrompt('');
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
  };

  // Create autocomplete suggestions from available variables
  const createCompletions = useCallback(() => {
    const completions = [];
    
    // Add built-in objects
    completions.push(
      { label: 'input', type: 'variable', info: 'Data from previous node' },
      { label: 'local', type: 'variable', info: 'Local variables dictionary' },
      { label: 'global', type: 'variable', info: 'Global flow variables' },
      { label: 'node_outputs', type: 'variable', info: 'Outputs from all nodes' },
      { label: 'output', type: 'variable', info: 'Set your return value here' },
    );
    
    // Add loop object if inside a loop
    if (availableVariables.loop) {
      completions.push(
        { label: 'loop', type: 'variable', info: 'Loop iteration variables' }
      );
    }

    // Add functions
    completions.push(
      { label: 'set_global', type: 'function', info: 'Set a global variable', apply: 'set_global("", )' },
      { label: 'string["upper"]', type: 'function', info: 'Convert to uppercase' },
      { label: 'string["lower"]', type: 'function', info: 'Convert to lowercase' },
      { label: 'string["split"]', type: 'function', info: 'Split string' },
      { label: 'string["join"]', type: 'function', info: 'Join strings' },
      { label: 'string["replace"]', type: 'function', info: 'Replace in string' },
      { label: 'math["add"]', type: 'function', info: 'Add numbers' },
      { label: 'math["subtract"]', type: 'function', info: 'Subtract numbers' },
      { label: 'math["multiply"]', type: 'function', info: 'Multiply numbers' },
      { label: 'math["divide"]', type: 'function', info: 'Divide numbers' },
      { label: 'math["power"]', type: 'function', info: 'Power operation' },
      { label: 'math["sqrt"]', type: 'function', info: 'Square root' },
    );

    // Add variable paths from availableVariables
    if (availableVariables.input) {
      Object.keys(availableVariables.input).forEach(key => {
        if (key !== '_description') {
          completions.push({
            label: `input.get('${key}')`,
            type: 'variable',
            info: availableVariables.input[key] || key
          });
        }
      });
    }
    
    // Add loop variable completions if inside a loop
    if (availableVariables.loop) {
      Object.keys(availableVariables.loop).forEach(key => {
        if (key !== '_description') {
          completions.push({
            label: `loop['${key}']`,
            type: 'variable',
            info: availableVariables.loop[key] || key
          });
        }
      });
    }

    if (availableVariables.global) {
      Object.keys(availableVariables.global).forEach(key => {
        if (key !== '_description' && key !== '[any_variable]') {
          completions.push({
            label: `global.get('${key}')`,
            type: 'variable',
            info: availableVariables.global[key] || key
          });
        }
      });
    }

    if (availableVariables.node_outputs) {
      Object.keys(availableVariables.node_outputs).forEach(nodeId => {
        completions.push({
          label: `node_outputs['${nodeId}']`,
          type: 'variable',
          info: `Output from ${nodeId}`
        });
      });
    }

    return completions;
  }, [availableVariables]);

  // Custom autocomplete function
  const myCompletions = useCallback((context) => {
    let word = context.matchBefore(/\w*/);
    if (word.from === word.to && !context.explicit) return null;
    
    return {
      from: word.from,
      options: createCompletions()
    };
  }, [createCompletions]);

  // Extensions for CodeMirror
  const extensions = useMemo(() => [
    python(),
    autocompletion({ override: [myCompletions] })
  ], [myCompletions]);

  // Toggle category expansion
  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };

  // Insert variable at cursor
  const insertVariable = (variable) => {
    onChange(value + (value ? '\n' : '') + variable);
  };

  // Helper function to render nested node output structure
  const renderNodeOutputStructure = (obj, path, depth) => {
    if (!obj || typeof obj !== 'object' || depth > 5) return null;
    
    return Object.entries(obj).filter(([key]) => !key.startsWith('_')).map(([key, value]) => {
      const fullPath = /^\d+$/.test(key) ? `${path}['${key}']` : `${path}['${key}']`;
      
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        return (
          <div key={key} className="mb-1">
            <button
              onClick={() => toggleCategory(`${path}_${key}`)}
              className="flex items-center text-xs text-gray-600 hover:text-gray-800"
            >
              {expandedCategories[`${path}_${key}`] ? <ChevronDownIcon className="w-3 h-3 mr-1" /> : <ChevronRightIcon className="w-3 h-3 mr-1" />}
              {key}
            </button>
            {expandedCategories[`${path}_${key}`] && (
              <div className="ml-3 mt-1">
                {renderNodeOutputStructure(value, fullPath, depth + 1)}
              </div>
            )}
          </div>
        );
      } else {
        return (
          <div key={key} className="flex items-center justify-between py-0.5">
            <span className="text-xs text-gray-600">
              {key}: <span className="text-gray-500">{typeof value === 'string' ? value : typeof value}</span>
            </span>
            <button
              onClick={() => insertVariable(fullPath)}
              className="text-xs text-blue-600 hover:text-blue-800 ml-2"
            >
              Insert
            </button>
          </div>
        );
      }
    });
  };

  // AI Assistant Tab Content
  const renderAiAssistantTab = () => (
    <div className="space-y-4">
      {/* AI Settings Status */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <CogIcon className="w-5 h-5 text-gray-500" />
            <span className="text-sm font-medium">AI Configuration</span>
          </div>
          {aiSettings?.has_api_key ? (
            <div className="flex items-center space-x-2 text-green-600">
              <CheckCircleIcon className="w-4 h-4" />
              <span className="text-xs">{aiSettings.provider} ({aiSettings.model_name})</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2 text-amber-600">
              <ExclamationTriangleIcon className="w-4 h-4" />
              <span className="text-xs">Not configured</span>
            </div>
          )}
        </div>
        {!aiSettings?.has_api_key && (
          <div className="mt-2 text-xs text-gray-600">
            Configure your AI settings in the user profile to use this feature.
          </div>
        )}
      </div>

      {/* Conversation Controls */}
      <div className="bg-blue-50 p-4 rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <ChatBubbleLeftRightIcon className="w-5 h-5 text-blue-500" />
            <span className="text-sm font-medium text-blue-900">Conversation</span>
          </div>
          <div className="flex space-x-2">
            <button
              onClick={loadConversationHistory}
              className="flex items-center space-x-1 text-xs text-gray-600 hover:text-gray-800"
              title="Refresh conversation history"
            >
              <span>↻</span>
              <span>Refresh</span>
            </button>
            {conversationHistory.length > 0 && (
              <>
                <button
                  onClick={() => setShowHistory(!showHistory)}
                  className="flex items-center space-x-1 text-xs text-blue-600 hover:text-blue-800"
                >
                  {showHistory ? <EyeSlashIcon className="w-4 h-4" /> : <EyeIcon className="w-4 h-4" />}
                  <span>{showHistory ? 'Hide' : 'Show'} History</span>
                </button>
                <button
                  onClick={startNewConversation}
                  className="flex items-center space-x-1 text-xs text-green-600 hover:text-green-800"
                >
                  <PlusIcon className="w-4 h-4" />
                  <span>New</span>
                </button>
                <button
                  onClick={clearConversationHistory}
                  className="flex items-center space-x-1 text-xs text-red-600 hover:text-red-800"
                >
                  <TrashIcon className="w-4 h-4" />
                  <span>Clear</span>
                </button>
              </>
            )}
          </div>
        </div>
        <div className="text-xs text-blue-800">
          {conversationHistory.length > 0 ? (
            <div className="flex items-center space-x-2">
              <ClockIcon className="w-4 h-4" />
              <span>{conversationHistory.length} messages in conversation</span>
              {isFollowup && <span className="text-blue-600">(follow-up mode)</span>}
            </div>
          ) : (
            <div>
              <span>Start a new AI conversation for this transform node</span>
              <div className="text-xs text-gray-500 mt-1">
                Flow: {flowContext?.flowId || 'not set'} | Node: {nodeContext?.id || nodeContext?.nodeId || nodeContext?.data?.id || 'not set'}
              </div>
            </div>
          )}
          {/* Debug info - remove this later */}
          <div className="text-xs text-gray-400 mt-2 p-2 bg-gray-100 rounded">
            DEBUG: showHistory={showHistory ? 'true' : 'false'} | 
            conversationHistory.length={conversationHistory.length} | 
            currentConversationId={currentConversationId || 'null'}
          </div>
        </div>
      </div>

      {/* System Prompt Editor */}
      <div className="bg-purple-50 p-4 rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <DocumentTextIcon className="w-5 h-5 text-purple-500" />
            <span className="text-sm font-medium text-purple-900">System Prompt</span>
          </div>
          <div className="flex space-x-2">
            {!systemPromptEdit ? (
              <>
                <button
                  onClick={loadSystemPrompt}
                  className="flex items-center space-x-1 text-xs text-purple-600 hover:text-purple-800"
                  disabled={systemPromptLoading}
                >
                  {systemPromptLoading ? (
                    <div className="w-3 h-3 border border-purple-300 border-t-purple-600 rounded-full animate-spin"></div>
                  ) : (
                    <DocumentIcon className="w-4 h-4" />
                  )}
                  <span>View/Edit</span>
                </button>
                {customSystemPrompt && (
                  <button
                    onClick={resetSystemPrompt}
                    className="flex items-center space-x-1 text-xs text-gray-600 hover:text-gray-800"
                    title="Reset to default prompt"
                  >
                    <ArrowPathIcon className="w-4 h-4" />
                    <span>Reset</span>
                  </button>
                )}
              </>
            ) : (
              <>
                <button
                  onClick={saveCustomSystemPrompt}
                  className="flex items-center space-x-1 text-xs text-green-600 hover:text-green-800"
                >
                  <CheckIcon className="w-4 h-4" />
                  <span>Save</span>
                </button>
                <button
                  onClick={cancelSystemPromptEdit}
                  className="flex items-center space-x-1 text-xs text-gray-600 hover:text-gray-800"
                >
                  <XMarkIcon className="w-4 h-4" />
                  <span>Cancel</span>
                </button>
              </>
            )}
          </div>
        </div>
        
        <div className="text-xs text-purple-800 mb-2">
          {customSystemPrompt ? (
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-purple-400 rounded-full"></div>
              <span>Using custom system prompt</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-gray-400 rounded-full"></div>
              <span>Using default system prompt</span>
            </div>
          )}
        </div>

        {systemPromptEdit && (
          <div className="space-y-3">
            <div className="bg-white p-3 rounded border">
              <label className="block text-xs font-medium text-gray-700 mb-2">
                System Prompt ({systemPromptPreview.length} characters)
              </label>
              <textarea
                value={systemPromptPreview}
                onChange={(e) => setSystemPromptPreview(e.target.value)}
                className="w-full h-40 text-xs border border-gray-300 rounded p-2 font-mono resize-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                placeholder="Enter custom system prompt or leave empty to use default..."
              />
            </div>
            
            {defaultSystemPrompt && (
              <div className="bg-gray-50 p-3 rounded">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-medium text-gray-700">
                    Default Prompt Preview ({defaultSystemPrompt.length} characters)
                  </label>
                  <button
                    onClick={() => setSystemPromptPreview(defaultSystemPrompt)}
                    className="text-xs text-purple-600 hover:text-purple-800"
                  >
                    Copy to editor
                  </button>
                </div>
                <div className="text-xs text-gray-600 max-h-32 overflow-y-auto font-mono bg-white p-2 rounded border">
                  {defaultSystemPrompt.substring(0, 500)}
                  {defaultSystemPrompt.length > 500 && '...'}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Conversation History */}
      {showHistory && conversationHistory.length > 0 && (
        <div className="bg-gray-50 p-4 rounded-lg max-h-80 overflow-y-auto">
          <h4 className="text-sm font-medium text-gray-900 mb-3">
            Conversation History ({conversationHistory.length} messages)
          </h4>
          <div className="space-y-3">
            {conversationHistory.map((message, index) => (
              <div key={message.message_id} className={`p-3 rounded ${
                message.message_type === 'user_prompt' 
                  ? 'bg-blue-100 border-l-4 border-blue-500' 
                  : 'bg-green-100 border-l-4 border-green-500'
              }`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-gray-600">
                    {message.message_type === 'user_prompt' ? 'You' : 'AI Assistant'} 
                    - #{message.sequence_number}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(message.created_at).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-sm text-gray-800 whitespace-pre-wrap">
                  {message.content}
                </div>
                {message.message_type === 'ai_response' && message.generated_code && (
                  <div className="mt-2">
                    <div className="text-xs text-gray-600 mb-1 flex items-center justify-between">
                      <span>Generated Code:</span>
                      <div className="flex items-center space-x-2">
                        {message.was_applied && (
                          <span className="text-green-600 text-xs">✓ Applied</span>
                        )}
                        <button
                          onClick={() => copyToClipboard(message.generated_code)}
                          className="text-gray-500 hover:text-gray-700"
                        >
                          <ClipboardDocumentIcon className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                    <pre className="text-xs bg-gray-800 text-gray-100 p-2 rounded overflow-x-auto max-h-32">
                      <code>{message.generated_code}</code>
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Context Display */}
      <div className="bg-blue-50 p-4 rounded-lg">
        <h4 className="text-sm font-medium text-blue-900 mb-2">Available Context</h4>
        <div className="text-xs text-blue-800 space-y-1">
          <div>• Flow: {flowContext.flowName || 'Unknown'}</div>
          <div>• Node: {nodeContext.label || 'Transform Node'}</div>
          <div>• Input fields: {Object.keys(availableVariables.input || {}).length}</div>
          {availableVariables.loop && (
            <div className="bg-purple-100 rounded px-2 py-1">
              • Loop variables: {Object.keys(availableVariables.loop || {}).filter(k => k !== '_description').length} (inside loop iteration)
            </div>
          )}
          <div>• Global variables: {Object.keys(availableVariables.global || {}).length}</div>
          <div>• Previous nodes: {(() => {
            const nodeOutputs = availableVariables.node_outputs || {};
            const count = Object.keys(nodeOutputs).length;
            
            if (count === 0) {
              return "None (no previous nodes to get data from)";
            } else {
              const nodeIds = Object.keys(nodeOutputs);
              return `${count} (${nodeIds.join(', ')})`;
            }
          })()}</div>
          <div>• Next nodes: {(() => {
            const nextNodes = nextNodeInfo.nextNodes || [];
            if (nextNodes.length === 0) {
              return "None (this transform output won't be used by other nodes)";
            } else {
              const nodeLabels = nextNodes.map(node => `${node.label} (${node.type})`);
              return `${nextNodes.length} (${nodeLabels.join(', ')})`;
            }
          })()}</div>
        </div>
      </div>

      {/* AI Prompt Input */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          {isFollowup ? 'Follow-up prompt:' : 'Describe your transformation in natural language:'}
        </label>
        <textarea
          value={aiPrompt}
          onChange={(e) => setAiPrompt(e.target.value)}
          placeholder={isFollowup 
            ? "Example: Make the code more efficient, add error handling, change the output format..."
            : "Example: Convert to, subject, body and attachments to Gmail RFC 2822 format with base64 encoding"
          }
          className="w-full h-24 p-3 border border-gray-300 rounded-lg text-sm resize-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          disabled={!aiSettings?.has_api_key}
        />
        {isFollowup && (
          <div className="text-xs text-blue-600 bg-blue-50 p-2 rounded">
            💡 This will be a follow-up to your previous conversation. The AI will consider all previous exchanges when generating the response.
          </div>
        )}
      </div>

      {/* Generate Button */}
      <button
        onClick={generateAiCode}
        disabled={!aiPrompt.trim() || aiLoading || !aiSettings?.has_api_key}
        className="w-full flex items-center justify-center space-x-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium"
      >
        {aiLoading ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
            <span>Generating...</span>
          </>
        ) : (
          <>
            <SparklesIcon className="w-4 h-4" />
            <span>{isFollowup ? 'Continue Conversation' : 'Generate Transform Code'}</span>
          </>
        )}
      </button>

      {/* AI Error */}
      {aiError && (
        <div className="bg-red-50 border border-red-200 p-4 rounded-lg">
          <div className="flex items-start space-x-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-red-500 mt-0.5" />
            <div className="text-sm text-red-700">{aiError}</div>
          </div>
        </div>
      )}

      {/* AI Response */}
      {aiResponse && (
        <div className="space-y-4">
          {/* Explanation */}
          <div className="bg-green-50 border border-green-200 p-4 rounded-lg">
            <h4 className="text-sm font-medium text-green-900 mb-2">Explanation</h4>
            <p className="text-sm text-green-800">{aiResponse.explanation}</p>
          </div>

          {/* Generated Code */}
          <div className="bg-gray-50 border border-gray-200 p-4 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium text-gray-900">Generated Code</h4>
              <button
                onClick={() => copyToClipboard(aiResponse.generated_code)}
                className="flex items-center space-x-1 text-xs text-gray-600 hover:text-gray-800"
              >
                <ClipboardDocumentIcon className="w-4 h-4" />
                <span>Copy</span>
              </button>
            </div>
            <pre className="text-xs bg-gray-800 text-gray-100 p-3 rounded overflow-x-auto">
              <code>{aiResponse.generated_code}</code>
            </pre>
          </div>

          {/* Apply Button */}
          <button
            onClick={applyAiCode}
            className="w-full flex items-center justify-center space-x-2 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            <CheckCircleIcon className="w-4 h-4" />
            <span>Apply This Code</span>
          </button>

          {/* Warnings */}
          {aiResponse.warnings && aiResponse.warnings.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 p-4 rounded-lg">
              <h4 className="text-sm font-medium text-amber-900 mb-2">Warnings</h4>
              <ul className="text-sm text-amber-800 space-y-1">
                {aiResponse.warnings.map((warning, index) => (
                  <li key={index} className="flex items-start space-x-2">
                    <span>•</span>
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );

  // Example snippets (for Code tab)
  const snippets = [
    {
      name: 'Basic transformation',
      code: `# Basic data transformation
output['message'] = f"Hello, {input.get('name', 'World')}!"
output['processed'] = True
output['count'] = len(input.get('items', []))`
    },
    {
      name: 'Loop through items',
      code: `# Process list of items
local['items'] = input.get('items', [])
local['processed'] = []

for item in local['items']:
    local['processed'].append({
        'id': item.get('id'),
        'name': string['upper'](item.get('name', '')),
        'processed': True
    })

output['items'] = local['processed']
output['count'] = len(local['processed'])`
    },
    {
      name: 'Gmail RFC 2822 Format',
      code: `# Convert email fields to Gmail RFC 2822 format
import base64
import uuid

# Generate unique boundary for multipart message
local['boundary'] = f"boundary_{str(uuid.uuid4()).replace('-', '')}"

# Build email headers
local['headers'] = []
local['headers'].append(f"To: {input.get('to', '')}")
local['headers'].append(f"Subject: {input.get('subject', '')}")
local['headers'].append(f"From: {global.get('user_email', 'user@example.com')}")
local['headers'].append(f"Content-Type: multipart/mixed; boundary=\\"{local['boundary']}\\"")
local['headers'].append("")

# Build message body
local['body_parts'] = []
local['body_parts'].append(f"--{local['boundary']}")
local['body_parts'].append("Content-Type: text/plain; charset=UTF-8")
local['body_parts'].append("")
local['body_parts'].append(input.get('body', ''))

# Handle attachments
for attachment in input.get('attachments', []):
    local['body_parts'].append(f"--{local['boundary']}")
    local['body_parts'].append(f"Content-Type: {attachment.get('mime_type', 'application/octet-stream')}")
    local['body_parts'].append(f"Content-Disposition: attachment; filename=\\"{attachment.get('filename', 'file')}\\"")
    local['body_parts'].append("Content-Transfer-Encoding: base64")
    local['body_parts'].append("")
    local['body_parts'].append(attachment.get('content', ''))

# Close multipart message
local['body_parts'].append(f"--{local['boundary']}--")

# Combine all parts
local['full_message'] = string['join']('\\r\\n', local['headers'] + local['body_parts'])

# Base64 encode for Gmail API
local['encoded_message'] = base64.b64encode(local['full_message'].encode('utf-8')).decode('ascii')

# Output for Gmail API
output['raw'] = local['encoded_message']`
    }
  ];

  return (
    <div className="enhanced-transform-code-editor">
      {/* Tab Navigation */}
      <div className="mb-4 border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('ai')}
            className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
              activeTab === 'ai'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <SparklesIcon className="w-4 h-4" />
            <span>AI Assistant</span>
          </button>
          
          <button
            onClick={() => setActiveTab('code')}
            className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
              activeTab === 'code'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <CodeBracketIcon className="w-4 h-4" />
            <span>Code Editor</span>
          </button>
          
          <button
            onClick={() => setActiveTab('visual')}
            className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
              activeTab === 'visual'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <BeakerIcon className="w-4 h-4" />
            <span>Visual Builder</span>
            <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded">Coming Soon</span>
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {activeTab === 'ai' && renderAiAssistantTab()}
        
        {activeTab === 'code' && (
          <div>
            <div className="mb-2 flex justify-between items-center">
              <div className="flex items-center space-x-2">
                <CodeBracketIcon className="w-5 h-5 text-gray-500" />
                <span className="text-sm font-medium text-gray-700">Transform Script</span>
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => setShowVariablePanel(!showVariablePanel)}
                  className="text-sm text-blue-600 hover:text-blue-800 flex items-center"
                >
                  <VariableIcon className="w-4 h-4 mr-1" />
                  {showVariablePanel ? 'Hide' : 'Show'} Variables
                </button>
              </div>
            </div>

            <div className="flex space-x-4">
              {/* Code Editor */}
              <div className="flex-1">
                <div className="border rounded-lg overflow-hidden">
                  <CodeMirror
                    value={value}
                    height="400px"
                    theme={theme === 'dark' ? oneDark : undefined}
                    extensions={extensions}
                    onChange={onChange}
                    placeholder={placeholder}
                  />
                </div>

                {/* Snippets */}
                <div className="mt-3">
                  <div className="text-xs text-gray-600 mb-2">Quick snippets:</div>
                  <div className="flex flex-wrap gap-2">
                    {snippets.map((snippet, index) => (
                      <button
                        key={index}
                        onClick={() => onChange(snippet.code)}
                        className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
                      >
                        {snippet.name}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Variable Panel */}
              {showVariablePanel && (
                <div className="w-80 border rounded-lg p-4 bg-gray-50">
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Available Variables</h4>
                  
                  {/* Loop Variables - Show only if inside a loop */}
                  {availableVariables.loop && Object.keys(availableVariables.loop).filter(key => key !== '_description').length > 0 && (
                    <div className="mb-3">
                      <button
                        onClick={() => toggleCategory('loop')}
                        className="flex items-center text-sm font-medium text-purple-700 mb-1 hover:text-purple-900"
                      >
                        {expandedCategories.loop ? <ChevronDownIcon className="w-4 h-4 mr-1" /> : <ChevronRightIcon className="w-4 h-4 mr-1" />}
                        Loop Variables
                        <span className="ml-2 text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded">Inside Loop</span>
                      </button>
                      {expandedCategories.loop && (
                        <div className="ml-5 space-y-1 bg-purple-50 p-2 rounded">
                          <div className="text-xs text-purple-600 italic mb-2">Available inside loop iteration</div>
                          {Object.entries(availableVariables.loop || {}).map(([key, desc]) => (
                            key !== '_description' && (
                              <div key={key} className="flex items-center justify-between py-1">
                                <div>
                                  <span className="text-xs font-medium text-purple-700">{key}</span>
                                  <span className="text-xs text-gray-600 ml-2">- {desc}</span>
                                </div>
                                <button
                                  onClick={() => insertVariable(`loop['${key}']`)}
                                  className="text-xs text-purple-600 hover:text-purple-800"
                                >
                                  Insert
                                </button>
                              </div>
                            )
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Input Variables */}
                  <div className="mb-3">
                    <button
                      onClick={() => toggleCategory('input')}
                      className="flex items-center text-sm font-medium text-gray-700 mb-1 hover:text-gray-900"
                    >
                      {expandedCategories.input ? <ChevronDownIcon className="w-4 h-4 mr-1" /> : <ChevronRightIcon className="w-4 h-4 mr-1" />}
                      Input Variables
                    </button>
                    {expandedCategories.input && (
                      <div className="ml-5 space-y-1">
                        {renderNodeOutputStructure(availableVariables.input || {}, 'input', 0)}
                      </div>
                    )}
                  </div>

                  {/* Global Variables */}
                  <div className="mb-3">
                    <button
                      onClick={() => toggleCategory('global')}
                      className="flex items-center text-sm font-medium text-gray-700 mb-1 hover:text-gray-900"
                    >
                      {expandedCategories.global ? <ChevronDownIcon className="w-4 h-4 mr-1" /> : <ChevronRightIcon className="w-4 h-4 mr-1" />}
                      Global Variables
                    </button>
                    {expandedCategories.global && (
                      <div className="ml-5 space-y-1">
                        <div className="text-xs text-gray-500 italic mb-1">Set by transform nodes</div>
                        {Object.entries(availableVariables.global || {}).map(([key, desc]) => (
                          key !== '_description' && key !== '[any_variable]' && (
                            <div key={key} className="flex items-center justify-between">
                              <span className="text-xs text-gray-600">{key}</span>
                              <button
                                onClick={() => insertVariable(`global.get('${key}')`)}
                                className="text-xs text-blue-600 hover:text-blue-800"
                              >
                                Insert
                              </button>
                            </div>
                          )
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Node Outputs */}
                  <div className="mb-3">
                    <button
                      onClick={() => toggleCategory('node_outputs')}
                      className="flex items-center text-sm font-medium text-gray-700 mb-1 hover:text-gray-900"
                    >
                      {expandedCategories.node_outputs ? <ChevronDownIcon className="w-4 h-4 mr-1" /> : <ChevronRightIcon className="w-4 h-4 mr-1" />}
                      Node Outputs
                    </button>
                    {expandedCategories.node_outputs && (
                      <div className="ml-5 space-y-2">
                        {Object.entries(availableVariables.node_outputs || {}).map(([nodeId, nodeData]) => (
                          <div key={nodeId} className="border-l-2 border-gray-200 pl-2">
                            <button
                              onClick={() => toggleCategory(`node_${nodeId}`)}
                              className="flex items-center text-xs font-medium text-gray-700 hover:text-gray-900"
                            >
                              {expandedCategories[`node_${nodeId}`] ? <ChevronDownIcon className="w-3 h-3 mr-1" /> : <ChevronRightIcon className="w-3 h-3 mr-1" />}
                              {nodeId}
                            </button>
                            {expandedCategories[`node_${nodeId}`] && (
                              <div className="ml-3 mt-1 space-y-1">
                                {renderNodeOutputStructure(nodeData, `node_outputs['${nodeId}']`, 0)}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Built-in Functions */}
                  <div className="mt-4 p-3 bg-white rounded border">
                    <h5 className="text-xs font-semibold text-gray-700 mb-2">Built-in Functions</h5>
                    <div className="space-y-1 text-xs text-gray-600">
                      <div><code>set_global(name, value)</code></div>
                      <div><code>string['upper'](text)</code></div>
                      <div><code>string['lower'](text)</code></div>
                      <div><code>string['split'](text, sep)</code></div>
                      <div><code>math['add'](a, b)</code></div>
                      <div><code>math['multiply'](a, b)</code></div>
                      <div><code>len(items)</code></div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        
        {activeTab === 'visual' && (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <BeakerIcon className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Visual Builder</h3>
            <p className="text-gray-600 mb-4">
              Drag-and-drop transformation builder is coming soon!
            </p>
            <p className="text-sm text-gray-500">
              Use the AI Assistant or Code Editor for now.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default EnhancedTransformCodeEditor;