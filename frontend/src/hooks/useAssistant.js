import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { assistantService } from '../services/assistantService';
import { useAssistantWebSocket } from './useAssistantWebSocket';

const ASSISTANT_STATE_KEY = 'ioflow_assistant_state';

export const useAssistant = () => {
  const { user } = useAuth();

  // Load saved state from localStorage
  const loadSavedState = () => {
    try {
      const savedState = localStorage.getItem(ASSISTANT_STATE_KEY);
      if (savedState) {
        return JSON.parse(savedState);
      }
    } catch (error) {
      console.error('Failed to load saved assistant state:', error);
    }
    return null;
  };

  const savedState = loadSavedState();

  const [agents, setAgents] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState(savedState?.selectedAgent || null);
  const [sessionId, setSessionId] = useState(savedState?.sessionId || null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasConfiguredSettings, setHasConfiguredSettings] = useState(false);

  // Session-based configuration (not persisted to localStorage)
  const [sessionConfig, setSessionConfig] = useState({
    apiKey: '',
    model: 'gemini-2.0-flash-exp',
    provider: 'google',
    isTemporary: false
  });

  // WebSocket hook for streaming - pass saved messages if available
  const {
    messages,
    isStreaming,
    sendMessage,
    cancelExecution,
    clearMessages,
    connectionStatus,
    forceReconnect,
    restoreMessages
  } = useAssistantWebSocket(sessionId);

  // Save state to localStorage whenever it changes
  const saveState = () => {
    try {
      const stateToSave = {
        selectedAgent,
        sessionId,
        messages,
        timestamp: Date.now()
      };
      localStorage.setItem(ASSISTANT_STATE_KEY, JSON.stringify(stateToSave));
    } catch (error) {
      console.error('Failed to save assistant state:', error);
    }
  };

  // Save state when important values change
  useEffect(() => {
    if (selectedAgent && sessionId) {
      saveState();
    }
  }, [selectedAgent, sessionId, messages]);

  // Load available agents and check for existing settings on mount
  useEffect(() => {
    loadAgents();
    checkExistingSettings();

    // Restore messages if we have a saved session
    if (savedState?.messages && savedState.sessionId === sessionId) {
      restoreMessages?.(savedState.messages);
    }
  }, []);

  const checkExistingSettings = async () => {
    try {
      // Check if there are existing assistant settings configured
      const settings = await assistantService.getDefaultSettings();
      if (settings) {
        // Always update model and provider from settings to avoid invalid models
        const modelToUse = settings.assistant_settings?.model || settings.model || 'gemini-2.0-flash-exp';
        const providerToUse = settings.assistant_settings?.provider || settings.provider || 'google';

        // Check if there's an API key configured
        if (settings.has_api_key || (settings.assistant_settings && settings.assistant_settings.has_custom_api_key)) {
          setHasConfiguredSettings(true);
          // Update session config with the loaded settings including API key
          setSessionConfig(prevConfig => ({
            ...prevConfig,
            apiKey: 'USE_FROM_SETTINGS',
            model: modelToUse,
            provider: providerToUse
          }));
        } else {
          // Even without API key, update model and provider to avoid invalid models
          setSessionConfig(prevConfig => ({
            ...prevConfig,
            model: modelToUse,
            provider: providerToUse
          }));
        }
      }
    } catch (error) {
      console.error('Failed to check existing settings:', error);
      // Don't show error for settings check, it's not critical for initial load
    }
  };

  const loadAgents = async () => {
    try {
      setIsLoading(true);
      const agentList = await assistantService.listAgents();
      setAgents(agentList);

      // Auto-select first agent if available
      if (agentList.length > 0 && !selectedAgent) {
        setSelectedAgent(agentList[0]);
        // Create session ID for auto-selected agent to establish WebSocket connection
        if (!sessionId) {
          setSessionId(`session_${Date.now()}`);
        }
      }
    } catch (error) {
      console.error('Failed to load agents:', error);
      setError('Failed to load agents. Please check if the backend is running.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAgentSelect = (agent) => {
    // Only clear messages and create new session if switching to a different agent
    if (!selectedAgent || selectedAgent.id !== agent.id) {
      setSelectedAgent(agent);
      // Clear messages when switching agents
      clearMessages();
      // Create new session for new agent
      setSessionId(`session_${Date.now()}`);
    }
  };

  const handleClearConversation = async () => {
    if (!selectedAgent) return;

    try {
      // Call API to clear backend conversation
      await assistantService.clearConversation(selectedAgent.id);

      // Clear frontend messages
      clearMessages();

      // Create new session
      setSessionId(`session_${Date.now()}`);

      // Clear saved state from localStorage
      localStorage.removeItem(ASSISTANT_STATE_KEY);

      console.log('Conversation cleared for agent:', selectedAgent.id);
    } catch (error) {
      console.error('Failed to clear conversation:', error);
      setError('Failed to clear conversation');
    }
  };

  const handleConfigUpdate = (config) => {
    // Update session configuration
    setSessionConfig(prevConfig => ({
      ...prevConfig,
      ...config,
      isTemporary: true  // Mark as temporary until saved
    }));
    // Mark that settings have been configured if there's an API key
    if (config.apiKey) {
      setHasConfiguredSettings(true);
    }
  };

  const handleSendMessage = async (text) => {
    if (!selectedAgent) {
      setError('Please select an agent first');
      return;
    }

    if (!sessionConfig.apiKey && !hasConfiguredSettings) {
      setError('Please configure your API key in the Settings');
      return;
    }

    // Use existing sessionId or create a new one only if none exists
    // This maintains the same session for conversation continuity
    let currentSessionId = sessionId;
    if (!currentSessionId) {
      currentSessionId = `session_${Date.now()}`;
      setSessionId(currentSessionId);
    }

    // Send message through WebSocket with session configuration
    // The backend will maintain conversation context based on user and agent
    await sendMessage(text, {
      agent_id: selectedAgent.id,
      api_key: sessionConfig.apiKey,
      model: sessionConfig.model,
      provider: sessionConfig.provider,
      api_base: sessionConfig.apiBase
    });
  };

  const handleCancel = () => {
    if (!selectedAgent) {
      console.error('No agent selected for cancellation');
      return;
    }

    // Pass agent_id to cancelExecution for proper identification
    cancelExecution({
      agent_id: selectedAgent.id
    });
  };

  const refreshAgents = () => {
    loadAgents();
  };

  return {
    // State
    agents,
    selectedAgent,
    sessionId,
    isLoading,
    error,
    sessionConfig,
    hasConfiguredSettings,
    messages,
    isStreaming,
    connectionStatus,

    // Actions
    handleAgentSelect,
    handleClearConversation,
    handleConfigUpdate,
    handleSendMessage,
    handleCancel,
    refreshAgents,
    forceReconnect,
    setError
  };
};