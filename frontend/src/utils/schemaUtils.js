/**
 * Utility functions for handling JSON Schema operations
 */

/**
 * Convert a nested object JSON schema to flattened dot notation format
 * @param {Object} schema - JSON Schema object
 * @param {string} prefix - Prefix for nested properties
 * @returns {Array} Array of field definitions with dot notation paths
 */
export const flattenJsonSchema = (schema, prefix = '') => {
  const fields = [];
  
  if (schema.type === 'object' && schema.properties) {
    Object.entries(schema.properties).forEach(([key, value]) => {
      const fieldPath = prefix ? `${prefix}.${key}` : key;
      
      if (value.type === 'object' && value.properties) {
        // Add the object field itself
        fields.push({
          id: Date.now() + Math.random(),
          field_name: fieldPath,
          friendly_name: value.description || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          data_type: 'object',
          is_required: schema.required?.includes(key) || false,
          description: value.description || `Object containing ${Object.keys(value.properties).length} properties`,
          display_order: fields.length,
          schema: value,
        });
        
        // Recursively process nested object properties
        const nestedFields = flattenJsonSchema(value, fieldPath);
        fields.push(...nestedFields);
      } else {
        // Add regular field
        const field = {
          id: Date.now() + Math.random(),
          field_name: fieldPath,
          friendly_name: value.description || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
          data_type: value.type || 'string',
          is_required: schema.required?.includes(key) || false,
          description: value.description || '',
          display_order: fields.length,
          schema: value,
        };
        
        // Preserve parameter lookup configuration
        if (value.parameterLookup) {
          field.parameterLookup = value.parameterLookup;
        }
        
        fields.push(field);
      }
    });
  }
  
  return fields;
};

/**
 * Convert flattened fields back to nested JSON Schema
 * @param {Array} fields - Array of field definitions with dot notation paths
 * @returns {Object} JSON Schema object
 */
export const buildNestedSchema = (fields) => {
  const schema = {
    type: 'object',
    properties: {},
    required: []
  };
  
  // Filter out any undefined/null fields and validate field_name exists
  const validFields = (fields || []).filter(field => 
    field && field.field_name && typeof field.field_name === 'string'
  );
  
  // First, identify which object fields have nested properties
  const objectsWithChildren = new Set();
  validFields.forEach(field => {
    const parts = field.field_name.split('.');
    if (parts.length > 1) {
      // This field is nested, so mark all parent paths as having children
      for (let i = 0; i < parts.length - 1; i++) {
        const parentPath = parts.slice(0, i + 1).join('.');
        objectsWithChildren.add(parentPath);
      }
    }
  });
  
  validFields.forEach(field => {
    const parts = field.field_name.split('.');
    let current = schema.properties;
    
    // Navigate/create nested structure
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      if (!current[part]) {
        current[part] = {
          type: 'object',
          properties: {},
          description: `${part} object`
        };
      }
      current = current[part].properties;
    }
    
    // Set the final property
    const lastPart = parts[parts.length - 1];
    if (field.data_type === 'object') {
      // Only create the object if it doesn't have nested children
      if (!objectsWithChildren.has(field.field_name)) {
        current[lastPart] = {
          type: 'object',
          properties: {},
          description: field.description || field.friendly_name
        };
      }
      // If it has children, the structure will be created by the nested fields
    } else {
      current[lastPart] = {
        type: field.data_type,
        description: field.description || field.friendly_name
      };
      
      // Add additional schema properties based on data type
      if (field.data_type === 'string' && field.pattern) {
        current[lastPart].pattern = field.pattern;
      }
      if (field.data_type === 'string' && field.min_length) {
        current[lastPart].minLength = field.min_length;
      }
      if (field.data_type === 'string' && field.max_length) {
        current[lastPart].maxLength = field.max_length;
      }
      if ((field.data_type === 'number' || field.data_type === 'integer') && field.minimum !== undefined) {
        current[lastPart].minimum = field.minimum;
      }
      if ((field.data_type === 'number' || field.data_type === 'integer') && field.maximum !== undefined) {
        current[lastPart].maximum = field.maximum;
      }
      if (field.enum_values && field.enum_values.length > 0) {
        current[lastPart].enum = field.enum_values;
      }
      
      // Preserve parameter lookup configuration
      if (field.parameterLookup) {
        current[lastPart].parameterLookup = field.parameterLookup;
      }
    }
    
    // Handle required fields
    if (field.is_required) {
      // Need to add to the appropriate level's required array
      if (parts.length === 1) {
        schema.required.push(lastPart);
      } else {
        // For nested required fields, we need to traverse and set required at the right level
        let currentSchema = schema.properties;
        for (let i = 0; i < parts.length - 1; i++) {
          const part = parts[i];
          if (!currentSchema[part].required) {
            currentSchema[part].required = [];
          }
          if (i === parts.length - 2) {
            currentSchema[part].required.push(lastPart);
          }
          currentSchema = currentSchema[part].properties;
        }
      }
    }
  });
  
  return schema;
};

