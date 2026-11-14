import React, { forwardRef, useEffect, useRef } from 'react';
import {
  PaperAirplaneIcon,
  StopCircleIcon
} from '@heroicons/react/24/solid';

const InputControls = forwardRef(({
  value,
  onChange,
  onSend,
  onCancel,
  onKeyDown,
  isStreaming,
  disabled,
  placeholder
}, ref) => {
  const textareaRef = useRef(null);

  // Combine refs
  useEffect(() => {
    if (ref) {
      ref.current = textareaRef.current;
    }
  }, [ref]);

  // Auto-resize textarea based on content
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      // Reset height to auto to get the correct scrollHeight
      textarea.style.height = 'auto';

      // Calculate new height
      const scrollHeight = textarea.scrollHeight;
      const minHeight = 44; // Minimum height for single line
      const maxHeight = 200; // Maximum height before scrolling

      // Set the new height
      const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
      textarea.style.height = `${newHeight}px`;

      // Add or remove scrollbar based on content
      if (scrollHeight > maxHeight) {
        textarea.style.overflowY = 'auto';
      } else {
        textarea.style.overflowY = 'hidden';
      }
    }
  }, [value]);

  return (
    <div className="flex gap-2 items-end">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        disabled={disabled || isStreaming}
        className="flex-1 resize-none px-3 py-2.5 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500 transition-all duration-150"
        style={{
          minHeight: '44px',
          maxHeight: '200px',
          overflowY: 'hidden'
        }}
        rows={1}
      />
      {isStreaming ? (
        <button
          onClick={onCancel}
          className="h-[44px] w-[44px] bg-red-600 hover:bg-red-700 text-white rounded-md flex items-center justify-center transition-colors flex-shrink-0"
        >
          <StopCircleIcon className="h-5 w-5" />
        </button>
      ) : (
        <button
          onClick={onSend}
          disabled={disabled || !value.trim()}
          className="h-[44px] w-[44px] bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-md flex items-center justify-center transition-colors flex-shrink-0"
        >
          <PaperAirplaneIcon className="h-5 w-5" />
        </button>
      )}
    </div>
  );
});

InputControls.displayName = 'InputControls';

export default InputControls;