import React, { useState, useRef, useEffect } from 'react';
import MessageList from './MessageList';
import EnhancedInputControls from './EnhancedInputControls';
import StreamingIndicator from './StreamingIndicator';

function AssistantChat({
  messages,
  isStreaming,
  onSendMessage,
  onCancel,
  disabled,
  placeholder
}) {
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Auto-focus input when streaming stops (response completes)
  useEffect(() => {
    if (!isStreaming && inputRef.current) {
      // Small delay to ensure UI has updated
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  }, [isStreaming]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = () => {
    if (inputText.trim() && !isStreaming && !disabled) {
      // The EnhancedInputControls handles navigation internally
      // This will only be called for non-navigation messages
      onSendMessage(inputText);
      setInputText('');
      // Focus back on input after sending
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const handleCancel = () => {
    if (isStreaming && onCancel) {
      onCancel();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4">
        <MessageList messages={messages} />
        {isStreaming && <StreamingIndicator />}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="border-t bg-white p-4">
        <EnhancedInputControls
          ref={inputRef}
          value={inputText}
          onChange={setInputText}
          onSend={handleSend}
          onCancel={handleCancel}
          isStreaming={isStreaming}
          disabled={disabled}
          placeholder={placeholder || 'Type a page name to navigate or ask a question...'}
        />
      </div>
    </div>
  );
}

export default AssistantChat;