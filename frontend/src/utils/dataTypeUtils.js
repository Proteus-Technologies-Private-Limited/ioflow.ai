// Data type utilities for parameter input handling

export const DataTypes = {
  STRING: 'string',
  NUMBER: 'number',
  INTEGER: 'integer',
  BOOLEAN: 'boolean',
  ARRAY: 'array',
  OBJECT: 'object',
  JSON: 'json',
  DATE: 'date',
  DATETIME: 'datetime',
  EMAIL: 'email',
  URL: 'url',
  XML: 'xml',
  FILE: 'file',
};

// Detect the type of a value
export const detectValueType = (value) => {
  if (value === null || value === undefined) return DataTypes.STRING;
  if (Array.isArray(value)) return DataTypes.ARRAY;
  if (value instanceof Date) return DataTypes.DATE;
  if (typeof value === 'object') return DataTypes.OBJECT;
  if (typeof value === 'boolean') return DataTypes.BOOLEAN;
  if (typeof value === 'number') {
    return Number.isInteger(value) ? DataTypes.INTEGER : DataTypes.NUMBER;
  }
  if (typeof value === 'string') {
    // Try to detect special string types
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return DataTypes.DATE;
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) return DataTypes.DATETIME;
    if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return DataTypes.EMAIL;
    if (/^https?:\/\//.test(value)) return DataTypes.URL;
  }
  return DataTypes.STRING;
};

// Generate default value based on data type
export const getDefaultValue = (dataType, defaultValue = null) => {
  if (defaultValue !== null && defaultValue !== undefined) {
    try {
      // Try to parse default value if it's a string representation
      if (typeof defaultValue === 'string' && (dataType === DataTypes.ARRAY || dataType === DataTypes.OBJECT || dataType === DataTypes.JSON)) {
        return JSON.parse(defaultValue);
      }
      return defaultValue;
    } catch {
      // If parsing fails, continue with type-based default
    }
  }

  switch (dataType) {
    case DataTypes.ARRAY:
      return [];
    case DataTypes.OBJECT:
    case DataTypes.JSON:
      return {};
    case DataTypes.NUMBER:
    case DataTypes.INTEGER:
      return 0;
    case DataTypes.BOOLEAN:
      return false;
    case DataTypes.DATE:
      return new Date().toISOString().split('T')[0];
    case DataTypes.DATETIME:
      return new Date().toISOString();
    case DataTypes.FILE:
      return null;
    default:
      return '';
  }
};

// Validate value against data type
export const validateValue = (value, dataType, validation = {}) => {
  if (value === null || value === undefined) {
    return { isValid: false, error: 'Value is required' };
  }

  switch (dataType) {
    case DataTypes.ARRAY:
      if (!Array.isArray(value)) {
        return { isValid: false, error: 'Value must be an array' };
      }
      if (validation.minItems && value.length < validation.minItems) {
        return { isValid: false, error: `Array must have at least ${validation.minItems} items` };
      }
      if (validation.maxItems && value.length > validation.maxItems) {
        return { isValid: false, error: `Array must have at most ${validation.maxItems} items` };
      }
      break;

    case DataTypes.OBJECT:
    case DataTypes.JSON:
      if (typeof value !== 'object' || Array.isArray(value)) {
        return { isValid: false, error: 'Value must be an object' };
      }
      break;

    case DataTypes.NUMBER:
      if (typeof value !== 'number' || isNaN(value)) {
        return { isValid: false, error: 'Value must be a number' };
      }
      if (validation.min !== undefined && value < validation.min) {
        return { isValid: false, error: `Value must be at least ${validation.min}` };
      }
      if (validation.max !== undefined && value > validation.max) {
        return { isValid: false, error: `Value must be at most ${validation.max}` };
      }
      break;

    case DataTypes.INTEGER:
      if (!Number.isInteger(value)) {
        return { isValid: false, error: 'Value must be an integer' };
      }
      if (validation.min !== undefined && value < validation.min) {
        return { isValid: false, error: `Value must be at least ${validation.min}` };
      }
      if (validation.max !== undefined && value > validation.max) {
        return { isValid: false, error: `Value must be at most ${validation.max}` };
      }
      break;

    case DataTypes.BOOLEAN:
      if (typeof value !== 'boolean') {
        return { isValid: false, error: 'Value must be true or false' };
      }
      break;

    case DataTypes.STRING:
      if (typeof value !== 'string') {
        return { isValid: false, error: 'Value must be a string' };
      }
      if (validation.minLength && value.length < validation.minLength) {
        return { isValid: false, error: `String must be at least ${validation.minLength} characters` };
      }
      if (validation.maxLength && value.length > validation.maxLength) {
        return { isValid: false, error: `String must be at most ${validation.maxLength} characters` };
      }
      if (validation.pattern) {
        const regex = new RegExp(validation.pattern);
        if (!regex.test(value)) {
          return { isValid: false, error: 'Value does not match required pattern' };
        }
      }
      break;

    case DataTypes.EMAIL:
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        return { isValid: false, error: 'Invalid email format' };
      }
      break;

    case DataTypes.URL:
      try {
        new URL(value);
      } catch {
        return { isValid: false, error: 'Invalid URL format' };
      }
      break;

    case DataTypes.DATE:
      if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
        return { isValid: false, error: 'Invalid date format (YYYY-MM-DD)' };
      }
      break;

    case DataTypes.DATETIME:
      if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/.test(value)) {
        return { isValid: false, error: 'Invalid datetime format' };
      }
      break;
  }

  return { isValid: true };
};

