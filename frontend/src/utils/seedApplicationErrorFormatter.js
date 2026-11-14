/**
 * Formatter for seed application validation errors
 * Provides user-friendly messages and helpful suggestions
 */

export const formatSeedApplicationError = (error) => {
  const { path, message, schema_path } = error;
  
  // Extract the field name from path
  const fieldName = path ? path[path.length - 1] : 'Unknown field';
  const parentPath = path ? path.slice(0, -1) : [];
  
  // Common error patterns and their user-friendly messages
  const errorPatterns = [
    {
      pattern: /is not of type 'object'/,
      getMessage: (match) => ({
        title: 'Invalid Data Type',
        description: 'This field expects a JSON object but received a string.',
        suggestion: 'Ensure this field contains parsed JSON data, not a JSON string.',
        example: getExampleForField(fieldName)
      })
    },
    {
      pattern: /is not of type 'array'/,
      getMessage: (match) => ({
        title: 'Invalid Data Type',
        description: 'This field expects an array but received a string.',
        suggestion: 'Ensure this field contains a parsed JSON array.',
        example: getArrayExampleForField(fieldName)
      })
    },
    {
      pattern: /'(.+)' is a required property/,
      getMessage: (match) => ({
        title: 'Missing Required Field',
        description: `The field "${match[1]}" is required but was not provided.`,
        suggestion: `Add the "${match[1]}" field with an appropriate value.`,
        example: getRequiredFieldExample(match[1])
      })
    },
    {
      pattern: /does not match '\^(.+)\$'/,
      getMessage: (match) => ({
        title: 'Invalid Format',
        description: 'The value does not match the required format.',
        suggestion: getFormatSuggestion(match[1]),
        example: getFormatExample(match[1])
      })
    },
    {
      pattern: /'(.+)' is not one of \[(.+)\]/,
      getMessage: (match) => ({
        title: 'Invalid Value',
        description: `"${match[1]}" is not a valid option.`,
        suggestion: `Choose one of: ${match[2]}`,
        example: null
      })
    }
  ];
  
  // Find matching pattern
  for (const { pattern, getMessage } of errorPatterns) {
    const match = message.match(pattern);
    if (match) {
      return getMessage(match);
    }
  }
  
  // Default message
  return {
    title: 'Validation Error',
    description: message,
    suggestion: 'Check the field value and ensure it meets the requirements.',
    example: null
  };
};

// Helper functions to provide field-specific examples
function getExampleForField(fieldName) {
  const examples = {
    sample_output: {
      wrong: '"{\\"status\\": \\"success\\", \\"data\\": {}}"',
      correct: '{"status": "success", "data": {}}'
    },
    sample_input: {
      wrong: '"{\\"id\\": 123, \\"name\\": \\"test\\"}"',
      correct: '{"id": 123, "name": "test"}'
    },
    parameters: {
      wrong: '"[{\\"name\\": \\"id\\", \\"type\\": \\"string\\"}]"',
      correct: '[{"name": "id", "type": "string"}]'
    },
    auth_config: {
      wrong: '"{\\"header_name\\": \\"X-API-Key\\"}"',
      correct: '{"header_name": "X-API-Key"}'
    }
  };
  
  return examples[fieldName] || null;
}

function getArrayExampleForField(fieldName) {
  const examples = {
    parameters: {
      wrong: '"[{\\"name\\": \\"param1\\"}]"',
      correct: '[{"name": "param1", "type": "string", "required": true}]'
    },
    services: {
      wrong: '"services"',
      correct: '[]'
    },
    events: {
      wrong: '"events"',
      correct: '[]'
    }
  };
  
  return examples[fieldName] || null;
}

function getRequiredFieldExample(fieldName) {
  const examples = {
    app_name: '"My Application"',
    app_type: '"global" or "tenant"',
    category: '"Integration"',
    auth_type: '"api_key", "oauth2", "basic", "none", etc.',
    version: '"1.0.0"',
    event_name: '"Webhook Received"',
    description: '"A clear description of the functionality"',
    service_type: '"api_call", "webhook", "email_send", etc.',
    event_type: '"webhook", "schedule", "manual", etc.',
    configuration: '{}'
  };
  
  return examples[fieldName] ? `Example: ${examples[fieldName]}` : null;
}

function getFormatSuggestion(pattern) {
  const patterns = {
    '[a-z0-9_]+': 'Use only lowercase letters, numbers, and underscores',
    '\\d+\\.\\d+\\.\\d+': 'Use semantic versioning format (e.g., 1.0.0)',
    '[a-zA-Z0-9_]+': 'Use only letters, numbers, and underscores',
    '[a-zA-Z0-9_\\s]+': 'Use only letters, numbers, underscores, and spaces'
  };
  
  return patterns[pattern] || 'Check the required format for this field';
}

function getFormatExample(pattern) {
  const examples = {
    '[a-z0-9_]+': 'example_key_123',
    '\\d+\\.\\d+\\.\\d+': '1.0.0',
    '[a-zA-Z0-9_]+': 'ServiceName_1',
    '[a-zA-Z0-9_\\s]+': 'My Event Name'
  };
  
  return examples[pattern] ? `Example: ${examples[pattern]}` : null;
}

// Format multiple errors into a summary
export const formatErrorSummary = (errors) => {
  const errorTypes = {
    type: [],
    required: [],
    format: [],
    value: [],
    other: []
  };
  
  errors.forEach(error => {
    const formatted = formatSeedApplicationError(error);
    
    if (error.message.includes('is not of type')) {
      errorTypes.type.push(error);
    } else if (error.message.includes('is a required property')) {
      errorTypes.required.push(error);
    } else if (error.message.includes('does not match')) {
      errorTypes.format.push(error);
    } else if (error.message.includes('is not one of')) {
      errorTypes.value.push(error);
    } else {
      errorTypes.other.push(error);
    }
  });
  
  const summary = [];
  
  if (errorTypes.type.length > 0) {
    summary.push(`${errorTypes.type.length} field(s) have incorrect data types`);
  }
  if (errorTypes.required.length > 0) {
    summary.push(`${errorTypes.required.length} required field(s) are missing`);
  }
  if (errorTypes.format.length > 0) {
    summary.push(`${errorTypes.format.length} field(s) have invalid formats`);
  }
  if (errorTypes.value.length > 0) {
    summary.push(`${errorTypes.value.length} field(s) have invalid values`);
  }
  if (errorTypes.other.length > 0) {
    summary.push(`${errorTypes.other.length} other validation error(s)`);
  }
  
  return summary.join(', ');
};