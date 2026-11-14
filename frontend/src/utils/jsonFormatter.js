/**
 * Utility functions for formatting and displaying JSON data
 */

/**
 * Format a JSON string for display with proper indentation
 * @param {string} jsonString - The JSON string to format
 * @returns {string} - Formatted JSON string or error message
 */
export const formatJsonString = (jsonString) => {
  try {
    const parsed = JSON.parse(jsonString);
    return JSON.stringify(parsed, null, 2);
  } catch (error) {
    return jsonString; // Return original if parsing fails
  }
};

/**
 * Validate and format JSON with error highlighting
 * @param {string} jsonString - The JSON string to validate
 * @returns {object} - { valid: boolean, formatted: string, error: object|null }
 */
export const validateAndFormatJson = (jsonString) => {
  try {
    const parsed = JSON.parse(jsonString);
    return {
      valid: true,
      formatted: JSON.stringify(parsed, null, 2),
      error: null
    };
  } catch (error) {
    // Extract error details
    const errorMatch = error.message.match(/at position (\d+)/);
    const position = errorMatch ? parseInt(errorMatch[1], 10) : null;
    
    return {
      valid: false,
      formatted: jsonString,
      error: {
        message: error.message,
        position: position,
        line: position ? getLineFromPosition(jsonString, position) : null
      }
    };
  }
};

/**
 * Get line number from character position in string
 * @param {string} str - The string
 * @param {number} position - Character position
 * @returns {object} - { line: number, column: number }
 */
const getLineFromPosition = (str, position) => {
  const lines = str.substring(0, position).split('\n');
  return {
    line: lines.length,
    column: lines[lines.length - 1].length + 1
  };
};

/**
 * Truncate long JSON strings for preview
 * @param {string} jsonString - The JSON string
 * @param {number} maxLength - Maximum length
 * @returns {string} - Truncated string
 */
export const truncateJson = (jsonString, maxLength = 100) => {
  if (jsonString.length <= maxLength) {
    return jsonString;
  }
  
  // Try to truncate at a sensible point
  const truncated = jsonString.substring(0, maxLength);
  const lastComma = truncated.lastIndexOf(',');
  const lastBrace = Math.max(truncated.lastIndexOf('}'), truncated.lastIndexOf(']'));
  
  const cutPoint = Math.max(lastComma, lastBrace);
  if (cutPoint > maxLength * 0.8) {
    return truncated.substring(0, cutPoint) + '...';
  }
  
  return truncated + '...';
};

/**
 * Extract and format specific fields from JSON for preview
 * @param {string} jsonString - The JSON string
 * @param {array} fields - Fields to extract
 * @returns {object} - Extracted fields
 */
export const extractJsonFields = (jsonString, fields = []) => {
  try {
    const parsed = JSON.parse(jsonString);
    const extracted = {};
    
    fields.forEach(field => {
      if (parsed.hasOwnProperty(field)) {
        extracted[field] = parsed[field];
      }
    });
    
    return extracted;
  } catch (error) {
    return null;
  }
};

/**
 * Convert validation error paths to human-readable format
 * @param {array} path - The error path array
 * @returns {string} - Human-readable path
 */
export const formatErrorPath = (path) => {
  if (!path || !Array.isArray(path)) return 'Unknown field';
  
  return path.map((segment, index) => {
    if (typeof segment === 'number') {
      return `[${segment}]`;
    }
    
    // Convert snake_case to Title Case
    const formatted = segment
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
    
    return index === 0 ? formatted : `.${formatted}`;
  }).join('');
};