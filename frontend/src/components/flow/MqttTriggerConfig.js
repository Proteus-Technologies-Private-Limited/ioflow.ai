import React, { useState, useEffect } from 'react';
import { SignalIcon, InformationCircleIcon, ChevronDownIcon, ChevronRightIcon } from '@heroicons/react/24/outline';

// Shared "Performance & Delivery" fine-tuning section (batching, rate limit,
// dedup, concurrency). Rendered for BOTH attachment models: the flat 'mqtt'
// trigger below, and event triggers bound to an MQTT application event
// (FlowDesigner renders it directly in that case). Both write the same
// trigger_config keys, so backend resolution is shared.
export const MqttPerformanceSection = ({ value = {}, onChange, disabled = false }) => {
  const [expanded, setExpanded] = useState(false);

  const config = {
    mqtt_batch_size: value.mqtt_batch_size ?? 1,
    mqtt_batch_window_seconds: value.mqtt_batch_window_seconds ?? 0,
    mqtt_max_rate: value.mqtt_max_rate ?? 0,
    mqtt_rate_overflow: value.mqtt_rate_overflow || 'fold',
    mqtt_max_concurrent: value.mqtt_max_concurrent ?? 0,
    mqtt_dedup: value.mqtt_dedup || 'off',
    mqtt_dedup_key: value.mqtt_dedup_key || '',
    mqtt_dedup_window_seconds: value.mqtt_dedup_window_seconds ?? 300,
  };

  const handleChange = (field, newValue) => {
    onChange({ ...config, [field]: newValue });
  };

  const numberOrDefault = (raw, fallback, { float = false } = {}) => {
    const parsed = float ? parseFloat(raw) : parseInt(raw, 10);
    return Number.isNaN(parsed) ? fallback : parsed;
  };

  const isTuned = config.mqtt_batch_size > 1 || config.mqtt_max_rate > 0 ||
    config.mqtt_dedup !== 'off' || config.mqtt_max_concurrent > 0;

  return (
    <div className="border border-gray-200 rounded-lg">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <span className="text-sm font-medium text-gray-700">
          Performance &amp; Delivery
          {isTuned && (
            <span className="ml-2 text-xs font-normal text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
              tuned
            </span>
          )}
        </span>
        {expanded
          ? <ChevronDownIcon className="w-4 h-4 text-gray-400" />
          : <ChevronRightIcon className="w-4 h-4 text-gray-400" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-gray-100 pt-4">
          <p className="text-xs text-gray-500">
            Fine-tune how high-frequency messages turn into flow executions. Defaults
            (no batching, no limits) trigger one execution per message.
          </p>

          {/* Batching */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Batch Size
              </label>
              <input
                type="number"
                min="1"
                max="10000"
                value={config.mqtt_batch_size}
                onChange={(e) => handleChange('mqtt_batch_size', numberOrDefault(e.target.value, 1))}
                disabled={disabled}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">
                Messages per execution. 1 = no batching
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Batch Window (sec)
              </label>
              <input
                type="number"
                min="0"
                max="3600"
                step="0.1"
                value={config.mqtt_batch_window_seconds}
                onChange={(e) => handleChange('mqtt_batch_window_seconds', numberOrDefault(e.target.value, 0, { float: true }))}
                disabled={disabled}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">
                Flush a partial batch after this window. 0 = size-only
              </p>
            </div>
          </div>
          {config.mqtt_batch_size > 1 && (
            <p className="text-xs text-blue-700 bg-blue-50 rounded px-2 py-1">
              Batched executions receive <code className="font-mono">input.messages</code> (array)
              and <code className="font-mono">input.message_count</code>;
              <code className="font-mono"> input.payload</code> keeps pointing at the first message.
            </p>
          )}

          {/* Rate limiting */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Rate (executions/sec)
              </label>
              <input
                type="number"
                min="0"
                step="0.1"
                value={config.mqtt_max_rate}
                onChange={(e) => handleChange('mqtt_max_rate', numberOrDefault(e.target.value, 0, { float: true }))}
                disabled={disabled}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">
                0 = unlimited
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                On Rate Overflow
              </label>
              <select
                value={config.mqtt_rate_overflow}
                onChange={(e) => handleChange('mqtt_rate_overflow', e.target.value)}
                disabled={disabled}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value="fold">Fold into next batch</option>
                <option value="drop">Drop excess messages</option>
              </select>
            </div>
          </div>

          {/* Concurrency */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Concurrent Executions
            </label>
            <input
              type="number"
              min="0"
              value={config.mqtt_max_concurrent}
              onChange={(e) => handleChange('mqtt_max_concurrent', numberOrDefault(e.target.value, 0))}
              disabled={disabled}
              className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
            />
            <p className="mt-1 text-xs text-gray-500">
              Per-flow cap so this flow can't starve others. 0 = bounded only by the
              server's global worker pool (never exceeds it)
            </p>
          </div>

          {/* Deduplication */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Deduplication
              </label>
              <select
                value={config.mqtt_dedup}
                onChange={(e) => handleChange('mqtt_dedup', e.target.value)}
                disabled={disabled}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              >
                <option value="off">Off</option>
                <option value="payload">By topic + payload</option>
                <option value="key">By custom key</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Dedup Window (sec)
              </label>
              <input
                type="number"
                min="1"
                max="86400"
                value={config.mqtt_dedup_window_seconds}
                onChange={(e) => handleChange('mqtt_dedup_window_seconds', numberOrDefault(e.target.value, 300))}
                disabled={disabled || config.mqtt_dedup === 'off'}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
              />
              <p className="mt-1 text-xs text-gray-500">
                Duplicates within this window are skipped
              </p>
            </div>
          </div>
          {config.mqtt_dedup === 'key' && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Dedup Key Template <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={config.mqtt_dedup_key}
                onChange={(e) => handleChange('mqtt_dedup_key', e.target.value)}
                disabled={disabled}
                placeholder={'{{payload.device_id}}:{{payload.seq}}'}
                className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono"
              />
              <p className="mt-1 text-xs text-gray-500">
                What makes your messages unique — e.g. <code className="font-mono">{'{{payload.device_id}}:{{payload.seq}}'}</code>.
                Without a template, dedup stays off.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const MqttTriggerConfig = ({ value, onChange, disabled = false }) => {
  const [config, setConfig] = useState({
    mqtt_host: '',
    mqtt_port: 1883,
    mqtt_tls: false,
    mqtt_username: '',
    mqtt_password: '',
    mqtt_client_id: '',
    mqtt_topic_filter: '',
    mqtt_qos: 1,
    mqtt_payload_format: 'json',
    mqtt_batch_size: 1,
    mqtt_batch_window_seconds: 0,
    mqtt_max_rate: 0,
    mqtt_rate_overflow: 'fold',
    mqtt_max_concurrent: 0,
    mqtt_dedup: 'off',
    mqtt_dedup_key: '',
    mqtt_dedup_window_seconds: 300,
    ...value
  });

  useEffect(() => {
    if (value) {
      setConfig({
        mqtt_host: value.mqtt_host || '',
        mqtt_port: value.mqtt_port || 1883,
        mqtt_tls: value.mqtt_tls || false,
        mqtt_username: value.mqtt_username || '',
        mqtt_password: value.mqtt_password || '',
        mqtt_client_id: value.mqtt_client_id || '',
        mqtt_topic_filter: value.mqtt_topic_filter || '',
        mqtt_qos: value.mqtt_qos !== undefined ? value.mqtt_qos : 1,
        mqtt_payload_format: value.mqtt_payload_format || 'json',
        mqtt_batch_size: value.mqtt_batch_size ?? 1,
        mqtt_batch_window_seconds: value.mqtt_batch_window_seconds ?? 0,
        mqtt_max_rate: value.mqtt_max_rate ?? 0,
        mqtt_rate_overflow: value.mqtt_rate_overflow || 'fold',
        mqtt_max_concurrent: value.mqtt_max_concurrent ?? 0,
        mqtt_dedup: value.mqtt_dedup || 'off',
        mqtt_dedup_key: value.mqtt_dedup_key || '',
        mqtt_dedup_window_seconds: value.mqtt_dedup_window_seconds ?? 300,
      });
    }
  }, [value]);

  const handleChange = (field, newValue) => {
    const updatedConfig = { ...config, [field]: newValue };
    setConfig(updatedConfig);
    onChange(updatedConfig);
  };

  return (
    <div className="space-y-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <InformationCircleIcon className="w-5 h-5 text-blue-600 mt-0.5 mr-2 flex-shrink-0" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">MQTT Trigger</p>
            <p>Subscribe to an MQTT topic. The flow will be triggered every time a message matching your topic filter is published to the broker.</p>
          </div>
        </div>
      </div>

      {/* Broker Host */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Broker Host <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <SignalIcon className="h-5 w-5 text-gray-400" />
          </div>
          <input
            type="text"
            value={config.mqtt_host}
            onChange={(e) => handleChange('mqtt_host', e.target.value)}
            disabled={disabled}
            placeholder="broker.example.com or IP address"
            className="pl-10 block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          />
        </div>
        <p className="mt-1 text-xs text-gray-500">
          Hostname or IP address of the MQTT broker
        </p>
      </div>

      {/* Port + TLS */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Port
          </label>
          <input
            type="number"
            min="1"
            max="65535"
            value={config.mqtt_port}
            onChange={(e) => handleChange('mqtt_port', parseInt(e.target.value) || 1883)}
            disabled={disabled}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          />
          <p className="mt-1 text-xs text-gray-500">
            Default: 1883 (8883 for TLS)
          </p>
        </div>
        <div className="flex items-start pt-7">
          <label className="flex items-center">
            <input
              type="checkbox"
              checked={config.mqtt_tls}
              onChange={(e) => handleChange('mqtt_tls', e.target.checked)}
              disabled={disabled}
              className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
            <span className="ml-2 text-sm text-gray-700">Use TLS</span>
          </label>
        </div>
      </div>

      {/* Credentials */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Username
          </label>
          <input
            type="text"
            value={config.mqtt_username}
            onChange={(e) => handleChange('mqtt_username', e.target.value)}
            disabled={disabled}
            placeholder="Optional"
            className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Password
          </label>
          <input
            type="password"
            value={config.mqtt_password}
            onChange={(e) => handleChange('mqtt_password', e.target.value)}
            disabled={disabled}
            placeholder="Optional"
            className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          />
        </div>
      </div>
      <p className="-mt-2 text-xs text-gray-500">
        The broker user must have permission to <span className="font-medium">subscribe</span> (read) on the topic filter below.
      </p>

      {/* Topic Filter */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Topic Filter <span className="text-red-500">*</span>
        </label>
        <input
          type="text"
          value={config.mqtt_topic_filter}
          onChange={(e) => handleChange('mqtt_topic_filter', e.target.value)}
          disabled={disabled}
          placeholder="energy/+/reading"
          className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm font-mono"
        />
        <p className="mt-1 text-xs text-gray-500">
          Use <code className="font-mono">+</code> to match a single level (e.g. <code className="font-mono">energy/+/reading</code>) and <code className="font-mono">#</code> to match all remaining levels (e.g. <code className="font-mono">home/#</code>)
        </p>
      </div>

      {/* QoS + Payload Format */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            QoS
          </label>
          <select
            value={config.mqtt_qos}
            onChange={(e) => handleChange('mqtt_qos', parseInt(e.target.value))}
            disabled={disabled}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option value={0}>0 - At most once</option>
            <option value={1}>1 - At least once</option>
            <option value={2}>2 - Exactly once</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Payload Format
          </label>
          <select
            value={config.mqtt_payload_format}
            onChange={(e) => handleChange('mqtt_payload_format', e.target.value)}
            disabled={disabled}
            className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
          >
            <option value="json">JSON (parsed)</option>
            <option value="plain">Plain text</option>
          </select>
          <p className="mt-1 text-xs text-gray-500">
            JSON payloads that fail to parse fall back to plain text
          </p>
        </div>
      </div>

      {/* Client ID */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Client ID
        </label>
        <input
          type="text"
          value={config.mqtt_client_id}
          onChange={(e) => handleChange('mqtt_client_id', e.target.value)}
          disabled={disabled}
          placeholder="Auto-generated (ioflow-<flow-id>) if left empty"
          className="block w-full rounded-md border-gray-300 shadow-sm focus:ring-blue-500 focus:border-blue-500 sm:text-sm"
        />
      </div>

      {/* Performance & Delivery (batching, rate limit, dedup, concurrency) */}
      <MqttPerformanceSection
        value={config}
        onChange={(perfConfig) => {
          const updatedConfig = { ...config, ...perfConfig };
          setConfig(updatedConfig);
          onChange(updatedConfig);
        }}
        disabled={disabled}
      />

      {/* Preview */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="text-sm font-medium text-gray-700 mb-2">Configuration Summary</h4>
        <div className="text-xs text-gray-600 space-y-1">
          <p><span className="font-medium">Broker:</span> {config.mqtt_host ? `${config.mqtt_host}:${config.mqtt_port}` : '(not set)'}{config.mqtt_tls ? ' (TLS)' : ''}</p>
          <p><span className="font-medium">Topic:</span> {config.mqtt_topic_filter || '(not set)'}</p>
          <p><span className="font-medium">QoS:</span> {config.mqtt_qos}</p>
          <p><span className="font-medium">Auth:</span> {config.mqtt_username ? config.mqtt_username : 'anonymous'}</p>
          <p><span className="font-medium">Payload:</span> {config.mqtt_payload_format}</p>
        </div>
      </div>

      {/* Variables Available */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-green-800 mb-2">Available Variables in Flow</h4>
        <div className="text-xs text-green-700 space-y-1 font-mono">
          <p>• input.topic - Topic the message was published to</p>
          <p>• input.payload - Decoded payload (parsed object when JSON)</p>
          <p>• input.payload_raw - Raw payload string</p>
          <p>• input.qos - QoS level of the received message</p>
          <p>• input.retain - Whether the message was a retained message</p>
          <p>• input.timestamp - When the message was received</p>
        </div>
      </div>
    </div>
  );
};

export default MqttTriggerConfig;
