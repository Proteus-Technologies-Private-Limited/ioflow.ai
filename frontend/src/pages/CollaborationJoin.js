import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { UsersIcon } from '@heroicons/react/24/outline';
import collaborationService from '../services/collaborationService';
import { formatDateTime } from '../utils/dateFormatter';

export default function CollaborationJoin() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [joining, setJoining] = useState(false);

  useEffect(() => {
    if (!token) {
      setError('Invalid collaboration link - missing token');
      setLoading(false);
      return;
    }

    // Get session details by token
    loadSessionInfo();
  }, [token]);

  const loadSessionInfo = async () => {
    try {
      const session = await collaborationService.getSessionByToken(token);
      setSessionInfo(session);
      setLoading(false);
    } catch (err) {
      setError('Failed to load collaboration session. The link may be expired or invalid.');
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    setJoining(true);
    try {
      // Join the session
      await collaborationService.joinSession(sessionInfo.session_id, {
        token: token,
        displayName: localStorage.getItem('user_name') || 'Guest User',
        role: 'editor'
      });

      // Navigate to the flow designer with collaboration enabled
      navigate(`/flows/${sessionInfo.flow_id}/edit?collaborate=${sessionInfo.session_id}&token=${token}`);
    } catch (err) {
      setError('Failed to join collaboration session: ' + err.message);
      setJoining(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading collaboration session...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full space-y-8">
          <div className="text-center">
            <UsersIcon className="mx-auto h-12 w-12 text-red-400" />
            <h2 className="mt-6 text-3xl font-extrabold text-gray-900">
              Unable to Join Collaboration
            </h2>
            <p className="mt-2 text-sm text-gray-600">{error}</p>
            <button
              onClick={() => navigate('/')}
              className="mt-4 px-4 py-2 bg-gradient-primary text-white rounded-md hover:shadow-lg"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8">
        <div>
          <UsersIcon className="mx-auto h-12 w-12 text-primary" />
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Join Collaboration Session
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            You've been invited to collaborate on a flow
          </p>
        </div>
        
        {sessionInfo && (
          <div className="bg-white shadow rounded-lg p-6">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Flow Name</label>
                <p className="mt-1 text-lg font-semibold text-gray-900">{sessionInfo.flow_name}</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700">Active Participants</label>
                <p className="mt-1 text-sm text-gray-600">{sessionInfo.participant_count} user(s) currently editing</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700">Session Expires</label>
                <p className="mt-1 text-sm text-gray-600">
                  {formatDateTime(sessionInfo.expires_at)}
                </p>
              </div>
              
              {sessionInfo.enable_chat && (
                <div className="flex items-center text-sm text-gray-600">
                  <svg className="h-4 w-4 mr-2 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Chat enabled
                </div>
              )}
            </div>
            
            <div className="mt-6 space-y-3">
              <button
                onClick={handleJoin}
                disabled={joining}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gradient-primary hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary disabled:bg-gray-400"
              >
                {joining ? 'Joining...' : 'Join Collaboration'}
              </button>
              
              <button
                onClick={() => navigate('/')}
                className="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}