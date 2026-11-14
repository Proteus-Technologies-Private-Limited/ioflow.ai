import React, { useState, useEffect } from 'react';
import { Menu, Transition } from '@headlessui/react';
import AssistantChat from './AssistantChat';
import ModelConfig from './ModelConfig';
import { useAssistant } from '../../hooks/useAssistant';
import { useLayout, LAYOUT_MODES } from '../../contexts/LayoutContext';
import { useSidebar } from '../../contexts/SidebarContext';
import {
  ChatBubbleBottomCenterTextIcon,
  SparklesIcon,
  ChevronDownIcon,
  EllipsisVerticalIcon,
  CogIcon,
  ArrowPathIcon,
  SignalIcon,
  SignalSlashIcon,
  XMarkIcon,
  ArrowsPointingInIcon
} from '@heroicons/react/24/outline';

function AssistantPanel({ onClose }) {
  const [showSettings, setShowSettings] = useState(false);
  const { pendingAssistantMessage, setPendingAssistantMessage, setLayoutMode } = useLayout();
  const { setSidebarCollapsed } = useSidebar();

  // Handler to switch to classic layout with expanded navigation
  const handleSwitchToClassicLayout = () => {
    // Switch to classic layout
    setLayoutMode(LAYOUT_MODES.CLASSIC);
    // Expand the navigation sidebar
    setSidebarCollapsed(false);
  };

  const {
    agents,
    selectedAgent,
    isLoading,
    error,
    sessionConfig,
    hasConfiguredSettings,
    messages,
    isStreaming,
    connectionStatus,
    handleAgentSelect,
    handleClearConversation,
    handleConfigUpdate,
    handleSendMessage,
    handleCancel,
    refreshAgents,
    setError
  } = useAssistant();

  // Handle pending message from dashboard or other components
  useEffect(() => {
    if (pendingAssistantMessage && !isStreaming && !isLoading) {
      const { message, agentId } = typeof pendingAssistantMessage === 'object'
        ? pendingAssistantMessage
        : { message: pendingAssistantMessage, agentId: null };

      // Wait for agents to load if agentId is specified
      if (agentId && agents.length === 0) {
        return; // Wait for agents to load
      }

      // First, select the correct agent if specified
      if (agentId && agents.length > 0) {
        const targetAgent = agents.find(a => a.id === agentId) ||
                           agents.find(a => a.id === 'ioflow_analyst'); // fallback
        if (targetAgent && (!selectedAgent || selectedAgent.id !== targetAgent.id)) {
          handleAgentSelect(targetAgent);
          // Wait for agent selection to complete before sending
          return;
        }
      }

      // Send the message once agent is selected
      if (selectedAgent) {
        handleSendMessage(message);
        setPendingAssistantMessage(null);
      }
    }
  }, [pendingAssistantMessage, selectedAgent, agents, isStreaming, isLoading, handleAgentSelect, handleSendMessage, setPendingAssistantMessage]);

  const getAgentIcon = (type) => {
    if (type === 'python') return '🐍';
    if (type === 'json') return '📄';
    return '✨';
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full bg-white">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="h-full bg-white flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 bg-white border-b border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <ChatBubbleBottomCenterTextIcon className="h-5 w-5 text-primary-600" />
            <h2 className="text-lg font-semibold text-gray-900">Assistant</h2>
          </div>

          <div className="flex items-center space-x-2">
            {/* Connection Status */}
            <div className="flex items-center">
              {connectionStatus === 'connected' ? (
                <SignalIcon className="h-4 w-4 text-green-500" title="Connected" />
              ) : connectionStatus === 'connecting' ? (
                <SignalIcon className="h-4 w-4 text-yellow-500 animate-pulse" title="Connecting..." />
              ) : (
                <SignalSlashIcon className="h-4 w-4 text-red-500" title="Disconnected" />
              )}
            </div>

            {/* Settings Button */}
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
              title="Settings"
            >
              <CogIcon className="h-5 w-5" />
            </button>

            {/* Switch to Classic Layout Button */}
            <button
              onClick={handleSwitchToClassicLayout}
              className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
              title="Switch to Classic Layout"
            >
              <ArrowsPointingInIcon className="h-5 w-5" />
            </button>

            {/* Close Button (for mobile) */}
            {onClose && (
              <button
                onClick={onClose}
                className="p-1 text-gray-400 hover:text-gray-600 transition-colors lg:hidden"
                title="Close"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            )}
          </div>
        </div>

        {/* Agent Selector */}
        <div className="mt-3 flex items-center justify-between">
          <Menu as="div" className="relative flex-1">
            <Menu.Button className="w-full flex items-center justify-between px-3 py-2 text-sm bg-gray-50 border border-gray-200 rounded-md hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 transition-colors">
              {selectedAgent ? (
                <>
                  <div className="flex items-center space-x-2">
                    <span>{getAgentIcon(selectedAgent.type)}</span>
                    <span className="text-gray-700 font-medium truncate">
                      {selectedAgent.name}
                    </span>
                  </div>
                  <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                </>
              ) : (
                <>
                  <span className="text-gray-500">Select an agent</span>
                  <ChevronDownIcon className="h-4 w-4 text-gray-400" />
                </>
              )}
            </Menu.Button>

            <Transition
              as={React.Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute z-50 mt-1 w-full bg-white border border-gray-200 rounded-md shadow-lg max-h-60 overflow-auto focus:outline-none">
                {agents.map((agent) => (
                  <Menu.Item key={agent.id}>
                    {({ active }) => (
                      <button
                        onClick={() => handleAgentSelect(agent)}
                        className={`${
                          active ? 'bg-gray-100' : ''
                        } ${
                          selectedAgent?.id === agent.id ? 'bg-primary-50' : ''
                        } flex items-center w-full px-3 py-2 text-sm transition-colors`}
                      >
                        <span className="mr-2">{getAgentIcon(agent.type)}</span>
                        <div className="text-left">
                          <div className="font-medium text-gray-900">
                            {agent.name}
                          </div>
                          {agent.description && (
                            <div className="text-xs text-gray-500 truncate">
                              {agent.description}
                            </div>
                          )}
                        </div>
                      </button>
                    )}
                  </Menu.Item>
                ))}
              </Menu.Items>
            </Transition>
          </Menu>

          {/* Actions Menu */}
          <Menu as="div" className="relative ml-2">
            <Menu.Button className="p-1 text-gray-400 hover:text-gray-600 transition-colors">
              <EllipsisVerticalIcon className="h-5 w-5" />
            </Menu.Button>

            <Transition
              as={React.Fragment}
              enter="transition ease-out duration-100"
              enterFrom="transform opacity-0 scale-95"
              enterTo="transform opacity-100 scale-100"
              leave="transition ease-in duration-75"
              leaveFrom="transform opacity-100 scale-100"
              leaveTo="transform opacity-0 scale-95"
            >
              <Menu.Items className="absolute right-0 z-50 mt-1 w-48 bg-white border border-gray-200 rounded-md shadow-lg focus:outline-none">
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={handleClearConversation}
                      className={`${
                        active ? 'bg-gray-100' : ''
                      } flex items-center w-full px-3 py-2 text-sm text-gray-700 transition-colors`}
                      disabled={!selectedAgent}
                    >
                      Clear Conversation
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      onClick={refreshAgents}
                      className={`${
                        active ? 'bg-gray-100' : ''
                      } flex items-center w-full px-3 py-2 text-sm text-gray-700 transition-colors`}
                    >
                      <ArrowPathIcon className="h-4 w-4 mr-2" />
                      Refresh Agents
                    </button>
                  )}
                </Menu.Item>
              </Menu.Items>
            </Transition>
          </Menu>
        </div>
      </div>

      {/* Settings Panel (Slide-over) */}
      {showSettings && (
        <div className="absolute inset-0 z-40 bg-white">
          <div className="h-full flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Settings</h3>
              <button
                onClick={() => setShowSettings(false)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <ModelConfig
                config={sessionConfig}
                onConfigUpdate={handleConfigUpdate}
                onClose={() => setShowSettings(false)}
              />
            </div>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="mx-4 mt-2 p-3 bg-red-50 border border-red-200 rounded-md">
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={() => setError(null)}
            className="text-xs text-red-500 hover:text-red-700 mt-1"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Chat Area */}
      <div className="flex-1 overflow-hidden">
        {selectedAgent ? (
          <AssistantChat
            messages={messages}
            isStreaming={isStreaming}
            onSendMessage={handleSendMessage}
            onCancel={handleCancel}
            disabled={!selectedAgent || (!sessionConfig.apiKey && !hasConfiguredSettings)}
            placeholder={
              !sessionConfig.apiKey && !hasConfiguredSettings
                ? 'Please configure your API key in Settings...'
                : 'Type your message...'
            }
          />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <SparklesIcon className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p>Select an agent to start chatting</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AssistantPanel;