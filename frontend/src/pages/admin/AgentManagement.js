import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tab } from '@headlessui/react';
import { useLayout } from '../../contexts/LayoutContext';
import {
  SparklesIcon,
  PlusIcon,
  PlayIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
  TrashIcon,
  DocumentArrowDownIcon,
  DocumentArrowUpIcon
} from '@heroicons/react/24/outline';

function classNames(...classes) {
  return classes.filter(Boolean).join(' ');
}

// JSON Schema for agent configuration
const AGENT_SCHEMA = {
  agent_id: '',
  model: 'claude-sonnet-4-5',
  description: '',
  system_prompt: '',
  instruction: '',
  tools: []
};

// Available AI Models (synced with AI Settings)
const AVAILABLE_MODELS = {
  openai: [
    // GPT-5.1 Series (Latest - November 2025)
    'gpt-5.1', 'gpt-5.1-mini', 'gpt-5.1-nano', 'gpt-5.1-codex', 'gpt-5.1-codex-mini',
    // GPT-5 Series (August 2025)
    'gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5-chat', 'gpt-5-codex',
    // GPT-4.1 Series (January 2025)
    'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano',
    // GPT-4o Series (Current flagship multimodal)
    'gpt-4o', 'gpt-4o-mini',
    // GPT-4 Turbo and GPT-4 (maintained for compatibility)
    'gpt-4', 'gpt-4-turbo',
    // o-series reasoning models
    'o3', 'o3-mini', 'o4-mini',
    // Legacy GPT-3.5 (deprecated but supported)
    'gpt-3.5-turbo'
  ],
  claude: [
    // Claude 4.5 Series (Latest - October/November 2025)
    'claude-opus-4-5', 'claude-opus-4-5-20251101',
    'claude-sonnet-4-5', 'claude-sonnet-4-5-20250929',
    'claude-haiku-4-5', 'claude-haiku-4-5-20251001',
    // Claude 4.1 Series
    'claude-opus-4.1', 'claude-opus-4-1-20250805',
    // Claude 4 Series
    'claude-4-opus', 'claude-4-sonnet', 'claude-4-haiku',
    'claude-sonnet-4-20250514',
    // Claude 3.5 Series (maintained for compatibility)
    'claude-3-5-sonnet', 'claude-3-5-haiku',
    // Legacy Claude 3 Series
    'claude-3-sonnet', 'claude-3-opus', 'claude-3-haiku'
  ],
  gemini: [
    // Gemini 3 Series (Latest - 2025)
    'gemini-3-pro', 'gemini-3-flash', 'gemini-3-flash-lite',
    // Gemini 2.5 Series
    'gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite',
    // Gemini 2.0 Series
    'gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-2.0-pro-experimental',
    'gemini-2.0-flash-exp',
    // Legacy Gemini 1.5 Series (maintained for compatibility)
    'gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-1.5-flash-8b',
    // Legacy Gemini 1.0 Series
    'gemini-1.0-pro', 'gemini-1.0-pro-vision'
  ],
  azure_openai: [
    'gpt-5.1', 'gpt-5', 'gpt-4.5', 'gpt-4', 'gpt-4-turbo', 'gpt-35-turbo', 'gpt-4o', 'gpt-4o-mini'
  ]
};

// Sample agent configurations
const SAMPLE_AGENTS = {
  math_agent: {
    agent_id: 'math_agent',
    model: 'claude-sonnet-4-5',
    description: 'Agent specialized in mathematical calculations and unit conversions.',
    system_prompt: 'You are a helpful assistant specialized in mathematical calculations, unit conversions, and numerical analysis.',
    instruction: 'Use the calculate tool for math expressions, convert_units for unit conversions, and fibonacci for Fibonacci numbers.',
    tools: [
      {
        name: 'calculate',
        description: 'Evaluate mathematical expressions',
        function: 'calculate'
      },
      {
        name: 'convert_units',
        description: 'Convert between different units of measurement',
        function: 'convert_units'
      }
    ]
  },
  text_agent: {
    agent_id: 'text_agent',
    model: 'claude-sonnet-4-5',
    description: 'Agent for text processing and manipulation.',
    system_prompt: 'You are a text processing expert.',
    instruction: 'Help users with text analysis, transformation, and processing tasks.',
    tools: [
      {
        name: 'count_words',
        description: 'Count words in text',
        function: 'count_words'
      },
      {
        name: 'reverse_text',
        description: 'Reverse the given text',
        function: 'reverse_text'
      }
    ]
  },
  general_assistant: {
    agent_id: 'general_assistant',
    model: 'claude-sonnet-4-5',
    description: 'A general-purpose AI assistant without specialized tools.',
    system_prompt: 'You are a helpful, friendly, and knowledgeable AI assistant.',
    instruction: 'Provide helpful, accurate, and relevant responses to user queries.',
    tools: []
  }
};

