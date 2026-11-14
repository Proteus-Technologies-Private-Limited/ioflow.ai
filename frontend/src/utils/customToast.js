import React from 'react';
import toast from 'react-hot-toast';
import { XMarkIcon } from '@heroicons/react/24/solid';

/**
 * Show an error toast with a close button that persists until dismissed
 * @param {string} message - The error message to display
 */
export const showErrorToast = (message) => {
  // Ensure message is a string
  let errorMessage = message;
  if (typeof message === 'object' && message !== null) {
    // Handle error objects
    if (message.detail) {
      errorMessage = typeof message.detail === 'string' ? message.detail : JSON.stringify(message.detail);
    } else if (message.msg) {
      errorMessage = message.msg;
    } else if (message.message) {
      errorMessage = message.message;
    } else {
      errorMessage = JSON.stringify(message);
    }
  } else if (typeof message !== 'string') {
    errorMessage = String(message);
  }

  // Check if message contains newlines (multi-line error message)
  const isMultiLine = errorMessage && errorMessage.includes('\n');
  
  if (isMultiLine) {
    // For multi-line messages (like email auth errors), show a more detailed toast
    const lines = errorMessage.split('\n');
    return toast.error(
      (t) => (
        <div className="w-full">
          <div className="flex items-start justify-between mb-2">
            <span className="font-semibold text-sm">Connection Error</span>
            <button
              onClick={() => toast.dismiss(t.id)}
              className="ml-4 flex-shrink-0 bg-white bg-opacity-20 rounded-md p-1 hover:bg-opacity-30 focus:outline-none focus:ring-2 focus:ring-white"
            >
              <XMarkIcon className="h-4 w-4" />
            </button>
          </div>
          <div className="text-sm space-y-1">
            {lines.map((line, index) => (
              <div key={index} className={line.match(/^\d+\./) ? 'ml-2' : ''}>
                {line}
              </div>
            ))}
          </div>
        </div>
      ),
      {
        duration: Infinity,
        style: {
          maxWidth: '600px',
          padding: '12px',
        },
      }
    );
  } else {
    // Simple single-line error
    return toast.error(
      (t) => (
        <div className="flex items-center justify-between w-full">
          <span className="flex-1">{errorMessage}</span>
          <button
            onClick={() => toast.dismiss(t.id)}
            className="ml-4 flex-shrink-0 bg-white bg-opacity-20 rounded-md p-1 hover:bg-opacity-30 focus:outline-none focus:ring-2 focus:ring-white"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
      ),
      {
        duration: Infinity,
        style: {
          maxWidth: '500px',
        },
      }
    );
  }
};

/**
 * Show a custom error toast with full styling (alternative version)
 * @param {string} message - The error message to display
 */
export const showCustomErrorToast = (message) => {
  return toast.custom(
    (t) => (
      <div
        className={`${
          t.visible ? 'animate-enter' : 'animate-leave'
        } max-w-md w-full bg-red-500 shadow-lg rounded-lg pointer-events-auto flex ring-1 ring-black ring-opacity-5`}
      >
        <div className="flex-1 w-0 p-4">
          <div className="flex items-start">
            <div className="flex-shrink-0 pt-0.5">
              <svg
                className="h-10 w-10 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <div className="ml-3 flex-1">
              <p className="text-sm font-medium text-white">Error</p>
              <p className="mt-1 text-sm text-gray-100">{message}</p>
            </div>
          </div>
        </div>
        <div className="flex border-l border-red-600">
          <button
            onClick={() => toast.dismiss(t.id)}
            className="w-full border border-transparent rounded-none rounded-r-lg p-4 flex items-center justify-center text-sm font-medium text-white hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-red-300"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        </div>
      </div>
    ),
    {
      duration: Infinity,
      position: 'top-right',
    }
  );
};

/**
 * Show a success toast with a close button
 * @param {string|JSX.Element} message - The success message to display (can be string or JSX)
 * @param {number} duration - Duration in ms (default: 4000, use Infinity for persistent)
 */
export const showSuccessToast = (message, duration = 4000) => {
  // Handle both string and JSX messages
  const successMessage = React.isValidElement(message)
    ? message
    : (typeof message === 'string' ? message : String(message));

  return toast.success(
    (t) => (
      <div className="flex items-center justify-between w-full">
        <div className="flex-1">{successMessage}</div>
        <button
          onClick={() => toast.dismiss(t.id)}
          className="ml-4 flex-shrink-0 bg-white bg-opacity-20 rounded-md p-1 hover:bg-opacity-30 focus:outline-none focus:ring-2 focus:ring-white"
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
      </div>
    ),
    {
      duration: duration,
      style: {
        maxWidth: '500px',
      },
    }
  );
};

/**
 * Show a warning toast with a close button
 * @param {string|JSX.Element} message - The warning message to display (can be string or JSX)
 * @param {number} duration - Duration in ms (default: 5000, use Infinity for persistent)
 */
export const showWarningToast = (message, duration = 5000) => {
  // Handle both string and JSX messages
  const warningMessage = React.isValidElement(message)
    ? message
    : (typeof message === 'string' ? message : String(message));

  return toast.custom(
    (t) => (
      <div className="flex items-center justify-between w-full bg-amber-500 text-white rounded-lg shadow-lg p-4">
        <div className="flex items-center flex-1">
          <span className="text-2xl mr-3">⚠️</span>
          <div className="flex-1">{warningMessage}</div>
        </div>
        <button
          onClick={() => toast.dismiss(t.id)}
          className="ml-4 flex-shrink-0 bg-white bg-opacity-20 rounded-md p-1 hover:bg-opacity-30 focus:outline-none focus:ring-2 focus:ring-white"
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
      </div>
    ),
    {
      duration: duration,
      position: 'top-center',
    }
  );
};

/**
 * Show an info toast with a close button
 * @param {string|JSX.Element} message - The info message to display (can be string or JSX)
 * @param {number} duration - Duration in ms (default: 4000, use Infinity for persistent)
 */
export const showInfoToast = (message, duration = 4000) => {
  // Handle both string and JSX messages
  const infoMessage = React.isValidElement(message)
    ? message
    : (typeof message === 'string' ? message : String(message));

  return toast(
    (t) => (
      <div className="flex items-center justify-between w-full">
        <div className="flex-1">{infoMessage}</div>
        <button
          onClick={() => toast.dismiss(t.id)}
          className="ml-4 flex-shrink-0 bg-white bg-opacity-20 rounded-md p-1 hover:bg-opacity-30 focus:outline-none focus:ring-2 focus:ring-gray-400"
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
      </div>
    ),
    {
      duration: duration,
      icon: 'ℹ️',
      style: {
        maxWidth: '500px',
      },
    }
  );
};

// CSS for animations (add to your global CSS or Tailwind config)
const animationStyles = `
  @keyframes enter {
    from {
      opacity: 0;
      transform: translateX(100%);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @keyframes leave {
    from {
      opacity: 1;
      transform: translateX(0);
    }
    to {
      opacity: 0;
      transform: translateX(100%);
    }
  }

  .animate-enter {
    animation: enter 0.3s ease-out;
  }

  .animate-leave {
    animation: leave 0.3s ease-in forwards;
  }
`;

// Inject animation styles
if (typeof document !== 'undefined') {
  const style = document.createElement('style');
  style.textContent = animationStyles;
  document.head.appendChild(style);
}