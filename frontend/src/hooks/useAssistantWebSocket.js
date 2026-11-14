import { useEffect, useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * React hook for WebSocket integration with IOFlow Assistant
 * @param {string} sessionId - Session ID for the conversation
 * @returns {object} WebSocket state and methods
 */
export function useAssistantWebSocket(sessionId) {
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('');
  const [currentExecutionSteps, setCurrentExecutionSteps] = useState([]);
  const [allStreamedContent, setAllStreamedContent] = useState([]); // Store all streamed content

  const navigate = useNavigate();
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const sessionIdRef = useRef(sessionId);
  const currentStreamingMessageRef = useRef('');
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 10;
  const isManuallyClosedRef = useRef(false);
  const lastActivityTimeRef = useRef(Date.now());
  const messageQueueRef = useRef([]); // Queue messages during reconnection

  // Update session ID ref when it changes
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  // Update streaming message ref when it changes
  useEffect(() => {
    currentStreamingMessageRef.current = currentStreamingMessage;
  }, [currentStreamingMessage]);

  // Connect to WebSocket with improved error handling
  const connect = useCallback(() => {
    if (!sessionId) return;

    // Don't reconnect if manually closed
    if (isManuallyClosedRef.current) {
      console.log('WebSocket manually closed, not reconnecting');
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use window.location.host to go through NGINX proxy in production
    // In development (localhost), explicitly use port 7001
    const host = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
      ? `${window.location.hostname}:7001`
      : window.location.host;
    const wsUrl = `${protocol}//${host}/api/assistant/ws/${sessionId}`;

    console.log('Connecting to WebSocket:', wsUrl, 'Attempt:', reconnectAttemptsRef.current + 1);
    setConnectionStatus('connecting');

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0; // Reset reconnect attempts on successful connection

        // Process any queued messages
        while (messageQueueRef.current.length > 0) {
          const queuedMessage = messageQueueRef.current.shift();
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(queuedMessage));
          }
        }

        // Send ping to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
            lastActivityTimeRef.current = Date.now();
          } else {
            clearInterval(pingInterval);
          }
        }, 30000);

        ws.pingInterval = pingInterval;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          handleMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
      };

      ws.onclose = (event) => {
        console.log('WebSocket closed', event.code, event.reason);
        setConnectionStatus('disconnected');

        // Clear ping interval
        if (ws.pingInterval) {
          clearInterval(ws.pingInterval);
        }

        // Only attempt reconnect if not manually closed and within attempt limits
        if (!isManuallyClosedRef.current &&
            sessionIdRef.current === sessionId &&
            reconnectAttemptsRef.current < maxReconnectAttempts) {

          reconnectAttemptsRef.current++;

          // Exponential backoff with jitter
          const baseDelay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          const jitter = Math.random() * 1000;
          const reconnectDelay = baseDelay + jitter;

          console.log(`Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectDelay);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          console.error('Max reconnection attempts reached');
          setConnectionStatus('error');
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      setConnectionStatus('error');
    }
  }, [sessionId]);

  // Function to extract markdown links from text
  const extractMarkdownLinks = (text) => {
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    const links = [];
    let match;
    while ((match = linkRegex.exec(text)) !== null) {
      links.push({
        text: match[1],
        url: match[2]
      });
    }
    return links;
  };

  // Function to check if a link should trigger auto-navigation
  const shouldAutoNavigate = (link) => {
    // Auto-navigate for internal flow designer links or other internal routes
    const internalPatterns = [
      /^\/flow-designer/,
      /^\/flows\//,
      /flowId=/
    ];

    return internalPatterns.some(pattern => pattern.test(link.url));
  };

  // Handle incoming messages
  const handleMessage = useCallback((data) => {
    const { type } = data;

    switch (type) {
      case 'pong':
        // Ignore pong messages
        break;

      case 'message_received':
        // User message acknowledged
        break;

      case 'stream_event':
        // Handle streaming event
        const eventData = data.data;
        if (!eventData) break;

        // Check if this is a cancellation event
        if (eventData.type === 'cancelled') {
          // Handle cancellation from stream
          console.log('Stream cancelled');

          // Remove any existing streaming message and thinking messages
          setMessages(prev => prev.filter(msg => !msg.isStreaming && !msg.isThinking));

          // Add clear cancellation message
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: '🛑 **Execution cancelled by user**',
            isCancelled: true,
            executionSteps: currentExecutionSteps.length > 0 ? [...currentExecutionSteps] : undefined,
            timestamp: new Date().toISOString()
          }]);

          setIsStreaming(false);
          setCurrentStreamingMessage('');
          currentStreamingMessageRef.current = '';
          setCurrentExecutionSteps([]);
          setAllStreamedContent([]);
          break;
        }

        // Check if this is an error event
        if (eventData.type === 'error') {
          // Handle error from stream
          console.error('Stream error:', eventData);
          const errorMessage = eventData.error || eventData.message || 'An error occurred';

          // Add error to stream history
          setAllStreamedContent(prev => [...prev, {
            type: 'error',
            content: `❌ Error: ${errorMessage}`,
            timestamp: new Date().toISOString()
          }]);

          // Don't stop streaming yet - let execution_complete handle final state
          break;
        }

        // Handle different types of events
        if (eventData.event_type === 'tool_call' && eventData.tool_calls) {
          // Add each tool call as a separate message immediately when it starts
          eventData.tool_calls.forEach(call => {
            const args = typeof call.args === 'object' ? JSON.stringify(call.args) : call.args;
            const startTime = new Date().toISOString();

            // Add tool call as a message immediately
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: `Calling ${call.name}...`,
              isToolCall: true,
              toolData: {
                type: 'call',
                name: call.name,
                args: call.args,
                startTime: startTime
              },
              timestamp: startTime
            }]);

            // Also store in execution steps for final message
            const toolStep = {
              type: 'tool_call',
              name: call.name,
              args: call.args,
              timestamp: eventData.timestamp || new Date().toISOString()
            };
            setCurrentExecutionSteps(prev => [...prev, toolStep]);
          });

          // Add to stream history
          const toolCallText = eventData.tool_calls.map(call => {
            const args = typeof call.args === 'object' ? JSON.stringify(call.args) : call.args;
            return `🔧 Calling tool: ${call.name}(${args})`;
          }).join('\n');

          setAllStreamedContent(prev => [...prev, {
            type: 'tool_call',
            content: toolCallText,
            timestamp: new Date().toISOString()
          }]);

          setIsStreaming(true);
        } else if (eventData.event_type === 'tool_detail') {
          // Rich tool detail: update the last tool_call message for this tool with full input
          const toolName = eventData.tool_name || '';
          const filePath = eventData.file || '';
          const toolInput = eventData.input || {};

          setMessages(prev => {
            const newMessages = [...prev];
            // Find the last tool call message for this tool that hasn't been detailed yet
            for (let i = newMessages.length - 1; i >= 0; i--) {
              if (newMessages[i].isToolCall &&
                  newMessages[i].toolData?.name === toolName &&
                  !newMessages[i].toolData?.detailed) {
                newMessages[i].toolData.file = filePath;
                newMessages[i].toolData.input = toolInput;
                newMessages[i].toolData.detailed = true;
                break;
              }
            }
            return newMessages;
          });

          setIsStreaming(true);
        } else if (eventData.event_type === 'tool_response' && eventData.tool_responses) {
          // Update tool call messages with responses and completion time
          eventData.tool_responses.forEach(resp => {
            const endTime = new Date().toISOString();

            // Update the last tool call message for this tool
            setMessages(prev => {
              const newMessages = [...prev];
              // Find the last tool call message for this tool
              for (let i = newMessages.length - 1; i >= 0; i--) {
                if (newMessages[i].isToolCall && newMessages[i].toolData?.name === resp.name && !newMessages[i].toolData?.response) {
                  newMessages[i].toolData.response = resp.response;
                  newMessages[i].toolData.endTime = endTime;
                  newMessages[i].content = `✓ ${resp.name} completed`;
                  break;
                }
              }
              return newMessages;
            });

            // Store in execution steps
            const responseStep = {
              type: 'tool_response',
              name: resp.name || 'unknown',
              response: resp.response,
              timestamp: eventData.timestamp || new Date().toISOString()
            };
            setCurrentExecutionSteps(prev => [...prev, responseStep]);
          });

          // Add to stream history
          const toolResponseText = eventData.tool_responses.map(resp => {
            const response = typeof resp.response === 'object' ? JSON.stringify(resp.response) : resp.response;
            return `📊 Tool response: ${response}`;
          }).join('\n');

          setAllStreamedContent(prev => [...prev, {
            type: 'tool_response',
            content: toolResponseText,
            timestamp: new Date().toISOString()
          }]);

          // Check for markdown links in tool responses that should trigger auto-navigation
          const links = extractMarkdownLinks(toolResponseText);
          const autoNavigateLink = links.find(link => shouldAutoNavigate(link));

          if (autoNavigateLink) {
            // Extract flowId from the URL
            const urlMatch = autoNavigateLink.url.match(/flowId=([a-f0-9-]+)/);
            if (urlMatch && urlMatch[1]) {
              // Navigate to flow designer after a short delay to ensure message is displayed
              setTimeout(() => {
                console.log('Navigating to flow designer with flowId:', urlMatch[1]);
                navigate(`/flows/${urlMatch[1]}/edit`);
              }, 1500); // 1.5 second delay to let user see the message
            }
          }

          setIsStreaming(true);
        } else if (eventData.text) {
          // Regular text streaming - show each text chunk as it arrives
          console.log('Received text event:', eventData.text);

          // Add to stream history
          setAllStreamedContent(prev => [...prev, {
            type: 'text',
            content: eventData.text,
            timestamp: new Date().toISOString()
          }]);

          // Update the accumulated message for final response
          const newAccumulatedText = currentStreamingMessageRef.current + eventData.text;
          setCurrentStreamingMessage(newAccumulatedText);
          currentStreamingMessageRef.current = newAccumulatedText;

          // Check for markdown links that should trigger auto-navigation
          const links = extractMarkdownLinks(eventData.text);
          const autoNavigateLink = links.find(link => shouldAutoNavigate(link));

          if (autoNavigateLink) {
            // Extract flowId from the URL
            const urlMatch = autoNavigateLink.url.match(/flowId=([a-f0-9-]+)/);
            if (urlMatch && urlMatch[1]) {
              // Navigate to flow designer after a short delay to ensure message is displayed
              setTimeout(() => {
                console.log('Navigating to flow designer with flowId:', urlMatch[1]);
                navigate(`/flows/${urlMatch[1]}/edit`);
              }, 1000); // 1 second delay to let user see the message
            }
          }

          // Add each text chunk as a separate thinking message
          // This shows the thinking process in real-time between tool calls
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: eventData.text,
            isThinking: true,  // Mark as thinking narration
            timestamp: new Date().toISOString()
          }]);

          setIsStreaming(true);
        }
        break;

      case 'execution_complete':
        // Execution completed
        console.log('Execution complete:', data);

        // Don't remove thinking messages - they show the real-time process
        // Just remove any active streaming indicators
        setMessages(prev => prev.filter(msg => !msg.isStreaming));

        // Check if it was cancelled, failed, or successful
        if (data.data?.cancelled) {
          // Execution was cancelled - don't add another message, already handled
          console.log('Execution was cancelled');
        } else if (data.data?.success === false) {
          // Execution failed - show error
          const errorMessage = data.data?.error || 'An error occurred during execution';

          setMessages(prev => [...prev, {
            role: 'assistant',
            content: `❌ Error: ${errorMessage}`,
            executionSteps: currentExecutionSteps.length > 0 ? [...currentExecutionSteps] : undefined,
            streamHistory: allStreamedContent.length > 0 ? [...allStreamedContent] : undefined,
            isError: true
          }]);
        } else {
          // Successful completion
          // The thinking messages already show all the content
          // We don't need to add a duplicate final message
          console.log('Execution completed successfully');

          // Optionally add a completion indicator if needed
          if (currentExecutionSteps.length > 0) {
            setMessages(prev => [...prev, {
              role: 'assistant',
              content: '✅ Flow design completed successfully',
              isCompletionIndicator: true,
              executionSteps: currentExecutionSteps.length > 0 ? [...currentExecutionSteps] : undefined,
              timestamp: new Date().toISOString()
            }]);
          }
        }

        // Clear temporary state
        setCurrentStreamingMessage('');
        currentStreamingMessageRef.current = '';
        setCurrentExecutionSteps([]);
        setAllStreamedContent([]);
        setIsStreaming(false);
        break;

      case 'execution_started':
        // Execution started notification
        console.log('Execution started for agent:', data.agent_id);
        // Clear execution steps and stream history for new execution
        setCurrentExecutionSteps([]);
        setAllStreamedContent([]);
        setCurrentStreamingMessage('');
        currentStreamingMessageRef.current = '';
        // Set streaming to true so cancel button is enabled
        setIsStreaming(true);

        // Add a "thinking" indicator message immediately
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Processing your request...',
          isStreaming: true,
          timestamp: new Date().toISOString()
        }]);
        break;

      case 'cancelled':
        // Handle cancellation
        console.log('Execution cancelled');

        // Remove any streaming message and thinking messages
        setMessages(prev => prev.filter(msg => !msg.isStreaming && !msg.isThinking));

        // Add a clear cancellation message
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: '🛑 **Execution cancelled by user**',
          isCancelled: true,
          executionSteps: currentExecutionSteps.length > 0 ? [...currentExecutionSteps] : undefined,
          timestamp: new Date().toISOString()
        }]);

        setIsStreaming(false);
        setCurrentStreamingMessage('');
        currentStreamingMessageRef.current = '';
        setCurrentExecutionSteps([]);
        setAllStreamedContent([]);
        break;

      case 'error':
        // Handle error
        console.error('Assistant error:', data.message);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: `Error: ${data.message}`
        }]);
        setIsStreaming(false);
        setCurrentStreamingMessage('');
        currentStreamingMessageRef.current = '';
        break;

      case 'session_info':
        // Session information
        if (data.data?.messages) {
          const formattedMessages = data.data.messages.map(msg => ({
            role: msg.role,
            content: msg.content
          }));
          setMessages(formattedMessages);
        }
        break;

      case 'typing_indicator':
        // Handle typing indicator if needed
        break;

      default:
        console.log('Unknown message type:', type, data);
    }
  }, []);

  // Send message with queue support
  const sendMessage = useCallback(async (text, config) => {
    // Update last activity time
    lastActivityTimeRef.current = Date.now();

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, queueing message');

      // Queue the message for later sending
      const messageData = {
        type: 'send_message',
        text: text,
        token: localStorage.getItem('access_token') || localStorage.getItem('token'),
        ...config
      };
      messageQueueRef.current.push(messageData);

      // Try to reconnect if not already connecting
      if (connectionStatus === 'disconnected') {
        reconnectAttemptsRef.current = 0; // Reset attempts for user-initiated reconnection
        connect();
      }

      // Still add user message to the UI
      setMessages(prev => [...prev, { role: 'user', content: text }]);
      setIsStreaming(true);
      return;
    }

    // Add user message to list
    setMessages(prev => [...prev, { role: 'user', content: text }]);

    // Get authentication token for backend to identify user
    const token = localStorage.getItem('access_token') || localStorage.getItem('token');

    // Send message through WebSocket with authentication token
    wsRef.current.send(JSON.stringify({
      type: 'send_message',
      text: text,
      token: token,  // Include token for user identification
      ...config
    }));

    setIsStreaming(true);
  }, []);

  // Cancel execution
  const cancelExecution = useCallback((config = {}) => {
    console.log('Cancel execution called with config:', config);
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.error('WebSocket not connected');
      return;
    }

    // Get authentication token for backend to identify user
    const token = localStorage.getItem('access_token') || localStorage.getItem('token');

    console.log('Sending cancel message via WebSocket with agent_id:', config.agent_id);
    wsRef.current.send(JSON.stringify({
      type: 'cancel',
      token: token,  // Include token for user identification
      ...config      // Include agent_id and any other config
    }));

    // Don't set isStreaming to false immediately - wait for server confirmation
    // setIsStreaming(false);

    // Don't add the cancelled message here - wait for server to confirm
    // The server will send the proper cancellation event
  }, []);

  // Clear messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    setCurrentStreamingMessage('');
    currentStreamingMessageRef.current = '';
    setIsStreaming(false);
  }, []);

  // Restore messages from saved state
  const restoreMessages = useCallback((savedMessages) => {
    if (savedMessages && Array.isArray(savedMessages)) {
      setMessages(savedMessages);
      console.log('Restored', savedMessages.length, 'messages from saved state');
    }
  }, []);

  // Force reconnect function for external use
  const forceReconnect = useCallback(() => {
    console.log('Force reconnecting WebSocket');
    if (wsRef.current) {
      isManuallyClosedRef.current = true;
      wsRef.current.close();
    }
    isManuallyClosedRef.current = false;
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  // Handle visibility change (wake from sleep/tab becomes active)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('Page became visible');

        // Check if we've been inactive for more than 1 minute
        const inactiveTime = Date.now() - lastActivityTimeRef.current;
        if (inactiveTime > 60000) {
          console.log('Inactive for', Math.round(inactiveTime / 1000), 'seconds, reconnecting...');
          // Force reconnect after prolonged inactivity
          reconnectAttemptsRef.current = 0;
          if (wsRef.current && wsRef.current.readyState !== WebSocket.OPEN) {
            connect();
          } else if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            // Send a ping to check if connection is still alive
            wsRef.current.send(JSON.stringify({ type: 'ping' }));
          }
        }
      }
    };

    // Also handle online/offline events
    const handleOnline = () => {
      console.log('Network came online');
      if (connectionStatus === 'disconnected' || connectionStatus === 'error') {
        reconnectAttemptsRef.current = 0;
        connect();
      }
    };

    const handleOffline = () => {
      console.log('Network went offline');
      setConnectionStatus('disconnected');
    };

    // Handle focus event (when window/tab gets focus)
    const handleFocus = () => {
      console.log('Window focused');
      // Check connection status and reconnect if needed
      if (wsRef.current && wsRef.current.readyState !== WebSocket.OPEN && connectionStatus !== 'connecting') {
        console.log('WebSocket not open on focus, attempting reconnect');
        reconnectAttemptsRef.current = 0;
        connect();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    window.addEventListener('focus', handleFocus);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('focus', handleFocus);
    };
  }, [connectionStatus, connect]);

  // Connect on mount and disconnect on unmount
  useEffect(() => {
    if (sessionId) {
      isManuallyClosedRef.current = false;
      reconnectAttemptsRef.current = 0;
      connect();
    }

    return () => {
      // Clean up
      isManuallyClosedRef.current = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        if (wsRef.current.pingInterval) {
          clearInterval(wsRef.current.pingInterval);
        }
        wsRef.current.close();
      }
    };
  }, [sessionId, connect]);

  return {
    messages,
    isStreaming,
    sendMessage,
    cancelExecution,
    clearMessages,
    restoreMessages,
    connectionStatus,
    forceReconnect
  };
}