import React, { useState, useEffect } from 'react';
import {
  KeyIcon,
  CpuChipIcon,
  CheckIcon,
  ServerIcon,
  EyeIcon,
  EyeSlashIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline';
import { Listbox } from '@headlessui/react';
import { ChevronUpDownIcon } from '@heroicons/react/20/solid';
import { assistantService } from '../../services/assistantService';

function ModelConfig({ onUpdate, onConfigUpdate }) {
  // Support both prop names for backward compatibility
  const handleUpdate = onConfigUpdate || onUpdate;
  // State for configuration
  const [useDefaultSettings, setUseDefaultSettings] = useState(true);
  const [localProvider, setLocalProvider] = useState('google');
  const [localModel, setLocalModel] = useState('gemini-2.0-flash-exp');
  const [customApiKey, setCustomApiKey] = useState('');
  const [customApiBase, setCustomApiBase] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);

  // State for UI
  const [models, setModels] = useState([]);
  const [filteredModels, setFilteredModels] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaved, setIsSaved] = useState(true);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // State for settings from backend
  const [defaultSettings, setDefaultSettings] = useState(null);
  const [savedSettings, setSavedSettings] = useState(null);
  const [hasApiKeyInSettings, setHasApiKeyInSettings] = useState(false);
  const [hasCustomApiKey, setHasCustomApiKey] = useState(false);

  const providers = [
    { id: 'google', name: 'Google Gemini', keyLabel: 'Google API Key', keyHelpUrl: 'https://makersuite.google.com/app/apikey' },
    { id: 'openai', name: 'OpenAI', keyLabel: 'OpenAI API Key', keyHelpUrl: 'https://platform.openai.com/api-keys' },
    { id: 'anthropic', name: 'Anthropic Claude', keyLabel: 'Anthropic API Key', keyHelpUrl: 'https://console.anthropic.com/settings/keys' },
    { id: 'deepseek', name: 'DeepSeek', keyLabel: 'DeepSeek API Key', keyHelpUrl: 'https://platform.deepseek.com/api_keys' },
    { id: 'lm_studio', name: 'LM Studio (Local)', keyLabel: 'Not Required', keyHelpUrl: null, requiresApiBase: true, defaultApiBase: 'http://localhost:1234/v1' },
    { id: 'ollama', name: 'Ollama (Local)', keyLabel: 'Not Required', keyHelpUrl: null, requiresApiBase: true, defaultApiBase: 'http://localhost:11434' }
  ];

  useEffect(() => {
    loadModels();
    loadSettings();
  }, []);

  const loadSettings = async () => {
    console.log('=== ModelConfig: Loading settings ===');
    try {
      // Load both default and user settings
      const defaultData = await assistantService.getDefaultSettings();
      console.log('ModelConfig: Received default settings:', defaultData);

      if (defaultData) {
        setDefaultSettings(defaultData);
        setHasApiKeyInSettings(defaultData.has_api_key);

        console.log('ModelConfig: Default provider:', defaultData.provider);
        console.log('ModelConfig: Default model:', defaultData.model);
        console.log('ModelConfig: Has API key:', defaultData.has_api_key);

        let providerToUse = defaultData.provider || 'google';
        let modelToUse = defaultData.model || 'gemini-2.0-flash-exp';
        let shouldUseDefaults = true;

        console.log('ModelConfig: Provider to use (initial):', providerToUse);
        console.log('ModelConfig: Model to use (initial):', modelToUse);

        // Check if user has saved assistant settings
        if (defaultData.assistant_settings && defaultData.assistant_settings.saved) {
          console.log('ModelConfig: Found saved assistant settings');
          setSavedSettings(defaultData.assistant_settings);
          shouldUseDefaults = defaultData.assistant_settings.use_defaults;
          setUseDefaultSettings(shouldUseDefaults);

          if (!shouldUseDefaults) {
            // Use saved custom settings
            providerToUse = defaultData.assistant_settings.provider || providerToUse;
            modelToUse = defaultData.assistant_settings.model || modelToUse;
            setHasCustomApiKey(defaultData.assistant_settings.has_custom_api_key);
          }
        } else {
          // No saved settings, use defaults from AI configuration
          console.log('ModelConfig: No saved assistant settings, using AI config defaults');
          setUseDefaultSettings(true);
        }

        // Update local state
        console.log('ModelConfig: Setting local state - Provider:', providerToUse, 'Model:', modelToUse);
        setLocalProvider(providerToUse);
        setLocalModel(modelToUse);

        // Notify parent component with correct values
        const updateData = {
          apiKey: defaultData.has_api_key ? 'USE_FROM_SETTINGS' : '',
          model: modelToUse,
          provider: providerToUse
        };
        console.log('ModelConfig: Calling onUpdate with:', updateData);
        if (handleUpdate) handleUpdate(updateData);

        // Mark as saved initially since we just loaded from backend
        setIsSaved(true);
        setHasUnsavedChanges(false);
      } else {
        console.log('ModelConfig: No default data received');
      }
    } catch (error) {
      console.error('ModelConfig: Failed to load settings:', error);
    }
  };

  useEffect(() => {
    // Filter models based on selected provider
    const providerModels = models.filter(m => m.provider === localProvider);
    setFilteredModels(providerModels);

    // If current model is not from selected provider, select first available model
    const currentModelProvider = models.find(m => m.id === localModel)?.provider;
    if (currentModelProvider && currentModelProvider !== localProvider) {
      if (providerModels.length > 0) {
        setLocalModel(providerModels[0].id);
      } else if (localProvider === 'lm_studio') {
        // Set a default LM Studio model if none in list
        setLocalModel('mistral-7b-instruct-v0.2');  // Use your actual model
      } else if (localProvider === 'ollama') {
        // Set a default Ollama model if none in list
        setLocalModel('llama3.2');
      } else if (localProvider === 'deepseek') {
        // Set a default DeepSeek model if none in list
        setLocalModel('deepseek-chat');
      }
    }

    // Set default API base for local providers
    const provider = providers.find(p => p.id === localProvider);
    if (provider && provider.requiresApiBase && !customApiBase) {
      setCustomApiBase(provider.defaultApiBase);
    }
  }, [localProvider, models]);

  const loadModels = async () => {
    try {
      setIsLoading(true);
      const modelList = await assistantService.listModels();
      setModels(modelList);
    } catch (error) {
      console.error('Failed to load models:', error);
      // Fallback models if API fails
      setModels([
        // Google Gemini Models
        { id: 'gemini-3-pro', name: 'Gemini 3 Pro', provider: 'google', description: 'Most advanced Gemini model' },
        { id: 'gemini-3-flash', name: 'Gemini 3 Flash', provider: 'google', description: 'Fast and capable' },
        { id: 'gemini-3-flash-lite', name: 'Gemini 3 Flash Lite', provider: 'google', description: 'Lightweight and efficient' },
        { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', provider: 'google' },
        { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', provider: 'google' },
        { id: 'gemini-2.0-flash-exp', name: 'Gemini 2.0 Flash (Experimental)', provider: 'google', default: true },
        { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', provider: 'google' },
        // OpenAI Models
        { id: 'gpt-5.1', name: 'GPT-5.1', provider: 'openai', description: 'Latest flagship model' },
        { id: 'gpt-5.1-mini', name: 'GPT-5.1 Mini', provider: 'openai', description: 'Balanced performance' },
        { id: 'gpt-5.1-nano', name: 'GPT-5.1 Nano', provider: 'openai', description: 'Fastest and most efficient' },
        { id: 'gpt-5', name: 'GPT-5', provider: 'openai', description: 'Reasoning model' },
        { id: 'gpt-5-mini', name: 'GPT-5 Mini', provider: 'openai', description: 'Cost-optimized' },
        { id: 'gpt-5-nano', name: 'GPT-5 Nano', provider: 'openai', description: 'High-throughput' },
        { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai' },
        { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai' },
        // Anthropic Claude Models
        { id: 'claude-opus-4-5-20251101', name: 'Claude Opus 4.5', provider: 'anthropic', description: 'Most intelligent Claude model' },
        { id: 'claude-sonnet-4-5-20250929', name: 'Claude Sonnet 4.5', provider: 'anthropic', description: 'Best for complex tasks' },
        { id: 'claude-haiku-4-5-20251001', name: 'Claude Haiku 4.5', provider: 'anthropic', description: 'Fast with extended thinking' },
        { id: 'claude-opus-4-1-20250805', name: 'Claude Opus 4.1', provider: 'anthropic' },
        { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', provider: 'anthropic' },
        // DeepSeek models - use exact model names from DeepSeek API
        { id: 'deepseek-chat', name: 'DeepSeek Chat', provider: 'deepseek', description: 'Standard chat model' },
        { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner (V3.1)', provider: 'deepseek', description: 'Enhanced reasoning' },
        { id: 'deepseek-r1', name: 'DeepSeek R1', provider: 'deepseek', description: '671B reasoning model' },
        { id: 'deepseek-coder', name: 'DeepSeek Coder', provider: 'deepseek', description: 'Code generation' },
        { id: 'deepseek-r1-distill-qwen-32b', name: 'DeepSeek R1 Distill 32B', provider: 'deepseek', description: 'Efficient 32B model' },
        { id: 'deepseek-r1-distill-qwen-14b', name: 'DeepSeek R1 Distill 14B', provider: 'deepseek', description: 'Efficient 14B model' },
        { id: 'deepseek-r1-distill-qwen-7b', name: 'DeepSeek R1 Distill 7B', provider: 'deepseek', description: 'Budget-friendly 7B' },
        // LM Studio models (detected at runtime - use actual model IDs from LM Studio)
        { id: 'qwen/qwen2.5-coder-14b', name: 'Qwen 2.5 Coder 14B', provider: 'lm_studio' },
        { id: 'mistral-7b-instruct-v0.2', name: 'Mistral 7B Instruct v0.2', provider: 'lm_studio' },
        { id: 'deepseek-r1-distill-qwen-14b', name: 'DeepSeek R1 Distill 14B', provider: 'lm_studio' },
        // Ollama models (common ones)
        { id: 'llama3.2', name: 'Llama 3.2', provider: 'ollama' },
        { id: 'mistral', name: 'Mistral', provider: 'ollama' },
        { id: 'phi3', name: 'Phi-3', provider: 'ollama' },
        { id: 'codellama', name: 'Code Llama', provider: 'ollama' }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setIsLoading(true);
      setIsSaved(false); // Reset saved state when starting save

      // Save settings to backend
      const result = await assistantService.saveUserSettings({
        use_defaults: useDefaultSettings,
        provider: useDefaultSettings ? null : localProvider,
        model: useDefaultSettings ? null : localModel,
        custom_api_key: useDefaultSettings ? null : customApiKey,
        api_base: useDefaultSettings ? null : customApiBase
      });

      if (result) {
        setSavedSettings(result);
        setHasCustomApiKey(result.has_custom_api_key);
        setIsSaved(true);
        setHasUnsavedChanges(false);

        // Update parent component with new configuration
        if (handleUpdate) {
          handleUpdate({
            apiKey: (hasApiKeyInSettings || result.has_custom_api_key) ? 'USE_FROM_SETTINGS' : '',
            model: localModel,
            provider: localProvider,
            apiBase: customApiBase
          });
        }

        // Show saved indicator for 2 seconds
        setTimeout(() => setIsSaved(false), 2000);
      }
    } catch (error) {
      console.error('Failed to save settings:', error);
      // Show error message to user
      const errorMessage = error?.message || String(error) || 'Unknown error';
      alert(`Failed to save settings: ${errorMessage}`);
      setIsSaved(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUseDefaultsChange = (checked) => {
    setUseDefaultSettings(checked);
    setHasUnsavedChanges(true);
    setIsSaved(false); // Reset saved state when changing

    if (checked && defaultSettings) {
      // Switch to default settings
      setLocalProvider(defaultSettings.provider || 'google');
      setLocalModel(defaultSettings.model || 'gemini-2.0-flash-exp');
      setCustomApiKey('');
      setHasCustomApiKey(false);
    } else if (savedSettings && !savedSettings.use_defaults) {
      // Load saved custom settings
      setLocalProvider(savedSettings.provider || defaultSettings?.provider || 'google');
      setLocalModel(savedSettings.model || defaultSettings?.model || 'gemini-2.0-flash-exp');
      setHasCustomApiKey(savedSettings.has_custom_api_key);
    } else if (defaultSettings) {
      // No saved custom settings, pre-fill with defaults for editing
      setLocalProvider(defaultSettings.provider || 'google');
      setLocalModel(defaultSettings.model || 'gemini-2.0-flash-exp');
    }

    // Notify parent of temporary change
    if (handleUpdate) {
      handleUpdate({
        apiKey: hasApiKeyInSettings || hasCustomApiKey ? 'USE_FROM_SETTINGS' : '',
        model: localModel,
        provider: localProvider
      });
    }
  };

  const handleProviderChange = (newProvider) => {
    setLocalProvider(newProvider);
    setHasUnsavedChanges(true);
    setIsSaved(false); // Reset saved state when changing

    // Set default API base for local providers
    const provider = providers.find(p => p.id === newProvider);
    if (provider && provider.requiresApiBase) {
      setCustomApiBase(provider.defaultApiBase);
    } else {
      setCustomApiBase('');
    }

    if (handleUpdate) {
      handleUpdate({
        apiKey: hasApiKeyInSettings || hasCustomApiKey ? 'USE_FROM_SETTINGS' : '',
        model: localModel,
        provider: newProvider,
        apiBase: provider?.defaultApiBase || customApiBase
      });
    }
  };

  const handleModelChange = (newModel) => {
    setLocalModel(newModel);
    setHasUnsavedChanges(true);
    setIsSaved(false); // Reset saved state when changing
    if (handleUpdate) {
      handleUpdate({
        apiKey: hasApiKeyInSettings || hasCustomApiKey ? 'USE_FROM_SETTINGS' : '',
        model: newModel,
        provider: localProvider
      });
    }
  };

  const handleApiKeyChange = (e) => {
    setCustomApiKey(e.target.value);
    setHasUnsavedChanges(true);
    setIsSaved(false); // Reset saved state when changing
  };

  const currentProvider = providers.find(p => p.id === localProvider) || providers[0];

  return (
    <div className="space-y-4">
      {/* Unsaved Changes Indicator */}
      {hasUnsavedChanges && (
        <div className="p-2 bg-yellow-50 border border-yellow-200 rounded-md">
          <div className="flex items-center gap-2">
            <ExclamationTriangleIcon className="h-4 w-4 text-yellow-600" />
            <span className="text-sm text-yellow-800">Unsaved changes</span>
          </div>
        </div>
      )}

      {/* Use Default Settings Checkbox */}
      <div className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
        <div className="flex items-center space-x-2">
          <input
            type="checkbox"
            id="use-defaults"
            checked={useDefaultSettings}
            onChange={(e) => handleUseDefaultsChange(e.target.checked)}
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
          />
          <label htmlFor="use-defaults" className="text-sm font-medium text-gray-700">
            Use default settings
          </label>
        </div>
        {useDefaultSettings && defaultSettings && (
          <div className="text-xs text-gray-500">
            {defaultSettings.provider || 'no-provider'} / {defaultSettings.model || 'no-model'}
          </div>
        )}
      </div>


      {/* Provider Selection - Disabled when using defaults */}
      <div>
        <label htmlFor="provider" className="flex items-center gap-1 mb-2 text-sm font-medium text-gray-700">
          <ServerIcon className="h-3 w-3" />
          Provider
        </label>
        <Listbox value={localProvider} onChange={handleProviderChange} disabled={useDefaultSettings}>
          <div className="relative mt-1">
            <Listbox.Button className={`relative w-full cursor-pointer rounded-md border border-gray-300 bg-white py-2 pl-3 pr-10 text-left shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 ${useDefaultSettings ? 'opacity-50 cursor-not-allowed' : ''}`}>
              <span className="block truncate">
                {providers.find(p => p.id === localProvider)?.name || 'Select a provider'}
              </span>
              <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                <ChevronUpDownIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
              </span>
            </Listbox.Button>
            {!useDefaultSettings && (
              <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                {providers.map((p) => (
                  <Listbox.Option
                    key={p.id}
                    value={p.id}
                    className={({ active }) =>
                      `relative cursor-pointer select-none py-2 pl-3 pr-4 ${
                        active ? 'bg-blue-100 text-blue-900' : 'text-gray-900'
                      }`
                    }
                  >
                    <span className="block truncate font-medium">{p.name}</span>
                  </Listbox.Option>
                ))}
              </Listbox.Options>
            )}
          </div>
        </Listbox>
      </div>

      {/* Model Selection - Can be overridden even with defaults */}
      <div>
        <label htmlFor="model" className="flex items-center gap-1 mb-2 text-sm font-medium text-gray-700">
          <CpuChipIcon className="h-3 w-3" />
          Model {!useDefaultSettings && <span className="text-xs text-gray-500 ml-1">(Custom)</span>}
        </label>
        {((currentProvider?.id === 'lm_studio' || currentProvider?.id === 'ollama' || currentProvider?.id === 'deepseek') && filteredModels.length === 0) ? (
          // For providers without predefined models or when DeepSeek has no models, use text input
          <div>
            <input
              type="text"
              value={localModel}
              onChange={(e) => handleModelChange(e.target.value)}
              placeholder={
                currentProvider?.id === 'lm_studio' ? "Enter LM Studio model name" :
                currentProvider?.id === 'ollama' ? "Enter Ollama model name (e.g., llama3.2)" :
                currentProvider?.id === 'deepseek' ? "Enter DeepSeek model (e.g., deepseek-chat, deepseek-r1)" :
                "Enter model name"
              }
              disabled={useDefaultSettings}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
            {currentProvider?.id === 'lm_studio' && (
              <p className="text-xs text-gray-500 mt-1">
                Use the exact model name from LM Studio (e.g., mistral-7b-instruct-v0.2)
              </p>
            )}
            {currentProvider?.id === 'ollama' && (
              <p className="text-xs text-gray-500 mt-1">
                Use the model name from ollama list (e.g., llama3.2, mistral)
              </p>
            )}
            {currentProvider?.id === 'deepseek' && (
              <p className="text-xs text-gray-500 mt-1">
                Common models: deepseek-chat, deepseek-reasoner, deepseek-r1, deepseek-coder, deepseek-r1-distill-qwen-7b
              </p>
            )}
          </div>
        ) : (
          <Listbox value={localModel} onChange={handleModelChange} disabled={useDefaultSettings && !defaultSettings}>
            <div className="relative mt-1">
              <Listbox.Button className="relative w-full cursor-pointer rounded-md border border-gray-300 bg-white py-2 pl-3 pr-10 text-left shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500">
                <span className="block truncate">
                  {filteredModels.find(m => m.id === localModel)?.name || models.find(m => m.id === localModel)?.name || localModel || 'Select a model'}
                </span>
                <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
                  <ChevronUpDownIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
                </span>
              </Listbox.Button>
              <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-base shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none sm:text-sm">
                {filteredModels.length > 0 ? (
                  filteredModels.map((m) => (
                    <Listbox.Option
                      key={m.id}
                      value={m.id}
                      className={({ active }) =>
                        `relative cursor-pointer select-none py-2 pl-3 pr-4 ${
                          active ? 'bg-blue-100 text-blue-900' : 'text-gray-900'
                        }`
                      }
                    >
                      <div>
                        <div className="font-medium">{m.name}</div>
                        {m.description && (
                          <div className="text-xs text-gray-500">{m.description}</div>
                        )}
                      </div>
                    </Listbox.Option>
                  ))
                ) : (
                  <div className="py-2 px-3 text-gray-500 text-sm">
                    No models available for {currentProvider?.name || localProvider}
                  </div>
                )}
              </Listbox.Options>
            </div>
          </Listbox>
        )}
      </div>

      {/* API Key Configuration */}
      <div>
        <label className="flex items-center gap-1 mb-2 text-sm font-medium text-gray-700">
          <KeyIcon className="h-3 w-3" />
          API Key {currentProvider?.requiresApiBase && '(Optional for local models)'}
        </label>
        {useDefaultSettings ? (
          // Show status when using defaults
          hasApiKeyInSettings ? (
            <div className="p-3 bg-green-50 border border-green-200 rounded-md">
              <div className="flex items-center justify-between">
                <p className="text-sm text-green-800">
                  ✓ Using API key from AI Settings
                </p>
                <span className="text-xs text-green-600">Secured</span>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md">
              <p className="text-sm text-yellow-800">
                ⚠️ No API key configured in AI Settings
              </p>
              <p className="text-xs text-gray-600 mt-1">
                Configure in Settings → AI Configuration
              </p>
            </div>
          )
        ) : (
          // Show input field when not using defaults
          <div className="space-y-2">
            {hasApiKeyInSettings && (
              <div className="p-2 bg-blue-50 border border-blue-200 rounded-md text-xs text-blue-800">
                Default API key available from AI Settings
              </div>
            )}
            {hasCustomApiKey && !customApiKey && (
              <div className="p-2 bg-green-50 border border-green-200 rounded-md text-xs text-green-800">
                ✓ Custom API key saved (encrypted)
              </div>
            )}
            <div className="relative">
              <input
                type={showApiKey ? "text" : "password"}
                value={customApiKey}
                onChange={handleApiKeyChange}
                placeholder={hasCustomApiKey ? "••••••••• (saved)" : "Enter custom API key"}
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                {showApiKey ? (
                  <EyeSlashIcon className="h-4 w-4 text-gray-400" />
                ) : (
                  <EyeIcon className="h-4 w-4 text-gray-400" />
                )}
              </button>
            </div>
            <p className="text-xs text-gray-500">
              Leave empty to use default API key from AI Settings
            </p>
          </div>
        )}
      </div>

      {/* API Base URL Configuration for Local Models and DeepSeek */}
      {(currentProvider?.requiresApiBase || currentProvider?.id === 'deepseek') && !useDefaultSettings && (
        <div>
          <label className="flex items-center gap-1 mb-2 text-sm font-medium text-gray-700">
            <ServerIcon className="h-3 w-3" />
            API Base URL {currentProvider?.id === 'deepseek' && '(Optional)'}
          </label>
          <input
            type="text"
            value={customApiBase}
            onChange={(e) => {
              setCustomApiBase(e.target.value);
              setHasUnsavedChanges(true);
              setIsSaved(false);
            }}
            placeholder={currentProvider.defaultApiBase || (currentProvider?.id === 'deepseek' ? 'https://api.deepseek.com/v1' : '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-500 mt-1">
            {currentProvider.id === 'lm_studio' ? 'Default: http://localhost:1234/v1' :
             currentProvider.id === 'ollama' ? 'Default: http://localhost:11434' :
             currentProvider.id === 'deepseek' ? 'Default: https://api.deepseek.com/v1 (leave empty for default)' : ''}
          </p>
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={!hasUnsavedChanges || isLoading || (!useDefaultSettings && !currentProvider?.requiresApiBase && !hasApiKeyInSettings && !customApiKey)}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isLoading ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
            Saving...
          </>
        ) : isSaved ? (
          <>
            <CheckIcon className="h-4 w-4 mr-2" />
            Saved
          </>
        ) : (
          <>
            <CheckIcon className="h-4 w-4 mr-2" />
            Save Configuration
          </>
        )}
      </button>

      {/* Configuration Summary */}
      {!hasUnsavedChanges && (
        <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-600">
          <div className="font-medium mb-1">Current Configuration:</div>
          <div>Provider: {currentProvider?.name || localProvider}</div>
          <div>Model: {filteredModels.find(m => m.id === localModel)?.name || localModel}</div>
          {currentProvider?.requiresApiBase && (
            <div>API Base: {customApiBase || currentProvider.defaultApiBase}</div>
          )}
          <div>API Key: {hasApiKeyInSettings || hasCustomApiKey || currentProvider?.requiresApiBase ? '✓ Configured' : '✗ Not configured'}</div>
        </div>
      )}
    </div>
  );
}

export default ModelConfig;