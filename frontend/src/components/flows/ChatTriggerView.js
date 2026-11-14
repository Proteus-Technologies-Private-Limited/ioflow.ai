import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  PaperAirplaneIcon,
  ArrowPathIcon,
  StopIcon,
  ChatBubbleLeftRightIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  WrenchIcon,
  UserIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

/**
 * ChatTriggerView - Chat interface for flows with chat_input trigger type.
 *
 * Provides:
 * - Message list with streaming support
 * - Collapsible tool call details
 * - Input textarea with send button
 * - Session management (new chat, end chat)
 * - Auto-scroll and auto-focus behaviors
 */
const ChatTriggerView = ({
  flow,
  onSendMessage,
  isExecuting,
  messages = [],
  chatSessionId,
  onNewSession,
  onEndSession,
  error,
}) => {
  const [inputText, setInputText] = useState('');
  const [expandedToolCalls, setExpandedToolCalls] = useState({});
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Get placeholder and welcome message from trigger config
  const triggerNode = flow?.flow_definition?.nodes?.find(n => n.type === 'trigger');
  const triggerConfig = flow?.trigger_config || {};
  const placeholder = triggerNode?.data?.placeholderText || triggerConfig.placeholder_text || 'Type your message...';
  const welcomeMessage = triggerNode?.data?.welcomeMessage || triggerConfig.welcome_message || '';

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-focus input when not executing
  useEffect(() => {
    if (!isExecuting && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isExecuting]);

  const handleSend = useCallback(() => {
    if (inputText.trim() && !isExecuting) {
      onSendMessage(inputText.trim());
      setInputText('');
    }
  }, [inputText, isExecuting, onSendMessage]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleToolCall = (messageIndex) => {
    setExpandedToolCalls(prev => ({
      ...prev,
      [messageIndex]: !prev[messageIndex]
    }));
  };

  // Render a single message
  const renderMessage = (message, index) => {
    const isUser = message.role === 'user';
    const hasToolCalls = message.toolCalls && message.toolCalls.length > 0;

    return (
      <div
        key={index}
        className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
      >
        {/* Avatar */}
        <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? 'bg-blue-100' : 'bg-purple-100'
        }`}>
          {isUser ? (
            <UserIcon className="w-5 h-5 text-blue-600" />
          ) : (
            <SparklesIcon className="w-5 h-5 text-purple-600" />
          )}
        </div>

        {/* Message content */}
        <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : 'text-left'}`}>
          <div className={`inline-block px-4 py-2 rounded-lg ${
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-900'
          }`}>
            {message.isStreaming ? (
              <div className="flex items-center gap-2">
                <ArrowPathIcon className="w-4 h-4 animate-spin" />
                <span className="text-sm">Thinking...</span>
              </div>
            ) : isUser ? (
              <div className="whitespace-pre-wrap">{message.content}</div>
            ) : (
              <div className="prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown
                  components={{
                    code({ node, inline, className, children, ...props }) {
                      const match = /language-(\w+)/.exec(className || '');
                      return !inline && match ? (
                        <SyntaxHighlighter
                          style={oneDark}
                          language={match[1]}
                          PreTag="div"
                          {...props}
                        >
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                      ) : (
                        <code className={`${className} bg-gray-200 px-1 py-0.5 rounded`} {...props}>
                          {children}
                        </code>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {/* Collapsible tool calls section */}
          {hasToolCalls && !isUser && (
            <div className="mt-2">
              <button
                onClick={() => toggleToolCall(index)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700"
              >
                {expandedToolCalls[index] ? (
                  <ChevronDownIcon className="w-3 h-3" />
                ) : (
                  <ChevronRightIcon className="w-3 h-3" />
                )}
                <WrenchIcon className="w-3 h-3" />
                <span>{message.toolCalls.length} tool call{message.toolCalls.length > 1 ? 's' : ''}</span>
              </button>

              {expandedToolCalls[index] && (
                <div className="mt-2 space-y-2">
                  {message.toolCalls.map((toolCall, toolIndex) => (
                    <div
                      key={toolIndex}
                      className="bg-gray-50 border border-gray-200 rounded-md p-2 text-xs"
                    >
                      <div className="font-medium text-gray-700">{toolCall.name}</div>
                      {toolCall.args && (
                        <div className="mt-1 text-gray-500">
                          <div className="font-medium">Input:</div>
                          <pre className="mt-1 bg-gray-100 p-1 rounded overflow-x-auto">
                            {typeof toolCall.args === 'object'
                              ? JSON.stringify(toolCall.args, null, 2)
                              : toolCall.args}
                          </pre>
                        </div>
                      )}
                      {toolCall.result && (
                        <div className="mt-1 text-gray-500">
                          <div className="font-medium">Output:</div>
                          <pre className="mt-1 bg-gray-100 p-1 rounded overflow-x-auto max-h-32 overflow-y-auto">
                            {typeof toolCall.result === 'object'
                              ? JSON.stringify(toolCall.result, null, 2)
                              : toolCall.result}
                          </pre>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Timestamp */}
          {message.timestamp && (
            <div className={`text-xs text-gray-400 mt-1 ${isUser ? 'text-right' : 'text-left'}`}>
              {new Date(message.timestamp).toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Session Info Header */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b">
        <div className="flex items-center gap-2">
          <ChatBubbleLeftRightIcon className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-600">
            {chatSessionId ? (
              <>Session: <span className="font-mono">{chatSessionId.slice(0, 8)}...</span></>
            ) : (
              'New Conversation'
            )}
          </span>
          {messages.length > 0 && (
            <span className="text-xs text-gray-400">
              ({messages.length} message{messages.length !== 1 ? 's' : ''})
            </span>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onNewSession}
            disabled={isExecuting}
            className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400
                       flex items-center gap-1 px-2 py-1 rounded hover:bg-blue-50"
            title="Start new conversation"
          >
            <ArrowPathIcon className="w-4 h-4" />
            New Chat
          </button>
          {chatSessionId && (
            <button
              onClick={onEndSession}
              disabled={isExecuting}
              className="text-sm text-red-600 hover:text-red-800 disabled:text-gray-400
                         flex items-center gap-1 px-2 py-1 rounded hover:bg-red-50"
              title="End conversation"
            >
              <StopIcon className="w-4 h-4" />
              End Chat
            </button>
          )}
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-400">
            {welcomeMessage ? (
              <>
                <div className="flex gap-3 w-full max-w-[80%]">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-purple-100">
                    <SparklesIcon className="w-5 h-5 text-purple-600" />
                  </div>
                  <div className="flex-1">
                    <div className="inline-block px-4 py-2 rounded-lg bg-gray-100 text-gray-900">
                      <p className="whitespace-pre-wrap">{welcomeMessage}</p>
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <>
                <ChatBubbleLeftRightIcon className="w-12 h-12 mb-2" />
                <p className="text-sm">Start a conversation</p>
                <p className="text-xs mt-1">Type a message below to begin</p>
              </>
            )}
          </div>
        ) : (
          messages.map((message, index) => renderMessage(message, index))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Error Display */}
      {error && (
        <div className="px-4 py-2 bg-red-50 border-t border-red-200">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {/* Input Area */}
      <div className="border-t bg-white p-4">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              disabled={isExecuting}
              className="w-full resize-none border border-gray-300 rounded-lg px-3 py-2 pr-10
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       disabled:bg-gray-100 disabled:cursor-not-allowed
                       min-h-[44px] max-h-[120px]"
              rows={1}
              style={{
                height: 'auto',
                minHeight: '44px',
              }}
              onInput={(e) => {
                e.target.style.height = 'auto';
                e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
              }}
            />
          </div>
          <button
            onClick={handleSend}
            disabled={!inputText.trim() || isExecuting}
            className="flex-shrink-0 px-4 py-2 bg-blue-600 text-white rounded-lg
                     hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed
                     transition-colors flex items-center justify-center h-[44px] w-[44px]"
          >
            {isExecuting ? (
              <ArrowPathIcon className="w-5 h-5 animate-spin" />
            ) : (
              <PaperAirplaneIcon className="w-5 h-5" />
            )}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
};

export default ChatTriggerView;
