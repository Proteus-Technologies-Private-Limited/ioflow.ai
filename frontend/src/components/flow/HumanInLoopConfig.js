import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import WorkflowRoleUserSelector from './WorkflowRoleUserSelector';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const HumanInLoopConfig = ({ node, updateNodeData, availableVariables }) => {
  // Escalation dropdown data (lazy loaded)
  const [hitlRoles, setHitlRoles] = useState([]);
  const [tenantUsers, setTenantUsers] = useState([]);
  const escalationDataLoaded = useRef(false);

  const data = node.data || {};
  const taskType = data.taskType || 'review';
  const assignmentConfig = data.assignmentConfig || { type: 'user', users: [], roles: [] };
  const displayConfig = data.displayConfig || { format: 'form', fields: [] };
  const inputDataMapping = data.inputDataMapping || {};
  const timeoutMinutes = data.timeoutMinutes || 0;
  const escalationConfig = data.escalationConfig || {};
  const priority = data.priority || 'medium';

  // Lazy load roles/users only when escalation section needs them
  useEffect(() => {
    if (escalationConfig.on_timeout === 'escalate' && !escalationDataLoaded.current) {
      escalationDataLoaded.current = true;
      const token = localStorage.getItem('token') || localStorage.getItem('access_token');
      const headers = { Authorization: `Bearer ${token}` };
      Promise.all([
        axios.get(`${API_BASE_URL}/api/v1/hitl/roles`, { headers }),
        axios.get(`${API_BASE_URL}/api/v1/users/`, { headers }),
      ]).then(([rolesRes, usersRes]) => {
        setHitlRoles(rolesRes.data || []);
        setTenantUsers(usersRes.data || []);
      }).catch(err => console.error('Failed to load escalation data:', err));
    }
  }, [escalationConfig.on_timeout]);

  const update = (key, value) => {
    updateNodeData(node.id, { [key]: value });
  };

  // Build variable options from available context
  const getVariableOptions = () => {
    if (!availableVariables) return [];
    const options = [];
    if (Array.isArray(availableVariables)) {
      availableVariables.forEach(v => {
        if (typeof v === 'string') {
          options.push(v);
        } else if (v.path) {
          options.push(v.path);
        }
      });
    }
    return options;
  };

  const addInputMapping = () => {
    const fieldName = `field_${Object.keys(inputDataMapping).length + 1}`;
    update('inputDataMapping', { ...inputDataMapping, [fieldName]: '' });
  };

  const updateMapping = (oldKey, newKey, value) => {
    const updated = { ...inputDataMapping };
    if (oldKey !== newKey) {
      delete updated[oldKey];
    }
    updated[newKey] = value;
    update('inputDataMapping', updated);
  };

  const removeMapping = (key) => {
    const updated = { ...inputDataMapping };
    delete updated[key];
    update('inputDataMapping', updated);
  };

  return (
    <div className="space-y-5">
      <h3 className="text-sm font-medium text-gray-900">Human Review Configuration</h3>

      {/* Task Type */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Task Type</label>
        <select
          value={taskType}
          onChange={(e) => update('taskType', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-purple-500 text-sm"
        >
          <option value="review">Review (view only)</option>
          <option value="edit">Edit (modify data)</option>
          <option value="approve_reject">Approve / Reject</option>
        </select>
      </div>

      {/* Title */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Task Title</label>
        <input
          type="text"
          value={data.title || ''}
          onChange={(e) => update('title', e.target.value)}
          placeholder="e.g., Review extracted data"
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
        />
        <p className="mt-1 text-xs text-gray-500">Supports variables: {'{{node_outputs.node_id.field}}'}</p>
      </div>

      {/* Description */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Instructions (optional)</label>
        <textarea
          value={data.description || ''}
          onChange={(e) => update('description', e.target.value)}
          placeholder="Instructions for the reviewer..."
          rows={2}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
        />
      </div>

      {/* Priority */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
        <select
          value={priority}
          onChange={(e) => update('priority', e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
        >
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {/* Assignment */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">Assignment</label>
        <WorkflowRoleUserSelector
          assignmentConfig={assignmentConfig}
          onAssignmentChange={(newConfig) => update('assignmentConfig', newConfig)}
        />
      </div>

      {/* Input Data Mapping */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Data to Present
        </label>
        <p className="text-xs text-gray-500 mb-2">
          Map fields from flow context to display to the reviewer. Leave empty to include all previous node outputs.
        </p>
        {Object.entries(inputDataMapping).map(([key, value]) => (
          <div key={key} className="flex gap-2 mb-2">
            <input
              type="text"
              value={key}
              onChange={(e) => updateMapping(key, e.target.value, value)}
              placeholder="Field name"
              className="flex-1 px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
            <input
              type="text"
              value={value}
              onChange={(e) => updateMapping(key, key, e.target.value)}
              placeholder="{{node_outputs.node_id.field}}"
              className="flex-1 px-2 py-1.5 border border-gray-300 rounded text-sm"
            />
            <button
              onClick={() => removeMapping(key)}
              className="px-2 text-red-500 hover:text-red-700 text-sm"
            >
              x
            </button>
          </div>
        ))}
        <button
          onClick={addInputMapping}
          className="text-xs text-purple-600 hover:text-purple-800 font-medium"
        >
          + Add field mapping
        </button>
      </div>

      {/* Display Format */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Display Format</label>
        <select
          value={displayConfig.format || 'form'}
          onChange={(e) => update('displayConfig', { ...displayConfig, format: e.target.value })}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
        >
          <option value="form">Form (editable fields)</option>
          <option value="table">Table</option>
          <option value="json">JSON viewer</option>
          <option value="text">Plain text</option>
        </select>
      </div>

      {/* Timeout & Escalation */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Timeout (minutes)
        </label>
        <input
          type="number"
          value={timeoutMinutes}
          onChange={(e) => update('timeoutMinutes', parseInt(e.target.value) || 0)}
          min="0"
          placeholder="0 = no timeout"
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
        />
        <p className="mt-1 text-xs text-gray-500">Set to 0 for no timeout</p>
      </div>

      {timeoutMinutes > 0 && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">On Timeout</label>
          <select
            value={escalationConfig.on_timeout || 'fail'}
            onChange={(e) => update('escalationConfig', { ...escalationConfig, on_timeout: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-purple-500 text-sm"
          >
            <option value="fail">Fail execution</option>
            <option value="auto_approve">Auto-approve</option>
            <option value="auto_reject">Auto-reject</option>
            <option value="escalate">Escalate to another user/role</option>
          </select>

          {escalationConfig.on_timeout === 'escalate' && (
            <div className="mt-3 space-y-2">
              <label className="block text-xs font-medium text-gray-600">Escalate To</label>
              <select
                value={escalationConfig.escalate_to?.type || 'user'}
                onChange={(e) => update('escalationConfig', {
                  ...escalationConfig,
                  escalate_to: { ...escalationConfig.escalate_to, type: e.target.value }
                })}
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
              >
                <option value="user">User</option>
                <option value="hitl_role">Workflow Role</option>
              </select>

              {escalationConfig.escalate_to?.type === 'user' ? (
                <select
                  value={escalationConfig.escalate_to?.id || ''}
                  onChange={(e) => update('escalationConfig', {
                    ...escalationConfig,
                    escalate_to: { ...escalationConfig.escalate_to, id: e.target.value }
                  })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                >
                  <option value="">Select user...</option>
                  {tenantUsers.map(u => (
                    <option key={u.user_id} value={u.user_id}>{u.user_name || u.email}</option>
                  ))}
                </select>
              ) : (
                <select
                  value={escalationConfig.escalate_to?.id || ''}
                  onChange={(e) => update('escalationConfig', {
                    ...escalationConfig,
                    escalate_to: { ...escalationConfig.escalate_to, id: e.target.value }
                  })}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                >
                  <option value="">Select role...</option>
                  {hitlRoles.map(r => (
                    <option key={r.role_id} value={r.role_id}>{r.role_name}</option>
                  ))}
                </select>
              )}

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Max Escalations</label>
                <input
                  type="number"
                  value={escalationConfig.max_escalations || 3}
                  onChange={(e) => update('escalationConfig', {
                    ...escalationConfig,
                    max_escalations: parseInt(e.target.value) || 3
                  })}
                  min="1"
                  max="10"
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Escalation Timeout (minutes)</label>
                <input
                  type="number"
                  value={escalationConfig.escalation_timeout_minutes || 30}
                  onChange={(e) => update('escalationConfig', {
                    ...escalationConfig,
                    escalation_timeout_minutes: parseInt(e.target.value) || 30
                  })}
                  min="1"
                  className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default HumanInLoopConfig;