const AgentManagement = () => {
  const navigate = useNavigate();
  const { isAssistantLayout } = useLayout();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Agent configurations state
  const [agentConfigs, setAgentConfigs] = useState({});
  const [selectedConfig, setSelectedConfig] = useState('');
  const [jsonContent, setJsonContent] = useState('');
  const [jsonError, setJsonError] = useState(null);

  // Test state
  const [testInput, setTestInput] = useState('');
  const [testResponse, setTestResponse] = useState(null);
  const [isTestLoading, setIsTestLoading] = useState(false);

  // API key state
  const [apiKey, setApiKey] = useState(localStorage.getItem('ai_agent_api_key') || '');

  const tabs = [
    { name: 'JSON Editor', icon: DocumentTextIcon },
    { name: 'Test Agent', icon: PlayIcon },
    { name: 'Templates', icon: DocumentArrowDownIcon },
  ];

  useEffect(() => {
    loadAgentConfigurations();
  }, []);

  const loadAgentConfigurations = async () => {
    try {
      // Load existing agent configurations from backend
      const token = localStorage.getItem('access_token');
      if (token) {
        const response = await fetch('/api/v1/flow-agents/', {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          const agents = await response.json();
          if (agents && Array.isArray(agents)) {
            const backendConfigs = {};
            agents.forEach(agent => {
              backendConfigs[agent.agent_id] = agent;
            });
            setAgentConfigs({ ...SAMPLE_AGENTS, ...backendConfigs });

            const allConfigs = { ...SAMPLE_AGENTS, ...backendConfigs };
            const firstKey = Object.keys(allConfigs)[0];
            if (firstKey) {
              selectConfiguration(firstKey);
            }
            return;
          }
        }
      }
    } catch (err) {
      console.error('Failed to load agent configurations:', err);
    }

    // Fallback to sample configurations
    setAgentConfigs(SAMPLE_AGENTS);
    const firstKey = Object.keys(SAMPLE_AGENTS)[0];
    if (firstKey) {
      selectConfiguration(firstKey);
    }
  };

  const selectConfiguration = (configId) => {
    setSelectedConfig(configId);
    const config = agentConfigs[configId];
    if (config) {
      setJsonContent(JSON.stringify(config, null, 2));
      setJsonError(null);
    }
  };

  const validateJSON = (content) => {
    try {
      const parsed = JSON.parse(content);

      // Basic validation
      if (!parsed.agent_id) {
        throw new Error('agent_id is required');
      }
      if (!parsed.model) {
        throw new Error('model is required');
      }
      if (!parsed.system_prompt) {
        throw new Error('system_prompt is required');
      }
      if (parsed.tools && !Array.isArray(parsed.tools)) {
        throw new Error('tools must be an array');
      }

      setJsonError(null);
      return parsed;
    } catch (err) {
      setJsonError(err.message);
      return null;
    }
  };

  const handleJsonChange = (value) => {
    setJsonContent(value);
    validateJSON(value);
  };

  const handleSaveConfiguration = async () => {
    const config = validateJSON(jsonContent);
    if (!config) {
      setError('Invalid JSON configuration. Please fix the errors.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('access_token');

      // Save agent configuration
      const response = await fetch('/api/v1/flow-agents/', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(config)
      });

      if (response.ok) {
        // Update local state
        setAgentConfigs({
          ...agentConfigs,
          [config.agent_id]: config
        });

        setSuccessMessage(`Configuration saved: ${config.agent_id}`);
        setTimeout(() => setSuccessMessage(null), 3000);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to save configuration');
      }
    } catch (err) {
      console.error('Error saving configuration:', err);
      setError('Failed to save configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleTestAgent = async () => {
    const config = validateJSON(jsonContent);
    if (!config) {
      setError('Please fix JSON errors before testing');
      return;
    }

    if (!apiKey) {
      setError('Please enter your API key');
      return;
    }

    if (!testInput.trim()) {
      setError('Please enter some input to test');
      return;
    }

    setIsTestLoading(true);
    setError(null);
    setTestResponse(null);

    try {
      const token = localStorage.getItem('access_token');

      if (!token) {
        setError('You must be logged in to test agents');
        return;
      }

      // Prepare the request body for flow agent execution
      const requestBody = {
        agent_id: config.agent_id,
        input: testInput,
        use_dynamic: true,
        system_prompt: config.system_prompt,
        instruction: config.instruction || '',
        model: config.model,
        tools: config.tools.map(t => typeof t === 'string' ? t : (t.function || t.name)),
        api_key: apiKey
      };

      // Execute the flow agent
      const response = await fetch('/api/v1/flow-agents/execute', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestBody)
      });

      if (response.ok) {
        const result = await response.json();

        // Extract the actual response from the result
        if (result.response) {
          setTestResponse(result.response);
        } else if (result.result) {
          setTestResponse(typeof result.result === 'string' ? result.result : JSON.stringify(result.result, null, 2));
        } else if (result.message) {
          setTestResponse(result.message);
        } else {
          setTestResponse(JSON.stringify(result, null, 2));
        }

        setSuccessMessage('Agent executed successfully');
        setTimeout(() => setSuccessMessage(null), 3000);
      } else {
        let errorMessage = 'Failed to execute agent';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
        } catch (e) {
          // If response is not JSON
          if (response.status === 401) {
            errorMessage = 'Authentication failed. Please log in again.';
          } else if (response.status === 403) {
            errorMessage = 'Permission denied. You do not have access to this feature.';
          } else {
            errorMessage = `Server error: ${response.status} ${response.statusText}`;
          }
        }
        setError(errorMessage);
      }
    } catch (err) {
      console.error('Error testing agent:', err);
      setError(`Failed to test agent: ${err.message}`);
    } finally {
      setIsTestLoading(false);
    }
  };

  const handleExportConfig = () => {
    const config = validateJSON(jsonContent);
    if (!config) {
      setError('Please fix JSON errors before exporting');
      return;
    }

    const blob = new Blob([jsonContent], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${config.agent_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    setSuccessMessage('Configuration exported successfully');
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const handleImportConfig = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const content = e.target.result;
          const config = JSON.parse(content);

          // Validate imported config
          if (!config.agent_id) {
            throw new Error('Invalid configuration: missing agent_id');
          }

          setJsonContent(JSON.stringify(config, null, 2));
          setAgentConfigs({
            ...agentConfigs,
            [config.agent_id]: config
          });
          setSelectedConfig(config.agent_id);

          setSuccessMessage('Configuration imported successfully');
          setTimeout(() => setSuccessMessage(null), 3000);
        } catch (err) {
          setError(`Failed to import configuration: ${err.message}`);
        }
      };
      reader.readAsText(file);
    }
  };

  const loadTemplate = (templateKey) => {
    const template = SAMPLE_AGENTS[templateKey];
    if (template) {
      // Create a copy with a new ID
      const newConfig = {
        ...template,
        agent_id: `${template.agent_id}_copy_${Date.now()}`
      };

      setJsonContent(JSON.stringify(newConfig, null, 2));
      setSelectedConfig(newConfig.agent_id);
      setAgentConfigs({
        ...agentConfigs,
        [newConfig.agent_id]: newConfig
      });

      setSuccessMessage('Template loaded. Modify the agent_id and save.');
      setTimeout(() => setSuccessMessage(null), 3000);

      // Switch to editor tab
      setSelectedIndex(0);
    }
  };

  return (
    <div className={`py-6 ${isAssistantLayout ? 'px-3 sm:px-4 lg:px-6' : 'px-4 sm:px-6 lg:px-8'}`}>
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-gray-900 flex items-center gap-2">
            <SparklesIcon className="h-8 w-8 text-primary" />
            Flow Agent Configuration
          </h1>
          <p className="mt-2 text-gray-600">
            Define, edit, and test flow agent JSON configurations
          </p>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <div className="flex">
              <ExclamationTriangleIcon className="h-5 w-5 mr-2 flex-shrink-0" />
              <span>{error}</span>
            </div>
          </div>
        )}

        {successMessage && (
          <div className="mb-6 bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded">
            <div className="flex">
              <CheckCircleIcon className="h-5 w-5 mr-2 flex-shrink-0" />
              <span>{successMessage}</span>
            </div>
          </div>
        )}

        <Tab.Group selectedIndex={selectedIndex} onChange={setSelectedIndex}>
          <Tab.List className="flex space-x-1 rounded-xl bg-gray-100 p-1">
            {tabs.map((tab) => (
              <Tab
                key={tab.name}
                className={({ selected }) =>
                  classNames(
                    'w-full rounded-lg py-2.5 text-sm font-medium leading-5',
                    'ring-white ring-opacity-60 ring-offset-2 ring-offset-blue-400 focus:outline-none focus:ring-2',
                    selected
                      ? 'bg-white text-blue-700 shadow'
                      : 'text-gray-600 hover:bg-white/[0.12] hover:text-gray-800'
                  )
                }
              >
                <div className="flex items-center justify-center space-x-2">
                  <tab.icon className="h-5 w-5" />
                  <span>{tab.name}</span>
                </div>
              </Tab>
            ))}
          </Tab.List>

          <Tab.Panels className="mt-6">
            {/* JSON Editor Panel */}
            <Tab.Panel className="rounded-xl bg-white p-6 shadow">
              <div className="space-y-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h2 className="text-lg font-medium text-gray-900">Agent Configuration Editor</h2>
                    <p className="mt-1 text-sm text-gray-600">
                      Edit the JSON configuration for your flow agent
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleExportConfig}
                      className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                    >
                      <DocumentArrowUpIcon className="h-4 w-4 mr-1" />
                      Export
                    </button>
                    <label className="inline-flex items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 cursor-pointer">
                      <DocumentArrowDownIcon className="h-4 w-4 mr-1" />
                      Import
                      <input
                        type="file"
                        accept=".json"
                        onChange={handleImportConfig}
                        className="hidden"
                      />
                    </label>
                  </div>
                </div>

                {/* Configuration Selector */}
                <div className="flex gap-4">
                  <div className="w-1/4">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Available Configurations
                    </label>
                    <div className="border border-gray-200 rounded-md overflow-hidden">
                      {Object.keys(agentConfigs).map((configId) => (
                        <button
                          key={configId}
                          onClick={() => selectConfiguration(configId)}
                          className={classNames(
                            'w-full text-left px-3 py-2 text-sm border-b last:border-b-0',
                            selectedConfig === configId
                              ? 'bg-primary-10 text-primary font-medium'
                              : 'hover:bg-gray-50'
                          )}
                        >
                          {configId}
                        </button>
                      ))}
                      {Object.keys(agentConfigs).length === 0 && (
                        <p className="px-3 py-2 text-sm text-gray-500">
                          No configurations loaded
                        </p>
                      )}
                    </div>
                  </div>

                  {/* JSON Editor */}
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      JSON Configuration {jsonError && (
                        <span className="text-red-600 ml-2">- Error: {jsonError}</span>
                      )}
                    </label>
                    <textarea
                      value={jsonContent}
                      onChange={(e) => handleJsonChange(e.target.value)}
                      className={classNames(
                        'w-full h-96 font-mono text-sm p-3 border rounded-md',
                        jsonError ? 'border-red-300' : 'border-gray-300'
                      )}
                      placeholder={JSON.stringify(AGENT_SCHEMA, null, 2)}
                    />

                    <div className="mt-4 flex justify-between">
                      <div className="text-xs text-gray-500">
                        Required fields: agent_id, model, system_prompt
                      </div>
                      <button
                        onClick={handleSaveConfiguration}
                        disabled={loading || !!jsonError}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg disabled:bg-gray-300"
                      >
                        {loading ? (
                          <>
                            <ArrowPathIcon className="mr-2 h-4 w-4 animate-spin" />
                            Saving...
                          </>
                        ) : (
                          <>Save Configuration</>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </Tab.Panel>

            {/* Test Agent Panel */}
            <Tab.Panel className="rounded-xl bg-white p-6 shadow">
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-medium text-gray-900">Test Agent Configuration</h2>
                  <p className="mt-2 text-sm text-gray-600">
                    Test the current agent configuration with custom input
                  </p>
                </div>

                {/* Current Configuration Info */}
                {selectedConfig && (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Current Configuration</h3>
                    <div className="text-sm text-gray-600 space-y-1">
                      <p><strong>Agent ID:</strong> {agentConfigs[selectedConfig]?.agent_id}</p>
                      <p><strong>Model:</strong> {agentConfigs[selectedConfig]?.model}</p>
                      <p><strong>Description:</strong> {agentConfigs[selectedConfig]?.description}</p>
                      <p><strong>Tools:</strong> {agentConfigs[selectedConfig]?.tools?.length || 0} configured</p>
                    </div>
                  </div>
                )}

                {/* API Key Configuration */}
                <div className="space-y-2">
                  <label htmlFor="api-key" className="block text-sm font-medium text-gray-700">
                    API Key
                  </label>
                  <input
                    id="api-key"
                    type="password"
                    value={apiKey}
                    onChange={(e) => {
                      setApiKey(e.target.value);
                      localStorage.setItem('ai_agent_api_key', e.target.value);
                    }}
                    placeholder="Enter your Google AI or OpenAI API key"
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm px-3 py-2 border"
                  />
                  <p className="text-xs text-gray-500">
                    Get your API key from{' '}
                    <a
                      href="https://makersuite.google.com/app/apikey"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      Google AI Studio
                    </a>
                  </p>
                </div>

                {/* Test Input */}
                <div className="space-y-2">
                  <label className="block text-sm font-medium text-gray-700">Test Input</label>
                  <textarea
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    placeholder="Enter your test input..."
                    rows={4}
                    className="block w-full rounded-md border-gray-300 shadow-sm focus:border-primary focus:ring-primary sm:text-sm px-3 py-2 border"
                  />
                  <button
                    onClick={handleTestAgent}
                    disabled={isTestLoading || !apiKey || !testInput.trim() || !selectedConfig}
                    className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-gradient-primary hover:shadow-lg disabled:bg-gray-300"
                  >
                    {isTestLoading ? (
                      <>
                        <ArrowPathIcon className="mr-2 h-4 w-4 animate-spin" />
                        Testing...
                      </>
                    ) : (
                      <>
                        <PlayIcon className="mr-2 h-4 w-4" />
                        Test Agent
                      </>
                    )}
                  </button>
                </div>

                {/* Response Display */}
                {testResponse && (
                  <div className="mt-6">
                    <h3 className="text-lg font-medium text-gray-900 mb-2">Response</h3>
                    <div className="bg-gray-50 rounded-lg p-4">
                      <pre className="whitespace-pre-wrap text-sm text-gray-700">{testResponse}</pre>
                    </div>
                  </div>
                )}
              </div>
            </Tab.Panel>

            {/* Templates Panel */}
            <Tab.Panel className="rounded-xl bg-white p-6 shadow">
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-medium text-gray-900">Agent Templates</h2>
                  <p className="mt-2 text-sm text-gray-600">
                    Start with a pre-configured template and customize it for your needs
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(SAMPLE_AGENTS).map(([key, template]) => (
                    <div
                      key={key}
                      className="border border-gray-200 rounded-lg p-4 hover:border-primary transition-colors"
                    >
                      <h3 className="text-sm font-medium text-gray-900">{template.agent_id}</h3>
                      <p className="mt-1 text-xs text-gray-500">Model: {template.model}</p>
                      <p className="mt-2 text-sm text-gray-600">{template.description}</p>
                      <div className="mt-3">
                        <p className="text-xs text-gray-500">
                          Tools: {template.tools.length > 0 ? template.tools.map(t => t.name).join(', ') : 'None'}
                        </p>
                      </div>
                      <button
                        onClick={() => loadTemplate(key)}
                        className="mt-4 w-full inline-flex justify-center items-center px-3 py-1.5 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                      >
                        Use Template
                      </button>
                    </div>
                  ))}
                </div>

                <div className="mt-6 p-4 bg-blue-50 rounded-lg">
                  <h3 className="text-sm font-medium text-blue-900 mb-2">Available Tools</h3>
                  <p className="text-sm text-blue-700 mb-3">
                    These tools can be added to your agent configuration:
                  </p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div><strong>calculate:</strong> Mathematical calculations</div>
                    <div><strong>convert_units:</strong> Unit conversions</div>
                    <div><strong>fibonacci:</strong> Fibonacci numbers</div>
                    <div><strong>count_words:</strong> Word counting</div>
                    <div><strong>reverse_text:</strong> Text reversal</div>
                    <div><strong>translate:</strong> Language translation</div>
                  </div>
                </div>
              </div>
            </Tab.Panel>
          </Tab.Panels>
        </Tab.Group>
      </div>
    </div>
  );
};

export default AgentManagement;