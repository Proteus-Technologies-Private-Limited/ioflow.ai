import React, { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { showSuccessToast, showErrorToast } from '../utils/customToast';

/**
 * "Authenticate with Twasta" callback.
 *
 * Twasta's /api/auth/runtime-authorize redirects here with ?token=<twasta_jwt>
 * (and an optional ?next=<path> we appended when starting the flow). We
 * exchange the twasta token for an IOFlow session via
 * POST /api/v1/auth/twasta-exchange (which verifies the token server-side and
 * auto-provisions the tenant + user on first login), then store the session
 * exactly like a normal login.
 */
const TwastaAuthCallback = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuthData } = useAuth();
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return; // guard against StrictMode double-invoke
    ranRef.current = true;
    handleCallback();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCallback = async () => {
    const twastaToken = searchParams.get('token');
    const next = searchParams.get('next');

    if (!twastaToken) {
      showErrorToast('Twasta did not return a token. Please try again.');
      navigate('/login');
      return;
    }

    try {
      const response = await axios.post('/api/v1/auth/twasta-exchange', {
        twasta_token: twastaToken,
      });

      const { access_token, user_id, tenant_id, tenant_name, username, role } = response.data;
      if (!access_token) {
        throw new Error('No access token received from server');
      }

      setAuthData({
        token: access_token,
        userId: user_id,
        tenantId: tenant_id,
        tenantName: tenant_name,
        username,
        userRole: role,
      });

      showSuccessToast(`Welcome, ${username}!`);
      // Only allow same-app relative paths for next (no open redirect).
      const target = next && next.startsWith('/') && !next.startsWith('//') ? next : '/dashboard';
      navigate(target, { replace: true });
    } catch (error) {
      console.error('Twasta exchange error:', error);
      const message =
        error.response?.data?.detail ||
        error.message ||
        'Twasta sign-in failed. Please try again.';
      showErrorToast(message);
      navigate('/login');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-gray-600">Signing you in with Twasta...</p>
      </div>
    </div>
  );
};

export default TwastaAuthCallback;
