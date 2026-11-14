import React, { useState, useEffect, useCallback } from 'react';

/**
 * ApiDropdown - Dropdown that fetches options from a REST API via backend proxy
 *
 * Props:
 *   slug       - Public URL slug for the proxy endpoint
 *   config     - { url, method, headers, response_path, label_field, value_field, depends_on, placeholder }
 *   value      - Current selected value
 *   onChange   - (value) => void
 *   formData   - Full form data (for depends_on lookups)
 *   fieldName  - Name of this field
 *   disabled   - Whether the dropdown is disabled
 */
export default function ApiDropdown({ slug, config, value, onChange, formData, fieldName, disabled }) {
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const dependsOnValue = config.depends_on ? formData?.[config.depends_on] : null;

  const fetchOptions = useCallback(async () => {
    if (!config.url) return;

    // If depends_on is set but value is empty, clear options
    if (config.depends_on && !dependsOnValue) {
      setOptions([]);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let url = config.url;
      let params = {};

      // Replace {depends_on_value} placeholder in URL
      if (dependsOnValue) {
        url = url.replace(/\{depends_on_value\}/g, encodeURIComponent(dependsOnValue));
        params[config.depends_on] = dependsOnValue;
      }

      const response = await fetch(`/api/v1/public-apps/${slug}/proxy-dropdown`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          method: config.method || 'GET',
          headers: config.headers || {},
          params,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const result = await response.json();
      const data = result.data;

      // Extract options using response_path
      let items = data;
      if (config.response_path) {
        const pathParts = config.response_path.split('.');
        for (const part of pathParts) {
          if (items && typeof items === 'object') {
            items = items[part];
          } else {
            items = [];
            break;
          }
        }
      }

      if (!Array.isArray(items)) {
        items = [];
      }

      const labelField = config.label_field || 'label';
      const valueField = config.value_field || 'value';

      const mapped = items.map((item) => {
        if (typeof item === 'string') {
          return { label: item, value: item };
        }
        return {
          label: String(item[labelField] ?? item[valueField] ?? ''),
          value: String(item[valueField] ?? item[labelField] ?? ''),
        };
      });

      setOptions(mapped);
    } catch (err) {
      setError('Failed to load options');
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, [slug, config.url, config.method, config.response_path, config.label_field, config.value_field, config.depends_on, dependsOnValue]);

  useEffect(() => {
    fetchOptions();
  }, [fetchOptions]);

  // Clear value when depends_on changes
  useEffect(() => {
    if (config.depends_on && value) {
      onChange('');
    }
  }, [dependsOnValue]);

  return (
    <div>
      <select
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || loading}
        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary text-sm"
      >
        <option value="">
          {loading ? 'Loading...' : (config.placeholder || 'Select...')}
        </option>
        {options.map((opt, idx) => (
          <option key={`${opt.value}-${idx}`} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="mt-1 text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
