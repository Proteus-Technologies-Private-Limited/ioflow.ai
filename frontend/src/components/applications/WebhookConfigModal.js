import React, { useState } from 'react';
import { XMarkIcon, BoltIcon, PlusIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import axios from 'axios';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const WebhookConfigModal = ({ application, onClose, onUpdate }) => {
  const [webhookConfig, setWebhookConfig] = useState(() => {
    const config = application?.webhook_config;
    return typeof config === 'string' ? JSON.parse(config) : (config || {});
  });
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.put(
        `${API_BASE_URL}/api/v1/applications/${application.app_id}/webhook-config`,
        { webhook_config: webhookConfig },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      showSuccessToast('Webhook configuration updated successfully');
      onUpdate(response.data);
      onClose();
    } catch (error) {
      showErrorToast((error.response?.data?.message || error.response?.data?.detail) || 'Failed to update webhook configuration');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-[9999]">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        <form onSubmit={handleSubmit}>
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center">
              <BoltIcon className="w-5 h-5 text-gray-400 mr-2" />
              <h3 className="text-lg font-medium text-gray-900">
                Webhook Configuration
              </h3>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          <div className="px-6 py-4 space-y-6 overflow-y-auto max-h-[calc(90vh-200px)]">
            {/* Verification Method */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Verification Method
              </label>
              <select
                value={webhookConfig.verification_method || 'none'}
                onChange={(e) => setWebhookConfig({ ...webhookConfig, verification_method: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
              >
                <option value="none">None (No verification)</option>
                <option value="hmac">HMAC Signature</option>
                <option value="token">Token/API Key</option>
                <option value="challenge">URL Challenge</option>
              </select>
              <p className="mt-1 text-xs text-gray-500">
                How to verify incoming webhooks are authentic
              </p>
            </div>

            {/* API Key Header Name - Incoming Configuration */}
            <div className="border-t pt-4">
              <div className="flex items-center mb-2">
                <InformationCircleIcon className="w-4 h-4 text-indigo-500 mr-1" />
                <h4 className="text-sm font-medium text-gray-900">Incoming API Key Configuration</h4>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  API Key Header Name (Optional)
                </label>
                <input
                  type="text"
                  value={webhookConfig.api_key_header_name || ''}
                  onChange={(e) => setWebhookConfig({ ...webhookConfig, api_key_header_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono text-sm"
                  placeholder="X-Custom-Api-Key"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Custom header name for API key authentication. If not specified, will use standard headers:
                  <code className="ml-1 px-1 py-0.5 bg-gray-100 rounded text-xs">Authorization</code> or
                  <code className="ml-1 px-1 py-0.5 bg-gray-100 rounded text-xs">X-API-Key</code>
                </p>
                <div className="mt-2 p-2 bg-blue-50 border border-blue-200 rounded-md">
                  <p className="text-xs text-blue-800">
                    <strong>Example:</strong> For Telegram webhooks, use
                    <code className="ml-1 px-1 py-0.5 bg-blue-100 rounded">X-Telegram-Bot-Api-Secret-Token</code>
                    to receive the secret_token sent by Telegram.
                  </p>
                </div>
              </div>
            </div>

            {/* HMAC Configuration */}
            {webhookConfig.verification_method === 'hmac' && (
              <div className="space-y-4 border-t pt-4">
                <h4 className="text-sm font-medium text-gray-900">HMAC Configuration</h4>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Signature Header Name
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.signature_header || ''}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, signature_header: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="X-Webhook-Signature"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Header containing the HMAC signature
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Signature Algorithm
                  </label>
                  <select
                    value={webhookConfig.signature_algorithm || 'sha256'}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, signature_algorithm: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  >
                    <option value="sha256">SHA-256</option>
                    <option value="sha1">SHA-1</option>
                    <option value="sha512">SHA-512</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Signature Format Template
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.signature_format || '{{signature}}'}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, signature_format: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                    placeholder="{{signature}}"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Format template for the signature header value. Use {"{{signature}}"} as placeholder.
                    Examples: "sha256={'{{signature}}'}" for GitHub, "v0={'{{signature}}'}" for Slack
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Signature Base Format
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.signature_base_format || '{{body}}'}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, signature_base_format: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                    placeholder="{{body}}"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Template for building the signature base string. Available variables: {"{{body}}"}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Timestamp Header Name (Optional)
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.timestamp_header || ''}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, timestamp_header: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="X-Webhook-Timestamp"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Header containing the request timestamp (for replay protection)
                  </p>
                </div>

                {webhookConfig.timestamp_header && (
                  <>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Timestamp Tolerance (seconds)
                      </label>
                      <input
                        type="number"
                        value={webhookConfig.timestamp_tolerance || 300}
                        onChange={(e) => setWebhookConfig({ ...webhookConfig, timestamp_tolerance: parseInt(e.target.value) })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                        min="60"
                        max="3600"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Maximum age of webhook requests (default: 300 seconds)
                      </p>
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Signature Base Format with Timestamp
                      </label>
                      <input
                        type="text"
                        value={webhookConfig.signature_base_format_with_timestamp || '{{timestamp}}:{{body}}'}
                        onChange={(e) => setWebhookConfig({ ...webhookConfig, signature_base_format_with_timestamp: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
                        placeholder="{{timestamp}}:{{body}}"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Template when timestamp is present. Variables: {"{{timestamp}}"}, {"{{body}}"}.
                        Example for Slack: "v0:{'{{timestamp}}'}:{'{{body}}'}"
                      </p>
                    </div>
                  </>
                )}

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="signing_secret_required"
                    checked={webhookConfig.signing_secret_required || false}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, signing_secret_required: e.target.checked })}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="signing_secret_required" className="ml-2 block text-sm text-gray-900">
                    Require signing secret from users
                  </label>
                </div>
              </div>
            )}

            {/* Token Configuration */}
            {webhookConfig.verification_method === 'token' && (
              <div className="space-y-4 border-t pt-4">
                <h4 className="text-sm font-medium text-gray-900">Token Configuration</h4>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Token Header Name
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.token_header || 'Authorization'}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, token_header: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="Authorization"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Token Query Parameter (Optional)
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.token_param || ''}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, token_param: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="token"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Query parameter name if token is sent in URL
                  </p>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="webhook_token_required"
                    checked={webhookConfig.webhook_token_required || false}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, webhook_token_required: e.target.checked })}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="webhook_token_required" className="ml-2 block text-sm text-gray-900">
                    Require webhook token from users
                  </label>
                </div>
              </div>
            )}

            {/* URL Challenge Configuration */}
            {(webhookConfig.verification_method === 'challenge' || webhookConfig.url_verification_enabled) && (
              <div className="space-y-4 border-t pt-4">
                <h4 className="text-sm font-medium text-gray-900">Challenge Configuration</h4>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="url_verification_enabled"
                    checked={webhookConfig.url_verification_enabled !== false}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, url_verification_enabled: e.target.checked })}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="url_verification_enabled" className="ml-2 block text-sm text-gray-900">
                    Enable URL verification challenges
                  </label>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Verification Token (Optional)
                  </label>
                  <input
                    type="text"
                    value={webhookConfig.verify_token || ''}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, verify_token: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    placeholder="Optional verification token"
                  />
                  <p className="mt-1 text-xs text-gray-500">
                    Token to verify during challenge (e.g., for Facebook)
                  </p>
                </div>

                {/* Challenge Configurations */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Challenge Configurations
                  </label>
                  <div className="space-y-3">
                    {(webhookConfig.challenge_configs || []).map((config, index) => (
                      <div key={index} className="border border-gray-200 rounded-md p-4 space-y-3">
                        <div className="flex justify-between items-start">
                          <h5 className="text-sm font-medium text-gray-900">Challenge Config #{index + 1}</h5>
                          <button
                            type="button"
                            onClick={() => {
                              const newConfigs = [...(webhookConfig.challenge_configs || [])];
                              newConfigs.splice(index, 1);
                              setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                            }}
                            className="text-red-600 hover:text-red-800"
                          >
                            <XMarkIcon className="w-5 h-5" />
                          </button>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-gray-700">
                              Name
                            </label>
                            <input
                              type="text"
                              value={config.name || ''}
                              onChange={(e) => {
                                const newConfigs = [...(webhookConfig.challenge_configs || [])];
                                newConfigs[index] = { ...config, name: e.target.value };
                                setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                              }}
                              className="mt-1 w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                              placeholder="Slack URL Verification"
                            />
                          </div>
                          
                          <div>
                            <label className="block text-xs font-medium text-gray-700">
                              Method
                            </label>
                            <select
                              value={config.method || 'POST'}
                              onChange={(e) => {
                                const newConfigs = [...(webhookConfig.challenge_configs || [])];
                                newConfigs[index] = { ...config, method: e.target.value };
                                setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                              }}
                              className="mt-1 w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                            >
                              <option value="GET">GET</option>
                              <option value="POST">POST</option>
                            </select>
                          </div>
                          
                          <div>
                            <label className="block text-xs font-medium text-gray-700">
                              Challenge Field
                            </label>
                            <input
                              type="text"
                              value={config.challenge_field || ''}
                              onChange={(e) => {
                                const newConfigs = [...(webhookConfig.challenge_configs || [])];
                                newConfigs[index] = { ...config, challenge_field: e.target.value };
                                setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                              }}
                              className="mt-1 w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                              placeholder="challenge"
                            />
                          </div>
                          
                          <div>
                            <label className="block text-xs font-medium text-gray-700">
                              Response Field
                            </label>
                            <input
                              type="text"
                              value={config.response_field || ''}
                              onChange={(e) => {
                                const newConfigs = [...(webhookConfig.challenge_configs || [])];
                                newConfigs[index] = { ...config, response_field: e.target.value };
                                setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                              }}
                              className="mt-1 w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                              placeholder="challenge"
                            />
                          </div>
                        </div>
                        
                        <div>
                          <label className="block text-xs font-medium text-gray-700">
                            Conditions (JSON)
                          </label>
                          <textarea
                            value={JSON.stringify(config.conditions || {}, null, 2)}
                            onChange={(e) => {
                              try {
                                const conditions = JSON.parse(e.target.value);
                                const newConfigs = [...(webhookConfig.challenge_configs || [])];
                                newConfigs[index] = { ...config, conditions };
                                setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                              } catch (err) {
                                // Invalid JSON, ignore
                              }
                            }}
                            className="mt-1 w-full px-2 py-1 text-sm border border-gray-300 rounded-md font-mono"
                            rows={2}
                            placeholder='{"type": "url_verification"}'
                          />
                        </div>
                        
                        {config.method === 'GET' && (
                          <div>
                            <label className="block text-xs font-medium text-gray-700">
                              Token Field (Optional)
                            </label>
                            <input
                              type="text"
                              value={config.token_field || ''}
                              onChange={(e) => {
                                const newConfigs = [...(webhookConfig.challenge_configs || [])];
                                newConfigs[index] = { ...config, token_field: e.target.value };
                                setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                              }}
                              className="mt-1 w-full px-2 py-1 text-sm border border-gray-300 rounded-md"
                              placeholder="hub.verify_token"
                            />
                          </div>
                        )}

                        {/* Plain Text Response Option */}
                        <div className="col-span-2 mt-2">
                          <div className="flex items-center">
                            <input
                              type="checkbox"
                              id={`plain_text_response_${index}`}
                              checked={config.plain_text_response || false}
                              onChange={(e) => {
                                const newConfigs = [...(webhookConfig.challenge_configs || [])];
                                newConfigs[index] = { ...config, plain_text_response: e.target.checked };
                                setWebhookConfig({ ...webhookConfig, challenge_configs: newConfigs });
                              }}
                              className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                            />
                            <label htmlFor={`plain_text_response_${index}`} className="ml-2 block text-xs text-gray-900">
                              Plain text response (required for META/Facebook webhooks)
                            </label>
                          </div>
                          <p className="mt-1 text-xs text-gray-500 ml-6">
                            When enabled, returns challenge value as plain text instead of JSON. Required by META WhatsApp and Facebook.
                          </p>
                        </div>
                      </div>
                    ))}
                    
                    <button
                      type="button"
                      onClick={() => {
                        const newConfig = {
                          name: '',
                          method: 'POST',
                          conditions: {},
                          challenge_field: 'challenge',
                          response_field: 'challenge',
                          plain_text_response: false
                        };
                        setWebhookConfig({
                          ...webhookConfig,
                          challenge_configs: [...(webhookConfig.challenge_configs || []), newConfig]
                        });
                      }}
                      className="flex items-center text-sm text-indigo-600 hover:text-indigo-700"
                    >
                      <PlusIcon className="w-4 h-4 mr-1" />
                      Add Challenge Configuration
                    </button>
                  </div>
                  
                  <div className="mt-2 bg-blue-50 border border-blue-200 rounded-md p-3">
                    <p className="text-xs text-blue-800">
                      <InformationCircleIcon className="w-4 h-4 inline mr-1" />
                      Challenge configurations define how to handle URL verification requests from different providers.
                      For example, Slack sends POST with type="url_verification", while Facebook/META uses GET with hub.mode="subscribe".
                      <strong> For META WhatsApp/Facebook webhooks, enable "Plain text response"</strong> as they require the challenge to be returned as plain text, not JSON.
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Additional Settings */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Additional Settings</h4>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Supported Events (comma-separated)
                </label>
                <input
                  type="text"
                  value={(webhookConfig.events || []).join(', ')}
                  onChange={(e) => setWebhookConfig({ 
                    ...webhookConfig, 
                    events: e.target.value.split(',').map(s => s.trim()).filter(s => s)
                  })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  placeholder="push, pull_request, issues"
                />
                <p className="mt-1 text-xs text-gray-500">
                  List of event types this webhook supports
                </p>
              </div>
            </div>

            {/* Legacy Support */}
            <div className="border-t pt-4">
              <h4 className="text-sm font-medium text-gray-900 mb-3">Legacy Settings</h4>
              
              <div className="flex items-center space-x-4">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="verification_token_required"
                    checked={webhookConfig.verification_token_required || false}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, verification_token_required: e.target.checked })}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="verification_token_required" className="ml-2 block text-sm text-gray-900">
                    Verification token required
                  </label>
                </div>

                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="secret_required"
                    checked={webhookConfig.secret_required || false}
                    onChange={(e) => setWebhookConfig({ ...webhookConfig, secret_required: e.target.checked })}
                    className="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded"
                  />
                  <label htmlFor="secret_required" className="ml-2 block text-sm text-gray-900">
                    Secret required (legacy)
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default WebhookConfigModal;