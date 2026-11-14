/**
 * SchemaRenderer — Generic JSON Schema -> form component.
 *
 * Takes a JSON Schema with ui: hints, current form data, and onChange callback.
 * Renders appropriate widgets per property based on `ui:widget` hint.
 *
 * Supported ui: hints:
 *   ui:widget   — widget type: text-input, url-input, password-input, number-input,
 *                  select, multi-select, checkbox, toggle, textarea, code-editor,
 *                  json-editor, key-value-pairs, array-input, section
 *   ui:placeholder — placeholder text
 *   ui:help     — help text shown below field
 *   ui:showWhen — conditional visibility { field, value }
 *   ui:groups   — field grouping with collapsible sections
 *   ui:message  — informational message (no fields)
 */
import React, { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline';

// ─── Widget Components ───

function TextInput({ name, schema, value, onChange, required }) {
  return (
    <input
      type="text"
      value={value || ''}
      onChange={e => onChange(name, e.target.value)}
      placeholder={schema['ui:placeholder'] || ''}
      required={required}
      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
    />
  );
}

function UrlInput({ name, schema, value, onChange, required }) {
  return (
    <input
      type="url"
      value={value || ''}
      onChange={e => onChange(name, e.target.value)}
      placeholder={schema['ui:placeholder'] || 'https://'}
      required={required}
      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
    />
  );
}

function PasswordInput({ name, schema, value, onChange, required }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        type={show ? 'text' : 'password'}
        value={value || ''}
        onChange={e => onChange(name, e.target.value)}
        placeholder={schema['ui:placeholder'] || ''}
        required={required}
        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm pr-16"
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-500 hover:text-gray-700"
      >
        {show ? 'Hide' : 'Show'}
      </button>
    </div>
  );
}

function NumberInput({ name, schema, value, onChange, required }) {
  return (
    <input
      type="number"
      value={value ?? ''}
      onChange={e => onChange(name, e.target.value === '' ? null : Number(e.target.value))}
      placeholder={schema['ui:placeholder'] || ''}
      required={required}
      min={schema.minimum}
      max={schema.maximum}
      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
    />
  );
}

function SelectInput({ name, schema, value, onChange, required }) {
  const options = schema.enum || [];
  return (
    <select
      value={value || ''}
      onChange={e => onChange(name, e.target.value)}
      required={required}
      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
    >
      <option value="">Select...</option>
      {options.map(opt => (
        <option key={opt} value={opt}>{opt}</option>
      ))}
    </select>
  );
}

function TextareaInput({ name, schema, value, onChange, required }) {
  return (
    <textarea
      value={value || ''}
      onChange={e => onChange(name, e.target.value)}
      placeholder={schema['ui:placeholder'] || ''}
      required={required}
      rows={schema['ui:rows'] || 4}
      className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm font-mono"
    />
  );
}

function ToggleInput({ name, schema, value, onChange }) {
  return (
    <label className="flex items-center cursor-pointer">
      <div className="relative">
        <input
          type="checkbox"
          checked={!!value}
          onChange={e => onChange(name, e.target.checked)}
          className="sr-only"
        />
        <div className={`w-10 h-5 rounded-full transition-colors ${value ? 'bg-indigo-600' : 'bg-gray-300'}`} />
        <div className={`absolute left-0.5 top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${value ? 'translate-x-5' : ''}`} />
      </div>
      {schema.title && <span className="ml-2 text-sm text-gray-700">{schema.title}</span>}
    </label>
  );
}

function CheckboxInput({ name, schema, value, onChange }) {
  return (
    <label className="flex items-center">
      <input
        type="checkbox"
        checked={!!value}
        onChange={e => onChange(name, e.target.checked)}
        className="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
      />
      {schema.description && <span className="ml-2 text-sm text-gray-600">{schema.description}</span>}
    </label>
  );
}

