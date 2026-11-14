import React from 'react';
import { Users } from 'lucide-react';

const CollaborationIndicator = ({ 
  participants, 
  isCollaborating,
  isConnected,
  onShowParticipants,
  currentUserId,
  currentUserEmail,
  currentUserName
}) => {
  const getInitials = (name) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  const getParticipantColor = (participant) => {
    return participant.color || '#6B7280';
  };

  if (!isCollaborating) return null;

  // Filter out the current user from participants
  // Check against multiple possible fields since participant structure may vary
  const otherParticipants = participants.filter(p => {
    // Check if this participant is the current user by comparing various fields
    const isCurrentUser = (
      (currentUserId && (p.user_id === currentUserId || p.id === currentUserId || p.participant_id === currentUserId)) ||
      (currentUserEmail && p.email === currentUserEmail) ||
      (currentUserName && (p.username === currentUserName || p.display_name === currentUserName))
    );
    return !isCurrentUser;
  });

  return (
    <div className="flex items-center gap-2">
      {/* Connection status indicator */}
      <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
        isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      }`}>
        <div className={`w-2 h-2 rounded-full ${
          isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
        }`} />
        <span>{isConnected ? 'Live' : 'Offline'}</span>
      </div>

      {/* Active participants - only show other users */}
      {otherParticipants.length > 0 && (
        <div className="flex items-center -space-x-1">
          {otherParticipants.slice(0, 4).map((participant) => (
          <div
            key={participant.id}
            className="relative group"
            title={participant.display_name}
          >
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-semibold border-2 border-white shadow-sm hover:z-10 transition-all hover:scale-110"
              style={{ backgroundColor: getParticipantColor(participant) }}
            >
              {getInitials(participant.display_name)}
            </div>
            {/* Name tooltip */}
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 mt-1 px-2 py-1 bg-gray-900 text-white text-xs rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
              {participant.display_name}
              <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-gray-900"></div>
            </div>
            {/* Online indicator */}
            {participant.is_online && (
              <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-500 rounded-full border-2 border-white"></div>
            )}
          </div>
        ))}
          
          {/* Show +N more if there are more than 4 other participants */}
          {otherParticipants.length > 4 && (
            <button
              onClick={onShowParticipants}
              className="w-8 h-8 rounded-full bg-gray-200 text-gray-600 text-xs font-semibold border-2 border-white shadow-sm hover:bg-gray-300 transition-colors flex items-center justify-center"
              title={`${otherParticipants.length - 4} more participant${otherParticipants.length - 4 > 1 ? 's' : ''}`}
            >
              +{otherParticipants.length - 4}
            </button>
          )}
        </div>
      )}

      {/* View all participants button - only show if there are other participants */}
      {otherParticipants.length > 0 && (
        <button
          onClick={onShowParticipants}
          className="p-1.5 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md transition-colors"
          title="View all participants"
        >
          <Users className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};

export default CollaborationIndicator;