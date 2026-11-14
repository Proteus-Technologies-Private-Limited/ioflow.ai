import React, { useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline';

function CollapsibleSection({ title, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-gray-200 rounded-lg">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-t-lg"
      >
        {open ? (
          <ChevronDownIcon className="w-4 h-4" />
        ) : (
          <ChevronRightIcon className="w-4 h-4" />
        )}
        {title}
      </button>
      {open && <div className="px-3 pb-3 space-y-3">{children}</div>}
    </div>
  );
}

export default function TriggerFormConfig({ config, onChange, manualVariables = [] }) {
  const fieldOverrides = config.fieldOverrides || {};
  const validations = config.validations || {};
  const apiDropdowns = config.apiDropdowns || {};

  const updateFieldOverride = (varName, field, value) => {
    const updated = {
      ...fieldOverrides,
      [varName]: { ...(fieldOverrides[varName] || {}), [field]: value },
    };
    onChange({ ...config, fieldOverrides: updated });
  };

  const updateValidation = (varName, field, value) => {
    const updated = {
      ...validations,
      [varName]: { ...(validations[varName] || {}), [field]: value },
    };
    onChange({ ...config, validations: updated });
  };

  const updateApiDropdown = (varName, field, value) => {
    const updated = {
      ...apiDropdowns,
      [varName]: { ...(apiDropdowns[varName] || {}), [field]: value },
    };
    onChange({ ...config, apiDropdowns: updated });
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-gray-800 border-b pb-1">Trigger Form</h3>

      {/* Basic Settings */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
        <input
          type="text"
          value={config.title || ''}
          onChange={(e) => onChange({ ...config, title: e.target.value })}
          placeholder="Form title"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
        <textarea
          value={config.description || ''}
          onChange={(e) => onChange({ ...config, description: e.target.value })}
          placeholder="Form description"
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Submit Button Text</label>
        <input
          type="text"
          value={config.submitButtonText || ''}
          onChange={(e) => onChange({ ...config, submitButtonText: e.target.value })}
          placeholder="Submit"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        />
      </div>

      {/* Layout */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Layout</label>
        <select
          value={config.layout || 'single_column'}
          onChange={(e) => onChange({ ...config, layout: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-primary/50 focus:border-primary"
        >
          <option value="single_column">Single Column</option>
          <option value="two_column">Two Columns</option>
        </select>
      </div>

      {/* Toggles */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={config.showPrerequisites || false}
            onChange={(e) => onChange({ ...config, showPrerequisites: e.target.checked })}
            className="rounded border-gray-300 text-primary focus:ring-primary"
          />
          Show Prerequisites
        </label>
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
          <input
            type="checkbox"
            checked={config.showFollowups || false}
            onChange={(e) => onChange({ ...config, showFollowups: e.target.checked })}
            className="rounded border-gray-300 text-primary focus:ring-primary"
          />
          Show Follow-ups
        </label>
      </div>

      {/* Field Overrides */}
      {manualVariables.length > 0 && (
        <CollapsibleSection title={`Field Overrides (${manualVariables.length} fields)`}>
          {manualVariables.map((v) => {
            const varName = typeof v === 'string' ? v : v.name;
            const override = fieldOverrides[varName] || {};
            return (
              <div key={varName} className="border border-gray-100 rounded p-2 bg-gray-50">
                <p className="text-xs font-semibold text-gray-600 mb-2">{varName}</p>
                <div className="space-y-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Label</label>
                    <input
                      type="text"
                      value={override.label || ''}
                      onChange={(e) => updateFieldOverride(varName, 'label', e.target.value)}
                      placeholder={varName}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Placeholder</label>
                    <input
                      type="text"
                      value={override.placeholder || ''}
                      onChange={(e) => updateFieldOverride(varName, 'placeholder', e.target.value)}
                      placeholder="Placeholder text"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Help Text</label>
                    <input
                      type="text"
                      value={override.helpText || ''}
                      onChange={(e) => updateFieldOverride(varName, 'helpText', e.target.value)}
                      placeholder="Help text"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </CollapsibleSection>
      )}

      {/* Validations */}
      {manualVariables.length > 0 && (
        <CollapsibleSection title={`Validations (${manualVariables.length} fields)`}>
          {manualVariables.map((v) => {
            const varName = typeof v === 'string' ? v : v.name;
            const validation = validations[varName] || {};
            return (
              <div key={varName} className="border border-gray-100 rounded p-2 bg-gray-50">
                <p className="text-xs font-semibold text-gray-600 mb-2">{varName}</p>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-xs font-medium text-gray-600">
                    <input
                      type="checkbox"
                      checked={validation.required || false}
                      onChange={(e) => updateValidation(varName, 'required', e.target.checked)}
                      className="rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    Required
                  </label>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Pattern (regex)</label>
                    <input
                      type="text"
                      value={validation.pattern || ''}
                      onChange={(e) => updateValidation(varName, 'pattern', e.target.value)}
                      placeholder="e.g. ^[A-Z]{5}[0-9]{4}[A-Z]$"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Validation Message</label>
                    <input
                      type="text"
                      value={validation.message || ''}
                      onChange={(e) => updateValidation(varName, 'message', e.target.value)}
                      placeholder="Error message"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Min Length</label>
                      <input
                        type="number"
                        value={validation.minLength || ''}
                        onChange={(e) => updateValidation(varName, 'minLength', e.target.value ? parseInt(e.target.value) : '')}
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Max Length</label>
                      <input
                        type="number"
                        value={validation.maxLength || ''}
                        onChange={(e) => updateValidation(varName, 'maxLength', e.target.value ? parseInt(e.target.value) : '')}
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Min Value</label>
                      <input
                        type="number"
                        value={validation.min || ''}
                        onChange={(e) => updateValidation(varName, 'min', e.target.value ? parseFloat(e.target.value) : '')}
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Max Value</label>
                      <input
                        type="number"
                        value={validation.max || ''}
                        onChange={(e) => updateValidation(varName, 'max', e.target.value ? parseFloat(e.target.value) : '')}
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                      />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </CollapsibleSection>
      )}

      {/* API Dropdowns */}
      {manualVariables.length > 0 && (
        <CollapsibleSection title={`API Dropdowns (${manualVariables.length} fields)`}>
          {manualVariables.map((v) => {
            const varName = typeof v === 'string' ? v : v.name;
            const dropdown = apiDropdowns[varName] || {};
            return (
              <div key={varName} className="border border-gray-100 rounded p-2 bg-gray-50">
                <p className="text-xs font-semibold text-gray-600 mb-2">{varName}</p>
                <div className="space-y-2">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">API URL</label>
                    <input
                      type="text"
                      value={dropdown.url || ''}
                      onChange={(e) => updateApiDropdown(varName, 'url', e.target.value)}
                      placeholder="https://api.example.com/options"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Method</label>
                    <select
                      value={dropdown.method || 'GET'}
                      onChange={(e) => updateApiDropdown(varName, 'method', e.target.value)}
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Response Path</label>
                    <input
                      type="text"
                      value={dropdown.response_path || ''}
                      onChange={(e) => updateApiDropdown(varName, 'response_path', e.target.value)}
                      placeholder="e.g. data.items"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Label Field</label>
                      <input
                        type="text"
                        value={dropdown.label_field || ''}
                        onChange={(e) => updateApiDropdown(varName, 'label_field', e.target.value)}
                        placeholder="name"
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-600 mb-1">Value Field</label>
                      <input
                        type="text"
                        value={dropdown.value_field || ''}
                        onChange={(e) => updateApiDropdown(varName, 'value_field', e.target.value)}
                        placeholder="id"
                        className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Depends On</label>
                    <input
                      type="text"
                      value={dropdown.depends_on || ''}
                      onChange={(e) => updateApiDropdown(varName, 'depends_on', e.target.value)}
                      placeholder="Another field name"
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Placeholder</label>
                    <input
                      type="text"
                      value={dropdown.placeholder || ''}
                      onChange={(e) => updateApiDropdown(varName, 'placeholder', e.target.value)}
                      placeholder="Select an option..."
                      className="w-full px-2 py-1.5 border border-gray-300 rounded text-xs focus:ring-2 focus:ring-primary/50 focus:border-primary"
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </CollapsibleSection>
      )}

      {manualVariables.length === 0 && (
        <p className="text-xs text-gray-400 italic">
          No manual variables found. Field overrides, validations, and API dropdowns will appear once the flow has manual input variables.
        </p>
      )}
    </div>
  );
}
