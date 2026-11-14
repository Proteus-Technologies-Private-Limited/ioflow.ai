/**
 * Service for IOFlow Assistant API interactions
 */
class AssistantService {
  constructor() {
    this.baseUrl = '/api/assistant';
  }

  async getHeaders() {
    // Try both 'access_token' (new) and 'token' (legacy) for compatibility
    const token = localStorage.getItem('access_token') || localStorage.getItem('token');
    console.log('AssistantService: Token from localStorage:', token ? `Bearer ${token.substring(0, 20)}...` : 'NO TOKEN');
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : ''
    };
  }

  async handleResponse(response) {
    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Request failed' }));
      throw new Error(error.message || `HTTP error! status: ${response.status}`);
    }
    return response.json();
  }
  /**
   * List all available agents
   */
  async listAgents() {
    const response = await fetch(`${this.baseUrl}/agents`, {
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }

  /**
   * Get information about a specific agent
   */
  async getAgent(agentId) {
    const response = await fetch(`${this.baseUrl}/agents/${agentId}`, {
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }

  /**
   * Execute an agent with configuration
   */
  async executeAgent(data) {
    const response = await fetch(`${this.baseUrl}/execute`, {
      method: 'POST',
      headers: await this.getHeaders(),
      body: JSON.stringify(data)
    });
    return this.handleResponse(response);
  }

  /**
   * Cancel an active execution
   */
  async cancelExecution(sessionId) {
    const response = await fetch(`${this.baseUrl}/cancel/${sessionId}`, {
      method: 'POST',
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }

  /**
   * Get session status
   */
  async getSessionStatus(sessionId) {
    const response = await fetch(`${this.baseUrl}/session/${sessionId}`, {
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }

  /**
   * List active sessions
   */
  async listActiveSessions() {
    const response = await fetch(`${this.baseUrl}/sessions/active`, {
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }

  /**
   * Get session history
   */
  async getSessionHistory(limit = 50) {
    const response = await fetch(`${this.baseUrl}/sessions/history?limit=${limit}`, {
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }

  /**
   * Clear conversation history for a specific agent
   */
  async clearConversation(agentId) {
    const response = await fetch(`${this.baseUrl}/clear-conversation`, {
      method: 'POST',
      headers: await this.getHeaders(),
      body: JSON.stringify({ agent_id: agentId })
    });
    return this.handleResponse(response);
  }

  /**
   * List available models
   */
  async listModels() {
    const response = await fetch(`${this.baseUrl}/models`, {
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }

  /**
   * Get default assistant settings from AI settings
   */
  async getDefaultSettings() {
    console.log('AssistantService: Fetching default settings...');
    try {
      const url = `${this.baseUrl}/default-settings`;
      const headers = await this.getHeaders();
      console.log('AssistantService: Request URL:', url);
      console.log('AssistantService: Request headers:', headers);

      const response = await fetch(url, {
        headers: headers
      });

      console.log('AssistantService: Response status:', response.status);
      const data = await this.handleResponse(response);
      console.log('AssistantService: Response data:', data);
      return data;
    } catch (error) {
      console.error('AssistantService: Failed to fetch default settings:', error);
      return null;
    }
  }

  /**
   * Save user's assistant-specific settings
   */
  async saveUserSettings(settings) {
    const response = await fetch(`${this.baseUrl}/save-settings`, {
      method: 'POST',
      headers: await this.getHeaders(),
      body: JSON.stringify(settings)
    });
    return this.handleResponse(response);
  }

  /**
   * Get user's saved assistant settings
   */
  async getUserSettings() {
    try {
      const response = await fetch(`${this.baseUrl}/user-settings`, {
        headers: await this.getHeaders()
      });
      return this.handleResponse(response);
    } catch (error) {
      console.error('Failed to fetch user settings:', error);
      return null;
    }
  }

  /**
   * Check assistant health
   */
  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/health`, {
      headers: await this.getHeaders()
    });
    return this.handleResponse(response);
  }
}

export const assistantService = new AssistantService();
export default assistantService;