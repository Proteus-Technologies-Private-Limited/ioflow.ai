import { useState, useEffect, useCallback, useRef } from 'react';
import collaborationService from '../services/collaborationService';

/**
 * Hook for managing real-time collaboration in flow editing
 */
export function useCollaboration(flowId, options = {}) {
  const {
    onOperation,
    onCursorMove,
    onSelectionChange,
    onChatMessage,
    onParticipantJoined,
    onParticipantLeft,
    enabled = false
  } = options;

  const [isCollaborating, setIsCollaborating] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [error, setError] = useState(null);

  const cursorThrottleRef = useRef(null);
  const selectionThrottleRef = useRef(null);

  // Start collaboration session
  const startCollaboration = useCallback(async (options = {}) => {
    try {
      setError(null);
      
      // Create session
      console.log('Creating collaboration session for flow:', flowId);
      const session = await collaborationService.createSession(flowId, options);
      console.log('Session created:', session);
      setSessionInfo(session);

      // Join session
      console.log('Joining session:', session.session_id);
      await collaborationService.joinSession(session.session_id);

      // Connect WebSocket - owner uses their JWT token, not the collaboration token
      const authToken = localStorage.getItem('access_token');
      console.log('Connecting WebSocket with auth token');
      await collaborationService.connect(session.session_id, authToken);
      
      setIsCollaborating(true);
      setIsConnected(true); // Set connected state immediately
      console.log('Collaboration started successfully');
      return session;
    } catch (err) {
      console.error('Failed to start collaboration:', err);
      console.error('Error details:', err.message, err.stack);
      setError(err.message);
      throw err;
    }
  }, [flowId]);

  // Join existing collaboration session
  const joinCollaboration = useCallback(async (sessionId, token = null) => {
    try {
      setError(null);

      // Get session info if token provided
      if (token) {
        const session = await collaborationService.getSessionByToken(token);
        setSessionInfo(session);
        sessionId = session.session_id;
      }

      // Join session
      const participant = await collaborationService.joinSession(sessionId, { token });

      // Connect WebSocket
      await collaborationService.connect(sessionId, token || localStorage.getItem('access_token'));
      
      setIsCollaborating(true);
      setIsConnected(true); // Set connected state immediately
      return participant;
    } catch (err) {
      console.error('Failed to join collaboration:', err);
      setError(err.message);
      throw err;
    }
  }, []);

  // End collaboration session
  const endCollaboration = useCallback(async () => {
    try {
      await collaborationService.leaveSession();
      setIsCollaborating(false);
      setIsConnected(false);
      setSessionInfo(null);
      setParticipants([]);
      setChatMessages([]);
      setError(null);
    } catch (err) {
      console.error('Failed to end collaboration:', err);
      setError(err.message);
    }
  }, []);

  // Send flow operation
  const sendOperation = useCallback((operation) => {
    if (!isConnected) return;
    
    collaborationService.sendOperation({
      operation_type: operation.type,
      ...operation
    });
  }, [isConnected]);

  // Send cursor position (throttled)
  const sendCursorPosition = useCallback((position) => {
    if (!isConnected) return;

    // Throttle cursor updates to every 100ms
    if (cursorThrottleRef.current) {
      clearTimeout(cursorThrottleRef.current);
    }

    cursorThrottleRef.current = setTimeout(() => {
      collaborationService.sendCursorPosition(position);
      cursorThrottleRef.current = null;
    }, 100);
  }, [isConnected]);

  // Send selection change (throttled)
  const sendSelectionChange = useCallback((selection) => {
    if (!isConnected) return;

    // Throttle selection updates to every 200ms
    if (selectionThrottleRef.current) {
      clearTimeout(selectionThrottleRef.current);
    }

    selectionThrottleRef.current = setTimeout(() => {
      collaborationService.sendSelectionChange(selection);
      selectionThrottleRef.current = null;
    }, 200);
  }, [isConnected]);

  // Send chat message
  const sendChatMessage = useCallback((message, mentions = [], nodeReferences = []) => {
    if (!isConnected) return;
    
    collaborationService.sendChatMessage(message, mentions, nodeReferences);
  }, [isConnected]);

  // Event handlers
  const handleConnected = useCallback(() => {
    setIsConnected(true);
  }, []);

  const handleDisconnected = useCallback(() => {
    setIsConnected(false);
  }, []);

  const handleSessionState = useCallback(({ state, participants: sessionParticipants }) => {
    setParticipants(sessionParticipants);
  }, []);

  const handleParticipantJoined = useCallback((participant) => {
    setParticipants(prev => [...prev, participant]);
    if (onParticipantJoined) {
      onParticipantJoined(participant);
    }
  }, [onParticipantJoined]);

  const handleParticipantLeft = useCallback((participant) => {
    setParticipants(prev => prev.filter(p => p.id !== participant.id));
    if (onParticipantLeft) {
      onParticipantLeft(participant);
    }
  }, [onParticipantLeft]);

  const handleOperation = useCallback((event) => {
    if (onOperation) {
      onOperation(event);
    }
  }, [onOperation]);

  const handleCursorMove = useCallback((data) => {
    // Update participant cursor position
    setParticipants(prev => prev.map(p => 
      p.id === data.participant_id 
        ? { ...p, cursor_position: data.position }
        : p
    ));

    if (onCursorMove) {
      onCursorMove(data);
    }
  }, [onCursorMove]);

  const handleSelectionChange = useCallback((data) => {
    // Update participant selection
    setParticipants(prev => prev.map(p => 
      p.id === data.participant_id 
        ? { 
            ...p, 
            selected_nodes: data.selected_nodes,
            selected_edges: data.selected_edges 
          }
        : p
    ));

    if (onSelectionChange) {
      onSelectionChange(data);
    }
  }, [onSelectionChange]);

  const handleChatMessage = useCallback((message) => {
    setChatMessages(prev => [...prev, message]);
    if (onChatMessage) {
      onChatMessage(message);
    }
  }, [onChatMessage]);

  const handleError = useCallback((error) => {
    setError(error.message);
    console.error('Collaboration error:', error);
  }, []);

  // Set up event listeners
  useEffect(() => {
    if (!enabled) return;

    // Set up listeners before connecting to avoid race conditions
    collaborationService.on('connected', handleConnected);
    collaborationService.on('disconnected', handleDisconnected);
    collaborationService.on('session_state', handleSessionState);
    collaborationService.on('participant_joined', handleParticipantJoined);
    collaborationService.on('participant_left', handleParticipantLeft);
    collaborationService.on('operation', handleOperation);
    collaborationService.on('cursor_move', handleCursorMove);
    collaborationService.on('selection_change', handleSelectionChange);
    collaborationService.on('chat_message', handleChatMessage);
    collaborationService.on('error', handleError);

    return () => {
      collaborationService.off('connected', handleConnected);
      collaborationService.off('disconnected', handleDisconnected);
      collaborationService.off('session_state', handleSessionState);
      collaborationService.off('participant_joined', handleParticipantJoined);
      collaborationService.off('participant_left', handleParticipantLeft);
      collaborationService.off('operation', handleOperation);
      collaborationService.off('cursor_move', handleCursorMove);
      collaborationService.off('selection_change', handleSelectionChange);
      collaborationService.off('chat_message', handleChatMessage);
      collaborationService.off('error', handleError);
    };
  }, [
    enabled,
    handleConnected,
    handleDisconnected,
    handleSessionState,
    handleParticipantJoined,
    handleParticipantLeft,
    handleOperation,
    handleCursorMove,
    handleSelectionChange,
    handleChatMessage,
    handleError
  ]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (cursorThrottleRef.current) {
        clearTimeout(cursorThrottleRef.current);
      }
      if (selectionThrottleRef.current) {
        clearTimeout(selectionThrottleRef.current);
      }
    };
  }, []);

  return {
    // State
    isCollaborating,
    isConnected,
    sessionInfo,
    participants,
    chatMessages,
    error,

    // Actions
    startCollaboration,
    joinCollaboration,
    endCollaboration,
    sendOperation,
    sendCursorPosition,
    sendSelectionChange,
    sendChatMessage,

    // Service instance (for advanced usage)
    collaborationService
  };
}