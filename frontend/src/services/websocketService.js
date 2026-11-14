/**
 * WebSocket Service for real-time execution updates
 */
class WebSocketService {
  constructor() {
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 5000; // 5 seconds
    this.listeners = new Map();
    this.subscriptions = new Set();
    this.isConnecting = false;
    this.connectionPromise = null;
  }

  /**
   * Connect to WebSocket server
   * @param {string} token - Authentication token
   * @returns {Promise<void>}
   */
  async connect(token) {
    console.log('websocketService.connect() called with token:', token?.substring(0, 20) + '...');
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      console.log('WebSocket already open, returning');
      return Promise.resolve();
    }

    if (this.isConnecting && this.connectionPromise) {
      console.log('Already connecting, returning existing promise');
      return this.connectionPromise;
    }

    console.log('Starting new WebSocket connection');
    this.isConnecting = true;
    
    this.connectionPromise = new Promise((resolve, reject) => {
      const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/executions?token=${encodeURIComponent(token)}`;
      
      console.log('Connecting to WebSocket:', wsUrl);
      
      // Add connection timeout
      const timeout = setTimeout(() => {
        console.error('WebSocket connection timeout after 10 seconds');
        if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
          this.ws.close();
        }
        this.isConnecting = false;
        reject(new Error('WebSocket connection timeout'));
      }, 10000);
      
      try {
        this.ws = new WebSocket(wsUrl);
        console.log('WebSocket object created, readyState:', this.ws.readyState);
      } catch (error) {
        console.error('Failed to create WebSocket:', error);
        clearTimeout(timeout);
        this.isConnecting = false;
        reject(error);
        return;
      }

      this.ws.onopen = () => {
        clearTimeout(timeout); // Clear the connection timeout
        console.log('WebSocket connected');
        console.log('WebSocket readyState:', this.ws.readyState);
        console.log('WebSocket URL:', this.ws.url);
        this.reconnectAttempts = 0;
        this.isConnecting = false;
        
        // Emit connection event
        this.emit('connection', { connected: true });
        
        // Resubscribe to all previous subscriptions
        // Note: We send the subscription message directly here to avoid 
        // re-adding to the subscriptions set
        console.log('Resubscribing to', this.subscriptions.size, 'executions');
        this.subscriptions.forEach(executionId => {
          console.log('Resubscribing to execution:', executionId);
          this.send({
            action: 'subscribe',
            execution_id: executionId
          });
        });
        
        resolve();
      };

      this.ws.onmessage = (event) => {
        console.log('WebSocket message received:', event.data);
        try {
          const message = JSON.parse(event.data);
          console.log('Parsed message:', message);
          this.handleMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        clearTimeout(timeout);
        console.error('WebSocket error:', error);
        console.error('WebSocket error type:', error.type);
        console.error('WebSocket readyState:', this.ws.readyState);
        console.error('WebSocket URL:', this.ws.url);
        this.isConnecting = false;
        reject(error);
      };

      this.ws.onclose = (event) => {
        clearTimeout(timeout);
        console.log('WebSocket closed:', event.code, event.reason);
        this.isConnecting = false;
        this.ws = null;
        
        // Emit disconnect event
        this.emit('disconnect', { connected: false });
        
        // Attempt to reconnect if not a normal closure
        if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
          
          setTimeout(() => {
            const authToken = localStorage.getItem('access_token');
            if (authToken) {
              this.connect(authToken);
            }
          }, this.reconnectInterval * this.reconnectAttempts);
        }
      };
    });

    return this.connectionPromise;
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect() {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.listeners.clear();
    this.subscriptions.clear();
  }

  /**
   * Subscribe to execution updates
   * @param {string} executionId - Execution ID to subscribe to
   */
  subscribe(executionId) {
    console.log('subscribe() called for execution:', executionId);
    console.log('WebSocket state:', this.ws ? this.ws.readyState : 'null');
    console.log('WebSocket.OPEN constant:', WebSocket.OPEN);
    
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, queuing subscription:', executionId);
      this.subscriptions.add(executionId);
      return;
    }

    console.log('WebSocket is open, subscribing to:', executionId);
    this.subscriptions.add(executionId);
    const message = {
      action: 'subscribe',
      execution_id: executionId
    };
    console.log('Sending subscription message:', message);
    this.send(message);
  }

  /**
   * Unsubscribe from execution updates
   * @param {string} executionId - Execution ID to unsubscribe from
   */
  unsubscribe(executionId) {
    this.subscriptions.delete(executionId);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.send({
        action: 'unsubscribe',
        execution_id: executionId
      });
    }
  }

  /**
   * Subscribe to all tenant executions
   */
  subscribeTenant() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, cannot subscribe to tenant');
      return;
    }

    this.send({
      action: 'subscribe_tenant'
    });
  }

  /**
   * Unsubscribe from tenant-wide updates
   */
  unsubscribeTenant() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.send({
        action: 'unsubscribe_tenant'
      });
    }
  }

  /**
   * Send a message to the server
   * @param {object} data - Data to send
   */
  send(data) {
    console.log('send() called with data:', data);
    console.log('WebSocket state in send():', this.ws ? this.ws.readyState : 'null');
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const jsonData = JSON.stringify(data);
      console.log('Sending WebSocket message:', jsonData);
      this.ws.send(jsonData);
    } else {
      console.warn('WebSocket not connected, cannot send message:', data);
    }
  }

  /**
   * Handle incoming messages
   * @param {object} message - Received message
   */
  handleMessage(message) {
    const { type, execution_id, data } = message;

    // Emit to specific execution listeners
    if (execution_id) {
      this.emit(`execution:${execution_id}`, message);
    }

    // Emit to type-specific listeners
    this.emit(type, message);

    // Emit to global listeners
    this.emit('message', message);
  }

  /**
   * Add event listener
   * @param {string} event - Event name
   * @param {function} callback - Callback function
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
  }

  /**
   * Remove event listener
   * @param {string} event - Event name
   * @param {function} callback - Callback function
   */
  off(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  /**
   * Emit an event
   * @param {string} event - Event name
   * @param {any} data - Event data
   */
  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
  }

  /**
   * Check if connected
   * @returns {boolean}
   */
  isConnected() {
    return this.ws && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Send ping to keep connection alive
   */
  ping() {
    this.send({ action: 'ping' });
  }
}

// Create singleton instance
const websocketService = new WebSocketService();

// Set up ping interval to keep connection alive
setInterval(() => {
  if (websocketService.isConnected()) {
    websocketService.ping();
  }
}, 30000); // Ping every 30 seconds

export default websocketService;