/**
 * ValidationEngine - Client-side validation for landing page form fields
 *
 * Supports: required, pattern (regex), minLength, maxLength, min, max, custom message
 */

export function validateField(value, rules) {
  if (!rules) return { isValid: true, errors: [] };

  const errors = [];
  const val = value ?? '';
  const strVal = String(val);

  if (rules.required && (val === '' || val === null || val === undefined)) {
    errors.push(rules.message || 'This field is required');
    return { isValid: false, errors };
  }

  // Skip other validations if value is empty and not required
  if (val === '' || val === null || val === undefined) {
    return { isValid: true, errors: [] };
  }

  if (rules.pattern) {
    try {
      const regex = new RegExp(rules.pattern);
      if (!regex.test(strVal)) {
        errors.push(rules.message || `Value does not match the expected format`);
      }
    } catch {
      // Invalid regex, skip
    }
  }

  if (rules.minLength != null && strVal.length < rules.minLength) {
    errors.push(rules.message || `Must be at least ${rules.minLength} characters`);
  }

  if (rules.maxLength != null && strVal.length > rules.maxLength) {
    errors.push(rules.message || `Must be at most ${rules.maxLength} characters`);
  }

  if (rules.min != null && Number(val) < rules.min) {
    errors.push(rules.message || `Must be at least ${rules.min}`);
  }

  if (rules.max != null && Number(val) > rules.max) {
    errors.push(rules.message || `Must be at most ${rules.max}`);
  }

  return { isValid: errors.length === 0, errors };
}

export function validateAllFields(formData, validations) {
  if (!validations) return { isValid: true, fieldErrors: {} };

  const fieldErrors = {};
  let isValid = true;

  for (const [fieldName, rules] of Object.entries(validations)) {
    const result = validateField(formData[fieldName], rules);
    if (!result.isValid) {
      isValid = false;
      fieldErrors[fieldName] = result.errors;
    }
  }

  return { isValid, fieldErrors };
}
