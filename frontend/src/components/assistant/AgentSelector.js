import React from 'react';
import {
  ArrowPathIcon,
  CodeBracketIcon,
  DocumentTextIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';

function AgentSelector({ agents, selectedAgent, onSelectAgent, onRefresh }) {
  const getAgentIcon = (type) => {
    if (type === 'python') return <CodeBracketIcon className="h-4 w-4" />;
    if (type === 'json') return <DocumentTextIcon className="h-4 w-4" />;
    return <SparklesIcon className="h-4 w-4" />;
  };

  const getAgentTypeLabel = (type) => {
    if (type === 'python') return 'Python Agent';
    if (type === 'json') return 'JSON Config';
    return 'Agent';
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium">Available Agents</h3>
        <button
          onClick={onRefresh}
          className="p-1 rounded hover:bg-gray-100 transition-colors"
        >
          <ArrowPathIcon className="h-4 w-4" />
        </button>
      </div>

      <div className="h-[400px] w-full rounded-md border border-gray-200 overflow-y-auto">
        <div className="p-2 space-y-1">
          {agents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <SparklesIcon className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No agents found</p>
              <p className="text-xs mt-1">Check backend configuration</p>
            </div>
          ) : (
            agents.map((agent) => (
              <button
                key={agent.id}
                onClick={() => onSelectAgent(agent)}
                className={`w-full text-left p-3 rounded-lg transition-colors ${
                  selectedAgent?.id === agent.id
                    ? 'bg-blue-50 border border-blue-300'
                    : 'hover:bg-gray-50 border border-transparent'
                }`}
              >
                <div className="flex items-start gap-2">
                  <div className={`mt-0.5 ${
                    selectedAgent?.id === agent.id ? 'text-blue-600' : 'text-gray-500'
                  }`}>
                    {getAgentIcon(agent.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {agent.name}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {getAgentTypeLabel(agent.type)}
                    </div>
                    {agent.description && (
                      <div className="text-xs text-gray-600 mt-1 line-clamp-2">
                        {agent.description}
                      </div>
                    )}
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {selectedAgent && (
        <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
          <div className="text-xs font-medium text-blue-700 mb-1">
            Selected Agent
          </div>
          <div className="text-sm font-medium">{selectedAgent.name}</div>
          <div className="text-xs text-blue-600 mt-0.5">
            ID: {selectedAgent.id}
          </div>
        </div>
      )}
    </div>
  );
}

export default AgentSelector;