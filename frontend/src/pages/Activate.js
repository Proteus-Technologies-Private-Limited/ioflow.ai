import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline';
import { useAuth } from '../contexts/AuthContext';
import logo from '../assets/logo.png';

const Activate = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { activate } = useAuth();

  const email = searchParams.get('email') || '';
  const code = searchParams.get('code') || '';

  const [status, setStatus] = useState('activating'); // activating | success | already | error | missing
  const [errorMessage, setErrorMessage] = useState('');
  const ranRef = useRef(false);

  useEffect(() => {
    if (ranRef.current) return;
    ranRef.current = true;

    if (!email || !code) {
      setStatus('missing');
      return;
    }

    (async () => {
      try {
        const response = await activate(email, code);
        const message = response?.message || '';
        if (/already activated/i.test(message)) {
          setStatus('already');
        } else {
          setStatus('success');
        }
        setTimeout(() => navigate('/login'), 2500);
      } catch (error) {
        const data = error?.response?.data;
        const message =
          data?.detail ||
          data?.message ||
          data?.error ||
          (typeof data === 'string' ? data : '') ||
          error?.message ||
          'Activation failed. The link may be invalid or expired.';
        setErrorMessage(message);
        setStatus('error');
      }
    })();
  }, [email, code, activate, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8 text-center">
        <div className="flex justify-center">
          <img src={logo} alt="IOFlow" className="h-16 w-16" />
        </div>

        {status === 'activating' && (
          <>
            <div className="flex justify-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            </div>
            <h2 className="text-2xl font-extrabold text-gray-900">Activating your account…</h2>
            {email && (
              <p className="text-sm text-gray-600">
                Activating <span className="font-medium">{email}</span>
              </p>
            )}
          </>
        )}

        {status === 'success' && (
          <>
            <div className="flex justify-center">
              <div className="bg-green-100 rounded-full p-3">
                <CheckCircleIcon className="h-8 w-8 text-green-600" />
              </div>
            </div>
            <h2 className="text-2xl font-extrabold text-gray-900">Account Activated</h2>
            <p className="text-sm text-gray-600">
              Your account has been activated successfully. Redirecting you to login…
            </p>
            <Link
              to="/login"
              className="inline-block mt-4 px-5 py-2 rounded-md text-white bg-gradient-primary hover:shadow-lg transition-all"
            >
              Go to Login
            </Link>
          </>
        )}

        {status === 'already' && (
          <>
            <div className="flex justify-center">
              <div className="bg-blue-100 rounded-full p-3">
                <CheckCircleIcon className="h-8 w-8 text-blue-600" />
              </div>
            </div>
            <h2 className="text-2xl font-extrabold text-gray-900">Already Activated</h2>
            <p className="text-sm text-gray-600">
              This account is already activated. Redirecting you to login…
            </p>
            <Link
              to="/login"
              className="inline-block mt-4 px-5 py-2 rounded-md text-white bg-gradient-primary hover:shadow-lg transition-all"
            >
              Go to Login
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="flex justify-center">
              <div className="bg-red-100 rounded-full p-3">
                <XCircleIcon className="h-8 w-8 text-red-600" />
              </div>
            </div>
            <h2 className="text-2xl font-extrabold text-gray-900">Activation Failed</h2>
            <p className="text-sm text-gray-600">{errorMessage}</p>
            <div className="space-y-3 mt-6">
              <Link
                to="/register"
                className="block w-full py-2 px-4 rounded-md text-white bg-gradient-primary hover:shadow-lg transition-all"
              >
                Back to Registration
              </Link>
              <Link
                to="/login"
                className="block w-full py-2 px-4 border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 transition-colors"
              >
                Go to Login
              </Link>
            </div>
          </>
        )}

        {status === 'missing' && (
          <>
            <div className="flex justify-center">
              <div className="bg-red-100 rounded-full p-3">
                <XCircleIcon className="h-8 w-8 text-red-600" />
              </div>
            </div>
            <h2 className="text-2xl font-extrabold text-gray-900">Invalid Activation Link</h2>
            <p className="text-sm text-gray-600">
              This activation link is missing required information. Please use the link from your activation email.
            </p>
            <Link
              to="/login"
              className="inline-block mt-4 px-5 py-2 rounded-md text-white bg-gradient-primary hover:shadow-lg transition-all"
            >
              Go to Login
            </Link>
          </>
        )}
      </div>
    </div>
  );
};

export default Activate;
