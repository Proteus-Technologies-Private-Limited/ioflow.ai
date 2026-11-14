import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:7001';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const agentService = {
  // List all available agents
  listAgents: async () => {
    const response = await api.get('/agents');
    return response.data;
  },

  // Get details of a specific agent
  getAgent: async (agentId) => {
    const response = await api.get(`/agents/${agentId}`);
    return response.data;
  },

  // Execute an agent with input
  executeAgent: async (agentId, userInput, apiKey = null) => {
    const response = await api.post(`/agents/${agentId}/run`, {
      input: userInput,
      user_id: null,
      session_id: null,
      api_key: apiKey,
    });
    return response.data;
  },

  // Health check
  healthCheck: async () => {
    const response = await api.get('/');
    return response.data;
  },

  // Unload all agents from memory
  unloadAllAgents: async () => {
    const response = await api.delete('/agents/unload-all');
    return response.data;
  },

  // Get loaded agents
  getLoadedAgents: async () => {
    const response = await api.get('/agents/loaded');
    return response.data;
  },
};

export default api;