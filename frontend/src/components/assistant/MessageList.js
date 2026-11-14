import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UserIcon,
  SparklesIcon,
  ClipboardDocumentIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  WrenchIcon,
  DocumentTextIcon,
  DocumentMagnifyingGlassIcon,
  PencilSquareIcon,
  CommandLineIcon,
  MagnifyingGlassIcon,
  FolderOpenIcon,
  GlobeAltIcon,
  CloudArrowDownIcon,
  DocumentPlusIcon,
  CogIcon
} from '@heroicons/react/24/outline';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

function MessageList({ messages }) {
  const navigate = useNavigate();
  const [copiedIndex, setCopiedIndex] = React.useState(null);
  const [expandedSteps, setExpandedSteps] = React.useState({});
  const [expandedStream, setExpandedStream] = React.useState({});
  const [expandedToolRequest, setExpandedToolRequest] = React.useState({});
  const [expandedToolResponse, setExpandedToolResponse] = React.useState({});
  const [copiedToolIndex, setCopiedToolIndex] = React.useState(null);

  const copyToClipboard = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const copyToolToClipboard = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedToolIndex(index);
    setTimeout(() => setCopiedToolIndex(null), 2000);
  };

  // Tool-specific icon, color, and label mapping
  const getToolMeta = (toolName) => {
    const map = {
      Read:      { icon: DocumentMagnifyingGlassIcon, color: 'blue',   label: 'Read File' },
      Write:     { icon: DocumentPlusIcon,            color: 'green',  label: 'Write File' },
      Edit:      { icon: PencilSquareIcon,            color: 'amber',  label: 'Edit File' },
      Bash:      { icon: CommandLineIcon,             color: 'slate',  label: 'Run Command' },
      Grep:      { icon: MagnifyingGlassIcon,         color: 'violet', label: 'Search Content' },
      Glob:      { icon: FolderOpenIcon,              color: 'cyan',   label: 'Find Files' },
      WebSearch: { icon: GlobeAltIcon,                color: 'indigo', label: 'Web Search' },
      WebFetch:  { icon: CloudArrowDownIcon,          color: 'teal',   label: 'Fetch URL' },
    };
    return map[toolName] || { icon: CogIcon, color: 'gray', label: toolName };
  };

  // Build a concise summary of what the tool is doing from its input
  const getToolSummary = (toolData) => {
    if (!toolData) return '';
    const { name, file, input } = toolData;
    const path = file || input?.file_path || input?.path || '';
    if (name === 'Bash') {
      const cmd = input?.command || toolData.args || '';
      // Truncate long commands
      return cmd.length > 120 ? cmd.slice(0, 120) + '...' : cmd;
    }
    if (name === 'Grep') {
      const pattern = input?.pattern || path || '';
      const target = input?.path || '';
      return pattern ? `/${pattern}/${target ? ' in ' + target : ''}` : '';
    }
    if (name === 'Glob') return input?.pattern || path || '';
    if (name === 'WebSearch') return input?.query || path || '';
    if (name === 'WebFetch') return input?.url || path || '';
    // Read, Write, Edit — show file path
    return path;
  };

  const formatDuration = (startTime, endTime) => {
    if (!startTime || !endTime) return null;
    const duration = new Date(endTime) - new Date(startTime);
    if (duration < 1000) return `${duration}ms`;
    if (duration < 60000) return `${(duration / 1000).toFixed(1)}s`;
    return `${Math.floor(duration / 60000)}m ${((duration % 60000) / 1000).toFixed(0)}s`;
  };

  const toggleSteps = (messageIndex) => {
    setExpandedSteps(prev => ({
      ...prev,
      [messageIndex]: !prev[messageIndex]
    }));
  };

  const toggleStream = (messageIndex) => {
    setExpandedStream(prev => ({
      ...prev,
      [messageIndex]: !prev[messageIndex]
    }));
  };

  const toggleToolRequest = (messageIndex) => {
    setExpandedToolRequest(prev => ({
      ...prev,
      [messageIndex]: !prev[messageIndex]
    }));
  };

  const toggleToolResponse = (messageIndex) => {
    setExpandedToolResponse(prev => ({
      ...prev,
      [messageIndex]: !prev[messageIndex]
    }));
  };

  const renderExecutionStep = (step, stepIndex) => {
    const isToolCall = step.type === 'tool_call';
    const icon = isToolCall ? (
      <WrenchIcon className="h-4 w-4 text-blue-600" />
    ) : (
      <DocumentTextIcon className="h-4 w-4 text-green-600" />
    );

    return (
      <div key={stepIndex} className="border-l-2 border-gray-200 ml-4 pl-4 py-2">
        <div className="flex items-start gap-2">
          {icon}
          <div className="flex-1">
            <div className="text-xs font-medium text-gray-600">
              {isToolCall ? 'Tool Call' : 'Tool Response'}: {step.name}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {isToolCall ? (
                <code className="bg-gray-100 px-1 py-0.5 rounded">
                  {typeof step.args === 'object' ? JSON.stringify(step.args) : step.args}
                </code>
              ) : (
                <div className="whitespace-pre-wrap">
                  {typeof step.response === 'object' ? JSON.stringify(step.response, null, 2) : step.response}
                </div>
              )}
            </div>
            {step.timestamp && (
              <div className="text-xs text-gray-400 mt-1">
                {new Date(step.timestamp).toLocaleTimeString()}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const renderMessage = (message, index, messages) => {
    const isUser = message.role === 'user';
    const isToolCall = message.isToolCall;
    const isFinalResponse = message.isFinalResponse || false;
    const isStreaming = message.isStreaming || false;
    const isStreamingChunk = message.isStreamingChunk || false;
    const isCancelled = message.isCancelled || false;
    const isThinking = message.isThinking || false;
    const isCompletionIndicator = message.isCompletionIndicator || false;

    const toolMeta = isToolCall && message.toolData ? getToolMeta(message.toolData.name) : null;
    const ToolIcon = toolMeta?.icon || WrenchIcon;

    const icon = isUser ? (
      <UserIcon className="h-5 w-5" />
    ) : isToolCall ? (
      <ToolIcon className="h-5 w-5" />
    ) : (
      <SparklesIcon className="h-5 w-5" />
    );

    // For thinking messages, check if they contain markdown that needs rendering
    if (isThinking) {
      // Check if the content contains markdown indicators (links, bold, code blocks, etc.)
      const hasMarkdown = message.content && (
        message.content.includes('[') && message.content.includes('](') ||
        message.content.includes('**') ||
        message.content.includes('`') ||
        message.content.includes('✅') ||
        message.content.includes('📝') ||
        message.content.includes('##')
      );

      if (hasMarkdown) {
        // Render with full markdown support for flow responses
        return (
          <div
            key={index}
            className="flex gap-3 justify-start mb-4"
          >
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
              <SparklesIcon className="h-5 w-5" />
            </div>
            <div className="max-w-[80%] rounded-lg p-3 bg-gray-50 text-gray-800">
              <div className="prose prose-sm max-w-none prose-gray prose-a:text-blue-600 prose-a:underline prose-a:font-medium hover:prose-a:text-blue-800">
                <ReactMarkdown
                  components={{
                    a({ href, children, ...props }) {
                      console.log('Rendering link in thinking message:', { href, children });
                      if (href && href.startsWith('/')) {
                        return (
                          <a
                            href={href}
                            className="text-blue-600 hover:text-blue-800 underline cursor-pointer font-medium"
                            onClick={(e) => {
                              e.preventDefault();
                              console.log('Navigating to:', href);
                              navigate(href);
                            }}
                            {...props}
                          >
                            {children}
                          </a>
                        );
                      }
                      return (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 underline"
                          {...props}
                        >
                          {children}
                        </a>
                      );
                    }
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            </div>
          </div>
        );
      } else {
        // Simple thinking message without markdown
        return (
          <div
            key={index}
            className="flex gap-3 justify-start mb-2"
          >
            <div className="flex-shrink-0 w-8"></div>
            <div className="max-w-[80%] text-gray-600 italic text-sm px-3 py-1">
              {message.content}
            </div>
          </div>
        );
      }
    }

    // For completion indicators, render a subtle success message
    if (isCompletionIndicator) {
      return (
        <div
          key={index}
          className="flex gap-3 justify-start mb-2"
        >
          <div className="flex-shrink-0 w-8"></div>
          <div className="text-green-600 text-sm px-3 py-1">
            {message.content}
          </div>
        </div>
      );
    }

    // For streaming chunks (legacy), render them differently - as inline thinking narration
    if (isStreamingChunk) {
      return (
        <div
          key={index}
          className="flex gap-3 justify-start mb-2"
        >
          <div className="flex-shrink-0 w-8"></div>
          <div className="max-w-[80%] text-gray-500 italic text-sm">
            {message.content}
          </div>
        </div>
      );
    }

    return (
      <div
        key={index}
        className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'} ${isToolCall ? 'mb-1.5' : 'mb-4'}`}
      >
        {!isUser && (
          <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
            isToolCall ? 'bg-slate-100 text-slate-500' : 'bg-blue-100'
          }`}>
            {icon}
          </div>
        )}

        <div
          className={`max-w-[80%] rounded-lg ${isToolCall ? 'px-3 py-2' : 'p-3'} ${
            isUser
              ? 'bg-blue-600 text-white'
              : message.isError
              ? 'bg-red-50 text-red-900 border border-red-200'
              : isCancelled
              ? 'bg-orange-50 text-orange-900 border border-orange-300 font-medium'
              : isStreaming
              ? 'bg-gray-50 text-gray-800 border border-gray-300 animate-pulse'
              : isToolCall
              ? 'bg-slate-50 text-slate-800 border border-slate-200'
              : isFinalResponse
              ? 'bg-green-50 text-green-900 border border-green-200'
              : 'bg-gray-50 text-gray-800'
          }`}
        >
          {isUser ? (
            <div className="whitespace-pre-wrap">{message.content}</div>
          ) : isToolCall && message.toolData ? (() => {
            const meta = getToolMeta(message.toolData.name);
            const summary = getToolSummary(message.toolData);
            const isRunning = !message.toolData.response && !message.toolData.detailed;
            const isComplete = !!message.toolData.response;
            const duration = formatDuration(
              message.toolData.startTime || message.timestamp,
              message.toolData.endTime
            );
            const hasInput = message.toolData.input && Object.keys(message.toolData.input).length > 0;

            return (
              <div className="space-y-1.5">
                {/* Header row: icon + label + summary + status */}
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`inline-flex items-center gap-1 text-xs font-semibold px-1.5 py-0.5 rounded bg-${meta.color}-100 text-${meta.color}-700 whitespace-nowrap`}>
                    {meta.label}
                  </span>
                  {summary && (
                    <code className="text-xs text-gray-600 truncate min-w-0 font-mono" title={summary}>
                      {summary}
                    </code>
                  )}
                  <span className="ml-auto flex-shrink-0">
                    {isRunning && (
                      <span className="text-xs text-blue-500 flex items-center gap-1 animate-pulse">
                        <span className="inline-block w-1.5 h-1.5 bg-blue-500 rounded-full"></span>
                        Running
                      </span>
                    )}
                    {isComplete && (
                      <span className="text-xs text-green-600 flex items-center gap-1">
                        <CheckIcon className="h-3 w-3" />
                        {duration || 'Done'}
                      </span>
                    )}
                    {!isRunning && !isComplete && (
                      <span className="text-xs text-gray-400">
                        <CheckIcon className="h-3 w-3" />
                      </span>
                    )}
                  </span>
                </div>

                {/* Expandable details */}
                {hasInput && (
                  <div>
                    <button
                      onClick={() => toggleToolRequest(index)}
                      className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-0.5"
                    >
                      {expandedToolRequest[index] ? (
                        <ChevronDownIcon className="h-3 w-3" />
                      ) : (
                        <ChevronRightIcon className="h-3 w-3" />
                      )}
                      Details
                    </button>
                    {expandedToolRequest[index] && (
                      <div className="mt-1 bg-white/70 rounded p-2 text-xs relative border border-gray-100">
                        <button
                          onClick={() => copyToolToClipboard(
                            JSON.stringify(message.toolData.input, null, 2),
                            `${index}-tool-request`
                          )}
                          className="absolute top-1.5 right-1.5 p-0.5 rounded bg-gray-100 hover:bg-gray-200 transition-colors"
                          title="Copy"
                        >
                          {copiedToolIndex === `${index}-tool-request` ? (
                            <CheckIcon className="h-3 w-3 text-green-600" />
                          ) : (
                            <ClipboardDocumentIcon className="h-3 w-3 text-gray-500" />
                          )}
                        </button>
                        <pre className="text-gray-600 whitespace-pre-wrap pr-6 font-mono text-[11px] leading-relaxed">
                          {JSON.stringify(message.toolData.input, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}

                {/* Response (if available) */}
                {message.toolData.response && (
                  <div>
                    <button
                      onClick={() => toggleToolResponse(index)}
                      className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-0.5"
                    >
                      {expandedToolResponse[index] ? (
                        <ChevronDownIcon className="h-3 w-3" />
                      ) : (
                        <ChevronRightIcon className="h-3 w-3" />
                      )}
                      Response
                    </button>
                    {expandedToolResponse[index] && (
                      <div className="mt-1 bg-white/70 rounded p-2 text-xs relative border border-gray-100">
                        <button
                          onClick={() => copyToolToClipboard(
                            typeof message.toolData.response === 'object'
                              ? JSON.stringify(message.toolData.response, null, 2)
                              : message.toolData.response,
                            `${index}-tool-response`
                          )}
                          className="absolute top-1.5 right-1.5 p-0.5 rounded bg-gray-100 hover:bg-gray-200 transition-colors"
                          title="Copy"
                        >
                          {copiedToolIndex === `${index}-tool-response` ? (
                            <CheckIcon className="h-3 w-3 text-green-600" />
                          ) : (
                            <ClipboardDocumentIcon className="h-3 w-3 text-gray-500" />
                          )}
                        </button>
                        <pre className="text-gray-600 whitespace-pre-wrap pr-6 font-mono text-[11px] leading-relaxed">
                          {typeof message.toolData.response === 'object'
                            ? JSON.stringify(message.toolData.response, null, 2)
                            : message.toolData.response}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })() : (
            <div className="prose prose-sm max-w-none prose-gray prose-a:text-blue-600 prose-a:underline prose-a:font-medium hover:prose-a:text-blue-800">
              <ReactMarkdown
                components={{
                  strong({ children, ...props }) {
                    // Custom strong/bold component to properly render nested content
                    return <strong {...props}>{children}</strong>;
                  },
                  em({ children, ...props }) {
                    // Custom em/italic component to properly render nested content
                    return <em {...props}>{children}</em>;
                  },
                  p({ children, ...props }) {
                    // Custom paragraph component to ensure proper rendering
                    return <p className="mb-2" {...props}>{children}</p>;
                  },
                  code({ node, inline, className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const codeString = String(children).replace(/\n$/, '');

                    if (!inline && match) {
                      return (
                        <div className="relative group">
                          <button
                            className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded bg-gray-700 hover:bg-gray-600 text-white"
                            onClick={() => copyToClipboard(codeString, `${index}-code`)}
                          >
                            {copiedIndex === `${index}-code` ? (
                              <CheckIcon className="h-4 w-4" />
                            ) : (
                              <ClipboardDocumentIcon className="h-4 w-4" />
                            )}
                          </button>
                          <SyntaxHighlighter
                            style={oneDark}
                            language={match[1]}
                            PreTag="div"
                            {...props}
                          >
                            {codeString}
                          </SyntaxHighlighter>
                        </div>
                      );
                    }

                    return (
                      <code className="bg-gray-200 px-1 py-0.5 rounded text-sm" {...props}>
                        {children}
                      </code>
                    );
                  },
                  a({ href, children, ...props }) {
                    // Debug logging for link rendering
                    console.log('Rendering link:', { href, children });

                    // Check if it's a relative path (starts with /)
                    if (href && href.startsWith('/')) {
                      // Internal navigation for relative paths
                      return (
                        <a
                          href={href}
                          className="text-blue-600 hover:text-blue-800 underline cursor-pointer font-medium"
                          onClick={(e) => {
                            e.preventDefault();
                            console.log('Navigating to:', href);
                            // Use React Router for internal navigation
                            navigate(href);
                          }}
                          {...props}
                        >
                          {children}
                        </a>
                      );
                    }
                    // Check if it's an absolute URL to the same origin
                    if (href && (href.includes(window.location.origin) || href.includes('/flow-designer'))) {
                      return (
                        <a
                          href={href}
                          className="text-blue-600 hover:text-blue-800 underline cursor-pointer"
                          onClick={(e) => {
                            e.preventDefault();
                            // Parse the URL and navigate internally
                            try {
                              const url = new URL(href, window.location.origin);
                              navigate(`${url.pathname}${url.search}`);
                            } catch (err) {
                              // If it's already a relative path, navigate directly
                              navigate(href);
                            }
                          }}
                          {...props}
                        >
                          {children}
                        </a>
                      );
                    }
                    // For external links, open in new tab
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:text-blue-800 underline"
                        {...props}
                      >
                        {children}
                      </a>
                    );
                  }
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {!isUser && (
            <div className="mt-2 space-y-2">
              <div className="flex gap-4">
                {/* Stream History Toggle */}
                {message.streamHistory && message.streamHistory.length > 0 && (
                  <button
                    className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1 transition-colors"
                    onClick={() => toggleStream(index)}
                  >
                    {expandedStream[index] ? (
                      <ChevronDownIcon className="h-3 w-3" />
                    ) : (
                      <ChevronRightIcon className="h-3 w-3" />
                    )}
                    View full stream
                  </button>
                )}

                {/* Execution Steps Toggle */}
                {message.executionSteps && message.executionSteps.length > 0 && (
                  <button
                    className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1 transition-colors"
                    onClick={() => toggleSteps(index)}
                  >
                    {expandedSteps[index] ? (
                      <ChevronDownIcon className="h-3 w-3" />
                    ) : (
                      <ChevronRightIcon className="h-3 w-3" />
                    )}
                    View {message.executionSteps.length} execution step{message.executionSteps.length > 1 ? 's' : ''}
                  </button>
                )}
              </div>

              {/* Expanded Stream History */}
              {expandedStream[index] && message.streamHistory && (
                <div className="mt-2 bg-purple-50 rounded-lg p-3">
                  <div className="text-xs font-semibold text-purple-700 mb-2">
                    Full Stream History:
                  </div>
                  <div className="space-y-1 text-xs">
                    {message.streamHistory.map((item, itemIndex) => (
                      <div key={itemIndex} className="whitespace-pre-wrap font-mono text-gray-700">
                        {item.content}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Expanded Execution Steps */}
              {expandedSteps[index] && message.executionSteps && (
                <div className="mt-2 bg-gray-50 rounded-lg p-3">
                  <div className="text-xs font-semibold text-gray-700 mb-2">
                    Execution Steps:
                  </div>
                  {message.executionSteps.map((step, stepIndex) =>
                    renderExecutionStep(step, stepIndex)
                  )}
                </div>
              )}

              {/* Copy Button */}
              <div className="flex justify-end">
                <button
                  className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
                  onClick={() => copyToClipboard(message.content, index)}
                >
                  {copiedIndex === index ? (
                    <>
                      <CheckIcon className="h-3 w-3" />
                      Copied
                    </>
                  ) : (
                    <>
                      <ClipboardDocumentIcon className="h-3 w-3" />
                      Copy
                    </>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {isUser && (
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center text-white">
            {icon}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-2">
      {messages.length === 0 ? (
        <div className="text-center text-gray-500 py-8">
          <SparklesIcon className="h-12 w-12 mx-auto mb-3 opacity-50" />
          <p>No messages yet. Start a conversation!</p>
        </div>
      ) : (
        messages.map((message, index) => renderMessage(message, index, messages))
      )}
    </div>
  );
}

export default MessageList;