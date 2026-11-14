import React, { useState } from 'react';
import { X, Copy, Check, Mail, Link, Users, Clock, Shield } from 'lucide-react';
import { formatDateTime } from '../../utils/dateFormatter';

const InviteDialog = ({ sessionInfo, shareLink, onInvite, onClose }) => {
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('editor');
  const [expiresHours, setExpiresHours] = useState(24);
  const [maxUses, setMaxUses] = useState(1);
  const [linkCopied, setLinkCopied] = useState(false);
  const [inviteSent, setInviteSent] = useState(false);
  const [isInviting, setIsInviting] = useState(false);
  const [error, setError] = useState('');

  const handleCopyLink = () => {
    if (shareLink) {
      navigator.clipboard.writeText(shareLink);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    }
  };

  const handleSendInvite = async () => {
    if (!inviteEmail || !inviteEmail.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    setIsInviting(true);
    setError('');

    try {
      const invite = await onInvite({
        email: inviteEmail,
        role: inviteRole,
        expires_hours: expiresHours,
        max_uses: maxUses
      });

      setInviteSent(true);
      setTimeout(() => {
        setInviteSent(false);
        setInviteEmail('');
      }, 3000);
    } catch (error) {
      setError('Failed to send invite. Please try again.');
      console.error('Failed to send invite:', error);
    } finally {
      setIsInviting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-800">
            Invite Co-editors
          </h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
            title="Close"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 space-y-4">
          {/* Share link section */}
          <div className="space-y-2">
            <div className="flex items-center space-x-2 text-sm font-medium text-gray-700">
              <Link className="w-4 h-4" />
              <span>Share Link</span>
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={shareLink}
                readOnly
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm"
                onClick={(e) => e.target.select()}
              />
              <button
                onClick={handleCopyLink}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center space-x-2"
              >
                {linkCopied ? (
                  <>
                    <Check className="w-4 h-4" />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
            <p className="text-xs text-gray-500">
              Anyone with this link can join the collaboration session
            </p>
          </div>

          <div className="border-t border-gray-200"></div>

          {/* Email invite section */}
          <div className="space-y-4">
            <div className="flex items-center space-x-2 text-sm font-medium text-gray-700">
              <Mail className="w-4 h-4" />
              <span>Send Email Invite</span>
            </div>

            {/* Email input */}
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                Email Address
              </label>
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@example.com"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Role selection */}
            <div>
              <label className="block text-sm text-gray-600 mb-1">
                <Shield className="w-4 h-4 inline mr-1" />
                Role
              </label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="editor">Editor - Can make changes</option>
                <option value="viewer">Viewer - Can only view</option>
              </select>
            </div>

            {/* Advanced options */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  <Clock className="w-4 h-4 inline mr-1" />
                  Expires In
                </label>
                <select
                  value={expiresHours}
                  onChange={(e) => setExpiresHours(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value={1}>1 hour</option>
                  <option value={6}>6 hours</option>
                  <option value={24}>24 hours</option>
                  <option value={48}>48 hours</option>
                  <option value={168}>1 week</option>
                </select>
              </div>

              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  <Users className="w-4 h-4 inline mr-1" />
                  Max Uses
                </label>
                <input
                  type="number"
                  value={maxUses}
                  onChange={(e) => setMaxUses(parseInt(e.target.value) || 1)}
                  min="1"
                  max="100"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Error message */}
            {error && (
              <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">
                {error}
              </div>
            )}

            {/* Success message */}
            {inviteSent && (
              <div className="text-sm text-green-600 bg-green-50 px-3 py-2 rounded flex items-center space-x-2">
                <Check className="w-4 h-4" />
                <span>Invite sent successfully!</span>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 bg-gray-50">
          <div className="text-xs text-gray-500">
            Session expires: {sessionInfo && formatDateTime(sessionInfo.expires_at)}
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Close
            </button>
            <button
              onClick={handleSendInvite}
              disabled={!inviteEmail || isInviting}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
            >
              {isInviting ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  <span>Sending...</span>
                </>
              ) : (
                <>
                  <Mail className="w-4 h-4" />
                  <span>Send Invite</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default InviteDialog;