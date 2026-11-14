import React from 'react';

const AgentSelector = ({ agents, selectedAgent, onSelectAgent }) => {
  return (
    <div className="mb-6">
      <label htmlFor="agent-select" className="block text-sm font-medium text-gray-700 mb-2">
        Select an Agent
      </label>
      <select
        id="agent-select"
        value={selectedAgent?.id || ''}
        onChange={(e) => {
          const agent = agents.find(a => a.id === e.target.value);
          onSelectAgent(agent);
        }}
        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      >
        <option value="">Choose an agent...</option>
        {agents.map((agent) => (
          <option key={agent.id} value={agent.id}>
            {agent.name} - {agent.description}
          </option>
        ))}
      </select>

      {selectedAgent && (
        <div className="mt-4 p-4 bg-blue-50 rounded-lg">
          <h3 className="font-semibold text-blue-900">
            {selectedAgent.name}
            {selectedAgent.isLoaded && (
              <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                Loaded in Memory
              </span>
            )}
          </h3>
          <p className="text-blue-700 text-sm mt-1">{selectedAgent.description}</p>
          <p className="text-blue-600 text-xs mt-2">Model: {selectedAgent.model}</p>
        </div>
      )}
    </div>
  );
};

export default AgentSelector;