// Convert value to expected type
export const convertToType = (value, dataType) => {
  if (value === null || value === undefined) {
    return getDefaultValue(dataType);
  }

  try {
    switch (dataType) {
      case DataTypes.ARRAY:
        if (Array.isArray(value)) return value;
        if (typeof value === 'string') {
          try {
            const parsed = JSON.parse(value);
            return Array.isArray(parsed) ? parsed : [value];
          } catch {
            return [value];
          }
        }
        return [value];

      case DataTypes.OBJECT:
      case DataTypes.JSON:
        if (typeof value === 'object' && !Array.isArray(value)) return value;
        if (typeof value === 'string') {
          try {
            const parsed = JSON.parse(value);
            return typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : { value };
          } catch {
            return { value };
          }
        }
        return { value };

      case DataTypes.NUMBER:
        return parseFloat(value) || 0;

      case DataTypes.INTEGER:
        return parseInt(value) || 0;

      case DataTypes.BOOLEAN:
        if (typeof value === 'boolean') return value;
        if (typeof value === 'string') {
          return value.toLowerCase() === 'true';
        }
        return !!value;

      case DataTypes.DATE:
      case DataTypes.DATETIME:
      case DataTypes.EMAIL:
      case DataTypes.URL:
      case DataTypes.STRING:
      default:
        return String(value);
    }
  } catch {
    return getDefaultValue(dataType);
  }
};

// Generate sample data for a given schema
export const generateSampleData = (variable) => {
  const { dataType, validation = {}, defaultValue, sampleValue } = variable;
  
  if (sampleValue) return sampleValue;
  if (defaultValue) return convertToType(defaultValue, dataType);

  switch (dataType) {
    case DataTypes.ARRAY:
      const itemType = variable.itemType || DataTypes.STRING;
      const itemCount = validation.minItems || 2;
      return Array(itemCount).fill(null).map((_, i) => 
        generateSampleData({ dataType: itemType, name: `item${i + 1}` })
      );

    case DataTypes.OBJECT:
    case DataTypes.JSON:
      const sampleObj = {};
      if (variable.properties) {
        Object.entries(variable.properties).forEach(([key, prop]) => {
          sampleObj[key] = generateSampleData(prop);
        });
      } else {
        sampleObj.sampleKey1 = 'sampleValue1';
        sampleObj.sampleKey2 = 123;
        sampleObj.sampleKey3 = true;
      }
      return sampleObj;

    case DataTypes.NUMBER:
      return validation.min || 42;

    case DataTypes.INTEGER:
      return validation.min || 1;

    case DataTypes.BOOLEAN:
      return true;

    case DataTypes.DATE:
      return new Date().toISOString().split('T')[0];

    case DataTypes.DATETIME:
      return new Date().toISOString();

    case DataTypes.EMAIL:
      return 'user@example.com';

    case DataTypes.URL:
      return 'https://example.com';

    default:
      return variable.name || 'sample value';
  }
};