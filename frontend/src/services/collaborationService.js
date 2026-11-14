/**
 * Collaboration Service for real-time flow editing
 */
class CollaborationService {
  constructor() {
    this.ws = null;
    this.sessionId = null;
    this.participantId = null;
    this.isConnected = false;
    this.listeners = new Map();
    this.participants = new Map();
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 3000;
    this.connectionPromise = null;
  }

  /**
   * Create a new collaboration session
   */
  async createSession(flowId, options = {}) {
    const token = localStorage.getItem('access_token');
    // Get the current origin (protocol + host + port)
    const currentOrigin = window.location.origin;
    
    const response = await fetch(`/api/v1/collaborate/flows/${flowId}/invite`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        duration_hours: options.durationHours || 24,
        allow_anonymous: options.allowAnonymous !== false,
        max_participants: options.maxParticipants || 10,
        enable_chat: options.enableChat !== false,
        enable_voice: options.enableVoice || false,
        enable_video: options.enableVideo || false,
        origin_url: currentOrigin  // Send current browser origin
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to create collaboration session: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Get session details by token
   */
  async getSessionByToken(token) {
    const response = await fetch(`/api/v1/collaborate/join/${token}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get session details: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Join a collaboration session
   */
  async joinSession(sessionId, options = {}) {
    const authToken = localStorage.getItem('access_token');
    const headers = {
      'Content-Type': 'application/json'
    };
    
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`;
    }

    const params = new URLSearchParams();
    if (options.token) {
      params.append('token', options.token);
    }

    const url = `/api/v1/collaborate/session/${sessionId}/join${params.toString() ? '?' + params.toString() : ''}`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        display_name: options.displayName || 'Anonymous',
        role: options.role || 'editor'
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to join session: ${response.statusText}`);
    }

    const result = await response.json();
    this.sessionId = sessionId;
    this.participantId = result.participant_id;
    
    return result;
  }

  /**
   * Connect to collaboration WebSocket
   */
  async connect(sessionId, token) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('Collaboration WebSocket already connected');
      return Promise.resolve();
    }

    if (this.connectionPromise) {
      return this.connectionPromise;
    }

    this.connectionPromise = new Promise((resolve, reject) => {
      const params = new URLSearchParams({
        token: token || localStorage.getItem('access_token')
      });
      
      if (this.participantId) {
        params.append('participant_id', this.participantId);
      }

      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/collaborate/ws/${sessionId}?${params}`;
      
      console.log('Connecting to collaboration WebSocket:', wsUrl);
      
      const timeout = setTimeout(() => {
        if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
          this.ws.close();
        }
        reject(new Error('WebSocket connection timeout'));
      }, 10000);

      try {
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
          clearTimeout(timeout);
          console.log('Collaboration WebSocket connected');
          this.isConnected = true;
          this.reconnectAttempts = 0;
          this.sessionId = sessionId;
          this.connectionPromise = null; // Reset connection promise
          
          // Emit connection event
          this.emit('connected', { sessionId });
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Failed to parse collaboration message:', error);
          }
        };

        this.ws.onerror = (error) => {
          clearTimeout(timeout);
          console.error('Collaboration WebSocket error:', error);
          this.connectionPromise = null; // Reset connection promise
          reject(error);
        };

        this.ws.onclose = (event) => {
          clearTimeout(timeout);
          console.log('Collaboration WebSocket closed:', event.code, event.reason);
          this.isConnected = false;
          this.ws = null;
          this.connectionPromise = null; // Reset connection promise
          
          // Emit disconnect event
          this.emit('disconnected', { sessionId });
          
          // Attempt to reconnect if not a normal closure
          if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
            
            setTimeout(() => {
              this.connect(sessionId, token);
            }, this.reconnectInterval * this.reconnectAttempts);
          }
        };
      } catch (error) {
        clearTimeout(timeout);
        this.connectionPromise = null; // Reset connection promise
        reject(error);
      }
    });

    return this.connectionPromise;
  }

  /**
   * Disconnect from collaboration session
   */
  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.isConnected = false;
    this.sessionId = null;
    this.participantId = null;
    this.participants.clear();
    this.listeners.clear();
  }

  /**
   * Send a message to the collaboration server
   */
  send(type, data) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('Collaboration WebSocket not connected');
      return;
    }

    const message = {
      type,
      ...data
    };

    this.ws.send(JSON.stringify(message));
  }

  /**
   * Send a flow operation
   */
  sendOperation(operation) {
    console.log('Sending operation:', operation);
    this.send('operation', { data: operation });
  }

  /**
   * Send cursor position
   */
  sendCursorPosition(position) {
    this.send('cursor_move', { position });
  }

  /**
   * Send selection change
   */
  sendSelectionChange(selection) {
    this.send('selection_change', { selection });
  }

  /**
   * Send chat message
   */
  sendChatMessage(content, mentions = [], nodeReferences = []) {
    this.send('chat_message', {
      content,
      mentions,
      node_references: nodeReferences
    });
  }

  /**
   * Handle incoming messages
   */
  handleMessage(message) {
    const { type } = message;
    console.log('Collaboration message received:', type, message);

    switch (type) {
      case 'session_state':
        this.handleSessionState(message);
        break;
      
      case 'participant_joined':
        this.handleParticipantJoined(message.participant);
        break;
      
      case 'participant_left':
        this.handleParticipantLeft(message.participant);
        break;
      
      case 'operation':
        console.log('Received operation:', message.event);
        this.emit('operation', message.event);
        break;
      
      case 'cursor_move':
        this.emit('cursor_move', message);
        break;
      
      case 'selection_change':
        this.emit('selection_change', message);
        break;
      
      case 'chat_message':
        this.emit('chat_message', message.message);
        break;
      
      case 'error':
        console.error('Collaboration error:', message.message);
        this.emit('error', message);
        break;
      
      default:
        console.log('Unknown collaboration message type:', type);
    }
  }

  /**
   * Handle session state
   */
  handleSessionState(message) {
    const { state, participants } = message;
    
    // Update participants map
    this.participants.clear();
    participants.forEach(participant => {
      this.participants.set(participant.id, participant);
    });
    
    // Emit session state event
    this.emit('session_state', { state, participants });
  }

  /**
   * Handle participant joined
   */
  handleParticipantJoined(participant) {
    this.participants.set(participant.id, participant);
    this.emit('participant_joined', participant);
  }

  /**
   * Handle participant left
   */
  handleParticipantLeft(participant) {
    this.participants.delete(participant.id);
    this.emit('participant_left', participant);
  }

  /**
   * Get active participants
   */
  getParticipants() {
    return Array.from(this.participants.values());
  }

  /**
   * Get participant by ID
   */
  getParticipant(participantId) {
    return this.participants.get(participantId);
  }

  /**
   * Leave the current session
   */
  async leaveSession() {
    if (!this.sessionId || !this.participantId) {
      return;
    }

    const token = localStorage.getItem('access_token');
    const headers = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    try {
      await fetch(`/api/v1/collaborate/session/${this.sessionId}/leave`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          participant_id: this.participantId
        })
      });
    } catch (error) {
      console.error('Failed to leave session:', error);
    }

    this.disconnect();
  }

  /**
   * Create an invite for the session
   */
  async createInvite(options = {}) {
    if (!this.sessionId) {
      throw new Error('No active session');
    }

    const token = localStorage.getItem('access_token');
    // Get the current origin (protocol + host + port)
    const currentOrigin = window.location.origin;
    
    const response = await fetch(`/api/v1/collaborate/session/${this.sessionId}/invite`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        email: options.email,
        role: options.role || 'editor',
        expires_hours: options.expiresHours || 24,
        max_uses: options.maxUses || 1,
        origin_url: currentOrigin  // Send current browser origin
      })
    });

    if (!response.ok) {
      throw new Error(`Failed to create invite: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Get session participants
   */
  async getSessionParticipants() {
    if (!this.sessionId) {
      throw new Error('No active session');
    }

    const token = localStorage.getItem('access_token');
    const response = await fetch(`/api/v1/collaborate/session/${this.sessionId}/participants`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to get participants: ${response.statusText}`);
    }

    return await response.json();
  }

  /**
   * Add event listener
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
  }

  /**
   * Remove event listener
   */
  off(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  /**
   * Emit an event
   */
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in collaboration event listener for ${event}:`, error);
        }
      });
    }
  }

  /**
   * Check if connected
   */
  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }
}

// Export singleton instance
const collaborationService = new CollaborationService();
export default collaborationService;