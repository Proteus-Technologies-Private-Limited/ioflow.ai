import React from 'react';
import { X, User, Crown, Eye, Edit } from 'lucide-react';

const ParticipantsList = ({ participants, onClose, currentUserId, currentUserEmail, currentUserName }) => {
  const getRoleIcon = (role) => {
    switch (role) {
      case 'owner':
        return <Crown className="w-4 h-4 text-yellow-500" />;
      case 'editor':
        return <Edit className="w-4 h-4 text-blue-500" />;
      case 'viewer':
        return <Eye className="w-4 h-4 text-gray-500" />;
      default:
        return <User className="w-4 h-4 text-gray-500" />;
    }
  };

  const getInitials = (name) => {
    return name
      .split(' ')
      .map(part => part[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  // Filter out the current user
  // Check against multiple possible fields since participant structure may vary
  const otherParticipants = participants.filter(p => {
    const isCurrentUser = (
      (currentUserId && (p.user_id === currentUserId || p.id === currentUserId || p.participant_id === currentUserId)) ||
      (currentUserEmail && p.email === currentUserEmail) ||
      (currentUserName && (p.username === currentUserName || p.display_name === currentUserName))
    );
    return !isCurrentUser;
  });

  return (
    <div className="bg-white rounded-lg shadow-lg border border-gray-200 w-80">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-800">
          Active Collaborators ({otherParticipants.length})
        </h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded transition-colors"
          title="Close"
        >
          <X className="w-5 h-5 text-gray-500" />
        </button>
      </div>

      {/* Participants list */}
      <div className="max-h-96 overflow-y-auto">
        {otherParticipants.length === 0 ? (
          <div className="px-4 py-8 text-center text-gray-500">
            No other collaborators yet
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {otherParticipants.map((participant) => (
              <li
                key={participant.id}
                className="px-4 py-3 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  {/* Avatar with color */}
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-sm"
                    style={{ backgroundColor: participant.color }}
                  >
                    {getInitials(participant.display_name)}
                  </div>

                  {/* Participant info */}
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-medium text-gray-800">
                        {participant.display_name}
                      </span>
                      {getRoleIcon(participant.role)}
                    </div>
                    {participant.email && (
                      <div className="text-sm text-gray-500">
                        {participant.email}
                      </div>
                    )}
                  </div>

                  {/* Online indicator */}
                  <div className="flex items-center">
                    <div
                      className={`w-2 h-2 rounded-full ${
                        participant.is_online ? 'bg-green-500' : 'bg-gray-300'
                      }`}
                      title={participant.is_online ? 'Online' : 'Offline'}
                    />
                  </div>
                </div>

                {/* Cursor position indicator (if available) */}
                {participant.cursor_position && (
                  <div className="mt-2 text-xs text-gray-500">
                    Cursor: ({Math.round(participant.cursor_position.x)}, {Math.round(participant.cursor_position.y)})
                  </div>
                )}

                {/* Selected nodes indicator */}
                {participant.selected_nodes && participant.selected_nodes.length > 0 && (
                  <div className="mt-1 text-xs text-gray-500">
                    Editing: {participant.selected_nodes.length} node(s)
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Footer with stats */}
      <div className="px-4 py-3 border-t border-gray-200 bg-gray-50">
        <div className="flex justify-between text-sm text-gray-600">
          <span>
            {otherParticipants.filter(p => p.is_online).length} online
          </span>
          <span>
            {otherParticipants.filter(p => p.role === 'editor').length} editors
          </span>
        </div>
      </div>
    </div>
  );
};

export default ParticipantsList;