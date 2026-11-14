import React, { useEffect, useState } from 'react';
import { ChevronDownIcon, ChevronRightIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

// Mirrors backend/services/node_error_handling.py
export const ERROR_HANDLE_ID = 'error';

export const ON_ERROR_OPTIONS = [
  {
    value: 'stop',
    label: 'Stop the flow',
    help: 'The execution fails at this node (default).',
  },
  {
    value: 'continue',
    label: 'Continue',
    help: 'The node outputs { success: false, error } and the next nodes run as usual.',
  },
  {
    value: 'error_branch',
    label: 'Route to error branch',
    help: 'Only nodes connected to the red "on error" handle run; normal connections are skipped.',
  },
];

export const ERROR_TYPE_OPTIONS = [
  { value: 'connection', label: 'Connection', transient: true },
  { value: 'timeout', label: 'Timeout', transient: true },
  { value: 'rate_limit', label: 'Rate limit (429)', transient: true },
  { value: 'server', label: 'Server error (5xx)', transient: true },
  { value: 'auth', label: 'Auth (401/403)' },
  { value: 'not_found', label: 'Not found (404)' },
  { value: 'validation', label: 'Validation (400/422)' },
  { value: 'client', label: 'Other 4xx' },
  { value: 'unknown', label: 'Unknown' },
];

const DEFAULT_RETRY_ON = ERROR_TYPE_OPTIONS.filter(t => t.transient).map(t => t.value);

// Node types without error handling / without retry (see backend policy)
const NO_POLICY_TYPES = ['trigger'];
const NON_RETRYABLE_TYPES = ['trigger', 'loop', 'parallel', 'human_in_loop', 'wait_for_event'];

const DEFAULT_RETRY = {
  enabled: false,
  maxAttempts: 3,
  initialDelayMs: 1000,
  backoff: 'exponential',
  maxDelayMs: 30000,
  jitter: true,
  retryOn: DEFAULT_RETRY_ON,
};

export const isErrorHandlingActive = (errorHandling) =>
  !!errorHandling && (
    (errorHandling.onError && errorHandling.onError !== 'stop') ||
    !!errorHandling.retry?.enabled
  );

const clampInt = (value, min, max, fallback) => {
  const n = parseInt(value, 10);
  if (Number.isNaN(n)) return fallback;
  return Math.min(max, Math.max(min, n));
};

const NodeErrorHandlingConfig = ({ node, updateNodeData, onErrorBranchDisabled }) => {
  const nodeType = node?.type;
  const config = node?.data?.errorHandling || {};
  const onError = config.onError || 'stop';
  const retry = { ...DEFAULT_RETRY, ...(config.retry || {}) };
  const retryAllowed = !NON_RETRYABLE_TYPES.includes(nodeType);
  const active = isErrorHandlingActive(config);

  const [expanded, setExpanded] = useState(active);
  const [continueOutputText, setContinueOutputText] = useState('');
  const [continueOutputError, setContinueOutputError] = useState(null);

  // Keep the JSON editor in sync when another node is selected
  useEffect(() => {
    const value = node?.data?.errorHandling?.continueOutput;
    setContinueOutputText(value === undefined || value === null ? '' : JSON.stringify(value, null, 2));
    setContinueOutputError(null);
    setExpanded(isErrorHandlingActive(node?.data?.errorHandling));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node?.id]);

  if (!node || NO_POLICY_TYPES.includes(nodeType)) {
    return null;
  }

  const save = (changes) => {
    const next = { ...config, ...changes };
    // Drop the block entirely when it is back to the defaults so flows stay clean
    const isDefault = (next.onError || 'stop') === 'stop' && !next.retry?.enabled
      && !next.failOnUnsuccessfulResponse && next.continueOutput === undefined;
    updateNodeData(node.id, { errorHandling: isDefault ? null : next });
  };

  const saveRetry = (changes) => save({ retry: { ...retry, ...changes } });

  const handleOnErrorChange = (value) => {
    if (onError === 'error_branch' && value !== 'error_branch' && onErrorBranchDisabled) {
      onErrorBranchDisabled(node.id);
    }
    const changes = { onError: value };
    if (value !== 'continue') {
      changes.continueOutput = undefined;
      setContinueOutputText('');
      setContinueOutputError(null);
    }
    save(changes);
  };

  const toggleRetryType = (type) => {
    const current = retry.retryOn || [];
    const next = current.includes(type) ? current.filter(t => t !== type) : [...current.filter(t => t !== 'any'), type];
    saveRetry({ retryOn: next.length ? next : DEFAULT_RETRY_ON });
  };

  const commitContinueOutput = () => {
    const text = continueOutputText.trim();
    if (!text) {
      setContinueOutputError(null);
      save({ continueOutput: undefined });
      return;
    }
    try {
      save({ continueOutput: JSON.parse(text) });
      setContinueOutputError(null);
    } catch (e) {
      setContinueOutputError(`Invalid JSON: ${e.message}`);
    }
  };

  const retryAny = (retry.retryOn || []).includes('any');
  const summary = [
    onError !== 'stop' && ON_ERROR_OPTIONS.find(o => o.value === onError)?.label,
    retry.enabled && retryAllowed && `retry ×${retry.maxAttempts}`,
  ].filter(Boolean).join(' · ');

  return (
    <div className="border border-gray-200 rounded-md">
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-gray-900">
          <ExclamationTriangleIcon className={`w-4 h-4 ${active ? 'text-red-500' : 'text-gray-400'}`} />
          Error Handling
        </span>
        <span className="flex items-center gap-2">
          {summary && <span className="text-xs text-red-600 truncate max-w-[180px]">{summary}</span>}
          {expanded ? <ChevronDownIcon className="w-4 h-4 text-gray-500" /> : <ChevronRightIcon className="w-4 h-4 text-gray-500" />}
        </span>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-4 border-t border-gray-100 pt-3">
          {/* On error */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">On Error</label>
            <div className="space-y-1.5">
              {ON_ERROR_OPTIONS.map(option => (
                <label key={option.value} className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="radio"
                    name={`on-error-${node.id}`}
                    value={option.value}
                    checked={onError === option.value}
                    onChange={() => handleOnErrorChange(option.value)}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="text-sm text-gray-800">{option.label}</span>
                    <span className="block text-xs text-gray-500">{option.help}</span>
                  </span>
                </label>
              ))}
            </div>
            {nodeType === 'condition' && onError === 'continue' && (
              <p className="mt-1 text-xs text-amber-700">A condition that fails and continues takes its false branch.</p>
            )}
            {nodeType === 'loop' && onError === 'continue' && (
              <p className="mt-1 text-xs text-amber-700">A loop that fails and continues runs its Continue output.</p>
            )}
          </div>

          {/* Continue output */}
          {onError === 'continue' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Fallback output <span className="font-normal text-gray-400">(optional JSON)</span>
              </label>
              <textarea
                value={continueOutputText}
                onChange={(e) => setContinueOutputText(e.target.value)}
                onBlur={commitContinueOutput}
                rows={3}
                placeholder='{"items": []}'
                className={`w-full px-2 py-1.5 border rounded-md font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary ${continueOutputError ? 'border-red-400' : 'border-gray-300'}`}
              />
              {continueOutputError
                ? <p className="mt-1 text-xs text-red-600">{continueOutputError}</p>
                : <p className="mt-1 text-xs text-gray-500">Merged into the node's output when it fails, so later nodes find the fields they expect.</p>}
            </div>
          )}

          {/* Soft failures */}
          {nodeType === 'action' && (
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!!config.failOnUnsuccessfulResponse}
                onChange={(e) => save({ failOnUnsuccessfulResponse: e.target.checked || undefined })}
                className="mt-0.5"
              />
              <span>
                <span className="text-sm text-gray-800">Treat unsuccessful responses as errors</span>
                <span className="block text-xs text-gray-500">
                  A response with <code>success: false</code> (e.g. a status outside the service's success codes) counts as a failure.
                </span>
              </span>
            </label>
          )}

          {/* Retry */}
          {retryAllowed ? (
            <div className="space-y-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={!!retry.enabled}
                  onChange={(e) => saveRetry({ enabled: e.target.checked })}
                />
                <span className="text-sm font-medium text-gray-700">Retry on failure</span>
              </label>

              {retry.enabled && (
                <div className="pl-6 space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-gray-600 mb-0.5">Max attempts</label>
                      <input
                        type="number" min={1} max={10}
                        value={retry.maxAttempts}
                        onChange={(e) => saveRetry({ maxAttempts: clampInt(e.target.value, 1, 10, 3) })}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-0.5">Backoff</label>
                      <select
                        value={retry.backoff}
                        onChange={(e) => saveRetry({ backoff: e.target.value })}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      >
                        <option value="exponential">Exponential</option>
                        <option value="fixed">Fixed</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-0.5">Initial delay (ms)</label>
                      <input
                        type="number" min={0} max={300000} step={500}
                        value={retry.initialDelayMs}
                        onChange={(e) => saveRetry({ initialDelayMs: clampInt(e.target.value, 0, 300000, 1000) })}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-0.5">Max delay (ms)</label>
                      <input
                        type="number" min={0} max={300000} step={1000}
                        value={retry.maxDelayMs}
                        disabled={retry.backoff === 'fixed'}
                        onChange={(e) => saveRetry({ maxDelayMs: clampInt(e.target.value, 0, 300000, 30000) })}
                        className="w-full px-2 py-1 border border-gray-300 rounded text-sm disabled:bg-gray-100"
                      />
                    </div>
                  </div>
                  <p className="text-xs text-gray-500">
                    Max attempts includes the first try.
                  </p>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs text-gray-600">Retry on</span>
                      <label className="flex items-center gap-1 text-xs text-gray-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={retryAny}
                          onChange={(e) => saveRetry({ retryOn: e.target.checked ? ['any'] : DEFAULT_RETRY_ON })}
                        />
                        Any error
                      </label>
                    </div>
                    {!retryAny && (
                      <div className="grid grid-cols-2 gap-x-2 gap-y-1">
                        {ERROR_TYPE_OPTIONS.map(type => (
                          <label key={type.value} className="flex items-center gap-1.5 text-xs text-gray-700 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={(retry.retryOn || []).includes(type.value)}
                              onChange={() => toggleRetryType(type.value)}
                            />
                            {type.label}
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-gray-500">Retry isn't available for this node type, because re-running it would repeat the nodes it controls.</p>
          )}

          {/* Variables help */}
          {onError !== 'stop' && (
            <div className="text-xs text-gray-600 bg-red-50 border border-red-100 rounded p-2 space-y-1">
              <div className="font-medium text-red-700">Available after a failure</div>
              <div><code>{`{{${node.id}.error.message}}`}</code> · <code>{`{{${node.id}.error.type}}`}</code></div>
              <div><code>{`{{${node.id}.error.status_code}}`}</code> · <code>{`{{${node.id}.error.attempts}}`}</code></div>
              <div><code>{'{{error.message}}'}</code> refers to the most recent handled error; transforms can read <code>error</code> directly.</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default NodeErrorHandlingConfig;
