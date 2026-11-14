import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { showSuccessToast, showErrorToast } from '../utils/customToast';

const GoogleAuthCallback = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setAuthData } = useAuth();

  useEffect(() => {
    handleCallback();
  }, []);

  const handleCallback = () => {
    // Get parameters from URL
    const token = searchParams.get('token');
    const userId = searchParams.get('user_id');
    const tenantId = searchParams.get('tenant_id');
    const tenantName = searchParams.get('tenant_name');
    const username = searchParams.get('username');
    const role = searchParams.get('role');
    const isNew = searchParams.get('is_new') === 'true';
    const error = searchParams.get('error');

    if (error) {
      // Handle error cases
      if (error === 'user_not_found') {
        showErrorToast('User not found. Please sign up first.');
        navigate('/register');
      } else if (error === 'oauth_failed') {
        showErrorToast('Google authentication failed. Please try again.');
        navigate('/login');
      } else {
        showErrorToast('An error occurred during authentication.');
        navigate('/login');
      }
      return;
    }

    if (token && userId && tenantId) {
      // Save auth data
      localStorage.setItem('token', token);
      localStorage.setItem('userId', userId);
      localStorage.setItem('tenantId', tenantId);
      localStorage.setItem('tenantName', tenantName);
      localStorage.setItem('username', username);
      localStorage.setItem('userRole', role);

      // Update auth context
      setAuthData({
        token,
        userId,
        tenantId,
        tenantName,
        username,
        userRole: role
      });

      if (isNew) {
        showSuccessToast('Account created successfully! Welcome to IOFlow!');
      } else {
        showSuccessToast('Logged in successfully!');
      }

      // Redirect to dashboard
      navigate('/dashboard');
    } else {
      showErrorToast('Invalid authentication response.');
      navigate('/login');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-gray-600">Completing authentication...</p>
      </div>
    </div>
  );
};

export default GoogleAuthCallback;