/**
 * Validate if a JSON string is a valid JSON Schema
 * @param {string} jsonString - JSON string to validate
 * @returns {Object} { valid: boolean, error?: string, schema?: object }
 */
export const validateJsonSchema = (jsonString) => {
  try {
    const schema = JSON.parse(jsonString);
    
    // Basic JSON Schema validation
    if (!schema.type) {
      return { valid: false, error: 'Schema must have a "type" property' };
    }
    
    if (schema.type === 'object' && !schema.properties) {
      return { valid: false, error: 'Object schema must have "properties"' };
    }
    
    return { valid: true, schema };
  } catch (e) {
    return { valid: false, error: e.message };
  }
};

/**
 * Generate sample data from a JSON Schema
 * @param {Object} schema - JSON Schema object
 * @returns {Object} Sample data object
 */
export const generateSampleFromSchema = (schema, fieldName = '') => {
  if (!schema || !schema.type) return null;
  
  const keyLower = fieldName.toLowerCase();
  
  switch (schema.type) {
    case 'object':
      const obj = {};
      if (schema.properties && Object.keys(schema.properties).length > 0) {
        Object.entries(schema.properties).forEach(([key, propSchema]) => {
          obj[key] = generateSampleFromSchema(propSchema, key);
        });
      } else {
        // If no properties defined, generate a generic object based on field name
        if (fieldName) {
          if (keyLower.includes('address')) {
            return {
              street: '123 Main St',
              city: 'San Francisco',
              state: 'CA',
              zip: '94105'
            };
          }
          if (keyLower.includes('user') || keyLower.includes('customer')) {
            return {
              id: `${fieldName.toUpperCase()}_ID-${Math.floor(Math.random() * 10000)}`,
              name: 'John Doe',
              email: 'user@example.com'
            };
          }
          if (keyLower.includes('order')) {
            return {
              order_id: `ORDER-${Math.floor(Math.random() * 10000)}`,
              amount: 99.99,
              status: 'pending'
            };
          }
          // Generic nested object
          return {
            id: `${fieldName}_id`,
            name: `${fieldName} name`,
            value: `${fieldName} value`
          };
        }
      }
      return obj;
      
    case 'array':
      const itemSchema = schema.items || { type: 'string' };
      return [generateSampleFromSchema(itemSchema, 'item')];
      
    case 'string':
      if (schema.enum) return schema.enum[0];
      if (schema.format === 'date') return '2024-01-01';
      if (schema.format === 'date-time') return new Date().toISOString();
      if (schema.format === 'email') return 'user@example.com';
      if (schema.format === 'uri') return 'https://example.com';
      
      // Generate based on field name
      if (keyLower.includes('email')) return 'user@example.com';
      if (keyLower.includes('phone')) return '+1-555-123-4567';
      if (keyLower.includes('url') || keyLower.includes('link')) return 'https://example.com';
      if (keyLower.includes('name')) {
        if (keyLower.includes('first')) return 'John';
        if (keyLower.includes('last')) return 'Doe';
        if (keyLower.includes('company')) return 'Acme Corp';
        return 'John Doe';
      }
      if (keyLower.includes('address')) return '123 Main St';
      if (keyLower.includes('city')) return 'San Francisco';
      if (keyLower.includes('state')) return 'CA';
      if (keyLower.includes('country')) return 'USA';
      if (keyLower.includes('zip') || keyLower.includes('postal')) return '12345';
      if (keyLower.includes('id')) return `${fieldName.toUpperCase()}-${Math.floor(Math.random() * 10000)}`;
      if (keyLower.includes('status')) return 'active';
      if (keyLower.includes('description')) return 'Sample description';
      if (keyLower.includes('message')) return 'Sample message';
      if (keyLower.includes('title')) return 'Sample Title';
      
      return schema.description || `Sample ${fieldName || 'string'}`;
      
    case 'number':
      if (schema.minimum !== undefined) return schema.minimum;
      if (keyLower.includes('price') || keyLower.includes('amount')) return 99.99;
      if (keyLower.includes('quantity') || keyLower.includes('count')) return 5;
      if (keyLower.includes('age')) return 25;
      if (keyLower.includes('year')) return new Date().getFullYear();
      return 42.5;
      
    case 'integer':
      if (schema.minimum !== undefined) return Math.floor(schema.minimum);
      if (keyLower.includes('quantity') || keyLower.includes('count')) return 5;
      if (keyLower.includes('age')) return 25;
      if (keyLower.includes('year')) return new Date().getFullYear();
      return 42;
      
    case 'boolean':
      return true;
      
    case 'null':
      return null;
      
    default:
      return null;
  }
};