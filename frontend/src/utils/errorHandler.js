/**
 * Utility functions for handling API errors consistently across the application
 */

/**
 * Extract a user-friendly error message from an API error response
 * @param {Error} error - The error object from axios
 * @param {string} defaultMessage - Default message if no specific error found
 * @returns {string} - User-friendly error message
 */
export const getErrorMessage = (error, defaultMessage = 'An error occurred') => {
  // Check if it's a network error
  if (!error.response) {
    if (error.message === 'Network Error') {
      return 'Unable to connect to the server. Please check your connection.';
    }
    if (error.code === 'ERR_NETWORK') {
      return 'Network error: Unable to reach the server.';
    }
    if (error.code === 'ERR_CANCELED') {
      return 'Request was cancelled.';
    }
    return error.message || defaultMessage;
  }

  // Extract error detail from response
  const detail = error.response?.data?.detail;
  
  if (!detail) {
    // Check for other common error fields
    if (error.response?.data?.message) {
      return error.response.data.message;
    }
    if (error.response?.data?.error) {
      return error.response.data.error;
    }
    return defaultMessage;
  }

  // Handle different types of error details
  if (typeof detail === 'string') {
    return formatErrorMessage(detail);
  } 
  
  // Handle validation error arrays from FastAPI/Pydantic
  if (Array.isArray(detail)) {
    const errors = detail.map(err => {
      const field = err.loc ? err.loc[err.loc.length - 1] : 'Field';
      const msg = formatErrorMessage(err.msg || err.message || 'Invalid value');
      return `${field}: ${msg}`;
    });
    return errors.join(', ');
  }
  
  // Handle object error messages
  if (typeof detail === 'object') {
    // Check for seed application validation errors
    if (detail.message === 'Seed application validation failed' && detail.errors) {
      return {
        type: 'validation',
        message: detail.message,
        errors: detail.errors,
        warnings: detail.warnings || []
      };
    }
    
    // Try to extract meaningful message from object
    if (detail.message) {
      return formatErrorMessage(detail.message);
    }
    
    // Check if it's a structured error with errors array
    if (detail.errors && Array.isArray(detail.errors)) {
      return {
        type: 'validation',
        message: 'Validation failed',
        errors: detail.errors,
        warnings: detail.warnings || []
      };
    }
    
    // Last resort: stringify the object
    return JSON.stringify(detail);
  }

  return defaultMessage;
};

/**
 * Format error messages to be more user-friendly
 * @param {string} message - Raw error message
 * @returns {string} - Formatted error message
 */
const formatErrorMessage = (message) => {
  let formatted = message;

  // Replace technical terms with user-friendly ones
  const replacements = {
    'Invalid trigger type': 'Invalid event type',
    'Invalid synchronous flow:': 'Synchronous flow validation failed:',
    'tenant_id': 'tenant',
    'app_id': 'application',
    'flow_id': 'flow',
    'user_id': 'user',
    '_': ' ',
    'KeyError': 'Missing required field',
    'ValueError': 'Invalid value',
  };

  for (const [technical, friendly] of Object.entries(replacements)) {
    formatted = formatted.replace(new RegExp(technical, 'g'), friendly);
  }

  // Capitalize first letter
  return formatted.charAt(0).toUpperCase() + formatted.slice(1);
};

/**
 * Handle common HTTP status codes with appropriate messages
 * @param {number} status - HTTP status code
 * @returns {string|null} - Error message for the status code, or null if not a common error
 */
export const getStatusMessage = (status) => {
  const statusMessages = {
    400: 'Invalid request. Please check your input.',
    401: 'You are not authenticated. Please log in.',
    403: 'You do not have permission to perform this action.',
    404: 'The requested resource was not found.',
    409: 'This action conflicts with existing data.',
    422: 'The provided data is invalid.',
    429: 'Too many requests. Please try again later.',
    500: 'An internal server error occurred. Please try again.',
    502: 'The server is temporarily unavailable.',
    503: 'The service is currently unavailable. Please try again later.',
  };

  return statusMessages[status] || null;
};

/**
 * Get a complete error message with status-based fallback
 * @param {Error} error - The error object
 * @param {string} defaultMessage - Default message
 * @returns {string} - Complete error message
 */
export const getFullErrorMessage = (error, defaultMessage = 'An error occurred') => {
  const errorMessage = getErrorMessage(error, null);
  
  if (errorMessage) {
    return errorMessage;
  }

  // If no specific error message, check status code
  const status = error.response?.status;
  const statusMessage = status ? getStatusMessage(status) : null;
  
  return statusMessage || defaultMessage;
};