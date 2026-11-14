import React from 'react';
import {
  GlobeAltIcon,
  BoltIcon,
  EnvelopeIcon,
  CpuChipIcon,
  ServerIcon,
  CircleStackIcon
} from '@heroicons/react/24/outline';
import { usePluginRegistry } from '../../plugins/registry';
import SchemaRenderer from '../../plugins/SchemaRenderer';

const ServiceTypeConfig = ({ serviceType, config, onChange, mode = 'edit' }) => {
  const pluginRegistry = usePluginRegistry();
  const handleChange = (field, value) => {
    // For method field, place it inside request_config
    if (field === 'method') {
      onChange({
        ...config,
        request_config: {
          ...config?.request_config,
          method: value
        }
      });
    } else {
      onChange({
        ...config,
        [field]: value
      });
    }
  };

  const renderApiCallConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">HTTP Method</label>
          <select
            value={config?.request_config?.method || 'GET'}
            onChange={(e) => handleChange('method', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="DELETE">DELETE</option>
            <option value="PATCH">PATCH</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">Response Type</label>
          <select
            value={config?.response_type || 'json'}
            onChange={(e) => handleChange('response_type', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="json">JSON</option>
            <option value="xml">XML</option>
            <option value="text">Plain Text</option>
            <option value="binary">Binary</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Parameter Method</label>
          <select
            value={config?.request_config?.parameter_method || 'json_payload'}
            onChange={(e) => {
              onChange({
                ...config,
                request_config: {
                  ...config?.request_config,
                  parameter_method: e.target.value
                }
              });
            }}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="json_payload">JSON Body</option>
            <option value="query_params">Query Parameters</option>
            <option value="form_data">Form Data</option>
            <option value="xml_payload">XML Body</option>
            <option value="path_params">Path Parameters Only</option>
            <option value="multipart">Multipart Form Data</option>
            <option value="multipart_related">Multipart Related (Google Drive)</option>
            <option value="url_pattern">URL Pattern</option>
          </select>
          <p className="mt-1 text-xs text-gray-500">How parameters are sent in the request</p>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">Content Type</label>
          <input
            type="text"
            value={config?.content_type || ''}
            onChange={(e) => handleChange('content_type', e.target.value)}
            placeholder="Auto-detected based on parameter method"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
          <p className="mt-1 text-xs text-gray-500">Override default Content-Type header</p>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">
          Endpoint Template
          <span className="text-xs text-gray-500 ml-2">Use {'{variable}'} for placeholders</span>
        </label>
        <input
          type="text"
          value={config?.endpoint_template || ''}
          onChange={(e) => handleChange('endpoint_template', e.target.value)}
          placeholder="https://api.example.com/v1/users/{userId}"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          disabled={mode === 'view'}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Headers Template (JSON)</label>
        <textarea
          value={JSON.stringify(config?.headers_template || {}, null, 2)}
          onChange={(e) => {
            try {
              handleChange('headers_template', JSON.parse(e.target.value));
            } catch (err) {
              // Invalid JSON, ignore
            }
          }}
          rows={3}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm"
          disabled={mode === 'view'}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Timeout (seconds)</label>
        <input
          type="number"
          value={config?.timeout_seconds || 30}
          onChange={(e) => handleChange('timeout_seconds', parseInt(e.target.value))}
          min="1"
          max="300"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          disabled={mode === 'view'}
        />
      </div>

      {/* Query Parameters Template - Always show for API calls */}
      <div>
        <label className="block text-sm font-medium text-gray-700">Query Parameters Template (JSON)</label>
        <textarea
          value={JSON.stringify(config?.request_config?.query_params_template || {}, null, 2)}
          onChange={(e) => {
            try {
              const parsedValue = JSON.parse(e.target.value);
              handleChange('request_config', {
                ...config?.request_config,
                query_params_template: parsedValue
              });
            } catch (err) {
              // Invalid JSON, ignore
            }
          }}
          rows={3}
          placeholder={'{\n  "param1": "{{value1}}",\n  "param2": "{{value2}}"\n}'}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm"
          disabled={mode === 'view'}
        />
        <p className="mt-1 text-xs text-gray-500">
          Parameters to include in the URL query string. Use {"{{variable}}"} for dynamic values
        </p>
      </div>

      {/* Body Template - Always show for POST/PUT/PATCH */}
      {['POST', 'PUT', 'PATCH'].includes(config?.request_config?.method) && (
        <div>
          <label className="block text-sm font-medium text-gray-700">Body Template (JSON)</label>
          <textarea
            value={JSON.stringify(config?.request_config?.body_template || {}, null, 2)}
            onChange={(e) => {
              try {
                const parsedValue = JSON.parse(e.target.value);
                handleChange('request_config', {
                  ...config?.request_config,
                  body_template: parsedValue
                });
              } catch (err) {
                // Invalid JSON, ignore
              }
            }}
            rows={4}
            placeholder={'{\n  "field1": "{{value1}}",\n  "field2": "{{value2}}"\n}'}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm"
            disabled={mode === 'view'}
          />
          <p className="mt-1 text-xs text-gray-500">
            Template for request body. Defines exactly which parameters go in the body. Use {"{{variable}}"} for dynamic values
          </p>
        </div>
      )}

      {/* Sample Input/Output */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Sample Input (JSON)</label>
          <textarea
            value={JSON.stringify(config?.sample_input || {}, null, 2)}
            onChange={(e) => {
              try {
                handleChange('sample_input', JSON.parse(e.target.value));
              } catch (err) {
                // Invalid JSON, ignore
              }
            }}
            rows={3}
            placeholder='{\n  "key": "value"\n}'
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm"
            disabled={mode === 'view'}
          />
          <p className="mt-1 text-xs text-gray-500">Example input for testing</p>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700">Sample Output (JSON)</label>
          <textarea
            value={JSON.stringify(config?.sample_output || {}, null, 2)}
            onChange={(e) => {
              try {
                handleChange('sample_output', JSON.parse(e.target.value));
              } catch (err) {
                // Invalid JSON, ignore
              }
            }}
            rows={3}
            placeholder='{\n  "result": "success"\n}'
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm"
            disabled={mode === 'view'}
          />
          <p className="mt-1 text-xs text-gray-500">Expected output example</p>
        </div>
      </div>

      {/* Response Configuration Section */}
      <div className="col-span-2 border-t pt-4 mt-4">
        <h4 className="text-sm font-medium text-gray-900 mb-3">Response Configuration</h4>
        
        <div className="space-y-4">
          {/* Success Status Codes */}
          <div>
            <label className="block text-sm font-medium text-gray-700">Success Status Codes</label>
            <input
              type="text"
              defaultValue={config?.response_config?.success_check?.success_status_codes?.join(', ') || ''}
              onBlur={(e) => {
                const codes = e.target.value
                  .split(',')
                  .map(code => code.trim())
                  .filter(code => code && !isNaN(code))
                  .map(code => parseInt(code));
                
                handleChange('response_config', {
                  ...config?.response_config,
                  success_check: {
                    ...config?.response_config?.success_check,
                    type: 'status_code',
                    success_status_codes: codes.length > 0 ? codes : undefined
                  }
                });
              }}
              placeholder="200, 201, 400"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              disabled={mode === 'view'}
            />
            <p className="mt-1 text-xs text-gray-500">
              Comma-separated HTTP status codes to treat as success. Leave empty for default (200-399).
            </p>
          </div>
          
          {/* Error Message Extraction */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Error Message Field</label>
              <input
                type="text"
                value={config?.response_config?.error_extraction?.message_field || ''}
                onChange={(e) => {
                  handleChange('response_config', {
                    ...config?.response_config,
                    error_extraction: {
                      ...config?.response_config?.error_extraction,
                      message_field: e.target.value
                    }
                  });
                }}
                placeholder="error.message"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                disabled={mode === 'view'}
              />
              <p className="mt-1 text-xs text-gray-500">Path to error message in response</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700">Error Code Field</label>
              <input
                type="text"
                value={config?.response_config?.error_extraction?.error_field || ''}
                onChange={(e) => {
                  handleChange('response_config', {
                    ...config?.response_config,
                    error_extraction: {
                      ...config?.response_config?.error_extraction,
                      error_field: e.target.value
                    }
                  });
                }}
                placeholder="error.code"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                disabled={mode === 'view'}
              />
              <p className="mt-1 text-xs text-gray-500">Path to error code in response</p>
            </div>
          </div>
        </div>
      </div>
      
      {/* Request Configuration Section */}
      <div className="col-span-2 border-t pt-4 mt-4">
        <h4 className="text-sm font-medium text-gray-900 mb-3">Request Configuration</h4>
        
        <div className="space-y-4">
          {/* Pagination Configuration */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Pagination Type</label>
              <select
                value={config?.request_config?.pagination_type || 'none'}
                onChange={(e) => {
                  handleChange('request_config', {
                    ...config?.request_config,
                    pagination_type: e.target.value
                  });
                }}
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                disabled={mode === 'view'}
              >
                <option value="none">None</option>
                <option value="offset">Offset-based</option>
                <option value="cursor">Cursor-based</option>
                <option value="page">Page-based</option>
              </select>
            </div>
            
            {config?.request_config?.pagination_type !== 'none' && (
              <div>
                <label className="block text-sm font-medium text-gray-700">Page Size Parameter</label>
                <input
                  type="text"
                  value={config?.request_config?.page_size_param || 'limit'}
                  onChange={(e) => {
                    handleChange('request_config', {
                      ...config?.request_config,
                      page_size_param: e.target.value
                    });
                  }}
                  placeholder="limit"
                  className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                  disabled={mode === 'view'}
                />
              </div>
            )}
          </div>
          
          {/* Rate Limiting */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">Rate Limit (reqs/sec)</label>
              <input
                type="number"
                value={config?.request_config?.rate_limit || ''}
                onChange={(e) => {
                  handleChange('request_config', {
                    ...config?.request_config,
                    rate_limit: e.target.value ? parseInt(e.target.value) : null
                  });
                }}
                placeholder="10"
                min="1"
                max="1000"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                disabled={mode === 'view'}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700">Max Retries</label>
              <input
                type="number"
                value={config?.request_config?.max_retries || 3}
                onChange={(e) => {
                  handleChange('request_config', {
                    ...config?.request_config,
                    max_retries: parseInt(e.target.value)
                  });
                }}
                min="0"
                max="10"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                disabled={mode === 'view'}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700">Retry Delay (ms)</label>
              <input
                type="number"
                value={config?.request_config?.retry_delay || 1000}
                onChange={(e) => {
                  handleChange('request_config', {
                    ...config?.request_config,
                    retry_delay: parseInt(e.target.value)
                  });
                }}
                min="100"
                max="60000"
                step="100"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                disabled={mode === 'view'}
              />
            </div>
          </div>
          
          {/* Custom Headers */}
          <div className="flex items-center">
            <input
              type="checkbox"
              id="follow_redirects"
              checked={config?.request_config?.follow_redirects !== false}
              onChange={(e) => {
                handleChange('request_config', {
                  ...config?.request_config,
                  follow_redirects: e.target.checked
                });
              }}
              className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
              disabled={mode === 'view'}
            />
            <label htmlFor="follow_redirects" className="ml-2 block text-sm text-gray-900">
              Follow redirects automatically
            </label>
          </div>
        </div>
      </div>
    </div>
  );

  const renderWebhookConfig = () => (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700">Webhook URL</label>
        <input
          type="url"
          value={config?.webhook_url || ''}
          onChange={(e) => handleChange('webhook_url', e.target.value)}
          placeholder="https://webhook.site/unique-id"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          disabled={mode === 'view'}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Method</label>
          <select
            value={config?.request_config?.method || 'POST'}
            onChange={(e) => handleChange('method', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="GET">GET</option>
            <option value="POST">POST</option>
            <option value="PUT">PUT</option>
            <option value="PATCH">PATCH</option>
            <option value="DELETE">DELETE</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Signature Method</label>
          <select
            value={config?.signature_method || ''}
            onChange={(e) => handleChange('signature_method', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="">None</option>
            <option value="hmac-sha256">HMAC-SHA256</option>
            <option value="hmac-sha1">HMAC-SHA1</option>
            <option value="custom">Custom</option>
          </select>
        </div>
      </div>

      {config?.signature_method && (
        <div>
          <label className="block text-sm font-medium text-gray-700">Signature Header</label>
          <input
            type="text"
            value={config?.signature_header || ''}
            onChange={(e) => handleChange('signature_header', e.target.value)}
            placeholder="X-Webhook-Signature"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      )}
    </div>
  );

  const renderEmailConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">From Address</label>
          <input
            type="email"
            value={config?.from_address || ''}
            onChange={(e) => handleChange('from_address', e.target.value)}
            placeholder="noreply@example.com"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">From Name</label>
          <input
            type="text"
            value={config?.from_name || ''}
            onChange={(e) => handleChange('from_name', e.target.value)}
            placeholder="My Application"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Subject Template</label>
        <input
          type="text"
          value={config?.subject_template || ''}
          onChange={(e) => handleChange('subject_template', e.target.value)}
          placeholder="Welcome {{ user_name }}!"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          disabled={mode === 'view'}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Body Template</label>
        <textarea
          value={config?.body_template || ''}
          onChange={(e) => handleChange('body_template', e.target.value)}
          rows={6}
          placeholder="<h1>Hello {{ user_name }}!</h1>"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm"
          disabled={mode === 'view'}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Body Type</label>
          <select
            value={config?.body_type || 'html'}
            onChange={(e) => handleChange('body_type', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="html">HTML</option>
            <option value="plain">Plain Text</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Template Engine</label>
          <select
            value={config?.template_engine || 'jinja2'}
            onChange={(e) => handleChange('template_engine', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="jinja2">Jinja2</option>
            <option value="mustache">Mustache</option>
            <option value="plain">Plain (no templating)</option>
          </select>
        </div>
      </div>
    </div>
  );

  const renderSmtpSendConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">SMTP Host</label>
          <input
            type="text"
            value={config?.smtp_host || ''}
            onChange={(e) => handleChange('smtp_host', e.target.value)}
            placeholder="smtp.gmail.com"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">SMTP Port</label>
          <input
            type="number"
            value={config?.smtp_port || 587}
            onChange={(e) => handleChange('smtp_port', parseInt(e.target.value))}
            placeholder="587"
            min="1"
            max="65535"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Timeout (seconds)</label>
          <input
            type="number"
            value={config?.timeout_seconds || 30}
            onChange={(e) => handleChange('timeout_seconds', parseInt(e.target.value))}
            min="1"
            max="300"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex items-center">
          <input
            type="checkbox"
            id="use_tls"
            checked={config?.use_tls !== false}
            onChange={(e) => handleChange('use_tls', e.target.checked)}
            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            disabled={mode === 'view'}
          />
          <label htmlFor="use_tls" className="ml-2 block text-sm text-gray-900">
            Use TLS (STARTTLS) - Port 587
          </label>
        </div>

        <div className="flex items-center">
          <input
            type="checkbox"
            id="use_ssl"
            checked={config?.use_ssl === true}
            onChange={(e) => handleChange('use_ssl', e.target.checked)}
            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            disabled={mode === 'view'}
          />
          <label htmlFor="use_ssl" className="ml-2 block text-sm text-gray-900">
            Use SSL - Port 465
          </label>
        </div>
      </div>
    </div>
  );

  const renderPop3ReceiveConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">POP3 Host</label>
          <input
            type="text"
            value={config?.pop3_host || ''}
            onChange={(e) => handleChange('pop3_host', e.target.value)}
            placeholder="pop.gmail.com"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">POP3 Port</label>
          <input
            type="number"
            value={config?.pop3_port || 995}
            onChange={(e) => handleChange('pop3_port', parseInt(e.target.value))}
            placeholder="995"
            min="1"
            max="65535"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Timeout (seconds)</label>
          <input
            type="number"
            value={config?.timeout_seconds || 30}
            onChange={(e) => handleChange('timeout_seconds', parseInt(e.target.value))}
            min="1"
            max="300"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Max Messages</label>
          <input
            type="number"
            value={config?.max_messages || 50}
            onChange={(e) => handleChange('max_messages', parseInt(e.target.value))}
            min="1"
            max="1000"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div className="flex items-center">
          <input
            type="checkbox"
            id="use_ssl_pop3"
            checked={config?.use_ssl !== false}
            onChange={(e) => handleChange('use_ssl', e.target.checked)}
            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            disabled={mode === 'view'}
          />
          <label htmlFor="use_ssl_pop3" className="ml-2 block text-sm text-gray-900">
            Use SSL encryption
          </label>
        </div>
      </div>

      <div className="flex items-center">
        <input
          type="checkbox"
          id="delete_after_read"
          checked={config?.delete_after_read === true}
          onChange={(e) => handleChange('delete_after_read', e.target.checked)}
          className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
          disabled={mode === 'view'}
        />
        <label htmlFor="delete_after_read" className="ml-2 block text-sm text-gray-900">
          Delete messages after reading (⚠️ Caution: This permanently removes emails from server)
        </label>
      </div>
    </div>
  );

  const renderImapReceiveConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">IMAP Host</label>
          <input
            type="text"
            value={config?.imap_host || ''}
            onChange={(e) => handleChange('imap_host', e.target.value)}
            placeholder="imap.gmail.com"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">IMAP Port</label>
          <input
            type="number"
            value={config?.imap_port || 993}
            onChange={(e) => handleChange('imap_port', parseInt(e.target.value))}
            placeholder="993"
            min="1"
            max="65535"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Timeout (seconds)</label>
          <input
            type="number"
            value={config?.timeout_seconds || 30}
            onChange={(e) => handleChange('timeout_seconds', parseInt(e.target.value))}
            min="1"
            max="300"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Default Mailbox</label>
          <input
            type="text"
            value={config?.mailbox || 'INBOX'}
            onChange={(e) => handleChange('mailbox', e.target.value)}
            placeholder="INBOX"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Max Messages</label>
          <input
            type="number"
            value={config?.max_messages || 50}
            onChange={(e) => handleChange('max_messages', parseInt(e.target.value))}
            min="1"
            max="1000"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Default Search Criteria</label>
        <input
          type="text"
          value={config?.search_criteria || 'UNSEEN'}
          onChange={(e) => handleChange('search_criteria', e.target.value)}
          placeholder="UNSEEN"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          disabled={mode === 'view'}
        />
        <p className="mt-1 text-xs text-gray-500">
          IMAP search criteria (e.g., UNSEEN, FROM sender@example.com, SUBJECT test, SINCE 01-Jan-2024)
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="flex items-center">
          <input
            type="checkbox"
            id="use_ssl_imap"
            checked={config?.use_ssl !== false}
            onChange={(e) => handleChange('use_ssl', e.target.checked)}
            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            disabled={mode === 'view'}
          />
          <label htmlFor="use_ssl_imap" className="ml-2 block text-sm text-gray-900">
            Use SSL encryption
          </label>
        </div>

        <div className="flex items-center">
          <input
            type="checkbox"
            id="mark_as_read"
            checked={config?.mark_as_read !== false}
            onChange={(e) => handleChange('mark_as_read', e.target.checked)}
            className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
            disabled={mode === 'view'}
          />
          <label htmlFor="mark_as_read" className="ml-2 block text-sm text-gray-900">
            Mark messages as read after fetching
          </label>
        </div>
      </div>
    </div>
  );

  const renderLLMConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Provider</label>
          <select
            value={config?.provider || 'openai'}
            onChange={(e) => handleChange('provider', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="google">Google</option>
            <option value="azure">Azure OpenAI</option>
            <option value="custom">Custom</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Model</label>
          <input
            type="text"
            value={config?.model || ''}
            onChange={(e) => handleChange('model', e.target.value)}
            placeholder="gpt-4-turbo-preview"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      {config?.provider === 'custom' && (
        <div>
          <label className="block text-sm font-medium text-gray-700">Custom Endpoint</label>
          <input
            type="url"
            value={config?.endpoint || ''}
            onChange={(e) => handleChange('endpoint', e.target.value)}
            placeholder="https://api.custom-llm.com/v1/completions"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-gray-700">System Prompt Template</label>
        <textarea
          value={config?.system_prompt_template || ''}
          onChange={(e) => handleChange('system_prompt_template', e.target.value)}
          rows={3}
          placeholder="You are a helpful assistant..."
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          disabled={mode === 'view'}
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">User Prompt Template</label>
        <textarea
          value={config?.user_prompt_template || ''}
          onChange={(e) => handleChange('user_prompt_template', e.target.value)}
          rows={3}
          placeholder="Please help with: {{ task_description }}"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          disabled={mode === 'view'}
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Temperature</label>
          <input
            type="number"
            value={config?.temperature || 0.7}
            onChange={(e) => handleChange('temperature', parseFloat(e.target.value))}
            min="0"
            max="2"
            step="0.1"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Max Tokens</label>
          <input
            type="number"
            value={config?.max_tokens || ''}
            onChange={(e) => handleChange('max_tokens', e.target.value ? parseInt(e.target.value) : null)}
            min="1"
            placeholder="Auto"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Response Format</label>
          <select
            value={config?.response_format || 'text'}
            onChange={(e) => handleChange('response_format', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="text">Text</option>
            <option value="json_object">JSON Object</option>
          </select>
        </div>
      </div>
    </div>
  );

  const renderMCPConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Server Name</label>
          <input
            type="text"
            value={config?.server_name || ''}
            onChange={(e) => handleChange('server_name', e.target.value)}
            placeholder="my-mcp-server"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Tool Name</label>
          <input
            type="text"
            value={config?.tool_name || ''}
            onChange={(e) => handleChange('tool_name', e.target.value)}
            placeholder="search_documents"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700">Connection Config (JSON)</label>
        <textarea
          value={JSON.stringify(config?.connection_config || {}, null, 2)}
          onChange={(e) => {
            try {
              handleChange('connection_config', JSON.parse(e.target.value));
            } catch (err) {
              // Invalid JSON, ignore
            }
          }}
          rows={4}
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 font-mono text-sm"
          disabled={mode === 'view'}
        />
      </div>

      <div className="flex items-center">
        <input
          type="checkbox"
          id="retry_on_failure"
          checked={config?.retry_on_failure !== false}
          onChange={(e) => handleChange('retry_on_failure', e.target.checked)}
          className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
          disabled={mode === 'view'}
        />
        <label htmlFor="retry_on_failure" className="ml-2 block text-sm text-gray-900">
          Retry on failure
        </label>
      </div>
    </div>
  );

  const renderDatabaseQueryConfig = () => (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Operation Type</label>
          <select
            value={config?.operation_type || 'query'}
            onChange={(e) => handleChange('operation_type', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="query">Query (SELECT)</option>
            <option value="execute">Execute (INSERT/UPDATE/DELETE)</option>
            <option value="batch">Batch</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Result Format</label>
          <select
            value={config?.result_format || 'json_array'}
            onChange={(e) => handleChange('result_format', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="json_array">JSON Array</option>
            <option value="json_object">JSON Object (first row)</option>
            <option value="csv">CSV</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Transaction Mode</label>
          <select
            value={config?.transaction_mode || 'auto'}
            onChange={(e) => handleChange('transaction_mode', e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          >
            <option value="auto">Auto</option>
            <option value="manual">Manual</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Max Rows</label>
          <input
            type="number"
            value={config?.max_rows ?? 10000}
            onChange={(e) => handleChange('max_rows', parseInt(e.target.value))}
            min="1"
            max="100000"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
          <p className="mt-1 text-xs text-gray-500">Max rows returned (1–100,000). Result is truncated if exceeded.</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Fetch Size</label>
          <input
            type="number"
            value={config?.fetch_size ?? 1000}
            onChange={(e) => handleChange('fetch_size', parseInt(e.target.value))}
            min="100"
            max="10000"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
          <p className="mt-1 text-xs text-gray-500">Rows fetched per batch (100–10,000).</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Timeout (seconds)</label>
          <input
            type="number"
            value={config?.timeout_seconds ?? 30}
            onChange={(e) => handleChange('timeout_seconds', parseInt(e.target.value))}
            min="1"
            max="300"
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            disabled={mode === 'view'}
          />
        </div>
      </div>
    </div>
  );

  const getServiceIcon = () => {
    switch (serviceType) {
      case 'api_call':
      case 'graphql':
        return <GlobeAltIcon className="w-5 h-5" />;
      case 'webhook':
        return <BoltIcon className="w-5 h-5" />;
      case 'email_send':
      case 'smtp_send':
      case 'pop3_receive':
      case 'imap_receive':
        return <EnvelopeIcon className="w-5 h-5" />;
      case 'llm_api_call':
        return <CpuChipIcon className="w-5 h-5" />;
      case 'mcp_call':
        return <ServerIcon className="w-5 h-5" />;
      case 'database_query':
        return <CircleStackIcon className="w-5 h-5" />;
      default:
        return null;
    }
  };

  const getServiceTitle = () => {
    switch (serviceType) {
      case 'api_call':
        return 'API Call Configuration';
      case 'graphql':
        return 'GraphQL Configuration';
      case 'webhook':
        return 'Webhook Configuration';
      case 'email_send':
        return 'Email Configuration';
      case 'smtp_send':
        return 'SMTP Email Send Configuration';
      case 'pop3_receive':
        return 'POP3 Email Receive Configuration';
      case 'imap_receive':
        return 'IMAP Email Receive Configuration';
      case 'llm_api_call':
        return 'LLM API Configuration';
      case 'mcp_call':
        return 'MCP Call Configuration';
      case 'database_query':
        return 'Database Query Configuration';
      default:
        return 'Service Configuration';
    }
  };

  return (
    <div className="border rounded-lg p-4 bg-gray-50">
      <div className="flex items-center gap-2 mb-4">
        {getServiceIcon()}
        <h3 className="text-lg font-medium">{getServiceTitle()}</h3>
      </div>

      {(serviceType === 'api_call' || serviceType === 'graphql') && renderApiCallConfig()}
      {serviceType === 'webhook' && renderWebhookConfig()}
      {serviceType === 'email_send' && renderEmailConfig()}
      {serviceType === 'smtp_send' && renderSmtpSendConfig()}
      {serviceType === 'pop3_receive' && renderPop3ReceiveConfig()}
      {serviceType === 'imap_receive' && renderImapReceiveConfig()}
      {serviceType === 'llm_api_call' && renderLLMConfig()}
      {serviceType === 'mcp_call' && renderMCPConfig()}
      {serviceType === 'database_query' && renderDatabaseQueryConfig()}

      {/* Schema-driven fallback for plugin-registered service types */}
      {!['api_call', 'graphql', 'webhook', 'email_send', 'smtp_send', 'pop3_receive', 'imap_receive', 'llm_api_call', 'mcp_call', 'database_query'].includes(serviceType) && (() => {
        const pluginSchema = pluginRegistry?.getServiceTypeSchema?.(serviceType);
        if (pluginSchema?.config_schema) {
          return (
            <SchemaRenderer
              schema={pluginSchema.config_schema}
              value={config}
              onChange={onChange}
            />
          );
        }
        return null;
      })()}
    </div>
  );
};

export default ServiceTypeConfig;