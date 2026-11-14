/**
 * Field Matcher Utility
 * Provides intelligent field matching between parameter names and available variables
 * Used for auto-suggestions in the flow designer
 */

/**
 * Calculate similarity score between two strings (0-1, higher is better)
 * Uses a combination of exact match, contains, starts with, and Levenshtein distance
 */
const calculateSimilarity = (str1, str2) => {
  if (!str1 || !str2) return 0;

  const s1 = str1.toLowerCase().trim();
  const s2 = str2.toLowerCase().trim();

  // Exact match
  if (s1 === s2) return 1.0;

  // Starts with (high priority)
  if (s1.startsWith(s2) || s2.startsWith(s1)) return 0.9;

  // Contains (medium priority)
  if (s1.includes(s2) || s2.includes(s1)) return 0.7;

  // Calculate Levenshtein distance for fuzzy matching
  const distance = levenshteinDistance(s1, s2);
  const maxLength = Math.max(s1.length, s2.length);

  // Convert distance to similarity score (0-1)
  const similarity = 1 - (distance / maxLength);

  // Only return if similarity is above threshold
  return similarity > 0.5 ? similarity * 0.6 : 0;
};

/**
 * Calculate Levenshtein distance between two strings
 * (minimum number of single-character edits required to transform one string into another)
 */
const levenshteinDistance = (str1, str2) => {
  const matrix = [];

  for (let i = 0; i <= str2.length; i++) {
    matrix[i] = [i];
  }

  for (let j = 0; j <= str1.length; j++) {
    matrix[0][j] = j;
  }

  for (let i = 1; i <= str2.length; i++) {
    for (let j = 1; j <= str1.length; j++) {
      if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1, // substitution
          matrix[i][j - 1] + 1,     // insertion
          matrix[i - 1][j] + 1      // deletion
        );
      }
    }
  }

  return matrix[str2.length][str1.length];
};

/**
 * Normalize field name for comparison
 * Removes common prefixes, suffixes, and separators
 */
const normalizeFieldName = (fieldName) => {
  if (!fieldName) return '';

  let normalized = fieldName.toLowerCase().trim();

  // Remove common prefixes
  const prefixes = ['input_', 'output_', 'user_', 'data_', 'field_', 'param_', 'value_'];
  for (const prefix of prefixes) {
    if (normalized.startsWith(prefix)) {
      normalized = normalized.substring(prefix.length);
      break;
    }
  }

  // Remove common suffixes
  const suffixes = ['_id', '_name', '_value', '_data', '_field', '_param'];
  for (const suffix of suffixes) {
    if (normalized.endsWith(suffix)) {
      normalized = normalized.substring(0, normalized.length - suffix.length);
      break;
    }
  }

  // Replace separators with spaces for better matching
  normalized = normalized.replace(/[_-]/g, ' ');

  return normalized.trim();
};

/**
 * Extract all variable paths from availableVariables object
 * Returns array of { path, score, category, displayName }
 */
const extractVariablePaths = (availableVariables, nodeMetadata = {}) => {
  const paths = [];

  // Helper to recursively extract paths
  const extractFromObject = (obj, prefix, category) => {
    if (!obj || typeof obj !== 'object') return;

    Object.entries(obj).forEach(([key, value]) => {
      const path = prefix ? `${prefix}.${key}` : key;

      // Add this path
      paths.push({
        path,
        category,
        key,
        displayName: key,
        value: value,
        type: typeof value
      });

      // Recurse for nested objects (but not arrays)
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        extractFromObject(value, path, category);
      }
    });
  };

  // Extract from each category
  if (availableVariables.input) {
    extractFromObject(availableVariables.input, 'input', 'Trigger Input');
  }

  if (availableVariables.node_outputs) {
    Object.entries(availableVariables.node_outputs).forEach(([nodeId, nodeData]) => {
      const nodeInfo = nodeMetadata[nodeId] || {};
      const nodeLabel = nodeInfo.label || nodeId;
      extractFromObject(nodeData, `node_outputs.${nodeId}`, `Previous Steps (${nodeLabel})`);
    });
  }

  if (availableVariables.loop) {
    extractFromObject(availableVariables.loop, 'loop', 'Current Item');
  }

  if (availableVariables.flow) {
    extractFromObject(availableVariables.flow, 'flow', 'Flow Information');
  }

  if (availableVariables.global) {
    extractFromObject(availableVariables.global, 'global', 'Global Variables');
  }

  if (availableVariables.data) {
    extractFromObject(availableVariables.data, 'data', 'Data');
  }

  return paths;
};

/**
 * Find best matching variables for a given field name
 * Returns array of matches sorted by score (highest first)
 *
 * @param {string} fieldName - The field name to match against
 * @param {object} availableVariables - Available variables from flow context
 * @param {object} nodeMetadata - Node metadata for labels
 * @param {number} maxResults - Maximum number of results to return
 * @param {number} minScore - Minimum similarity score (0-1)
 * @returns {array} Array of matches with { path, score, category, suggestion }
 */
export const findMatchingVariables = (
  fieldName,
  availableVariables = {},
  nodeMetadata = {},
  maxResults = 3,
  minScore = 0.6
) => {
  if (!fieldName || !availableVariables) return [];

  // Extract all variable paths
  const variablePaths = extractVariablePaths(availableVariables, nodeMetadata);

  // Normalize the field name
  const normalizedFieldName = normalizeFieldName(fieldName);

  // Calculate scores for each variable path
  const scoredMatches = variablePaths.map(variable => {
    const normalizedKey = normalizeFieldName(variable.key);
    const score = calculateSimilarity(normalizedFieldName, normalizedKey);

    return {
      ...variable,
      score,
      suggestion: `Use ${variable.category} → ${variable.key}`
    };
  });

  // Filter by minimum score and sort by score descending
  const matches = scoredMatches
    .filter(match => match.score >= minScore)
    .sort((a, b) => b.score - a.score)
    .slice(0, maxResults);

  return matches;
};

/**
 * Auto-map fields from availableVariables to target parameters
 * Attempts to find the best match for each parameter
 *
 * @param {array} parameters - Array of parameter objects with { name, type, required }
 * @param {object} availableVariables - Available variables from flow context
 * @param {object} nodeMetadata - Node metadata for labels
 * @param {number} minScore - Minimum similarity score for auto-mapping
 * @returns {object} Mapping of parameter names to variable paths
 */
export const autoMapFields = (
  parameters = [],
  availableVariables = {},
  nodeMetadata = {},
  minScore = 0.7
) => {
  const mapping = {};

  parameters.forEach(param => {
    const matches = findMatchingVariables(
      param.name,
      availableVariables,
      nodeMetadata,
      1, // Only get best match
      minScore
    );

    if (matches.length > 0) {
      mapping[param.name] = matches[0].path;
    }
  });

  return mapping;
};

/**
 * Check if a field name suggests it needs dynamic data
 * (vs static values)
 */
export const suggestsDynamicData = (fieldName) => {
  if (!fieldName) return false;

  const dynamicIndicators = [
    'id', 'email', 'name', 'user', 'customer', 'data', 'value',
    'result', 'output', 'response', 'message', 'content', 'text',
    'body', 'subject', 'title', 'description', 'status', 'type'
  ];

  const normalized = normalizeFieldName(fieldName);
  return dynamicIndicators.some(indicator =>
    normalized.includes(indicator)
  );
};

/**
 * Get friendly suggestion text for a match
 */
export const getFriendlySuggestion = (match) => {
  if (!match) return '';

  return `💡 Suggestion: ${match.suggestion}`;
};
