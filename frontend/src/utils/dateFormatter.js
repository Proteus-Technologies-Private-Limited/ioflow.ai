/**
 * Utility functions for consistent date/time formatting across the application
 * All dates are displayed in the user's local timezone
 */

/**
 * Format a date/time string to user's local timezone
 * @param {string|Date} dateString - ISO date string or Date object
 * @param {Object} options - Formatting options
 * @returns {string} Formatted date/time string
 */
export const formatDateTime = (dateString, options = {}) => {
  if (!dateString) return '-';
  
  try {
    // If the date string doesn't contain timezone info (no 'Z' or offset), 
    // assume it's UTC by appending 'Z'
    let normalizedDateString = dateString;
    if (typeof dateString === 'string' && 
        !dateString.endsWith('Z') && 
        !dateString.match(/[+-]\d{2}:\d{2}$/)) {
      normalizedDateString = dateString + 'Z';
    }
    
    const date = new Date(normalizedDateString);
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '-';
    }
    
    // Default options for full date/time display
    const defaultOptions = {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    };
    
    return date.toLocaleString(undefined, { ...defaultOptions, ...options });
  } catch (error) {
    console.error('Error formatting date:', error);
    return '-';
  }
};

/**
 * Format a date string to show only date in user's timezone
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted date string
 */
export const formatDate = (dateString) => {
  return formatDateTime(dateString, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: undefined,
    minute: undefined,
    second: undefined,
  });
};

/**
 * Format a date string to show only time in user's timezone
 * @param {string|Date} dateString - ISO date string or Date object
 * @param {boolean} includeSeconds - Whether to include seconds
 * @returns {string} Formatted time string
 */
export const formatTime = (dateString, includeSeconds = true) => {
  const options = {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
    year: undefined,
    month: undefined,
    day: undefined,
  };
  
  if (includeSeconds) {
    options.second = '2-digit';
  }
  
  return formatDateTime(dateString, options);
};

/**
 * Format a timestamp for log entries (includes milliseconds)
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Formatted timestamp with milliseconds
 */
export const formatTimestamp = (dateString) => {
  if (!dateString) return '-';
  
  try {
    // If the date string doesn't contain timezone info (no 'Z' or offset), 
    // assume it's UTC by appending 'Z'
    let normalizedDateString = dateString;
    if (typeof dateString === 'string' && 
        !dateString.endsWith('Z') && 
        !dateString.match(/[+-]\d{2}:\d{2}$/)) {
      normalizedDateString = dateString + 'Z';
    }
    
    const date = new Date(normalizedDateString);
    
    if (isNaN(date.getTime())) {
      return '-';
    }
    
    // Format time with milliseconds
    const timeStr = date.toLocaleTimeString(undefined, {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    });
    
    // Add milliseconds
    const ms = date.getMilliseconds().toString().padStart(3, '0');
    
    return `${timeStr}.${ms}`;
  } catch (error) {
    console.error('Error formatting timestamp:', error);
    return '-';
  }
};

/**
 * Format a relative time (e.g., "2 minutes ago")
 * @param {string|Date} dateString - ISO date string or Date object
 * @returns {string} Relative time string
 */
export const formatRelativeTime = (dateString) => {
  if (!dateString) return '-';
  
  try {
    // If the date string doesn't contain timezone info (no 'Z' or offset), 
    // assume it's UTC by appending 'Z'
    let normalizedDateString = dateString;
    if (typeof dateString === 'string' && 
        !dateString.endsWith('Z') && 
        !dateString.match(/[+-]\d{2}:\d{2}$/)) {
      normalizedDateString = dateString + 'Z';
    }
    
    const date = new Date(normalizedDateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) {
      return 'just now';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    } else if (diffInSeconds < 604800) {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days} day${days !== 1 ? 's' : ''} ago`;
    } else {
      return formatDateTime(date);
    }
  } catch (error) {
    console.error('Error formatting relative time:', error);
    return '-';
  }
};

/**
 * Get timezone display string (e.g., "PST", "EST")
 * @returns {string} Timezone abbreviation
 */
export const getTimezoneDisplay = () => {
  const date = new Date();
  const timeStr = date.toLocaleTimeString('en-US', { timeZoneName: 'short' });
  const parts = timeStr.split(' ');
  return parts[parts.length - 1]; // Gets the timezone part
};

/**
 * Format duration between two dates
 * @param {string|Date} startDate - Start date
 * @param {string|Date} endDate - End date (optional, uses current time if not provided)
 * @returns {string} Formatted duration
 */
export const formatDuration = (startDate, endDate = null) => {
  if (!startDate) return '-';
  
  try {
    // Normalize start date
    let normalizedStartDate = startDate;
    if (typeof startDate === 'string' && 
        !startDate.endsWith('Z') && 
        !startDate.match(/[+-]\d{2}:\d{2}$/)) {
      normalizedStartDate = startDate + 'Z';
    }
    
    // Normalize end date if provided
    let normalizedEndDate = endDate;
    if (endDate && typeof endDate === 'string' && 
        !endDate.endsWith('Z') && 
        !endDate.match(/[+-]\d{2}:\d{2}$/)) {
      normalizedEndDate = endDate + 'Z';
    }
    
    const start = new Date(normalizedStartDate);
    const end = normalizedEndDate ? new Date(normalizedEndDate) : new Date();
    const durationMs = end - start;
    
    if (durationMs < 0) return '-';
    
    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    
    if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    } else if (seconds > 0) {
      return `${seconds}s`;
    } else {
      return `${durationMs}ms`;
    }
  } catch (error) {
    console.error('Error formatting duration:', error);
    return '-';
  }
};