function KeyValuePairs({ name, schema, value, onChange }) {
  const pairs = Object.entries(value || {});

  const updatePair = (index, key, val) => {
    const entries = [...pairs];
    entries[index] = [key, val];
    onChange(name, Object.fromEntries(entries));
  };

  const addPair = () => {
    onChange(name, { ...value, '': '' });
  };

  const removePair = (index) => {
    const entries = pairs.filter((_, i) => i !== index);
    onChange(name, Object.fromEntries(entries));
  };

  return (
    <div className="space-y-2">
      {pairs.map(([k, v], i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            type="text"
            value={k}
            onChange={e => updatePair(i, e.target.value, v)}
            placeholder="Key"
            className="flex-1 px-2 py-1.5 border border-gray-300 rounded-md text-sm"
          />
          <input
            type="text"
            value={v}
            onChange={e => updatePair(i, k, e.target.value)}
            placeholder="Value"
            className="flex-1 px-2 py-1.5 border border-gray-300 rounded-md text-sm"
          />
          <button type="button" onClick={() => removePair(i)}
                  className="text-red-500 hover:text-red-700">
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button type="button" onClick={addPair}
              className="flex items-center text-sm text-indigo-600 hover:text-indigo-800">
        <PlusIcon className="w-4 h-4 mr-1" /> Add Pair
      </button>
    </div>
  );
}

function ArrayInput({ name, schema, value, onChange }) {
  const items = Array.isArray(value) ? value : [];

  const updateItem = (index, val) => {
    const newItems = [...items];
    newItems[index] = val;
    onChange(name, newItems);
  };

  const addItem = () => {
    onChange(name, [...items, '']);
  };

  const removeItem = (index) => {
    onChange(name, items.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div key={i} className="flex gap-2 items-center">
          <input
            type="text"
            value={item || ''}
            onChange={e => updateItem(i, e.target.value)}
            placeholder={schema.items?.['ui:placeholder'] || `Item ${i + 1}`}
            className="flex-1 px-2 py-1.5 border border-gray-300 rounded-md text-sm"
          />
          <button type="button" onClick={() => removeItem(i)}
                  className="text-red-500 hover:text-red-700">
            <TrashIcon className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button type="button" onClick={addItem}
              className="flex items-center text-sm text-indigo-600 hover:text-indigo-800">
        <PlusIcon className="w-4 h-4 mr-1" /> Add Item
      </button>
    </div>
  );
}

function JsonEditorInput({ name, schema, value, onChange }) {
  const [text, setText] = useState(() =>
    typeof value === 'string' ? value : JSON.stringify(value || {}, null, 2)
  );
  const [error, setError] = useState(null);

  const handleChange = (val) => {
    setText(val);
    try {
      const parsed = JSON.parse(val);
      onChange(name, parsed);
      setError(null);
    } catch {
      setError('Invalid JSON');
    }
  };

  return (
    <div>
      <textarea
        value={text}
        onChange={e => handleChange(e.target.value)}
        rows={schema['ui:rows'] || 6}
        className={`w-full px-3 py-2 border rounded-md shadow-sm font-mono text-sm ${
          error ? 'border-red-300' : 'border-gray-300'
        } focus:outline-none focus:ring-indigo-500 focus:border-indigo-500`}
      />
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
}

// ─── Widget Registry ───

const WIDGETS = {
  'text-input': TextInput,
  'url-input': UrlInput,
  'password-input': PasswordInput,
  'number-input': NumberInput,
  'select': SelectInput,
  'textarea': TextareaInput,
  'code-editor': TextareaInput,  // Basic fallback; can be enhanced later
  'json-editor': JsonEditorInput,
  'key-value-pairs': KeyValuePairs,
  'array-input': ArrayInput,
  'toggle': ToggleInput,
  'checkbox': CheckboxInput,
};

function getWidget(schema) {
  const widgetHint = schema['ui:widget'];
  if (widgetHint && WIDGETS[widgetHint]) return WIDGETS[widgetHint];

  // Infer from type
  if (schema.enum) return SelectInput;
  if (schema.type === 'boolean') return ToggleInput;
  if (schema.type === 'integer' || schema.type === 'number') return NumberInput;
  if (schema.type === 'array') return ArrayInput;
  if (schema.type === 'object' && !schema.properties) return KeyValuePairs;

  return TextInput;
}

// ─── Field Wrapper ───

function SchemaField({ name, schema, value, onChange, required, allValues }) {
  // Conditional visibility
  const showWhen = schema['ui:showWhen'];
  if (showWhen) {
    const depValue = allValues?.[showWhen.field];
    const expected = showWhen.value;
    const match = Array.isArray(expected)
      ? expected.includes(depValue)
      : depValue === expected;
    if (!match) return null;
  }

  // Nested object with properties — render recursively
  if (schema.type === 'object' && schema.properties && schema['ui:widget'] !== 'key-value-pairs' && schema['ui:widget'] !== 'json-editor') {
    return (
      <div className="border border-gray-200 rounded-md p-3 space-y-3">
        {schema.title && <h4 className="text-sm font-medium text-gray-700">{schema.title}</h4>}
        <SchemaRenderer
          schema={schema}
          value={value || {}}
          onChange={(newVal) => onChange(name, newVal)}
        />
      </div>
    );
  }

  const Widget = getWidget(schema);

  return (
    <div>
      {schema.title && schema['ui:widget'] !== 'toggle' && schema['ui:widget'] !== 'checkbox' && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {schema.title}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      <Widget
        name={name}
        schema={schema}
        value={value}
        onChange={onChange}
        required={required}
      />
      {schema['ui:help'] && (
        <p className="text-xs text-gray-500 mt-1">{schema['ui:help']}</p>
      )}
    </div>
  );
}

// ─── Group Wrapper ───

function SchemaGroup({ group, schema, value, onChange }) {
  const [collapsed, setCollapsed] = useState(group.collapsed ?? false);
  const requiredFields = schema.required || [];

  return (
    <div className="border border-gray-200 rounded-md">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="w-full px-3 py-2 flex items-center justify-between text-sm font-medium text-gray-700 hover:bg-gray-50"
      >
        {group.name}
        {collapsed ? <ChevronRightIcon className="w-4 h-4" /> : <ChevronDownIcon className="w-4 h-4" />}
      </button>
      {!collapsed && (
        <div className="px-3 pb-3 space-y-3">
          {group.fields.map(fieldName => {
            const fieldSchema = schema.properties?.[fieldName];
            if (!fieldSchema) return null;
            return (
              <SchemaField
                key={fieldName}
                name={fieldName}
                schema={fieldSchema}
                value={value?.[fieldName]}
                onChange={(name, val) => onChange({ ...value, [name]: val })}
                required={requiredFields.includes(fieldName)}
                allValues={value}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Main SchemaRenderer ───

/**
 * Renders a form from a JSON Schema with ui: hints.
 *
 * @param {Object} props
 * @param {Object} props.schema - JSON Schema with ui: extensions
 * @param {Object} props.value - Current form data
 * @param {Function} props.onChange - Called with updated form data
 */
export default function SchemaRenderer({ schema, value, onChange }) {
  if (!schema || !schema.properties) {
    // Check for ui:message
    if (schema?.['ui:message']) {
      return <p className="text-sm text-gray-500 italic">{schema['ui:message']}</p>;
    }
    return null;
  }

  const requiredFields = schema.required || [];
  const groups = schema['ui:groups'];

  const handleFieldChange = (name, val) => {
    onChange({ ...value, [name]: val });
  };

  // If groups are defined, render in groups
  if (groups && groups.length > 0) {
    // Collect fields that belong to groups
    const groupedFields = new Set();
    groups.forEach(g => g.fields?.forEach(f => groupedFields.add(f)));

    // Ungrouped fields render first
    const ungroupedFields = Object.keys(schema.properties).filter(f => !groupedFields.has(f));

    return (
      <div className="space-y-4">
        {ungroupedFields.length > 0 && (
          <div className="space-y-3">
            {ungroupedFields.map(fieldName => (
              <SchemaField
                key={fieldName}
                name={fieldName}
                schema={schema.properties[fieldName]}
                value={value?.[fieldName]}
                onChange={handleFieldChange}
                required={requiredFields.includes(fieldName)}
                allValues={value}
              />
            ))}
          </div>
        )}
        {groups.map((group, i) => (
          <SchemaGroup
            key={i}
            group={group}
            schema={schema}
            value={value}
            onChange={onChange}
          />
        ))}
      </div>
    );
  }

  // No groups — render all fields in order
  return (
    <div className="space-y-3">
      {Object.entries(schema.properties).map(([fieldName, fieldSchema]) => (
        <SchemaField
          key={fieldName}
          name={fieldName}
          schema={fieldSchema}
          value={value?.[fieldName]}
          onChange={handleFieldChange}
          required={requiredFields.includes(fieldName)}
          allValues={value}
        />
      ))}
    </div>
  );
}
