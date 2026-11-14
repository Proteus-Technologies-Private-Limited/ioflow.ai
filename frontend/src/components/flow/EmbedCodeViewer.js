import React, { useState, useEffect } from 'react';
import { 
  XMarkIcon, 
  CodeBracketIcon,
  ClipboardDocumentIcon,
  EyeIcon,
  Cog6ToothIcon,
  DocumentDuplicateIcon,
  CheckIcon
} from '@heroicons/react/24/outline';
import { showErrorToast, showSuccessToast } from '../../utils/customToast';

const EmbedCodeViewer = ({ 
  isOpen, 
  onClose, 
  frontendApp 
}) => {
  const [embedConfig, setEmbedConfig] = useState({
    embed_type: 'widget',
    theme: 'light',
    width: '100%',
    height: 'auto',
    custom_css: '',
    callback_config: {}
  });

  const [embedCode, setEmbedCode] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeCodeTab, setActiveCodeTab] = useState('html');
  const [copiedSection, setCopiedSection] = useState(null);
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    if (frontendApp && isOpen) {
      generateEmbedCode();
    }
  }, [frontendApp, isOpen, embedConfig]);

  const generateEmbedCode = async () => {
    if (!frontendApp) return;

    setIsGenerating(true);
    try {
      const response = await fetch(`/api/v1/frontend-applications/${frontendApp.frontend_app_id}/embed-code`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify(embedConfig)
      });

      if (!response.ok) {
        throw new Error('Failed to generate embed code');
      }

      const result = await response.json();
      setEmbedCode(result);
    } catch (error) {
      showErrorToast(`Failed to generate embed code: ${error.message}`);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleConfigChange = (field, value) => {
    setEmbedConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const copyToClipboard = async (text, section) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedSection(section);
      showSuccessToast(`${section} code copied to clipboard`);
      setTimeout(() => setCopiedSection(null), 2000);
    } catch (error) {
      showErrorToast('Failed to copy to clipboard');
    }
  };

  const getPreviewContent = () => {
    if (!embedCode) return '';

    if (embedConfig.embed_type === 'iframe') {
      return embedCode.html;
    } else {
      return `
        <!DOCTYPE html>
        <html>
        <head>
          <title>IOFlow App Preview</title>
          <style>${embedCode.css}</style>
        </head>
        <body>
          ${embedCode.html}
          <script>${embedCode.javascript}</script>
        </body>
        </html>
      `;
    }
  };

  if (!isOpen || !frontendApp) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[100]">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-4 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <CodeBracketIcon className="w-6 h-6" />
              <div>
                <h2 className="text-xl font-semibold">Embed Code Generator</h2>
                <p className="text-blue-100 text-sm">{frontendApp.frontend_app_name}</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 transition-colors"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>
        </div>

        <div className="flex h-[80vh]">
          {/* Configuration Panel */}
          <div className="w-1/3 bg-gray-50 border-r p-6 overflow-y-auto">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Configuration</h3>
            
            <div className="space-y-6">
              {/* Embed Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Embed Type
                </label>
                <div className="space-y-2">
                  <div className="flex items-center">
                    <input
                      type="radio"
                      id="widget"
                      name="embed_type"
                      value="widget"
                      checked={embedConfig.embed_type === 'widget'}
                      onChange={(e) => handleConfigChange('embed_type', e.target.value)}
                      className="h-4 w-4 text-blue-600"
                    />
                    <label htmlFor="widget" className="ml-3 text-sm text-gray-900">
                      Widget (Full HTML/CSS/JS)
                    </label>
                  </div>
                  <div className="flex items-center">
                    <input
                      type="radio"
                      id="iframe"
                      name="embed_type"
                      value="iframe"
                      checked={embedConfig.embed_type === 'iframe'}
                      onChange={(e) => handleConfigChange('embed_type', e.target.value)}
                      className="h-4 w-4 text-blue-600"
                    />
                    <label htmlFor="iframe" className="ml-3 text-sm text-gray-900">
                      iFrame (Simple)
                    </label>
                  </div>
                  <div className="flex items-center">
                    <input
                      type="radio"
                      id="modal"
                      name="embed_type"
                      value="modal"
                      checked={embedConfig.embed_type === 'modal'}
                      onChange={(e) => handleConfigChange('embed_type', e.target.value)}
                      className="h-4 w-4 text-blue-600"
                    />
                    <label htmlFor="modal" className="ml-3 text-sm text-gray-900">
                      Modal (Trigger Button)
                    </label>
                  </div>
                </div>
              </div>

              {/* Theme */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Theme
                </label>
                <select
                  value={embedConfig.theme}
                  onChange={(e) => handleConfigChange('theme', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                  <option value="custom">Custom</option>
                </select>
              </div>

              {/* Dimensions */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Width
                  </label>
                  <input
                    type="text"
                    value={embedConfig.width}
                    onChange={(e) => handleConfigChange('width', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="100%"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Height
                  </label>
                  <input
                    type="text"
                    value={embedConfig.height}
                    onChange={(e) => handleConfigChange('height', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="auto"
                  />
                </div>
              </div>

              {/* Custom CSS */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Custom CSS (optional)
                </label>
                <textarea
                  value={embedConfig.custom_css}
                  onChange={(e) => handleConfigChange('custom_css', e.target.value)}
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  placeholder="/* Your custom styles */"
                />
              </div>

              {/* Application Info */}
              <div className="pt-4 border-t border-gray-200">
                <h4 className="text-sm font-medium text-gray-900 mb-2">Application Details</h4>
                <div className="text-xs text-gray-600 space-y-1">
                  <div>
                    <span className="font-medium">URL:</span> {frontendApp.public_url}
                  </div>
                  <div>
                    <span className="font-medium">Access:</span> {frontendApp.access_type?.replace('_', ' ')}
                  </div>
                  <div>
                    <span className="font-medium">Rate Limit:</span> {frontendApp.rate_limit_per_hour}/hour
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Code Display Panel */}
          <div className="flex-1 flex flex-col">
            {/* Code Tabs */}
            <div className="border-b bg-white">
              <nav className="flex px-6">
                <button
                  onClick={() => setActiveCodeTab('html')}
                  className={`py-3 px-4 text-sm font-medium border-b-2 ${
                    activeCodeTab === 'html'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  HTML
                </button>
                {embedConfig.embed_type === 'widget' && (
                  <>
                    <button
                      onClick={() => setActiveCodeTab('css')}
                      className={`py-3 px-4 text-sm font-medium border-b-2 ${
                        activeCodeTab === 'css'
                          ? 'border-blue-500 text-blue-600'
                          : 'border-transparent text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      CSS
                    </button>
                    <button
                      onClick={() => setActiveCodeTab('javascript')}
                      className={`py-3 px-4 text-sm font-medium border-b-2 ${
                        activeCodeTab === 'javascript'
                          ? 'border-blue-500 text-blue-600'
                          : 'border-transparent text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      JavaScript
                    </button>
                  </>
                )}
                {embedCode?.sdk_code && (
                  <button
                    onClick={() => setActiveCodeTab('sdk')}
                    className={`py-3 px-4 text-sm font-medium border-b-2 ${
                      activeCodeTab === 'sdk'
                        ? 'border-blue-500 text-blue-600'
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    SDK
                  </button>
                )}
                <button
                  onClick={() => setActiveCodeTab('complete')}
                  className={`py-3 px-4 text-sm font-medium border-b-2 ${
                    activeCodeTab === 'complete'
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Complete
                </button>
                
                <div className="ml-auto flex items-center space-x-2">
                  <button
                    onClick={() => setShowPreview(!showPreview)}
                    className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 flex items-center"
                  >
                    <EyeIcon className="w-4 h-4 mr-1" />
                    {showPreview ? 'Hide Preview' : 'Show Preview'}
                  </button>
                  <button
                    onClick={generateEmbedCode}
                    disabled={isGenerating}
                    className="px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 flex items-center"
                  >
                    <Cog6ToothIcon className={`w-4 h-4 mr-1 ${isGenerating ? 'animate-spin' : ''}`} />
                    {isGenerating ? 'Generating...' : 'Regenerate'}
                  </button>
                </div>
              </nav>
            </div>

            {/* Code Content */}
            <div className="flex-1 overflow-hidden">
              {showPreview ? (
                <div className="h-full p-4 bg-gray-100">
                  <iframe
                    srcDoc={getPreviewContent()}
                    className="w-full h-full border border-gray-300 rounded-md"
                    title="Embed Preview"
                  />
                </div>
              ) : (
                <div className="h-full relative">
                  {embedCode ? (
                    <div className="h-full flex flex-col">
                      <div className="flex items-center justify-between p-4 bg-gray-50 border-b">
                        <h4 className="text-sm font-medium text-gray-900">
                          {activeCodeTab === 'html' && 'HTML Code'}
                          {activeCodeTab === 'css' && 'CSS Code'}
                          {activeCodeTab === 'javascript' && 'JavaScript Code'}
                          {activeCodeTab === 'sdk' && 'JavaScript SDK'}
                          {activeCodeTab === 'complete' && 'Complete Integration Code'}
                        </h4>
                        <button
                          onClick={() => {
                            let code = '';
                            if (activeCodeTab === 'html') code = embedCode.html;
                            else if (activeCodeTab === 'css') code = embedCode.css;
                            else if (activeCodeTab === 'javascript') code = embedCode.javascript;
                            else if (activeCodeTab === 'sdk') code = embedCode.sdk_code;
                            else if (activeCodeTab === 'complete') {
                              code = `<!-- HTML -->\n${embedCode.html}\n\n/* CSS */\n${embedCode.css}\n\n// JavaScript\n${embedCode.javascript}`;
                            }
                            copyToClipboard(code, activeCodeTab.toUpperCase());
                          }}
                          className="px-3 py-1 bg-blue-600 text-white rounded-md hover:bg-blue-700 flex items-center text-sm"
                        >
                          {copiedSection === activeCodeTab.toUpperCase() ? (
                            <>
                              <CheckIcon className="w-4 h-4 mr-1" />
                              Copied!
                            </>
                          ) : (
                            <>
                              <DocumentDuplicateIcon className="w-4 h-4 mr-1" />
                              Copy Code
                            </>
                          )}
                        </button>
                      </div>
                      
                      <div className="flex-1 overflow-auto">
                        <pre className="p-4 text-sm bg-gray-900 text-green-400 h-full overflow-auto">
                          <code>
                            {activeCodeTab === 'html' && embedCode.html}
                            {activeCodeTab === 'css' && embedCode.css}
                            {activeCodeTab === 'javascript' && embedCode.javascript}
                            {activeCodeTab === 'sdk' && embedCode.sdk_code}
                            {activeCodeTab === 'complete' && (
                              `<!-- HTML -->\n${embedCode.html}\n\n/* CSS */\n<style>\n${embedCode.css}\n</style>\n\n<!-- JavaScript -->\n<script>\n${embedCode.javascript}\n</script>`
                            )}
                          </code>
                        </pre>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full">
                      <div className="text-center">
                        <CodeBracketIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                        <p className="text-gray-500">
                          {isGenerating ? 'Generating embed code...' : 'Configure settings and generate embed code'}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 px-6 py-4 border-t">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              Embed code for: <span className="font-medium">{frontendApp.frontend_app_name}</span>
            </div>
            <div className="flex space-x-3">
              {embedCode && (
                <button
                  onClick={() => copyToClipboard(getPreviewContent(), 'Complete HTML')}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 flex items-center"
                >
                  <ClipboardDocumentIcon className="w-4 h-4 mr-2" />
                  Copy Complete Code
                </button>
              )}
              <button
                onClick={onClose}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EmbedCodeViewer;