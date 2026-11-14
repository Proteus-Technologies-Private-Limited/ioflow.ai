import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Link, 
  UserPlus, 
  X, 
  Copy, 
  Check,
  Circle,
  MessageSquare,
  Video,
  Mic
} from 'lucide-react';
import collaborationService from '../../services/collaborationService';
import ParticipantsList from './ParticipantsList';
import InviteDialog from './InviteDialog';

const CollaborationToolbar = ({ 
  flowId, 
  isCollaborating, 
  onStartCollaboration, 
  onEndCollaboration,
  className = '' 
}) => {
  const [showParticipants, setShowParticipants] = useState(false);
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [participants, setParticipants] = useState([]);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [shareLink, setShareLink] = useState('');
  const [linkCopied, setLinkCopied] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (isCollaborating) {
      // Set up collaboration event listeners
      collaborationService.on('connected', handleConnected);
      collaborationService.on('disconnected', handleDisconnected);
      collaborationService.on('participant_joined', handleParticipantJoined);
      collaborationService.on('participant_left', handleParticipantLeft);
      collaborationService.on('session_state', handleSessionState);

      return () => {
        collaborationService.off('connected', handleConnected);
        collaborationService.off('disconnected', handleDisconnected);
        collaborationService.off('participant_joined', handleParticipantJoined);
        collaborationService.off('participant_left', handleParticipantLeft);
        collaborationService.off('session_state', handleSessionState);
      };
    }
  }, [isCollaborating]);

  const handleConnected = () => {
    setIsConnected(true);
  };

  const handleDisconnected = () => {
    setIsConnected(false);
  };

  const handleSessionState = ({ participants: sessionParticipants }) => {
    setParticipants(sessionParticipants);
  };

  const handleParticipantJoined = (participant) => {
    setParticipants(prev => [...prev, participant]);
  };

  const handleParticipantLeft = (participant) => {
    setParticipants(prev => prev.filter(p => p.id !== participant.id));
  };

  const handleStartCollaboration = async () => {
    try {
      // Create collaboration session
      const session = await collaborationService.createSession(flowId, {
        durationHours: 24,
        maxParticipants: 10,
        enableChat: true
      });

      setSessionInfo(session);
      setShareLink(session.share_link);

      // Join the session
      await collaborationService.joinSession(session.session_id);

      // Connect to WebSocket
      await collaborationService.connect(session.session_id, session.access_token);

      if (onStartCollaboration) {
        onStartCollaboration(session);
      }
    } catch (error) {
      console.error('Failed to start collaboration:', error);
      alert('Failed to start collaboration session. Please try again.');
    }
  };

  const handleEndCollaboration = async () => {
    try {
      await collaborationService.leaveSession();
      setSessionInfo(null);
      setShareLink('');
      setParticipants([]);
      setIsConnected(false);

      if (onEndCollaboration) {
        onEndCollaboration();
      }
    } catch (error) {
      console.error('Failed to end collaboration:', error);
    }
  };

  const handleCopyLink = () => {
    if (shareLink) {
      navigator.clipboard.writeText(shareLink);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    }
  };

  const handleInvite = async (inviteData) => {
    try {
      const invite = await collaborationService.createInvite(inviteData);
      return invite;
    } catch (error) {
      console.error('Failed to create invite:', error);
      throw error;
    }
  };

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      {!isCollaborating ? (
        <button
          onClick={handleStartCollaboration}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          title="Start collaboration session"
        >
          <Users className="w-4 h-4" />
          <span>Invite Co-editor</span>
        </button>
      ) : (
        <>
          {/* Connection status indicator */}
          <div className="flex items-center space-x-2 px-3 py-2 bg-gray-100 rounded-lg">
            <Circle 
              className={`w-3 h-3 ${isConnected ? 'text-green-500' : 'text-red-500'}`} 
              fill="currentColor"
            />
            <span className="text-sm text-gray-700">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          {/* Participants count */}
          <button
            onClick={() => setShowParticipants(!showParticipants)}
            className="relative flex items-center space-x-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
            title="View participants"
          >
            <Users className="w-4 h-4 text-gray-700" />
            <span className="text-sm font-medium text-gray-700">
              {participants.length} {participants.length === 1 ? 'participant' : 'participants'}
            </span>
          </button>

          {/* Share link button */}
          {shareLink && (
            <button
              onClick={handleCopyLink}
              className="flex items-center space-x-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              title="Copy share link"
            >
              {linkCopied ? (
                <>
                  <Check className="w-4 h-4 text-green-600" />
                  <span className="text-sm text-green-600">Copied!</span>
                </>
              ) : (
                <>
                  <Link className="w-4 h-4 text-gray-700" />
                  <span className="text-sm text-gray-700">Copy Link</span>
                </>
              )}
            </button>
          )}

          {/* Invite button */}
          <button
            onClick={() => setShowInviteDialog(true)}
            className="flex items-center space-x-2 px-3 py-2 bg-blue-100 rounded-lg hover:bg-blue-200 transition-colors"
            title="Invite participants"
          >
            <UserPlus className="w-4 h-4 text-blue-700" />
            <span className="text-sm text-blue-700">Invite</span>
          </button>

          {/* End collaboration button */}
          <button
            onClick={handleEndCollaboration}
            className="flex items-center space-x-2 px-3 py-2 bg-red-100 rounded-lg hover:bg-red-200 transition-colors"
            title="End collaboration"
          >
            <X className="w-4 h-4 text-red-700" />
            <span className="text-sm text-red-700">End Session</span>
          </button>
        </>
      )}

      {/* Participants list popup */}
      {showParticipants && (
        <div className="absolute top-full mt-2 right-0 z-50">
          <ParticipantsList
            participants={participants}
            onClose={() => setShowParticipants(false)}
          />
        </div>
      )}

      {/* Invite dialog */}
      {showInviteDialog && (
        <InviteDialog
          sessionInfo={sessionInfo}
          shareLink={shareLink}
          onInvite={handleInvite}
          onClose={() => setShowInviteDialog(false)}
        />
      )}
    </div>
  );
};

export default CollaborationToolbar;