import React, { useState, useEffect } from 'react';
import {
  SparklesIcon,
  CogIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  CloudIcon,
  BeakerIcon,
  CpuChipIcon
} from '@heroicons/react/24/outline';

const AISettings = () => {
  const [settings, setSettings] = useState({
    provider: '',
    model_name: '',
    api_key: '',
    api_endpoint: '',
    temperature: 0.7,
    max_tokens: 4000,
    top_p: 1.0,
    has_api_key: false,
    agent_framework: 'google_adk'
  });
  const [claudeCodeAvailable, setClaudeCodeAvailable] = useState(null);
  const [checkingClaudeCode, setCheckingClaudeCode] = useState(false);
  
  const [availableProviders, setAvailableProviders] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [showApiKey, setShowApiKey] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  // Load settings and available providers on mount
  useEffect(() => {
    loadSettings();
    loadAvailableProviders();
    checkClaudeCodeAvailability();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await fetch('/api/v1/ai-settings/', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      } else if (response.status !== 404) {
        throw new Error('Failed to load AI settings');
      }
    } catch (error) {
      console.error('Error loading AI settings:', error);
      setError('Failed to load AI settings');
    } finally {
      setLoading(false);
    }
  };

  const loadAvailableProviders = async () => {
    try {
      const response = await fetch('/api/v1/ai-settings/providers');
      if (response.ok) {
        const data = await response.json();
        setAvailableProviders(data.providers);
      }
    } catch (error) {
      console.error('Error loading providers:', error);
    }
  };

  const checkClaudeCodeAvailability = async () => {
    setCheckingClaudeCode(true);
    try {
      const response = await fetch('/api/v1/claude-code-agent/check-availability');
      if (response.ok) {
        const data = await response.json();
        setClaudeCodeAvailable(data.available);
      } else {
        setClaudeCodeAvailable(false);
      }
    } catch (error) {
      console.error('Error checking Claude Code availability:', error);
      setClaudeCodeAvailable(false);
    } finally {
      setCheckingClaudeCode(false);
    }
  };

  const handleInputChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Clear test result when settings change
    setTestResult(null);
    setError(null);
    setSuccess(null);
  };

  const handleProviderChange = (provider) => {
    const providerInfo = availableProviders[provider];
    setSettings(prev => ({
      ...prev,
      provider: provider,
      model_name: providerInfo?.models[0] || '',
      api_endpoint: providerInfo?.requires_endpoint ? '' : null
    }));
    setTestResult(null);
  };

  const saveSettings = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        provider: settings.provider || null,
        model_name: settings.model_name || null,
        api_key: settings.api_key || null,
        api_endpoint: settings.api_endpoint || null,
        temperature: settings.temperature,
        max_tokens: settings.max_tokens,
        top_p: settings.top_p,
        agent_framework: settings.agent_framework || 'google_adk'
      };

      const response = await fetch('/api/v1/ai-settings/', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        const data = await response.json();
        setSettings(data);
        setSuccess('AI settings saved successfully');
        setTestResult(null); // Clear test result after saving
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save settings');
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    if (!settings.provider || !settings.api_key) {
      setError('Provider and API key are required for testing');
      return;
    }

    setTesting(true);
    setTestResult(null);
    setError(null);

    try {
      // Send current form data for testing instead of using saved settings
      const testPayload = {
        provider: settings.provider,
        model_name: settings.model_name || null,
        api_key: settings.api_key,
        api_endpoint: settings.api_endpoint || null,
        temperature: settings.temperature,
        max_tokens: settings.max_tokens,
        top_p: settings.top_p
      };

      const response = await fetch('/api/v1/ai-settings/test-connection', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(testPayload)
      });

      if (response.ok) {
        const data = await response.json();
        setTestResult(data);
      } else {
        const errorData = await response.json();
        setTestResult({
          success: false,
          message: errorData.detail || 'Connection test failed'
        });
      }
    } catch (error) {
      setTestResult({
        success: false,
        message: error.message
      });
    } finally {
      setTesting(false);
    }
  };

  const deleteSettings = async () => {
    if (!window.confirm('Are you sure you want to delete your AI settings? This action cannot be undone.')) {
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const response = await fetch('/api/v1/ai-settings/', {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        }
      });

      if (response.ok) {
        setSettings({
          provider: '',
          model_name: '',
          api_key: '',
          api_endpoint: '',
          temperature: 0.7,
          max_tokens: 4000,
          top_p: 1.0,
          has_api_key: false,
          agent_framework: 'google_adk'
        });
        setTestResult(null);
        setSuccess('AI settings deleted successfully');
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete settings');
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setSaving(false);
    }
  };

  const currentProvider = availableProviders[settings.provider];
  const requiresEndpoint = currentProvider?.requires_endpoint;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <SparklesIcon className="w-6 h-6 text-blue-600" />
          <div>
            <h1 className="text-xl font-semibold text-gray-900">AI Settings</h1>
            <p className="text-sm text-gray-600">Configure AI models for automatic code generation in transform nodes</p>
          </div>
        </div>
      </div>

      {/* Alert Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start space-x-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-red-500 mt-0.5" />
            <div className="text-sm text-red-700">{error}</div>
          </div>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-start space-x-2">
            <CheckCircleIcon className="w-5 h-5 text-green-500 mt-0.5" />
            <div className="text-sm text-green-700">{success}</div>
          </div>
        </div>
      )}

      {/* Configuration Form */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-6">
        <div className="flex items-center space-x-2 pb-4 border-b border-gray-200">
          <CogIcon className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-medium text-gray-900">Model Configuration</h2>
        </div>

        {/* Provider Selection */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            AI Provider *
          </label>
          <select
            value={settings.provider}
            onChange={(e) => handleProviderChange(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Select AI Provider</option>
            {Object.entries(availableProviders).map(([key, provider]) => (
              <option key={key} value={key}>
                {provider.name}
              </option>
            ))}
          </select>
        </div>

        {/* Model Selection */}
        {settings.provider && (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Model *
            </label>
            <select
              value={settings.model_name}
              onChange={(e) => handleInputChange('model_name', e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">Select Model</option>
              {currentProvider?.models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* API Endpoint (for Azure OpenAI) */}
        {requiresEndpoint && (
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              API Endpoint *
            </label>
            <input
              type="url"
              value={settings.api_endpoint || ''}
              onChange={(e) => handleInputChange('api_endpoint', e.target.value)}
              placeholder="https://your-resource.openai.azure.com"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-xs text-gray-500">
              Your Azure OpenAI resource endpoint
            </p>
          </div>
        )}

        {/* API Key */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            API Key *
          </label>
          <div className="relative">
            <input
              type={showApiKey ? "text" : "password"}
              value={settings.api_key || ''}
              onChange={(e) => handleInputChange('api_key', e.target.value)}
              placeholder={settings.has_api_key && !settings.api_key ? "API key is configured (enter new key to change)" : "Enter your API key"}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <button
              type="button"
              onClick={() => setShowApiKey(!showApiKey)}
              className="absolute inset-y-0 right-0 pr-3 flex items-center"
            >
              {showApiKey ? (
                <EyeSlashIcon className="w-4 h-4 text-gray-500" />
              ) : (
                <EyeIcon className="w-4 h-4 text-gray-500" />
              )}
            </button>
          </div>
          <p className="text-xs text-gray-500">
            Your API key is encrypted and stored securely. It will only be used to make API calls on your behalf.
          </p>
        </div>

        {/* Agent Framework Selection */}
        <div className="space-y-4 pt-4 border-t border-gray-200">
          <div className="flex items-center space-x-2">
            <CpuChipIcon className="w-5 h-5 text-gray-500" />
            <h3 className="text-sm font-medium text-gray-900">Agent Framework</h3>
          </div>
          <p className="text-xs text-gray-500">
            Choose which framework to use for AI agent execution
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Google ADK Option */}
            <div
              onClick={() => handleInputChange('agent_framework', 'google_adk')}
              className={`cursor-pointer border-2 rounded-lg p-4 transition-all ${
                settings.agent_framework === 'google_adk'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center space-x-3">
                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                  settings.agent_framework === 'google_adk'
                    ? 'border-blue-500'
                    : 'border-gray-300'
                }`}>
                  {settings.agent_framework === 'google_adk' && (
                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                  )}
                </div>
                <div>
                  <div className="font-medium text-sm text-gray-900">Google ADK</div>
                  <div className="text-xs text-gray-500 mt-1">
                    Agent Development Kit - Uses Gemini models with MCP tools
                  </div>
                </div>
              </div>
            </div>

            {/* Claude Code Option */}
            <div
              onClick={() => {
                if (claudeCodeAvailable !== false) {
                  handleInputChange('agent_framework', 'claude_code');
                }
              }}
              className={`cursor-pointer border-2 rounded-lg p-4 transition-all ${
                settings.agent_framework === 'claude_code'
                  ? 'border-blue-500 bg-blue-50'
                  : claudeCodeAvailable === false
                    ? 'border-gray-200 bg-gray-50 opacity-60 cursor-not-allowed'
                    : 'border-gray-200 hover:border-gray-300'
              }`}
            >
              <div className="flex items-center space-x-3">
                <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                  settings.agent_framework === 'claude_code'
                    ? 'border-blue-500'
                    : 'border-gray-300'
                }`}>
                  {settings.agent_framework === 'claude_code' && (
                    <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                  )}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-sm text-gray-900">Claude Code</span>
                    {checkingClaudeCode && (
                      <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-gray-400"></div>
                    )}
                    {claudeCodeAvailable === true && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700">
                        Available
                      </span>
                    )}
                    {claudeCodeAvailable === false && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                        Not Installed
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    Claude Code CLI - Uses Anthropic Claude models with file tools
                  </div>
                  {claudeCodeAvailable === false && (
                    <div className="text-xs text-red-500 mt-1">
                      Install with: npm install -g @anthropic-ai/claude-code
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Advanced Settings */}
        <div className="space-y-4 pt-4 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-900">Advanced Settings</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Temperature */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                Temperature
              </label>
              <input
                type="number"
                min="0"
                max="2"
                step="0.1"
                value={settings.temperature}
                onChange={(e) => handleInputChange('temperature', parseFloat(e.target.value))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500">0 = deterministic, 2 = very creative</p>
            </div>

            {/* Max Tokens */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                Max Tokens
              </label>
              <input
                type="number"
                min="1"
                max={(() => {
                  // GPT-5 and o-series models have 128K limit, others have 200K
                  const model = settings.model_name || '';
                  const isGpt5OrO = model.startsWith('gpt-5') || model.startsWith('o3') || model.startsWith('o4') || model.startsWith('o1');
                  return isGpt5OrO ? "128000" : "200000";
                })()}
                value={settings.max_tokens}
                onChange={(e) => handleInputChange('max_tokens', parseInt(e.target.value))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500">
                {(() => {
                  const model = settings.model_name || '';
                  const isGpt5OrO = model.startsWith('gpt-5') || model.startsWith('o3') || model.startsWith('o4') || model.startsWith('o1');
                  return isGpt5OrO 
                    ? "Maximum response length (GPT-5/o-series: 128K limit)"
                    : "Maximum response length (up to 200K for other models)";
                })()}
              </p>
            </div>

            {/* Top P */}
            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700">
                Top P
              </label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.1"
                value={settings.top_p}
                onChange={(e) => handleInputChange('top_p', parseFloat(e.target.value))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <p className="text-xs text-gray-500">Nucleus sampling parameter</p>
            </div>
          </div>
        </div>
      </div>

      {/* Test Connection */}
      {(settings.provider || settings.agent_framework === 'claude_code') && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-4">
          <div className="flex items-center space-x-2">
            <BeakerIcon className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-medium text-gray-900">Test Connection</h2>
          </div>

          <div className="flex items-center space-x-3">
            {/* Test AI Provider Connection */}
            {settings.provider && (
              <button
                onClick={testConnection}
                disabled={testing || !settings.api_key}
                className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                {testing ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Testing Provider...</span>
                  </>
                ) : (
                  <>
                    <CloudIcon className="w-4 h-4" />
                    <span>Test AI Provider</span>
                  </>
                )}
              </button>
            )}

            {/* Test Claude Code CLI */}
            {settings.agent_framework === 'claude_code' && (
              <button
                onClick={checkClaudeCodeAvailability}
                disabled={checkingClaudeCode}
                className="flex items-center space-x-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                {checkingClaudeCode ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>Checking CLI...</span>
                  </>
                ) : (
                  <>
                    <CpuChipIcon className="w-4 h-4" />
                    <span>Test Claude Code CLI</span>
                  </>
                )}
              </button>
            )}
          </div>

          {/* AI Provider Test Result */}
          {testResult && (
            <div className={`p-4 rounded-lg ${testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
              <div className="flex items-start space-x-2">
                {testResult.success ? (
                  <CheckCircleIcon className="w-5 h-5 text-green-500 mt-0.5" />
                ) : (
                  <ExclamationTriangleIcon className="w-5 h-5 text-red-500 mt-0.5" />
                )}
                <div className="flex-1">
                  <p className={`text-sm font-medium ${testResult.success ? 'text-green-800' : 'text-red-800'}`}>
                    {testResult.success ? 'AI Provider Connection Successful' : 'AI Provider Connection Failed'}
                  </p>
                  <p className={`text-sm mt-1 ${testResult.success ? 'text-green-700' : 'text-red-700'}`}>
                    {testResult.message}
                  </p>
                  {testResult.model_info && (
                    <div className="mt-2 text-xs text-green-600">
                      <p>Provider: {testResult.model_info.provider}</p>
                      <p>Model: {testResult.model_info.model}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Claude Code CLI Test Result */}
          {settings.agent_framework === 'claude_code' && claudeCodeAvailable !== null && (
            <div className={`p-4 rounded-lg ${claudeCodeAvailable ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
              <div className="flex items-start space-x-2">
                {claudeCodeAvailable ? (
                  <CheckCircleIcon className="w-5 h-5 text-green-500 mt-0.5" />
                ) : (
                  <ExclamationTriangleIcon className="w-5 h-5 text-red-500 mt-0.5" />
                )}
                <div className="flex-1">
                  <p className={`text-sm font-medium ${claudeCodeAvailable ? 'text-green-800' : 'text-red-800'}`}>
                    {claudeCodeAvailable ? 'Claude Code CLI Available' : 'Claude Code CLI Not Found'}
                  </p>
                  <p className={`text-sm mt-1 ${claudeCodeAvailable ? 'text-green-700' : 'text-red-700'}`}>
                    {claudeCodeAvailable
                      ? 'Claude Code CLI is installed and ready to use for agent execution.'
                      : 'Claude Code CLI is not installed. Install with: npm install -g @anthropic-ai/claude-code'}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-between pt-6 border-t border-gray-200">
        <button
          onClick={deleteSettings}
          disabled={saving || !settings.has_api_key}
          className="text-sm text-red-600 hover:text-red-700 disabled:text-gray-400"
        >
          Delete AI Settings
        </button>
        
        <button
          onClick={saveSettings}
          disabled={saving || (
            settings.agent_framework === 'claude_code'
              ? false
              : (!settings.provider || !settings.model_name || (!settings.api_key && !settings.has_api_key))
          )}
          className="flex items-center space-x-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-6 py-2 rounded-lg text-sm font-medium"
        >
          {saving ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Saving...</span>
            </>
          ) : (
            <span>Save Settings</span>
          )}
        </button>
      </div>

      {/* Information */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start space-x-2">
          <InformationCircleIcon className="w-5 h-5 text-blue-500 mt-0.5" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">How it works:</p>
            <ul className="space-y-1 text-sm">
              <li>• Configure your preferred AI model and API key</li>
              <li>• Choose your agent framework: <strong>Google ADK</strong> (uses Gemini models) or <strong>Claude Code</strong> (uses Anthropic CLI)</li>
              <li>• In transform nodes, use the "AI Assistant" tab to describe transformations in natural language</li>
              <li>• The AI will generate Python code based on your flow context and available data</li>
              <li>• Review and apply the generated code to your transform node</li>
            </ul>
            <p className="font-medium mt-3 mb-1">Agent Framework Comparison:</p>
            <ul className="space-y-1 text-sm">
              <li>• <strong>Google ADK</strong>: Uses Google's Agent Development Kit with MCP tools. Best for Gemini models and custom tool configurations.</li>
              <li>• <strong>Claude Code</strong>: Uses Anthropic's Claude Code CLI with built-in file tools (Read, Write, Edit, Grep). Best for code generation and file manipulation tasks. Requires Claude Code CLI installed locally.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AISettings;